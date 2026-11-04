"""Physical-row, selection and source-preservation tests for raw NUS export."""

import numpy as np
import pytest

from workflow.uniform_nus import _rows, export_nus, inspect_uniform


def source_data(tmp_path, ndim=2, byte_order=0):
    root = tmp_path / "raw"
    root.mkdir()
    root.joinpath("acqus").write_text(
        f"##$TD= 514\n##$DTYPA= 2\n##$BYTORDA= {byte_order}\n##$AQ_mod= 3\n"
        f"##$AQSEQ= 0\n##$PARMODE= {ndim - 1}\n##$GRPDLY= 0\n##END=\n"
    )
    root.joinpath("acqu2s").write_text("##$TD= 8\n##$FnMODE= 4\n##END=\n")
    if ndim == 3:
        root.joinpath("acqu3s").write_text("##$TD= 10\n##$FnMODE= 6\n##END=\n")
    nrows = 8 if ndim == 2 else 80
    data = np.zeros((nrows, 640), dtype=">f8" if byte_order else "<f8")
    t = np.arange(257)
    for i in range(nrows):
        trace = (i + 1) * np.exp(-t / 200) * np.exp(1j * (t * 0.13 + i * 0.17))
        data[i, :514:2] = trace.real
        data[i, 1:514:2] = trace.imag
    data.tofile(root / "ser")
    return root, data


@pytest.mark.parametrize("ndim", [2, 3])
@pytest.mark.parametrize("byte_order", [0, 1])
def test_manual_compacts_complete_groups_and_keeps_absolute_coordinates(tmp_path, ndim, byte_order):
    source, data = source_data(tmp_path, ndim, byte_order)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    # Origin may be bad: never silently retain it or renumber later coordinates.
    excluded = [(0,)] if ndim == 2 else [(0, 0), (2, 3)]
    output = tmp_path / "output"
    report = export_nus(source, output, excluded=excluded)
    td = [514, 8] + ([10] if ndim == 3 else [])
    schedule = [
        tuple(map(int, line.split())) for line in (output / "nuslist").read_text().splitlines()
    ]
    assert not set(excluded) & set(schedule)
    assert report["selection"] == "manual"
    assert report["sample_count"] == (4 if ndim == 2 else 20) - len(excluded)
    assert (output / "ser").read_bytes() == b"".join(
        data[r].tobytes() for c in schedule for r in _rows(c, td)
    )
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    assert "##$NusTD= 8" in (output / "acqu2s").read_text()
    assert "##$FnTYPE= 2" in (output / "acqus").read_text()
    if ndim == 3:
        assert "##$NusTD= 10" in (output / "acqu3s").read_text()
    assert not list(tmp_path.glob(".nus-export-*"))


@pytest.mark.parametrize("ndim", [2, 3])
def test_auto_detects_zero_nonfinite_and_spike_and_drops_phase_groups(tmp_path, ndim):
    source, data = source_data(tmp_path, ndim)
    td = [514, 8] + ([10] if ndim == 3 else [])
    coords = [(0,), (1,), (2,)] if ndim == 2 else [(0, 0), (1, 0), (2, 0)]
    # A 2D four-point grid cannot delete three and leave two; inspect it only.
    for r in _rows(coords[0], td):
        data[r, :514] = 0
    data[_rows(coords[1], td)[0], 50] = np.nan
    data[_rows(coords[2], td)[-1], 200] = 1e9
    data.tofile(source / "ser")
    report = inspect_uniform(source)
    points = {tuple(p["coordinate"]): p for p in report["points"]}
    assert "all_zero_increment" in points[coords[0]]["reasons"]
    assert "nonfinite" in points[coords[1]]["reasons"]
    assert "isolated_spike" in points[coords[2]]["reasons"]
    assert all(points[c]["auto_remove"] for c in coords)
    if ndim == 3:
        exported = export_nus(source, tmp_path / "out", automatic=True)
        assert set(coords) <= {tuple(c) for c in exported["deleted_coordinates"]}


def test_stale_inspection_and_invalid_selection_leave_no_output(tmp_path):
    source, _ = source_data(tmp_path)
    report = inspect_uniform(source)
    (source / "title").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        export_nus(source, tmp_path / "stale", excluded=[(1,)], expected_source=report["source"])
    with pytest.raises(ValueError, match="outside"):
        export_nus(source, tmp_path / "outside", excluded=[(99,)])
    with pytest.raises(ValueError, match="At least two"):
        export_nus(source, tmp_path / "empty", excluded=[(0,), (1,), (2,)])
    assert not any((tmp_path / name).exists() for name in ("stale", "outside", "empty"))


def test_existing_destination_and_unsupported_order_preserved(tmp_path):
    source, _ = source_data(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    (output / "sentinel").write_text("keep")
    with pytest.raises(ValueError, match="exists"):
        export_nus(source, output, excluded=[(1,)])
    assert (output / "sentinel").read_text() == "keep"
    path = source / "acqus"
    path.write_text(path.read_text().replace("AQSEQ= 0", "AQSEQ= 1"))
    with pytest.raises(ValueError, match="AQSEQ"):
        inspect_uniform(source)


def test_readonly_metadata_and_non_utf8_comments_are_preserved(tmp_path):
    source, _ = source_data(tmp_path)
    params = source / "acqus"
    params.write_bytes(params.read_bytes() + b"$$ micro: \xb5\n")
    title = source / "pdata/1/title"
    title.parent.mkdir(parents=True)
    title.write_text("Sample title", encoding="utf-8")
    (title.parent / "old.ft2").write_bytes(b"old processed spectrum")
    before = params.read_bytes()
    params.chmod(0o444)
    try:
        export_nus(source, tmp_path / "out", excluded=[(1,)])
    finally:
        params.chmod(0o644)
    assert params.read_bytes() == before
    assert b"$$ micro: \xb5\n" in (tmp_path / "out/acqus").read_bytes()
    assert (tmp_path / "out/pdata/1/title").read_text() == "Sample title"
    assert not (tmp_path / "out/pdata/1/old.ft2").exists()


def test_large_dense_3d_schedule_is_accepted_and_size_bound_remains(tmp_path):
    from core.data.nus_reader import _SCHEDULE_MAX_BYTES, find_schedule_file

    schedule = tmp_path / "nuslist"
    schedule.write_text("".join(f"{y} {z}\n" for z in range(129) for y in range(129)))
    assert schedule.stat().st_size > 64 * 1024
    found, _ = find_schedule_file(tmp_path, expected_columns=2)
    assert found == schedule
    with schedule.open("wb") as stream:
        stream.truncate(_SCHEDULE_MAX_BYTES + 1)
    found, _ = find_schedule_file(tmp_path, expected_columns=2)
    assert found is None
