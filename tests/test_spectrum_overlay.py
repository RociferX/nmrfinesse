"""Physical alignment, independent colors, SVG and comparison mode lifecycle."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from viewer.spectrum import Spectrum, Spectrum1D, SpectrumAxis
from viewer.spectrum_overlay import fit_translation, sample_spectrum, validate_spectra


def _spectrum(shape=(96, 128), displacement=(0, 0), origin=(115, 7.5)):
    data = np.zeros(shape)
    for y, x, height in [(25, 35, 10), (58, 80, 7), (40, 94, -6), (76, 44, 4)]:
        data[y + displacement[0], x + displacement[1]] = height
    data = gaussian_filter(data, 1.5)
    axes = [SpectrumAxis(label, n, n * step * obs, obs, 0, orig * obs)
            for label, n, step, obs, orig in zip(
                ['15N', '1H'], shape, [.05, .01], [60, 600], origin)]
    return Spectrum(data, axes)


def test_translation_has_physical_sign_and_preserves_data():
    fixed, moving = _spectrum(), _spectrum(displacement=(3, -5))
    before = moving.data.copy()
    offset, score = fit_translation(fixed, moving)
    assert offset == pytest.approx((.15, -.05), abs=.003)
    assert score > .99
    np.testing.assert_array_equal(moving.data, before)
    sampled = sample_spectrum(moving, [a.ppm for a in fixed.axes], offset)
    assert np.nanmax(np.abs(sampled - fixed.data)) < .005


def test_translation_uses_ppm_not_pixel_grid():
    fixed, moving = _spectrum(), _spectrum(origin=(115.1, 7.47))
    offset, score = fit_translation(fixed, moving)
    assert offset == pytest.approx((-.1, .03), abs=.003)
    assert score > .99


def test_fit_different_resolution_and_1d():
    fixed = _spectrum()
    axes = [replace(a, size=a.size // 2, orig_hz=float(a.ppm[-2] * a.obs_mhz))
            for a in fixed.axes]
    moving = Spectrum(fixed.data[::2, ::2].copy(), axes)
    offset, score = fit_translation(fixed, moving)
    assert offset == pytest.approx((0, 0), abs=.004)
    assert score > .99
    line = fixed.data[25]
    a = Spectrum1D(line, fixed.axes[1])
    b = Spectrum1D(np.roll(line, 5), fixed.axes[1])
    offset, score = fit_translation(a, b)
    assert offset == pytest.approx((.05,), abs=.003)
    assert score > .99


def test_fit_retains_narrow_peaks_in_long_direct_axis():
    from scipy.ndimage import shift as array_shift

    random = np.random.default_rng(34)
    shape = (96, 2048)
    data = np.zeros(shape)
    for _ in range(24):
        data[random.integers(12, 80), random.integers(24, 2010)] = random.uniform(2, 10)
    data = gaussian_filter(data, .8)
    axes = [SpectrumAxis('15N', 96, 288, 60, 117),
            SpectrumAxis('1H', 2048, 1228.8, 600, 8)]
    fixed = Spectrum(data, axes)
    moving = Spectrum(array_shift(data, (3, 9), order=1), axes)
    offset, score = fit_translation(fixed, moving)
    assert offset == pytest.approx((.15, .009), abs=.003)
    assert score > .9


def test_blank_and_wrong_nuclei_fail_without_fabricated_fit():
    fixed, moving = _spectrum(), _spectrum()
    moving.data[:] = 0
    with pytest.raises(ValueError):
        fit_translation(fixed, moving)
    moving.axes[0] = replace(moving.axes[0], label='13C')
    with pytest.raises(ValueError):
        fit_translation(fixed, moving)


@pytest.mark.parametrize('labels', [('Nx', 'N'), ('Ny', '15N'), ('15Nx', '15Ny'),
                                   ('N15x', 'Ny'), ('Nx', 'Ny')])
def test_nnh_planes_compare_by_nucleus_and_keep_original_roles(labels):
    fixed, moving = _spectrum(), _spectrum(displacement=(3, -5))
    fixed.axes[0] = replace(fixed.axes[0], label=labels[0])
    moving.axes[0] = replace(moving.axes[0], label=labels[1])
    fixed.axes[1] = replace(fixed.axes[1], label='H')
    fixed.dim_indices, moving.dim_indices = (1, 2), (0, 2)
    before = moving.data.copy()
    offset, score = fit_translation(fixed, moving)
    assert offset == pytest.approx((.15, -.05), abs=.003)
    assert score > .99
    assert (fixed.axes[0].label, moving.axes[0].label) == labels
    assert moving.dim_indices == (0, 2)
    np.testing.assert_array_equal(moving.data, before)


@pytest.mark.parametrize('mismatch', ['nucleus', 'orientation', 'isotope', 'unknown'])
def test_overlay_still_rejects_mismatched_axes_after_role_normalization(mismatch):
    fixed, moving = _spectrum(), _spectrum()
    fixed.axes[0] = replace(fixed.axes[0], label='Nx')
    if mismatch == 'orientation':
        moving.axes.reverse()
    else:
        label = {'nucleus': 'C', 'isotope': '14N', 'unknown': 'F1'}[mismatch]
        moving.axes[0] = replace(moving.axes[0], label=label)
    with pytest.raises(ValueError):
        validate_spectra([fixed, moving])


@pytest.mark.parametrize('mismatch', ['suffix', 'logical_axis'])
def test_nn_planes_retain_axis_identity(mismatch):
    fixed, moving = _spectrum(), _spectrum()
    for spectrum in (fixed, moving):
        spectrum.axes = [replace(axis, label=label) for axis, label
                         in zip(spectrum.axes, ['Ny', 'Nx'])]
        spectrum.dim_indices = (0, 1)
    validate_spectra([fixed, moving])
    if mismatch == 'suffix':
        moving.axes = [replace(axis, label=label) for axis, label
                       in zip(moving.axes, ['Nx', 'Ny'])]
    else:
        moving.dim_indices = (1, 0)
    with pytest.raises(ValueError):
        validate_spectra([fixed, moving])


def test_three_nnh_spectra_can_enable_and_render_overlay(qapp):
    from gui.overlay_comparison import OverlayComparison

    spectra = [_spectrum(), _spectrum(), _spectrum()]
    for spectrum, label in zip(spectra, ['Nx', '15N', 'Ny']):
        spectrum.axes[0] = replace(spectrum.axes[0], label=label)
    widget = OverlayComparison()
    widget.set_spectra(spectra, ['Nx-H', 'N-H', 'Ny-H'])
    assert widget.toggle.isEnabled()
    widget.toggle.setChecked(True)
    widget.render()
    assert widget.viewer is not None
    widget.close()


def test_overlay_two_three_svg_and_reference(qapp, tmp_path):
    from gui.overlay_comparison import OverlayComparison

    spectra = [_spectrum(), _spectrum(displacement=(3, -5)), _spectrum()]
    widget = OverlayComparison()
    widget.set_spectra(spectra, ['current', 'reference', 'third'])
    widget.toggle.setChecked(True)
    widget.render()
    widget.viewer.resize(800, 650)
    widget.viewer.show()
    qapp.processEvents()
    assert len(widget.viewer.layers) == 3
    assert not widget.use_reference.isChecked()
    widget.set_color(1, '#ff00ff')
    widget.spins[0].setValue(.03)
    assert widget.shifts[1][1] == pytest.approx(.03)
    widget.use_reference.setChecked(True)
    assert widget.reference_index == 1
    assert widget.shifts[1] == pytest.approx([0, 0])
    widget.render()
    path = tmp_path / 'overlay.svg'
    widget.export_svg(path)
    xml = ET.parse(path)
    assert xml.getroot().tag.endswith('svg')
    content = path.read_text(encoding='utf-8')
    assert '#ff00ff' in content.lower()
    assert '>current<' not in content and '>third<' not in content
    assert 'ppm' in content
    assert '<image' not in content
    widget.viewer.close()
    widget.close()


def test_overlay_1d_and_stale_fit(qapp):
    from gui.overlay_comparison import OverlayComparison

    first = _spectrum()
    spectra = [Spectrum1D(first.data[25], first.axes[1]),
               Spectrum1D(first.data[25].copy(), first.axes[1])]
    widget = OverlayComparison()
    widget.set_spectra(spectra, ['first', 'second'])
    widget.toggle.setChecked(True)
    widget.render()
    assert len(widget.curves) == 2
    generation = widget.generation
    widget.spins[0].setValue(.02)
    widget._apply_fit(generation, {1: ((.08,), 1)}, None)
    assert widget.shifts[1][0] == pytest.approx(.02)
    widget.render()
    assert sum(item.isVisible() for item in widget.viewer.plot.listDataItems()) == 2
    widget.close()


@pytest.mark.parametrize('ndim', [1, 2])
@pytest.mark.parametrize('wide_index', [0, 1, 2])
def test_overlay_full_range_covers_wider_spectrum(qapp, ndim, wide_index):
    from gui.overlay_comparison import OverlayComparison
    from gui.overlay_svg_export import _current_ppm_ranges

    narrow = _spectrum()
    wide = Spectrum(narrow.data * 3, [replace(a, sw_hz=a.sw_hz * 3,
                                             orig_hz=a.orig_hz - a.sw_hz)
                                      for a in narrow.axes])
    spectra = [narrow, narrow, narrow]
    spectra[wide_index] = wide
    if ndim == 1:
        spectra = [Spectrum1D(s.data[25], s.axes[1]) for s in spectra]
    widget = OverlayComparison()
    widget.set_spectra(spectra, ['current', 'comparison', 'third'])
    widget.toggle.setChecked(True)
    for comparison_reference in [False, True]:
        widget.use_reference.setChecked(comparison_reference)
        widget.render()
        widget.viewer.reset_view()
        widget.render()
        qapp.processEvents()
        ranges = _current_ppm_ranges(widget.viewer)
        for position in range(ndim):
            axis = (spectra[wide_index].axis if ndim == 1
                    else spectra[wide_index].axes[1 - position])
            lo, hi = sorted(ranges[position])
            assert lo <= min(axis.ppm) + 1e-6
            assert hi >= max(axis.ppm) - 1e-6
        if ndim == 1:
            assert ranges[1][1] >= float(np.max(wide.data[25]))
            assert widget.viewer.plot.getAxis('bottom')._tickLevels is None
        else:
            ticks = widget.viewer.plot.getAxis('bottom')._tickLevels[0]
            assert len(ticks) >= 4
            base = widget.viewer.displayed_spectrum.x_axis
            if widget.reference_index != wide_index:
                assert any(index < 0 or index >= base.size for index, _ in ticks)
    widget.close()


def test_overlay_cursor_reports_ppm_beyond_fixed_spectrum(qapp):
    from qtcompat.QtCore import QPointF

    from gui.overlay_comparison import OverlayComparison

    narrow = _spectrum()
    wide = Spectrum(narrow.data, [replace(a, sw_hz=a.sw_hz * 3,
                                         orig_hz=a.orig_hz - a.sw_hz)
                                  for a in narrow.axes])
    widget = OverlayComparison()
    widget.set_spectra([narrow, wide], ['current', 'wide'])
    widget.toggle.setChecked(True)
    widget.render()
    point = QPointF(-30, 40)
    widget.viewer._on_mouse_moved(widget.viewer.plot.getViewBox().mapViewToScene(point))
    x_ppm = narrow.x_axis.ppm[0] - 30 * (narrow.x_axis.ppm[1] - narrow.x_axis.ppm[0])
    y_ppm = narrow.y_axis.ppm[40]
    assert widget.viewer.crosshair_label.text() == (
        f'1H {x_ppm:.3f} ppm | 15N {y_ppm:.3f} ppm'
    )
    widget.close()


def test_replacing_comparison_with_wider_range_resets_view_but_render_keeps_zoom(qapp):
    from gui.overlay_comparison import OverlayComparison

    widget = OverlayComparison()
    current = _spectrum()
    widget.set_spectra([current, _spectrum()], ['current', 'comparison'])
    widget.toggle.setChecked(True)
    widget.render()
    box = widget.viewer.plot.getViewBox()
    box.setRange(xRange=(20, 50), yRange=(20, 50), padding=0)
    zoom = box.viewRange()
    widget.render()
    np.testing.assert_allclose(box.viewRange(), zoom)
    wider = Spectrum(current.data, [replace(a, sw_hz=a.sw_hz * 3) for a in current.axes])
    widget.set_spectra([current, wider], ['current', 'comparison'])
    assert box.viewRange()[0][1] - box.viewRange()[0][0] > current.x_axis.size * 2
    widget.close()


def test_panel_three_comparison_overlay_close_and_context(qapp, tmp_path):
    from gui.spectrum_panel import SpectrumPanel
    from tests.test_gui_layout import _manager_with_experiment, _write_ft2

    manager = _manager_with_experiment(tmp_path)
    paths = []
    for experiment, name in [('exp_001', 'current'), ('exp_002', 'other'), ('exp_002', 'third')]:
        path = manager.data_dir(experiment, 'd_001', 'spectra') / (name + '.ft2')
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_ft2(path)
        paths.append(path)
    panel = SpectrumPanel(manager)
    panel.resize(1600, 1000)
    panel.set_context('exp_001', 'd_001')
    assert panel.load_current_spectrum()
    panel.show()
    panel.expand_button.setChecked(True)
    assert panel._load_compare_spectrum(paths[1])
    panel._activate_comparison(paths[1])
    assert not panel.overlay.controls.isHidden()
    panel.viewer.hide_negative.setChecked(True)
    panel._compare_viewer.hide_positive.setChecked(True)
    panel.overlay.toggle.setChecked(True)
    assert panel.overlay.spectrum_controls[0].hide_negative.isChecked()
    assert panel.overlay.spectrum_controls[1].hide_positive.isChecked()
    panel._add_third_comparison(paths[2])
    assert len(panel.overlay.spectra) == 3
    qapp.processEvents()
    assert 250 < panel._expand_splitter.sizes()[-1] <= 470
    panel.overlay.set_color(2, '#ff00ff')
    panel.overlay.toggle.setChecked(True)
    qapp.processEvents()
    assert panel._overlay_column is not None
    assert panel._current_column.isHidden() and panel._extra_compare_column.isHidden()
    assert len(panel.overlay.viewer.layers) == 3
    panel.overlay.spins[0].setValue(.02)
    assert panel.overlay.shifts[1][1] == pytest.approx(.02)
    panel.overlay.spectrum_controls[0].hide_positive.setChecked(True)
    panel.overlay.toggle.setChecked(False)
    assert not panel._current_column.isHidden()
    assert panel.viewer.hide_positive.isChecked() and panel.viewer.hide_negative.isChecked()
    assert panel._compare_viewer.hide_positive.isChecked()
    panel._remove_third_comparison()
    assert len(panel.overlay.spectra) == 2
    panel.overlay.toggle.setChecked(True)
    panel.set_context('exp_002', 'd_001')
    assert not panel._comparison_active
    assert panel._overlay_column is None
    assert panel.overlay.controls.isHidden()
    panel.expand_button.setChecked(False)
    panel.close()


def test_auto_fit_worker_applies_shift(qapp):
    from qtcompat.QtCore import QEventLoop, QTimer

    from gui.overlay_comparison import OverlayComparison

    widget = OverlayComparison()
    widget.set_spectra([_spectrum(), _spectrum(displacement=(3, -5))], ['fixed', 'moving'])
    widget.toggle.setChecked(True)
    widget.render()
    loop = QEventLoop()
    widget.fitted.connect(lambda *_: loop.quit())
    QTimer.singleShot(10000, loop.quit)
    widget.auto_fit()
    loop.exec()
    assert not widget.fit_running
    assert widget.shifts[1] == pytest.approx([.15, -.05], abs=.003)
    assert not widget.status.text()
    assert widget.status.isHidden()
    widget.close()


def test_3d_slice_controls_restore_after_overlay(qapp, tmp_path, monkeypatch):
    from gui.spectrum_panel import SpectrumPanel
    from tests.test_gui_layout import _manager_with_experiment
    from tests.test_viewer3d import _synthetic3d, _write_ft3

    manager = _manager_with_experiment(tmp_path)
    paths = []
    for exp in ('exp_001', 'exp_002'):
        path = manager.data_dir(exp, 'd_001', 'spectra') / 'plane.ft3'
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_ft3(path, _synthetic3d())
        paths.append(path)
    panel = SpectrumPanel(manager)
    monkeypatch.setattr(panel, '_ensure_plane_stream', lambda: None)
    panel.resize(1700, 1100)
    panel.show()
    panel.set_context('exp_001', 'd_001')
    assert panel.load_current_spectrum()
    qapp.processEvents()
    panel.expand_button.setChecked(True)
    assert panel._load_compare_spectrum(paths[1])
    panel._activate_comparison(paths[1])
    panel.overlay.toggle.setChecked(True)
    qapp.processEvents()
    assert panel._spectrum3d_panel.parentWidget() is panel.overlay.slice_controls
    assert panel._compare_3d_panel.parentWidget() is panel.overlay.slice_controls
    panel.overlay.use_reference.setChecked(True)
    panel._render_3d_view()
    qapp.processEvents()
    assert panel.overlay.reference_index == 1
    panel.overlay.toggle.setChecked(False)
    assert panel._spectrum3d_panel.parentWidget() is panel.viewer.controls_layout.parentWidget()
    panel._deactivate_comparison()
    panel.expand_button.setChecked(False)
    panel.close()


def test_peak_table_fit_resists_intensity_changes_and_extra_artifacts():
    from scipy.ndimage import shift as array_shift

    random = np.random.default_rng(23)
    data = np.zeros((128, 256))
    for y, x in [(18, 30), (24, 180), (36, 102), (50, 50), (69, 217),
                 (82, 141), (102, 74), (111, 210)]:
        data[y, x] = random.uniform(3, 10)
    data = gaussian_filter(data, 1.2)
    axes = [SpectrumAxis('15N', 128, 384, 60, 117),
            SpectrumAxis('1H', 256, 1536, 600, 8)]
    mobile = array_shift(data, (2.4, -3.7), order=3)
    mobile += random.normal(0, .001, mobile.shape)
    mobile[62:65, 23:26] += 30  # A very bright, unrelated artifact must not set the offset.
    offset, fraction = fit_translation(Spectrum(data, axes), Spectrum(mobile, axes))
    assert offset == pytest.approx((.12, -.037), abs=.003)
    assert fraction > .8


def test_independent_contours_fine_shift_and_reference_selector(qapp):
    from qtcompat.QtCore import Qt

    from gui.overlay_comparison import OverlayComparison

    widget = OverlayComparison()
    widget.set_spectra([_spectrum(), _spectrum(), _spectrum()], ['a', 'b', 'c'],
                       ['a: /raw/a', 'b: /raw/b', 'c: /raw/c'])
    widget.toggle.setChecked(True)
    widget.render()
    assert widget.reference_row.isHidden()
    assert widget.color_buttons[2].toolTip() == 'c: /raw/c'
    levels_before = widget.viewer.layers[0]._levels.copy()
    widget.spectrum_controls[1].start.setValue(12)
    widget.spectrum_controls[1].levels.setValue(12)
    np.testing.assert_array_equal(widget.viewer.layers[0]._levels, levels_before)
    assert len(widget.viewer.layers[1]._levels) == 24
    assert widget.viewer.layers[2]._pen_neg.style() == Qt.PenStyle.SolidLine
    # Fine travel is five data points; one tick is 1/200 of a data point.
    widget.fine_sliders[0].setValue(100)
    assert widget.shifts[1][1] == pytest.approx(.005)
    assert widget.spins[0].value() == pytest.approx(.005)
    widget.fine_sliders[0].sliderReleased.emit()
    assert widget.fine_sliders[0].value() == 0
    assert widget.shifts[1][1] == pytest.approx(.005)
    widget.use_reference.setChecked(True)
    assert not widget.reference_row.isHidden()
    widget.close()


def test_overlay_signed_contour_controls_are_independent_and_persistent(qapp):
    from qtcompat.QtCore import QPoint
    from qtcompat.QtGui import QFont

    from gui.overlay_comparison import OverlayComparison

    spectra = [_spectrum(), _spectrum(), _spectrum()]
    widget = OverlayComparison()
    widget.set_spectra(spectra, ['a', 'b', 'c'], display_settings=[
        (2.9791, 8), (3.5, 9, True, False), (4.5, 10, False, True),
    ])
    controls = widget.spectrum_controls
    controls[0].setFont(QFont(controls[0].font().family(), 18))
    widget.controls.resize(220, 600)
    widget.controls.show()
    widget.toggle.setChecked(True)
    widget.spectrum_tabs.setCurrentIndex(0)
    qapp.processEvents()
    qapp.processEvents()
    for button in (controls[0].hide_positive, controls[0].hide_negative):
        top_left = button.mapTo(controls[0], QPoint(0, 0))
        button_rect = button.rect().translated(top_left)
        assert controls[0].rect().contains(button_rect)
        assert button_rect.top() > controls[0].slider.geometry().bottom()
    assert all(not c.hide_positive.isChecked() and not c.hide_negative.isChecked()
               for c in controls[:1])
    assert controls[1].hide_positive.isChecked()
    assert not controls[1].hide_negative.isChecked()
    assert not controls[2].hide_positive.isChecked()
    assert controls[2].hide_negative.isChecked()
    assert controls[1].start.value() == pytest.approx(3.5)
    assert controls[1].levels.value() == 9

    widget.toggle.setChecked(True)
    widget.render()
    # Sign toggles update layer visibility without rebuilding contour levels.
    levels_before = [layer._levels.copy() for layer in widget.viewer.layers]
    controls[0].hide_positive.setChecked(True)
    assert [(layer._show_positive, layer._show_negative)
            for layer in widget.viewer.layers] == [
                (False, True), (False, True), (True, False),
            ]
    for layer, levels in zip(widget.viewer.layers, levels_before):
        np.testing.assert_array_equal(layer._levels, levels)

    controls[1].hide_negative.setChecked(True)
    assert (widget.viewer.layers[1]._show_positive,
            widget.viewer.layers[1]._show_negative) == (False, False)
    widget.use_reference.setChecked(True)
    assert widget.reference_index == 1
    assert controls[1].hide_positive.isChecked() and controls[1].hide_negative.isChecked()
    assert controls[0].hide_positive.isChecked() and not controls[0].hide_negative.isChecked()
    widget.render()
    assert widget.spectrum_controls[0].hide_positive.isChecked()
    assert widget.spectrum_controls[1].hide_negative.isChecked()
    assert [(layer._show_positive, layer._show_negative)
            for layer in widget.viewer.layers] == [
                (False, False), (False, True), (True, False),
            ]

    # The older two-value settings format remains accepted.
    restored = OverlayComparison()
    restored.set_spectra([_spectrum()], ['legacy'], display_settings=[(5.25, 11)])
    assert restored.spectrum_controls[0].start.value() == pytest.approx(5.25)
    assert restored.spectrum_controls[0].levels.value() == 11
    assert not restored.spectrum_controls[0].hide_positive.isChecked()
    assert not restored.spectrum_controls[0].hide_negative.isChecked()
    restored.set_spectra([Spectrum1D(s.data[25], s.axes[1]) for s in spectra[:2]],
                         ['current-1d', 'comparison-1d'])
    assert not restored.spectrum_controls[0].hide_positive.isEnabled()
    assert not restored.spectrum_controls[0].hide_negative.isEnabled()
    widget.close()
    restored.close()


def test_compare_sources_are_in_menu_and_color_tooltips(qapp, tmp_path, monkeypatch):
    from gui.spectrum_panel import SpectrumPanel
    from tests.test_gui_layout import _manager_with_experiment, _write_ft2

    manager = _manager_with_experiment(tmp_path)
    paths = []
    for exp, name in [('exp_001', 'current'), ('exp_002', 'reference')]:
        manager.data(exp, 'd_001').source = '/raw/' + name
        path = manager.data_dir(exp, 'd_001', 'spectra') / (name + '.ft2')
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_ft2(path)
        paths.append(path)
    panel = SpectrumPanel(manager)
    panel.resize(1700, 1100)
    panel.show()
    panel.set_context('exp_001', 'd_001')
    assert panel.load_current_spectrum()
    panel.expand_button.setChecked(True)
    panel._refresh_compare_menu()
    action = next(a for a in panel.compare_menu.actions() if isinstance(a.data(), (tuple, list)))
    assert '/raw/reference' in action.toolTip()
    assert panel.compare_menu.toolTipsVisible()
    assert panel._load_compare_spectrum(paths[1])
    panel._activate_comparison(paths[1])
    assert '/raw/current' in panel.overlay.color_buttons[0].toolTip()
    assert '/raw/reference' in panel.overlay.color_buttons[1].toolTip()
    assert panel.overlay.export_directory == manager.data_dir('exp_001', 'd_001', 'figures')
    seen = {}

    class ExportDialog:
        def __init__(self, viewer, parent, *, directory, spectra):
            seen.update(directory=directory, spectra=spectra)

        def exec(self):
            pass

    monkeypatch.setattr('gui.overlay_svg_export.OverlaySvgExportDialog', ExportDialog)
    panel.overlay.toggle.setChecked(True)
    panel.overlay.use_reference.setChecked(True)
    panel.overlay.set_color(1, '#ab12ef')
    panel.overlay._export()
    assert seen['directory'] == manager.data_dir('exp_001', 'd_001', 'figures')
    assert seen['spectra'] == list(zip(panel.overlay.names, panel.overlay.colors))
    qapp.processEvents()
    assert panel._expand_splitter.sizes()[-1] <= 470
    panel._deactivate_comparison()
    panel.expand_button.setChecked(False)
    panel.close()


@pytest.mark.parametrize('ndim', [1, 2, 3])
def test_compare_menu_loads_external_spectrum_without_replacing_current(
    qapp, tmp_path, monkeypatch, ndim,
):
    from gui.spectrum_panel import SpectrumPanel
    from tests.test_gui_layout import _manager_with_experiment, _write_ft2
    from tests.test_viewer3d import _synthetic3d, _write_ft3
    from tests.test_viewer_1d import _write_fid

    manager = _manager_with_experiment(tmp_path)
    current = manager.data_dir('exp_001', 'd_001', 'spectra') / 'current.ft2'
    current.parent.mkdir(parents=True)
    _write_ft2(current)
    external = tmp_path / f'outside-project.ft{ndim}'
    if ndim == 3:
        _write_ft3(external, _synthetic3d())
    elif ndim == 1:
        _write_fid(external, np.exp(-.5 * ((np.arange(128) - 60) / 3) ** 2))
    else:
        _write_ft2(external)
    panel = SpectrumPanel(manager)
    panel.set_context('exp_001', 'd_001')
    assert panel.load_current_spectrum()
    original = panel.viewer.displayed_spectrum
    panel.expand_button.setChecked(True)
    panel._refresh_compare_menu()
    action = next(a for a in panel.compare_menu.actions() if a.data() == '__load__')
    assert action.isEnabled()
    assert not panel._comparison_candidates()
    choices = iter(['', str(external), '', str(tmp_path / 'missing.ft2')])
    monkeypatch.setattr('gui.spectrum_panel.QFileDialog.getOpenFileName',
                        lambda *_args: (next(choices), ''))
    panel._on_compare_action(action)
    assert not panel._comparison_active
    panel._on_compare_action(action)
    assert panel._comparison_active
    assert panel._compare_spectrum == external
    assert panel._current_spectrum == current
    assert panel.viewer.displayed_spectrum is original
    assert panel._compare_viewer.displayed_spectrum is not None
    assert str(external) in panel.overlay.color_buttons[1].toolTip()
    panel._on_compare_action(action)
    assert panel._compare_spectrum == external
    panel._on_compare_action(action)
    assert not panel._comparison_active
    assert panel.viewer.displayed_spectrum is original
    panel.expand_button.setChecked(False)
    panel.close()


@pytest.mark.parametrize('ndim', [1, 2])
@pytest.mark.parametrize('fine', [False, True])
@pytest.mark.parametrize('comparison_reference', [False, True])
def test_shift_slider_right_moves_spectrum_right(qapp, ndim, fine, comparison_reference):
    from qtcompat.QtCore import QPointF, Qt
    from qtcompat.QtTest import QTest

    from gui.overlay_comparison import OverlayComparison

    spectrum = _spectrum()
    spectra = [spectrum, _spectrum()]
    if ndim == 1:
        spectra = [Spectrum1D(s.data[25], s.axes[1]) for s in spectra]
    widget = OverlayComparison()
    widget.set_spectra(spectra, ['current', 'comparison'])
    widget.toggle.setChecked(True)
    widget.use_reference.setChecked(comparison_reference)
    widget.render()
    widget.viewer.resize(800, 650)
    qapp.processEvents()
    moving = int(widget.moving.currentData())

    def peak_screen_x():
        if ndim == 2:
            order = [widget.reference_index, moving]
            layer = widget.viewer.layers[order.index(moving)]
            return layer.mapToScene(QPointF(35, 25)).x()
        curve = widget.curves[moving]
        return curve.mapToScene(QPointF(
            spectra[moving].axis.ppm[35] + widget.shifts[moving][0],
            spectra[moving].data[35],
        )).x()

    from qtcompat.QtWidgets import QStyle, QStyleOptionSlider

    bar = widget.fine_sliders[0] if fine else widget.sliders[0]
    bar.resize(400, 20)
    bar.setSingleStep(100)

    def handle_screen_x():
        option = QStyleOptionSlider()
        bar.initStyleOption(option)
        return bar.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option,
            QStyle.SubControl.SC_SliderHandle, bar,
        ).center().x()

    before_handle = handle_screen_x()
    before = peak_screen_x()
    QTest.keyClick(bar, Qt.Key.Key_Right)
    assert handle_screen_x() > before_handle
    assert peak_screen_x() > before
    assert widget.shifts[moving][-1] < 0  # ppm decreases to the right.
    assert widget.spins[0].value() < 0
    right = peak_screen_x()
    QTest.keyClick(bar, Qt.Key.Key_Left)
    assert peak_screen_x() < right
    assert widget.shifts[moving][-1] == pytest.approx(0)
    widget.close()


def test_fit_success_does_not_show_match_rate(qapp):
    from gui.overlay_comparison import OverlayComparison

    widget = OverlayComparison()
    widget.set_spectra([_spectrum(), _spectrum()], ['current', 'comparison'])
    widget.toggle.setChecked(True)
    widget._apply_fit(widget.generation, {1: ((.01, .02), .93)}, None)
    assert widget.shifts[1] == pytest.approx((.01, .02))
    assert not widget.status.text()
    assert widget.status.isHidden()
    widget.close()
