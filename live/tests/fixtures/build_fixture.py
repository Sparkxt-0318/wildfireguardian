"""Build the recorded-input fixture for a past issue time, from committed archives only (plus one GFS cycle).

    python3 live/tests/fixtures/build_fixture.py --issue 2025-03-25T09:00:00Z --out live/tests/fixtures/kfs01_20250325T0900Z

RECONSTRUCTED, not fetched live. The KFS record is written in the format of the live feed for the 의성 fire of 22 March
2025 (reported 11:25 KST, 의성군 안평면). The repository has no KFS record of that fire, so its point is the first
VIIRS detection of the fire (2025-03-22 04:22 UTC, research/kcf-replay/fire_discs.json). FIRMS rows are the committed
2025 country archives (S-NPP, NOAA-20, MODIS) acquired in the 5 days before the issue time; NOAA-21 is not in the
archive and is recorded as missing. AHI scans are the committed KFS_01 Japan-area scans
(research/harness-2026-11/data-fetch-2/ahi_kfs01). GFS is the issued cycle c(t), fetched once from the NOAA bucket.
Every fetch time is set to the issue time minus 10 minutes and labelled RECONSTRUCTED.
"""
import argparse
import csv
import glob
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from wfg_live import common as C, fetch  # noqa: E402

FIRMS = C.REPO / "research/harness-2026-11/data-fetch/small/firms"
AHI = C.REPO / "research/harness-2026-11/data-fetch-2/ahi_kfs01"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    T = C.parse_iso(a.issue)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = C.settings()
    t_fetch = T - timedelta(minutes=10)
    man = {"schema": "wfg.live.inputs/1", "issue_utc": C.iso(T), "reconstructed": True,
           "note": "RECONSTRUCTED from committed archives (live/tests/fixtures/build_fixture.py); not fetched live", "sources": {}}

    def rec(name, url, body, path, err=None, extra=None):
        d = {"source": name, "url": url, "fetched_utc": C.iso(t_fetch), "http_status": 200 if body is not None else 0,
             "ok": body is not None and not err, "error": err, "bytes": None if body is None else len(body),
             "sha256": None if body is None else C.sha256(body), "file": path, "reconstructed": True}
        d.update(extra or {})
        return d

    # KFS record, live-feed format
    fx, fy = 1100979.3442916097, 1819961.075389934           # first FIRMS-N disc of fire_discs.json
    from pyproj import Transformer
    lon, lat = Transformer.from_crs(5179, 4326, always_xy=True).transform(fx, fy)
    kfs = {"fireShowInfoList": [{
        "frfrInfoId": "FIXTURE-20250322-UISEONG", "frfrPrgrsStcd": "02", "frfrPrgrsStcdNm": "진화중",
        "frfrLctnXcrd": "%.6f" % lon, "frfrLctnYcrd": "%.6f" % lat, "frfrSttmnDt": "20250322", "frfrSttmnHms": "112500",
        "frfrSttmnAddr": "경상북도 의성군 안평면", "lgdngCd": "4773000000", "frfrStepIssuNm": "3단계", "frfrPotfrRt": None,
        "_fixture_note": "reconstructed record; point = first VIIRS detection of the fire, not a KFS coordinate"}]}
    b = json.dumps(kfs, ensure_ascii=False).encode()
    (out / "kfs.json").write_bytes(b)
    man["sources"]["kfs"] = rec("kfs", cfg["kfs"]["url"], b, "kfs.json")

    # FIRMS: committed 2025 archives, rows in [T - 5 d, T)
    w, s, e, n = cfg["firms"]["bbox"]
    for src, f in (("VIIRS_SNPP_NRT", "viirs-snpp"), ("VIIRS_NOAA20_NRT", "viirs-jpss1"), ("VIIRS_NOAA21_NRT", None), ("MODIS_NRT", "modis")):
        if f is None:
            man["sources"]["firms:" + src] = rec("firms:" + src, "(not in the committed archive)", None, None, "not in archive")
            continue
        rows = list(csv.reader(open(FIRMS / ("%s_2025_Republic_of_Korea.csv" % f), encoding="utf-8")))
        h = rows[0]
        keep = [h]
        for r in rows[1:]:
            d = dict(zip(h, r))
            t = datetime.strptime(d["acq_date"] + d["acq_time"].zfill(4), "%Y-%m-%d%H%M").replace(tzinfo=C.UTC)
            if T - timedelta(days=cfg["firms"]["day_range"]) <= t < T and w <= float(d["longitude"]) <= e and s <= float(d["latitude"]) <= n:
                keep.append(r)
        sio = io.StringIO()
        csv.writer(sio, lineterminator="\n").writerows(keep)
        b = sio.getvalue().encode()
        name = "firms_%s.csv" % src
        (out / name).write_bytes(b)
        man["sources"]["firms:" + src] = rec("firms:" + src, "research/harness-2026-11/data-fetch/small/firms/%s_2025_Republic_of_Korea.csv" % f, b, name)

    # AHI: committed scans in [max(report - 1 h, T - 6 h), T), pixels within 60 km of the point
    rep = fetch.report_utc(kfs["fireShowInfoList"][0])
    t_from = max(rep - timedelta(hours=1), T - timedelta(hours=cfg["ahi"]["window_h"]))
    scans = []
    for fpath in sorted(glob.glob(str(AHI / "*.npz"))):
        z = np.load(fpath)
        d = np.hypot(z["x5179"] - fx, z["y5179"] - fy) <= cfg["ahi"]["box_pad_km"] * 1000
        for i, st in enumerate(z["scan_start_utc"]):
            ts = datetime.fromisoformat(str(st)).replace(tzinfo=C.UTC)
            if not (t_from <= ts < T):
                continue
            te = datetime.fromisoformat(str(z["scan_end_utc"][i])).replace(tzinfo=C.UTC)
            b7 = z["b07_K"][i][d].astype(float); b14 = z["b14_K"][i][d].astype(float)
            scans.append({"id": "%s_%s" % (ts.strftime("%Y%m%d_%H%M"), z["scan_id"][i]), "start_utc": C.iso(ts), "end_utc": C.iso(te),
                          "lat": np.round(z["lat"][d], 5).tolist(), "lon": np.round(z["lon"][d], 5).tolist(),
                          "b07": [None if not np.isfinite(v) else round(v, 2) for v in b7],
                          "b07_b14": [None if not np.isfinite(v) else round(v, 2) for v in b7 - b14]})
    b = fetch.ahi_store(scans, [], cfg["ahi"])
    (out / "ahi_pixels.json").write_bytes(b)
    man["sources"]["ahi"] = rec("ahi", "research/harness-2026-11/data-fetch-2/ahi_kfs01", b, "ahi_pixels.json", None if scans else "no scan",
                                {"window_utc": [C.iso(t_from), C.iso(T)], "scans_read": len(scans)})

    # GFS c(t), fetched once
    g = fetch.fetch_gfs(cfg, out, T.replace(minute=0, second=0), None)
    g["fetched_utc"] = C.iso(t_fetch)
    g["reconstructed"] = True
    man["sources"]["gfs"] = g
    man["fetch_finished_utc"] = C.iso(t_fetch)
    C.dump(out / "manifest.json", man)
    print(json.dumps({k: (v["ok"], v.get("bytes")) for k, v in man["sources"].items()}, indent=1))


if __name__ == "__main__":
    main()
