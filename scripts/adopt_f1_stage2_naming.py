#!/usr/bin/env python
"""Adopt Stage 2's naming for an F1 run that was produced by the pre-rename script.

The 2026-09-14 laptop run of F1 happened against the PREVIOUS revision of
``scripts/run_forecast_track_f1.py`` — a ``git pull`` had aborted on divergent branches
and the failure scrolled past above the run. Two things differ from the current script,
and only two:

  * the entrant bundle went to ``entrants/e4a_wfg_frozen_t0`` instead of
    ``entrants/f1_wfg_frozen_t0`` (Stage 2's name, the author's choice of 2026-09-14);
  * the E3-reuse check did not exist yet, so nothing verified that the model F1 simulated
    with is the one E3 was fitted with.

The expensive outputs — ``routing_demo_f1_frozen_t0.npz`` and ``forecast_track_f1.json`` —
carry the SAME filenames in both revisions, and the JSON already records the held-out AUC
at full precision. So the run does not need repeating: this script VERIFIES the reuse from
what was recorded, re-emits the entrant bundle under the Stage 2 name, and renders
``docs/forecast_track.md`` §4 from the artifact rather than from anything retyped.

⚠ It verifies before it renames. If the recorded AUC does not match E3's to full precision
the run was NOT E3's model, and no amount of renaming would make the leaderboard row mean
what Stage 2 says it means — so it stops instead.

The superseded ``e4a_*`` bundle is left on disk (CHARTER §3 rule 7) and named in the JSON.

    python scripts/adopt_f1_stage2_naming.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUTDIR = REPO / "data/processed/forecast_track"
OUT = OUTDIR / "forecast_track_f1.json"
OUT_NPZ = OUTDIR / "routing_demo_f1_frozen_t0.npz"
OLD_ENTRANT = REPO / "data/processed/benchmark/entrants/e4a_wfg_frozen_t0"
NEW_ENTRANT = REPO / "data/processed/benchmark/entrants/f1_wfg_frozen_t0"
LEAKFREE_JSON = REPO / "data/processed/leakfree_yeongdeok_fold.json"
DOC = REPO / "docs/forecast_track.md"
FIRE = "yeongdeok_2025"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    for q in (OUT, OUT_NPZ, LEAKFREE_JSON):
        if not q.exists():
            print(f"STOP: {q.relative_to(REPO)} is missing. Run F1 on the machine that holds "
                  "the raw bundle first.", file=sys.stderr)
            return 2

    doc = json.loads(OUT.read_text(encoding="utf-8"))
    e3 = json.loads(LEAKFREE_JSON.read_text(encoding="utf-8"))["held_out_yeongdeok_auc"]

    got = doc["field"].get("held_out_yeongdeok_auc_same_fit")
    want = float(e3["leakfree_fold"])
    if got is None:
        print("STOP: the artifact records no held-out AUC, so the reuse cannot be verified "
              "from it. Re-run F1 with the current script.", file=sys.stderr)
        return 2
    if abs(float(got) - want) > 1e-12:
        print(f"STOP: this run did NOT use E3's model.\n  recorded  {float(got):.16f}\n"
              f"  E3        {want:.16f}\n  Stage 2 requires F1 to reuse E3's fit; renaming a "
              "different model would make F1's leaderboard row a comparison of two things at "
              "once.", file=sys.stderr)
        return 3
    print(f"[verify] held-out 영덕 AUC {float(got):.16f} == E3 {want:.16f}  -> F1 is E3's model")

    if sha(OUT_NPZ) != doc["field"]["npz_sha256"]:
        print("STOP: the npz on disk does not match the digest the artifact recorded.",
              file=sys.stderr)
        return 3
    print(f"[verify] npz digest matches the artifact  ({doc['field']['npz_sha256'][:16]}...)")

    # ⚠ REBUILT, not copied. The superseded e4a_ bundle was written with the FIELD npz's key
    # names (haz_stack / haz_times); scripts/benchmark/score_kspread.py reads stack / times_min
    # / grid_extent, as the committed e0_persistence and e3_wfg_canonical bundles do. Copying
    # the old file forward is what made the first score run die with
    # KeyError: 'stack is not a file in the archive'. The field npz is the source of truth
    # either way, so this reads it and writes the entrant's own contract.
    import numpy as np
    NEW_ENTRANT.mkdir(parents=True, exist_ok=True)
    ev_dst = NEW_ENTRANT / f"{FIRE}.npz"
    z = np.load(OUT_NPZ)
    missing = [k for k in ("grid_extent", "haz_stack", "haz_times") if k not in z.files]
    if missing:
        print(f"STOP: {OUT_NPZ.relative_to(REPO)} lacks {missing}; it holds {sorted(z.files)}.",
              file=sys.stderr)
        return 3
    np.savez_compressed(ev_dst, grid_extent=z["grid_extent"], times_min=z["haz_times"],
                        stack=z["haz_stack"])
    check = np.load(ev_dst)
    if sorted(check.files) != ["grid_extent", "stack", "times_min"]:
        print(f"STOP: wrote {sorted(check.files)}, not the scorer's three keys.", file=sys.stderr)
        return 3
    print(f"[write ] {ev_dst.relative_to(REPO)}  keys {sorted(check.files)}")

    ent = {
        "id": "f1_wfg_frozen_t0", "protocol_entrant": "F1",
        "name": "F1 WFG frozen weather at T0 (E3's fold, reproduced and checked)",
        "protocol_version": "v0.1", "track": "forecast",
        "resolution_m": float(doc["field"]["parameters"]["cell_size_m"]),
        "inputs_used": ["FIRMS cumulative detections at T0", "SRTM/5 m DEM", "land cover",
                        "ERA5 at the last time AT OR BEFORE T0, held flat for every step"],
        "track_reason": "No input is an observation after T0. ⚠ A FLOOR, not an estimate of "
                        "what a forecast buys: it is the worst honest assumption (no forecast "
                        "at all) — docs/forecast_track.md §3.",
        "what_it_is": "E3's own fitted model (held-out 영덕 AUC verified equal to "
                      "data/processed/leakfree_yeongdeok_fold.json to full precision), driven "
                      "by frozen T0 weather instead of post-T0 reanalysis",
        "provenance": {"source": str(OUT_NPZ.relative_to(REPO)), "array": "haz_stack",
                       "source_sha256": doc["field"]["npz_sha256"],
                       "fold_artifact": str(OUT.relative_to(REPO)),
                       "fitted_by": "scripts/run_forecast_track_f1.py",
                       "adopted_by": "scripts/adopt_f1_stage2_naming.py",
                       "superseded_bundle": str(OLD_ENTRANT.relative_to(REPO)) +
                                            " (pre-rename run, kept under CHARTER §3 rule 7)"},
        "events": {FIRE: {"npz": str(ev_dst.relative_to(REPO)), "sha256": sha(ev_dst)}},
        "generated_utc": doc["generated_utc"], "git_commit": doc["git_commit"],
    }
    (NEW_ENTRANT / "entrant.json").write_text(
        json.dumps(ent, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    doc["entrant"] = "F1"
    doc["naming"] = ("Stage 2 (docs/auto/briefs/K_SPREAD_STAGE2.md), author's choice "
                     "2026-09-14. This run was produced by the pre-rename script after a "
                     "git pull aborted on divergent branches; the field and the routing are "
                     "unaffected, only the entrant name was, and the E3 reuse was verified "
                     "after the fact from the AUC this artifact recorded.")
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[write ] {(NEW_ENTRANT / 'entrant.json').relative_to(REPO)}")
    print(f"\nScore it:\n  python scripts/benchmark/score_kspread.py --entrant "
          f"{NEW_ENTRANT.relative_to(REPO)}")
    print(f"\nThen render §4:\n  python scripts/render_forecast_track_results.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
