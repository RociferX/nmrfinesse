"""Explicit candidate pools are exclusive and cannot silently return default settings."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core.data.bruker_reader import read_dataset
from workflow.optimization_candidates import (
    CandidateSelectionError,
    candidate_switches,
    normalize_optimization_candidates,
    validate_candidate_context,
)
from workflow.window_optimize import optimize_direct_window


def test_normalize_candidates_completes_deduplicates_and_preserves_order() -> None:
    pools = normalize_optimization_candidates(
        {
            "window": {
                "direct": [
                    {"type": "sp", "off": 0.3},
                    {"type": "sine_bell", "off": 0.3},
                    {"type": "sine_bell_squared"},
                ]
            },
            "baseline": [{"mode": "auto", "order": 0}, {"mode": "auto", "order": 1}],
        }
    )
    assert pools["window"]["direct"] == [
        {"type": "sine_bell", "off": 0.3, "end": 0.95, "pow": 1.0, "c": 0.5},
        {"type": "sine_bell", "off": 0.45, "end": 0.95, "pow": 2.0, "c": 0.5},
    ]
    assert pools["baseline"] == [{"mode": "auto", "order": 1}]
    switches = candidate_switches({"optimization_candidates": pools})
    assert switches["window"]["direct_candidates"] == pools["window"]["direct"]
    assert "indirect_candidates" not in switches["window"]
    assert switches["baseline"]["grid"] == [["auto", 1]]


@pytest.mark.parametrize(
    "pools",
    [
        {"window": {"direct": []}},
        {"baseline": []},
        {"window": {}},
        {"other": []},
        {"window": {"F1": [{"type": "none"}]}},
        {"window": {"direct": [{"type": "none", "off": 0.3}]}},
        {"window": {"direct": [{"type": "sp", "end": float("nan")}]}},
        {"window": {"direct": [{"type": "sp", "off": True}]}},
        {"window": {"direct": [{"type": "sp", "end": 1.2}]}},
        {"window": {"direct": [{"type": "gaussian", "g3": 0.5}]}},
        {"window": {"direct": [{"type": "exp", "c": 0.5}]}},
        {"window": {"direct": [{"type": "sine_bell_squared", "pow": 1}]}},
        {"baseline": [{"mode": "auto", "order": 2}]},
        {"baseline": [{"mode": "order", "order": True}]},
        {"baseline": [{"mode": "order", "order": 1.2}]},
    ],
)
def test_invalid_pools_fail_before_selection(pools: dict) -> None:
    with pytest.raises(ValueError):
        normalize_optimization_candidates(pools)


def test_context_conflicts_and_nus_direct_window_validation(bruker_dir: Path) -> None:
    pools = {"window": {"direct": [{"type": "none"}]}}
    params = {"optimization_candidates": normalize_optimization_candidates(pools)}
    experiment = read_dataset(bruker_dir / "nus_2d")
    with pytest.raises(ValueError, match="NUS direct-window"):
        validate_candidate_context(params, experiment)
    with pytest.raises(ValueError, match="unified"):
        validate_candidate_context({**params, "phase_route": "none"})
    with pytest.raises(ValueError, match="conflicts"):
        validate_candidate_context({**params, "reference_optimize": {"window": "off"}})


def test_window_selection_is_only_from_explicit_pool_and_has_no_fallback() -> None:
    rng = np.random.default_rng(43)
    t = np.arange(256)
    fid = np.tile(np.exp(-t / 80) * np.exp(2j * np.pi * 0.12 * t), (8, 1))
    fid += 0.01 * (rng.normal(size=fid.shape) + 1j * rng.normal(size=fid.shape))
    pool = normalize_optimization_candidates(
        {
            "window": {
                "direct": [
                    {"type": "sp", "off": 0.37, "end": 0.97, "pow": 1.3},
                    {"type": "sp", "off": 0.41, "end": 0.96, "pow": 1.1},
                ]
            }
        }
    )["window"]["direct"]
    result = optimize_direct_window(fid, candidates=pool, sw=6000, strict_candidates=True)
    assert result.choice in pool
    assert [row["cfg"] for row in result.scores] == pool
    assert sum(row["selected"] for row in result.scores) == 1
    selected = next(row for row in result.scores if row["selected"])
    assert selected["cfg"] == result.choice
    assert selected["score"] == max(row["score"] for row in result.scores)
    with pytest.raises(CandidateSelectionError, match="No valid explicit"):
        optimize_direct_window(np.zeros_like(fid), candidates=pool, strict_candidates=True)
