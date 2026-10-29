"""Track 1C-3 campaigns C1 to C4 (observing system simulation experiment) on the 15 frozen Korean windows, 20 missions.

Truths (never shown to the router):
  holdout_trajectory     trajectories 512..611 of the export v3 rollout (N = 1024, seed 0, replay mode), uniform sub-hour
                         timing; forecast members are drawn only from trajectories 0..511.
  reconstructed_arrival  the Zenodo time-of-arrival raster of the fire (hash-checked against the export record).
Forecast sources (members):
  C1  v1_K4 (the frozen packet), v1_K16 (frozen bridge law, 16 members, seed 20261008), v2_K4 and v2_K16 (first
      trajectories), v2_K16_ordered, v2_K16_fs (forward selection on the edge-arrival distance over 0..511, extremes).
  C2  rate_x0.5, rate_x1, rate_x2 (independent per-cell draws from q_c = 1 - (1 - q)^c, common random numbers, K = 16,
      seed 20261008; at the one-hour horizon this is the trajectory law of the rate-scaled model), persistence (present
      fire active over the whole horizon, no new ignitions), uniform (spatially uniform probability with the forecast's
      expected ignition count, K = 16), and the policy that ignores the forecast: current_state_only (present fire with its
      remaining-time enclosure, no new ignitions).
  C3  v2 first K trajectories, K in {4, 8, 16, 32}, rules all and k_of_m with k/m in {0.9, 0.75} (k = ceil(f m)).
  C4  truth = reconstructed arrival; forecasts v1_K4, v2_K16, current_state_only, persistence.
Decisions: wfg_osse.harness.decide (SIPP planner, cheap per-member checker). Records: Contract E JSON lines (gzip).

  python research/synthetic-truth/run_campaigns.py --exports DIR --toa-dir DIR --out research/synthetic-truth/data [--regions ...]
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import platform
import sys
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "synthetic-truth" / "src"))
from wfg_osse import harness, truth as TR  # noqa: E402  (puts scenario-members and sipp-routing on sys.path)
import bridge_v2 as B2  # noqa: E402
from wfg_members import acceptance as A  # noqa: E402
from wfg_members import coverage, decide as D, kit, reduction  # noqa: E402
from wfg_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import sipp_plan  # noqa: E402

HOLDOUT = list(range(512, 612))
POOL = 512
V1_SEED = 20261008
TOA_FILES = {"KFS_01": "KFS_01_pswt_ok_toa.tif", "KFS_02": "KFS_02_pswt_ok_toa.tif", "KFS_05": "KFS_05_pswt_ok_toa.tif",
             "KFS_11": "KFS_11_pswt_ok_toa.tif"}


def crop(a, w):
    return a if w is None else a[..., w["r0"]:w["r1"] + 1, w["c0"]:w["c1"] + 1]


def graph_events(ev_native, shape):
    H, W = shape
    out = []
    for s in range(ev_native.shape[0]):
        flat = ev_native[s].ravel()
        idx = np.flatnonzero(np.isfinite(flat))
        out.append({(H - 1 - int(i) // W) * W + int(i) % W: F(float(flat[i])) for i in idx})
    return out


class Window:
    def __init__(self, region, tag, event, missions, exports, toa_dir):
        K = kit.install()
        self.K = K
        self.region, self.tag, self.event = region, tag, event
        p = kit.paths(region, tag, event)
        self.p = p
        self.graph = json.loads(p["graph"].read_text())
        self.fc, self.record = B2.load_export(p["export_npz"], p["export_record"])
        self.T = float(self.fc["contract__cell_duration_s"])
        self.window = B2.frozen_window(p["packet"])
        self.v1 = ContactModel.from_packet(p["packet"], label="v1_K4")
        md = json.loads((p["packet"] / "NATIVE_METADATA.json").read_text())
        self.shape = tuple(md["shape"])
        with np.load(p["packet"] / "constructed_arrays.npz") as a:
            cur_native = a["current_active"].copy()
        self.kern = coverage.Kernels(md["affine_transform"], K["bridge"].settings_for(self.T), self.record["epsg"], self.shape)
        self.cur_flux = self.kern.of_mask(cur_native)
        rec = json.loads((Path(exports) / event / ("FORECAST_RECORD_%s.json" % tag)).read_text())
        npz = Path(exports) / event / ("FORECAST_%s.npz" % tag)
        if kit.sha256_file(npz) != rec["npz_sha256"]:
            raise SystemExit("V3_HASH")
        self.v3_sha = rec["npz_sha256"]
        with np.load(npz) as z:
            self.fbh = z["trajectory_first_burn_hour"].copy()
        self.traj_events = graph_events(crop(B2.ignition_seconds(self.fbh, range(self.fbh.shape[0])), self.window), self.shape)
        self.missions = []
        for m in missions:
            req = json.loads(kit.paths(region, tag, event, m)["request"].read_text())
            self.missions.append((m, req, sipp_plan(self.graph, req, self.v1.shared_only())))
        bv = self.fc["source_burned_area_valid"]
        known_burned = bv & (np.nan_to_num(self.fc["source_burned_area"]) == 1)
        self.cq = np.where(self.fc["probability_valid"], self.fc["new_burn_probability"], 0.0)
        self.cq[known_burned] = 0.0
        self.cq = np.where(np.isfinite(self.cq), self.cq, 0.0)
        self.support = self.fc["probability_valid"] & ~known_burned
        H, W = self.shape
        sup_w = crop(self.support, self.window)
        self.brier_cells = [(H - 1 - r) * W + c for r, c in zip(*np.nonzero(sup_w))]
        self.holdouts = [TR.Truth("holdout_trajectory", "trajectory_%d" % j, dict(self.traj_events[j]), list(self.v1.current),
                                  self.v1.R, self.v1.T, {"trajectory_index": j}) for j in HOLDOUT]
        self.toa = None
        if toa_dir:
            ev = next(e for e in json.loads((REPO / "forecast/data/environment/events.json").read_text()) if e["id"] == event)
            self.toa = TR.reconstructed_arrival(Path(toa_dir) / TOA_FILES[event], t0_utc=ev["t0_utc"], cutoff_utc=kit.cutoff_iso(tag),
                                                window=self.window, export=self.fc,
                                                expected_sha256=self.record["data_identity_sha256"]["regions/%s/arrival_time_hours.tif" % event],
                                                current_graph=self.v1.current, R=self.v1.R, T=self.v1.T, shape=self.shape)
        self.clair = {}

    # ------------------------------------------------------------------ forecast sources
    def independent(self, q_full, K, seed, label):
        ev = self.K["bridge"].draw_ignitions(q_full, K, seed, 3600.0)
        return self.v1.with_events(graph_events(crop(ev, self.window), self.shape), ["%s:%d" % (label, k) for k in range(K)], label=label)

    def trajectories(self, indices, label, timing="uniform", weights=None):
        if timing == "uniform":
            evs = [self.traj_events[j] for j in indices]
        else:
            evs = graph_events(crop(B2.ignition_seconds(self.fbh, indices, timing=timing), self.window), self.shape)
        return self.v1.with_events(evs, ["%s:%d" % (label, k) for k in range(len(indices))], weights=weights, label=label)

    def persistence(self):
        m = self.v1.shared_only(label="persistence")
        if m.R > 0 or m.current:
            m.R = F(3600)
        return m

    def forward_selection(self, K):
        burn = set(self.v1.current) | {c for ev in self.traj_events[:POOL] for c in ev}
        expo = reduction.EdgeExposure(self.graph, burn, self.K["core"])
        cur, R = set(self.v1.current), float(self.v1.R)
        A_ = reduction.edge_arrival_matrix(expo, [{c: float(b) for c, b in ev.items()} for ev in self.traj_events[:POOL]],
                                           float(self.v1.T), 3600.0, cur, R)
        if not A_.size:
            return self.trajectories(list(range(K)), "v2_K%d_fs" % K), {"note": "no road-relevant cells"}
        C = reduction.distance_edge_arrival(A_, expo.edge_len)
        a_shared = expo.first_unsafe({}, float(self.v1.T), 3600.0, cur, R)
        eid = {e["id"]: i for i, e in enumerate(self.graph["edges"])}
        cors, sf = [], []
        for m, req, sh in self.missions:
            cols = sorted({expo.col[eid[l["edge"]]] for l in sh["legs"] if l["kind"] == "EDGE" and eid[l["edge"]] in expo.col})
            cors.append(cols)
            sf.append(float(a_shared[cols].min()) if cols else math.inf)
        sel = reduction.reduce_members(C, K, "forward_selection", A=A_, corridors=cors, shared_first=sf)
        return self.trajectories(sel["indices"], "v2_K%d_fs" % K, weights=sel["weights"]), sel

    # ------------------------------------------------------------------ one forecast source on all missions
    def run(self, label, model, truths, *, rule=None, weights=None, campaign, sink, extra=None):
        for m, req0, shared in self.missions:
            req = B2.rekey_request_k(req0, model.ids, kit.cutoff_iso(self.tag))
            t0 = time.perf_counter()
            dec = harness.decide(self.graph, req, model, rule=rule or {"rule": "all", "k": len(model.ids), "m": len(model.ids)},
                                 weights=weights if weights is not None else model.weights, kernels=self.kern, current_flux=self.cur_flux)
            wall = time.perf_counter() - t0
            recs = harness.score_against(self.graph, req, dec, truths, cutoff=self.tag, region=self.region, mission=m,
                                         forecast_source=label, shared_route=shared, kernels=self.kern, current_flux=self.cur_flux,
                                         clair_cache=self.clair)
            for r, t in zip(recs, truths):
                r.update({"campaign": campaign, "event": self.event, "parent_fire": kit.PARENT_FIRE[self.region],
                          "members": len(model.ids), "rule": dec["rule"]["rule"], "k": dec["rule"].get("k"), "m": dec["rule"].get("m"),
                          "reason": dec["reason"], "decision_wall_s": wall, "planner_calls": dec.get("planner_calls"),
                          "brier": harness.brier(model.events, model.weights, t.births, self.brier_cells) if not t.observed else None,
                          "truth_new_ignitions": len(t.births)})
                if extra:
                    r.update(extra)
                sink.append(r)
            if campaign == "C4":
                sink_legs.append({"region": self.region, "cutoff": self.tag, "mission": m, "forecast_source": label,
                                  "verdict": dec["verdict"], "arrival_s": dec["arrival_s"], "legs": dec["legs"]})


sink_legs = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exports", required=True)
    ap.add_argument("--toa-dir", default=None)
    ap.add_argument("--out", default=str(HERE / "data"))
    ap.add_argument("--regions", nargs="*")
    ap.add_argument("--campaigns", nargs="*", default=["C1", "C2", "C3", "C4"])
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    kit.verify_inputs()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sinks = {c: [] for c in a.campaigns}
    host = {"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(),
            "loadavg_start": os.getloadavg(), "note": "host-specific Linux measurement on a shared host"}
    t_all = time.perf_counter()
    for region, tag, event, ms in kit.PANEL:
        if a.regions and region not in a.regions:
            continue
        w = Window(region, tag, event, ms, a.exports, a.toa_dir)
        print("window", region, tag, "holdouts", len(w.holdouts), "toa ignitions", None if w.toa is None else len(w.toa.births), flush=True)
        if "C1" in sinks:
            w.run("v1_K4", w.v1, w.holdouts, campaign="C1", sink=sinks["C1"])
            w.run("v1_K16", w.independent(w.cq, 16, V1_SEED, "v1_K16"), w.holdouts, campaign="C1", sink=sinks["C1"])
            w.run("v2_K4", w.trajectories(range(4), "v2_K4"), w.holdouts, campaign="C1", sink=sinks["C1"])
            w.run("v2_K16", w.trajectories(range(16), "v2_K16"), w.holdouts, campaign="C1", sink=sinks["C1"])
            w.run("v2_K16_ordered", w.trajectories(list(range(16)), "v2_K16_ordered", timing="ordered"), w.holdouts, campaign="C1",
                  sink=sinks["C1"])
            fs, sel = w.forward_selection(16)
            w.run("v2_K16_fs", fs, w.holdouts, campaign="C1", sink=sinks["C1"], extra={"selection_indices": sel.get("indices")})
        if "C2" in sinks:
            for c in (0.5, 1.0, 2.0):
                qc = 1.0 - (1.0 - w.cq) ** c
                w.run("rate_x%g" % c, w.independent(qc, 16, V1_SEED, "rate_x%g" % c), w.holdouts, campaign="C2", sink=sinks["C2"])
            w.run("persistence", w.persistence(), w.holdouts, campaign="C2", sink=sinks["C2"])
            n_sup = int(w.support.sum())
            qu = np.where(w.support, w.cq.sum() / n_sup if n_sup else 0.0, 0.0)
            w.run("uniform", w.independent(qu, 16, V1_SEED, "uniform"), w.holdouts, campaign="C2", sink=sinks["C2"])
            w.run("current_state_only", w.v1.shared_only(label="current_state_only"), w.holdouts, campaign="C2", sink=sinks["C2"])
        if "C3" in sinks:
            for K in (4, 8, 16, 32):
                model = w.trajectories(range(K), "v2_K%d" % K)
                for f in (1.0, 0.9, 0.75):
                    rule = {"rule": "all", "k": K, "m": K} if f == 1.0 else A.k_of_m_rule(K, f)
                    w.run("v2_K%d" % K, model, w.holdouts, rule=rule, campaign="C3", sink=sinks["C3"], extra={"k_over_m_target": f})
        if "C4" in sinks and w.toa is not None:
            for label, model in (("v1_K4", w.v1), ("v2_K16", w.trajectories(range(16), "v2_K16")),
                                 ("current_state_only", w.v1.shared_only(label="current_state_only")), ("persistence", w.persistence())):
                w.run(label, model, [w.toa], campaign="C4", sink=sinks["C4"], extra={"toa_sha256": w.toa.meta["toa_sha256"]})
    suffix = ("_" + a.tag) if a.tag else ""
    for c, rows in sinks.items():
        with gzip.open(out / ("%s%s.jsonl.gz" % (c, suffix)), "wt") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")
    if sink_legs:
        (out / ("C4_journeys%s.json" % suffix)).write_text(json.dumps(sink_legs, default=str) + "\n")
    host.update(loadavg_end=os.getloadavg(), total_wall_s=time.perf_counter() - t_all, holdout_indices=[HOLDOUT[0], HOLDOUT[-1]],
                member_pool=POOL, v1_seed=V1_SEED)
    (out / ("host%s.json" % suffix)).write_text(json.dumps(host, indent=1) + "\n")


if __name__ == "__main__":
    main()
