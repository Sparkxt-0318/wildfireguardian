"""Figures for suite evaluations (300 dpi PNG and SVG in results/figures/).

  .venv/bin/python scripts/figures_suite.py core --runs pf0 pf08 pf12      # tuning comparison
  .venv/bin/python scripts/figures_suite.py core                           # committed default run

Writes <suite>_completeness[_<runs>].png/.svg (detection completeness against ember SNR,
pooled over every clip of each run) and <suite>_case_errors.png/.svg (per case errors of
the default run against the plan goals).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from wfglink import PROJECT_ROOT
from wfglink.viz.suite_figures import case_errors_figure, completeness_figure, load_eval, pooled_completeness

LABELS = {"": "default", "pf0": "no prefilter", "pf08": "prefilter 0.8 px", "pf12": "prefilter 1.2 px",
          "pf12ref": "prefilter 1.2 px, refined streaks", "pf08k6": "prefilter 0.8 px, seed 6 sigma"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("suite")
    ap.add_argument("--runs", nargs="*", default=[""])
    a = ap.parse_args()
    figs = PROJECT_ROOT / "results" / "figures"
    curves = {}
    evals = {}
    for tag in a.runs:
        d = PROJECT_ROOT / "results" / "runs" / (f"suite_{a.suite}" + (f"_{tag}" if tag else ""))
        evals[tag] = load_eval(d)
        curves[LABELS.get(tag, tag)] = pooled_completeness(evals[tag]["clips"])
    suffix = "" if a.runs == [""] else "_" + "_".join(a.runs)
    out = completeness_figure(curves, figs / f"{a.suite}_completeness{suffix}",
                              f"Detection completeness, {a.suite} suite (all clips pooled)")
    print("wrote", *out)
    if a.runs == [""]:
        out = case_errors_figure(evals[""]["cases"], figs / f"{a.suite}_case_errors",
                                 f"{a.suite} suite: median over seeds; shaded: plan goal")
        print("wrote", *out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
