"""Blind window annotation of the precision evaluation of 2026-10-17: labeller files, disagreements, truth.

The annotation workflow (two independent agent labellers per batch of windows, see
results/validation/precision_20261017/annotation/README.md) returns JSON with one entry per
labeller and batch: {"who": "A"|"B", "bi": batch, "rows": [...], "done": ["clip/wNNN", ...]}.
This script turns it into the inputs of `python -m wfglink verify truth`:

    python scripts/precision_annotation.py split RAW.json [RAW2.json ...] --population test
        -> annotation/<population>/<clip>/labels_a.csv and labels_b.csv (labeller A of every batch
           is "a", labeller B is "b"); a window a labeller reported done without any row gets a
           "none" row; a window with no row and not reported done stays unlabelled (no truth).
    python scripts/precision_annotation.py disagree --population test --out jobs.json
        -> the windows where the two labellers disagree (a sure point of one without a sure point
           of the other within 3 px, rule 2 of verify/truth.py), with the disputed points, for the
           adjudication workflow.
    python scripts/precision_annotation.py adjudicated RAW.json [...] --population test
        -> annotation/<population>/<clip>/labels_adjudicator.csv
    python scripts/precision_annotation.py truth --population test
        -> annotation/<population>/<clip>/truth.json via verify truth (adjudicator file when present)

Coordinates are tile pixels with pixel centres at integers, as the windows' README states.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "results/runs/precision_20261017/windows"
ANN = ROOT / "results/validation/precision_20261017/annotation"
COLUMNS = ["window_id", "k", "x", "y", "confidence", "ember_id", "size_class", "note"]


def _rows_from_raw(paths: list[str]) -> list[dict]:
    out = []
    for p in paths:
        d = json.loads(Path(p).read_text())
        d = d.get("result", d)
        for lab in d.get("labels", d.get("adjudications", [])):
            out.append(lab)
    return out


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in sorted(rows, key=lambda r: (r["window_id"], -1 if r["k"] is None else r["k"],
                                             str(r.get("ember_id")), r.get("x") or 0)):
            w.writerow(["" if r.get(c) is None else r.get(c) for c in COLUMNS])


def _collect(labs: list[dict], who_map: dict[str, str]) -> dict[tuple[str, str], list[dict]]:
    """(clip, role) -> label rows; windows done without rows get a 'none' row."""
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for lab in labs:
        role = who_map[lab["who"]]
        seen = set()
        for r in lab["rows"]:
            clip, wid = r["clip_id"], r["window_id"]
            seen.add(f"{clip}/{wid}")
            note = (r.get("note") or "").replace("\u2014", ",").replace("\u2013", "-")
            if r.get("x") is None or r.get("y") is None:
                out[(clip, role)].append({"window_id": wid, "k": None, "x": None, "y": None, "confidence": None,
                                          "ember_id": None, "size_class": None, "note": note or "none"})
            else:
                out[(clip, role)].append({**{c: r.get(c) for c in COLUMNS}, "window_id": wid, "note": note})
        for cw in lab.get("done", []):
            if cw not in seen and "/" in cw:
                clip, wid = cw.split("/", 1)
                out[(clip, role)].append({"window_id": wid, "k": None, "x": None, "y": None, "confidence": None,
                                          "ember_id": None, "size_class": None, "note": "none"})
    return out


def cmd_split(a) -> int:
    rows = _collect(_rows_from_raw(a.raw), {"A": "a", "B": "b"})
    for (clip, role), rs in sorted(rows.items()):
        _write(ANN / a.population / clip / f"labels_{role}.csv", rs)
        print(f"{clip} {role}: {len(rs)} rows, {len({r['window_id'] for r in rs})} windows")
    return 0


def cmd_adjudicated(a) -> int:
    rows = _collect(_rows_from_raw(a.raw), {"C": "adjudicator"})
    for (clip, role), rs in sorted(rows.items()):
        _write(ANN / a.population / clip / f"labels_{role}.csv", rs)
        print(f"{clip} {role}: {len(rs)} rows, {len({r['window_id'] for r in rs})} windows")
    return 0


def cmd_disagree(a) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from wfglink.verify.truth import merge_window, read_window_labels
    from wfglink.verify.windows import read_manifest

    jobs, total = [], 0
    for cdir in sorted((ANN / a.population).iterdir()):
        if not (cdir / "labels_a.csv").exists() or not (cdir / "labels_b.csv").exists():
            continue
        la, lb = read_window_labels(cdir / "labels_a.csv"), read_window_labels(cdir / "labels_b.csv")
        man = read_manifest(WINDOWS / cdir.name)
        wins = []
        for _, wr in man.iterrows():
            wid = wr["window_id"]
            xa, xb = la[la["window_id"] == wid], lb[lb["window_id"] == wid]
            if not len(xa) or not len(xb):
                continue
            m = merge_window(xa, xb, xa.iloc[0:0], int(wr["k"]), float(wr["w"]), float(wr["h"]), False)
            dis = [{"k": p["k"], "x": round(p["tx"], 1), "y": round(p["ty"], 1), "reason": p.get("reason", "")}
                   for p in m["points"] if p["source"] == "unadjudicated"]
            if dis:
                wins.append({"window_id": wid, "disputed": dis})
        total += len(wins)
        if wins:
            jobs.append({"clip_id": cdir.name, "k": int(man["k"].iloc[0]), "windows": wins})
    Path(a.out).write_text(json.dumps({"population": a.population, "root": str(WINDOWS), "jobs": jobs}, indent=1))
    print(f"{total} windows with disagreements in {len(jobs)} recordings -> {a.out}")
    return 0


def cmd_truth(a) -> int:
    rc = 0
    for cdir in sorted((ANN / a.population).iterdir()):
        if not (cdir / "labels_a.csv").exists():
            continue
        cmd = [sys.executable, "-m", "wfglink", "verify", "truth", str(WINDOWS / cdir.name),
               "--a", str(cdir / "labels_a.csv"), "--b", str(cdir / "labels_b.csv"), "--out", str(cdir / "truth.json")]
        if (cdir / "labels_adjudicator.csv").exists():
            cmd += ["--adjudicator", str(cdir / "labels_adjudicator.csv")]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        print(cdir.name, r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] if (r.stdout + r.stderr).strip() else "")
        rc |= r.returncode
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("split", "adjudicated"):
        q = sub.add_parser(name)
        q.add_argument("raw", nargs="+")
        q.add_argument("--population", required=True, choices=["calibration", "test"])
    q = sub.add_parser("disagree")
    q.add_argument("--population", required=True, choices=["calibration", "test"])
    q.add_argument("--out", required=True)
    q = sub.add_parser("truth")
    q.add_argument("--population", required=True, choices=["calibration", "test"])
    a = ap.parse_args(argv)
    return {"split": cmd_split, "adjudicated": cmd_adjudicated, "disagree": cmd_disagree, "truth": cmd_truth}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
