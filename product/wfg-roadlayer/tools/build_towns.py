"""Build data/towns/<region>.csv: the 읍·면·동 of every planner origin (village or care facility).

Run once by a maintainer; the CSV is committed and the tool only reads it. Standard library only.

Sources
  * places: planner/public/data/regions/<region>/places.geojson (OSM names; 시·군 labels from V-World
    BND_SIGUNGU_PG, research/harness-2026-11/W-KIT/JURISDICTION).
  * 법정동코드 (행정안전부 행정표준코드, 법정동 단위, incl. 리): the table bundled in the PyPI wheel
    PublicDataReader 1.1.1.post2 (file PublicDataReader/raw/code_bdong.json, MIT-licensed package; the code table
    itself is public government data). The wheel is downloaded once and verified by SHA-256.

Method, per origin (column `method`)
  * `legal_ri_unique`: the OSM name, with a 행정리 number dropped (강구2리 -> 강구리), is a live 법정리 (or 법정동)
    of exactly one 읍·면·동 inside the origin's 시·군. This is the only method marked established.
  * `legal_ri_ambiguous_nearest`: the name exists in two or more 읍·면 of that 시·군; the 읍·면 is taken from the
    3 nearest `legal_ri_unique` origins of the same 시·군 among those candidates (majority, then nearest).
    ESTIMATE: the sheet marks the row.
  * `name_contains_legal`: no exact 법정리 name, but the name starts with one (괴시리전통마을 -> 괴시리) or with a
    법정동 stem followed by a number or facility word (용상3구경로당 -> 용상동), unique in the 시·군. ESTIMATE.
  * `nearest_established`: no 법정리 name (care facilities, named hamlets); the 읍·면 of the 3 nearest
    `legal_ri_unique` origins of the same 시·군 (majority, then nearest). ESTIMATE: the sheet marks the row.
  * `unknown`: no 시·군 label or nothing to borrow from. The row goes on a sheet titled "읍·면 미확인".

Usage: python3 tools/build_towns.py [--wheel PATH] [--repo REPO_ROOT]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent
WHEEL_URL = ("https://files.pythonhosted.org/packages/48/21/a5294088eaa39e5d1e89ee4e94db895e7ee30c263bed9a6821dbb05283e6/"
             "PublicDataReader-1.1.1.post2-py3-none-any.whl")
WHEEL_NAME = "PublicDataReader-1.1.1.post2-py3-none-any.whl"
WHEEL_SHA256 = "7802f750bcd538b078e7be54146556968017dd43fb1b4e781fa440a4e770b2b6"
MEMBER = "PublicDataReader/raw/code_bdong.json"
REGIONS = ("yeongdeok_2025", "uiseong_andong_2025")
SIDO = "경상북도"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def haversine_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def _val(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def load_codes(wheel: bytes):
    with zipfile.ZipFile(io.BytesIO(wheel)) as z:
        raw = z.read(MEMBER)
    d = json.loads(raw)
    n = len(d["법정동코드"])
    rows = [{k: _val(d[k][str(i)]) for k in d} for i in range(n)]
    live = [r for r in rows if r["시도명"] == SIDO and not r["말소일자"]]
    idx = defaultdict(set)
    for r in live:
        if r["동리명"]:
            idx[(r["시군구명"], r["동리명"])].add(r["읍면동명"])
        elif r["읍면동명"] and r["읍면동명"].endswith("동"):
            idx[(r["시군구명"], r["읍면동명"])].add(r["읍면동명"])
    newest = max((r["생성일자"] for r in rows if r["생성일자"]), default=None)
    return idx, sha256(raw), newest


def borrow(o, established, sg, allowed=None, k=3):
    near = sorted(((haversine_m(o["xy"], e["xy"]), e["eupmyeon"], e["id"]) for e in established
                   if e["sigungu"] == sg and (allowed is None or e["eupmyeon"] in allowed)))[:k]
    if not near:
        return None, []
    votes = Counter(e for _, e, _ in near)
    top = max(votes.values())
    pick = next(e for _, e, _ in near if votes[e] == top)
    return pick, near


def name_stem_match(name, sg, idx):
    """A name that starts with a 법정리/동 name (괴시리전통마을 -> 괴시리) or with its stem followed by a number or
    the facility word (용상3구경로당 -> 용상동). Returns (legal name, 읍·면·동) when exactly one matches."""
    hits = set()
    m = re.match(r"^(\S+?[리동])", name)
    if m and len(idx.get((sg, m.group(1)), ())) == 1:
        hits.add((m.group(1), next(iter(idx[(sg, m.group(1))]))))
    for k in (3, 2):
        stem = name[:k]
        if len(stem) < k or not re.fullmatch(r"[가-힣]+", stem):
            continue
        for suf in ("동", "리"):
            c = idx.get((sg, stem + suf), set())
            if len(c) == 1 and re.match(re.escape(stem) + r"(\d|구|경로당|마을)", name):
                hits.add((stem + suf, next(iter(c))))
    return next(iter(hits)) if len(hits) == 1 else None


def build(repo: Path, wheel: bytes, sources: dict):
    idx, table_sha, newest = load_codes(wheel)
    report = {}
    for region in REGIONS:
        feats = json.loads((repo / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]
        origins = []
        for f in feats:
            p = f["properties"]
            if p["role"] != "origin":
                continue
            sg = (p.get("sigungu") or {}).get("ko")
            if (p.get("sigungu") or {}).get("status") != "established":
                sg = None
            origins.append({"id": p["id"], "name": p.get("name") or "", "sigungu": sg,
                            "xy": tuple(f["geometry"]["coordinates"]), "category": p.get("category")})
        for o in origins:
            key = re.sub(r"\d+리$", "리", o["name"])
            cand = idx.get((o["sigungu"], key), set()) if o["sigungu"] else set()
            o["cand"] = sorted(cand)
            if len(cand) == 1:
                o.update(eupmyeon=next(iter(cand)), method="legal_ri_unique",
                         note="법정리 %s → %s %s" % (key, o["sigungu"], next(iter(cand))))
        est = [o for o in origins if o.get("method") == "legal_ri_unique"]
        for o in origins:
            if o.get("method"):
                continue
            if not o["sigungu"]:
                o.update(eupmyeon="", method="unknown", note="시·군 미확인")
                continue
            stem = name_stem_match(o["name"], o["sigungu"], idx) if not o["cand"] else None
            if stem:
                o.update(eupmyeon=stem[1], method="name_contains_legal",
                         note="이름에 법정리·동 %s 포함 → %s (추정)" % stem)
            elif o["cand"]:
                pick, near = borrow(o, est, o["sigungu"], set(o["cand"]))
                if pick is None:
                    o.update(eupmyeon="", method="unknown", note="법정리 후보 %s; 인접 확인 마을 없음" % "/".join(o["cand"]))
                else:
                    o.update(eupmyeon=pick, method="legal_ri_ambiguous_nearest",
                             note="법정리 후보 %s; 가까운 확인 마을 %s" % ("/".join(o["cand"]),
                                                                ", ".join("%s %.1fkm" % (e, d / 1000) for d, e, _ in near)))
            else:
                pick, near = borrow(o, est, o["sigungu"])
                if pick is None:
                    o.update(eupmyeon="", method="unknown", note="법정리 이름 없음; 인접 확인 마을 없음")
                else:
                    o.update(eupmyeon=pick, method="nearest_established",
                             note="법정리 이름 없음; 가까운 확인 마을 %s" % ", ".join("%s %.1fkm" % (e, d / 1000) for d, e, _ in near))
        out = PRODUCT / "data/towns" / f"{region}.csv"
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["place_id", "name", "sigungu", "eupmyeon", "method", "note"])
            for o in sorted(origins, key=lambda o: o["id"]):
                w.writerow([o["id"], o["name"], o["sigungu"] or "", o["eupmyeon"], o["method"], o["note"]])
        report[region] = dict(Counter(o["method"] for o in origins))
        print(region, report[region])
    sources["towns"] = {"code_table_member": MEMBER, "code_table_sha256": table_sha, "code_table_newest_created": newest,
                        "counts": report}
    return sources


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wheel", type=Path, help="local copy of %s" % WHEEL_NAME)
    ap.add_argument("--repo", type=Path, default=PRODUCT.parents[1])
    a = ap.parse_args()
    src_path = PRODUCT / "data/sources.json"
    sources = json.loads(src_path.read_text()) if src_path.exists() else {}
    wheel = a.wheel.read_bytes() if a.wheel else urllib.request.urlopen(WHEEL_URL).read()
    if sha256(wheel) != WHEEL_SHA256:
        raise SystemExit("wheel SHA-256 %s differs from the pinned %s; nothing written" % (sha256(wheel), WHEEL_SHA256))
    sources["towns_wheel"] = {"name": WHEEL_NAME, "url": WHEEL_URL, "sha256": WHEEL_SHA256}
    sources = build(a.repo, wheel, sources)
    src_path.write_text(json.dumps(sources, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
