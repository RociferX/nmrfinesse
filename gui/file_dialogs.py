"""Shared file dialog helpers for GUI workflows."""

from __future__ import annotations

import os
from pathlib import Path

from qtcompat.QtCore import Qt
from qtcompat.QtWidgets import QApplication, QFileDialog, QWidget


def browse_start_directory(start: str = "") -> str:
    """Resolve a real folder instead of leaving native pickers in Recent."""
    if start:
        path = Path(os.path.expandvars(start)).expanduser()
        if path.is_absolute():
            while not path.is_dir() and path != path.parent:
                path = path.parent
            if path.is_dir() and (path != Path(path.anchor) or path == Path(start)):
                return str(path)
    return str(Path.home())


def choose_file(parent: QWidget | None, title: str, start: str = "", filters: str = "") -> str:
    """Select an existing file, starting at the current path or its directory."""
    owner = QApplication.activeModalWidget() or (parent.window() if parent is not None else None)
    if owner is not None:
        owner.winId()
    selected = Path(os.path.expandvars(start)).expanduser() if start else None
    initial = (str(selected) if selected is not None and selected.is_file()
               else browse_start_directory(start))
    path, _ = QFileDialog.getOpenFileName(owner, title, initial, filters)
    return path


def choose_directory(parent: QWidget | None, title: str, start: str = "") -> str:
    """Use the desktop directory picker with modal ownership."""
    owner = QApplication.activeModalWidget() or (parent.window() if parent is not None else None)
    if owner is not None:
        owner.winId()
    dialog = QFileDialog(owner, title, browse_start_directory(start))
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, False)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    if dialog.exec() != QFileDialog.DialogCode.Accepted:
        return ""
    selected = dialog.selectedFiles()
    return selected[0] if selected else ""
