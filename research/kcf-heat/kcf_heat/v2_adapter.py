"""Evaluate the repository's v2 solid-flame panel law (experimental/flame-front-radiation, unchanged) on the
straight-front geometry measured in the C064 field.

The v2 operator places two diffuse emitting panels of exitance E (default 100 kW/m2) on the leading and trailing
contours of the flaming zone, with height from Byram's L = 0.0775 I^0.46 and Putnam wind tilt (vertical when the wind
is zero, the library default). Here the receiver is at the origin, height z_r, and the front lies at +x and moves
towards it: the leading panel at x = d, the trailing panel at x = d + depth, both spanning y in [-w/2, w/2].
``receiver='vertical_facing(0)'`` is a horizontal normal facing the fire (the FDS radiometer orientation);
``'worst_case'`` is the v2 default (each panel's own maximising normal).
"""
from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[3] / "experimental" / "flame-front-radiation" / "src"


def _lib():
    if str(_LIB) not in sys.path:
        sys.path.insert(0, str(_LIB))
    from wfg_flamefront.solidflame import rectangle_flux
    from wfg_flamefront.intensity import flame_length, flame_geometry
    from wfg_flamefront.provenance import provenance
    return rectangle_flux, flame_length, flame_geometry, provenance


def v2_emissive_power_default():
    return _lib()[3]()["constants"]["emissive_power_kw_m2"]["value"]


def v2_flux(d_m, depth_m, width_m, intensity_kw_m, *, receiver_height_m=1.5, emissive_power_kw_m2=None,
            receiver="vertical_facing(0)", wind_toward_receiver_m_s=0.0, panels=("leading", "trailing")):
    rectangle_flux, flame_length, flame_geometry, _ = _lib()
    e = v2_emissive_power_default() if emissive_power_kw_m2 is None else float(emissive_power_kw_m2)
    length = flame_length(intensity_kw_m)
    height, _tilt, shift = flame_geometry(length, (-float(wind_toward_receiver_m_s), 0.0))
    w = float(width_m) / 2.0
    total = 0.0
    for kind in panels:
        x0 = d_m if kind == "leading" else d_m + depth_m
        total += rectangle_flux((0.0, 0.0), (x0, -w), (x0, w), height, e, tip_shift_xy=shift, receiver=receiver,
                                receiver_height_m=receiver_height_m)
    return total, {"flame_length_m": length, "panel_height_m": height, "tip_shift_x_m": shift[0], "E_kw_m2": e}
