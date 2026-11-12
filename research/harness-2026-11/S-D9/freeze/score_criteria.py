"""Stage-2 criterion scorer (S-D9): writes every A1 §6.1 criterion pair.

The frozen sd9bench CLI fixes references to (persistence, dilation_best), so it
cannot write criteria 3 and 4 (vs logistic_rebuilt, vs d4_wind_recal). The frozen
library function ``sd9bench.score`` already takes any reference names. This
wrapper only fixes the arguments; it adds no scoring logic, so the scores are those
of the frozen library at its pinned sha.

Usage (run with research/harness-2026-11/S-D9 on PYTHONPATH):
  python freeze/score_criteria.py --out SCORES.json FIRE.npz ...

Each file must carry p_persistence, p_dilation_8h, p_logistic_rebuilt, p_d4_wind_recal
and the candidate columns (sd9bench entries contract, population "full_rectangle").
The output format is the CLI's: sorted keys, indent 1, no NaN, and no overwrite.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sd9bench import load, score
from sd9bench.__main__ import _clean

# A1 §6.1 criteria 1-4, by exact object name (revision 29). Fixed here.
REFERENCES = ("persistence", "dilation_8h", "logistic_rebuilt", "d4_wind_recal")
DRAWS = 10000
SEED = 20261030
POPULATION = "full_rectangle"  # A1 §4.1 rule 3


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="score_criteria")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    entries = load(args.files, None, population=POPULATION)
    missing = [r for r in REFERENCES if r not in entries.predictions]
    if missing:
        raise SystemExit(f"missing reference columns: {missing}")
    result = score(entries, references=REFERENCES, draws=DRAWS, seed=SEED)
    result["criterion_references"] = list(REFERENCES)
    args.out.write_text(json.dumps(_clean(result), indent=1, sort_keys=True, allow_nan=False) + "\n")
    print(f"wrote {args.out}: {result['entries']} entries, {result['positives']} positives, "
          f"{len(result['fires'])} fires")


if __name__ == "__main__":
    main()
