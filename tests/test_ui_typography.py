"""Bounded interface font-size preference and application helper tests."""

from __future__ import annotations


def test_font_size_setting_round_trips_and_partial_save_preserves_other_values(
    tmp_path, monkeypatch
) -> None:
    import yaml

    from gui import settings

    path = tmp_path / "settings.yaml"
    monkeypatch.setattr(settings, "_settings_path", lambda: path)
    settings.save_settings({"interface_font_size": 15, "data_root": "somewhere"})

    assert settings.load_settings()["interface_font_size"] == 15
    settings.save_settings({"interface_font_size": 40})
    assert settings.load_settings()["interface_font_size"] == 18
    settings.save_settings({"interface_font_size": -2})
    assert settings.load_settings()["interface_font_size"] == 0
    settings.save_settings({"interface_font_size": "not-a-size"})
    assert settings.load_settings()["interface_font_size"] == 0
    assert settings.load_settings()["data_root"] == "somewhere"
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["interface_font_size"] == 0


def test_illegal_persisted_font_size_normalizes_on_read(tmp_path, monkeypatch) -> None:
    from gui import settings

    path = tmp_path / "settings.yaml"
    path.write_text("interface_font_size: 2\n", encoding="utf-8")
    monkeypatch.setattr(settings, "_settings_path", lambda: path)
    assert settings.load_settings()["interface_font_size"] == 8


def test_automatic_font_size_uses_logical_available_height() -> None:
    from ui_support.typography import automatic_font_size

    assert automatic_font_size(700) == 10
    assert automatic_font_size(700, 12) == 10
    assert automatic_font_size(900, 10) == 10
    assert automatic_font_size(1600, 10) == 11
    assert automatic_font_size(1600, 14) == 12


def test_apply_interface_font_preserves_family_and_applies_size(qapp) -> None:
    from qtcompat.QtGui import QFont

    from ui_support.typography import apply_interface_font

    original = QFont(qapp.font())
    try:
        custom = QFont(original)
        custom.setFamily("DejaVu Sans")
        custom.setPointSize(10)
        qapp.setFont(custom)

        assert apply_interface_font(qapp, 16) == 16
        assert qapp.font().family() == "DejaVu Sans"
        assert qapp.font().pointSize() == 16
    finally:
        qapp.setFont(original)


def test_returning_to_automatic_uses_original_system_font(qapp, monkeypatch) -> None:
    from qtcompat.QtGui import QFont

    from ui_support.typography import apply_interface_font, automatic_font_size

    original = QFont(qapp.font())
    monkeypatch.setattr(qapp, '_interface_system_font', QFont(original), raising=False)
    try:
        apply_interface_font(qapp, 18)
        expected = automatic_font_size(
            qapp.primaryScreen().availableGeometry().height(), original.pointSize(),
        )
        assert apply_interface_font(qapp, 0) == expected
        assert qapp.font().pointSize() == expected
    finally:
        qapp.setFont(original)
