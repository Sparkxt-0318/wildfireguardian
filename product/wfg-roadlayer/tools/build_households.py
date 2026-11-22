"""SUPERSEDED by research/kcf-buildings (build_demand.py, build_product_inputs.py): the committed data/households/*.csv now
holds MOIS 2025-02 읍·면·동 counts split over the 법정리. This tool builds the earlier (assumed) tables, kept in
data/households_assumed/. Original text: build data/households/<region>.csv: households, vehicles and residents assumed without a car, for every origin.

Run once by a maintainer; the CSV is committed. Standard library only. Every value carries its status (CITED,
DERIVED, ASSUMED); the rules and sources are in data/traffic_sources.json:

  * households of a village = cited households of its 읍·면 (영덕군) or 시·군 (의성군, 청송군, 영양군) / number of live
    법정리·법정동 there (법정동코드 table of the PublicDataReader wheel, SHA-256 pinned): equal split, ASSUMED;
    안동시 villages take the 의성군 per-리 figure (ASSUMED: 안동시 is mostly urban 동);
  * care facility: residents from traffic_sources.json (ASSUMED), households 0;
  * persons per household = cited population / households of the same unit.

Vehicles and residents without a car are computed at run time from these and the settings (cards.toml), so the
no-car share stays a setting.

Usage: python3 tools/build_households.py [--wheel PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from build_towns import MEMBER, PRODUCT, SIDO, WHEEL_NAME, WHEEL_SHA256, WHEEL_URL, _val, sha256  # noqa: F401

import io
import urllib.request
import zipfile

REGIONS = ("uiseong_andong_2025", "yeongdeok_2025")
FACILITY = {"social_facility", "nursing_home"}


def legal_counts(wheel: bytes):
    with zipfile.ZipFile(io.BytesIO(wheel)) as z:
        d = json.loads(z.read(MEMBER))
    n = len(d["법정동코드"])
    em, sg = defaultdict(set), defaultdict(set)
    for i in range(n):
        r = {k: _val(d[k][str(i)]) for k in d}
        if r["시도명"] != SIDO or r["말소일자"]:
            continue
        if r["동리명"]:
            unit = (r["읍면동명"], r["동리명"])
        elif r["읍면동명"] and r["읍면동명"].endswith("동"):
            unit = (r["읍면동명"], "")
        else:
            continue
        em[(r["시군구명"], r["읍면동명"])].add(unit)
        sg[r["시군구명"]].add(unit)
    return {k: len(v) for k, v in em.items()}, {k: len(v) for k, v in sg.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wheel", type=Path)
    a = ap.parse_args()
    wheel = a.wheel.read_bytes() if a.wheel else urllib.request.urlopen(WHEEL_URL, timeout=120).read()
    assert sha256(wheel) == WHEEL_SHA256, "wheel SHA-256 mismatch"
    n_em, n_sg = legal_counts(wheel)
    src = json.loads((PRODUCT / "data/traffic_sources.json").read_text(encoding="utf-8"))["households"]
    county = src["county_2024_11_30"]["values"]
    ydem = src["yeongdeok_eupmyeon_2025_12"]["values"]
    fac_res = src["care_facility"]["residents"]
    for rid in REGIONS:
        towns = list(csv.DictReader(open(PRODUCT / "data/towns" / ("%s.csv" % rid), encoding="utf-8")))
        feats = {f["properties"]["id"]: f["properties"] for f in
                 json.loads((PRODUCT.parents[1] / ("planner/public/data/regions/%s/places.geojson" % rid)).read_text())["features"]}
        out = PRODUCT / "data/households_assumed" / ("%s.csv" % rid)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["place_id", "name", "sigungu", "eupmyeon", "kind", "households", "persons_per_household",
                        "facility_residents", "status", "basis"])
            for t in towns:
                sgn, emn = t["sigungu"], t["eupmyeon"]
                cat = feats[t["place_id"]].get("category")
                if cat in FACILITY:
                    w.writerow([t["place_id"], t["name"], sgn, emn, "care_facility", 0, "", fac_res, "ASSUMED",
                                "care facility: %d residents, none with a car (ASSUMED)" % fac_res])
                    continue
                if sgn == "영덕군" and emn in ydem:
                    tot, pop, n = ydem[emn]["households"], ydem[emn]["population"], n_em[(sgn, emn)]
                    basis = "%s %s %d세대 (yd.go.kr 2025-12, CITED) / 법정리 %d (equal split ASSUMED)" % (sgn, emn, tot, n)
                elif sgn in ("의성군", "청송군", "영양군"):
                    tot, pop, n = county[sgn]["households"], county[sgn]["population"], n_sg[sgn]
                    basis = "%s %d세대 (gb.go.kr 2024-11-30, CITED) / 법정리·동 %d (equal split ASSUMED)" % (sgn, tot, n)
                elif sgn == "안동시":
                    tot, pop, n = county["의성군"]["households"], county["의성군"]["population"], n_sg["의성군"]
                    basis = ("안동시 is mostly urban 동: 의성군 per-리 figure used, %d세대 (gb.go.kr 2024-11-30) / 법정리·동 %d "
                             "(ASSUMED)" % (tot, n))
                else:
                    raise SystemExit("no household rule for %s %s" % (sgn, emn))
                w.writerow([t["place_id"], t["name"], sgn, emn, "village", round(tot / n, 1), round(pop / tot, 3), "",
                            "ASSUMED", basis])
        print("wrote", out)


if __name__ == "__main__":
    main()
