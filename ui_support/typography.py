"""Small helpers for choosing and applying the application's interface font size."""

from __future__ import annotations

MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 18


def normalize_font_size(value: object) -> int:
    """Return 0 (automatic) or a supported integer point size.

    Invalid values and negative values select automatic sizing. Positive values
    outside the manual range are clamped to its nearest endpoint.
    """
    if isinstance(value, bool):
        return 0
    try:
        # Do not silently truncate fractional values: the setting is in whole pt.
        size = int(value)
        if str(value).strip() not in {str(size), f"{size}.0"} and not isinstance(
            value, int
        ):
            return 0
    except (TypeError, ValueError, OverflowError):
        return 0
    if size == 0:
        return 0
    if size < 0:
        return 0
    return min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, size))


def automatic_font_size(
    available_height: int, system_point_size: int | None = None
) -> int:
    """Choose a conservative 9–12 pt size from logical available screen height."""
    try:
        height = int(available_height)
    except (TypeError, ValueError, OverflowError):
        height = 0

    # Bounds by logical screen height prevent Qt's high-DPI scaling from being
    # applied a second time to a physical-pixel measurement.
    if height > 0 and height < 800:
        low, high = 9, 10
    elif height >= 1400:
        low, high = 11, 12
    else:
        low, high = 9, 11

    try:
        system_size = int(system_point_size) if system_point_size is not None else 10
    except (TypeError, ValueError, OverflowError):
        system_size = 10
    return min(high, max(low, system_size))


def apply_interface_font(app, value: object = 0, screen=None) -> int:
    """Apply a point size while preserving the application's current font family."""
    from qtcompat.QtGui import QFont

    if getattr(app, '_interface_system_font', None) is None:
        app._interface_system_font = QFont(app.font())
    size = normalize_font_size(value)
    if size == 0:
        target_screen = screen
        if target_screen is None:
            target_screen = app.primaryScreen()
        height = target_screen.availableGeometry().height() if target_screen else 0
        size = automatic_font_size(height, app._interface_system_font.pointSize())

    font = QFont(app.font())
    font.setPointSize(size)
    app.setFont(font)
    # Qt's stylesheet engine caches inherited fonts on existing widgets. Reapply
    # the current rules so the live interface follows the new application font.
    stylesheet = app.styleSheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)
    return size


def configured_font_size() -> int:
    """Read the shared GUI preference without importing the project GUI."""
    import os
    import sys

    import yaml

    from core.app_paths import local_config_path

    path = local_config_path('nmrfinesse.local.yaml',
                             packaged=bool(os.environ.get('APPIMAGE') or
                                           getattr(sys, 'frozen', False)))
    try:
        raw = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError):
        return 0
    return normalize_font_size(raw.get('interface_font_size')) if isinstance(raw, dict) else 0


__all__ = [
    "apply_interface_font", "automatic_font_size", "configured_font_size", "normalize_font_size",
]
