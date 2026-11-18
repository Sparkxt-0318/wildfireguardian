"""Fetch stage: every live input into one folder, with source, fetch time, status and SHA-256 (PROTOCOL §1).

The compute stage (compute.py) reads only this folder, so any run can be replayed from what it stored.
"""
from __future__ import annotations

import bz2
import json
import math
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from . import common as C


def _rec(name, url, status, body, err, t0, path=None, extra=None):
    d = {"source": name, "url": url, "fetched_utc": C.iso(t0), "http_status": status, "ok": body is not None and not err,
         "error": err or None, "bytes": None if body is None else len(body), "sha256": None if body is None else C.sha256(body),
         "file": path}
    d.update(extra or {})
    return d


# ---------------------------------------------------------------- KFS
def fetch_kfs(cfg, out: Path):
    url = cfg["kfs"]["url"]
    t0 = C.utcnow()
    st, body, err = C.http(url, headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest",
                                         "Referer": cfg["kfs"]["page"]})
    if body is not None:
        try:
            j = json.loads(body.decode("utf-8"))
            if not isinstance(j.get("fireShowInfoList"), list):
                err = "unexpected JSON: no fireShowInfoList list"
        except Exception as e:  # noqa: BLE001
            err = "not JSON: %s" % e
    if body is not None:
        (out / "kfs.json").write_bytes(body)
    return _rec("kfs", url, st, body, err, t0, "kfs.json" if body is not None else None)


def kfs_fires(inputs: Path, manifest) -> list | None:
    m = manifest["sources"].get("kfs")
    if not m or not m["ok"]:
        return None
    return json.loads((inputs / m["file"]).read_text(encoding="utf-8"))["fireShowInfoList"]


# ---------------------------------------------------------------- FIRMS
def firms_key():
    k = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if k:
        return k, "secret FIRMS_MAP_KEY"
    p = C.LIVE / "config/firms_map_key.txt"
    if p.exists() and p.read_text().strip():
        return p.read_text().strip(), "file live/config/firms_map_key.txt"
    return None, "none"


def fetch_firms(cfg, out: Path):
    key, where = firms_key()
    f = cfg["firms"]
    box = ",".join("%g" % v for v in f["bbox"])
    res = {}
    for src in f["sources"]:
        url_pub = "%s/<MAP_KEY>/%s/%s/%d" % (f["api"], src, box, f["day_range"])
        t0 = C.utcnow()
        if not key:
            res[src] = _rec("firms:" + src, url_pub, 0, None, "no FIRMS map key (secret FIRMS_MAP_KEY empty, no key file)", t0)
            continue
        st, body, err = C.http("%s/%s/%s/%s/%d" % (f["api"], key, src, box, f["day_range"]), timeout=90)
        if body is not None:
            head = body[:200].decode("utf-8", "replace")
            if not head.startswith(("latitude", "country_id")):
                err = "not a FIRMS CSV: %s" % head.strip()[:120]
        name = "firms_%s.csv" % src
        if body is not None:
            (out / name).write_bytes(body)
        res[src] = _rec("firms:" + src, url_pub, st, body, err, t0, name if body is not None else None, {"key_from": where})
    return res


# ---------------------------------------------------------------- AHI
def _ahi_slots(t_from: datetime, t_to: datetime):
    s = t_from.replace(minute=t_from.minute - t_from.minute % 10, second=0)
    while s < t_to:
        yield s
        s += timedelta(minutes=10)


def fetch_ahi(cfg, out: Path, points, t_from: datetime, t_to: datetime, cache: Path | None):
    """Decode every Japan-area scan in [t_from, t_to) and keep B07, B07-B14 for pixels within box_pad_km of a point.
    Writes ahi_pixels.json: per scan the kept pixel values. Hotspot logic is in area.py (frozen rule)."""
    import warnings
    warnings.filterwarnings("ignore")
    from pyproj import Transformer
    a = cfg["ahi"]
    tr = Transformer.from_crs(4326, 5179, always_xy=True)
    P = np.array([tr.transform(lo, la) for la, lo in points])
    scans, missing, nbytes = [], [], 0
    t0 = C.utcnow()
    idx = None
    for slot in _ahi_slots(t_from, t_to):
        for jp in ("JP01", "JP02", "JP03", "JP04"):
            key = "%s_%s" % (slot.strftime("%Y%m%d_%H%M"), jp)
            cpath = cache / ("ahi_%s.json" % key) if cache else None
            if cpath and cpath.exists():
                rec = json.loads(cpath.read_text())
                if rec.get("points") == P.round(0).tolist():
                    if rec["scan"]:
                        scans.append(rec["scan"])
                    else:
                        missing.append(key)
                    continue
            rec = {"points": P.round(0).tolist(), "scan": None}
            with tempfile.TemporaryDirectory() as td:
                files = []
                for b in ("B07", "B14"):
                    n = "HS_H09_%s_%s_%s_R20_S0101.DAT.bz2" % (slot.strftime("%Y%m%d_%H%M"), b, jp)
                    st, body, err = C.http("%s/%s/%s" % (a["bucket"], slot.strftime("%Y/%m/%d/%H%M"), n), timeout=60, attempts=2, wait=3)
                    if body is None:
                        break
                    nbytes += len(body)
                    Path(td, n).write_bytes(body)
                    files.append(str(Path(td, n)))
                if len(files) == 2:
                    try:
                        from satpy import Scene
                        scn = Scene(reader="ahi_hsd", filenames=files)
                        scn.load(["B07", "B14"])
                        if idx is None:
                            lon, lat = scn["B07"].attrs["area"].get_lonlats()
                            ok = np.isfinite(lon) & np.isfinite(lat)
                            x, y = tr.transform(np.where(ok, lon, 0), np.where(ok, lat, 0))
                            d = np.full(lon.shape, np.inf)
                            for px, py in P:
                                d = np.minimum(d, np.hypot(x - px, y - py))
                            sel = np.where(ok & (d <= a["box_pad_km"] * 1000.0))
                            idx = (sel, lat[sel], lon[sel])
                        (sel, la, lo) = idx
                        b7 = scn["B07"].values[sel].astype(float)
                        b14 = scn["B14"].values[sel].astype(float)
                        rec["scan"] = {"id": key, "start_utc": C.iso(scn["B07"].attrs["start_time"].replace(tzinfo=C.UTC)),
                                       "end_utc": C.iso(scn["B07"].attrs["end_time"].replace(tzinfo=C.UTC)),
                                       "lat": np.round(la, 5).tolist(), "lon": np.round(lo, 5).tolist(),
                                       "b07": np.round(b7, 2).tolist(), "b07_b14": np.round(b7 - b14, 2).tolist()}
                    except Exception as e:  # noqa: BLE001
                        rec["error"] = "%s: %s" % (type(e).__name__, e)
            if cpath:
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(json.dumps(rec))
            if rec["scan"]:
                scans.append(rec["scan"])
            else:
                missing.append(key)
    body = json.dumps({"scans": scans, "missing": missing}, sort_keys=True).encode()
    (out / "ahi_pixels.json").write_bytes(body)
    expected = len(list(_ahi_slots(t_from, t_to))) * 4
    err = None if scans else "no AHI scan could be read"
    return _rec("ahi", cfg["ahi"]["bucket"], 200 if scans else 0, body, err, t0, "ahi_pixels.json",
                {"window_utc": [C.iso(t_from), C.iso(t_to)], "scans_read": len(scans), "scans_expected": expected,
                 "scans_missing": len(missing), "bytes_downloaded": nbytes})


# ---------------------------------------------------------------- GFS
def gfs_cycle(t: datetime) -> datetime:
    c = t - timedelta(hours=5)
    return c.replace(hour=c.hour - c.hour % 6, minute=0, second=0, microsecond=0)


def fetch_gfs(cfg, out: Path, issue_hour: datetime, cache: Path | None):
    import fetch_nwp as F  # research/kcf-abstain, unchanged
    cyc = gfs_cycle(issue_hour)
    name = "gfs_%s.npz" % cyc.strftime("%Y%m%d%H")
    t0 = C.utcnow()
    url = F.url("gfs", cyc.strftime("%Y%m%d%H"), 6)
    cpath = cache / name if cache else None
    if cpath and cpath.exists():
        body = cpath.read_bytes()
        meta = json.loads(cpath.with_suffix(".json").read_text())
    else:
        lat, lon = F.lattice("KOR")
        arr = np.full((len(F.LEADS), len(F.FIELDS), lat.size, lon.size), np.nan, np.float32)
        miss = {}
        for i, L in enumerate(F.LEADS):
            lead, o, m, b = F.one("gfs", "KOR", cyc.strftime("%Y%m%d%H"), L)
            arr[i] = o
            if m:
                miss[L] = m
        import io
        bio = io.BytesIO()
        np.savez_compressed(bio, arr=arr, leads=np.array(F.LEADS), lat=lat, lon=lon,
                            fields=np.array(["%s:%s" % f for f in F.FIELDS]))
        body = bio.getvalue()
        meta = {"cycle_utc": C.iso(cyc), "missing": {str(k): v for k, v in miss.items()}, "fetched_utc": C.iso(t0)}
        complete = not miss and not np.isnan(arr).any()
        meta["complete"] = bool(complete)
        if cpath and complete:   # only a complete cycle is reused by later runs
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_bytes(body)
            cpath.with_suffix(".json").write_text(json.dumps(meta))
    (out / name).write_bytes(body)
    err = None if meta.get("complete") else "GFS cycle %s incomplete: %s" % (cyc.strftime("%Y%m%d%H"), meta.get("missing"))
    return _rec("gfs", url.rsplit(".f", 1)[0] + ".f006…f018", 200, body, err, C.parse_iso(meta["fetched_utc"]), name,
                {"cycle_utc": C.iso(cyc), "complete": meta.get("complete"), "missing": meta.get("missing")})


# ---------------------------------------------------------------- all
def in_scope(cfg, f) -> bool:
    k = cfg["kfs"]
    if str(f.get("frfrPrgrsStcd")) not in k["active_status"]:
        return False
    code = str(f.get("lgdngCd") or "")
    addr = str(f.get("frfrSttmnAddr") or "")
    return code[:2] in k["province_codes"] or addr.startswith(tuple(k["province_prefixes"]))


def report_utc(f) -> datetime | None:
    d, h = str(f.get("frfrSttmnDt") or ""), str(f.get("frfrSttmnHms") or "").zfill(6)
    try:
        return datetime.strptime(d + h, "%Y%m%d%H%M%S").replace(tzinfo=C.KST).astimezone(C.UTC)
    except ValueError:
        return None


def fetch_all(out: Path, issue: datetime, cache: Path | None = None, skip=()):
    """Run the fetch stage. `skip` names sources to leave out (tests and RUNBOOK drills)."""
    cfg = C.settings()
    out.mkdir(parents=True, exist_ok=True)
    man = {"schema": "wfg.live.inputs/1", "issue_utc": C.iso(issue), "sources": {}}
    if "kfs" not in skip:
        man["sources"]["kfs"] = fetch_kfs(cfg, out)
    if "firms" not in skip:
        for src, r in fetch_firms(cfg, out).items():
            man["sources"]["firms:" + src] = r
    fires = kfs_fires(out, man) or []
    scope = [f for f in fires if in_scope(cfg, f)]
    if scope and "ahi" not in skip:
        pts, starts = [], []
        for f in scope:
            try:
                pts.append((float(f["frfrLctnYcrd"]), float(f["frfrLctnXcrd"])))
            except (TypeError, ValueError, KeyError):
                continue
            r = report_utc(f)
            starts.append((r or issue) - timedelta(hours=cfg["area"]["lookback_before_report_h"]))
        if pts:
            t_from = max(min(starts), issue - timedelta(hours=cfg["ahi"]["window_h"]))
            man["sources"]["ahi"] = fetch_ahi(cfg, out, pts, t_from, issue, cache)
    if "gfs" not in skip:
        ih = issue.replace(minute=0, second=0)
        try:
            man["sources"]["gfs"] = fetch_gfs(cfg, out, ih, cache)
        except Exception as e:  # noqa: BLE001
            man["sources"]["gfs"] = _rec("gfs", "noaa-gfs-bdp-pds", 0, None, "%s: %s" % (type(e).__name__, e), C.utcnow())
    man["fetch_finished_utc"] = C.iso(C.utcnow())
    C.dump(out / "manifest.json", man)
    return man
