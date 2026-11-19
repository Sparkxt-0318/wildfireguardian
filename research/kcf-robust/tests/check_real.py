"""Checks on the real data (PROTOCOL.md section 7): R90 raster = committed example rasters; lattice->road-cell
mapping = fireinput.load_geotiff; compiled pass = unchanged engine (latest departure per shelter-origin pair)."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import lib
import reachpass as RP
from wfg_roadlayer import geotiff, fireinput, engine
from wfg_roadlayer.vendor.deadline_field import core

discs = lib.load_discs()
res = {}
WIDE = len(sys.argv) > 1 and sys.argv[1] == "wide"   # amendment 1(a): 6 levels on 4 region-hours
HOURS = ((5, "uiseong_andong_2025"), (11, "uiseong_andong_2025"), (6, "yeongdeok_2025"), (12, "yeongdeok_2025")) if WIDE else \
    ((3, "uiseong_andong_2025"), (9, "yeongdeok_2025"))
LEVELS = (0.0, 0.25, 1.0, 2.5, 5.0, 10.0) if WIDE else (0.0, 0.5, 1.5)
for hh, rid in HOURS:
    T = lib.REPLAY_ISSUES[hh - 3]
    d = lib.known_distance_m(discs, T)
    r5, r8, cls, _ = MA_curve = lib.MA.curve("MEASURED", discs, T, 8)
    m = lib.minutes_r90(d, r5, r8)
    rp = lib.PRODUCT / ("examples/fire_arrival_2025032%dT%02d00Z_MEASURED_8h.tif" % (5, hh))
    if rp.exists():
        ref = geotiff.read(rp).data[::-1].ravel()
        same = np.array_equal(np.isinf(m), np.isinf(ref)) and np.array_equal(m[np.isfinite(m)], ref[np.isfinite(ref)])
    else:
        same = None
    # generic curve == MA.closure_s
    m2 = lib.minutes_from_curve(d, lib.knots_measured(r5 / 1000, r8 / 1000))
    same2 = np.array_equal(np.isinf(m), np.isinf(m2)) and np.array_equal(m[np.isfinite(m)], m2[np.isfinite(m2)])
    reg = lib.region(rid)
    for rr in (0.0, 1.0):  # mapping check also on a dilated raster
        mm = lib.dilate_minutes(m, rr)
        p = Path("/tmp/claude-0/chk.tif"); lib.write_tif(p, mm, T, "check")
        f = fireinput.load_geotiff(p, reg.road, issue_utc=T, horizon_min=None)
        mine = lib.close_s_from_minutes(rid, mm)
        assert f.uncovered == [], len(f.uncovered)
        assert {int(k): v for k, v in f.arrival_s.items()} == mine, rid
    close = lib.close_s_from_minutes(rid, m)
    t = time.time(); rows, inst = lib.run_product(rid, close, T); te = time.time() - t
    g = RP.Graph(reg.road)
    lv = np.stack([lib.close_array_from_minutes(rid, lib.dilate_minutes(m, r)) for r in LEVELS])
    t = time.time(); best, raw, pairs = RP.latest_by_level(g, reg, lv, lib.HORIZON_S, lib.DWELL); tp = time.time() - t
    # engine per pair at level 0 and at the dilated levels
    mism = 0; n = 0
    for k, r in enumerate(LEVELS):
        cl = lib.close_s_from_minutes(rid, lib.dilate_minutes(m, r))
        inst = engine.build_instance(reg.road, cl, lib.HORIZON_S)
        for sn in sorted({s for _, s in pairs}):
            inst.A = [[] for _ in range(len(inst.tail))]
            for j in reg.road.inc_by_node.get(sn, []):
                inst.A[j] = engine.accept(reg.road, cl, sn, lib.HORIZON_S, lib.DWELL)
            fld = core.backward(inst)
            for mi, (oid, s2) in enumerate(pairs):
                if s2 != sn: continue
                on = next(o["node"] for o in reg.origins if o["id"] == oid)
                inst.IB = {on: engine.origin_closure(reg.road, cl, on, lib.HORIZON_S)}
                S = core.issue_set(fld, on)
                inst.IB = {}
                want = -1 if not S else S[-1][1]
                assert (not S) or S[0][0] == 0, ("not downward closed", S)
                assert (not S) or len(S) == 1, ("not one interval", S)
                n += 1
                if want != raw[k, mi]:
                    mism += 1
                    print("MISMATCH", rid, r, oid, sn, want, raw[k, mi])
    # product L per place == compiled max over shelters at level 0
    pl = {o["origin"]["id"]: o["L"] for o in rows if not o["refusal"]}
    bad = sum(1 for oid, L in pl.items() if (L if L is not None else -1) != best[oid][0])
    res["%s_%02d" % (rid, hh)] = dict(levels=list(LEVELS), raster_equal_committed=bool(same), generic_curve_equal=bool(same2), pairs_checked=n, mismatches=mism,
                    places_L_mismatch=bad, product_s=round(te, 1), compiled_3levels_s=round(tp, 2))
    print(rid, hh, res["%s_%02d" % (rid, hh)], flush=True)
Path(__file__).resolve().parents[1].joinpath("out").mkdir(exist_ok=True)
(Path(__file__).resolve().parents[1] / ("out/check_real%s.json" % ("_wide" if WIDE else ""))).write_text(json.dumps(res, indent=1))
