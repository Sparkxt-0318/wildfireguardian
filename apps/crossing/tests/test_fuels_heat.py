"""fuels.py (FBFM40 table copy, residence, consumed load, heat content) and heat.py (closed form, FDS reference)."""
import csv
import json
import math
import sys

import pytest

from crossing import _repo, fuels, heat


# ------------------------------------------------------------------------------------------------- fuels
@pytest.mark.parametrize("code,expected", [("GR1", 11.2), ("SH6", 20.1), ("TU4", 10.4)])
def test_residence_listed_values(code, expected):
    assert round(fuels.get_fuel(code).residence_s, 1) == expected


def _forecast_heat():
    """forecast/wildfire/heat.py if importable in this venv (it is stdlib + numpy for these classes)."""
    p = str(_repo.REPO / "forecast")
    added = p not in sys.path
    if added:
        sys.path.insert(0, p)
    try:
        from wildfire import heat as fh  # noqa: WPS433
        from wildfire import heat_parameters as hp
        return fh, hp
    except Exception:  # noqa: BLE001
        return None, None
    finally:
        if added:
            sys.path.remove(p)


def test_table_and_residence_match_forecast_heat_py():
    fh, hp = _forecast_heat()
    if fh is None:
        pytest.skip("forecast/wildfire/heat.py not importable here; listed values tested above")
    import numpy as np
    assert dict(fuels.FBFM40_PARAMETERS) == dict(fh._FBFM40_PARAMETERS)
    for code, (name, _, _) in fuels.FBFM40_PARAMETERS.items():
        ref = float(fh.FlameResidenceTime.from_fbfm40(np.array([[code]])).duration_s[0, 0])
        assert fuels.get_fuel(name).residence_s == pytest.approx(ref, rel=1e-12)
        ref_h = float(hp.heat_content_from_fbfm40(np.array([[code]]))[0, 0]) / 1000.0
        assert fuels.get_fuel(code).heat_kj_kg == pytest.approx(ref_h, rel=1e-12)


def test_consumed_load_and_heat_content():
    gr2 = fuels.get_fuel("GR2")
    assert gr2.consumed_load_kg_m2 == pytest.approx((0.10 + 0.5 * 1.00) * 0.224170231, rel=1e-6)
    sh6 = fuels.get_fuel("SH6")        # no live herb: 1-h dead only
    assert sh6.consumed_load_kg_m2 == pytest.approx(2.90 * 0.224170231, rel=1e-6)
    assert fuels.get_fuel("GR6").heat_kj_kg == pytest.approx(20934.0)
    assert fuels.get_fuel("GR1").heat_kj_kg == pytest.approx(18608.0)
    assert gr2.energy_kj_m2 == pytest.approx(gr2.heat_kj_kg * gr2.consumed_load_kg_m2)


def test_c064_and_default():
    c = fuels.get_fuel("C064_GRASS")
    assert c.residence_s == pytest.approx(384 * 60 / 0.3048 / 9770.0)
    assert round(c.residence_s, 2) == 7.74
    assert (c.consumed_load_kg_m2, c.heat_kj_kg) == (0.28, 17425.0)
    d = fuels.DEFAULT
    assert (d.residence_s, d.consumed_load_kg_m2, d.heat_kj_kg) == (11.52, 1.0, 18608.0)
    assert len(fuels.FUELS) == 40 + 2


def test_lookup_and_custom():
    assert fuels.get_fuel(101) is fuels.get_fuel("GR1") is fuels.get_fuel("101")
    with pytest.raises(KeyError):
        fuels.get_fuel("XX9")
    f = fuels.custom_fuel("ROADSIDE_TEST", residence_s=9.0, consumed_load_kg_m2=0.3)
    assert fuels.get_fuel("ROADSIDE_TEST") is f
    with pytest.raises(ValueError):
        fuels.custom_fuel("GR1", 9.0, 0.3)
    with pytest.raises(ValueError):
        fuels.Fuel("X", "x", float("nan"), 0.3, 1.0, 18000.0)


# -------------------------------------------------------------------------------------------------- heat
def test_in_flame_is_contact_convention():
    for depth, i in ((1.0, 500.0), (4.0, 3000.0)):
        assert heat.in_flame_flux(depth, i) == pytest.approx(0.30 * i / (math.pi * depth), rel=1e-12)


def test_line_flux_calls_law_with_s_equal_d_plus_half_depth():
    law = _repo.kcf_law()
    q = heat.closed_form_line_flux(7.0, 3.0, 2000.0, chi=0.3, half_width_m=20.0)
    assert q == pytest.approx(law.line_flux_s(8.5, 0.3, 2000.0, 20.0), rel=1e-12)
    assert q < heat.closed_form_line_flux(7.0, 3.0, 2000.0)              # finite front lowers flux
    # equal to law.line_flux with R*t_r = depth
    R, tr = 0.25, 12.0
    e = 2000.0 / R
    assert heat.closed_form_line_flux(7.0, R * tr, 2000.0) == pytest.approx(law.line_flux(7.0, 0.3, e, R, tr))
    with pytest.raises(ValueError):
        heat.closed_form_line_flux(-1.0, 3.0, 2000.0)
    with pytest.raises(ValueError):
        heat.closed_form_line_flux(1.0, float("nan"), 2000.0)


def test_fds_reference_bins_and_scaling():
    data = json.loads(_repo.B2_FDS_COMPARE.read_text())
    i_ref = data["mean_intensity_kw_m"]
    for b in data["bins"]:
        c = 0.5 * (b["d_bin_m"][0] + b["d_bin_m"][1])
        r = heat.fds_reference(c, i_ref)
        assert r.q_kw_m2 == pytest.approx(b["fds_geomean"], rel=1e-9)
        assert r.label == "FDS C064 reference, not a measurement"
    assert heat.fds_reference(0.0, i_ref).q_kw_m2 == pytest.approx(78.239, rel=1e-9)
    assert heat.fds_reference(10.0, 2 * i_ref).q_kw_m2 == pytest.approx(2 * heat.fds_reference(10.0, i_ref).q_kw_m2)
    qs = [heat.fds_reference(d, i_ref).q_kw_m2 for d in range(0, 80, 2)]
    assert all(a > b for a, b in zip(qs, qs[1:]))
    assert heat.fds_reference(70.0, i_ref).extrapolated and not heat.fds_reference(40.0, i_ref).extrapolated


def test_in_flame_radiometer_maxima_match_devc_csv():
    if not _repo.C064_DEVC.exists():
        pytest.skip("C064 devc csv not present")
    with open(_repo.C064_DEVC, newline="") as fh:
        rows = list(csv.reader(fh))
    names = [n.strip() for n in rows[1]]
    vals = [[float(x) for x in r] for r in rows[2:] if r]
    for dev, mx in heat.FDS_IN_FLAME_MAX_KW_M2.items():
        k = names.index(dev)
        assert max(v[k] for v in vals) == pytest.approx(mx, abs=1e-3)
