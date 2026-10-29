"""Locate NMRPipe on this machine (Linux).

Search order (user requirement: trust the nmrpipe the csh environment really answers with):
1. an explicitly configured path (a directory or the executable itself);
2. ``which nmrPipe`` after ``source ~/.cshrc`` in csh/tcsh (the NMRPipe environment lives in
   ~/.cshrc);
3. shutil.which as a last resort.

Note: the NMRPipe executable is the case-sensitive ``nmrPipe``.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path


def _csh_which(name: str) -> str | None:
    """Find an executable path inside the csh login environment (source ~/.cshrc)."""
    shell = shutil.which("tcsh") or shutil.which("csh")
    if shell is None:
        return None
    script = f"if (-e ~/.cshrc) source ~/.cshrc; which {name}"
    try:
        proc = subprocess.run(
            [shell, "-c", script],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "/" in line and "not found" not in line and "no " not in line.lower():
            return line
    return None


def _bash_which(name: str) -> str | None:
    """Find a tool in interactive login bash when csh is unavailable."""
    shell = shutil.which("bash")
    if shell is None:
        return None
    try:
        marker = "__NMRFINESSE_TOOL_PATH__="
        proc = subprocess.run(
            [shell, "-lic", f"printf '\\n{marker}%s\\n' \"$(command -v {name})\""],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(marker):
            return line.removeprefix(marker).strip() or None
    return None


def find_pipe2ucsf_with_shell(
    explicit: str = "",
) -> tuple[Path | None, str | None]:
    """Find pipe2ucsf and return its configured, csh, or bash environment."""
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_dir():
            path = path / "pipe2ucsf"
        if path.is_file():
            resolved = path.resolve()
            csh_path = _csh_which("pipe2ucsf")
            if csh_path and Path(csh_path).expanduser().resolve() == resolved:
                return resolved, "csh"
            bash_path = _bash_which("pipe2ucsf")
            if bash_path and Path(bash_path).expanduser().resolve() == resolved:
                return resolved, "bash"
            return resolved, "configured"
    found = _csh_which("pipe2ucsf")
    if found:
        path = Path(found).expanduser()
        if path.is_file():
            return path.resolve(), "csh"
    found = _bash_which("pipe2ucsf")
    if found:
        path = Path(found).expanduser()
        if path.is_file():
            return path.resolve(), "bash"
    return None, None


def find_pipe2ucsf(explicit: str = "") -> Path | None:
    """Find pipe2ucsf using explicit settings, then csh, then login bash."""
    return find_pipe2ucsf_with_shell(explicit)[0]


def bash_environment_csh_command(directory: str, csh: str) -> list[str] | None:
    """Build a temporary bash-login → interactive-csh bridge for GUI terminals.

    Only PATH and NMRPipe's plugin registration variables are explicitly carried
    across. The interactive csh then reads its normal rc file, whose values take
    precedence. No parent-process environment or rc file is changed.
    """
    bash = shutil.which("bash")
    if not bash:
        return None
    csh_script = (
        "if (-e ~/.cshrc) source ~/.cshrc; "
        'if (! $?NMR_PLUGIN_EXE && "$NMRFINESSE_BASH_PLUGIN_EXE" != "") '
        'setenv NMR_PLUGIN_EXE "$NMRFINESSE_BASH_PLUGIN_EXE"; '
        'if (! $?NMR_PLUGIN_FN && "$NMRFINESSE_BASH_PLUGIN_FN" != "") '
        'setenv NMR_PLUGIN_FN "$NMRFINESSE_BASH_PLUGIN_FN"; '
        'if ($?NMRFINESSE_BASH_PATH) setenv PATH "${PATH}:$NMRFINESSE_BASH_PATH"; '
        "unsetenv NMRFINESSE_BASH_PATH; "
        "unsetenv NMRFINESSE_BASH_PLUGIN_EXE; "
        "unsetenv NMRFINESSE_BASH_PLUGIN_FN; "
        f"exec {shlex.quote(csh)} -if"
    )
    script = (
        f"cd {shlex.quote(directory)} && exec env PATH=\"$PATH\" "
        'NMRFINESSE_BASH_PATH="$PATH" '
        'NMRFINESSE_BASH_PLUGIN_EXE="${NMR_PLUGIN_EXE-}" '
        'NMRFINESSE_BASH_PLUGIN_FN="${NMR_PLUGIN_FN-}" '
        f"{shlex.quote(csh)} -f -c {shlex.quote(csh_script)}"
    )
    return [bash, "-lic", script]


def find_nmrpipe_bin(explicit: str = "") -> Path | None:
    """Return the bin directory holding the nmrPipe executable (None when it cannot be found)."""
    candidates: list[Path] = []
    if explicit:
        path = Path(explicit).expanduser()
        candidates.append(path if path.is_dir() else path.parent)
    else:
        csh = _csh_which("nmrPipe")
        if csh:
            path = Path(csh)
            candidates.append(path if path.is_dir() else path.parent)
        which = shutil.which("nmrPipe")
        if which:
            candidates.append(Path(which).parent)
    for candidate in candidates:
        if (candidate / "nmrPipe").is_file():
            return candidate.resolve()
    return None


def csh_run(command: str, timeout: float = 15.0) -> tuple[int, str]:
    """Run a command in the csh login environment and return ``(return_code, combined_output)``.

    This must use csh because SMILE is an NMRPipe plugin registered through the
    ``NMR_PLUGIN_EXE`` and ``NMR_PLUGIN_FN`` environment variables in the user's shell setup.
    A plain shell reports ``unknown function SMILE`` for ``nmrPipe -fn SMILE -help``; the
    configured csh environment reports the plugin version. Therefore SMILE availability must
    be checked through csh rather than by running ``nmrPipe`` directly with
    ``subprocess.run``.

    Parameters
    ----------
    command : str
        Command to run after sourcing the user's csh startup file.
    timeout : float
        Timeout in seconds.

    Returns
    -------
    tuple[int, str]
        ``(return_code, stdout+stderr)``; returns ``(-1, "")`` if csh is unavailable or times
        out. Standard input is connected to ``/dev/null`` because ``nmrPipe`` may otherwise wait
        for terminal input.

    Side effects
    ------------
    Read-only: starts a csh subprocess.
    """
    shell = shutil.which("tcsh") or shutil.which("csh")
    if shell is None:
        return -1, ""
    script = f"if (-e ~/.cshrc) source ~/.cshrc; {command}"
    try:
        proc = subprocess.run(
            [shell, "-c", script],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""
    return proc.returncode, f"{proc.stdout or ''}\n{proc.stderr or ''}"


def find_tool(name: str, nmrpipe_bin: Path | None = None) -> Path | None:
    """Find an NMRPipe companion tool (bruker and similar live in com/).

    The csh answer wins; otherwise the bin directory and its parent levels are searched,
    including
    their com/ subdirectories.
    """
    csh = _csh_which(name)
    if csh:
        path = Path(csh)
        if path.is_file():
            return path.resolve()
    if nmrpipe_bin is not None:
        for root in (nmrpipe_bin, nmrpipe_bin.parent, nmrpipe_bin.parent.parent):
            for sub in ("", "com"):
                candidate = root / sub / name
                if candidate.is_file():
                    return candidate.resolve()
    return None
