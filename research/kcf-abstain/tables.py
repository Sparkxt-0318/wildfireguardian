#!/usr/bin/env python3
"""Print the Markdown tables used in RESULTS.md from numbers.json (so no number is transcribed by hand).

    python3 tables.py numbers.json > derived/tables.md
"""
import json
import sys


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def ci(c, d=1):
    return "n/a" if not c or c[0] is None else f"{100 * c[0]:.{d}f}-{100 * c[1]:.{d}f}"


def f2(x, d=2):
    return "n/a" if x is None else f"{x:.{d}f}"


def main():
    nb = json.load(open(sys.argv[1]))
    P = print
    P("## A. Calibration, leave-one-fire-out (beta = 0.05)\n")
    P("| arm | h | n fires | hours | abstention (fire-weighted, 95% CI) | miss among kept (95% CI) | miss with no abstention (95% CI) | "
      "pooled: abstained hours / miss rate among them | AUROC (95% CI) | Delta miss (95% CI) | verdict |")
    P("|---|---|---|---|---|---|---|---|---|---|---|")
    for arm, lab in (("primary", "**primary**"), ("S1_two_sided", "S1 two-sided"), ("S2_gfs_only", "S2 GFS-only (11 fires)")):
        for h in (5, 8):
            b = nb["calibration_lofo"][arm][f"h{h}"]
            a, s = b["at_beta_0_05"], b["separation"]
            P(f"| {lab} | {h} h | {a['n_fires']} | {a['hours']} | {pct(a['abstention_rate'])} ({ci(a['abstention_ci95'])}) | "
              f"{pct(a['miss_rate_retained'])} ({ci(a['miss_rate_retained_ci95'])}) | "
              f"{pct(a['miss_rate_no_abstention'])} ({ci(a['miss_rate_no_abstention_ci95'])}) | "
              f"{a['hours_abstained']} / {pct(a['pooled_miss_rate_among_abstained'])} | "
              f"{f2(s['auroc'])} ({f2(s['auroc_ci95'][0])}-{f2(s['auroc_ci95'][1])}) | "
              f"{100 * s['delta_risk']:+.2f} pts ({100 * s['delta_risk_ci95'][0]:+.2f} to {100 * s['delta_risk_ci95'][1]:+.2f}) | "
              f"{s['verdict']} |")
    P("\nFires with every hour abstained at beta = 0.05 (left out of the miss-among-kept mean):",
      {arm: {h: nb["calibration_lofo"][arm][f"h{h}"]["at_beta_0_05"]["fires_all_hours_abstained"] for h in (5, 8)}
       for arm in nb["calibration_lofo"]})
    P("\nAbstained calibration hours by the predictor that gave the minimum tail probability (primary):",
      nb["calibration_lofo"]["primary"].get("abstained_hours_by_min_predictor"))

    P("\n## B. Risk-coverage points (primary, fire-weighted, leave-one-fire-out)\n")
    P("| beta | coverage 5 h | miss among kept 5 h | coverage 8 h | miss among kept 8 h |")
    P("|---|---|---|---|---|")
    r5 = nb["calibration_lofo"]["primary"]["h5"]["risk_coverage"]
    r8 = nb["calibration_lofo"]["primary"]["h8"]["risk_coverage"]
    for b in (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5):
        i = r5["beta"].index(b)
        P(f"| {b:.2f} | {pct(r5['coverage'][i])} | {pct(r5['risk'][i])} | {pct(r8['coverage'][i])} | {pct(r8['risk'][i])} |")
    P(f"\nNo abstention (= random abstention): 5 h {pct(r5['random_risk'])}, 8 h {pct(r8['random_risk'])}.")

    P("\n## C. Thresholds for test fires\n")
    P(nb["thresholds_for_test_fires"])

    P("\n## D. Test groups (counts; rates only where >= 10 fires)\n")
    P("| group | h | fires | scored hours | abstained | margin missed | abstained & missed | abstained & held | kept & missed | kept & held | rates |")
    P("|---|---|---|---|---|---|---|---|---|---|---|")
    for g, blk in nb["test_groups"].items():
        for h in (5, 8):
            c = blk[f"h{h}"]
            rates = ""
            if "abstention_rate" in c:
                rates = (f"abstention {pct(c['abstention_rate'])} ({ci(c['abstention_ci95'])}); miss among kept "
                         f"{pct(c['miss_rate_retained'])} ({ci(c['miss_rate_retained_ci95'])}); no abstention "
                         f"{pct(c['miss_rate_no_abstention'])} ({ci(c['miss_rate_no_abstention_ci95'])})")
            P(f"| {g} | {h} h | {c['fires']} | {c['scored_hours']} | {c['abstained']} | {c['missed']} | {c['abstained_missed']} | "
              f"{c['abstained_held']} | {c['kept_missed']} | {c['kept_held']} | {rates} |")

    P("\n## E. Every test fire (counts)\n")
    P("| fire | product | forecast | issue hours | not scored | 5 h: scored / abstained / missed / abstained & missed | "
      "8 h: scored / abstained / missed / abstained & missed |")
    P("|---|---|---|---|---|---|---|")
    for k, r in sorted(nb["test_fires"].items(), key=lambda kv: (kv[1]["country"], kv[0])):
        fire, prod = k.split("|")
        cells = []
        for h in (5, 8):
            c = r[f"h{h}"]
            ab = c["abstained_held"] + c["abstained_missed"]
            ms = c["abstained_missed"] + c["kept_missed"]
            cells.append(f"{c['scored_hours']} / {ab} / {ms} / {c['abstained_missed']}")
        ns = sum(r["not_scored"].values()) if r["not_scored"] else 0
        P(f"| {fire} | {prod} | {r['model'].upper()} | {r['issue_hours']} | {ns} | {cells[0]} | {cells[1]} |")
    P("\nNOT TESTED (no eligible issue hour):", nb["test_fires_not_tested"])

    P("\n## F. 25 March 2025, 10:00-20:00 KST (DET product; GFS as issued)\n")
    P("| KST | cycle (UTC) | gust m/s | 850 hPa m/s | min RH % | HDW | prior-3 h km | score s | abstain | lowest-p predictor | "
      "5 h reach km (R 3.75) | 5 h | 8 h reach km (R 5.03) | 8 h |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in nb["march25"]["hours_10_20_kst"]:
        def held(v, c):
            if not c:
                return "not scored"
            return "held" if v else "**missed**"
        P(f"| {r['kst_hour']:02d}:00 | {r['cycle_utc'][5:13]} | {f2(r['gust_ms'], 1)} | {f2(r['w850_ms'], 1)} | "
          f"{f2(r['rhmin_pct'], 0)} | {f2(r['hdw'], 0)} | {f2(r['prior3_km'], 2)} | {f2(r['score'], 4)} | "
          f"{'**yes**' if r['abstain'] else 'no'} | {r['min_predictor']} | {f2(r['reach5_km'], 1)} | {held(r['held5'], r['complete5'])} | "
          f"{f2(r['reach8_km'], 1)} | {held(r['held8'], r['complete8'])} |")
    P(f"\nThreshold tau = {nb['thresholds_for_test_fires']['primary']:.5f}.")
    P("\nSecondary arms on the same hours (abstain flags): S1 two-sided",
      [(r["kst_hour"], r["abstain_two_sided"]) for r in nb["march25"]["hours_10_20_kst"]],
      "; S2 GFS-only", [(r["kst_hour"], r["abstain_gfs_only"]) for r in nb["march25"]["hours_10_20_kst"]])
    P("\nAll 24 hours (00-23 KST):", [(r["kst_hour"], round(r["score"], 4) if r["score"] is not None else None,
                                        r["abstain"]) for r in nb["march25"]["hours"]])

    P("\n## G. S3 product cross-check (same fire, same issue hours, frozen R)\n")
    for h in (5, 8):
        s = nb["S3_product_crosscheck"][f"h{h}"]
        P(f"h = {h}: n = {s['n_fires']} fires; miss rate GOFER {pct(s['miss_rate_gofer'])} ({ci(s['miss_rate_gofer_ci95'])}); "
          f"Choi raster {pct(s['miss_rate_choi'])} ({ci(s['miss_rate_choi_ci95'])})")
        for r in s["per_fire"]:
            P(f"  {r['fire']}: hours {r['hours']}, miss GOFER {pct(r['miss_gofer'])}, Choi {pct(r['miss_choi'])}, "
              f"median reach GOFER {r['median_reach_gofer']:.2f} km, Choi {r['median_reach_choi']:.2f} km")

    P("\n## H. Tail (GEV on 28 per-fire maximum 5 h reaches)\n")
    t = nb["tail_evt"]
    P(json.dumps({k: t[k] for k in ("gev_mle", "p40", "T40_fires", "fires_needed_to_bound", "trust")}, indent=1))
    P("largest:", t["data"]["largest_km"], "ratio:", t["data"]["extrapolation_ratio_40_over_largest"])

    P("\n## I. Calibration hours not scored\n")
    P(nb["calibration_not_scored"])


if __name__ == "__main__":
    main()
