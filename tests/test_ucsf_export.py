"""Final spectrum -> Sparky UCSF conversion test (0.2.162-patch15)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from workflow.ucsf_export import export_ucsf


def test_stepwise_export_ucsf_skips_1d_ft1(monkeypatch) -> None:
    """
    0.2.199-patch29gj-fix: a 1D final spectrum (.ft1) does not call pipe2ucsf, it is
    skipped.
    """
    import workflow.stepwise as stepwise

    called: list[str] = []
    manager = SimpleNamespace()

    def _boom(*args, **kwargs):
        called.append("export")
        return "boom", "boom"

    monkeypatch.setattr(stepwise, "export_ucsf", _boom)
    path, message = stepwise._export_ucsf(
        manager, "exp_001", "d_001", "d_001.ft1"
    )
    assert path is None
    assert "1D" in message
    assert not called


def test_export_ucsf_runs_pipe2ucsf_and_writes_target(tmp_path: Path) -> None:
    """pipe2ucsf succeeds: the call arguments are correct and the UCSF path is returned."""
    source = tmp_path / "d_001.ft2"
    source.write_bytes(b"pipe")
    target = tmp_path / "d_001.ucsf"
    calls: list[list[str]] = []

    def fake_run(argv, cwd=None, timeout=None):
        calls.append(argv)
        target.write_bytes(b"ucsf-data")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    path, message = export_ucsf(source, target, run=fake_run)
    assert path == str(target)
    assert "UCSF 已生成" in message
    assert calls[0][0] == "pipe2ucsf"
    assert str(source) in calls[0][1]
    assert str(target) in calls[0][2]


def test_export_ucsf_uses_configured_executable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "d_001.ft2"
    source.write_bytes(b"pipe")
    target = tmp_path / "d_001.ucsf"
    configured = tmp_path / "tools with spaces" / "pipe2ucsf"
    configured.parent.mkdir()
    configured.touch()
    calls: list[list[str]] = []

    class FakeRuntime:
        def run(self, argv, **kwargs):
            calls.append(argv)
            target.write_bytes(b"ucsf")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("backend.runtime.CshRuntime", FakeRuntime)
    from gui import settings as gui_settings

    monkeypatch.setattr(
        gui_settings, "load_settings", lambda: {"pipe2ucsf_path": str(configured)}
    )
    path, _ = export_ucsf(source, target)
    assert path == str(target)
    assert calls[0][0] == str(configured.resolve())


def test_export_ucsf_bash_only_tool_runs_in_bash_login_environment(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "d_001.ft2"
    source.write_bytes(b"pipe")
    target = tmp_path / "d_001.ucsf"
    tool = tmp_path / "bash tools" / "pipe2ucsf"
    tool.parent.mkdir()
    tool.touch()
    calls = []

    monkeypatch.setattr("backend.nmrpipe_finder._csh_which", lambda _name: None)
    monkeypatch.setattr("backend.nmrpipe_finder._bash_which", lambda _name: str(tool))
    monkeypatch.setattr("backend.nmrpipe_finder.shutil.which", lambda _name: "/bin/bash")

    class FakeRuntime:
        def run(self, argv, **kwargs):
            calls.append((argv, kwargs))
            target.write_bytes(b"ucsf")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("backend.runtime.CshRuntime", FakeRuntime)
    from gui import settings as gui_settings

    monkeypatch.setattr(
        gui_settings, "load_settings", lambda: {"pipe2ucsf_path": str(tool)}
    )
    path, _ = export_ucsf(source, target)
    assert path == str(target)
    assert calls[0][0][0:2] == ["/bin/bash", "-lic"]
    assert str(tool) in calls[0][0][2]


def test_export_ucsf_failure_returns_none_and_cleans_partial(tmp_path: Path) -> None:
    """pipe2ucsf fails: None is returned and the leftover partial file is cleaned up."""
    source = tmp_path / "d_001.ft3"
    source.write_bytes(b"pipe")
    target = tmp_path / "d_001.ucsf"

    def fake_run(argv, cwd=None, timeout=None):
        target.write_bytes(b"partial")
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    path, message = export_ucsf(source, target, run=fake_run)
    assert path is None
    assert "转换失败" in message and "boom" in message
    assert not target.exists()


def test_export_ucsf_exception_removes_stale_target(tmp_path: Path) -> None:
    """SMILE-005: when the conversion fails to start, no stale UCSF may be left behind posing as
    the current spectrum's companion product."""
    source = tmp_path / "d_001.ft2"
    target = tmp_path / "d_001.ucsf"
    source.write_bytes(b"new-spectrum")
    target.write_bytes(b"stale-ucsf")

    def failed_run(*args, **kwargs):
        raise OSError("pipe2ucsf missing")

    path, message = export_ucsf(source, target, run=failed_run)
    assert path is None
    assert "执行失败" in message
    assert not target.exists()


def test_export_ucsf_missing_source_skips(tmp_path: Path) -> None:
    """Source spectrum does not exist: skip, do not call the tool."""
    path, message = export_ucsf(
        tmp_path / "missing.ft2", tmp_path / "missing.ucsf"
    )
    assert path is None
    assert "源谱不存在" in message


def test_export_ucsf_missing_tool_degrades_gracefully(
    tmp_path: Path, monkeypatch
) -> None:
    """No csh/pipe2ucsf here (e.g. a Windows dev box): degrade to None, no exception."""
    source = tmp_path / "d_001.ft2"
    source.write_bytes(b"pipe")
    target = tmp_path / "d_001.ucsf"

    class _MissingCsh:
        def run(self, *args, **kwargs):
            raise RuntimeError("本机未找到 tcsh/csh")

    monkeypatch.setattr("backend.runtime.CshRuntime", _MissingCsh)
    path, message = export_ucsf(source, target)
    assert path is None
    assert "跳过 UCSF 转换" in message
