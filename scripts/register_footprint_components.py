#!/usr/bin/env python
"""Register the footprint-geometry figures in docs/NUMBERS.json (WFG-255).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `fc_yeongdeok_` keys, and writes it back.

    python scripts/register_footprint_components.py          # upsert + report
    python scripts/register_footprint_components.py --check   # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ART_DIR = REPO / "data" / "processed" / "footprint_components"
PREFIX = "fc_yeongdeok_"

#: The caveat every one of these keys carries. The first point is the load-bearing
#: one and the one a later lap will be tempted to drop, because it is the half
#: that stops 「55」 from being quoted as a property of the fire.
BAND = (
    "THE GEOMETRY OF ONE DETECTION FIELD ON ONE FIRE, NOT A COUNT OF FIRES AND "
    "NOT A VALIDATION. Measured by scripts/measure_footprint_components.py from "
    "the committed data/processed/routing_demo_canonical.npz on the canonical "
    "181x156 / 500 m grid, at the same p_cut (0.5) and the same "
    "nearest-observation matching docs/disc_null.md scores at. Five facts travel "
    "together or none of these keys may be quoted. (1) ⚠⚠ A COMPONENT COUNT IS A "
    "READING OF A RULE, NOT A PROPERTY OF THE FIRE. The same committed mask at "
    "the headline slice is 101 pieces under 4-connectivity, 55 under "
    "8-connectivity, 11 when cells within 1 km are joined, 3 within 2 km and 1 "
    "within 4 km. No rule here is justified over the others, so the STABILITY "
    "PROFILE is the result and any single count quoted without its rule beside it "
    "is a parameter wearing a finding's clothes. ⚠ The joining rule is a pairwise "
    "Chebyshev distance threshold with NO dilation, and d=1 is exactly "
    "8-connectivity: an earlier artifact in the same lap "
    "(footprint_components_20260912T1527Z.json) dilated instead, which joins at "
    "2k+1 rather than k, and its sweep is superseded and must not be cited. (2) "
    "⚠⚠ IT SAYS NOTHING ABOUT HOW "
    "MANY FIRES THERE ARE, and 「여러 개의 산불」 or any count of fires is "
    "forbidden on every surface. FIRMS gaps fragment a single perimeter, and "
    "separate simultaneous ignitions produce a genuinely multi-piece field; this "
    "repository cannot tell those apart from the array alone, and point (1) is "
    "exactly why. (3) IT MOVES NO IoU AND PRODUCES "
    "NO MARGIN. 0.394, the 2.2044 seed-removed ratio, every dn_yeongdeok_ and "
    "rn_yeongdeok_ key, 42, 91, 9 and 27 are untouched; nothing was refit, "
    "re-acquired, re-routed or regenerated and one committed array was read. (4) "
    "obs_stack IS A FIRMS-DERIVED OBSERVATION with its own detection floor "
    "(docs/detection_floor.md) and 500 m resampling, so what is measured is the "
    "geometry of a DETECTION FIELD and not of a fire perimeter, and the "
    "fragmentation may be the record rather than the fire. (5) obs_stack IS "
    "CUMULATIVE, so a component count that is identical at four consecutive "
    "slices is a stable RECORD and not a stable fire: only 86 cells are added "
    "between 333 and 2403 minutes."
)

FORBIDDEN = [
    "the footprint is 55 separate fires",
    "the mask contains 55 fires",
    "여러 개의 산불",
    "55개의 산불",
    "the fire broke into 55 pieces",
    "the observation is 55 disconnected fires",
]


def _fig(art: dict) -> list[tuple[str, str, str, str]]:
    """(key suffix, json_path, unit, derivation), with every index resolved here."""
    obs = art["observations"]
    cores = art["forecast_cores"]
    seed_i = next(i for i, e in enumerate(obs) if e["is_seed_slice"])
    head_obs = art["headline"]["obs_time_min"]
    obs_i = next(i for i, e in enumerate(obs) if e["obs_time_min"] == head_obs)
    head_haz = art["headline"]["haz_time_min"]
    core_i = next(i for i, e in enumerate(cores) if e["haz_time_min"] == head_haz)
    o, c = f"observations.{obs_i}", f"forecast_cores.{core_i}"
    s = f"observations.{seed_i}"
    return [
        # ---- the graded observation at the headline slice ----
        # ⚠ The 「Regenerate:」 clause is read by scripts/build_artifact_manifest.py,
        # which otherwise infers the command from filename literals in scripts and
        # so resolves the SUPERSEDED artifact (named literally in the measurement
        # script's `supersedes` field) while leaving the LIVE one UNKNOWN. Stating
        # it here points the manifest at the file 29 keys actually depend on.
        ("obs_time_min", f"{o}.obs_time_min", "minutes",
         "the observation slice every headline IoU on this fire is scored "
         "against, fixed by the nearest-observation rule and not chosen here. "
         "Regenerate: python scripts/measure_footprint_components.py"),
        ("obs_cells", f"{o}.n_cells", "cells",
         "cells in that observed footprint"),
        ("obs_components_8conn", f"{o}.n_components_8conn", "count",
         "pieces under 8-connectivity. ⚠ Quote it only beside obs_components_4conn "
         "and the link sweep; alone it is a parameter"),
        ("obs_components_4conn", f"{o}.n_components_4conn", "count",
         "pieces under 4-connectivity — nearly double the 8-connected count on "
         "the identical mask, which is the whole argument of caveat (1)"),
        ("obs_components_link_500m", f"{o}.link_sweep.1", "count",
         "pieces when cells within 500 m (Chebyshev d=1) are joined. ⚠ This IS "
         "8-connectivity and equals obs_components_8conn by construction; the "
         "script refuses to write a file in which they disagree. It is registered "
         "so the sweep starts at a "
         "rule the reader already has"),
        ("obs_components_link_1km", f"{o}.link_sweep.2", "count",
         "pieces when cells within 1.0 km (d=2) are joined"),
        ("obs_components_link_2km", f"{o}.link_sweep.4", "count",
         "pieces when cells within 2.0 km (d=4) are joined"),
        ("obs_components_link_4km", f"{o}.link_sweep.8", "count",
         "pieces when cells within 4.0 km (d=8) are joined — the first distance "
         "in the sweep at which this mask becomes a single object"),
        ("obs_largest_cells", f"{o}.largest_component_cells", "cells",
         "the dominant connected piece of the graded observation"),
        ("obs_second_cells", f"{o}.second_component_cells", "cells",
         "the second-largest piece, an order of magnitude below the first"),
        ("obs_largest_share", f"{o}.largest_component_share", "ratio",
         "the dominant piece's share of the observed cells — the number that "
         "says 「one structure plus scatter」 rather than 「55 equal pieces」"),
        ("obs_cells_outside_largest", f"{o}.cells_outside_largest", "cells",
         "observed cells that are NOT in the dominant piece"),
        ("obs_singletons_8conn", f"{o}.singleton_components_8conn", "count",
         "one-cell pieces under 8-connectivity, which is what most of the 55 are"),
        ("obs_span_long_km", f"{o}.span_km.1", "km",
         "the long side of the observation's bounding box, cell footprints "
         "included ((max-min+1)*cell)"),
        ("obs_span_short_km", f"{o}.span_km.0", "km",
         "the short side of the same box, same convention"),
        ("obs_centre_span_long_km", f"{o}.centre_span_km.1", "km",
         "the same long side measured between extreme cell CENTRES "
         "((max-min)*cell). It is exactly one cell less than obs_span_long_km, "
         "and both are registered because the WFG-255 row quoted this convention "
         "and a lap reading only the other would think the row was wrong"),
        ("obs_largest_span_long_km", f"{o}.largest_component_span_km.1", "km",
         "the long side of the DOMINANT PIECE's own box — the measurement that "
         "earns the 「reach」 reading in docs/disc_null.md, because the piece "
         "carrying 70 per cent of the mask is itself elongated"),
        # ---- the t=0 seed, which is the centre every null is anchored at ----
        ("seed_cells", f"{s}.n_cells", "cells",
         "cells in the t=0 seed the disc and rotation nulls take their centre from"),
        ("seed_components_8conn", f"{s}.n_components_8conn", "count",
         "pieces in that seed under 8-connectivity. ⚠ It is 226 pieces in 249 "
         "cells: the seed is very nearly pure scatter, which is what "
         "docs/oracle_gap.md §4's centroid is the centre of mass OF"),
        ("seed_largest_cells", f"{s}.largest_component_cells", "cells",
         "the largest piece in the seed — three cells, so no structure at all"),
        # ---- the forecast core it is graded against ----
        ("core_time_min", f"{c}.haz_time_min", "minutes",
         "the forward-simulation slice of the headline comparison"),
        ("core_cells", f"{c}.n_cells", "cells",
         "cells in that core"),
        ("core_components_8conn", f"{c}.n_components_8conn", "count",
         "pieces in the model's own core under 8-connectivity. ⚠ The model's "
         "output is fragmented too, which is why this is not a defect found in "
         "the observation alone"),
        ("core_largest_share", f"{c}.largest_component_share", "ratio",
         "the model core's dominant-piece share"),
        # ---- how the two meet ----
        ("intersection_cells", "headline.intersection_cells", "cells",
         "cells in both the core and the graded observation"),
        ("intersection_share_in_largest", "headline.intersection_share_in_largest_obs_component",
         "ratio",
         "the share of that overlap lying inside the observation's dominant "
         "piece. ⚠ It is BELOW the dominant piece's share of the observation, so "
         "the overlap is not concentrated in the one blob"),
        ("obs_components_touched", "headline.obs_components_touched_by_core", "count",
         "how many of the observed pieces the model's core intersects at all"),
        # ---- what the cumulative stack hides ----
        ("last_slice_cells", "cumulative.last_slice_cells", "cells",
         "cells in the LAST observation slice, more than a day after the graded "
         "one"),
        ("cells_added_graded_to_last", "cumulative.cells_added_graded_to_last",
         "cells",
         "cells the record adds between the graded slice and the last one. ⚠ This "
         "is caveat (5) as arithmetic: obs_stack is cumulative, so a component "
         "count identical at four consecutive slices is the RECORD standing "
         "still, not the fire"),
    ]


def build_entries(art: dict, artifact_rel: str, head: str, config_hash: str) -> dict:
    out: dict[str, dict] = {}
    for suffix, path, unit, why in _fig(art):
        out[PREFIX + suffix] = {
            "value": None,  # filled below from the artifact itself
            "unit": unit,
            # The same arm as dn_ and rn_: these keys measure the geometry of the
            # very fields those keys compare, at the same slices under the same
            # p_cut, so isolating them separately would let a lap move one
            # without seeing the other.
            "arm": "field_comparison",
            "git_commit": head,
            "config_hash": config_hash,
            "source": artifact_rel,
            "json_path": path,
            "derivation": why,
            "caveat": BAND,
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": artifact_rel,
                                         "json_path": path}}},
        }
    node_cache = art
    for key, entry in out.items():
        node = node_cache
        for part in entry["json_path"].split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
        entry["value"] = node
    return out


def newest_artifact() -> Path:
    files = sorted(ART_DIR.glob("footprint_components_*.json"))
    if not files:
        raise SystemExit(
            "no footprint-component artifact under "
            f"{ART_DIR.relative_to(REPO).as_posix()}/; run "
            "scripts/measure_footprint_components.py first")
    return files[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--artifact", type=Path, default=None)
    args = ap.parse_args()

    art_path = args.artifact or newest_artifact()
    artifact_rel = art_path.resolve().relative_to(REPO).as_posix()
    art = json.loads(art_path.read_text(encoding="utf-8"))
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(art, artifact_rel, head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"]
             or cur[k].get("caveat") != e.get("caveat")
             or cur[k].get("source") != e.get("source")]
    if args.check:
        if stale:
            print("STALE footprint-component registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} footprint-component entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} footprint-component entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
