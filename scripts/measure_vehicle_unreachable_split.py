#!/usr/bin/env python
"""WFG-264 — what does the 439 series actually establish when it says a home is
「차량 도달 불가」?

The A4 dispatch sheet the booth hands a judge prints, for every home in the
``no_surviving_vehicle_ingress`` class::

    예산 내 차량 진입로가 화재로 차단됨(우회 포함)

which asserts three things at once: that the vehicle access road is blocked, that
FIRE is what blocked it, and that a budget was spent on detours before the
conclusion was drawn. This script measures what the committed record can settle
about those assertions. It re-runs nothing, refits nothing, and moves no
committed number.

The code condition, read off the return sites
---------------------------------------------
``rescue.build_dispatch_list`` puts a home in the unreachable set iff
``rescue.rescuer_reachable`` returns False, and that function is a loop over
depots which keeps a depot only when ``rt.reached and not rt.enters_hazard``.
``rt`` is ``rescuer_route`` = ``evacuation.future_aware_route`` called with the
DEPOT as ``start`` and the home as the only shelter. So three distinct return
sites collapse into the one sheet sentence:

(A) ``evacuation.py`` pre-search refusal — the START node (here the depot, not
    the home) is already at or above the vehicle cutoff at dispatch time, and
    the function returns before a single edge is relaxed. No detour was tried
    and no budget was consumed.
(B) ``evacuation.py`` exhausted Dijkstra — which merges three different worlds:
    the responder time budget ran out, the ceil-rounded hazard gate closed every
    edge, or the drive graph has no depot -> home path at all.
(C) ``rescue.py`` route found and reached, but ``_evaluate_path`` set
    ``enters_hazard``.

Only the middle of (B) is 「예산 내 … 화재로 차단됨(우회 포함)」.

What the committed artifacts CAN settle, and how
------------------------------------------------
``build_dispatch_list`` stores, for context only, ``best_closing_window_min`` —
``assess_ingress``'s best direct-corridor closing window (corridor survival time
minus responder ETA) over all depots, with an infinity mapped to ``null``.

1. A ``null`` window is an INFINITY of either sign, and both signs are real
   worlds: ``-inf`` is ``ingress_corridor``'s ``NetworkXNoPath`` branch (no depot
   has any drive path to the home at all) and ``+inf`` is a corridor the fire
   never crosses (infinite survival time, which also makes the corridor
   ``reachable``). ⚠ **An earlier draft of this script claimed null meant the
   first alone. That was false and a constructed reproduction caught it**
   (``tests/test_vehicle_unreachable_split.py``, the over-budget case: a road
   exists, no fire anywhere, and the window serialises as null). So the count
   below is deliberately named for what it measures — how many homes have NO
   finite best window — and a zero there rules out **both** worlds at once.
2. ``reachable`` is ``survival >= eta + safety_margin``, and ``assess_ingress``
   returns a feasible corridor when one exists and the MAXIMUM window otherwise.
   So a **finite** stored window at or above the run's own recorded
   ``responder_safety_margin_min`` can only have come from the FEASIBLE branch:
   for that home the direct corridor screening itself says a vehicle can get in
   with the full margin, while the survival-aware router — the decider — says
   there is no route. The two tests are different by design; what the pair
   establishes is that 「화재로 차단됨」 is not what this artifact's own corridor
   assessment recorded about that home.
3. A finite window at or above zero is the weaker version of 2: the corridor's
   earliest cutoff-crossing is at or after the moment the responder would
   arrive, and only the safety margin puts it out of reach.

Identity controls, required to pass before any count is believed
----------------------------------------------------------------
For each artifact: ``len(unreachable_homes)`` re-derives against BOTH
``four_way_counts["no_surviving_vehicle_ingress"]`` and
``responder_exposure["n_unreachable"]``, ``four_way_sums_to_n`` is true, and the
safety margin used as the threshold is READ from the artifact's own
``provenance.assumed`` rather than typed here. A margin this script had to
supply would be a parameter of the measurement instead of a property of the run.

Deliberately clock-free, network-free and DEM-free: it opens two committed JSON
files and nothing else.

Output: ``data/processed/vehicle_unreachable_split/split_<stamp>.json``.
Registered additively by ``scripts/register_vehicle_unreachable_split.py``.
Stated in ``docs/routing_limitations.md`` §7.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "processed" / "vehicle_unreachable_split"

#: (label, committed artifact) — the two fields the 439 series committed.
ARMS: tuple[tuple[str, str], ...] = (
    ("committed_dispatch_slice", "data/processed/rescue_routing.json"),
    ("full_coverage_rerun", "data/processed/rescue_routing_full.json"),
)


class IdentityError(RuntimeError):
    """An identity control did not reproduce; nothing downstream is believable."""


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def measure_arm(label: str, rel: str) -> dict:
    """One committed artifact -> the split, with its identity controls."""
    art = json.loads((REPO / rel).read_text(encoding="utf-8"))
    homes = art["unreachable_homes"]
    n = len(homes)

    n_four_way = art["four_way_counts"]["no_surviving_vehicle_ingress"]
    n_resp = art["responder_exposure"]["n_unreachable"]
    if not (n == n_four_way == n_resp):
        raise IdentityError(
            f"{rel}: unreachable_homes has {n} entries, four_way_counts says "
            f"{n_four_way}, responder_exposure says {n_resp}")
    if not art.get("four_way_sums_to_n"):
        raise IdentityError(f"{rel}: four_way_sums_to_n is not true")

    margin = art["provenance"]["assumed"]["responder_safety_margin_min"]
    if not isinstance(margin, (int, float)):
        raise IdentityError(f"{rel}: no responder_safety_margin_min in provenance")

    windows = [h.get("best_closing_window_min") for h in homes]
    finite = [w for w in windows if w is not None]
    return {
        "label": label,
        "source_file": rel,
        "identity_controls": {
            "n_unreachable": n,
            "n_origins": art["n_origins"],
            "four_way_counts_agrees": True,
            "responder_exposure_agrees": True,
            "four_way_sums_to_n": True,
            "responder_safety_margin_min_read_from_artifact": float(margin),
        },
        "n_unreachable": n,
        "n_no_finite_best_closing_window": sum(1 for w in windows if w is None),
        "n_corridor_survives_past_responder_eta": sum(1 for w in finite if w >= 0.0),
        "n_corridor_reachable_by_the_screening_test":
            sum(1 for w in finite if w >= float(margin)),
        "min_best_closing_window_min": (min(finite) if finite else None),
        "max_best_closing_window_min": (max(finite) if finite else None),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    arms = [measure_arm(label, rel) for label, rel in ARMS]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "title": "WFG-264 — what the 439-series unreachable class establishes",
        "generated_utc": stamp,
        "git_commit": _git(),
        "row": "WFG-264",
        "method": (
            "Reads two committed artifacts and nothing else. No scan re-run, no "
            "refit, no committed count moved. best_closing_window_min is "
            "assess_ingress's best DIRECT-corridor closing window over all depots, "
            "stored for context by build_dispatch_list; the class itself is decided "
            "by rescuer_reachable, which is a different and more conservative test. "
            "The three counts below are properties of the context field, read "
            "against the run's own recorded safety margin."),
        "what_this_is_not": (
            "NOT a claim that any home is misclassified. rescuer_reachable is the "
            "decider by design and this measurement does not second-guess it. NOT a "
            "count of which of the three return sites (A) (B) (C) each home came "
            "from: the committed artifacts do not record that, and recovering it "
            "would mean re-running the scan. What it establishes is narrower and "
            "sufficient: the sheet sentence asserts fire as the cause and detours as "
            "tried, and for the homes counted here the artifact's own corridor "
            "assessment recorded a corridor that fire had not yet closed at the "
            "responder's arrival. ⚠ A null best window is an infinity of EITHER "
            "sign -- no drive path at all, or a corridor the fire never crosses "
            "-- so the first count rules out both worlds together and neither "
            "separately."),
        "arms": arms,
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"split_{stamp}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    for a in arms:
        print(f"{a['label']:24s} n={a['n_unreachable']:3d}  "
              f"no-finite-window={a['n_no_finite_best_closing_window']:3d}  "
              f"corridor>=ETA={a['n_corridor_survives_past_responder_eta']:3d}  "
              f"corridor-reachable={a['n_corridor_reachable_by_the_screening_test']:3d}")
    print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
