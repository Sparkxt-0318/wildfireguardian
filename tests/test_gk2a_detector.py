"""The Session-19 GK2A detector had no tests. WFG-021 gives it five kinds.

`src/wildfireguardian/detection/gk2a.py` and `scripts/gk2a_detection.py` were
written in Session 19 and shipped three numbers the finals screen and the Q&A
bank quote (+22 / +34 / +64 minutes after the RECORDED REPORT TIME). SESSION19
item 11 records the gap in one sentence: "새 코드에 테스트가 하나도 없습니다".

What is pinned here, and why each one:

1. **The radiance unit round-trips.** The module's own docstring says the unit
   was settled empirically, not read from the file, and that a wrong choice
   moves every temperature by tens of kelvin. A round trip through the forward
   Planck function in the unit the module claims (mW·m⁻²·sr⁻¹·(cm⁻¹)⁻¹) is the
   cheapest thing that fails if anyone "simplifies" the ×1e-3/100 factor.
2. **The bit mask is per channel and the guard fires when it is wrong.** The
   module says masking sw038 (14 bits) to 13 produced a whole-scene 376 K that
   the pixel-range check did not catch, and that the scene-MEDIAN check is what
   catches it. That is a claim about the code, so it is testable on synthetic
   arrays: build a scene whose 14-bit DN needs the top bit, and assert that
   reading it 13-bit raises.
3. **The K = 4 contextual rule is a conjunction, and the floor is load-bearing.**
   A high 3.8 μm pixel with a small MIR-TIR difference is not a detection; a
   background with a vanishing spread does not become a detection factory.
4. **A regression pin on the committed artifact**, tied to the registry keys, so
   the three delays and the 0/709 false-alarm control cannot drift under the
   prose that cites them.
5. **A real granule**, opt-in, read from the public archive. See below.

⚠ WHAT MOST OF THIS FILE DOES NOT DO. Groups 1-3 validate no arithmetic against
outside truth: every array is synthetic and every calibration constant was
chosen by this test, not read from a granule. They confirm internal consistency
and that the module's stated guards fire. That is not nothing, but it is not
evidence that the reader handles a REAL granule.

**An earlier draft of this file said the real granule was out of reach from the
sandbox. That was false, and it was never checked** — the independent reviewer
of 2026-09-03 fetched
`AMI/L1B/LA/202503/22/02/gk2a_ami_le1b_sw038_la020ge_202503220224.nc`
anonymously from `noaa-gk2a-pds` in about three seconds, and this lap reproduced
it (458,172 bytes, HTTP 200). The unreachability claim was the excuse for every
synthetic fixture below, so it is corrected here rather than quietly deleted.
Group 5 is the test it was standing in the way of: it reads that granule and
checks the things the synthetic fixtures can only assume.

Group 5 is **opt-in** (`WFG_GK2A_NETWORK_TESTS=1`), for the reason WFG-039
exists: a suite that downloads half a megabyte mid-run has a different pass/skip
count on a warm machine than on a cold one, and this project's gates read those
counts. Reachable is not the same as belonging in the default run.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.detection.gk2a import (  # noqa: E402
    BT_MEDIAN_SANITY_K,
    BT_SANITY_K,
    DEFAULT_VALID_BITS,
    MIR_CHANNEL,
    TIR_CHANNEL,
    brightness_temperature,
    s3_key,
)

ARTIFACT = REPO / "data" / "processed" / "detection" / "gk2a_detection_floor.json"
REGISTRY = REPO / "docs" / "NUMBERS.json"


def _detection_module():
    """`scripts/gk2a_detection.py` is a script, not a package module."""
    spec = importlib.util.spec_from_file_location(
        "_gk2a_detection", REPO / "scripts" / "gk2a_detection.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# 1. units and the DN -> BT path
# --------------------------------------------------------------------------

#: A synthetic granule's global attributes. The physical constants are the
#: CODATA values the file itself carries; the gain, offset and corner scan
#: angles are CHOSEN BY THIS TEST so the arithmetic is checkable by hand. They
#: are not GK2A's real calibration and must never be quoted as such.
def _attrs(wavelength_um: float, gain: float, offset: float) -> dict:
    return {
        "DN_to_Radiance_Gain": gain,
        "DN_to_Radiance_Offset": offset,
        "channel_center_wavelength": wavelength_um,
        "Plank_constant_h": 6.62606957e-34,          # sic: the file's spelling
        "light_speed": 299792458.0,
        "Boltzmann_constant_k": 1.3806488e-23,
        # identity Teff -> Tbb, so this test measures the Planck path alone
        "Teff_to_Tbb_c0": 0.0,
        "Teff_to_Tbb_c1": 1.0,
        "Teff_to_Tbb_c2": 0.0,
    }


def _radiance_for(bt_k: float, wavelength_um: float) -> float:
    """Forward Planck, returned in the unit the module says it reads.

    Written from the inverse in the module, in the opposite direction, so a
    sign or factor error in either one fails the round trip.
    """
    h, c, k = 6.62606957e-34, 299792458.0, 1.3806488e-23
    nu = 1.0 / (wavelength_um * 1e-6)                      # m^-1
    spectral = 2 * h * c**2 * nu**3 / (math.exp(h * c * nu / (k * bt_k)) - 1.0)
    return spectral * 100.0 * 1e3          # W..(m^-1)^-1 -> mW..(cm^-1)^-1


#: DN that the fixture's calibration maps to exactly 290 K.
ANCHOR_DN, ANCHOR_K, ZERO_DN_K = 12000, 290.0, 390.0


def _calibration(wavelength_um: float) -> tuple[float, float]:
    """A DECREASING gain, as the module's own bug report implies GK2A's is.

    The module records that a 13-bit read of the 14-bit sw038 channel produced
    a 376 K scene -- hotter, not colder, than the truth. Dropping the top bit
    lowers the count, so a count that maps to a HIGHER radiance is the only way
    that observation can arise: the gain is negative and the offset positive.
    The two numbers here are solved from that shape (DN 0 -> 390 K,
    DN 12000 -> 290 K) and are the test's own, not GK2A's calibration.
    """
    offset = _radiance_for(ZERO_DN_K, wavelength_um)
    gain = (_radiance_for(ANCHOR_K, wavelength_um) - offset) / ANCHOR_DN
    assert gain < 0.0
    return gain, offset


def _dn_for(bt_k: float, wavelength_um: float) -> int:
    gain, offset = _calibration(wavelength_um)
    return int(round((_radiance_for(bt_k, wavelength_um) - offset) / gain))


def _bt_from_dn(dn: int, wavelength_um: float,
                cal: tuple[float, float] | None = None) -> float:
    """The same inverse the module computes, WITHOUT its sanity guards.

    The guards are the thing under test, so the test cannot ask the module what
    a scene's temperature would have been if the guard had not fired.
    """
    h, c, k = 6.62606957e-34, 299792458.0, 1.3806488e-23
    gain, offset = cal if cal is not None else _calibration(wavelength_um)
    nu = 1.0 / (wavelength_um * 1e-6)
    spectral = (gain * dn + offset) * 1e-3 / 100.0
    return h * c * nu / k / math.log(2 * h * c**2 * nu**3 / spectral + 1.0)


@pytest.mark.parametrize("bt_k", [200.0, 240.0, 273.15, 290.0, 300.0, 320.0])
@pytest.mark.parametrize("wavelength_um", [3.83, 11.2])
def test_the_radiance_unit_round_trips_through_the_module(bt_k, wavelength_um):
    """Forward Planck -> DN -> brightness_temperature returns the same kelvin.

    Tolerance is 0.75 K, not machine epsilon, because DN is an integer count:
    at 200 K on the 3.8 um channel one count is worth about half a kelvin. A
    wrong unit conversion is worth tens to hundreds, so the tolerance is not
    close to hiding one.
    """
    gain, offset = _calibration(wavelength_um)
    dn = np.full((8, 8), _dn_for(bt_k, wavelength_um), dtype="uint16")

    out = brightness_temperature(dn, _attrs(wavelength_um, gain, offset),
                                 valid_bits=16)

    assert np.isfinite(out).all()
    assert float(np.abs(out - bt_k).max()) < 0.75, (
        "the DN -> radiance -> Planck path no longer returns the temperature "
        "it was given; the mW/(cm^-1) unit conversion is the usual cause")


def test_a_scene_the_module_would_have_to_call_impossible_is_refused():
    """The 150-400 K pixel guard is not decorative.

    Its own calibration, increasing this time, because the fixture above cannot
    express a temperature above its DN-zero anchor.
    """
    lam = 3.83
    r_lo, r_hi = _radiance_for(300.0, lam), _radiance_for(500.0, lam)
    gain = (r_hi - r_lo) / 20000.0
    offset = r_lo - gain * 10000.0
    assert gain > 0.0
    assert abs(_bt_from_dn(30000, lam, (gain, offset)) - 500.0) < 0.5

    dn = np.full((8, 8), 30000, dtype="uint16")
    with pytest.raises(ValueError, match="outside"):
        brightness_temperature(dn, _attrs(lam, gain, offset), valid_bits=16)


def test_the_wrong_bit_mask_is_caught_by_the_scene_median_not_the_pixel_range():
    """sw038 carries 14 valid bits; reading it as 13 must fail loudly.

    The module's docstring records that a 13-bit read of sw038 produced a
    376 K scene and that the pixel-range check did NOT catch it, because 376 K
    is inside 150-400. This fixture reproduces that shape: the truncated scene
    lands at about 376 K, and only the scene-median check has anything to say.
    """
    lam = 3.83
    gain, offset = _calibration(lam)
    attrs = _attrs(lam, gain, offset)
    dn_true = ANCHOR_DN
    assert dn_true > (1 << 13), (
        "fixture no longer needs the 14th bit, so it cannot exercise the mask")

    dn = np.full((64, 64), dn_true, dtype="uint16")
    ok = brightness_temperature(dn, attrs, valid_bits=14)
    assert abs(float(np.median(ok)) - ANCHOR_K) < 0.05

    truncated = dn_true & ((1 << 13) - 1)
    got = _bt_from_dn(truncated, lam)
    assert BT_SANITY_K[0] < got < BT_SANITY_K[1], (
        "this fixture is only interesting while the truncated scene stays "
        "INSIDE the pixel window; otherwise the pixel guard catches it and "
        "this test pins the wrong guard")
    assert got > BT_MEDIAN_SANITY_K[1]

    with pytest.raises(ValueError, match="SCENE MEDIAN"):
        brightness_temperature(dn, attrs, valid_bits=13)


def test_a_mask_error_small_enough_to_pass_both_guards_exists():
    """The honest limit of the two guards, pinned so nobody oversells them.

    Neither guard is a checksum. On the 3.8 um channel the DN -> BT map is
    steeply logarithmic, so a truncation that lands the scene at, say, 300 K
    passes the pixel window AND the median window while every temperature in it
    is wrong. What protects the numbers is `read_granule` taking the bit count
    from the granule (`number_of_valid_bits_per_pixel`), not the guards.
    """
    lam = 3.83
    # An INCREASING gain this time. Which way a dropped top bit moves the
    # temperature is the sign of the gain, and only the decreasing case (the
    # one the test above reproduces) is guaranteed to overshoot 330 K.
    gain = _radiance_for(ANCHOR_K, lam) / ANCHOR_DN
    attrs = _attrs(lam, gain, 0.0)
    dn = np.full((16, 16), ANCHOR_DN, dtype="uint16")

    right = brightness_temperature(dn, attrs, valid_bits=14)
    wrong = brightness_temperature(dn, attrs, valid_bits=13)   # no raise

    assert abs(float(np.median(right)) - ANCHOR_K) < 0.05
    med = float(np.median(wrong))
    assert BT_MEDIAN_SANITY_K[0] <= med <= BT_MEDIAN_SANITY_K[1], (
        "if this ever stops holding, the guards became stronger and this "
        "test's claim about their limit needs rewriting, not deleting")
    assert abs(med - ANCHOR_K) > 10.0, (
        "the truncation must actually change the temperature, or the test "
        "is demonstrating nothing")


def test_the_s3_key_names_the_two_minute_granule_the_detector_asks_for():
    import datetime as dt
    key = s3_key(MIR_CHANNEL, dt.datetime(2025, 3, 22, 2, 24))
    assert key == ("AMI/L1B/LA/202503/22/02/"
                   "gk2a_ami_le1b_sw038_la020ge_202503220224.nc")
    assert MIR_CHANNEL == "sw038" and TIR_CHANNEL == "ir112"


# --------------------------------------------------------------------------
# 2. geometry: the 15 km disc and the 30-80 km annulus
# --------------------------------------------------------------------------

def test_the_target_disc_and_background_annulus_are_the_documented_geometry():
    m = _detection_module()
    assert m.TARGET_RADIUS_KM == 15.0
    assert (m.BG_INNER_KM, m.BG_OUTER_KM) == (30.0, 80.0)

    lat0, lon0 = 36.5, 128.7
    # one degree of latitude is the module's own 111 km, so distances along a
    # meridian are exact under its approximation.
    offsets_km = [0.0, 14.0, 16.0, 29.0, 31.0, 79.0, 81.0]
    lats = np.array([[lat0 + d / 111.0 for d in offsets_km]])
    lons = np.full_like(lats, lon0)

    target, bg, km = m._masks(lats, lons, lat0, lon0)
    assert np.allclose(km[0], offsets_km, atol=1e-6)

    assert list(target[0]) == [True, True, False, False, False, False, False]
    assert list(bg[0]) == [False, False, False, False, True, True, False]


def test_no_pixel_is_both_target_and_background_and_the_gap_is_deliberate():
    """15-30 km belongs to neither, which is what keeps the two independent."""
    m = _detection_module()
    lat0, lon0 = 36.5, 128.7
    d = np.linspace(0.0, 100.0, 401)
    lats = np.array([lat0 + x / 111.0 for x in d]).reshape(1, -1)
    lons = np.full_like(lats, lon0)

    target, bg, km = m._masks(lats, lons, lat0, lon0)
    assert not (target & bg).any(), "the fire would be inside its own background"
    gap = (km > m.TARGET_RADIUS_KM) & (km < m.BG_INNER_KM)
    assert gap.any() and not target[gap].any() and not bg[gap].any()


# --------------------------------------------------------------------------
# 3. the K = 4 contextual rule
# --------------------------------------------------------------------------

def test_k_is_four_and_the_absolute_floor_is_three_kelvin():
    m = _detection_module()
    assert m.K_SIGMA == 4.0, (
        "K was fixed at 4 before any fire was examined and is not a tuned "
        "parameter; changing it re-opens every delay this project reports")
    assert m.DELTA_FLOOR_K == 3.0


def test_a_hot_pixel_without_the_mir_tir_contrast_is_not_a_detection():
    """Both channel conditions must clear; warm bare ground is not a fire."""
    m = _detection_module()
    target = np.array([[True, True]])
    mir = np.array([[400.0, 400.0]])       # both very hot at 3.8 um
    delta = np.array([[40.0, 1.0]])        # only the first has the contrast

    flagged = m.contextual_flag(mir, delta, target,
                                m_mu=290.0, m_sd=1.0, d_mu=2.0, d_sd=0.5)
    assert list(flagged[0]) == [True, False]


def test_a_pixel_outside_the_target_disc_is_never_flagged():
    m = _detection_module()
    target = np.array([[True, False]])
    mir = np.array([[400.0, 400.0]])
    delta = np.array([[40.0, 40.0]])
    flagged = m.contextual_flag(mir, delta, target,
                                m_mu=290.0, m_sd=1.0, d_mu=2.0, d_sd=0.5)
    assert list(flagged[0]) == [True, False]


def test_a_quiet_background_cannot_manufacture_a_detection():
    """With sd -> 0 the sigma test is trivially cleared; the floor is what holds.

    This is the half of the rule that a reviewer should look at hardest: the
    contextual threshold is relative, so a scene with no spread would flag a
    pixel 0.01 K above the median if nothing else stopped it.
    """
    m = _detection_module()
    target = np.array([[True]])
    mir = np.array([[290.02]])
    delta = np.array([[2.0]])              # below DELTA_FLOOR_K = 3.0
    flagged = m.contextual_flag(mir, delta, target,
                                m_mu=290.0, m_sd=0.0, d_mu=0.0, d_sd=0.0)
    assert not flagged.any()

    # and the same pixel WITH the contrast does clear, so the floor is the
    # only thing that refused it above.
    assert m.contextual_flag(mir, np.array([[3.5]]), target,
                             m_mu=290.0, m_sd=0.0, d_mu=0.0, d_sd=0.0).all()


def _yeongdeok_ring(diag: dict) -> tuple[float, float]:
    s = diag["strongest_anomaly"]
    return float(s["bg_delta_median_k"]), float(s["bg_delta_mad_sd_k"])


def test_a_contaminated_background_reproduces_the_recorded_yeongdeok_threshold():
    """Why 영덕 is 교란 (disturbed) and not counted either way.

    `docs/detection_floor.md` §4 is careful about this and so is the registry:
    영덕 is classified 교란 and counted NEITHER as a detection NOR as a fire the
    satellite missed, and whether the fire, the coordinates or the timestamp is
    at fault was NOT separated. What IS measured is the arithmetic: the best
    step's anomaly was 11.611 K against a contextual threshold of 21.964 K, on a
    background ring whose median was 8.328 K with a MAD-sd of 3.409 K, where a
    clean Korean night scene reads 1.13 / 0.49.

    Every number below is the committed artifact's, read from it here rather
    than typed, so the rule must reproduce the recorded threshold to the third
    decimal. That is the part an outside fact decides; the rest of this file
    only asks the code to agree with itself.
    """
    m = _detection_module()
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))["per_fire"]["yeongdeok_2025"]
    diag = json.loads((REPO / "data" / "processed" / "detection" /
                       "yeongdeok_background_contamination.json").read_text())
    best = float(art["best_target_delta_k"])
    recorded_threshold = float(art["threshold_at_best_k"])

    bg_med, bg_sd = _yeongdeok_ring(diag)
    assert bg_med + m.K_SIGMA * bg_sd == pytest.approx(recorded_threshold, abs=5e-3), (
        "the K = 4 rule no longer reproduces the threshold the artifact "
        "recorded for 영덕's best step; one of the two moved")

    target = np.array([[True]])
    mir, delta = np.array([[330.0]]), np.array([[best]])
    contaminated = m.contextual_flag(mir, delta, target,
                                     m_mu=290.0, m_sd=1.0,
                                     d_mu=bg_med, d_sd=bg_sd)
    clean = m.contextual_flag(mir, delta, target,
                              m_mu=290.0, m_sd=1.0, d_mu=1.13, d_sd=0.49)
    assert not contaminated.any() and clean.all(), (
        "a contaminated ring must RAISE the bar; if this ever inverts, 영덕's "
        "classification rests on nothing")


# --------------------------------------------------------------------------
# 4. regression pin on the committed artifact and the registry
# --------------------------------------------------------------------------

#: (registry key, path into the artifact). The artifact is the source of truth;
#: the registry is what prose is allowed to cite. Both must agree.
PINNED = [
    ("det_gk2a_delay_uiseong_andong_min", ("per_fire", "uiseong_andong_2025", "delay_min"), 22),
    ("det_gk2a_delay_gangneung_2023_min", ("per_fire", "gangneung_2023", "delay_min"), 34),
    ("det_gk2a_delay_hongseong_2023_min", ("per_fire", "hongseong_2023", "delay_min"), 64),
    ("det_gk2a_yeongdeok_best_delta_k", ("per_fire", "yeongdeok_2025", "best_target_delta_k"), 11.611),
    ("det_control_steps", ("false_alarms", "n_steps"), 709),
    ("det_false_alarm_steps", ("false_alarms", "n_steps_with_a_flagged_pixel"), 0),
]


@pytest.mark.parametrize("key,path,expected", PINNED, ids=[p[0] for p in PINNED])
def test_the_artifact_and_the_registry_agree_on_every_cited_number(key, path, expected):
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    node = art
    for step in path:
        node = node[step]
    assert node == pytest.approx(expected), (
        f"{'.'.join(path)} moved in the artifact; the delays are quoted in "
        "docs/detection_floor.md, JUDGE_QA and the finals screen")

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))["numbers"][key]
    assert reg["value"] == pytest.approx(float(expected))
    assert reg["source_file"] == "data/processed/detection/gk2a_detection_floor.json"


def test_the_detector_settings_in_the_artifact_are_the_settings_in_the_code():
    """A rerun with different constants must not be able to reuse this file."""
    m = _detection_module()
    det = json.loads(ARTIFACT.read_text(encoding="utf-8"))["detector"]
    assert det["k_sigma"] == m.K_SIGMA
    assert det["delta_floor_k"] == m.DELTA_FLOOR_K
    assert det["target_radius_km"] == m.TARGET_RADIUS_KM
    assert det["background_annulus_km"] == [m.BG_INNER_KM, m.BG_OUTER_KM]
    assert det["cadence_min"] == m.STEP_MIN


def test_yeongdeok_carries_no_delay_and_is_counted_in_neither_direction():
    """Three fires with a delay, not six. And 영덕 is 교란, not a miss.

    `docs/detection_floor.md` §4 refuses both readings of 영덕 in bold: it is
    「교란」, 「탐지로도 세지 않고, 위성이 못 본 사례로도 세지 않습니다」. The
    artifact's `detected: false` is therefore the absence of a delay, NOT a
    finding that the satellite failed to see the fire, and no prose may promote
    it to one.
    """
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    y = art["per_fire"]["yeongdeok_2025"]
    assert y["detected"] is False
    assert y.get("delay_min") is None
    assert "no pixel cleared the contextual threshold" in y["note"]

    doc = (REPO / "docs" / "detection_floor.md").read_text(encoding="utf-8")
    assert "탐지로도 세지 않고, 위성이 못 본 사례로도 세지 않습니다" in doc, (
        "the sentence that refuses both readings of 영덕 left the document")
    detected = [k for k, v in art["per_fire"].items() if v.get("detected")]
    assert sorted(detected) == ["gangneung_2023", "hongseong_2023",
                                "uiseong_andong_2025"]


def test_the_control_is_the_same_extent_and_clock_two_weeks_earlier():
    """A false-alarm rate is only worth quoting if the control held things fixed."""
    m = _detection_module()
    fa = json.loads(ARTIFACT.read_text(encoding="utf-8"))["false_alarms"]
    assert fa["n_sites"] == 4
    assert sum(s["n_steps"] for s in fa["per_site"].values()) == fa["n_steps"]
    assert all(s["n_steps_flagged"] == 0 for s in fa["per_site"].values())
    assert fa["false_alarm_rate_per_step"] == 0.0
    assert m.CONTROL_DAYS_BEFORE == 14


# --------------------------------------------------------------------------
# 5. the real granule (opt-in)
# --------------------------------------------------------------------------

#: One granule the archive is known to hold: the 02:24 UTC sw038 scene on the
#: day of the 영덕 fire's report, which is the key `s3_key` is tested against
#: above. Anonymous, no credentials, about 0.45 MB.
REAL_GRANULE_URL = (
    "https://noaa-gk2a-pds.s3.amazonaws.com/AMI/L1B/LA/202503/22/02/"
    "gk2a_ami_le1b_sw038_la020ge_202503220224.nc")

network = pytest.mark.skipif(
    os.environ.get("WFG_GK2A_NETWORK_TESTS") != "1",
    reason="opt-in: downloads ~0.45 MB from noaa-gk2a-pds. The archive IS "
           "reachable from a clean sandbox (verified 2026-09-03); this is "
           "gated so the default suite has one pass/skip count on a cold "
           "machine and a warm one (WFG-039). Set WFG_GK2A_NETWORK_TESTS=1.")


@network
def test_the_reader_decodes_a_real_granule_and_takes_its_bit_count_from_it(tmp_path):
    """The one test the synthetic fixtures above cannot substitute for.

    Everything before this asks the code to agree with itself. This asks the
    archive. It is the reason the earlier "unreachable" claim mattered: it was
    standing between this project and the only external check it can make of a
    reader whose calibration constants all come out of the file.
    """
    import urllib.request

    import xarray as xr

    from wildfireguardian.detection.gk2a import read_granule

    path = tmp_path / "granule.nc"
    with urllib.request.urlopen(REAL_GRANULE_URL, timeout=120) as r:
        path.write_bytes(r.read())

    with xr.open_dataset(path, engine="h5netcdf") as ds:
        var = ds["image_pixel_values"]
        bits = int(var.attrs["number_of_valid_bits_per_pixel"])
        gain = float(ds.attrs["DN_to_Radiance_Gain"])

    # This is the whole argument of the module's DEFAULT_VALID_BITS comment:
    # sw038 is 14, the default is 13, so a reader that trusts the default is
    # wrong on this channel. `read_granule` reads it from the file.
    assert bits == 14 and bits != DEFAULT_VALID_BITS

    # And the decreasing gain the synthetic fixture had to argue for from a
    # docstring is simply what the instrument ships.
    assert gain < 0.0

    g = read_granule(path)
    assert g.channel == MIR_CHANNEL
    assert 3.7 <= g.wavelength_um <= 3.9
    med = float(np.median(g.bt))
    assert BT_MEDIAN_SANITY_K[0] < med < BT_MEDIAN_SANITY_K[1], (
        "a real Korean scene must land inside the window the module defends; "
        "if it does not, the module's empirical radiance unit is wrong")
    assert BT_SANITY_K[0] < float(g.bt.min())
    assert float(g.bt.max()) < BT_SANITY_K[1]
