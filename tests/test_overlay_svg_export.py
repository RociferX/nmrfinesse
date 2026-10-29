from __future__ import annotations

import os
from copy import deepcopy

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pyqtgraph as pg
import pytest
from qtcompat.QtCore import QRectF
from qtcompat.QtGui import QPainter, QPixmap
from qtcompat.QtSvg import QSvgGenerator

from gui import overlay_svg_export as svg_export
from viewer.spectrum import Spectrum, Spectrum1D, SpectrumAxis
from viewer.spectrum_viewer import SpectrumViewer


def _spectrum():
    axes = [
        SpectrumAxis(label='N', size=32, sw_hz=2000, obs_mhz=60, carrier_ppm=120,
                     orig_hz=120 * 60),
        SpectrumAxis(label='H', size=48, sw_hz=3600, obs_mhz=600, carrier_ppm=4.7,
                     orig_hz=4.7 * 600),
    ]
    data = np.zeros((32, 48))
    data[12, 20] = 10
    return Spectrum(data, axes)


def _viewer_with_legend():
    viewer = SpectrumViewer()
    viewer.add_spectrum(_spectrum(), 'sample')
    legend = viewer.plot.addLegend()
    legend.addItem(pg.PlotDataItem(pen='blue'), 'sample')
    return viewer, legend


def test_export_maps_ppm_ranges_and_restores_view_and_legend(tmp_path, qapp):
    viewer, legend = _viewer_with_legend()
    vb = viewer.plot.getViewBox()
    vb.setRange(xRange=(10, 30), yRange=(5, 25), padding=0)
    before = vb.viewRange()
    axes = viewer.displayed_spectrum
    ppm_ranges = ((float(axes.x_axis.ppm_at(8)), float(axes.x_axis.ppm_at(38))),
                  (float(axes.y_axis.ppm_at(3)), float(axes.y_axis.ppm_at(28))))
    mapped = svg_export._data_ranges(viewer, ppm_ranges)
    assert mapped[0] == pytest.approx((8, 38))
    assert mapped[1] == pytest.approx((3, 28))
    path = tmp_path / 'overlay.svg'
    svg_export.export_svg(viewer, path, ppm_ranges)
    assert path.exists()
    after = vb.viewRange()
    assert after[0] == pytest.approx(before[0])
    assert after[1] == pytest.approx(before[1])
    assert legend.isVisible()
    svg = path.read_text(encoding='utf-8')
    assert '<svg' in svg
    assert 'sample' not in svg
    viewer.close()


def test_export_omits_hidden_legend_and_preserves_hidden_state(tmp_path, qapp):
    viewer, legend = _viewer_with_legend()
    legend.hide()
    svg_export.export_svg(viewer, tmp_path / 'no_legend.svg')
    assert not legend.isVisible()
    viewer.close()


def test_locked_aspect_keeps_requested_range_exact_during_render(tmp_path, qapp, monkeypatch):
    viewer, _legend = _viewer_with_legend()
    vb = viewer.plot.getViewBox()
    vb.setAspectLocked(True, ratio=2.5)
    vb.setLimits(xMin=0, xMax=47, yMin=0, yMax=31,
                 minXRange=2, maxXRange=200, minYRange=2, maxYRange=200)
    qapp.processEvents()
    before = vb.viewRange()
    old_auto_range = tuple(vb.autoRangeEnabled())
    old_limits = deepcopy(vb.state['limits'])
    spectrum = viewer.displayed_spectrum
    ppm_ranges = (
        (spectrum.x_axis.ppm[0] - 5 * (spectrum.x_axis.ppm[1] - spectrum.x_axis.ppm[0]),
         spectrum.x_axis.ppm_at(15)),
        (spectrum.y_axis.ppm_at(2), spectrum.y_axis.ppm_at(22)),
    )
    expected = ((-5.0, 15.0), (2.0, 22.0))
    mapped = svg_export._data_ranges(viewer, ppm_ranges)
    assert mapped[0] == pytest.approx(expected[0])
    assert mapped[1] == pytest.approx(expected[1])
    scene = viewer.plot.scene()
    seen = {}

    class SceneProxy:
        def render(self, *args):
            seen['ranges'] = vb.viewRange()
            seen['limits'] = deepcopy(vb.state['limits'])
            scene.render(*args)

    monkeypatch.setattr(viewer.plot, 'scene', lambda: SceneProxy())
    svg_export.export_svg(viewer, tmp_path / 'locked.svg', ppm_ranges)
    assert seen['ranges'][0] == pytest.approx(expected[0]), seen
    assert seen['ranges'][1] == pytest.approx(expected[1])
    after = vb.viewRange()
    assert after[0] == pytest.approx(before[0])
    assert after[1] == pytest.approx(before[1])
    assert vb.state['aspectLocked'] == pytest.approx(2.5)
    assert tuple(vb.autoRangeEnabled()) == old_auto_range
    assert vb.state['limits'] == old_limits
    viewer.close()


def test_current_view_range_round_trips_beyond_spectrum_edges(qapp):
    viewer, _legend = _viewer_with_legend()
    vb = viewer.plot.getViewBox()
    vb._min_rect = None
    vb.setRange(xRange=(-5, 55), yRange=(-3, 37), padding=0)
    original = vb.viewRange()
    ppm_ranges = svg_export._current_ppm_ranges(viewer)
    mapped = svg_export._data_ranges(viewer, ppm_ranges)
    assert mapped[0] == pytest.approx(original[0])
    assert mapped[1] == pytest.approx(original[1])
    viewer.close()


def test_one_dimensional_x_range_is_used_as_ppm_directly(qapp):
    viewer = SpectrumViewer()
    axis = SpectrumAxis(label='H', size=16, sw_hz=1600, obs_mhz=600, carrier_ppm=4.7,
                        orig_hz=4.7 * 600)
    viewer.add_spectrum(Spectrum1D(np.arange(16.0), axis), 'trace')
    assert svg_export._data_ranges(viewer, ((1.0, 5.0), (-2.0, 20.0))) == (
        (1.0, 5.0), (-2.0, 20.0)
    )
    viewer.close()


def test_preview_and_save_call_same_renderer(monkeypatch, qapp, tmp_path):
    calls = []

    def fake_render(viewer, path, ranges=None, aspect_ratio=None):
        calls.append((path, ranges, aspect_ratio))
        generator = QSvgGenerator()
        generator.setFileName(str(path))
        generator.setSize(svg_export.QSize(20, 20))
        generator.setViewBox(QRectF(0, 0, 20, 20))
        painter = QPainter()
        assert painter.begin(generator)
        painter.end()

    monkeypatch.setattr(svg_export, '_render_svg', fake_render)
    viewer, _legend = _viewer_with_legend()
    dialog = svg_export.OverlaySvgExportDialog(viewer)
    # Constructor creates the initial preview through the common render helper.
    assert len(calls) == 1
    dialog.x_min.setValue(dialog.x_min.value() + 0.1)
    dialog.update_preview()
    assert calls[-1][1] == dialog.ppm_ranges()
    monkeypatch.setattr(svg_export.QFileDialog, 'getSaveFileName',
                        lambda *_args: (str(tmp_path / 'saved.svg'), 'SVG (*.svg)'))
    dialog.save_svg()
    assert calls[-1][1] == dialog.ppm_ranges()
    assert len(calls) == 3
    assert calls[-1][2] == dialog.aspect_spin.value()
    dialog.aspect_spin.setValue(2.5)
    assert calls[-1][2] == 2.5
    assert dialog.aspect_slider.value() == 250
    dialog.aspect_slider.setValue(75)
    assert calls[-1][2] == .75
    dialog.save_svg()
    assert calls[-1][2] == .75
    dialog.close()
    viewer.close()


def test_preview_thumbnail_fits_without_distorting_source_aspect(qapp):
    preview = svg_export._SvgPreviewLabel()
    preview.resize(80, 80)
    preview.set_source_pixmap(QPixmap(100, 50))
    assert preview.pixmap().size().width() == 80
    assert preview.pixmap().size().height() == 40


@pytest.mark.parametrize('count', [2, 3])
def test_save_defaults_to_current_figures_and_names_each_spectrum_color(
    qapp, tmp_path, monkeypatch, count,
):
    from ui_support.i18n import tr

    viewer, _legend = _viewer_with_legend()
    spectra = [('current:HSQC', '#1f77b4'), ('author', '#d62728'), ('third', '#ab12ef')][:count]
    directory = tmp_path / 'current-data' / 'figures'
    dialog = svg_export.OverlaySvgExportDialog(viewer, directory=directory, spectra=spectra)
    seen = []
    chosen = tmp_path / 'chosen-name'

    def choose(_parent, _title, default, _filter):
        seen.append(default)
        return str(chosen), 'SVG (*.svg)'

    monkeypatch.setattr(svg_export.QFileDialog, 'getSaveFileName', choose)
    dialog.save_svg()
    default = svg_export.Path(seen[0])
    assert default.parent == directory
    assert directory.is_dir()
    assert f'current_HSQC_{tr("Blue")}(#1f77b4)' in default.name
    assert f'author_{tr("Red")}(#d62728)' in default.name
    assert default.name.count('_vs_') == count - 1
    assert ('third_(#ab12ef)' in default.name) == (count == 3)
    for name, color in spectra:
        assert name in dialog.spectrum_description.text()
        assert color in dialog.spectrum_description.text()
    assert chosen.with_suffix('.svg').exists()
    assert not (directory / default.name).exists()
    dialog.close()
    viewer.close()


@pytest.mark.parametrize('aspect_ratio', [.5, 2.5])
def test_export_aspect_reflows_plot_and_keeps_ranges_fonts_and_original_view(
    qapp, tmp_path, monkeypatch, aspect_ratio,
):
    import xml.etree.ElementTree as ET

    viewer, legend = _viewer_with_legend()
    viewer.resize(800, 650)
    viewer.show()
    qapp.processEvents()
    plot, vb = viewer.plot.plotItem, viewer.plot.getViewBox()
    before_geometry = QRectF(plot.geometry())
    before_ranges = vb.viewRange()
    ranges = svg_export._current_ppm_ranges(viewer)
    baseline_path = tmp_path / 'baseline.svg'
    svg_export.export_svg(viewer, baseline_path, ranges)
    baseline_fonts = {element.attrib['font-size']
                      for element in ET.parse(baseline_path).getroot().iter()
                      if 'font-size' in element.attrib}
    scene = viewer.plot.scene()
    seen = {}

    class SceneProxy:
        def render(self, *args):
            seen['ranges'] = vb.viewRange()
            seen['geometry'] = QRectF(plot.geometry())
            scene.render(*args)

    monkeypatch.setattr(viewer.plot, 'scene', lambda: SceneProxy())
    path = tmp_path / 'resized.svg'
    svg_export.export_svg(viewer, path, ranges, aspect_ratio)
    svg = ET.parse(path).getroot()
    _, _, width, height = map(float, svg.attrib['viewBox'].split())
    assert width / height == pytest.approx(aspect_ratio, rel=.005)
    assert {element.attrib['font-size'] for element in svg.iter()
            if 'font-size' in element.attrib} == baseline_fonts
    assert seen['geometry'].width() / seen['geometry'].height() == pytest.approx(
        aspect_ratio, rel=.005,
    )
    assert seen['ranges'][0] == pytest.approx(before_ranges[0])
    assert seen['ranges'][1] == pytest.approx(before_ranges[1])
    assert plot.geometry() == before_geometry
    assert vb.viewRange()[0] == pytest.approx(before_ranges[0])
    assert vb.viewRange()[1] == pytest.approx(before_ranges[1])
    assert legend.isVisible()
    assert 'sample' not in path.read_text(encoding='utf-8')
    viewer.close()



def _spectral_color_mask(image):
    from qtcompat.QtGui import QImage

    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    rows = np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    rgb = rows[:, :image.width() * 4].reshape(image.height(), image.width(), 4)
    rgb = rgb[:, :, :3].astype(int)
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    return ((blue > red + 40) & (blue > green + 15)) | (
        (red > green + 50) & (red > blue + 50)
    )


def _svg_image(path, device_ratio=1.0):
    from qtcompat.QtGui import QImage
    from qtcompat.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(path))
    size = renderer.defaultSize()
    image = QImage(round(size.width() * device_ratio), round(size.height() * device_ratio),
                   QImage.Format.Format_ARGB32)
    image.setDevicePixelRatio(device_ratio)
    image.fill(0xffffffff)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
    painter.end()
    return image


@pytest.mark.parametrize('hide_positive,hide_negative', [(False, False), (True, False),
                                                       (False, True), (True, True)])
def test_svg_renders_only_the_enabled_contour_signs(qapp, tmp_path, hide_positive, hide_negative):
    from qtcompat.QtGui import QImage

    viewer = SpectrumViewer()
    spectrum = _spectrum()
    spectrum.data[22, 35] = -10
    before = spectrum.data.copy()
    viewer.add_spectrum(spectrum, color='#1f77b4')
    viewer.resize(800, 650)
    viewer.show()
    qapp.processEvents()
    viewer.set_contour_signs(hide_positive=hide_positive, hide_negative=hide_negative)
    path = tmp_path / 'signs.svg'
    svg_export.export_svg(viewer, path)
    image = _svg_image(path).convertToFormat(QImage.Format.Format_RGBA8888)
    rgba = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
        image.height(), image.bytesPerLine() // 4, 4,
    ).astype(int)
    red, green, blue = rgba[..., 0], rgba[..., 1], rgba[..., 2]
    positive_ink = ((blue > red + 40) & (blue > green + 20)).sum()
    negative_ink = ((red > green + 80) & (red > blue + 80)).sum()
    assert bool(positive_ink) == (not hide_positive)
    assert bool(negative_ink) == (not hide_negative)
    np.testing.assert_array_equal(spectrum.data, before)
    viewer.close()


def test_svg_contour_ink_matches_screen_line_width(qapp, tmp_path):
    from tests.test_spectrum_overlay import _spectrum

    viewer = SpectrumViewer()
    viewer.set_data_bounds_visible(False)
    viewer.add_spectrum(_spectrum())
    viewer.resize(800, 650)
    viewer.show()
    qapp.processEvents()
    screen_ink = _spectral_color_mask(viewer.plot.grab().toImage()).sum()
    path = tmp_path / 'thin-contours.svg'
    svg_export.export_svg(viewer, path, svg_export._current_ppm_ranges(viewer))
    svg_ink = _spectral_color_mask(_svg_image(path, viewer.plot.devicePixelRatioF())).sum()
    assert screen_ink > 100
    assert .8 < svg_ink / screen_ink < 1.25
    assert '<image' not in path.read_text(encoding='utf-8')
    viewer.close()


@pytest.mark.parametrize('connected', [False, True])
def test_dense_paths_survive_svg_export_and_dialog_preview(qapp, tmp_path, capfd, connected):
    from qtcompat.QtGui import QPainterPath

    viewer, _legend = _viewer_with_legend()
    viewer.set_data_bounds_visible(False)
    path = QPainterPath()
    if connected:
        x = np.linspace(2, 45, 40000)
        y = 16 + 8 * np.sin(x * 2)
        path.moveTo(float(x[0]), float(y[0]))
        for px, py in zip(x[1:], y[1:]):
            path.lineTo(float(px), float(py))
    else:
        angles = np.linspace(0, 2 * np.pi, 50)
        for cx in np.linspace(2, 45, 40):
            for cy in np.linspace(2, 29, 24):
                path.moveTo(float(cx + .2), float(cy))
                for angle in angles[1:]:
                    path.lineTo(float(cx + .2 * np.cos(angle)),
                                float(cy + .2 * np.sin(angle)))
    viewer.layers[0]._path = path
    viewer.layers[0]._path_neg = QPainterPath()
    viewer.resize(800, 650)
    viewer.show()
    qapp.processEvents()
    screen_ink = _spectral_color_mask(viewer.plot.grab().toImage()).sum()
    output = tmp_path / 'dense.svg'
    svg_export.export_svg(viewer, output, svg_export._current_ppm_ranges(viewer))
    svg_ink = _spectral_color_mask(_svg_image(output, viewer.plot.devicePixelRatioF())).sum()
    assert screen_ink > 100
    assert .8 < svg_ink / screen_ink < 1.25
    dialog = svg_export.OverlaySvgExportDialog(viewer)
    preview_ink = _spectral_color_mask(dialog.preview._source_pixmap.toImage()).sum()
    assert .8 < preview_ink / screen_ink < 1.25
    assert 'path truncated' not in capfd.readouterr().err
    assert '<image' not in output.read_text(encoding='utf-8')
    dialog.close()
    viewer.close()


@pytest.mark.parametrize('ndim', [1, 2])
@pytest.mark.parametrize('aspect_ratio', [.75, 2.0])
def test_svg_crop_keeps_spectral_ink_inside_plot(qapp, tmp_path, monkeypatch, ndim, aspect_ratio):
    from tests.test_spectrum_overlay import _spectrum

    spectrum = _spectrum()
    viewer = SpectrumViewer()
    viewer.set_data_bounds_visible(False)
    if ndim == 2:
        viewer.add_spectrum(spectrum)
        ranges = ((spectrum.x_axis.ppm[30], spectrum.x_axis.ppm[90]),
                  (spectrum.y_axis.ppm[30], spectrum.y_axis.ppm[65]))
    else:
        x = np.arange(128)
        line = np.exp(-.5 * ((x - 35) / 2) ** 2) + .8 * np.exp(-.5 * ((x - 80) / 2) ** 2)
        viewer.add_spectrum(Spectrum1D(line, spectrum.axes[1]))
        ranges = ((spectrum.x_axis.ppm[30], spectrum.x_axis.ppm[70]), (.1, 1.1))
    viewer.resize(800, 650)
    viewer.show()
    qapp.processEvents()
    scene = viewer.plot.scene()
    seen = {}

    class SceneProxy:
        def render(self, painter, target, source):
            rect = viewer.plot.getViewBox().sceneBoundingRect()
            sx, sy = target.width() / source.width(), target.height() / source.height()
            seen['clip'] = ((rect.left() - source.left()) * sx,
                            (rect.top() - source.top()) * sy,
                            (rect.right() - source.left()) * sx,
                            (rect.bottom() - source.top()) * sy)
            scene.render(painter, target, source)

    monkeypatch.setattr(viewer.plot, 'scene', lambda: SceneProxy())
    path = tmp_path / 'cropped.svg'
    svg_export.export_svg(viewer, path, ranges, aspect_ratio)
    mask = _spectral_color_mask(_svg_image(path))
    assert mask.sum() > 50
    y, x = np.indices(mask.shape)
    left, top, right, bottom = seen['clip']
    outside = (x < left - 1) | (x > right + 1) | (y < top - 1) | (y > bottom + 1)
    assert not mask[outside].any()
    viewer.close()
