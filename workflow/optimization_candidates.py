"""Validate explicit reference candidate pools before running any processing."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


class CandidateSelectionError(RuntimeError):
    """An explicit pool cannot produce a valid choice; default fallback is forbidden."""


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _keys(value: Any, allowed: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown {name} keys: {sorted(map(str, unknown))}")
    return dict(value)


def _pool(value: Any, name: str, normalize: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{name} must be a non-empty candidate list")
    output = []
    for item in value:
        candidate = normalize(item)
        if candidate not in output:
            output.append(candidate)
    return output


def _window(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("type"), str):
        raise ValueError("Each window candidate must specify a string type")
    kind = value["type"].lower()
    aliases = {"off": "none", "sp": "sine_bell", "gm": "gaussian", "em": "exp"}
    kind = aliases.get(kind, kind)
    if kind == "none":
        _keys(value, {"type"}, "none window")
        return {"type": "none"}
    if kind in {"sine_bell", "sine_bell_squared"}:
        cfg = _keys(value, {"type", "off", "end", "pow", "c"}, "SP window")
        off = _number(cfg.get("off", 0.45), "window.off")
        end = _number(cfg.get("end", 0.95), "window.end")
        power = _number(cfg.get("pow", 2 if kind == "sine_bell_squared" else 1), "window.pow")
        scale = _number(cfg.get("c", 0.5), "window.c")
        if not (0 <= off <= 1 and 0 <= end <= 1 and power >= 0 and scale >= 0):
            raise ValueError("SP requires off/end in [0,1] and non-negative pow/c")
        if kind == "sine_bell_squared" and power != 2:
            raise ValueError("sine_bell_squared requires pow=2")
        return {"type": "sine_bell", "off": off, "end": end, "pow": power, "c": scale}
    if kind == "gaussian":
        cfg = _keys(value, {"type", "g1", "g2", "g3", "c"}, "GM window")
        if _number(cfg.get("g3", 0), "window.g3") != 0 or _number(cfg.get("c", 1), "window.c") != 1:
            raise ValueError("Automatic GM candidates currently require g3=0 and c=1")
        return {
            "type": kind,
            "g1": _number(cfg.get("g1", 8), "window.g1"),
            "g2": _number(cfg.get("g2", 15), "window.g2"),
            "g3": 0.0,
            "c": 1.0,
        }
    if kind == "exp":
        cfg = _keys(value, {"type", "lb", "c"}, "EM window")
        if _number(cfg.get("c", 1), "window.c") != 1:
            raise ValueError("Automatic EM candidates currently require c=1")
        return {"type": kind, "lb": _number(cfg.get("lb", 5), "window.lb"), "c": 1.0}
    raise ValueError(f"Unsupported window candidate type: {value['type']}")


def _baseline(value: Any) -> dict[str, Any]:
    cfg = _keys(value, {"mode", "order"}, "baseline candidate")
    mode = cfg.get("mode")
    order = cfg.get("order", 0)
    if isinstance(order, bool) or not isinstance(order, int):
        raise ValueError("baseline.order must be an integer")
    if mode == "off" and order == 0:
        return {"mode": "off", "order": 0}
    if mode == "auto" and order in (0, 1):
        return {"mode": "auto", "order": 1}
    if mode == "order" and order >= 1:
        return {"mode": "order", "order": order}
    raise ValueError("Baseline candidates require off:0, auto:0/1 or order:<positive integer>")


def normalize_optimization_candidates(value: Any) -> dict[str, Any]:
    cfg = _keys(value, {"window", "baseline"}, "optimization_candidates")
    output: dict[str, Any] = {}
    if "baseline" in cfg:
        output["baseline"] = _pool(cfg["baseline"], "baseline", _baseline)
    if "window" in cfg:
        window = _keys(cfg["window"], {"direct", "indirect"}, "window candidates")
        if not window:
            raise ValueError("window candidates must specify direct and/or indirect")
        output["window"] = {
            key: _pool(pool, f"window.{key}", _window) for key, pool in window.items()
        }
    return output


def validate_candidate_context(params: Mapping[str, Any], experiment: Any = None) -> None:
    pools = params.get("optimization_candidates") or {}
    if not pools:
        return
    if params.get("phase_route") == "none" or (experiment is not None and experiment.ndim == 1):
        raise ValueError(
            "optimization_candidates requires the unified reference optimisation route"
        )
    switches = params.get("reference_optimize") or {}
    if not isinstance(switches, Mapping):
        raise ValueError("reference_optimize must be a mapping")
    for stage in pools:
        if stage in switches:
            raise ValueError(
                f"optimization_candidates.{stage} conflicts with reference_optimize.{stage}"
            )
    if experiment is not None and str(experiment.sampling.mode) == "nus":
        direct = (pools.get("window") or {}).get("direct", [])
        if any(cfg["type"] != "sine_bell" for cfg in direct):
            raise ValueError(
                "NUS direct-window candidates must use SP (sine_bell); SMILE requires it"
            )


def candidate_switches(params: Mapping[str, Any]) -> dict[str, Any]:
    switches = dict(params.get("reference_optimize") or {})
    pools = params.get("optimization_candidates")
    if pools is None:
        return switches
    pools = normalize_optimization_candidates(pools)
    validate_candidate_context({**params, "optimization_candidates": pools})
    if "baseline" in pools:
        switches["baseline"] = {
            "grid": [[cfg["mode"], cfg["order"]] for cfg in pools["baseline"]],
            "strict_candidates": True,
        }
    if "window" in pools:
        switches["window"] = {key + "_candidates": pool for key, pool in pools["window"].items()}
        switches["window"].update({key + "_strict": True for key in pools["window"]})
    return switches
