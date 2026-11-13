"""NOT_EVALUATED_LABEL_RULE.md: B0 per (region, start, horizon, variant) from Leo's build.main (stopped inside add_b0,
no packet written), start-point inside / touches split, and the split re-tabulation of the HEADLINE /2 run.
    python3 -m deadline_field.not_evaluated_split --leo LEO --runs DIR_NR2 --nr1-summary J1 --nr2-summary J2 --out OUT"""
from __future__ import annotations
import argparse, json, os, sys, glob, copy
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.explain_deadlines.roads import RoadGraph  # noqa: E402
from tools.explain_deadlines.geometry import clip_closed  # noqa: E402

STATE = "start point on ground the model shows as burned before this start time: not evaluated"
LINE = ("Under the no-re-entry rule nothing is computed from this point. This says nothing about whether people are "
        "there or whether roads are passable.")
FLAG = "depends on the no-re-entry rule"
CAUSE = "every road exit crosses ground the model shows as already burned"
VARS = ("kriged_mean", "firms_early", "envelope", "envelope_burnset")


class _Stop(Exception):
    pass


def b0_masks(leo: Path, cmd: list):
    """Run Leo's build.main with the manifest /2 command; capture B0 per member inside add_b0; stop before writing."""
    fd = leo / "research/harness-2026-11/F-DYN"
    sys.path.insert(0, str(fd))
    import importlib
    build = importlib.import_module("fdyn.build")
    cap = {}
    orig = build.add_b0

    def wrap(p, arrival, export_burned, present_fire, start_h):
        before = p["times"].copy()
        added = orig(p, arrival, export_burned, present_fire, start_h)
        after = p["times"]
        cap["b0"] = [(before[k] != 0.0) & (after[k] == 0.0) for k in range(after.shape[0])]
        cap["added"] = added
        raise _Stop()
    build.add_b0 = wrap
    argv = list(cmd[2:])
    o = argv.index("--out"); argv[o + 1] = os.path.join(os.environ.get("NE_SCRATCH", "/tmp"), "ne_never_written", "pk")
    cwd = os.getcwd(); os.chdir(leo)
    try:
        build.main(argv)
    except _Stop:
        pass
    finally:
        os.chdir(cwd); build.add_b0 = orig
    if "b0" not in cap:
        raise SystemExit("add_b0 not reached")
    return cap["b0"], cap["added"]


def router_b0(grid, masks, aff):
    a, _b, c, _d, e, f = aff
    sets = []
    for m in masks:
        s = set()
        for cell in range(grid.W * grid.H):
            x, y = (float(v) for v in grid.centre(cell))
            col, row = int(np.floor((x - c) / a)), int(np.floor((y - f) / e))
            if 0 <= row < m.shape[0] and 0 <= col < m.shape[1] and m[row, col]:
                s.add(cell)
        sets.append(s)
    return sets


def point_class(g, grid, node, B):
    p = g.xy(node)
    if grid.cell_of(*p) in B:
        return "inside"
    for c in grid.cells_touching_box(p[0], p[0], p[1], p[1]):
        if c in B and clip_closed(p, p, grid.rect(c)) is not None:
            return "touches"
    return None


def main():
    ap = argparse.ArgumentParser()
    for k in ("leo", "runs", "nr1-summary", "nr2-summary", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    leo = Path(a.leo); fd = leo / "research/harness-2026-11/F-DYN"
    man = json.loads((fd / "MANIFEST_v3_7.json").read_text())
    ent = {(e["region"], e["start"], e["horizon_h"], e["variant"]): e for e in man["entries"]
           if e["start_kind"] == "recorded" and e["transform"] == "no_reentry/2"}
    s1 = {(p["region"], p["start"], p["horizon_h"], p["origin"]): p for p in json.load(open(a.nr1_summary))["places"]}
    rows, checks, graphs = [], [], {}
    for f in sorted(glob.glob(os.path.join(a.runs, "*.json"))):
        x = json.load(open(f)); n = os.path.basename(f)[:-5]; reg, rest = n.split("__")
        st, h, var = rest[:16], int(rest[18]), rest[20:]
        e = ent[(reg, st, h, var)]
        masks, added = b0_masks(leo, e["cmd"])
        gp = e["cmd"][e["cmd"].index("--graph") + 1]
        if gp not in graphs:
            graphs[gp] = RoadGraph(json.loads((leo / gp).read_text()))
        g = graphs[gp]; grid = g.grid
        with np.load(leo / "data/routing/latest_inputs_try02/exports/KFS_01" / ("FORECAST_%s.npz" % st)) as z:
            aff = tuple(float(v) for v in z["affine_transform"])
        rb = router_b0(grid, masks, aff)
        U = set().union(*rb)
        cnt_ok = [int(m.sum()) == ad["b0_total"] for m, ad in zip(masks, added)]
        checks.append({"region": reg, "start": st, "horizon_h": h, "variant": var, "b0_pixels_per_member": [int(m.sum()) for m in masks],
                       "plan_meta_b0_total": [ad["b0_total"] for ad in added], "b0_count_check": all(cnt_ok),
                       "router_cells_union": len(U), "members_agree": all(s == rb[0] for s in rb)})
        for oid, v in x["origins_detail"].items():
            pc = point_class(g, grid, v["entry_node"], U)
            nr = (v.get("no_route") or {}).get("split")
            p1 = s1[(reg, st, h, oid)]
            v1 = p1["nr_cert"]["per_variant"].get(var) if var != "envelope_burnset" else {"leave_by_s": p1.get("static_final_footprint_row", {}).get("nr_cert")}
            had1 = isinstance(v1, dict) and v1.get("leave_by_s") is not None
            if pc:
                cls = "not_evaluated"
            elif v["leave_by_nr_cert"] is not None:
                cls = "route"
            elif had1:
                cls = "lost_route_depends_on_no_reentry"
            else:
                cls = "no_route_" + str(nr)
            rows.append({"region": reg, "start": st, "horizon_h": h, "variant": var, "origin": oid, "type": v.get("type"),
                         "point": pc, "class": cls, "no_route_split_nr2": nr, "route_on_nr1": had1,
                         "leave_by_nr_cert": v["leave_by_nr_cert"], "leave_by_nr_router": v["leave_by_nr_router"],
                         "consistency_ok": (pc is None) or nr == "origin_point_in_flame_at_departure"})
        print(reg, st, h, var, checks[-1]["b0_count_check"], checks[-1]["router_cells_union"], flush=True)
    tab = defaultdict(Counter)
    for r in rows:
        k = "%s|%s|h%d|%s" % (r["region"], r["start"], r["horizon_h"], r["variant"])
        tab[k][r["class"]] += 1
        if r["point"]: tab[k]["not_evaluated:" + r["point"]] += 1
    out = {"what": "HEADLINE no_reentry/2 re-tabulated with the not-evaluated state (NOT_EVALUATED_LABEL_RULE.md)",
           "state_label": STATE, "state_line": LINE, "lost_route_flag": FLAG, "lost_route_cause": CAUSE,
           "labels": ["SCENARIO, not what happened; graphs are road-limited",
                      "Assumes no fire outside mapped or forecast cells; no conservative unknown-support tier exists at multi-hour.",
                      "CERT = router OR closed footprint; ROUTER = router rule only; refusal claims only from ROUTER"],
           "b0_checks": checks, "b0_count_check_all": all(c["b0_count_check"] for c in checks),
           "consistency_exceptions": [r for r in rows if not r["consistency_ok"]],
           "table": {k: dict(v) for k, v in sorted(tab.items())}, "rows": rows}
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({"b0_count_check_all": out["b0_count_check_all"], "consistency_exceptions": len(out["consistency_exceptions"])}))


if __name__ == "__main__":
    main()
