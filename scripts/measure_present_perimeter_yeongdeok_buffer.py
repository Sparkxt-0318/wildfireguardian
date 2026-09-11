#!/usr/bin/env python
"""How the 영덕 present-perimeter partition moves when the burning set is DILATED.

WFG-259, route (i).  It exists to make one sentence re-derivable and nothing else.

THE SENTENCE
------------
`docs/present_perimeter_yeongdeok.md` §5 item 5 asserted, as fact:

    Dilating the burning set to a strict superset of the 162 at 100 m moves origin
    11935180417 from `still_enters_forecast` to `saved` --- the transition the draft
    said could never happen --- and at 500 m, 15 of the 16 flip.

That sentence is the repair of a FALSE monotonicity claim and it is the most
consequential integer on the page: the headline the booth says out loud is the
**42**, and 「15 of the 16 flip」 says a router which sees only where the fire is
now, plus half a kilometre, reaches all but one of the origins the 42 credits to
the forecast.  It came from a reviewer's in-session probe that has ended.  No
artifact in this tree holds it, no `ppy_yeongdeok_` key is it, and the script
that produced the committed 26 / 16 / 2 takes no buffer argument.  CHARTER §3.3:
「A number you cannot register, you do not write.」

WHAT A DILATION IS HERE, PRE-REGISTERED BEFORE THE RUN
-------------------------------------------------------
Declared in this lap's claim commit, `031214b`, before any number existed, because
the word 「dilating」 does not pin the operation and two defensible readings
disagree.  **The dilation is in NODE space, not raster space:** a walk-graph node
is refused when its Euclidean distance in projected metres to ANY node of the base
burning set --- the committed 162 --- is at most ``d``.  A refuge inside the
dilated set is removed with the rest, exactly as at ``d = 0``.

The other reading, dilating the burning RASTER cells and re-thresholding
``prob_at``, is NOT run here and was not run afterwards to see whether it matches
the sentence better.  On a 500 m grid it would differ enormously at 100 m, where a
raster dilation rounds to zero cells and is a no-op.  One definition, declared
first; the result is published whichever way it comes out.

Widths: **0, 100 and 500 m**, and 0 / 100 / 500 are the only widths this script
knows.  100 and 500 are the two already written in the prose, so no width could be
chosen after the answer, and ``d = 0`` is the identity control.

Everything downstream of the node set is UNCHANGED from the zero-buffer run: the
same :func:`naive_route` over the filtered graph, the same ``departure_min``, the
same ``p_cut``, the same scoring against the full forecast :class:`HazardSequence`,
and the same three named outcomes reported separately for the same reason (a node
filter can cut a village off from every refuge for a reason that has nothing to do
with the fire).

WHAT IT REFUSES TO DO
---------------------
Three gates, and the run writes nothing if any of them fails:

1. the committed 414 / 42 / 2 partition must re-derive in this process, from the
   committed snapshots, with the committed parameters (the WFG-114 pattern the
   zero-buffer script already uses);
2. the ``d = 0`` arm must reproduce the committed 26 / 16 / 2 **exactly**.  If the
   identity control does not reproduce, this harness is wrong and nothing
   downstream means anything.  ``d = 0`` runs through the SAME distance code as
   every other width and is additionally asserted to refuse exactly the base set,
   so the control certifies the dilation arithmetic rather than stepping around it;
3. the 100 m node set must be a **strict superset** of the 162, which is what the
   prose itself asserts.

WHAT IT IS NOT
--------------
It is **not** WFG-033(b) and it does not pre-empt NH-027.  A buffered opponent
scored as the project's opponent of record is the author's decision.  This run
makes an existing sentence re-derivable and prices the direction of one bias; it
does not nominate a new opponent, and no width here is presented as the right one.

Run:  python scripts/measure_present_perimeter_yeongdeok_buffer.py
      python scripts/measure_present_perimeter_yeongdeok_buffer.py --out <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.evacuation import naive_route  # noqa: E402
from wildfireguardian.routing.future_front import RoadNetwork  # noqa: E402

from measure_present_perimeter_yeongdeok import (  # noqa: E402
    CANON, EXPECTED, EXPECTED_ORIGINS, NPZ, build, reproduce_partition, sha256,
)
from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402

OUT = REPO / "data/processed/present_perimeter_buffer_shape_yeongdeok_2025.json"

#: The widths, in metres. PRE-REGISTERED in the claim commit 031214b before the run.
#: 100 and 500 are the two already written in docs/present_perimeter_yeongdeok.md
#: §5 item 5; 0 is the identity control. This list is not a sweep and must not be
#: extended by a later lap to find a better one --- that is WFG-033(b) and NH-027.
BUFFERS_M = (0.0, 100.0, 500.0)

#: The committed zero-buffer outcome the d = 0 arm must reproduce exactly.
EXPECTED_ZERO = {"saved": 26, "still_enters_forecast": 16, "not_reached": 2,
                 "origin_removed_by_filter": 0}
EXPECTED_BASE_REMOVED = 162


def burning_nodes(net, hazard, p_cut: float) -> set[int]:
    """The base burning set: the committed 162, by the committed predicate."""
    return {n for n in net.graph.nodes
            if float(hazard.prob_at(*net.node_xy(n), 0.0)) >= p_cut}


def dilated_view(net, base: set[int], d: float) -> tuple[RoadNetwork, dict]:
    """Refuse every node within ``d`` metres of a base burning node.

    Euclidean distance in the network's own projected metre coordinates. At
    ``d = 0`` this is the base set itself and the view is the zero-buffer one.
    """
    nodes = list(net.graph.nodes)
    xy = np.array([net.node_xy(n) for n in nodes], dtype=float)
    base_idx = [i for i, n in enumerate(nodes) if n in base]
    bxy = xy[base_idx]
    # ⚠ NO special case for d = 0. An earlier draft short-circuited it to `set(base)`,
    # which would have made the identity control certify everything EXCEPT the distance
    # computation it exists to certify — the one line where a unit error or a wrong axis
    # would live. d = 0 goes through the same code as every other width: a base node's
    # distance to itself is 0 and is kept, and nothing else can be at distance 0 unless
    # two nodes share coordinates, which the assertion below rules out in the same run.
    # (n_nodes, n_base) is 8443 x 162 here; small enough to do flat.
    d2 = ((xy[:, None, :] - bxy[None, :, :]) ** 2).sum(axis=2)
    near = d2.min(axis=1) <= d * d
    refused = {nodes[i] for i in np.nonzero(near)[0]}
    if d <= 0.0 and refused != set(base):
        raise SystemExit(
            "the d = 0 dilation is not the identity: %d nodes refused against a base "
            "set of %d. Two walk nodes share coordinates, or the distance computation "
            "is wrong; either way no width below is trustworthy."
            % (len(refused), len(base)))
    keep = set(nodes) - refused
    sub = net.graph.subgraph(keep).copy()
    view = RoadNetwork(graph=sub, shelters=set(net.shelters) & keep)
    stats = {
        "buffer_m": float(d),
        "n_nodes_before": int(net.graph.number_of_nodes()),
        "n_nodes_removed": int(len(refused)),
        "n_nodes_after": int(sub.number_of_nodes()),
        "n_edges_after": int(sub.number_of_edges()),
        "n_shelters_before": int(len(net.shelters)),
        "n_shelters_removed": int(len(set(net.shelters) - keep)),
        "n_shelters_after": int(len(view.shelters)),
    }
    return view, stats


def score_targets(view, targets: dict, hazard, p_cut: float) -> list[dict]:
    """The same three named outcomes the zero-buffer run reports, per origin."""
    rows = []
    for n in sorted(targets):
        if n not in view.graph:
            rows.append({"origin": int(n), "bucket": targets[n]["bucket"],
                         "outcome": "origin_removed_by_filter",
                         "pp_distance_m": None})
            continue
        r = naive_route(view, n, hazard, departure_min=0.0, p_cut=p_cut,
                        objective="length_m")
        if not r.reached:
            outcome = "not_reached"
        elif r.enters_hazard:
            outcome = "still_enters_forecast"
        else:
            outcome = "saved"
        rows.append({"origin": int(n), "bucket": targets[n]["bucket"],
                     "outcome": outcome,
                     "pp_distance_m": float(r.total_distance_m)})
    return rows


def tally(rows: list[dict]) -> dict:
    keys = ("saved", "still_enters_forecast", "not_reached", "origin_removed_by_filter")
    return {k: sum(1 for r in rows if r["outcome"] == k) for k in keys}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    canon, prm, hazard, haz, extent, net, snaps = build()
    p_cut = float(prm["p_cut"])
    cand, _ign = candidate_origins(net, hazard, haz, extent, p_cut)
    print(f"[ppb] {len(cand)} candidate origins", file=sys.stderr, flush=True)
    if len(cand) != EXPECTED_ORIGINS:
        print(f"[ppb] REFUSING TO WRITE: {len(cand)} origins, expected {EXPECTED_ORIGINS}",
              file=sys.stderr)
        return 1

    counts, blind = reproduce_partition(net, cand, hazard, prm)
    print(f"[ppb] recomputed partition: {counts}", file=sys.stderr, flush=True)
    if any(counts.get(k) != v for k, v in EXPECTED.items()) or counts.get("other"):
        print(f"[ppb] REFUSING TO WRITE: partition {counts} != committed {EXPECTED}",
              file=sys.stderr)
        return 1

    base = burning_nodes(net, hazard, p_cut)
    print(f"[ppb] base burning set: {len(base)} nodes", file=sys.stderr, flush=True)
    if len(base) != EXPECTED_BASE_REMOVED:
        print(f"[ppb] REFUSING TO WRITE: base set {len(base)} != committed "
              f"{EXPECTED_BASE_REMOVED}", file=sys.stderr)
        return 1

    sensitivity, per_origin_by_buffer, refused_sets = [], {}, {}
    for d in BUFFERS_M:
        view, stats = dilated_view(net, base, d)
        refused_sets[d] = stats["n_nodes_removed"]
        rows = score_targets(view, blind, hazard, p_cut)
        out = tally(rows)
        per_origin_by_buffer[d] = {r["origin"]: r["outcome"] for r in rows}
        sensitivity.append({**stats, **out, "n_target": len(rows)})
        print(f"[ppb] buffer {d:5.0f} m: {stats['n_nodes_removed']:4d} nodes refused, "
              f"{out}", file=sys.stderr, flush=True)

    # Gate 2: the identity control must reproduce the committed zero-buffer outcome.
    zero = next(s for s in sensitivity if s["buffer_m"] == 0.0)
    got = {k: zero[k] for k in EXPECTED_ZERO}
    if got != EXPECTED_ZERO:
        print(f"[ppb] REFUSING TO WRITE: d = 0 gives {got}, committed {EXPECTED_ZERO}",
              file=sys.stderr)
        return 1

    # Gate 3: the prose's own assertion about the 100 m set.
    if refused_sets[100.0] <= EXPECTED_BASE_REMOVED:
        print(f"[ppb] REFUSING TO WRITE: the 100 m set is {refused_sets[100.0]} nodes, "
              f"not a strict superset of {EXPECTED_BASE_REMOVED}", file=sys.stderr)
        return 1

    # The transitions the page's sentence is about: out of the d = 0 still_enters
    # group, where does each origin land at each width?
    zero_map = per_origin_by_buffer[0.0]
    still_at_zero = sorted(o for o, v in zero_map.items() if v == "still_enters_forecast")

    # ⚠ The FULL cross-tabulation, d = 0 against each width, written so that any
    # sentence about WHERE an origin came from is read off the artifact rather than
    # inferred from two marginal counts that happen to be equal. WFG-259's independent
    # reviewer blocked this lap for exactly that: the first draft of §7.2 said 「all 23
    # refused at 500 m come out of the 26 that were saved」 because
    # origin_removed_by_filter (23) and n_saved_at_zero_that_stopped_being_saved (23)
    # are both 23. They overlap in 20. Marginals do not compose; this block is why.
    matrix = {}
    for d in BUFFERS_M:
        if d == 0.0:
            continue
        m = per_origin_by_buffer[d]
        cell: dict[str, dict[str, int]] = {}
        for o, before in zero_map.items():
            cell.setdefault(before, {})
            cell[before][m[o]] = cell[before].get(m[o], 0) + 1
        matrix["w%dm" % int(d)] = cell  # NOT str(d): a dotted key breaks json_path

    transitions = []
    for d in BUFFERS_M:
        if d == 0.0:
            continue
        m = per_origin_by_buffer[d]
        moved = [o for o in still_at_zero if m[o] == "saved"]
        transitions.append({
            "buffer_m": float(d),
            "n_still_entering_at_zero": len(still_at_zero),
            "n_of_those_now_saved": len(moved),
            "origins_now_saved": sorted(int(o) for o in moved),
            "n_of_those_now_not_reached": sum(
                1 for o in still_at_zero
                if m[o] in ("not_reached", "origin_removed_by_filter")),
            "n_saved_at_zero_that_stopped_being_saved": sum(
                1 for o, v in zero_map.items()
                if v == "saved" and m[o] != "saved"),
        })

    payload = {
        "_readme": (
            "WFG-259 route (i). What the 영덕 present-perimeter partition does when the "
            "burning set is DILATED in NODE space -- a walk-graph node is refused when "
            "its Euclidean distance in projected metres to any node of the committed 162 "
            "is at most d. Widths 0, 100 and 500 m, pre-registered in claim commit "
            "031214b before the run; 100 and 500 are the two already written in "
            "docs/present_perimeter_yeongdeok.md §5 item 5, so no width was chosen after "
            "the answer, and 0 is the identity control. This is NOT WFG-033(b) and does "
            "NOT nominate an opponent of record: that is NH-027 and the author's. Read "
            "docs/present_perimeter_yeongdeok.md §5 and §6 before quoting any number here."
        ),
        "written_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ"),
        "region": "yeongdeok-2025",
        "row": "WFG-259",
        "dilation_definition": (
            "NODE space, Euclidean, projected metres: node refused iff min distance to "
            "any node of the base burning set (prob_at(x, y, 0.0) >= p_cut, the committed "
            "162) is <= d. The RASTER reading -- dilate the burning cells and "
            "re-threshold -- is a different operation, was not run, and was not run "
            "afterwards to see whether it matches the prose better."
        ),
        "parameters": {k: prm[k] for k in sorted(prm)},
        "buffers_m": [float(d) for d in BUFFERS_M],
        "inputs": {
            "canonical_npz": {"path": str(NPZ.relative_to(REPO)), "sha256": sha256(NPZ)},
            "canonical_json": {"path": str(CANON.relative_to(REPO)), "sha256": sha256(CANON)},
            "snapshots": {k: {"path": str(v.relative_to(REPO)), "sha256": sha256(v)}
                          for k, v in snaps.items()},
        },
        "reproduction_gate": {
            "_readme": "The run writes nothing unless all three of these hold.",
            "partition": {"expected": {**EXPECTED, "n_origins_scanned": EXPECTED_ORIGINS},
                          "recomputed": {**{k: counts[k] for k in EXPECTED},
                                         "n_origins_scanned": len(cand)}},
            "identity_control": {"expected": EXPECTED_ZERO, "recomputed": got},
            "strict_superset_at_100m": {"base_nodes": EXPECTED_BASE_REMOVED,
                                        "at_100m": refused_sets[100.0]},
            "passed": True,
        },
        "target_set": {
            "n": len(still_at_zero) + zero["saved"] + zero["not_reached"]
            + zero["origin_removed_by_filter"],
            "definition": ("the same 44: every origin whose fire-blind route REACHES a "
                           "refuge and ENTERS the forecast hazard, committed "
                           "naive_into_FA_safe (42) plus no_safe_route (2)"),
        },
        "buffer_sensitivity": sensitivity,
        "transition_matrix_from_zero": {
            "_readme": (
                "Full cross-tabulation of the d = 0 outcome against each width's, over "
                "the same 44 origins. Read any 「where did these come from」 sentence off "
                "THIS block: the marginal counts in buffer_sensitivity and "
                "transitions_out_of_still_entering do not compose, and two of them being "
                "equal does not make them the same set of origins."),
            "cells": matrix,
        },
        "transitions_out_of_still_entering": transitions,
        "per_origin": {str(int(o)): {str(d): per_origin_by_buffer[d][o] for d in BUFFERS_M}
                       for o in sorted(zero_map)},
        "what_this_is_not": (
            "It is NOT a margin and must not be spoken as one: NH-032, NH-034 and NH-052 "
            "are open. It is NOT a proposal of a new opponent of record -- a buffered "
            "present-perimeter arm scored as THE opponent is WFG-033(b) and NH-027, and "
            "the author's. It is NOT a sweep: three widths, two of them taken verbatim "
            "from prose written before this run, and a later lap that adds a width to "
            "find a better one has crossed into WFG-033(b). It does NOT move the "
            "committed 414 / 42 / 2 or the committed 26 / 16 / 2; both re-derived here "
            "before anything was written. It is ONE fire, ONE region, ONE horizon, and "
            "the canonical field's 32.6 % envelope-coverage caveat applies unchanged. "
            "⚠ And it does NOT measure the effect of the INPUT's coarseness. Dilating "
            "grows one observation's burning set; coarseness is about a 226-component "
            "detection scatter standing in for a fire line (WFG-260). The dilation "
            "CONSTRAINS the direction of that bias -- it shows which way the outcome "
            "moves when the refused set grows -- and does not establish it."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"[ppb] wrote {args.out.relative_to(REPO)}")
    for t in transitions:
        print(f"[ppb] at {t['buffer_m']:.0f} m: {t['n_of_those_now_saved']} of "
              f"{t['n_still_entering_at_zero']} still-entering origins become saved; "
              f"{t['n_saved_at_zero_that_stopped_being_saved']} saved origins stopped "
              f"being saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
