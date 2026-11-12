"""Apply addendum A1 §1.2 items 9–12 and §1.3 to COHORT_SPLIT.csv using incident metadata only.

The --meta CSV is keyed by Incident_C, with columns poo_lat, poo_lon, discovery_date
(YYYY-MM-DD), first_utc and last_utc. Blank values are allowed and are logged as
missing. Reference fires (the FIT and SELECTED_ON ledger fires) are given in
--ref, with the same columns.

Rules, in order:
  §1.3   A b/c/d incident within 50 km and 30 days (discovery date) of any reference fire is excluded.
  item 10  Pairs within 5 km whose survey windows overlap are duplicates. Remove the a/d copy;
           if both copies are in b/c, remove the lower-ranked one.
  item 9   An a incident within 50 km and 30 days of any b or c incident is dropped from a.
  items 5,6,12  Excluded b/c slots are refilled from d in u order, keeping at least 30 incidents in d.
Outputs: COHORT_FINAL.csv (Incident_C, part, status, reason) and a JSON summary on stdout.

  python apply_filters.py --split COHORT_SPLIT.csv --meta meta.csv --ref ref.csv --out COHORT_FINAL.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, datetime
from pathlib import Path

NEAR_KM = 50.0
NEAR_DAYS = 30
DUP_KM = 5.0
D_FLOOR = 30


def km(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def parse(row):
    def f(k):
        v = (row.get(k) or "").strip()
        return v or None
    loc = (float(f("poo_lat")), float(f("poo_lon"))) if f("poo_lat") and f("poo_lon") else None
    day = date.fromisoformat(f("discovery_date")[:10]) if f("discovery_date") else None
    win = None
    if f("first_utc") and f("last_utc"):
        win = (datetime.fromisoformat(f("first_utc")), datetime.fromisoformat(f("last_utc")))
    return dict(loc=loc, day=day, win=win)


def near(m1, m2) -> bool:
    return (m1["loc"] is not None and m2["loc"] is not None and m1["day"] is not None and m2["day"] is not None
            and km(m1["loc"], m2["loc"]) <= NEAR_KM and abs((m1["day"] - m2["day"]).days) <= NEAR_DAYS)


def duplicate(m1, m2) -> bool:
    return (m1["loc"] is not None and m2["loc"] is not None and m1["win"] is not None and m2["win"] is not None
            and km(m1["loc"], m2["loc"]) <= DUP_KM and m1["win"][0] <= m2["win"][1] and m2["win"][0] <= m1["win"][1])


def run(split_rows, meta, ref) -> tuple[list[dict], dict]:
    rows = sorted(split_rows, key=lambda r: float(r["u"]))
    status = {r["Incident_C"]: dict(Incident_C=r["Incident_C"], part=r["part"], status="kept", reason="") for r in rows}
    m = {r["Incident_C"]: meta.get(r["Incident_C"], dict(loc=None, day=None, win=None)) for r in rows}
    missing = sorted(k for k, v in m.items() if v["loc"] is None or v["day"] is None)
    rank = {r["Incident_C"]: (int(r["eligible_rank"]) if r["eligible_rank"] else 10 ** 9) for r in rows}

    def drop(k, why):
        status[k]["status"] = "excluded"
        status[k]["reason"] = why

    # §1.3 independence from reference fires (b, c and d; part a is training data, the rule does not apply).
    for k, s in status.items():
        if s["part"] in "bcd":
            hit = next((rk for rk, rm in ref.items() if near(m[k], rm)), None)
            if hit:
                drop(k, f"§1.3 near reference fire {hit}")
    # item 10: duplicates
    keys = [k for k in status if status[k]["status"] == "kept"]
    for i, k1 in enumerate(keys):
        for k2 in keys[i + 1:]:
            if status[k1]["status"] != "kept" or status[k2]["status"] != "kept" or not duplicate(m[k1], m[k2]):
                continue
            p1, p2 = status[k1]["part"], status[k2]["part"]
            if p1 in "ad" and p2 in "bc":
                drop(k1, f"item 10 duplicate of {k2}")
            elif p2 in "ad" and p1 in "bc":
                drop(k2, f"item 10 duplicate of {k1}")
            elif p1 in "ad" and p2 in "ad":
                drop(k2 if p2 == "d" or (p1 == p2 and rank[k2] > rank[k1]) else k1, f"item 10 duplicate pair {k1}/{k2}")
            else:
                loser = k2 if rank[k2] > rank[k1] else k1
                drop(loser, f"item 10 duplicate within b/c of {k1 if loser == k2 else k2}")
    # items 5, 6, 12: refill b/c from d in u order, keeping the d floor.
    d_queue = [k for k in status if status[k]["part"] == "d" and status[k]["status"] == "kept"]
    refills = []
    for part in "bc":
        lost = sum(1 for s in status.values() if s["part"] == part and s["status"] == "excluded")
        for _ in range(lost):
            if len(d_queue) <= D_FLOOR:
                break
            k = d_queue.pop(0)
            status[k]["part"] = part
            status[k]["reason"] = f"replacement into {part} from d"
            refills.append(k)
    # item 9: a vs b/c leakage, drops from a only, after the final b/c is known.
    test = [k for k, s in status.items() if s["part"] in "bc" and s["status"] == "kept"]
    for k, s in status.items():
        if s["part"] == "a" and s["status"] == "kept":
            hit = next((t for t in test if near(m[k], m[t])), None)
            if hit:
                drop(k, f"item 9 near test incident {hit}")
    out = [status[r["Incident_C"]] for r in rows]
    summary = dict(
        kept={p: sum(1 for s in out if s["part"] == p and s["status"] == "kept") for p in "abcd"},
        excluded={p: sum(1 for s in out if s["part"] == p and s["status"] == "excluded") for p in "abcd"},
        replacements=refills, missing_metadata=len(missing),
    )
    return out, summary


def load_meta(path: Path) -> dict:
    return {r["Incident_C"]: parse(r) for r in csv.DictReader(path.open())}


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--split", "--meta", "--ref", "--out"):
        ap.add_argument(a, required=True, type=Path)
    args = ap.parse_args()
    out, summary = run(list(csv.DictReader(args.split.open())), load_meta(args.meta), load_meta(args.ref))
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Incident_C", "part", "status", "reason"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
