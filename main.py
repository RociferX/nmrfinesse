"""NMRFinesse program entry.

On the first development run, create the nmrfinesse virtual environment and install this
project, then restart the entry point in that environment. Frozen builds start directly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / "nmrfinesse"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _is_frozen() -> bool:
    """Whether to run in PyInstaller frozen environment (AppImage)."""
    return bool(getattr(sys, "frozen", False))


def _bootstrap_venv() -> None:
    """First run: Create venv and install this project (reuse directly later)."""
    venv_dir, venv_python = VENV_DIR, VENV_PYTHON
    if venv_python.exists():
        return
    print(
        "No virtual environment detected, creating nmrfinesse/ and installing dependencies "
        "(first run will take a few minutes)..."
    )
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(venv_python), "-m", "pip", "install", "-e", str(PROJECT_ROOT)])


def main() -> int:
    """Launch the Qt main window (GUI is built on core.project)."""
    from core.logging_setup import configure_logging

    # Configure entry-point logging on stderr (NMRFINESSE_LOG_LEVEL, default WARNING).
    configure_logging()
    from gui.main_window import MainWindow

    return MainWindow.run()


if __name__ == "__main__":
    if not _is_frozen() and "--inside-venv" not in sys.argv:
        _bootstrap_venv()
        venv_python = VENV_PYTHON
        if os.path.abspath(sys.executable) != os.path.abspath(str(venv_python)):
            os.execv(
                str(venv_python), [str(venv_python), str(__file__), "--inside-venv"]
            )
    raise SystemExit(main())
