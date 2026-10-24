"""Read-only carrier alternatives for explicit manual fid.com editing."""
from __future__ import annotations

import math
import re

from backend.bruker_workflow import (
    _temperature_kelvin,
    gamma_mapped_car,
    gamma_ratio,
    water_shift_ppm,
)
from ui_support.i18n import tr

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_CAR = re.compile(rf"(?<!\S)-([xyz]CAR)(\s+)({_NUMBER})(?![\w.])")


def _code_lines(content):
    """Separate shell comments without splitting quoted paths."""
    for line in content.splitlines(keepends=True):
        quote = None
        escaped = False
        for index, char in enumerate(line):
            if escaped:
                escaped = False
            elif char == "\\" and quote != "'":
                escaped = True
            elif char in ("'", '"'):
                if quote == char:
                    quote = None
                elif quote is None:
                    quote = char
            elif char == "#" and quote is None:
                yield line[:index], line[index:]
                break
        else:
            yield line, ""


def script_carrier_values(content):
    return {m[1]: m[3] for code, _comment in _code_lines(content)
            for m in _CAR.finditer(code)}


def replace_script_carrier(content, key, value):
    """Replace an existing finite numeric CAR; never insert missing parameters."""
    if key not in {"xCAR", "yCAR", "zCAR"} or not math.isfinite(float(value)):
        raise ValueError("CAR must be a finite ppm value for an existing axis")
    if key not in script_carrier_values(content):
        raise ValueError("CAR parameter is absent from the script")
    text = str(value).strip()
    if re.fullmatch(_NUMBER, text) is None:
        raise ValueError("CAR must be numeric")
    return "".join(_CAR.sub(lambda m: f"-{key}{m[2]}{text}" if m[1] == key else m[0], code)
                   + comment for code, comment in _code_lines(content))


def _finite(block, key):
    try:
        value = float(block[key])
        return value if math.isfinite(value) else None
    except (KeyError, TypeError, ValueError):
        return None


def carrier_choices(experiment):
    """Return acquisition-derived options; no reference is adopted automatically."""
    blocks = ["acqus", "acqu2s", "acqu3s"]
    axes = ["F3", "F2", "F1"] if experiment.ndim >= 3 else ["F2", "F1"]
    letters = {axis: letter for axis, letter in zip(axes, "xyz")}
    dims = {dim.logical_axis: dim for dim in experiment.dimensions}
    acquisition = experiment.acquisition_parameters or {}
    direct = dims.get(axes[0])
    direct_block = acquisition.get("acqus", {}) or {}
    direct_offset = _finite(direct_block, "O1")
    direct_base = _finite(direct_block, "BF1")
    direct_center = (direct_offset / direct_base
                     if direct_offset is not None and direct_base is not None and direct_base > 0
                     else None)
    temperature = _temperature_kelvin(direct_block.get("TE"))
    results = []
    for axis, filename in zip(axes, blocks):
        dim = dims.get(axis)
        if dim is None:
            continue
        block = acquisition.get(filename, {}) or {}
        options = []

        def add(value, label, description):
            if value is not None and math.isfinite(value):
                options.append({"value": value, "label": label, "description": description})

        offset, base, observed = (_finite(block, key) for key in ("O1", "BF1", "SFO1"))
        add(offset / base if offset is not None and base is not None and base > 0 else None,
            tr("Acquisition centre: O1/BF1"),
            tr("Transmitter offset divided by the base frequency. Use when matching the "
               "acquisition-centre convention; it can differ from NMRPipe's indirect reference."))
        add(_finite(block, "O1P"), tr("Recorded O1P"),
            tr("The ppm offset explicitly recorded in this acquisition file. "
               "Compare with O1/BF1 if the metadata disagree."))
        add(offset / observed
            if offset is not None and observed is not None and observed > 0 else None,
            tr("Legacy denominator: O1/SFO1"),
            tr("Uses the observed frequency instead of BF1. Mainly useful for matching older "
               "scripts; prefer O1/BF1 for the acquisition-centre convention "
               "when BF1 is available."))
        if (direct is not None and math.isfinite(direct.sf) and math.isfinite(dim.sf)
                and direct.sf > 0 and dim.sf > 0):
            mapped = (gamma_mapped_car(direct_center, direct.sf, dim.sf,
                                      direct.nucleus, dim.nucleus)
                      if direct_center is not None and axis != axes[0] else None)
            add(mapped, tr("Direct acquisition reference + gamma ratio"),
                tr("Indirect reference mapped from the direct acquisition centre using NMRPipe's "
                   "nuclear frequency ratios. Use to match that reference convention, "
                   "not as an independent calibration."))
            if temperature is not None and gamma_ratio(direct.nucleus) == 1.0:
                water = water_shift_ppm(temperature)
                value = water if axis == axes[0] else gamma_mapped_car(
                    water, direct.sf, dim.sf, direct.nucleus, dim.nucleus)
                add(value, tr("Water temperature reference + gamma ratio"),
                    tr("Approximate NMRPipe water reference at {p0:g} K; indirect axes use nuclear "
                       "frequency ratios. Use only when the direct proton transmitter was placed "
                       "on water and this convention is intended. Solvent, temperature and "
                       "referencing can introduce offsets.", p0=temperature))
        results.append({"key": letters[axis] + "CAR", "axis": axis,
                        "nucleus": dim.nucleus, "options": options})
    return results
