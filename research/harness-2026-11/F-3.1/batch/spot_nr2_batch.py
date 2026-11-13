"""Acceptance 8, spotting-dilation half on no_reentry/2 (rule: SPOTTING_NR2_ACCEPT8_RULE.md, committed first).
Clamped dilated kriged_mean rasters per (start, d); v3.7 manifest commands for (region, start, h5, kriged_mean) with
--arrival / --arrival-variant / --out replaced; /2 and reopening built; deadline_field.headline unchanged."""
import json, subprocess, sys, os, shutil, hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import numpy as np
S = "/tmp/claude-0/-home-user-wildfireguardian/bb5282c2-950b-50f1-81b9-ac1de20b6fe6/scratchpad"
LEO = S + "/leo819"; FD = LEO + "/research/harness-2026-11/F-DYN"; OUT = S + "/f31/spot_nr2"; RAS = OUT + "/rasters"
os.makedirs(RAS, exist_ok=True)
F31 = "/home/user/wildfireguardian/research/harness-2026-11/F-3.1"
sys.path.insert(0, FD)
from fdyn import variants  # noqa: E402  (Leo 819bcb91, unchanged)
sh = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
T0 = datetime(2025, 3, 22, 2, 24, tzinfo=timezone.utc)
D = (0, 500, 1000, 2000)
REC = {"uiseong_andong_2025": ["20250323T010000Z", "20250324T090000Z", "20250325T170000Z"],
       "yeongdeok_2025": ["20250325T190000Z", "20250325T230000Z", "20250326T080000Z"]}
m = json.load(open(FD + "/MANIFEST_v3_7.json"))
writer = {"leo_commit": subprocess.run(["git", "-C", LEO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
          "build_py_sha256": sh(FD + "/fdyn/build.py"), "variants_py_sha256": sh(FD + "/fdyn/variants.py"),
          "manifest": "MANIFEST_v3_7.json", "manifest_sha256": sh(FD + "/MANIFEST_v3_7.json")}
ent = {}
for e in m["entries"]:
    if e["start"] in REC.get(e["region"], []) and e["horizon_h"] == 5 and e["variant"] == "kriged_mean":
        ent[(e["region"], e["start"], e["transform"])] = e

def rasters():
    import rasterio
    with rasterio.open(FD + "/_data/KFS_01_pswt_ok_toa.tif") as r:
        a = r.read(1).astype(float)
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
    Dd = {d: variants.dilate(a, d, 0.0) for d in D}
    meta = {"base_sha256": sh(FD + "/_data/KFS_01_pswt_ok_toa.tif")}
    for region, starts in REC.items():
        for st in starts:
            h = (datetime.strptime(st, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc) - T0).total_seconds() / 3600
            fin = np.isfinite(a); burned = fin & (a <= h)
            ad = {}
            for d in D:
                x = np.where(burned, a, np.where(np.isfinite(Dd[d]), np.fmax(Dd[d], h), np.nan))
                ad[d] = x
                p = "%s/%s_%s_d%d.npz" % (RAS, region, st, d)
                sha = variants.save(__import__("pathlib").Path(p), x, "spot_clamped_%dm" % d,
                                    {"base": "KFS_01_pswt_ok_toa.tif", "dilate_m": d, "lag_s": 0, "clamp_h": h,
                                     "rule": "SPOTTING_NR2_ACCEPT8_RULE.md"})
                meta["%s|%s|%d" % (region, st, d)] = {
                    "npz_sha256": sha, "clamped_cells": int((~burned & np.isfinite(Dd[d]) & (Dd[d] < h)).sum()),
                    "finite_cells": int(np.isfinite(x).sum())}
            chk = {"a0_equals_a": bool(np.array_equal(ad[0], a, equal_nan=True))}
            for d1, d2 in zip(D, D[1:]):
                f1, f2 = np.isfinite(ad[d1]), np.isfinite(ad[d2])
                chk["order_fail_%d_%d" % (d1, d2)] = int((f1 & ~f2).sum() + (f1 & f2 & (ad[d2] > ad[d1])).sum())
            meta["%s|%s|nesting" % (region, st)] = chk
            assert chk["a0_equals_a"] and all(v == 0 for k, v in chk.items() if k.startswith("order_fail")), (region, st, chk)
    json.dump(meta, open(OUT + "/rasters_meta.json", "w"), indent=1)
    return meta

def build(e, ras, d, tag):
    cmd = list(e["cmd"])
    cmd[cmd.index("--arrival") + 1] = ras
    cmd[cmd.index("--arrival-variant") + 1] = "spot_clamped_%dm" % d
    out = "%s/pk_%s" % (OUT, tag); cmd[cmd.index("--out") + 1] = out
    r = subprocess.run(cmd, cwd=LEO, capture_output=True, text=True)
    return out, cmd, (r.stderr[-400:] if r.returncode else None)

def job(k):
    region, st, d = k
    tag = "%s__%s_h5_d%d" % (region, st, d)
    res = OUT + "/" + tag + ".json"
    if os.path.exists(res): return tag, "skip"
    ras = "%s/%s_%s_d%d.npz" % (RAS, region, st, d)
    nr, cnr, err = build(ent[(region, st, "no_reentry/2")], ras, d, tag + "__nr")
    if err: return tag, "BUILD_FAIL nr " + err
    re_, cre, err = build(ent[(region, st, "reopening")], ras, d, tag + "__re")
    if err: return tag, "BUILD_FAIL re " + err
    cmd = [sys.executable, "-m", "deadline_field.headline", "--graph", FD + "/_data/graphs_interim/%s/graph.json" % region,
           "--window-graph", LEO + "/data/routing/graphs/%s/graph.json" % region, "--nr-packet", nr, "--re-packet", re_,
           "--instance-json", FD + "/_data/INSTANCE.json", "--region", region, "--start", st,
           "--horizon-s", "18000", "--out", res + ".tmp"]
    r = subprocess.run(cmd, cwd=F31, capture_output=True, text=True)
    hz = {t: sh(p + "/HAZARD.json") if os.path.exists(p + "/HAZARD.json") else None for t, p in (("nr", nr), ("re", re_))}
    bs = {t: json.load(open(p + "/BUILD_SUMMARY.json")) if os.path.exists(p + "/BUILD_SUMMARY.json") else None
          for t, p in (("nr", nr), ("re", re_))}
    for p in (nr, re_):
        shutil.rmtree(p, ignore_errors=True)
        if os.path.exists(p + ".plan.npz"): os.remove(p + ".plan.npz")
    if r.returncode: return tag, "RUN_FAIL " + r.stderr[-600:]
    x = json.load(open(res + ".tmp"))
    x["spot"] = {"d_m": d, "lag_s": 0, "clamped": True, "raster": ras, "raster_sha256": sh(ras), "build_cmds": {"nr": cnr, "re": cre},
                 "hazard_sha256": hz}
    x["writer_identity"] = writer; x["build_summaries"] = bs
    json.dump(x, open(res, "w")); os.remove(res + ".tmp")
    return tag, "ok " + json.dumps({y: x[y] for y in ("witness_checks", "no_route_split")})

if __name__ == "__main__":
    meta = rasters()
    print(json.dumps({k: v for k, v in meta.items() if "nesting" in k}), flush=True)
    keys = [(r, s, d) for r in REC for s in REC[r] for d in D]
    with ThreadPoolExecutor(int(sys.argv[1])) as ex:
        for tag, st in ex.map(job, keys):
            print(tag, st, flush=True)
    print("done", flush=True)
