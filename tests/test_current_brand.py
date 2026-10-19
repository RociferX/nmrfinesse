"""Current product paths and public package names."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from core import app_paths, version, workspace
from core.project import recent
from core.project.manager import ProjectManager


def test_current_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert app_paths.local_config_path(packaged=True) == (
        tmp_path / ".config" / "NMRFinesse" / "nmrfinesse.local.yaml"
    )


def test_current_workspace_and_trash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert workspace.default_workspace_path() == tmp_path / "NMRFinesseWorkspace"
    assert ProjectManager(tmp_path)._trash_dir() == tmp_path / ".nmrfinesse_trash"
    assert workspace._trash_path(tmp_path) == tmp_path / ".nmrfinesse_trash"


def test_current_recent_projects_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recent, "default_config_dir", lambda: tmp_path / "NMRFinesse")
    store = recent.JsonRecentProjectsStore()
    store.push("project")
    assert store.path == tmp_path / "NMRFinesse" / "recent_projects.json"
    assert json.loads(store.path.read_text(encoding="utf-8")) == {"projects": ["project"]}


def test_current_tool_version_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version, "software_version", lambda: "1.2.3")
    monkeypatch.setattr(version, "dependency_versions", lambda: {})
    monkeypatch.setattr(version, "registered_tool_versions", lambda: {})
    monkeypatch.setattr(version, "software_commit", lambda: "")
    assert version.tool_versions() == {"nmrfinesse": "1.2.3"}


def test_current_distribution_and_api_names() -> None:
    import nmrfinesse_api
    from nmrfinesse_api.compat import COMPAT_SCHEMA
    from nmrfinesse_api.optimization_scores import SCORE_SCHEMA

    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["name"] == "nmrfinesse"
    assert set(metadata["project"]["scripts"]) == {"nmrfinesse-viewer"}
    assert COMPAT_SCHEMA == "nmrfinesse_api.compat.v1"
    assert SCORE_SCHEMA == "nmrfinesse_api.reference_optimization_scores.v1"
    assert nmrfinesse_api.API_VERSION == "1.1.5"
