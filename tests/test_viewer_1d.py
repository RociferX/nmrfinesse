'1D spectrum/FID view tests: Spectrum1D, TopSpin-style 1D strips, layer removal, peak toggle.'

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from qtcompat.QtCore import QEvent, QPointF, Qt
from qtcompat.QtWidgets import QApplication

from viewer.app import SpectrumWindow
from viewer.spectrum import Spectrum, Spectrum1D, SpectrumAxis
from viewer.spectrum_viewer import SpectrumViewer


def _axis(
    label: str, size: int, sw: float = 6000.0, car: float = 4.7
) -> SpectrumAxis:
    return SpectrumAxis(
        label=label,
        size=size,
        sw_hz=sw,
        obs_mhz=600.0,
        carrier_ppm=car,
        orig_hz=car * 600.0,
    )


def _synthetic_spectrum(shape: tuple[int, int] = (64, 128)) -> Spectrum:
    rng = np.random.default_rng(0)
    data = np.zeros(shape)
    data[shape[0] * 5 // 8, shape[1] * 15 // 16] = 500.0
    data[shape[0] * 5 // 8 + 5, shape[1] * 13 // 16] = 350.0
    from scipy.ndimage import gaussian_filter

    data = gaussian_filter(data, sigma=(1.5, 1.5))
    data = data + rng.normal(0, 0.05, size=shape)
    return Spectrum(
        data, [_axis("F1", shape[0]), _axis("F2", shape[1])]
    )


def _write_ft2(path: Path, spectrum: Spectrum) -> None:
    from nmrglue.fileio import pipe

    axes = spectrum.axes
    dic = {key: "0" for key in pipe.fdata_dic}
    dic["FDMAGIC"] = 9.2330230000000007e14
    dic["FDDIMCOUNT"] = 2
    dic["FDSIZE"] = axes[1].size
    dic["FDSPECNUM"] = axes[0].size
    dic["FDQUADFLAG"] = 1
    dic["FDF1QUADFLAG"] = 1
    dic["FDF2QUADFLAG"] = 1
    dic["FDTRANSPOSED"] = 0
    for prefix, axis in zip(("FDF1", "FDF2"), axes):
        dic[prefix + "T"] = axis.size
        dic[prefix + "SW"] = axis.sw_hz
        dic[prefix + "OBS"] = axis.obs_mhz
        dic[prefix + "CAR"] = axis.carrier_ppm
        dic[prefix + "ORIG"] = axis.orig_hz
    pipe.write(
        str(path), dic, spectrum.data.astype(np.float32), overwrite=True
    )


def _write_fid(path: Path, data: np.ndarray) -> None:
    from nmrglue.fileio import pipe

    data = np.asarray(data)
    dic = {key: "0" for key in pipe.fdata_dic}
    dic["FDMAGIC"] = 9.2330230000000007e14
    dic["FDDIMCOUNT"] = 1
    dic["FDSIZE"] = data.shape[-1]
    dic["FDQUADFLAG"] = 1
    dic["FDF2QUADFLAG"] = 1
    dic["FDTRANSPOSED"] = 0
    dic["FDF2SW"] = 6000.0
    dic["FDF2OBS"] = 600.0
    dic["FDF2CAR"] = 4.7
    dic["FDF2ORIG"] = 4.7 * 600.0
    pipe.write(str(path), dic, data.astype(np.float32), overwrite=True)


def _write_fid2d(path: Path, data: np.ndarray) -> None:
    """Write a 2D time-domain FID (FDDIMCOUNT=2: row = indirect-dim increment,
    column = direct-dim time point).
    """
    from nmrglue.fileio import pipe

    data = np.asarray(data)
    dic = {key: "0" for key in pipe.fdata_dic}
    dic["FDMAGIC"] = 9.2330230000000007e14
    dic["FDDIMCOUNT"] = 2
    dic["FDSIZE"] = data.shape[-1]
    dic["FDSPECNUM"] = data.shape[0]
    dic["FDQUADFLAG"] = 1
    dic["FDF1QUADFLAG"] = 1
    dic["FDF2QUADFLAG"] = 1
    dic["FDTRANSPOSED"] = 0
    dic["FDF1TDSIZE"] = data.shape[0]
    dic["FDF2TDSIZE"] = data.shape[1]
    dic["FDF2SW"] = 6000.0
    dic["FDF2OBS"] = 600.0
    dic["FDF2CAR"] = 4.7
    dic["FDF2ORIG"] = 4.7 * 600.0
    pipe.write(str(path), dic, data.astype(np.float32), overwrite=True)


def test_spectrum1d_load_from_fid_roundtrip(tmp_path: Path) -> None:
    data = np.linspace(0.0, 1.0, 64)
    path = tmp_path / "test.fid"
    _write_fid(path, data)
    loaded = Spectrum1D.load_from_fid(path)
    assert loaded.data.shape == (64,)
    np.testing.assert_allclose(loaded.data, data)
    assert loaded.axis.size == 64
    assert not loaded.ppm_valid
    np.testing.assert_allclose(loaded.x_values(), np.arange(64))
    assert loaded.source == path


def test_spectrum1d_load_from_fid_2d_returns_timedomain_spectrum(
    tmp_path: Path,
) -> None:
    """0.2.78: a 2D FID is shown as a whole nmrDraw-style time-domain image
    (rows = individual FIDs, columns = time points).
    """
    rng = np.random.default_rng(1)
    data = rng.normal(size=(16, 32))
    data[0, 3] += 10000.0
    path = tmp_path / "raw.fid"
    _write_fid2d(path, data)
    loaded = Spectrum1D.load_from_fid(path)
    assert isinstance(loaded, Spectrum)
    assert loaded.data.shape == (16, 32)
    np.testing.assert_allclose(loaded.data, data)
    assert loaded.axes[0].label == "FID"
    assert loaded.axes[1].label == "Points"
    assert loaded.axes[0].size == 16
    assert loaded.axes[1].size == 32
    assert loaded.source == path

    assert 0 < loaded.robust_max < loaded.max_intensity


def test_viewer_fid_2d_window_load(tmp_path: Path, qapp: QApplication) -> None:
    """0.2.78: opening a 2D FID shows a 2D time-domain image, not the 1D trace of
    the first FID.
    """
    rng = np.random.default_rng(2)
    data = rng.normal(size=(16, 64))
    data[0, :] = np.exp(-np.arange(64) / 10.0) * 5000.0
    path = tmp_path / "2d.fid"
    _write_fid2d(path, data)
    window = SpectrumWindow()
    assert window.load_spectrum(path) is True
    assert not window.viewer._mode_1d
    assert len(window.viewer.layers) == 1
    assert isinstance(window.viewer._primary, Spectrum)
    assert window.viewer._primary.data.shape == (16, 64)
    assert "FID" in window.statusBar().currentMessage()
    window.close()


def test_display_phase_math() -> None:
    """0.2.87: display-only phase (does not change the data): 0° identity, 180° sign
    flip, 90° change.
    """
    from viewer.spectrum_viewer import SpectrumViewer

    rng = np.random.default_rng(3)
    real = rng.normal(size=32)
    p0_0 = SpectrumViewer._display_phase(real, 0.0, 0.0)
    np.testing.assert_allclose(p0_0, real)
    p0_180 = SpectrumViewer._display_phase(real, 180.0, 0.0)
    np.testing.assert_allclose(p0_180, -real, atol=1e-9)
    p0_90 = SpectrumViewer._display_phase(real, 90.0, 0.0)
    assert not np.allclose(p0_90, real)


def test_viewer_phase_panel_display_only_real_data(
    qapp: QApplication,
) -> None:
    """0.2.87: the phase panel is available for real 1D spectra; it only displays
    the phase shift and never changes the data.
    """
    from viewer.spectrum import SpectrumAxis

    n = 64
    time = np.arange(n)
    real = np.exp(-time / 20.0) * np.cos(2 * np.pi * time / 8.0)
    spectrum1d = Spectrum1D(real, SpectrumAxis("1H", n, 6000.0, 600.0, 4.7))
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum1d, name="1d")
    assert viewer.phase_panel.p0_slider.isEnabled()
    viewer._on_phase_changed(True)
    _x0, y0 = viewer._plot_1d.getData()
    viewer.phase_panel.set_values(90, 0)
    _x1, y1 = viewer._plot_1d.getData()
    assert not np.allclose(np.asarray(y0), np.asarray(y1))

    np.testing.assert_allclose(viewer._primary_1d.data, real)
    viewer.phase_panel.set_values(0, 0)
    _x2, y2 = viewer._plot_1d.getData()
    np.testing.assert_allclose(np.asarray(y2), np.asarray(y0))
    viewer.close()


def test_viewer_1d_hide_then_clear_restore_2d_controls(
    qapp: QApplication,
) -> None:
    """0.2.199-patch29gj-fix: after the 1D view hides the contour/aspect controls,
    clear() must restore them; otherwise the contour control stays hidden when
    switching back to 2D/3D.
    """
    from viewer.spectrum import SpectrumAxis

    n = 64
    time = np.arange(n)
    real = np.exp(-time / 20.0) * np.cos(2 * np.pi * time / 8.0)
    spectrum1d = Spectrum1D(real, SpectrumAxis("1H", n, 6000.0, 600.0, 4.7))
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum1d, name="1d")
    assert viewer._mode_1d
    assert viewer.level_slider.isHidden()
    assert not viewer.aspect_slider.isHidden()

    viewer.clear()
    assert not viewer.level_slider.isHidden()
    assert not viewer.aspect_slider.isHidden()
    assert not viewer.count_slider.isHidden()
    assert not viewer.level_label.isHidden()
    viewer.add_spectrum(_synthetic_spectrum(), name="2d")
    assert not viewer.level_slider.isHidden()
    viewer.close()


def test_viewer_1d_strips_toggle_and_update(qapp: QApplication) -> None:
    """1D mode toggle: crosshair + top/right strips; clicking a position shows the two
    1D traces there.
    """
    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    assert viewer.show_1d_button.text() == "1D"
    assert not viewer.show_1d_button.isChecked()
    viewer.set_1d_mode(True)
    assert viewer._strips_active
    assert viewer.show_1d_button.isChecked()
    assert not viewer.strip_top.isHidden()
    assert not viewer.strip_right.isHidden()

    assert viewer.strip_top.minimumHeight() == viewer.strip_top.maximumHeight() == 170
    assert (
        viewer.strip_right.minimumWidth() == viewer.strip_right.maximumWidth() == 190
    )

    viewer._update_strips(40, 120)
    _xt, yt = viewer.strip_top_curve.getData()
    np.testing.assert_allclose(np.asarray(yt), spectrum.data[40, :])
    xr, _yr = viewer.strip_right_curve.getData()
    np.testing.assert_allclose(np.asarray(xr), spectrum.data[:, 120])

    viewer._mouse_left_pressed = True
    scene_pt = viewer.plot.getViewBox().mapViewToScene(QPointF(120.0, 40))
    viewer._on_mouse_moved(scene_pt)
    assert viewer._crosshair_v.pos().x() == pytest.approx(120.0)
    assert viewer._crosshair_h.pos().y() == pytest.approx(40.0)
    # Released hover must not move the crosshair or either chosen strip.
    viewer._mouse_left_pressed = False
    scene_pt2 = viewer.plot.getViewBox().mapViewToScene(QPointF(90.0, 30))
    viewer._on_mouse_moved(scene_pt2)
    _xt, yt = viewer.strip_top_curve.getData()
    np.testing.assert_allclose(np.asarray(yt), spectrum.data[40, :])
    xr, _yr = viewer.strip_right_curve.getData()
    np.testing.assert_allclose(np.asarray(xr), spectrum.data[:, 120])
    assert viewer._crosshair_v.pos().x() == pytest.approx(120.0)
    assert viewer._crosshair_h.pos().y() == pytest.approx(40.0)
    viewer.eventFilter(viewer._plot_viewport, QEvent(QEvent.Type.Leave))
    assert viewer._crosshair_v.isVisible() and viewer._crosshair_h.isVisible()
    # Another left drag selects a new pair of cuts.
    viewer._mouse_left_pressed = True
    viewer._on_mouse_moved(scene_pt2)
    viewer._mouse_left_pressed = False
    _xt, yt = viewer.strip_top_curve.getData()
    np.testing.assert_allclose(np.asarray(yt), spectrum.data[30, :])
    xr, _yr = viewer.strip_right_curve.getData()
    np.testing.assert_allclose(np.asarray(xr), spectrum.data[:, 90])
    assert viewer._crosshair_v.pos().x() == pytest.approx(90.0)
    assert viewer._crosshair_h.pos().y() == pytest.approx(30.0)

    viewer.set_1d_mode(False)
    assert not viewer._strips_active
    assert viewer.strip_top.isHidden()
    # Ordinary 2D hover resumes immediately after leaving strip mode.
    viewer._on_mouse_moved(scene_pt)
    assert viewer._crosshair_v.pos().x() == pytest.approx(120.0)
    assert viewer._crosshair_h.pos().y() == pytest.approx(40.0)
    viewer.eventFilter(viewer._plot_viewport, QEvent(QEvent.Type.Leave))
    assert not viewer._crosshair_v.isVisible() and not viewer._crosshair_h.isVisible()
    viewer.close()


def test_viewer_fid_window_load(tmp_path: Path, qapp: QApplication) -> None:
    fid_path = tmp_path / "1d.fid"
    _write_fid(fid_path, np.linspace(0.0, 1.0, 64))
    window = SpectrumWindow()
    assert window.load_spectrum(fid_path) is True
    assert window.viewer._mode_1d
    assert "FID" in window.statusBar().currentMessage()
    window.close()


def test_viewer_layer_delete(qapp: QApplication) -> None:
    viewer = SpectrumViewer()
    viewer.add_spectrum(_synthetic_spectrum(), name="A")
    viewer.add_spectrum(_synthetic_spectrum((48, 96)), name="B")
    assert viewer.layer_list.count() == 2
    viewer.remove_layer(0)
    assert viewer.layer_list.count() == 1
    assert viewer.layer_names == ["B"]
    assert len(viewer.layers) == 1
    viewer.remove_layer(0)
    assert viewer.layer_list.count() == 0
    assert viewer._primary is None
    viewer.close()


def test_viewer_view_to_data_maps_view_y_to_row(qapp: QApplication) -> None:
    'View coordinates are data indices: view y = row number, out of range returns (-1,-1).'
    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    rows, cols = spectrum.data.shape
    assert viewer._view_to_data(QPointF(120.0, 40)) == (120, 40)
    assert viewer._view_to_data(QPointF(0.0, 0)) == (0, 0)
    assert viewer._view_to_data(QPointF(0.0, rows)) == (-1, -1)
    assert viewer._view_to_data(QPointF(cols + 5, 40)) == (-1, -1)
    viewer.close()


def test_viewer_peaks_aligned_with_contour(qapp: QApplication) -> None:
    "Peak markers' view y is the data row (consistent with the contour)."
    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.set_peaks(
        [
            {
                "H_shift": spectrum.x_axis.ppm_at(120),
                "N_shift": spectrum.y_axis.ppm_at(40),
            }
        ]
    )
    assert float(viewer.peak_item.data["x"][0]) == 120.0
    assert float(viewer.peak_item.data["y"][0]) == 40
    viewer.close()


class _FakeClickEvent:
    'Minimal mouse-event stub: left click (not a drag).'

    def __init__(self, scene_pos: QPointF) -> None:
        self._pos = scene_pos

    def button(self) -> Qt.MouseButton:
        return Qt.MouseButton.LeftButton

    def scenePos(self) -> QPointF:
        return self._pos

    def buttonDownScenePos(self, _button) -> QPointF:
        return self._pos


def test_viewer_plot_click_strips_and_select(qapp: QApplication) -> None:
    """Click the screen position of data (120, 40): the strips show the correct
    row/column and that peak can be selected.
    """
    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    scene_pt = viewer.plot.getViewBox().mapViewToScene(QPointF(120.0, 40))
    viewer.set_peaks(
        [
            {
                "H_shift": spectrum.x_axis.ppm_at(120),
                "N_shift": spectrum.y_axis.ppm_at(40),
            }
        ]
    )
    viewer.set_1d_mode(True)
    viewer._on_plot_clicked(_FakeClickEvent(scene_pt))
    _xt, yt = viewer.strip_top_curve.getData()
    np.testing.assert_allclose(np.asarray(yt), spectrum.data[40, :])
    xr, _yr = viewer.strip_right_curve.getData()
    np.testing.assert_allclose(np.asarray(xr), spectrum.data[:, 120])
    viewer.set_1d_mode(False)
    viewer._on_plot_clicked(_FakeClickEvent(scene_pt))
    assert viewer._selected_peak == 0
    viewer.close()


def test_viewer_strip_right_y_direction_and_link(qapp: QApplication) -> None:
    """The right 1D strip matches the Y direction of the 2D spectrum, and its y
    range follows zooming of the main plot.
    """
    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.set_1d_mode(True)
    main_inv = viewer.plot.getViewBox().state["yInverted"]
    right_inv = viewer.strip_right.getViewBox().state["yInverted"]
    assert right_inv == main_inv

    viewer.plot.getViewBox().setRange(yRange=(10.0, 40.0), padding=0)
    np.testing.assert_allclose(
        viewer.strip_right.getViewBox().viewRange()[1],
        viewer.plot.getViewBox().viewRange()[1],
    )

    right_s0 = viewer.strip_right.getViewBox().mapViewToScene(
        QPointF(0.0, 0.0)
    )
    right_s1 = viewer.strip_right.getViewBox().mapViewToScene(
        QPointF(0.0, spectrum.data.shape[0] - 1)
    )
    main_s0 = viewer.plot.getViewBox().mapViewToScene(QPointF(0.0, 0.0))
    main_s1 = viewer.plot.getViewBox().mapViewToScene(
        QPointF(0.0, spectrum.data.shape[0] - 1)
    )
    assert (right_s0.y() < right_s1.y()) == (main_s0.y() < main_s1.y())
    viewer.close()


def test_viewer_clear_restores_2d_direction(qapp: QApplication) -> None:
    "clear() unifies the main plot's 2D display direction (row 0 = high ppm at the bottom)."
    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.plot.getViewBox().invertY(True)
    viewer.clear()
    assert viewer.plot.getViewBox().state["yInverted"] is False
    viewer.close()


def test_viewer_peaks_toggle(qapp: QApplication) -> None:
    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.set_peaks(
        [
            {"H_shift": spectrum.x_axis.ppm_at(120), "N_shift": spectrum.y_axis.ppm_at(40)},
            {"H_shift": spectrum.x_axis.ppm_at(110), "N_shift": spectrum.y_axis.ppm_at(45)},
        ]
    )
    assert viewer.peak_item.data["x"].shape == (2,)
    assert viewer.show_peaks_checkbox.isChecked()
    viewer.set_peaks_visible(False)
    assert not viewer.show_peaks_checkbox.isChecked()
    assert viewer.peak_item.data["x"].shape == (0,)
    viewer.set_peaks_visible(True)
    assert viewer.peak_item.data["x"].shape == (2,)
    viewer.close()



class _FakeClickEventNoPress(_FakeClickEvent):
    'Simulates pyqtgraph MouseClickEvent: no buttonDownScenePos (0.2.199-patch29aw).'

    def buttonDownScenePos(self, _button):
        raise AttributeError("MouseClickEvent has no attribute 'buttonDownScenePos'")


def test_viewer_plot_click_without_button_down_pos(qapp: QApplication) -> None:

    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.set_peaks(
        [
            {
                'H_shift': spectrum.x_axis.ppm_at(60),
                'N_shift': spectrum.y_axis.ppm_at(30),
            }
        ]
    )
    scene_pt = viewer.plot.getViewBox().mapViewToScene(QPointF(60.0, 30))
    viewer._on_plot_clicked(_FakeClickEventNoPress(scene_pt))
    assert viewer._selected_peak == 0
    viewer.close()



def test_box_select_uses_peak_coords_only(qapp: QApplication) -> None:

    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.set_peaks(
        [
            {'H_shift': spectrum.x_axis.ppm_at(30), 'N_shift': spectrum.y_axis.ppm_at(20)},
            {'H_shift': spectrum.x_axis.ppm_at(100), 'N_shift': spectrum.y_axis.ppm_at(50)},
            {'H_shift': spectrum.x_axis.ppm_at(80), 'N_shift': spectrum.y_axis.ppm_at(10)},
        ]
    )
    viewer._apply_peak_items()
    assert len(viewer._peak_data_xy) == 3
    vb = viewer.plot.getViewBox()
    viewer._box_press_scene = vb.mapViewToScene(QPointF(25.0, 15.0))
    viewer._finish_box_select(vb.mapViewToScene(QPointF(110.0, 55.0)))
    assert viewer._box_selected_rows == {0, 1}
    viewer.close()



def test_box_select_clamps_to_spectrum_edges(qapp: QApplication) -> None:

    spectrum = _synthetic_spectrum()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.set_peaks(
        [
            {'H_shift': spectrum.x_axis.ppm_at(30), 'N_shift': spectrum.y_axis.ppm_at(20)},
            {'H_shift': spectrum.x_axis.ppm_at(100), 'N_shift': spectrum.y_axis.ppm_at(50)},
        ]
    )
    vb = viewer.plot.getViewBox()
    viewer._box_press_scene = vb.mapViewToScene(QPointF(10.0, 10.0))

    viewer._finish_box_select(vb.mapViewToScene(QPointF(1e6, 1e6)))
    assert viewer._box_selected_rows == {0, 1}
    viewer.close()


def test_1d_zoom_pan_aspect_and_axis_reset(qapp: QApplication) -> None:
    """PPM zoom stays horizontal, panning works, and 2D direction cannot leak."""
    viewer = SpectrumViewer()
    viewer.resize(950, 850)
    viewer.show()
    viewer.add_spectrum(_synthetic_spectrum())
    spectrum = Spectrum1D(np.sin(np.arange(1024) / 20) * 1e12, _axis('H', 1024))
    viewer.add_spectrum(spectrum)
    qapp.processEvents()
    vb = viewer.plot.getViewBox()
    assert viewer.plot.getAxis('left')._tickLevels is None
    assert not viewer.aspect_controls.isHidden()
    assert viewer.contour_controls._grid.getItemPosition(0)[:2] == (0, 0)
    for _ in range(12):
        vb.scaleBy((.7, .7))
    (x0, x1), (y0, y1) = vb.viewRange()
    assert x1 - x0 < .2
    assert x1 - x0 >= vb._min_span[0] * .99

    class Drag:
        def button(self):
            return Qt.MouseButton.MiddleButton

        def pos(self):
            return QPointF(220, 200)

        def lastPos(self):
            return QPointF(180, 180)

        def accept(self):
            pass

    vb.mouseDragEvent(Drag())
    after = vb.viewRange()
    assert after[0] != [x0, x1] and after[1] != [y0, y1]
    assert after[0][1] - after[0][0] == pytest.approx(x1 - x0)
    viewer.aspect_slider.setValue(150)
    full = vb._min_rect
    assert vb.state['aspectLocked'] == pytest.approx(
        1.5 * (full[1][1] - full[1][0]) / (full[0][1] - full[0][0]))
    assert np.isfinite(np.array(vb.viewRange())).all()
    viewer.clear()
    spec2 = _synthetic_spectrum()
    viewer.add_spectrum(spec2)
    qapp.processEvents()
    left = vb.mapViewToScene(QPointF(0, 0))
    right = vb.mapViewToScene(QPointF(spec2.x_axis.size - 1, 0))
    assert left.x() < right.x()
    assert spec2.x_axis.ppm_at(0) > spec2.x_axis.ppm_at(spec2.x_axis.size - 1)
    assert not vb.state['xInverted']
    assert not vb.state['aspectLocked']
    viewer.close()


@pytest.mark.parametrize('one_dimensional', [False, True])
def test_full_spectrum_overview_threshold_and_navigation(qapp, one_dimensional):
    viewer = SpectrumViewer()
    viewer.resize(950, 850)
    viewer.show()
    spectrum = (Spectrum1D(np.sin(np.arange(512) / 20), _axis('H', 512))
                if one_dimensional else _synthetic_spectrum())
    viewer.add_spectrum(spectrum)
    qapp.processEvents()
    vb = viewer.plot.getViewBox()
    overview = viewer._overview
    assert overview.isHidden()
    vb.scaleBy((1 / 1.5, 1 / 1.5))
    qapp.processEvents()
    assert overview.isHidden()
    vb.scaleBy((.5, .5))
    qapp.processEvents()
    assert not overview.isHidden()
    assert overview.pos().x() >= viewer.plot.mapFromScene(vb.sceneBoundingRect().topLeft()).x()
    assert not overview.grab().isNull()
    area, mapping = overview._mapping()
    full = vb._min_rect
    p0 = mapping.map(QPointF(full[0][0], full[1][0]))
    p1 = mapping.map(QPointF(full[0][1], full[1][1]))
    assert (p0.x() > p1.x()) == one_dimensional
    before = vb.viewRange()
    overview._recenter(area.topLeft() + QPointF(area.width() * .25, area.height() * .25))
    assert vb.viewRange() != before
    assert vb.viewRange()[0][1] - vb.viewRange()[0][0] == pytest.approx(before[0][1] - before[0][0])
    viewer.reset_view()
    qapp.processEvents()
    assert overview.isHidden()
    viewer.clear()
    assert overview.isHidden()
    viewer.close()


@pytest.mark.parametrize('sign', [1, -1, 0])
def test_1d_zero_centred_and_wheel_vertical_rate(qapp, sign):
    viewer = SpectrumViewer()
    viewer.resize(950, 850)
    viewer.show()
    spectrum = Spectrum1D(np.linspace(.1, 1, 1024) * sign * 1e9, _axis('H', 1024))
    viewer.add_spectrum(spectrum)
    viewer.aspect_slider.setValue(0)  # Independent zoom rates apply in free-aspect mode.
    qapp.processEvents()
    vb = viewer.plot.getViewBox()
    before = np.diff(vb.viewRange(), axis=1).ravel()
    assert sum(vb.viewRange()[1]) == pytest.approx(0, abs=1e-6)

    class Wheel:
        def __init__(self, delta):
            self._delta = delta

        def delta(self):
            return self._delta

        def pos(self):
            return vb.mapFromView(QPointF(np.mean(vb.viewRange()[0]), 0))

        def accept(self):
            pass

    vb.wheelEvent(Wheel(120))
    factor = before / np.diff(vb.viewRange(), axis=1).ravel()
    assert factor[1] == pytest.approx(factor[0] ** 1.5)
    assert sum(vb.viewRange()[1]) == pytest.approx(0, abs=1e-5)
    vb.wheelEvent(Wheel(-120))
    np.testing.assert_allclose(np.diff(vb.viewRange(), axis=1).ravel(), before)
    viewer.clear()
    viewer.add_spectrum(_synthetic_spectrum())
    before = np.diff(vb.viewRange(), axis=1).ravel()
    vb.wheelEvent(Wheel(120))
    factor = before / np.diff(vb.viewRange(), axis=1).ravel()
    assert factor[1] == pytest.approx(factor[0])
    viewer.close()


@pytest.mark.parametrize('sign', [1, -1])
@pytest.mark.parametrize('size', [(1000, 800), (460, 900)])
def test_locked_1d_can_zoom_out_past_full_ppm_without_changing_initial_view(qapp, sign, size):
    from qtcompat.QtTest import QTest
    viewer = SpectrumViewer()
    viewer.resize(*size)
    viewer.show()
    QTest.qWait(40)
    water = sign * 1e6 * np.exp(-np.linspace(-5, 5, 1024)**2)
    viewer.add_spectrum(Spectrum1D(water, _axis('H', 1024)))
    QTest.qWait(60)
    vb = viewer.plot.getViewBox()
    full = np.asarray(vb._min_rect)
    initial = np.asarray(vb.viewRange())
    initial_spans = np.diff(initial, axis=1).ravel()
    full_spans = np.diff(full, axis=1).ravel()
    assert viewer.aspect_slider.value() == 2
    assert initial_spans[0] < 1.5 * full_spans[0]
    assert initial_spans[1] < .5 * full_spans[1]  # Water need not fit initially.
    center = QPointF(float(full[0].mean()), 0)
    vb.scaleBy((2, 2), center=center)
    after = np.asarray(vb.viewRange())
    spans = np.diff(after, axis=1).ravel()
    assert spans[0] > initial_spans[0] * 1.5
    assert spans[1] / initial_spans[1] == pytest.approx(spans[0] / initial_spans[0])
    assert after[0, 0] <= full[0, 0] and after[0, 1] >= full[0, 1]
    for _ in range(12):
        vb.scaleBy((2, 2), center=center)
    complete = np.asarray(vb.viewRange())
    assert np.all(complete[:, 0] <= full[:, 0] + 1e-6)
    assert np.all(complete[:, 1] >= full[:, 1] - 1e-6)
    viewer.reset_view()
    reset = np.asarray(vb.viewRange())
    assert reset[0] == pytest.approx(full[0])
    assert np.diff(reset[1])[0] < .5 * full_spans[1]
    viewer.close()
    viewer.deleteLater()
    qapp.processEvents()


def test_strip_phases_are_independent_and_preserved_when_selecting_cuts(qapp):
    spectrum = _synthetic_spectrum()
    original = spectrum.data.copy()
    viewer = SpectrumViewer()
    viewer.add_spectrum(spectrum)
    viewer.set_1d_mode(True)
    viewer._update_strips(40, 120)
    assert not viewer.right_phase_panel.isHidden()
    top_before = viewer.strip_top_curve.getData()[1].copy()
    right_before = viewer.strip_right_curve.getData()[0].copy()
    viewer.phase_panel.set_values(90, 15)
    np.testing.assert_allclose(viewer.strip_right_curve.getData()[0], right_before)
    top_phased = viewer.strip_top_curve.getData()[1].copy()
    assert not np.allclose(top_phased, top_before)
    viewer.right_phase_panel.set_values(-60, 20)
    np.testing.assert_allclose(viewer.strip_top_curve.getData()[1], top_phased)
    np.testing.assert_allclose(viewer.strip_right_curve.getData()[0],
        viewer._display_phase(spectrum.data[:, 120], -60, 20))
    viewer._update_strips(35, 110)
    np.testing.assert_allclose(viewer.strip_top_curve.getData()[1],
        viewer._display_phase(spectrum.data[35], 90, 15))
    np.testing.assert_allclose(viewer.strip_right_curve.getData()[0],
        viewer._display_phase(spectrum.data[:, 110], -60, 20))
    viewer.phase_panel.reset()
    assert viewer.right_phase_panel.values() == (-60, 20)
    np.testing.assert_allclose(viewer.strip_top_curve.getData()[1], spectrum.data[35])
    viewer.set_1d_mode(False)
    assert viewer.right_phase_panel.isHidden()
    viewer.set_1d_mode(True)
    assert viewer.phase_panel.values() == (0, 0)
    assert viewer.right_phase_panel.values() == (-60, 20)
    np.testing.assert_array_equal(spectrum.data, original)
    viewer.add_spectrum(Spectrum1D(spectrum.data[35], spectrum.x_axis))
    assert viewer.right_phase_panel.isHidden()
    assert not viewer.phase_panel.isHidden()
    viewer.close()
