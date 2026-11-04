"""User-requested viewport sizing and display control behavior."""

import numpy as np
from qtcompat.QtCore import QPointF, QRect
from qtcompat.QtWidgets import QGraphicsView

from ui_support.numeric_inputs import PeakSizeSpinBox
from ui_support.window_layout import initial_window_size
from viewer.spectrum import Spectrum, Spectrum1D, SpectrumAxis
from viewer.spectrum_viewer import SpectrumViewer


def axis(label, n):
    return SpectrumAxis(label=label, size=n, sw_hz=6000, obs_mhz=600, carrier_ppm=4.7, orig_hz=2820)


def test_peak_size_steps_cross_boundary_without_skipping(qapp):
    widget = PeakSizeSpinBox()
    widget.setRange(0.1, 50)
    widget.setDecimals(1)
    widget.setValue(0.5)
    widget.stepBy(1)
    assert widget.value() == 1
    widget.stepBy(-1)
    assert widget.value() == 0.5
    widget.stepBy(-1)
    assert widget.value() == 0.4
    widget.stepBy(-5)
    assert widget.value() == 0.1
    widget.stepBy(4)
    assert widget.value() == 0.5
    widget.stepBy(1)
    assert widget.value() == 1


def test_initial_window_uses_1080p_cap():
    assert initial_window_size(QRect(0, 0, 2560, 1440)).width() == 1920
    assert initial_window_size(QRect(0, 0, 2560, 1440)).height() == 1080
    assert initial_window_size(QRect(0, 0, 1280, 720)).height() == 720
    assert initial_window_size(QRect(0, 0, 1920, 1040)).height() == 1040


def test_1d_aspect_phase_curve_and_restore_2d(qapp):
    viewer = SpectrumViewer()
    data = np.exp(-(np.linspace(-4, 4, 128) ** 2))
    viewer._show_1d(Spectrum1D(data, axis("H", 128)))
    assert viewer.aspect_slider.value() == 2
    assert viewer.plot.viewportUpdateMode() == QGraphicsView.ViewportUpdateMode.FullViewportUpdate
    viewer.phase_panel.set_values(45, 0)
    viewer._update_phased_1d()
    assert np.allclose(viewer._plot_1d.yData, viewer._display_phase(data, 45, 0))
    assert len([p for p in viewer.plot.listDataItems() if p is viewer._plot_1d]) == 1
    viewer._restore_2d()
    assert viewer.aspect_slider.value() == 0
    viewer.close()
    viewer.deleteLater()
    qapp.processEvents()


def test_2d_crosshair_follows_without_pressed_button(qapp):
    viewer = SpectrumViewer()
    viewer.resize(800, 500)
    viewer.show()
    qapp.processEvents()
    spectrum = Spectrum(
        np.random.default_rng(1).normal(size=(32, 64)), [axis("N", 32), axis("H", 64)]
    )
    viewer.add_spectrum(spectrum)
    viewer._mouse_left_pressed = False
    point = viewer.plot.getViewBox().mapViewToScene(QPointF(12, 8))
    viewer._on_mouse_moved(point)
    assert viewer._crosshair_v.isVisible() and viewer._crosshair_h.isVisible()
    assert abs(viewer._crosshair_v.value() - 12) < 1e-5
    viewer.close()
    viewer.deleteLater()
    qapp.processEvents()
