"""Ember-positive sealed stratum of the precision evaluation (protocol amendment 2, 2026-10-17).

The rule is the protocol draft's populations.sealed_test_ember_positive.selection_rule
(results/validation/precision_20261017/protocol_draft.yaml, committed before any of these
clips was fetched):

    python scripts/precision_ember_stratum.py pool      -> ember_stratum/pool.json (ordered pool)
    python scripts/precision_ember_stratum.py fetch --first N
        fetches the first N pool clips not fetched yet into data/raw (receipts appended to
        ember_stratum/fetch_receipts.jsonl)
    python scripts/precision_ember_stratum.py render
        for every fetched clip: 4 triplets of 3 consecutive frames at 20, 40, 60 and 80 percent
        of the clip, as PNGs for the blind screen (results/runs/precision_20261017/ember_screen)
    python scripts/precision_ember_stratum.py include --screen SCREEN.json
        applies the inclusion rule to the two screeners' answers -> ember_stratum/inclusion.json

Only names, sizes and the screeners' answers decide; no detector or method output exists for
these clips when they are chosen.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
VAL = ROOT / "results/validation/precision_20261017"
OUT = VAL / "ember_stratum"
LISTINGS = ROOT / "results/runs/precision_20261017/rds"
SCREEN_DIR = ROOT / "results/runs/precision_20261017/ember_screen"
SEED = 20261019
FIRES = ["2007_GABayBigTurnAround_Sweatfarm", "2014_Beaver", "2006_Ralston", "2003_BlackMountain", "2016_Buffalo_Tatanka",
         "2016_Maple_Tatanka", "2008_Clover"]
CLIP_RE = re.compile(r"^([A-Z]{4}[0-9A-Z]{2,3})_C(\d+)\.avi$", re.I)     # plot ids may end in a letter (GEOR08A)
QS = (20, 40, 60, 80)
MAX_PER_FIRE, MAX_PER_PLOT, TARGET = 2, 1, 10


def pool() -> list[dict]:
    from precision_select_rds import _members, raw_name

    sel = json.loads((VAL / "data_selection_amendment1.json").read_text())
    used = {s["member"] for s in sel["selected"]}
    # amendment 3: no plot (camera deployment) of the low-observability sealed stratum
    low_obs_plots = {(s["fire"], s["plot"]) for s in sel["selected"] if s.get("role") in ("test", "test_negative_footage")}
    items = {}
    for m in _members(LISTINGS, "RDS-2021-0069"):
        parts = m["name"].split("/")
        if len(parts) < 3 or parts[1] not in FIRES or not CLIP_RE.match(parts[-1]) or m["name"] in used:
            continue
        mc = CLIP_RE.match(parts[-1])
        if (parts[1], mc.group(1).upper()) in low_obs_plots:
            continue
        item = {"archive": "RDS-2021-0069", "clip_group": "C8", "fire": parts[1], "plot": mc.group(1).upper(),
                "role": "test_ember_positive_candidate", "member": m["name"], "member_bytes": m["size"],
                "member_crc32": m["crc32"], "archive_url": m["archive_url"], "fetch": "whole"}
        item["raw_name"] = raw_name(item)
        items[m["name"]] = item
    ordered = [items[k] for k in sorted(items)]
    perm = np.random.default_rng(SEED).permutation(len(ordered))
    return [ordered[i] for i in perm]


def cmd_pool(a) -> int:
    p = pool()
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"rule": "protocol_draft.yaml populations.sealed_test_ember_positive.selection_rule (amendments 2 and 3)",
           "seed": SEED, "fires": FIRES, "n": len(p), "total_bytes": int(sum(i["member_bytes"] for i in p)), "pool": p}
    (OUT / "pool.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(f"{len(p)} clips, {rec['total_bytes'] / 1e6:.0f} MB; first: {[i['raw_name'] for i in p[:10]]}")
    return 0


def cmd_fetch(a) -> int:
    from fetch_rds_members import get_member, list_members

    p = json.loads((OUT / "pool.json").read_text())["pool"]
    receipts = OUT / "fetch_receipts.jsonl"
    done = set()
    if receipts.exists():
        done = {json.loads(line)["member"] for line in receipts.read_text().splitlines() if line.strip()}
    todo = [i for i in p if i["member"] not in done][: a.first]
    listings: dict[str, dict] = {}
    fails = 0
    for it in todo:
        out = ROOT / "data/raw" / it["raw_name"]
        try:
            if it["archive_url"] not in listings:
                listings[it["archive_url"]] = {m["name"]: m for m in list_members(it["archive_url"])["members"]}
            rec = get_member(it["archive_url"], listings[it["archive_url"]][it["member"]], out, None)
        except Exception as exc:          # recorded; the next clip is tried, and include refuses a gap
            fails += 1
            print(f"FAILED {it['member']}: {exc}")
            with open(OUT / "fetch_failures.jsonl", "a") as f:
                f.write(json.dumps({"member": it["member"], "raw_name": it["raw_name"], "error": str(exc)}) + "\n")
            continue
        rec.update({"role": it["role"], "clip_group": "C8", "raw_name": it["raw_name"], "pool_rank": p.index(it)})
        with open(receipts, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"ok {it['raw_name']} {rec['bytes_written'] / 1e6:.1f} MB")
    return 1 if fails else 0


def cmd_render(a) -> int:
    import av
    from PIL import Image

    receipts = [json.loads(line) for line in (OUT / "fetch_receipts.jsonl").read_text().splitlines() if line.strip()]
    for rec in receipts:
        clip = rec["raw_name"].rsplit(".", 1)[0]
        d = SCREEN_DIR / clip
        if d.exists() and len(list(d.glob("*.png"))) >= 12:
            continue
        d.mkdir(parents=True, exist_ok=True)
        c = av.open(str(ROOT / "data/raw" / rec["raw_name"]))
        s = c.streams.video[0]
        frames = []
        for fr in c.decode(s):
            frames.append((float(fr.time or 0.0), fr.to_ndarray(format="rgb24")))
        c.close()
        n = len(frames)
        for q in (20, 40, 60, 80):
            i0 = min(max(int(round(n * q / 100)) - 1, 0), n - 3)
            for j in range(3):
                t, img = frames[i0 + j]
                im = Image.fromarray(img)
                im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
                im.save(d / f"q{q}_f{i0 + j:05d}_t{t:07.2f}_k{j}.png")
        print(clip, n, "frames")
    return 0


def _complete(r: dict | None) -> bool:
    return bool(r) and sorted(int(t["q"]) for t in r.get("triplets", [])) == list(QS)


def cmd_include(a) -> int:
    """Amendment 3 reading of the rule: a clip qualifies when some triplet (the same q) has yes
    from both screeners, both screeners answered all four triplets, neither reports a moving
    camera or cuts, and neither reads its timebase as time-lapse. Inclusion walks the corrected
    pool in order and fails closed: every clip it passes must have both screeners' complete
    answers, or the command stops and lists them."""
    screens = []
    for path in a.screen:
        d = json.loads(Path(path).read_text())
        screens.append(d.get("result", d))
    p = json.loads((OUT / "pool.json").read_text())["pool"]
    by: dict[str, dict] = {}
    for sc in screens:
        for who in ("first", "second"):
            for r in sc[who]:
                by.setdefault(r["clip_id"], {})[who] = r
    out, per_fire, per_plot, rows, missing = [], {}, {}, [], []
    for it in p:
        if len(out) >= TARGET:
            break
        clip = it["raw_name"].rsplit(".", 1)[0]
        s1, s2 = by.get(clip, {}).get("first"), by.get(clip, {}).get("second")
        if not (_complete(s1) and _complete(s2)):
            missing.append(clip)
            continue
        a1 = {int(t["q"]): t["ember_visible"] for t in s1["triplets"]}
        a2 = {int(t["q"]): t["ember_visible"] for t in s2["triplets"]}
        both_yes = [q for q in QS if a1[q] == "yes" and a2[q] == "yes"]
        cam = all(r["camera"] in ("static", "unclear") for r in (s1, s2))
        tl = any(r["timebase_verdict"] == "time_lapse" for r in (s1, s2))
        qualifies = bool(both_yes and cam and not tl)
        take = (qualifies and per_fire.get(it["fire"], 0) < MAX_PER_FIRE
                and per_plot.get((it["fire"], it["plot"]), 0) < MAX_PER_PLOT)
        if take:
            out.append(clip)
            per_fire[it["fire"]] = per_fire.get(it["fire"], 0) + 1
            per_plot[(it["fire"], it["plot"])] = per_plot.get((it["fire"], it["plot"]), 0) + 1
        rows.append({"clip_id": clip, "fire": it["fire"], "plot": it["plot"], "triplets_yes_both": both_yes,
                     "camera": [s1["camera"], s2["camera"]], "timebase": [s1["timebase_verdict"], s2["timebase_verdict"]],
                     "qualifies": qualifies, "included": take})
    if missing:
        print(json.dumps({"incomplete_or_unscreened_before_the_end": missing}))
        (OUT / "inclusion_pending.json").write_text(json.dumps({"missing": missing, "rows_so_far": rows}, indent=1) + "\n")
        return 2
    rec = {"rule": ("amendment 3 reading: some triplet with yes from both screeners (all four triplets answered by both), "
                    "no moving camera or cuts, not time-lapse; at most "
                    f"{MAX_PER_FIRE} per fire and {MAX_PER_PLOT} per plot, in pool order, until {TARGET}"),
           "screens": [str(x) for x in a.screen], "screened_in_order": len(rows),
           "qualifying": sum(r["qualifies"] for r in rows), "included": out, "rows": rows}
    (OUT / "inclusion.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "rows"}, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pool")
    q = sub.add_parser("fetch")
    q.add_argument("--first", type=int, default=20)
    sub.add_parser("render")
    q = sub.add_parser("include")
    q.add_argument("--screen", nargs="+", required=True)
    a = ap.parse_args(argv)
    return {"pool": cmd_pool, "fetch": cmd_fetch, "render": cmd_render, "include": cmd_include}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
