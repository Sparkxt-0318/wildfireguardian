"""Planner cache (schema wfg.planner.cache/1) -> per-origin departure sweeps, exactly as the planner shows them.

This is a line-by-line Python mirror of ``planner/src/api/cache.ts::cacheToModel`` and
``planner/src/domain/plan.ts::planFromAttempts`` (dispatch-plan attempts, re-checks replacing the attempt they re-ran,
research route checks with "시간창 밖" window skips, refused requests), so that the deadline D this tool explains is
the same number the planner displays as 출발 마감. Routes are rebuilt from the cached route-check job and verified
against the router's own ``route_sha256``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

VERDICTS = ("checked_route", "model_no_route", "unresolved")


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf") else None


def _str(v):
    return v if isinstance(v, str) and v else None


def adapt_verdict(v) -> str:
    return v if v in VERDICTS else "unresolved"


@dataclass
class Attempt:
    offset_s: int
    destination_id: str
    verdict: str
    arrival_s: float | None
    job_id: str | None
    reason_code: str | None = None
    recheck_of: str | None = None


@dataclass
class Cell:
    offset_s: int
    verdict: str
    attempts: list
    best: Attempt | None = None
    skipped: str | None = None


@dataclass
class OriginPlan:
    origin_id: str
    sweep: list
    best_verdict: str
    latest_s: int | None
    contiguous_s: int | None
    best: Attempt | None
    kind: str                      # 'dispatch' | 'research' | 'rejected'
    notes: list = field(default_factory=list)


# ------------------------------------------------------------------------------------------------ plan.ts mirror
def combine(verdicts) -> str:
    vs = list(verdicts)
    if not vs:
        return "unresolved"
    if "checked_route" in vs:
        return "checked_route"
    if all(v == "model_no_route" for v in vs):
        return "model_no_route"
    return "unresolved"


def best_checked(attempts):
    """bestCheckedAttempt: earliest arrival, ties -> destination id (localeCompare; for the ASCII OSM ids of the
    caches this equals code-point order, and ties are reported by ``tie_at``)."""
    checked = [a for a in attempts if a.verdict == "checked_route"]
    checked.sort(key=lambda a: (a.arrival_s if a.arrival_s is not None else float("inf"), a.destination_id))
    return checked[0] if checked else None


def tie_at(attempts) -> bool:
    checked = [a for a in attempts if a.verdict == "checked_route"]
    if len(checked) < 2:
        return False
    arr = sorted(a.arrival_s if a.arrival_s is not None else float("inf") for a in checked)
    return arr[0] == arr[1]


def build_sweep(offsets, attempts, skipped=None):
    skipped = skipped or {}
    offs = set(int(o) for o in offsets) | {a.offset_s for a in attempts} | {int(k) for k in skipped}
    out = []
    for o in sorted(offs):
        here = [a for a in attempts if a.offset_s == o]
        cell = Cell(offset_s=o, verdict=combine(a.verdict for a in here), attempts=here, best=best_checked(here))
        if skipped.get(o) and not here:
            cell.skipped = skipped[o]
        out.append(cell)
    return out


def is_window_skip(cell: Cell) -> bool:
    return cell.skipped == "window_unsatisfiable"


def latest_safe(sweep):
    latest = None
    for c in sweep:
        if c.verdict == "checked_route" and (latest is None or c.offset_s > latest):
            latest = c.offset_s
    return latest


def contiguous_safe(sweep):
    latest = None
    for c in sorted((c for c in sweep if not is_window_skip(c)), key=lambda c: c.offset_s):
        if c.verdict != "checked_route":
            break
        latest = c.offset_s
    return latest


def plan_from_attempts(origin_id, offsets, attempts, kind, skipped=None) -> OriginPlan:
    sweep = build_sweep(offsets, attempts, skipped)
    latest = latest_safe(sweep)
    best = None
    if latest is not None:
        cell = next(c for c in sweep if c.offset_s == latest)
        best = cell.best
    return OriginPlan(origin_id=origin_id, sweep=sweep, best_verdict=combine(a.verdict for a in attempts), latest_s=latest,
                      contiguous_s=contiguous_safe(sweep), best=best, kind=kind)


def unresolved_plan(origin_id, offsets, kind="rejected") -> OriginPlan:
    sweep = [Cell(offset_s=o, verdict="unresolved", attempts=[]) for o in sorted(set(int(x) for x in offsets))]
    return OriginPlan(origin_id=origin_id, sweep=sweep, best_verdict="unresolved", latest_s=None, contiguous_s=None,
                      best=None, kind=kind)


# ------------------------------------------------------------------------------------------------ cache.ts mirror
def _attempt_from_wire(a: dict) -> Attempt:
    v = adapt_verdict(a.get("verdict"))
    return Attempt(offset_s=int(float(a["depart_offset_s"])), destination_id=str(a["destination_id"]), verdict=v,
                   arrival_s=_num(a.get("arrival_s")), job_id=_str(a.get("route_check_job_id")),
                   reason_code=_str(a.get("reason_code")) if v == "unresolved" else None)


def _attempt_from_route(job: dict, destination_id: str, offset_s: int) -> Attempt:
    res = job.get("result") if job.get("status") == "done" else None
    verdict = adapt_verdict(res.get("verdict")) if res else "unresolved"
    return Attempt(offset_s=offset_s, destination_id=destination_id,
                   verdict=verdict if job.get("status") == "done" else "unresolved",
                   arrival_s=_num(res.get("arrival_s")) if (res and verdict == "checked_route") else None,
                   job_id=_str(job.get("job_id")),
                   reason_code=(_str(res.get("reason_code")) if res else _str((job.get("error") or {}).get("code")))
                   if verdict == "unresolved" else None)


class CacheModel:
    """Origins of one cache file with the planner's sweeps, plus the route-check jobs by id."""

    def __init__(self, doc: dict):
        self.doc = doc
        self.jobs: dict = {}
        self.rechecks: dict = {}
        for key, job in (doc.get("route_checks") or {}).items():
            if not isinstance(job, dict):
                continue
            of = job.get("recheck_of") if isinstance(job.get("recheck_of"), str) and job.get("recheck_of") else None
            if of:
                self.rechecks[of] = job
                if job.get("job_id"):
                    self.jobs[job["job_id"]] = job
                if key != of and key not in self.jobs:
                    self.jobs[key] = job
            else:
                if key not in self.jobs:
                    self.jobs[key] = job
                if job.get("job_id") and job["job_id"] not in self.jobs:
                    self.jobs[job["job_id"]] = job
        self.plans: dict = {}
        self._dispatch()
        self._research()

    # -- dispatch plans --------------------------------------------------------------------------------------------
    def _with_rechecks(self, p: OriginPlan) -> OriginPlan:
        attempts = [a for c in p.sweep for a in c.attempts]
        if not any(a.job_id and a.job_id in self.rechecks for a in attempts):
            return p
        new = []
        for a in attempts:
            rj = self.rechecks.get(a.job_id) if a.job_id else None
            if rj is None:
                new.append(a)
            else:
                b = _attempt_from_route(rj, a.destination_id, a.offset_s)
                b.recheck_of = a.job_id
                new.append(b)
        out = plan_from_attempts(p.origin_id, [c.offset_s for c in p.sweep], new, p.kind)
        out.notes.append("recheck_replaced_attempts")
        return out

    def _dispatch(self):
        doc = self.doc
        all_offsets = sorted({int(float(o)) for r in doc.get("requests") or [] for o in r.get("depart_offsets_s") or []})
        for job in doc.get("plans") or []:
            if not isinstance(job, dict):
                continue
            req = job.get("request") or {}
            offsets = sorted({int(float(o)) for o in req.get("depart_offsets_s") or []})
            result = job.get("result") if job.get("status") == "done" else None
            for p in (result or {}).get("plans") or []:
                plan = plan_from_attempts(p["origin_id"], offsets, [_attempt_from_wire(a) for a in p.get("attempts") or []], "dispatch")
                self.plans[p["origin_id"]] = self._with_rechecks(plan)
            for r in (result or {}).get("rejected_origins") or []:
                self.plans[r["origin_id"]] = unresolved_plan(r["origin_id"], offsets)
            if job.get("status") == "failed":
                for o in req.get("origins") or []:
                    if o["id"] not in self.plans:
                        self.plans[o["id"]] = unresolved_plan(o["id"], offsets)
        for rej in doc.get("rejected_requests") or []:
            if rej.get("kind") != "dispatch_plan":
                continue
            req = rej.get("request") or {}
            ids = rej.get("origins") if isinstance(rej.get("origins"), list) else [str(o.get("id")) for o in req.get("origins") or []]
            offs = req.get("depart_offsets_s") or all_offsets
            for i in ids:
                if i not in self.plans:
                    self.plans[i] = unresolved_plan(i, offs)

    # -- research origins ------------------------------------------------------------------------------------------
    def _refused_research(self) -> set:
        out = set()
        for r in self.doc.get("rejected_requests") or []:
            if r.get("kind") != "route_check":
                continue
            req = r.get("request") or {}
            ref = req.get("client_ref")
            oid = r.get("origin_id") or (ref[len("planner-precompute:"):] if isinstance(ref, str) and ref.startswith("planner-precompute:") else None)
            off = r.get("depart_offset_s", req.get("depart_offset_s"))
            if oid and off is not None:
                out.add((oid, int(float(off))))
        return out

    def _research(self):
        refused = self._refused_research()
        slots: dict = {}
        for rc in self.doc.get("research_checks") or []:
            slot = slots.setdefault(rc["origin_id"], {"attempts": [], "offsets": [], "skipped": {}})
            off = int(float(rc["depart_offset_s"]))
            slot["offsets"].append(off)
            jid = rc.get("job_id")
            job = (self.jobs.get(jid) or self.rechecks.get(jid)) if jid else None
            if job:
                re = self.rechecks.get(jid)
                a = _attempt_from_route(re or job, rc["destination_id"], off)
                if re:
                    a.recheck_of = jid
                slot["attempts"].append(a)
            elif rc.get("skipped") in ("WINDOW_UNSATISFIABLE", "window_unsatisfiable") and (rc["origin_id"], off) not in refused:
                slot["skipped"][off] = "window_unsatisfiable"
            elif rc.get("skipped"):
                slot["attempts"].append(Attempt(off, rc["destination_id"], "unresolved", None, None, rc["skipped"]))
            else:
                slot["attempts"].append(Attempt(off, rc["destination_id"], "unresolved", None, None, None))
        for oid, slot in slots.items():
            self.plans[oid] = plan_from_attempts(oid, slot["offsets"], slot["attempts"], "research", slot["skipped"])

    def job(self, job_id):
        return self.jobs.get(job_id) if job_id else None


# ------------------------------------------------------------------------------------------------ routes
def canonical_sha256(x) -> str:
    """The router's route hash: sha256 of compact sorted-key JSON (rda_worker_v1_1.canonical)."""
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class RouteError(ValueError):
    pass


def reconstruct_legs(job: dict) -> dict:
    """Rebuild the router's legs from a cached checked route (vertex times, node ids, edge ids, merged waits).

    ``api/runner.py::route_feature`` emits one vertex per EDGE leg (its end time) and, for a run of 1 s WAIT legs at a
    node, one extra vertex at the same node with the run's end time; ``waits`` lists those runs. The rebuilt legs are
    accepted only if their canonical hash equals the recorded ``route_sha256`` (so the reconstruction is exact)."""
    res = job.get("result") or {}
    if job.get("status") != "done" or res.get("verdict") != "checked_route" or not res.get("route"):
        raise RouteError("not a checked route")
    pr = res["route"]["properties"]
    t, n, e, waits = pr["times_s"], pr["node_ids"], pr["edge_ids"], list(pr.get("waits") or [])
    if len(t) != len(n) or not t:
        raise RouteError("vertex arrays differ in length")
    legs, ei, wi = [], 0, 0
    for i in range(1, len(t)):
        w = waits[wi] if wi < len(waits) else None
        if w is not None and n[i] == n[i - 1] == w["node_id"] and int(w["from_s"]) == t[i - 1] and int(w["to_s"]) == t[i]:
            for s in range(int(t[i - 1]), int(t[i])):
                legs.append({"kind": "WAIT", "node": n[i], "start": s, "end": s + 1})
            wi += 1
            continue
        if ei >= len(e):
            raise RouteError("more vertices than edges")
        legs.append({"kind": "EDGE", "edge": e[ei], "start": t[i - 1], "end": t[i], "from_fraction": 0, "to_fraction": 1})
        ei += 1
    if ei != len(e) or wi != len(waits):
        raise RouteError("edges or waits left unused")
    rebuilt = canonical_sha256({"legs": legs, "destination": n[-1], "arrival": t[-1]})
    if pr.get("route_sha256") is None or rebuilt != pr["route_sha256"]:
        raise RouteError("rebuilt legs do not hash to route_sha256")
    if int(res["arrival_s"]) != t[-1] or int(res["departure_s"]) != t[0]:
        raise RouteError("arrival/departure differ from the vertex times")
    return {"legs": legs, "start_node": n[0], "destination": n[-1], "departure": t[0], "arrival": t[-1],
            "route_sha256": pr["route_sha256"], "node_ids": n}
