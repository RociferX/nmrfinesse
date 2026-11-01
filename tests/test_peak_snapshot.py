"""Picked-table CSV round trips preserve native coordinates and annotations."""

import pytest

from workflow.peak_snapshot import load_peak_snapshot, save_peak_snapshot


@pytest.mark.parametrize("coordinates", [
    {"H_shift": 8.123456789, "N_shift": 115.123456789},
    {"F1_shift": 115.123456789, "F2_shift": 54.123456789, "F3_shift": 8.123456789},
])
def test_snapshot_preserves_rows(tmp_path, coordinates):
    rows = [{"Peak_ID": 7, **coordinates, "label": "G1H-G1N",
             "SN": 123.123456789, "Intensity": -12345.6789123, "comment": "a,b\nc"}]
    path = save_peak_snapshot(tmp_path / "picked.csv", rows)
    assert load_peak_snapshot(path) == rows


@pytest.mark.parametrize("text", [
    "assignment,H_ppm,N_ppm\nG1,8,115\n",
    "Peak_ID,H_shift,N_shift\n1,no,115\n",
    "Peak_ID,H_shift,N_shift\n1,nan,115\n",
    "Peak_ID,H_shift,N_shift\n",
])
def test_snapshot_rejects_wrong_or_incomplete_csv(tmp_path, text):
    path = tmp_path / "wrong.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_peak_snapshot(path)
