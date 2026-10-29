"""Physics comparison of radiation law v2 with published numbers (Deliverable 2).

Writes, next to this script: VALIDATION_TABLE.csv, VALIDATION.json, TORNADO.csv, fig01_flux_vs_distance.{png,svg},
fig05_tornado_20m.{png,svg}. Deterministic (no random numbers). Run from the repository root:

    python research/flame-front-radiation/physics_validation/run_physics_validation.py
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from front_model import E_1200K, W, distance_for_flux, flame_length_from_intensity, straight_front_flux  # noqa: E402

DIST = [5.0, 10.0, 20.0, 50.0, 100.0]
E_DEF = W.constants.EMISSIVE_POWER_SURFACE_KW_M2
E_CROWN = W.constants.EMISSIVE_POWER_CROWN_KW_M2
MORANDINI = {"flame_height_m": 2.5, "distances_m": [5.0, 10.0, 15.0], "flux_kw_m2": [7.8, 2.2, 1.0],
             "front_length_m": 30.0}
PIMONT = {"flame_height_m": 20.0, "distances_m": [10.0, 30.0, 50.0], "range_kw_m2": [(22, 31), (8, 12), (5, 8)]}


def minimax_E(model_per_unit_E, measured):
    """E minimising the largest |log(model/measured)| (model linear in E)."""
    c = [math.log(m / y) for m, y in zip(model_per_unit_E, measured)]
    logE = -(max(c) + min(c)) / 2.0
    E = math.exp(logE)
    worst = math.exp(max(abs(logE + ci) for ci in c))
    return E, worst


def main():
    rows = []
    out = {"law_version": W.LAW_VERSION, "receiver": "worst_case at 0 m unless noted", "rows": None}

    def add(group, reference, quantity, published, model, E, geometry, kind, verification, note=""):
        ratio = None
        if isinstance(published, (int, float)) and isinstance(model, (int, float)) and published > 0:
            ratio = model / published
        rows.append({"group": group, "reference": reference, "quantity": quantity, "published": published,
                     "model": None if model is None else round(float(model), 3), "ratio_model_over_published":
                     None if ratio is None else round(ratio, 3), "E_kw_m2": E, "geometry": geometry,
                     "comparison_kind": kind, "verification": verification, "note": note})

    # 1. straight fronts of given intensity: flame length and flux table (model only)
    for I in (1000.0, 5000.0, 20000.0):
        h = flame_length_from_intensity(I)
        add("intensity", "Byram 1959 L = 0.0775 I^0.46", "flame length (m) at I = %g kW/m" % I,
            {1000.0: 1.9, 5000.0: 3.9, 20000.0: 7.4}[I], h, None, "", "formula check", "standard")
        for d in DIST:
            for length, lab in ((1e5, "infinite front"), (100.0, "100 m front")):
                add("flux_table", "model", "q (kW/m2) at %g m, I = %g kW/m, %s" % (d, I, lab), None,
                    straight_front_flux(d, h, E=E_DEF, length=length), E_DEF, "vertical flame h = %.2f m" % h,
                    "model output", "n/a")
    # 2. Butler and Cohen 1998: 1200 K blackbody, 20 m flame width, 7 kW/m2, separation >= 4 flame heights
    for h in (2.0, 5.0, 10.0, 20.0):
        d7 = distance_for_flux(7.0, h, E=E_1200K, length=20.0, receiver="vertical")
        add("safety_zone", "Butler and Cohen 1998 (Int. J. Wildland Fire 8:73-77): >= 4 flame heights for 7 kW/m2",
            "separation / flame height at 7 kW/m2, h = %g m" % h, 4.0, d7 / h, round(E_1200K, 1),
            "20 m wide vertical panel, vertical receiver facing it", "model-to-model (same assumptions)",
            "4H rule confirmed by search; 1200 K and 20 m width prompt-supplied")
    for target, ref_val in ((7.0, 3.8), (4.7, 4.8)):
        for h in (5.0, 10.0):
            d = distance_for_flux(target, h, E=E_1200K, length=20.0, receiver="vertical")
            add("safety_zone", "Zarate et al. 2008: 3.8 to 4.8 flame heights for 7 and 4.7 kW/m2 (plus 20 % convection)",
                "separation / flame height at %g kW/m2, h = %g m" % (target, h), ref_val, d / h, round(E_1200K, 1),
                "20 m wide vertical panel, vertical receiver", "model-to-model", "prompt-supplied")
    # 3. Morandini et al. 2006, measured: 2.5 m shrub flames, 30 m wide plot
    per_E = [straight_front_flux(d, MORANDINI["flame_height_m"], E=1.0, length=MORANDINI["front_length_m"])
             for d in MORANDINI["distances_m"]]
    E_fit, worst_fit = minimax_E(per_E, MORANDINI["flux_kw_m2"])
    out["measured_decay_emissive_power"] = {"E_kw_m2": E_fit, "worst_factor": worst_fit, "fit_to": "Morandini et al. 2006, three distances",
                                            "method": "minimax of |log(model / measured)|, model linear in E"}
    for E, lab in ((E_DEF, "default"), (round(E_fit, 1), "measured-decay fit")):
        for d, y, pe in zip(MORANDINI["distances_m"], MORANDINI["flux_kw_m2"], per_E):
            add("measured_decay", "Morandini et al. 2006 (Fire Safety J. 41:229-235), 2.5 m shrub flames",
                "q (kW/m2) at %g m (%s E)" % (d, lab), y, pe * E, E,
                "30 m front (plot width from the paper abstract), vertical 2.5 m flame",
                "order of magnitude (sensor field of view, flame tilt and depth not reproduced)",
                "values prompt-supplied; plot width located in the abstract")
    # 4. Packham and Pompe 1971 via Butler 2014
    add("measured_decay", "Packham and Pompe 1971, compiled by Butler 2014", "q adjacent to flames (kW/m2)", 100.0,
        E_DEF, E_DEF, "receiver inside the flame (engulfment term = E)", "order of magnitude", "prompt-supplied")
    for h in (5.0, 10.0, 20.0):
        add("measured_decay", "Packham and Pompe 1971, compiled by Butler 2014", "q at 7.6 m (kW/m2), assumed h = %g m" % h,
            57.0, straight_front_flux(7.6, h, E=E_DEF), E_DEF, "infinite front; flame height not located",
            "order of magnitude", "prompt-supplied; flame height not located",
            "57 kW/m2 at 7.6 m needs E >= %.0f kW/m2 for any flame height (worst-case factor < sin(45 deg))" % (57.0 / math.sin(math.pi / 4)))
    # 5. Silvani and Morandini 2009: 5.6 m flames, 36 % slope, 51 radiative, 112 total at the sensor
    add("measured_decay", "Silvani and Morandini 2009", "radiative flux at the sensor (kW/m2), 5.6 m flames", 51.0, None,
        E_DEF, "sensor distance and slope geometry not located", "not reproduced", "prompt-supplied",
        "model engulfment value is %.0f; a planar solid flame on a slope is not implemented" % E_DEF)
    # 6. Pimont, Dupuy and Linn 2014 FIRETEC, 20 m crown fires (simulation, not measurement)
    per_Ec = [straight_front_flux(d, PIMONT["flame_height_m"], E=1.0) for d in PIMONT["distances_m"]]
    mids = [math.sqrt(a * b) for a, b in PIMONT["range_kw_m2"]]
    Ec_fit, worst_c = minimax_E(per_Ec, mids)
    out["crown_simulation_emissive_power"] = {"E_kw_m2": Ec_fit, "worst_factor_to_range_midpoints": worst_c,
                                              "note": "fitted to a simulation; not used by any routing run"}
    for d, (lo, hi), pe in zip(PIMONT["distances_m"], PIMONT["range_kw_m2"], per_Ec):
        add("simulation", "Pimont, Dupuy and Linn 2014 (FIRETEC), one-minute mean peaks", "q at %g m (kW/m2), crown E" % d,
            math.sqrt(lo * hi), pe * E_CROWN, E_CROWN, "infinite 20 m flame wall (stand edge)", "model-to-model (simulation)",
            "prompt-supplied", "published range %g-%g" % (lo, hi))
    # 7. emissive powers (in-flame)
    add("emissive_power", "Frankman et al. 2013: surface fires in-flame radiative peaks 20-115 kW/m2", "in-flame q (kW/m2)",
        "20-115", E_DEF, E_DEF, "engulfment", "range check", "prompt-supplied", "default inside the range (upper part)")
    add("emissive_power", "Butler et al. 2004: crown fires about 200 average, 290 peak", "in-flame q (kW/m2)", 200.0,
        E_CROWN, E_CROWN, "engulfment", "range check", "prompt-supplied")
    add("emissive_power", "blackbody at 1200 K", "E (kW/m2)", 118.0, E_1200K, None, "", "formula check", "standard")
    # 8. ICFME (Cohen): walls at 10 m ignited only on flame contact, 20 m never ignited, 30 m never scorched; flames ~20 m
    for d in (10.0, 20.0, 30.0):
        add("qualitative", "ICFME wall experiments reported by Cohen (2004)", "model q at %g m from 20 m crown flames" % d,
            None, straight_front_flux(d, 20.0, E=E_CROWN), E_CROWN, "infinite 20 m flame wall",
            "qualitative only", "specific 10 m flux values unverified (paper not fetched)",
            "observation: 10 m walls ignited only on contact, 20 m never ignited, 30 m never scorched")
    # 9. bounding geometries
    from wfg_flamefront.solidflame import facing_panel_view_factor, infinite_wall_view_factor
    add("bounds", "infinite wall F = 0.5 h / sqrt(h^2 + d^2) at d = 2h", "F", 0.22, float(infinite_wall_view_factor(1.0, 2.0)),
        None, "vertical receiver", "formula check", "standard")
    add("bounds", "20 m x 20 m panel at d = 4h (h = 20 m)", "F", 0.02, facing_panel_view_factor(20.0, 20.0, 80.0), None,
        "vertical receiver on the bisector", "formula check", "prompt-supplied")

    with open(HERE / "VALIDATION_TABLE.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # factor-three screen on the comparisons that have a published number
    screen = []
    for r in rows:
        if r["ratio_model_over_published"] is not None and r["group"] not in ("flux_table",):
            rr = r["ratio_model_over_published"]
            screen.append({"reference": r["reference"], "quantity": r["quantity"], "ratio": rr,
                           "within_factor_3": (1 / 3) <= rr <= 3, "kind": r["comparison_kind"]})
    out["rows"] = rows
    out["factor_three_screen"] = screen
    out["E_1200K_kw_m2"] = E_1200K
    tornado = run_tornado()
    out["tornado"] = tornado
    (HERE / "VALIDATION.json").write_text(json.dumps(out, indent=1))
    figures(rows, tornado, E_fit)
    bad = [s for s in screen if not s["within_factor_3"]]
    print("rows", len(rows), "outside factor 3:", len(bad))
    for s in bad:
        print("  ", s["ratio"], s["quantity"], "|", s["reference"][:60])
    print("measured-decay E", round(E_fit, 2), "worst factor", round(worst_fit, 3), "crown fit", round(Ec_fit, 1))


def run_tornado():
    """Peak flux at 20 m from a 375 m front at the typical Korean-panel rate 0.05 m/s (Byram flame 1.8 m)."""
    R0 = 0.05
    base = {"E": E_DEF, "R": R0, "w": 1.0, "length": 375.0, "receiver": "worst_case", "zr": 0.0, "lean": 0.0}

    def q(p):
        I = W.constants.HEAT_CONTENT_KJ_KG * p["w"] * p["R"]
        L = flame_length_from_intensity(I)
        th = math.atan(abs(p["lean"]))   # lean expressed as tan(theta)
        h = L * math.cos(th); reach = math.copysign(L * math.sin(th), p["lean"])
        return straight_front_flux(20.0, h, E=p["E"], length=p["length"], receiver=p["receiver"],
                                   receiver_z=p["zr"], lean=reach)
    q0 = q(base)
    tilt5 = 1.4 * 5.0 / math.sqrt(9.80665 * 1.8)
    sweeps = [
        ("emissive power E (kW/m2)", "E", 23.0, 200.0),
        ("rate of spread R (m/s)", "R", 0.02, 0.5),
        ("flaming consumption w (kg/m2)", "w", 0.5, 2.0),
        ("front length (m)", "length", 100.0, 1e5),
        ("wind tilt, U = 5 m/s away / toward", "lean", -tilt5, tilt5),
        ("receiver height (m)", "zr", 0.0, 1.5),
        ("receiver orientation (vertical facing / worst case)", "receiver", "vertical", "worst_case"),
        ("flame residence time (s): 5 / 60", None, None, None),
    ]
    out = []
    for label, key, lo, hi in sweeps:
        if key is None:
            out.append({"parameter": label, "low_value": 5.0, "high_value": 60.0, "q_low": q0, "q_high": q0,
                        "note": "no effect on radiation outside the flame: the emitter is the leading isochrone; residence only sets the band depth (engulfment)"})
            continue
        pl = dict(base); pl[key] = lo
        ph = dict(base); ph[key] = hi
        out.append({"parameter": label, "low_value": lo, "high_value": hi, "q_low": q(pl), "q_high": q(ph), "note": ""})
    with open(HERE / "TORNADO.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["parameter", "low_value", "high_value", "q_low", "q_high", "note"])
        w.writeheader()
        for r in out:
            w.writerow(r)
    return {"baseline_kw_m2": q0, "baseline": base, "sweeps": out}


def figures(rows, tornado, E_fit):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, str(HERE.parent))
    from figstyle import OKABE, apply_style, save
    apply_style(plt)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2))
    d = np.geomspace(1.0, 200.0, 120)
    ax = axes[0]
    for I, col in ((1000.0, OKABE[1]), (5000.0, OKABE[2]), (20000.0, OKABE[5])):
        h = flame_length_from_intensity(I)
        ax.plot(d, [straight_front_flux(x, h, E=E_DEF) for x in d], color=col, lw=1.4,
                label="I = %g kW/m (L = %.1f m)" % (I, h))
        ax.plot(d, [straight_front_flux(x, h, E=E_DEF, length=100.0) for x in d], color=col, lw=1.0, ls="--")
    ax.axhline(10.0, color="0.3", lw=0.8, ls=":")
    ax.text(1.1, 13.0, "routing peak limit 10 kW/m$^2$", fontsize=7, color="0.3")
    ax.axhline(0.703, color="0.3", lw=0.8, ls="-.")
    ax.text(1.1, 0.8, "v1 global cap 0.703 kW/m$^2$", fontsize=7, color="0.3")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("ground distance from the front (m)"); ax.set_ylabel("incident radiant flux (kW/m$^2$)")
    ax.set_ylim(0.1, 200)
    ax.set_title("(a) E = 100 kW/m$^2$; solid: infinite front, dashed: 100 m", fontsize=8, loc="left")
    ax.legend(fontsize=6.5, frameon=False, loc="lower left")
    ax = axes[1]
    dm = np.array(MORANDINI["distances_m"])
    per = np.array([straight_front_flux(x, 2.5, E=1.0, length=30.0) for x in d])
    ax.plot(d, per * E_DEF, color=OKABE[5], lw=1.4, label="model, E = 100")
    ax.plot(d, per * E_fit, color=OKABE[2], lw=1.4, label="model, E = %.0f (fit)" % E_fit)
    ax.plot(dm, MORANDINI["flux_kw_m2"], "o", color="k", ms=4, label="Morandini et al. 2006")
    pc = np.array([straight_front_flux(x, 20.0, E=1.0) for x in d])
    ax.plot(d, pc * E_CROWN, color=OKABE[6], lw=1.2, ls="--", label="model crown, E = 200, h = 20 m")
    for x, (lo, hi) in zip(PIMONT["distances_m"], PIMONT["range_kw_m2"]):
        ax.plot([x, x], [lo, hi], color=OKABE[6], lw=2.5, solid_capstyle="butt")
    ax.plot([], [], color=OKABE[6], lw=2.5, label="Pimont et al. 2014 (FIRETEC)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("ground distance from the front (m)"); ax.set_ylim(0.3, 300)
    ax.set_title("(b) shrub (2.5 m, 30 m front) and crown comparisons", fontsize=8, loc="left")
    ax.legend(fontsize=6.5, frameon=False, loc="lower left")
    fig.tight_layout()
    save(fig, HERE / "fig01_flux_vs_distance")
    plt.close(fig)
    # tornado
    sw = [s for s in tornado["sweeps"]]
    q0 = tornado["baseline_kw_m2"]
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    order = sorted(range(len(sw)), key=lambda i: abs(sw[i]["q_high"] - sw[i]["q_low"]))
    for y, i in enumerate(order):
        s = sw[i]
        lo, hi = s["q_low"], s["q_high"]
        ax.barh(y, lo - q0, left=q0, color=OKABE[1], height=0.6)
        ax.barh(y, hi - q0, left=q0, color=OKABE[5], height=0.6, alpha=0.85)
        ax.text(max(lo, hi, q0) * 1.04, y, "%.2f / %.2f" % (lo, hi), va="center", fontsize=6.5, color="0.25")

    def fmt(v):
        if isinstance(v, str):
            return v
        if abs(v) >= 1e4:
            return "infinite"
        return "%g" % round(v, 2)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(["%s [%s / %s]" % (sw[i]["parameter"], fmt(sw[i]["low_value"]), fmt(sw[i]["high_value"]))
                        if "residence" not in sw[i]["parameter"] else sw[i]["parameter"] for i in order], fontsize=6.5)
    ax.axvline(q0, color="k", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlim(0.8, 25)
    ax.set_xlabel("incident flux at 20 m from a 375 m front (kW/m$^2$); baseline %.2f" % q0)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=OKABE[1], label="first value"), Patch(color=OKABE[5], label="second value")],
              fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    save(fig, HERE / "fig05_tornado_20m")
    plt.close(fig)


if __name__ == "__main__":
    main()
