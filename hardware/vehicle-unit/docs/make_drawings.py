"""Generate docs/wiring.svg and docs/housing.svg, and the computed checks block in docs/HOUSING.md.

Stdlib only, Python 3.11+. Run from anywhere:

    python hardware/vehicle-unit/docs/make_drawings.py          # rewrite both SVGs and the HOUSING.md checks block
    python hardware/vehicle-unit/docs/make_drawings.py --check  # exit 1 if any committed output differs

Status 2026-11-17: nothing here has been wired, printed, fitted or measured by this project.

- ``PIN_MAP`` is the ONE pin list. It is the pin map from the user's printed build manual (2026-11-17).
  ``wiring.svg``, the WIRING.md pin table (checked by ``test_docs.py``) and ``config/unit.yaml`` follow it.
- ``SUPPLIED`` and ``SENSOR_OFFSETS_MM`` are the housing dimensions AS GIVEN BY THE USER. The housing exists and is
  being printed; this project does not design it. ``housing.svg`` is a front-plate layout drawing of those numbers
  only: documentation of the supplied housing, not a design. ``config/unit.yaml`` (``housing:`` and
  ``mount.sensor_offsets_mm``) carries the same numbers; ``test_docs.py`` checks they agree.
- The x offsets are recorded exactly as the build manual gives them. Their sign convention (+ to the right seen from
  the front) is UNCONFIRMED; the drawing says so, and no check below depends on the sign.
- ``checks()`` holds the arithmetic for HOUSING.md section "Checks on the supplied housing". Every number it gives
  is a CALCULATION from stated assumptions (``ASSUMED``), not a measurement.
"""
from __future__ import annotations

import cmath
import math
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
C0 = 299_792_458.0  # speed of light, m/s
SIGMA = 5.670374419e-8


def radome_thickness_mm(eps_r: float, f_hz: float = 60e9, n: int = 1) -> float:
    """Half-wave-multiple slab thickness in mm: n * lambda0 / (2 * sqrt(eps_r)), normal incidence."""
    lam_mm = C0 / f_hz * 1000.0
    return n * lam_mm / (2.0 * math.sqrt(eps_r))


# --------------------------------------------------------------------------------------------------------------
# The supplied housing: numbers AS GIVEN BY THE USER (2026-11-17). Not a design. Mirrored in config/unit.yaml.
# --------------------------------------------------------------------------------------------------------------
SUPPLIED = {
    "body_mm": (180, 140, 72),            # read as width x depth x height (the 172 x 66 plate fits the 180 x 72 face)
    "wall_mm": 4,
    "pi_standoff_pattern_mm": (58, 49),   # four standoffs; their position in the body is not given
    "floor_rails": 3,
    "rail_pilot_hole": "M3",
    "rail_hole_pitch_mm": 10,
    "front_plate_mm": (172, 66, 3),       # bolt-on
    "sensor_centre_line_above_base_mm": 34,
    "heat_shield": {"material": "aluminium", "gap_mm": 10},   # 10 mm in front of the front plate
    "material": "PETG",                   # printed; material as told by the user
}
# x as in the build manual; sign convention (+ to the right seen from the front) UNCONFIRMED. z above the base.
SENSOR_OFFSETS_MM = {
    "camera": {"x": -52, "z": 34, "hole_d": 12},
    "radar": {"x": -8, "z": 34, "window_w": 52, "window_h": 42, "window_t": 1.2},
    "flux_disc": {"x": 45, "z": 34, "hole_d": 30.6},
}

# --------------------------------------------------------------------------------------------------------------
# Assumptions for the checks (NOT given by the user; each is stated in HOUSING.md and must be verified)
# --------------------------------------------------------------------------------------------------------------
ASSUMED = {
    "cam_hfov_deg": 56.0,     # InfiRay P2 Pro, vendor figure as we read it (verify); same as the laptop CameraModel
    "cam_vfov_deg": 42.0,
    "cam_pupil_d_mm": 3.0,    # entrance pupil ~ f / N = 3.2 mm / 1.1 (vendor-typical; UNVERIFIED)
    "cam_pitch_deg": -18.0,   # config/unit.yaml mount.camera_pitch_deg (placeholder); 0 = square to the plate
    "radar_half_deg": 60.0,   # IWR6843AOP antenna-on-package, about +-60 deg azimuth and elevation
    "radar_decision_half_deg": 30.0,   # laptop beam grid -30..30 deg (DESIGN.md 6.3)
    "radar_ant_mm": 10.0,     # radiating region of the AOP package, assumed (the package is 15 x 15 mm)
    "disc_d_mm": 30.0,        # copper disc diameter (not given; the hole is 30.6 mm)
    "disc_t_mm": 1.0,         # copper disc thickness (not given; crossing PlateSpec default 1 mm)
    "disc_absorptivity": 0.95,
    "rho_c_copper": 8960.0 * 385.0,    # J/(m3 K)
    "petg_eps_r": (2.6, 3.0),          # at 60 GHz, assumed, unverified
    "petg_tan_d": 0.01,                # assumed, unverified
    "petg_k": 0.2,                     # W/(m K), vendor-typical
    "petg_tg_c": 80.0,                 # glass transition, vendor-typical (about 75-85 C)
    "radar_f_ghz": (60.00, 60.55),     # config/iwr6843aop_vu.cfg chirp sweep
    "h_in": 6.0,                       # W/(m2 K) inside, natural convection + radiation, assumed
    "h_out": (10.0, 30.0),             # W/(m2 K) outside: parked / driving, assumed
    "unit_power_w": (7.0, 9.0, 17.0),  # MOUNTING_AND_POWER.md: Pi 4 typical, Pi 5 typical, Pi 5 worst (estimates)
}


# --------------------------------------------------------------------------------------------------------------
# Check arithmetic (calculations, not measurements)
# --------------------------------------------------------------------------------------------------------------
def camera_boundary_slopes(hfov_deg: float, vfov_deg: float, pitch_deg: float, n: int = 41) -> list:
    """(dx/dz, dy/dz) of pinhole rays on the image boundary in the front-plate frame (z out of the plate, y up),
    for a camera pitched by pitch_deg (+ up) about the horizontal axis. Symmetric in x, so a sign flip of the
    x offsets changes nothing."""
    th, tv = math.tan(math.radians(hfov_deg / 2)), math.tan(math.radians(vfov_deg / 2))
    p = math.radians(pitch_deg)
    out = []
    for i in range(n):
        u = -1.0 + 2.0 * i / (n - 1)
        for x, y in ((u * th, tv), (u * th, -tv), (th, u * tv), (-th, u * tv)):
            y2 = y * math.cos(p) + math.sin(p)
            z2 = -y * math.sin(p) + math.cos(p)
            out.append((x / z2, y2 / z2))
    return out


def camera_hole_max_setback_mm(hole_d: float, pupil_d: float, pitch_deg: float) -> float:
    """Largest distance from the entrance pupil back to the plate's FRONT face before the hole edge clips any image
    ray (no vignetting at the corners): (hole_d - pupil_d) / 2 / max radial slope."""
    s = camera_boundary_slopes(ASSUMED["cam_hfov_deg"], ASSUMED["cam_vfov_deg"], pitch_deg)
    m = max(math.hypot(a, b) for a, b in s)
    return (hole_d - pupil_d) / 2.0 / m


def camera_aperture_mm(dist_mm: float, pupil_d: float, pitch_deg: float) -> tuple:
    """Minimum rectangular opening (width, height, centre offset below the lens axis) at dist_mm in front of the
    entrance pupil that clears the whole field of view."""
    s = camera_boundary_slopes(ASSUMED["cam_hfov_deg"], ASSUMED["cam_vfov_deg"], pitch_deg)
    xs = [a for a, _ in s]
    ys = [b for _, b in s]
    w = pupil_d + dist_mm * (max(xs) - min(xs))
    up = pupil_d / 2 + dist_mm * max(ys)
    down = pupil_d / 2 - dist_mm * min(ys)
    return w, up + down, (down - up) / 2.0


def radar_aperture_mm(dist_mm: float, half_deg: float, ant_mm: float = ASSUMED["radar_ant_mm"]) -> float:
    """Opening that clears a +-half_deg cone from an antenna region of size ant_mm at dist_mm: a + 2 L tan."""
    return ant_mm + 2.0 * dist_mm * math.tan(math.radians(half_deg))


def radar_window_max_setback_mm(window_mm: float, half_deg: float, ant_mm: float = ASSUMED["radar_ant_mm"]) -> float:
    """Largest antenna distance behind the window's limiting edge before the +-half_deg cone is clipped."""
    return (window_mm - ant_mm) / 2.0 / math.tan(math.radians(half_deg))


def disc_view_factor(r1: float, r2: float, h: float) -> float:
    """View factor from a disc of radius r1 to a coaxial parallel disc (aperture) of radius r2 at distance h."""
    R1, R2 = r1 / h, r2 / h
    S = 1.0 + (1.0 + R2 * R2) / (R1 * R1)
    return 0.5 * (S - math.sqrt(S * S - 4.0 * (R2 / R1) ** 2))


def disc_aperture_for_view_factor(F: float, r1: float, h: float) -> float:
    """Aperture DIAMETER (mm) giving view factor F from the disc (bisection)."""
    lo, hi = 0.0, 10000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if disc_view_factor(r1, mid, h) < F:
            lo = mid
        else:
            hi = mid
    return 2.0 * hi


def slab_rt(eps_r: float, tan_d: float, d_mm: float, f_hz: float) -> tuple:
    """Normal-incidence power reflection and transmission of a lossy dielectric slab in air (|Gamma|^2, |T|^2)."""
    n = cmath.sqrt(complex(eps_r, -eps_r * tan_d))
    lam = C0 / f_hz * 1000.0
    delta = 2.0 * math.pi * n * d_mm / lam
    r = (1 - n) / (1 + n)
    e2 = cmath.exp(-2j * delta)
    den = 1 - r * r * e2
    gam = r * (1 - e2) / den
    t = (1 - r * r) * cmath.exp(-1j * delta) / den
    return abs(gam) ** 2, abs(t) ** 2


def db(x: float) -> float:
    return 10.0 * math.log10(x)


def window_rt_band(eps_r: float, d_mm: float) -> dict:
    """Worst case over the chirp band of one-way transmission, two-way loss and reflection (dB)."""
    rs, ts = [], []
    f0, f1 = ASSUMED["radar_f_ghz"]
    for i in range(12):
        f = (f0 + (f1 - f0) * i / 11) * 1e9
        R, T = slab_rt(eps_r, ASSUMED["petg_tan_d"], d_mm, f)
        rs.append(R)
        ts.append(T)
    return {"one_way_db": db(min(ts)), "two_way_db": 2 * db(min(ts)), "refl_db": db(max(rs)),
            "refl_db_min": db(min(rs))}


def body_area_m2() -> float:
    w, d, h = (v / 1000.0 for v in SUPPLIED["body_mm"])
    return 2.0 * (w * d + w * h + d * h)


def box_rise_k(power_w: float, h_out: float) -> float:
    """Steady inside-air rise over ambient for power_w dissipated inside the closed PETG box, no sun, no vents."""
    u = 1.0 / (1.0 / ASSUMED["h_in"] + SUPPLIED["wall_mm"] / 1000.0 / ASSUMED["petg_k"] + 1.0 / h_out)
    return power_w / (u * body_area_m2())


def disc_rate_k_s(q_kw_m2: float) -> float:
    """Copper disc heating rate (K/s) at incident flux q, losses ignored (upper bound on the rate)."""
    rcd = ASSUMED["rho_c_copper"] * ASSUMED["disc_t_mm"] / 1000.0
    return ASSUMED["disc_absorptivity"] * q_kw_m2 * 1000.0 / rcd


def checks() -> dict:
    """Every number quoted in HOUSING.md section 'Checks on the supplied housing'. Calculations only."""
    o = SENSOR_OFFSETS_MM
    gap = SUPPLIED["heat_shield"]["gap_mm"]
    pt = SUPPLIED["front_plate_mm"][2]
    pupil = ASSUMED["cam_pupil_d_mm"]
    c: dict = {}
    # camera
    th, tv = math.tan(math.radians(28)), math.tan(math.radians(21))
    c["cam_diag_half_deg"] = math.degrees(math.atan(math.hypot(th, tv)))
    for name, pitch in (("level", 0.0), ("pitched", ASSUMED["cam_pitch_deg"])):
        c["cam_setback_%s" % name] = camera_hole_max_setback_mm(o["camera"]["hole_d"], pupil, pitch)
        c["cam_setback_pinhole_%s" % name] = camera_hole_max_setback_mm(o["camera"]["hole_d"], 0.0, pitch)
        for s in (0.0, float(pt)):
            c["cam_shield_%s_s%d" % (name, s)] = camera_aperture_mm(s + gap, pupil, pitch)
    # radar
    for half, tag in ((ASSUMED["radar_half_deg"], "full"), (ASSUMED["radar_decision_half_deg"], "dec")):
        c["radar_win_setback_w_%s" % tag] = radar_window_max_setback_mm(o["radar"]["window_w"], half)
        c["radar_win_setback_h_%s" % tag] = radar_window_max_setback_mm(o["radar"]["window_h"], half)
        for s in (o["radar"]["window_t"], float(pt)):
            c["radar_shield_%s_s%s" % (tag, s)] = radar_aperture_mm(s + gap, half)
    # flux disc
    r1 = ASSUMED["disc_d_mm"] / 2.0
    c["disc_F_hole_recess3"] = disc_view_factor(r1, o["flux_disc"]["hole_d"] / 2.0, float(pt))
    for h in (float(gap), float(gap + pt)):
        for da in (o["flux_disc"]["hole_d"], 50.0, 80.0, 120.0):
            c["disc_F_h%d_a%s" % (h, da)] = disc_view_factor(r1, da / 2.0, h)
        for F in (0.5, 0.9, 0.95):
            c["disc_ap_h%d_F%s" % (h, F)] = disc_aperture_for_view_factor(F, r1, h)
    # radar window slab
    f_mid = 0.5 * sum(ASSUMED["radar_f_ghz"]) * 1e9
    for eps in ASSUMED["petg_eps_r"]:
        c["half_wave_eps%s" % eps] = radome_thickness_mm(eps, f_mid, 1)
        c["slab_1.2_eps%s" % eps] = window_rt_band(eps, o["radar"]["window_t"])
        c["slab_hw_eps%s" % eps] = window_rt_band(eps, radome_thickness_mm(eps, f_mid, 1))
        c["slab_3.0_eps%s" % eps] = window_rt_band(eps, float(pt))
    c["refl_max_quarter_wave"] = {eps: db((2 * abs((1 - math.sqrt(eps)) / (1 + math.sqrt(eps)))
                                         / (1 + ((1 - math.sqrt(eps)) / (1 + math.sqrt(eps))) ** 2)) ** 2)
                                  for eps in ASSUMED["petg_eps_r"]}
    # housing temperature
    c["body_area_m2"] = body_area_m2()
    for p in ASSUMED["unit_power_w"]:
        for ho in ASSUMED["h_out"]:
            c["rise_p%d_h%d" % (p, ho)] = box_rise_k(p, ho)
    c["sol_air_lid_k"] = {(a, ho): a * 1000.0 / ho for a in (0.3, 0.9) for ho in ASSUMED["h_out"]}
    # disc time to 70 C from 20 C, and margin to Tg after the stop
    for q in (5.0, 20.0, 50.0, 78.2):
        r = disc_rate_k_s(q)
        c["disc_rate_q%s" % q] = r
        c["disc_t70_q%s" % q] = 50.0 / r
        c["disc_t_tg_q%s" % q] = (ASSUMED["petg_tg_c"] - 70.0) / r
    rcd = ASSUMED["rho_c_copper"] * ASSUMED["disc_t_mm"] / 1000.0
    c["disc_tau_s"] = rcd / 20.0
    return c


def _f1(v: float) -> str:
    return "%.1f" % v


def _f2(v: float) -> str:
    return "%.2f" % v


def checks_markdown() -> str:
    """The generated block in HOUSING.md (between the checks markers). Calculations, not measurements."""
    c = checks()
    a = ASSUMED
    o = SENSOR_OFFSETS_MM
    gap = SUPPLIED["heat_shield"]["gap_mm"]
    L = []
    w = L.append
    w("Generated by `make_drawings.py` from `SUPPLIED`, `SENSOR_OFFSETS_MM` and `ASSUMED`. Every number is a")
    w("**calculation**, not a measurement. Pinhole optics, straight rays, normal incidence, handbook constants.")
    w("")
    w("**Camera (InfiRay P2 Pro, %g x %g deg FOV: verify).** Diagonal half-angle atan(sqrt(tan^2 28 + tan^2 21)) = "
      "**%s deg**." % (a["cam_hfov_deg"], a["cam_vfov_deg"], _f1(c["cam_diag_half_deg"])))
    w("Entrance pupil assumed %g mm (f / N ~ 3.2 mm / 1.1, unverified). Set-back s = distance from the pupil back to "
      "the plate's FRONT face." % a["cam_pupil_d_mm"])
    w("")
    w("| Camera case | Max set-back before the %g mm hole vignettes the corners | Same, pinhole limit | "
      "Shield opening (W x H) for s = 0 | for s = %d mm (pupil at the plate's back face) |"
      % (o["camera"]["hole_d"], SUPPLIED["front_plate_mm"][2]))
    w("|---|---|---|---|---|")
    for name, lab in (("level", "square to the plate (pitch 0)"),
                      ("pitched", "pitched %g deg (unit.yaml placeholder)" % a["cam_pitch_deg"])):
        s0 = c["cam_shield_%s_s0" % name]
        s3 = c["cam_shield_%s_s%d" % (name, SUPPLIED["front_plate_mm"][2])]
        off = lambda t: "" if abs(t[2]) < 0.05 else ", centre %s mm below the lens axis" % _f1(t[2])  # noqa: E731
        w("| %s | **%s mm** | %s mm | %s x %s mm%s | %s x %s mm%s |"
          % (lab, _f1(c["cam_setback_%s" % name]), _f1(c["cam_setback_pinhole_%s" % name]),
             _f1(s0[0]), _f1(s0[1]), off(s0), _f1(s3[0]), _f1(s3[1]), off(s3)))
    w("")
    w("**Radar (IWR6843AOP, about +-%g deg az/el).** Antenna region assumed %g mm square. Shield distance = s + %d mm."
      % (a["radar_half_deg"], a["radar_ant_mm"], gap))
    w("")
    w("| Radar cone | Max set-back behind the 52 mm (width) edge | behind the 42 mm (height) edge | "
      "Shield opening, antenna at s = %g mm | at s = %d mm |" % (o["radar"]["window_t"], SUPPLIED["front_plate_mm"][2]))
    w("|---|---|---|---|---|")
    for tag, half in (("full", a["radar_half_deg"]), ("dec", a["radar_decision_half_deg"])):
        w("| +-%g deg%s | %s mm | %s mm | %s mm square | %s mm square |"
          % (half, " (laptop beam grid)" if tag == "dec" else " (full field)",
             _f1(c["radar_win_setback_w_%s" % tag]), _f1(c["radar_win_setback_h_%s" % tag]),
             _f1(c["radar_shield_%s_s%s" % (tag, o["radar"]["window_t"])]),
             _f1(c["radar_shield_%s_s%s" % (tag, float(SUPPLIED["front_plate_mm"][2]))])))
    w("")
    w("**Flux disc.** Disc assumed %g mm dia (hole %g mm). View factor F from the disc to a coaxial opening of "
      "diameter D at distance H (parallel coaxial discs)." % (a["disc_d_mm"], o["flux_disc"]["hole_d"]))
    w("Disc recessed 3 mm (at the plate's back face), no shield: F to the %g mm hole = **%s**."
      % (o["flux_disc"]["hole_d"], _f2(c["disc_F_hole_recess3"])))
    w("")
    w("| H (disc to shield opening) | F, D = %g mm | F, D = 50 mm | F, D = 80 mm | F, D = 120 mm | D for F = 0.5 | "
      "D for F = 0.9 | D for F = 0.95 |" % o["flux_disc"]["hole_d"])
    w("|---|---|---|---|---|---|---|---|")
    for h, lab in ((gap, "%d mm (disc flush with the plate front)" % gap),
                   (gap + SUPPLIED["front_plate_mm"][2], "%d mm (disc 3 mm recessed)"
                    % (gap + SUPPLIED["front_plate_mm"][2]))):
        w("| %s | %s | %s | %s | %s | %s mm | %s mm | %s mm |"
          % (lab, _f2(c["disc_F_h%d_a%s" % (h, o["flux_disc"]["hole_d"])]), _f2(c["disc_F_h%d_a50.0" % h]),
             _f2(c["disc_F_h%d_a80.0" % h]), _f2(c["disc_F_h%d_a120.0" % h]), _f1(c["disc_ap_h%d_F0.5" % h]),
             _f1(c["disc_ap_h%d_F0.9" % h]), _f1(c["disc_ap_h%d_F0.95" % h])))
    w("")
    w("**Radar window, PETG slab, %g-%g GHz, eps_r %g-%g and tan d %g (assumed, unverified).** Worst case over the "
      "sweep." % (a["radar_f_ghz"][0], a["radar_f_ghz"][1], a["petg_eps_r"][0], a["petg_eps_r"][1], a["petg_tan_d"]))
    w("")
    w("| eps_r | Half-wave thickness | 1.2 mm: one-way | 1.2 mm: two-way loss | 1.2 mm: reflection into the radar | "
      "Half-wave slab: two-way | Half-wave: reflection | Unthinned 3 mm: two-way | 3 mm: reflection |")
    w("|---|---|---|---|---|---|---|---|---|")
    for eps in a["petg_eps_r"]:
        s12, shw, s3 = c["slab_1.2_eps%s" % eps], c["slab_hw_eps%s" % eps], c["slab_3.0_eps%s" % eps]
        w("| %g | %s mm | %s dB | **%s dB** | **%s dB** | %s dB | %s dB | %s dB | %s dB |"
          % (eps, _f2(c["half_wave_eps%s" % eps]), _f2(s12["one_way_db"]), _f2(s12["two_way_db"]),
             _f1(s12["refl_db"]), _f2(shw["two_way_db"]), _f1(shw["refl_db"]), _f2(s3["two_way_db"]),
             _f1(s3["refl_db"])))
    w("")
    w("Worst possible reflection (quarter-wave thickness): %s dB (eps_r %g), %s dB (eps_r %g)."
      % (_f1(c["refl_max_quarter_wave"][a["petg_eps_r"][0]]), a["petg_eps_r"][0],
         _f1(c["refl_max_quarter_wave"][a["petg_eps_r"][1]]), a["petg_eps_r"][1]))
    w("")
    w("**Housing temperature.** Body surface %s m2; 4 mm PETG, k %g W/(m K); h inside %g, outside %g (parked) / %g "
      "(driving) W/(m2 K), all assumed. Steady inside-air rise over ambient, closed box, no sun:"
      % (_f2(c["body_area_m2"]), a["petg_k"], a["h_in"], a["h_out"][0], a["h_out"][1]))
    w("")
    w("| Power dissipated inside (MOUNTING_AND_POWER.md estimate) | Parked | Driving |")
    w("|---|---|---|")
    for p in a["unit_power_w"]:
        w("| %g W | +%s K | +%s K |" % (p, _f1(c["rise_p%d_h%d" % (p, a["h_out"][0])]),
                                         _f1(c["rise_p%d_h%d" % (p, a["h_out"][1])])))
    w("")
    w("Sun on the lid (1000 W/m2): outside-surface rise alpha G / h = %s K (absorptivity 0.3, parked) to %s K "
      "(0.9, parked); %s-%s K driving."
      % (_f1(c["sol_air_lid_k"][(0.3, 10.0)]), _f1(c["sol_air_lid_k"][(0.9, 10.0)]),
         _f1(c["sol_air_lid_k"][(0.3, 30.0)]), _f1(c["sol_air_lid_k"][(0.9, 30.0)])))
    w("")
    w("**Flux disc against the 70 C stop.** Copper disc %g mm thick (assumed), absorptivity %g, losses ignored "
      "(so these are the fastest case)." % (a["disc_t_mm"], a["disc_absorptivity"]))
    w("")
    w("| Incident flux | Heating rate | 20 C -> 70 C stop | 70 C -> PETG Tg (%g C) if exposure continues |"
      % a["petg_tg_c"])
    w("|---|---|---|---|")
    for q, lab in ((5.0, "5 kW/m2"), (20.0, "20 kW/m2"), (50.0, "50 kW/m2"),
                   (78.2, "78.2 kW/m2 (FDS C064 in-flame reference, not a measurement)")):
        w("| %s | %s K/s | %s s | %s s |" % (lab, _f1(c["disc_rate_q%s" % q]), _f1(c["disc_t70_q%s" % q]),
                                              _f1(c["disc_t_tg_q%s" % q])))
    w("")
    w("Cooling time constant after a stop (h_eff ~ 20 W/(m2 K), assumed): about %d s." % round(c["disc_tau_s"]))
    return "\n".join(L) + "\n"


CHECKS_BEGIN = "<!-- checks:begin (generated by make_drawings.py; do not edit by hand) -->"
CHECKS_END = "<!-- checks:end -->"


def housing_md_with_checks(text: str) -> str:
    i, j = text.find(CHECKS_BEGIN), text.find(CHECKS_END)
    if i < 0 or j < i:
        raise ValueError("HOUSING.md lacks the checks markers")
    return text[:i + len(CHECKS_BEGIN)] + "\n" + checks_markdown() + text[j:]


# --------------------------------------------------------------------------------------------------------------
# Minimal SVG helpers
# --------------------------------------------------------------------------------------------------------------
def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def f(v: float) -> str:
    """Compact, deterministic number formatting for SVG coordinates."""
    r = round(v, 2)
    if r == int(r):
        return str(int(r))
    return ("%.2f" % r).rstrip("0").rstrip(".")


class Svg:
    def __init__(self, w: int, h: int, title: str, desc: str):
        self.w, self.h = w, h
        self.parts: list[str] = []
        self.title, self.desc = title, desc

    def add(self, s: str) -> None:
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, stroke="#222", width=2.0, dash=None, cls=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        c = ' class="%s"' % cls if cls else ""
        self.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s%s/>'
                 % (f(x1), f(y1), f(x2), f(y2), stroke, f(width), d, c))

    def poly(self, pts, stroke="#222", width=2.0, dash=None, fill="none"):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        p = " ".join("%s,%s" % (f(x), f(y)) for x, y in pts)
        self.add('<polyline points="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"%s/>'
                 % (p, fill, stroke, f(width), d))

    def rect(self, x, y, w, h, fill="#fff", stroke="#222", width=1.5, rx=0, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" stroke-width="%s"%s/>'
                 % (f(x), f(y), f(w), f(h), f(rx), fill, stroke, f(width), d))

    def circle(self, cx, cy, r, fill="#fff", stroke="#222", width=1.5, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.add('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="%s"%s/>'
                 % (f(cx), f(cy), f(r), fill, stroke, f(width), d))

    def text(self, x, y, s, size=12, anchor="start", weight="normal", fill="#111", italic=False):
        st = ' font-style="italic"' if italic else ""
        self.add('<text x="%s" y="%s" font-size="%s" text-anchor="%s" font-weight="%s" fill="%s"%s>%s</text>'
                 % (f(x), f(y), f(size), anchor, weight, fill, st, esc(s)))

    def lines(self, x, y, rows, size=12, step=None, **kw):
        step = step or size * 1.3
        for i, r in enumerate(rows):
            self.text(x, y + i * step, r, size=size, **kw)

    def dot(self, x, y, color="#222"):
        self.circle(x, y, 3.5, fill=color, stroke=color, width=1)

    def render(self) -> str:
        head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
                'role="img" aria-labelledby="t d" font-family="Helvetica, Arial, sans-serif">\n'
                '<title id="t">%s</title>\n<desc id="d">%s</desc>\n'
                '<defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" '
                'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>\n'
                '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>\n'
                % (self.w, self.h, self.w, self.h, esc(self.title), esc(self.desc), self.w, self.h))
        return head + "\n".join(self.parts) + "\n</svg>\n"


# --------------------------------------------------------------------------------------------------------------
# Wiring: the ONE pin list (user's printed build manual, 2026-11-17)
# --------------------------------------------------------------------------------------------------------------
PIN_MAP_SOURCE = "pin map from the user's printed build manual (2026-11-17)"

# Raspberry Pi J8 header, physical facts (Pi 4 and Pi 5 share it). Only the names; nothing here is a design choice.
PI_PINS = {
    1: "3V3", 2: "5V", 3: "GPIO2 SDA1", 4: "5V", 5: "GPIO3 SCL1", 6: "GND", 7: "GPIO4", 8: "GPIO14 TXD",
    9: "GND", 10: "GPIO15 RXD", 11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22",
    16: "GPIO23", 17: "3V3", 18: "GPIO24", 19: "GPIO10 MOSI", 20: "GND", 21: "GPIO9 MISO", 22: "GPIO25",
    23: "GPIO11 SCLK", 24: "GPIO8 CE0", 25: "GND", 26: "GPIO7 CE1", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5",
    30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19", 36: "GPIO16", 37: "GPIO26",
    38: "GPIO20", 39: "GND", 40: "GPIO21",
}

# (pin, net, goes to, label on the wire in wiring.svg). This is the user's map, nothing else.
PIN_MAP = (
    (1, "3V3", "BNO055 VIN (3.3 V)", "BNO055 VIN"),
    (3, "SDA", "BNO055 SDA", "BNO055 SDA"),
    (5, "SCL", "BNO055 SCL", "BNO055 SCL"),
    (6, "GND", "BNO055 GND", "BNO055 GND"),
    (17, "3V3", "VIN of all three MAX31855 boards", "MAX31855 VIN x3"),
    (20, "GND", "GND of all three MAX31855 boards", "MAX31855 GND x3"),
    (21, "MISO", "DO (SO) of all three MAX31855 boards", "DO x3"),
    (23, "SCLK", "CLK of all three MAX31855 boards", "CLK x3"),
    (24, "CS_PLATE", "CS of MAX31855 #1 (`tc_plate`, flux plate)", "plate CS"),
    (26, "CS_HOUSING", "CS of MAX31855 #2 (`tc_housing`)", "housing CS"),
    (29, "CS_AIR", "CS of MAX31855 #3 (`tc_air`, intake air), software chip select", "air CS (software)"),
)
USED_PINS = {pin: (net, label) for pin, net, _to, label in PIN_MAP}

# The user's map as stated, used by test_docs.py to check PIN_MAP and every document against it.
USER_MAP = {
    "max31855_3v3_pin": 17, "max31855_gnd_pin": 20, "max31855_clk": (23, 11), "max31855_do": (21, 9),
    "cs_plate": (24, 8), "cs_housing": (26, 7), "cs_air": (29, 5),
    "bno055_3v3_pin": 1, "bno055_gnd_pin": 6, "bno055_sda_pin": 3, "bno055_scl_pin": 5,
}

# Net colours. Every wire also carries a text label, so colour is never the only cue (accessibility).
NETS = {
    "3V3": ("#d62728", None, "3V3 (red)"),
    "GND": ("#222222", None, "GND (black)"),
    "SCLK": ("#ff7f0e", None, "SPI0 SCLK, GPIO11 pin 23 (orange)"),
    "MISO": ("#2ca02c", None, "SPI0 MISO = DO, GPIO9 pin 21 (green)"),
    "CS_PLATE": ("#1f77b4", "8 4", "CS plate, CE0 GPIO8 pin 24 (blue, dashed)"),
    "CS_HOUSING": ("#9467bd", "8 4", "CS housing, CE1 GPIO7 pin 26 (purple, dashed)"),
    "CS_AIR": ("#8c564b", "8 4", "CS air GPIO5 pin 29, software (brown, dashed)"),
    "SDA": ("#17becf", "2 3", "I2C1 SDA (cyan, dotted)"),
    "SCL": ("#e377c2", "2 3", "I2C1 SCL (pink, dotted)"),
    "TCP": ("#c9a400", None, "Type-K + (yellow, ANSI)"),
    "TCN": ("#d62728", "6 3", "Type-K - (red, ANSI, dashed here)"),
    "V12": ("#d62728", None, "+12 V"),
    "V5": ("#ff7f0e", None, "+5 V"),
    "USB": ("#555555", "10 3 2 3", "USB cable (grey, dash-dot)"),
}


def wiring_svg() -> str:
    W, H = 1400, 1130
    s = Svg(W, H, "WildfireGuardian vehicle unit wiring",
            "Raspberry Pi 4/5 40-pin header wired per the user's printed build manual: three MAX31855 "
            "thermocouple amplifiers sharing 3V3 pin 17, GND pin 20, CLK pin 23 and DO pin 21, chip selects "
            "GPIO8 pin 24 (plate), GPIO7 pin 26 (housing) and GPIO5 pin 29 (air, software chip select); BNO055 on "
            "I2C1 at 0x28 (3V3 pin 1, GND pin 6, SDA pin 3, SCL pin 5); USB thermal camera, radar EVM and GNSS; "
            "fused 12 V to 5 V power chain. Not verified on hardware.")
    s.text(30, 38, "WildfireGuardian vehicle unit: wiring (Raspberry Pi 4 / 5)", size=22, weight="bold")
    s.text(30, 62, "Pin map from the user's printed build manual (2026-11-17). Not wired or verified on hardware. "
                   "Header viewed from above, pin 1 top left.", size=13, fill="#444")

    # Header
    Y0, S = 150, 26
    hx0, hx1 = 540, 720
    xo, xe = 605, 655
    s.rect(hx0, Y0 - 24, hx1 - hx0, 20 * S + 22, fill="#f4f4f4", stroke="#333", width=2, rx=6)
    s.text((hx0 + hx1) / 2, Y0 - 32, "Raspberry Pi 40-pin header (J8)", size=14, anchor="middle", weight="bold")

    def py(pin: int) -> float:
        return Y0 + ((pin - 1) // 2) * S

    for pin, name in PI_PINS.items():
        odd = pin % 2 == 1
        x = xo if odd else xe
        used = pin in USED_PINS
        col = NETS[USED_PINS[pin][0]][0] if used else "#bbb"
        s.circle(x, py(pin), 7, fill=col if used else "#fff", stroke="#333" if used else "#999", width=1.2)
        s.text(x - 20 if odd else x + 20, py(pin) + 4, str(pin), size=11,
               anchor="end" if odd else "start", weight="bold" if used else "normal",
               fill="#111" if used else "#888")
        if used:
            net, lab = USED_PINS[pin]
            colr, dash, _ = NETS[net]
            xend = 420 if odd else 860
            if pin == 6:
                xend = 845
            s.line(hx0 if odd else hx1, py(pin), xend, py(pin), stroke=colr, width=2.5, dash=dash)
            s.text(hx0 - 8 if odd else hx1 + 8, py(pin) - 5, "%s <- %s" % (lab, name) if odd else
                   "%s -> %s" % (name, lab), size=10.5, anchor="end" if odd else "start", fill="#111")
        else:
            s.text(hx0 - 8 if odd else hx1 + 8, py(pin) + 4, name, size=10, anchor="end" if odd else "start",
                   fill="#999")

    # ---------------- MAX31855 boards (right) ----------------
    bx0, bx1 = 1010, 1150
    boards = [("plate", "MAX31855 #1  tc_plate  (CE0, GPIO8)", 120, "CS_PLATE", 990,
               ["Copper flux disc (30.6 mm hole)", "on printed PETG tabs:", "runs stop at 70 C disc"]),
              ("housing", "MAX31855 #2  tc_housing  (CE1, GPIO7)", 290, "CS_HOUSING", 975,
               ["Housing interior", "K probe taped to the wall", "away from Pi and buck"]),
              ("air", "MAX31855 #3  tc_air  (GPIO5, software CS)", 460, "CS_AIR", 960,
               ["Intake-height air probe", "radiation-shielded, ungrounded", "separate type-K extension lead"])]
    bus = {"3V3": 880, "GND": 900, "MISO": 920, "SCLK": 940}
    pin_off = {"VIN": 25, "GND": 45, "DO": 65, "CS": 85, "CLK": 105}
    first_top = boards[0][2]
    last_top = boards[-1][2]
    # GND from pin 20 straight to the bus
    cg = NETS["GND"][0]
    s.poly([(860, py(20)), (bus["GND"], py(20))], stroke=cg, width=2.5)
    s.line(bus["GND"], first_top + pin_off["GND"], bus["GND"], last_top + pin_off["GND"], stroke=cg, width=2.5)
    s.dot(bus["GND"], py(20), cg)
    # 3V3 (pin 17), MISO (pin 21), SCLK (pin 23), CS air (pin 29): left, down under the header, right, up
    routes = (("3V3", 17, 375, 700, bus["3V3"], "VIN"), ("MISO", 21, 360, 716, bus["MISO"], "DO"),
              ("SCLK", 23, 345, 732, bus["SCLK"], "CLK"))
    for net, pin, xl, yb, xbus, bpin in routes:
        colr = NETS[net][0]
        s.poly([(420, py(pin)), (xl, py(pin)), (xl, yb), (xbus, yb), (xbus, first_top + pin_off[bpin])],
               stroke=colr, width=2.5)
    c_air, d_air, _ = NETS["CS_AIR"]
    air_top = boards[2][2]
    s.poly([(420, py(29)), (330, py(29)), (330, 748), (960, 748), (960, air_top + pin_off["CS"]),
            (bx0, air_top + pin_off["CS"])], stroke=c_air, width=2.5, dash=d_air)
    s.lines(1010, 704, ["3V3 pin 17 -> VIN x3 (3.3 V part: never 5 V)", "DO x3 <- GPIO9 MISO pin 21",
                        "CLK x3 <- GPIO11 SCLK pin 23", "air CS <- GPIO5 pin 29 (software CS)"], size=10.5, step=16)
    for key, title, top, csnet, xcs, sensor in boards:
        s.rect(bx0, top, bx1 - bx0, 125, fill="#eef5ff", stroke="#1f3b66", width=1.8, rx=5)
        s.text(bx0, top - 6, title, size=12.5, weight="bold")
        for pn, off in pin_off.items():
            y = top + off
            s.text(bx0 + 8, y + 4, pn, size=10.5)
            net = {"VIN": "3V3", "GND": "GND", "DO": "MISO", "CLK": "SCLK"}.get(pn)
            if net:
                colr, dash, _ = NETS[net]
                s.line(bus[net], y, bx0, y, stroke=colr, width=2.5, dash=dash)
                s.dot(bus[net], y, colr)
        if key != "air":
            colr, dash, _ = NETS[csnet]
            src_pin = {"CS_PLATE": 24, "CS_HOUSING": 26}[csnet]
            s.poly([(860, py(src_pin)), (xcs, py(src_pin)), (xcs, top + pin_off["CS"]), (bx0, top + pin_off["CS"])],
                   stroke=colr, width=2.5, dash=dash)
        # thermocouple side
        s.text(bx1 - 8, top + 50, "T+", size=10.5, anchor="end")
        s.text(bx1 - 8, top + 80, "T-", size=10.5, anchor="end")
        s.line(bx1, top + 46, 1215, top + 46, stroke=NETS["TCP"][0], width=3)
        s.line(bx1, top + 76, 1215, top + 76, stroke=NETS["TCN"][0], width=3, dash=NETS["TCN"][1])
        s.text(1157, top + 41, "+ yellow", size=9.5, fill="#7a6400")
        s.text(1157, top + 92, "- red", size=9.5, fill="#a01010")
        s.rect(1215, top + 22, 175, 80, fill="#fffbe6", stroke="#8a7300", width=1.4, rx=4)
        s.lines(1222, top + 40, sensor, size=10.5, step=15)
        s.text(1222, top + 95, "type-K wire end to end", size=9.5, fill="#7a6400", italic=True)
    s.lines(1006, 604, ["Chip selects, active low. Plate CE0 (spidev0.0), housing CE1 (spidev0.1):",
                        "kernel CS. Air GPIO5: SOFTWARE CS, driver opens spidev0.0 with no_cs=True,",
                        "drives GPIO5 under a lock shared with plate and housing.",
                        "Advice: 10 kOhm pull-up GPIO5 -> 3V3. 10 nF across T+/T-.",
                        "MOSI (pin 19) unused: the MAX31855 is read-only."],
            size=10, step=15)

    # ---------------- BNO055 (left) ----------------
    cx0, cx1 = 150, 300
    s.rect(cx0, 120, cx1 - cx0, 335, fill="#f0fff4", stroke="#1d5e33", width=1.8, rx=5)
    s.text((cx0 + cx1) / 2, 113, "BNO055 IMU breakout  (imu)", size=12.5, anchor="middle", weight="bold")
    for pn, pin in (("VIN", 1), ("SDA", 3), ("SCL", 5)):
        net = USED_PINS[pin][0]
        colr, dash, _ = NETS[net]
        y = py(pin)
        s.line(420, y, cx1, y, stroke=colr, width=2.5, dash=dash)
        s.text(cx1 - 8, y + 4, pn, size=10.5, anchor="end")
    # GND from pin 6 (right column): right, up over the header, left, down into the top of the box
    s.poly([(845, py(6)), (845, 100), (125, 100), (125, 228), (cx0, 228)], stroke=cg, width=2.5)
    s.text(cx0 + 8, 232, "GND", size=10.5)
    s.text(470, 95, "GND pin 6 -> BNO055 GND", size=10.5, fill=cg)
    s.lines(cx0 + 8, 260, ["3V3 pin 1, GND pin 6", "SDA pin 3, SCL pin 5", "ADR -> GND: address 0x28",
                           "PS0, PS1 -> GND: I2C mode", "I2C1 (bus 1)", "BNO055 stretches SCL; Pi I2C",
                           "mishandles it: set"], size=10, step=13)
    s.text(cx0 + 8, 360, "i2c_arm_baudrate=10000", size=10, weight="bold")
    s.lines(30, 478, ["UART alternative (not the default): PS1 -> 3V3,",
                      "BNO055 TX -> GPIO15 RXD (pin 10), RX -> GPIO14 TXD",
                      "(pin 8), 115200 baud, enable_uart=1, serial console off."], size=10.5, step=15)

    # ---------------- USB devices (bottom left) ----------------
    uy = 830
    s.text(30, uy - 20, "USB devices (Pi USB-A ports)", size=15, weight="bold")
    s.rect(30, uy, 150, 200, fill="#f4f4f4", stroke="#333", width=1.8, rx=5)
    s.lines(40, uy + 25, ["Raspberry Pi", "USB 3.0 x2 (blue)", "USB 2.0 x2", "", "Pi 4: 1.2 A total",
                          "Pi 5: 600 mA total", "unless 5 V 5 A PD", "(or usb_max_current", "_enable=1)"],
            size=10.5, step=15)
    cu, du, _ = NETS["USB"]
    devs = [(uy + 10, "InfiRay P2 Pro thermal camera (thermal), USB 0bda:5830",
             ["USB-C plug -> USB-C(f) to USB-A(m) OTG adapter or cable",
              "UVC 256x384 YUYV (same frame as the Topdon TC001)"]),
            (uy + 75, "TI IWR6843AOPEVM radar (radar), stock mmw demo",
             ["micro-USB, 5 V from USB (about 2-3 W). Two serial ports enumerate:",
              "CLI 115200 baud (config) + DATA 921600 baud (TLV frames).",
              "Board must be in functional mode (SOP switch), see WIRING.md."]),
            (uy + 155, "USB GNSS receiver (gnss)",
             ["NMEA over USB serial, about 0.2 W; antenna needs sky view", "(clear of the aluminium heat shield)"])]
    for y, title, rows in devs:
        s.line(180, y + 20, 260, y + 20, stroke=cu, width=2.5, dash=du)
        s.rect(260, y, 420, 18 + 15 * len(rows) + 8, fill="#fafafa", stroke="#555", width=1.3, rx=4)
        s.text(268, y + 15, title, size=11.5, weight="bold")
        s.lines(268, y + 31, rows, size=10.5, step=15)
    s.text(190, uy + 225, "Option: powered USB hub fed from the 5 V buck if the Pi limits USB current.",
           size=10.5, fill="#444", italic=True)

    # ---------------- Power chain (bottom right) ----------------
    px = 730
    s.text(px, uy - 20, "Power: 12 V accessory socket to Pi", size=15, weight="bold")
    blocks = [("12 V socket", ["vehicle accessory", "plug (own fuse)"]),
              ("5 A blade fuse", ["inline, close", "to the plug"]),
              ("Reverse polarity", ["ideal diode /", "P-FET (or Schottky)"]),
              ("TVS to GND", ["load-dump clamp,", "unidirectional"]),
              ("12 -> 5 V buck", ["automotive, 5 V 5 A,", "input >= 36 V rated"])]
    bw, gap = 112, 14
    c12 = NETS["V12"][0]
    for i, (t, rows) in enumerate(blocks):
        x = px + i * (bw + gap)
        s.rect(x, uy, bw, 70, fill="#fff5f5", stroke="#7a1010", width=1.5, rx=4)
        s.text(x + bw / 2, uy + 18, t, size=11.5, anchor="middle", weight="bold")
        s.lines(x + bw / 2, uy + 36, rows, size=10, step=14, anchor="middle")
        if i < len(blocks) - 1:
            s.line(x + bw, uy + 35, x + bw + gap, uy + 35, stroke=c12, width=3)
    s.text(px + 10, uy + 90, "+12 V nominal (9-16 V running; dips to about 6 V while cranking; transients above "
                             "24 V possible)", size=10.5, fill=c12)
    c5 = NETS["V5"][0]
    xb = px + 4 * (bw + gap) + bw / 2
    s.poly([(xb, uy + 70), (xb, uy + 120), (px + 60, uy + 120), (px + 60, uy + 140)], stroke=c5, width=3)
    s.rect(px, uy + 140, 300, 60, fill="#fffaf0", stroke="#a35400", width=1.5, rx=4)
    s.lines(px + 10, uy + 158, ["Pi 5: USB-C PD 5.1 V 5 A (27 W class)", "Pi 4: USB-C 5.1 V 3 A",
                                "do not back-feed 5 V via GPIO pins 2/4 unprotected"], size=10.5, step=15)
    s.text(xb - 50, uy + 115, "+5 V", size=10.5, fill=c5, weight="bold")
    s.line(px, uy + 225, px + 640, uy + 225, stroke=cg, width=3)
    s.text(px + 4, uy + 243, "GND / 0 V: returns through the socket plug only. Copper disc and thermocouple "
                             "sheaths stay isolated from chassis.", size=10.5)
    s.text(px + 4, uy + 258, "(a grounded junction makes the MAX31855 report SHORT_GND)", size=10.5, fill="#444")

    # ---------------- Legend ----------------
    lx, ly = 30, 545
    s.text(lx, ly, "Wire legend (colour + pattern + label)", size=13, weight="bold")
    keys = ["3V3", "GND", "SCLK", "MISO", "CS_PLATE", "CS_HOUSING", "CS_AIR", "SDA", "SCL", "TCP", "TCN", "USB"]
    for i, k in enumerate(keys):
        colr, dash, lab = NETS[k]
        y = ly + 20 + i * 16
        s.line(lx, y - 4, lx + 40, y - 4, stroke=colr, width=3, dash=dash)
        s.text(lx + 48, y, lab, size=10)
    return s.render()


# --------------------------------------------------------------------------------------------------------------
# Front-plate layout of the SUPPLIED housing (documentation of user-given dimensions; not a design)
# --------------------------------------------------------------------------------------------------------------
HOUSING_LABEL = "documentation of the supplied housing, dimensions as given by the user; not a design"


def housing_svg() -> str:
    o = SENSOR_OFFSETS_MM
    bw, bd, bh = SUPPLIED["body_mm"]
    pw, ph, pt = SUPPLIED["front_plate_mm"]
    zc = SUPPLIED["sensor_centre_line_above_base_mm"]
    gap = SUPPLIED["heat_shield"]["gap_mm"]
    W, H = 1400, 900
    s = Svg(W, H, "Supplied housing: front-plate layout",
            "Front view and plan view of the user's printed PETG housing, drawn only from the dimensions the user "
            "gave: body 180 x 140 x 72 mm, 4 mm walls, bolt-on front plate 172 x 66 x 3 mm with a 12 mm camera "
            "hole at x = -52, a 52 x 42 mm radar window thinned to 1.2 mm at x = -8 and a 30.6 mm flux-disc hole "
            "at x = +45, all on one centre line 34 mm above the base, aluminium heat shield 10 mm in front. "
            "Documentation of the supplied housing, not a design.")
    s.text(30, 38, "Supplied housing: front-plate layout (dimensions in mm)", size=22, weight="bold")
    s.text(30, 62, HOUSING_LABEL + ". Printed PETG (material as told by the user), 2026-11-17.",
           size=13, fill="#444")
    dim_c = "#0b5394"

    def dim_h(x1, x2, y, label, ext_from=None):
        if ext_from is not None:
            s.line(x1, ext_from, x1, y + 4, stroke=dim_c, width=0.8)
            s.line(x2, ext_from, x2, y + 4, stroke=dim_c, width=0.8)
        s.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.1" marker-start="url(#arr)" '
              'marker-end="url(#arr)"/>' % (f(x1), f(y), f(x2), f(y), dim_c))
        s.text((x1 + x2) / 2, y - 4, label, size=11, anchor="middle", fill=dim_c)

    def dim_v(x, y1, y2, label, ext_from=None, side="left"):
        if ext_from is not None:
            s.line(ext_from, y1, x - 4 if side == "left" else x + 4, y1, stroke=dim_c, width=0.8)
            s.line(ext_from, y2, x - 4 if side == "left" else x + 4, y2, stroke=dim_c, width=0.8)
        s.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.1" marker-start="url(#arr)" '
              'marker-end="url(#arr)"/>' % (f(x), f(y1), f(x), f(y2), dim_c))
        tx = x - 6 if side == "left" else x + 6
        s.text(tx, (y1 + y2) / 2 + 4, label, size=11, anchor="end" if side == "left" else "start", fill=dim_c)

    # ---------------- FRONT VIEW ----------------
    k = 3.0
    ox, oy = 420, 470          # px of (x = 0, z = 0 = housing base)
    U = lambda xv: ox + xv * k                     # noqa: E731
    V = lambda zv: oy - zv * k                     # noqa: E731
    s.text(ox, 120, "FRONT VIEW (from ahead of the vehicle), scale 3 px/mm", size=14, anchor="middle",
           weight="bold")
    s.text(ox, 138, "x as in the build manual; drawn + to the right seen from the front: sign convention UNCONFIRMED",
           size=10.5, anchor="middle", fill="#a35400")
    s.rect(U(-bw / 2), V(bh), bw * k, bh * k, fill="#f7f7f7", stroke="#666", width=1.4, dash="7 4")
    s.lines(U(bw / 2) + 8, V(bh) + 10, ["body face", "180 x 72 (dashed)"], size=10, step=13, fill="#555")
    z0 = (bh - ph) / 2.0       # plate drawn centred on the body face: an assumption for the drawing only
    s.rect(U(-pw / 2), V(z0 + ph), pw * k, ph * k, fill="#e8f0e0", stroke="#2f4f1f", width=2)
    for xa, xb in ((U(-pw / 2) - 20, U(-pw / 2) + 6), (U(pw / 2) - 6, U(pw / 2) + 20)):
        s.line(xa, V(zc), xb, V(zc), stroke="#a35400", width=1.2, dash="10 4 2 4")
    s.text(U(pw / 2) + 22, V(zc) + 4, "centre line", size=10, fill="#a35400")
    s.line(U(0), V(z0), U(0), V(0) + 10, stroke="#888", width=0.8, dash="4 4")
    s.text(U(0) + 4, V(0) + 12, "x = 0", size=10, fill="#555")
    s.line(U(-bw / 2) - 30, V(0), U(bw / 2) + 30, V(0), stroke="#444", width=1.2)
    s.text(U(-60), V(0) + 14, "housing base (z = 0)", size=10, fill="#444")
    cam, rad, disc = o["camera"], o["radar"], o["flux_disc"]
    s.circle(U(cam["x"]), V(cam["z"]), cam["hole_d"] / 2 * k, fill="#ffffff", stroke="#22334d", width=1.6)
    s.text(U(cam["x"]), V(cam["z"]) - cam["hole_d"] / 2 * k - 6, "camera", size=10.5, anchor="middle")
    s.rect(U(rad["x"] - rad["window_w"] / 2), V(rad["z"] + rad["window_h"] / 2), rad["window_w"] * k,
           rad["window_h"] * k, fill="#f7f2d9", stroke="#7a6a1a", width=1.6)
    s.text(U(rad["x"]), V(rad["z"]) - 8, "radar window", size=10.5, anchor="middle")
    s.text(U(rad["x"]), V(rad["z"]) + 18, "thinned to %g" % rad["window_t"], size=10.5, anchor="middle")
    s.circle(U(disc["x"]), V(disc["z"]), disc["hole_d"] / 2 * k, fill="#ffffff", stroke="#7a3a10", width=1.6)
    s.text(U(disc["x"]), V(disc["z"]) + 24, "flux disc", size=10.5, anchor="middle")
    # dimensions
    dim_h(U(-pw / 2), U(pw / 2), V(z0) + 44, "plate %d x %d x %d" % (pw, ph, pt), ext_from=V(z0))
    dim_h(U(-bw / 2), U(bw / 2), V(0) + 70, "body %d" % bw, ext_from=V(0))
    dim_v(U(-bw / 2) - 40, V(bh), V(0), "%d" % bh, ext_from=U(-bw / 2))
    dim_v(U(-pw / 2) - 14, V(zc), V(0), "%d" % zc, ext_from=U(-pw / 2))
    yo = V(bh) - 18
    for xv, lab in ((cam["x"], "x = %d" % cam["x"]), (rad["x"], "x = %d" % rad["x"]), (disc["x"], "x = +%d" % disc["x"])):
        s.line(U(xv), V(bh), U(xv), yo + 4, stroke=dim_c, width=0.8)
        s.line(U(xv), V(zc) - 7, U(xv), V(zc) + 7, stroke="#a35400", width=1.2)
        s.line(U(xv) - 7, V(zc), U(xv) + 7, V(zc), stroke="#a35400", width=1.2)
        s.text(U(xv), yo, lab, size=11, anchor="middle", fill=dim_c)
    dim_h(U(cam["x"] - cam["hole_d"] / 2), U(cam["x"] + cam["hole_d"] / 2), V(zc) + cam["hole_d"] / 2 * k + 16,
          "dia %d" % cam["hole_d"])
    dim_h(U(rad["x"] - rad["window_w"] / 2), U(rad["x"] + rad["window_w"] / 2),
          V(rad["z"] - rad["window_h"] / 2) + 16, "%d" % rad["window_w"])
    dim_v(U(rad["x"] + rad["window_w"] / 2) + 14, V(rad["z"] + rad["window_h"] / 2),
          V(rad["z"] - rad["window_h"] / 2), "%d" % rad["window_h"], side="right")
    dim_h(U(disc["x"] - disc["hole_d"] / 2), U(disc["x"] + disc["hole_d"] / 2),
          V(zc) + disc["hole_d"] / 2 * k + 16, "dia %g" % disc["hole_d"])
    s.lines(60, 640, ["Plate drawn centred on the body face: its vertical position relative to the body",
                      "is not given (assumption for this drawing only). The holes sit on the 34 mm line",
                      "measured from the housing base, as given."], size=10.5, step=15, fill="#555", italic=True)

    # ---------------- PLAN VIEW ----------------
    k2 = 2.0
    qx, qy = 1050, 300         # px of (x = 0, front wall outer face)
    P = lambda xv: qx + xv * k2                    # noqa: E731
    s.text(qx, 120, "PLAN VIEW (from above, front up), scale 2 px/mm", size=14, anchor="middle", weight="bold")
    s.rect(P(-bw / 2), qy, bw * k2, bd * k2, fill="#f7f7f7", stroke="#666", width=1.6)
    s.rect(P(-bw / 2) + SUPPLIED["wall_mm"] * k2, qy + SUPPLIED["wall_mm"] * k2, (bw - 2 * SUPPLIED["wall_mm"]) * k2,
           (bd - 2 * SUPPLIED["wall_mm"]) * k2, fill="#ffffff", stroke="#999", width=1, dash="4 3")
    s.rect(P(-pw / 2), qy - pt * k2, pw * k2, pt * k2, fill="#2f4f1f", stroke="#2f4f1f", width=1)
    ysh = qy - (pt + gap) * k2
    s.line(P(-bw / 2) - 10, ysh, P(bw / 2) + 10, ysh, stroke="#6b7480", width=3, dash="12 4")
    s.text(P(bw / 2) + 14, ysh + 4, "Al heat shield", size=10.5, fill="#3a4250")
    s.text(P(bw / 2) + 14, ysh + 18, "(size, apertures:", size=10, fill="#3a4250")
    s.text(P(bw / 2) + 14, ysh + 31, "not given)", size=10, fill="#3a4250")
    for xv, lab in ((cam["x"], "cam"), (rad["x"], "radar"), (disc["x"], "disc")):
        s.line(P(xv), qy - pt * k2, P(xv), qy + 26, stroke="#a35400", width=1.2)
        s.text(P(xv), qy + 40, lab, size=10.5, anchor="middle", fill="#a35400")
    dim_h(P(-bw / 2), P(bw / 2), qy + bd * k2 + 26, "%d" % bw, ext_from=qy + bd * k2)
    dim_v(P(-bw / 2) - 26, qy, qy + bd * k2, "%d" % bd, ext_from=P(-bw / 2))
    dim_v(P(-pw / 2) - 8, ysh, qy - pt * k2, "%d" % gap, side="left")
    s.text(P(-pw / 2) - 40, ysh - 8, "gap %d mm" % gap, size=10.5, anchor="end", fill=dim_c)
    s.text(qx, qy + 75, "walls %d mm" % SUPPLIED["wall_mm"], size=10.5, anchor="middle", fill="#555")
    s.text(qx, qy + 92, "plate %d mm, bolt-on" % pt, size=10.5, anchor="middle", fill="#555")

    # ---------------- Notes ----------------
    nx, ny = 760, 660
    s.text(nx, ny, "As given by the user (positions inside the body not given, so not drawn)", size=13, weight="bold")
    notes = [
        "Body %d x %d x %d mm (read as width x depth x height), %d mm walls, printed %s."
        % (bw, bd, bh, SUPPLIED["wall_mm"], SUPPLIED["material"]),
        "Raspberry Pi on four standoffs, %d x %d mm hole pattern." % SUPPLIED["pi_standoff_pattern_mm"],
        "%d floor rails with %s pilot holes every %d mm."
        % (SUPPLIED["floor_rails"], SUPPLIED["rail_pilot_hole"], SUPPLIED["rail_hole_pitch_mm"]),
        "Bolt-on front plate %d x %d x %d mm; aluminium heat shield %d mm in front." % (pw, ph, pt, gap),
        "Copper flux disc on printed PETG tabs: every flux run stops and warns at 70 C.",
        "Questions about the shield, holes and window: HOUSING.md section 3 (calculations).",
    ]
    s.lines(nx, ny + 22, notes, size=11, step=17)
    return s.render()


def outputs() -> dict:
    return {"wiring.svg": wiring_svg(), "housing.svg": housing_svg()}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    bad = []
    files = dict(outputs())
    hp = DOCS / "HOUSING.md"
    files["HOUSING.md"] = housing_md_with_checks(hp.read_text(encoding="utf-8"))
    for name, text in files.items():
        p = DOCS / name
        if check:
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                bad.append(name)
        else:
            p.write_text(text, encoding="utf-8")
            print("wrote", p)
    if bad:
        print("out of date:", ", ".join(bad), "(run make_drawings.py)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
