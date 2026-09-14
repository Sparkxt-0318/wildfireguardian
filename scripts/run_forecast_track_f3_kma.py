#!/usr/bin/env python
"""F3 — the KMA-forecast field (K-SPREAD Stage 2; docs/auto/briefs/K_SPREAD_STAGE2.md).

⚠ NAMED F3, NOT F2. docs/auto/briefs/K_SPREAD_STAGE2.md is the canonical naming: its F2 is
the observed mountain-station field (a hindcast with the right wind) and F3 is this one, the
only true forecast-track entrant. An earlier draft of this script called it F2, after the
HINDCAST_CORRECTION brief; the author chose Stage 2's scheme on 2026-09-14.

The same model as F1, on the same canonical 영덕 canvas, but with
every step driven by the KMA 동네예보 **issued before T0** (초단기 where it covers, else
단기) instead of ERA5 reanalysis. That is what makes the entrant forecast-track: no input
is an observation after T0.

⚠ THIS SCRIPT REFUSES TO RUN WITHOUT THE ARCHIVED FORECAST, AND THAT IS ITS POINT.
The rule in ``docs/forecast_track.md`` §2 says F2 needs the files from 기상자료개방포털
under ``data/raw/kma_forecast/`` with a ``MANIFEST.json`` beside them. If they are absent
the honest outcome is 「not run」, not a substitute. In particular it NEVER falls back to
ERA5: reanalysis is the very thing that made the committed field a hindcast, so an F3 that
quietly used it would reproduce the defect this whole correction exists to fix, while
wearing the word 「forecast」 in its filename.

    python scripts/run_forecast_track_f3_kma.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KMA_DIR = REPO / "data/raw/kma_forecast"
MANIFEST = KMA_DIR / "MANIFEST.json"
DOC = "docs/forecast_track.md"

#: What the manifest has to describe before a run can be called forecast-track. Checked
#: rather than assumed, because 「the directory exists」 is not the same claim as 「the
#: forecast that covers this fire, issued before its ignition, is here」.
REQUIRED_KEYS = ("issued_utc", "event", "files", "product")


def refuse(why: str, detail: str = "") -> int:
    print("F3 (KMA forecast) DID NOT RUN.", file=sys.stderr)
    print(f"  reason: {why}", file=sys.stderr)
    if detail:
        print(f"  {detail}", file=sys.stderr)
    print(file=sys.stderr)
    print(f"  F3 needs the archived 동네예보 issued BEFORE T0, under {KMA_DIR.relative_to(REPO)}/", file=sys.stderr)
    print(f"  with a MANIFEST.json naming {', '.join(REQUIRED_KEYS)}.", file=sys.stderr)
    print("  Acquire it from 기상자료개방포털 (data.kma.go.kr); data/raw/** is git-ignored,", file=sys.stderr)
    print("  so this is the author's laptop's job and no cloud lap can do it.", file=sys.stderr)
    print(file=sys.stderr)
    print("  ⚠ There is deliberately NO fallback. Driving these steps with ERA5 reanalysis", file=sys.stderr)
    print("    is what made the committed field a hindcast in the first place", file=sys.stderr)
    print(f"    ({DOC} §1); an F3 that did that would be a hindcast wearing the word", file=sys.stderr)
    print("    「forecast」 in its filename. Not running is the honest outcome.", file=sys.stderr)
    return 3


def main() -> int:
    if not KMA_DIR.exists():
        return refuse(f"{KMA_DIR.relative_to(REPO)}/ does not exist.")
    if not MANIFEST.exists():
        present = sorted(p.name for p in KMA_DIR.iterdir())[:10]
        return refuse(
            f"{MANIFEST.relative_to(REPO)} does not exist.",
            f"the directory holds: {present if present else '(empty)'}",
        )
    try:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return refuse(f"{MANIFEST.relative_to(REPO)} is not readable JSON.", f"{type(exc).__name__}: {exc}")
    missing = [k for k in REQUIRED_KEYS if k not in man]
    if missing:
        return refuse(
            f"{MANIFEST.relative_to(REPO)} is missing required key(s): {', '.join(missing)}.",
            f"it holds: {sorted(man)}",
        )

    # ------------------------------------------------------------------ #
    # Past this point the archive is present. The build itself is NOT written
    # here, and pretending otherwise would be worse than this refusal: the
    # mapping from 동네예보 to the model's weather features (10 m wind -> u/v,
    # T, RH -> VPD, precipitation) has to be written against the real files'
    # actual schema -- category codes, grid (nx, ny), issue/lead structure --
    # which nobody in this repository has opened yet. A mapping written blind
    # would be a guess with a runnable shape, which is the most expensive kind
    # of wrong thing to commit.
    # ------------------------------------------------------------------ #
    print(f"[F3] manifest found: {MANIFEST.relative_to(REPO)}")
    print(f"[F3]   product={man.get('product')!r} issued_utc={man.get('issued_utc')!r} event={man.get('event')!r}")
    print(f"[F3]   files: {len(man.get('files', []))}")
    print()
    print("[F3] STOPPING: the archive is here, but the 동네예보 -> weather-feature mapping is", file=sys.stderr)
    print("     not implemented. It must be written against these files' real schema", file=sys.stderr)
    print("     (category codes, nx/ny grid, issue and lead-time structure) and verified", file=sys.stderr)
    print(f"     that every frame used was ISSUED BEFORE T0 -- {DOC} §2.", file=sys.stderr)
    print("     Write it in the session that can open the files; do not guess it.", file=sys.stderr)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
