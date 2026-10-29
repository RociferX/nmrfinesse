"""NMRPipe discovery logic tests."""

from __future__ import annotations

import shlex
from pathlib import Path

from backend.nmrpipe_finder import (
    bash_environment_csh_command,
    find_nmrpipe_bin,
    find_pipe2ucsf,
    find_tool,
)


def test_find_nmrpipe_bin_explicit(tmp_path: Path) -> None:
    bin_dir = tmp_path / "nmrbin.test"
    bin_dir.mkdir()
    (bin_dir / "nmrPipe").write_text("#!/bin/csh\n", encoding="utf-8")
    found = find_nmrpipe_bin(explicit=str(bin_dir))
    assert found is not None
    assert (found / "nmrPipe").is_file()


def test_find_nmrpipe_bin_explicit_missing(tmp_path: Path) -> None:
    assert find_nmrpipe_bin(explicit=str(tmp_path)) is None


def test_find_tool_via_com_dir(tmp_path: Path) -> None:
    bin_dir = tmp_path / "nmrbin.test"
    com_dir = tmp_path / "com"
    bin_dir.mkdir()
    com_dir.mkdir()
    (bin_dir / "nmrPipe").write_text("#!/bin/csh\n", encoding="utf-8")
    (com_dir / "bruker").write_text("#!/bin/csh\n", encoding="utf-8")
    found = find_tool("bruker", nmrpipe_bin=bin_dir)
    assert found is not None
    assert found.name == "bruker"


def test_find_pipe2ucsf_prefers_csh_then_bash(tmp_path: Path, monkeypatch) -> None:
    csh_tool = tmp_path / "csh tools" / "pipe2ucsf"
    bash_tool = tmp_path / "bash tools" / "pipe2ucsf"
    csh_tool.parent.mkdir()
    bash_tool.parent.mkdir()
    csh_tool.touch()
    bash_tool.touch()
    bash_calls: list[str] = []
    monkeypatch.setattr("backend.nmrpipe_finder._csh_which", lambda _name: str(csh_tool))
    monkeypatch.setattr(
        "backend.nmrpipe_finder._bash_which",
        lambda name: bash_calls.append(name) or str(bash_tool),
    )
    assert find_pipe2ucsf() == csh_tool.resolve()
    assert bash_calls == []

    monkeypatch.setattr("backend.nmrpipe_finder._csh_which", lambda _name: None)
    assert find_pipe2ucsf() == bash_tool.resolve()


def test_bash_which_uses_interactive_login_and_extracts_marker(monkeypatch) -> None:
    from types import SimpleNamespace

    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(
            returncode=0,
            stdout="bash startup notice\n__NMRFINESSE_TOOL_PATH__=/opt/nmr bin/pipe2ucsf\n",
        )

    monkeypatch.setattr("backend.nmrpipe_finder.shutil.which", lambda name: "/bin/bash")
    monkeypatch.setattr("backend.nmrpipe_finder.subprocess.run", fake_run)
    from backend.nmrpipe_finder import _bash_which

    assert _bash_which("pipe2ucsf") == "/opt/nmr bin/pipe2ucsf"
    assert calls[0][1] == "-lic"


def test_find_pipe2ucsf_explicit_path_wins(tmp_path: Path, monkeypatch) -> None:
    explicit = tmp_path / "my tools" / "pipe2ucsf"
    explicit.parent.mkdir()
    explicit.touch()
    monkeypatch.setattr("backend.nmrpipe_finder._csh_which", lambda _name: None)
    monkeypatch.setattr("backend.nmrpipe_finder._bash_which", lambda _name: None)
    assert find_pipe2ucsf(str(explicit)) == explicit.resolve()


def test_find_pipe2ucsf_explicit_cached_bash_path_keeps_bash_origin(
    tmp_path: Path, monkeypatch
) -> None:
    tool = tmp_path / "bash tools" / "pipe2ucsf"
    tool.parent.mkdir()
    tool.touch()
    monkeypatch.setattr("backend.nmrpipe_finder._csh_which", lambda _name: None)
    monkeypatch.setattr("backend.nmrpipe_finder._bash_which", lambda _name: str(tool))
    assert find_pipe2ucsf(str(tool)) == tool.resolve()
    from backend.nmrpipe_finder import find_pipe2ucsf_with_shell

    assert find_pipe2ucsf_with_shell(str(tool)) == (tool.resolve(), "bash")


def test_bash_environment_bridge_quotes_directory_and_limits_transferred_vars(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "backend.nmrpipe_finder.shutil.which",
        lambda name: "/bin/bash" if name == "bash" else None,
    )
    csh_path = str(tmp_path / "csh $bang! path")
    argv = bash_environment_csh_command(str(tmp_path / "a path"), csh_path)
    assert argv is not None
    script = argv[-1]
    assert "cd '" in script and "a path'" in script
    assert 'PATH="$PATH"' in script
    assert "NMR_PLUGIN_EXE" in script and "NMR_PLUGIN_FN" in script
    assert "-lic" in argv
    assert "-if" in script
    assert shlex.quote(csh_path) in script
    assert "setenv PATH \"${PATH}:$NMRFINESSE_BASH_PATH\"" in script
    assert script.index("source ~/.cshrc") < script.index("setenv PATH")
