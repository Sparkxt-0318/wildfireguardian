"""Authoritative application-facing journey decision (schema wfg.journey-decision/1).

One function, ``decide``, turns the raw centre-surrogate search result, the mandatory whole-road check, the
publication timing and the identity evidence into ONE status that an application may present. The raw search
status (for example CONDITIONAL_OPTIMUM) is never an application outcome on its own: it is kept only under
``diagnostics``. Pure python (stdlib only); inputs are deep-copied, so later mutation of the inputs cannot change
a returned decision. See API_CONTRACT.md for the status contract, the precedence table and the claim scopes.

``decision_from_worker_record`` derives the same decision from frozen campaign worker records
(reference cold_worker, candidate cand_worker_final and ablation worker formats), read-only.
No physical-safety claim is made by any status.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from fractions import Fraction

SCHEMA = "wfg.journey-decision/1"
MODULE_VERSION = "wfg.journey-decision.module/1.0"

SUCCESS_STATUSES = ("CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN", "CHECKED_JOURNEY_CENTRE_OPTIMUM", "CHECKED_JOURNEY_FEASIBLE")
AUTHORITATIVE_STATUSES = SUCCESS_STATUSES + (
    "FULL_MODEL_REFUSAL_PROVEN", "CENTRE_MODEL_REFUSAL_ONLY", "UNRESOLVED", "INVALID_INPUT", "UNSUPPORTED_INPUT",
    "AT_ISSUE_FAILURE", "DISCONNECTED")

UNRESOLVED_REASONS = {
    "CANDIDATE_REJECTED_BY_WHOLE_ROAD": "The returned candidate route failed the mandatory whole-road check (definite rejection). "
                                        "This is not a refusal; alternative routes may exist.",
    "WHOLE_ROAD_CHECK_UNRESOLVED": "The whole-road check completed without certifying or rejecting the route.",
    "WHOLE_ROAD_CHECK_NOT_STARTED": "The whole-road check did not run (NOT_RUN) or no check record is present.",
    "WHOLE_ROAD_CHECK_INTERRUPTED": "The whole-road check started or initialised but did not complete (deadline, wall or memory cap, "
                                    "or an authority change during the check).",
    "LATE_RESULT": "The result was not published before the shared deadline (or its publication time is not proven).",
    "STALE_OR_IDENTITY_MISMATCH": "An identity (graph, source packet, settings, checker module, members, or route binding) did "
                                  "not match, or a required identity could not be verified.",
    "SEARCH_TIMEOUT": "The search stopped at a cap without a whole-road-certified route. A timeout is never a refusal.",
    "NO_SOLVER_WITNESS": "The search returned no route and no refusal.",
    "CONTRADICTORY_EVIDENCE": "A route certificate and a refusal certificate contradict each other; nothing is concluded.",
    "INVALID_INPUT": "Pass-through: the search refused the input as invalid.",
    "UNSUPPORTED_INPUT": "Pass-through: the input is outside the supported scope.",
    "AT_ISSUE_FAILURE": "Pass-through: the mission is already in violation at issue time.",
    "DISCONNECTED": "Pass-through: no destination is reachable in the declared directed graph and turn rules (forecast independent).",
}

# Whole-road UNRESOLVED reasons that mean the check did not complete (as opposed to completing unresolved).
INTERRUPTED_CHECK_REASONS = frozenset({
    "CHECK_STARTED_NOT_COMPLETED", "CHECK_INITIALIZATION_NOT_COMPLETED", "AUTHORITY_CHANGED_DURING_ADAPTIVE_FALLBACK",
    "WALL_CAP_AFTER_CHECK", "WALL_CAP_DURING_FINALIZATION", "WALL_CAP_AFTER_ADAPTIVE_FALLBACK", "RSS_LIMIT",
    "RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK", "NO_REMAINING_COMPLETE_BUDGET", "INCOMPLETE"})
_INTERRUPTED_PREFIXES = ("WALL_CAP", "RSS_LIMIT", "AUTHORITY_CHANGED", "CHECK_STARTED", "CHECK_INITIALIZATION", "DEADLINE")

PASS_THROUGH = {"INVALID_INPUT": "INVALID_INPUT", "UNSUPPORTED": "UNSUPPORTED_INPUT", "AT_ISSUE_FAILURE": "AT_ISSUE_FAILURE",
                "DISCONNECTED": "DISCONNECTED"}
CENTRE_OPTIMUM_CLAIMS = frozenset({"CONDITIONAL_OPTIMUM", "EXACT_OPTIMUM"})

# Identity fields. A field is VERIFIED when both sides carry it and they are equal; it is a MISMATCH when they
# differ or when an expected value has no observed counterpart (fail closed). A field carried by neither side, or
# only observed, is UNPINNED (recorded, not compared). Required fields must be verified for any success.
IDENTITY_FIELDS = ("graph_file_sha256", "graph_canonical_sha256", "hazard_file_sha256", "source_report_sha256",
                   "source_npz_sha256", "checker_source_identity", "construction_id", "settings_digest",
                   "checker_module_sha256", "member_ids", "checked_member_ids")
REQUIRED_IDENTITY_FIELDS = ("graph_file_sha256", "graph_canonical_sha256", "source_report_sha256", "source_npz_sha256",
                            "member_ids")
_SET_FIELDS = ("member_ids", "checked_member_ids")

CLAIM_SCOPES = {
    "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN": "Route passed the mandatory whole-road check before the deadline with verified identities, and a "
        "supplied complete relaxation lower bound equals its arrival, so it is earliest among whole-road-feasible routes on the "
        "declared lattice for the supplied members. The decision records, but does not re-verify, the relaxation's mathematics.",
    "CHECKED_JOURNEY_CENTRE_OPTIMUM": "Route passed the mandatory whole-road check (single returned path) before the deadline with "
        "verified identities. Optimality is proven only for the cell-centre surrogate search; whole-road optimality is NOT claimed.",
    "CHECKED_JOURNEY_FEASIBLE": "Route passed the mandatory whole-road check (single returned path) before the deadline with verified "
        "identities. No optimality claim (CHECKED_ROUTE, checked timeout incumbent, or no optimality claim by the search).",
    "FULL_MODEL_REFUSAL_PROVEN": "The centre search proved infeasibility and a supplied complete relaxation certificate extends the "
        "refusal to the declared whole-road scope (recorded, not re-verified here).",
    "CENTRE_MODEL_REFUSAL_ONLY": "Refusal proven only for the centre surrogate (exact search over the supplied members); not a "
        "whole-road refusal unless the dose is not involved and a contact-only relaxation is certified.",
    "UNRESOLVED": "Nothing may be presented as a journey or as a refusal.",
    "INVALID_INPUT": "Input refused as invalid; no journey, no refusal.",
    "UNSUPPORTED_INPUT": "Input outside supported scope; no journey, no refusal.",
    "AT_ISSUE_FAILURE": "Mission violated at issue time under the supplied members; no journey.",
    "DISCONNECTED": "Structural: no destination reachable under the declared graph and turn rules (independent of forecast).",
}


def _canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


def canonical_sha256(x):
    return hashlib.sha256(_canon(x).encode()).hexdigest()


def _exact(v):
    """Exact rational from int/float/str 'p/q'/{'__wfg_fraction__': {...}}; None if not a finite number."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, dict) and "__wfg_fraction__" in v:
        f = v["__wfg_fraction__"]
        try:
            return Fraction(int(f["numerator"]), int(f["denominator"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            return None
    if isinstance(v, (int, Fraction)):
        return Fraction(v)
    if isinstance(v, float):
        return Fraction(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            return Fraction(v)
        except (ValueError, ZeroDivisionError):
            return None
    return None


def route_of(search_result):
    """(route, role): the primary route if a destination is present, else a checked incumbent, else (None, None)."""
    if not isinstance(search_result, dict):
        return None, None
    if search_result.get("destination") is not None:
        return search_result, "PRIMARY"
    inc = search_result.get("checked_incumbent")
    if isinstance(inc, dict) and inc.get("destination") is not None:
        return inc, "CHECKED_TIMEOUT_INCUMBENT"
    return None, None


def binding_of(search_result):
    """Binding of a decision to one exact result/request/generation (used by CheckedRoutingSession.commit)."""
    sr = search_result if isinstance(search_result, dict) else {}
    route, role = route_of(sr)
    return {
        "route_role": role,
        "route_sha256": None if route is None else canonical_sha256(
            {"legs": route.get("legs", []), "destination": route.get("destination"), "arrival": route.get("arrival")}),
        "request_sha256": canonical_sha256(sr["request"]) if isinstance(sr.get("request"), dict) else None,
        "request_generation": sr.get("request_generation"),
        "hazard_version": sr.get("hazard_version"),
    }


def _norm_identity_value(field, v):
    if v is None:
        return None
    if field in _SET_FIELDS:
        try:
            return sorted(str(x) for x in v)
        except TypeError:
            return ["<unorderable>", _canon(v)]
    return v


def _identity_block(expected, observed):
    expected = expected if isinstance(expected, dict) else {}
    observed = observed if isinstance(observed, dict) else {}
    fields = list(IDENTITY_FIELDS) + sorted((set(expected) | set(observed)) - set(IDENTITY_FIELDS))
    out, mismatched, unverified_required, unpinned = {}, [], [], []
    for f in fields:
        e = _norm_identity_value(f, expected.get(f)); o = _norm_identity_value(f, observed.get(f))
        if e is None and o is None:
            match, state = None, "UNPINNED"
        elif e is None:
            match, state = None, "UNPINNED_OBSERVED_ONLY"
        elif o is None:
            match, state = False, "EXPECTED_NOT_OBSERVED"
        else:
            match = _canon(e) == _canon(o); state = "VERIFIED" if match else "MISMATCH"
        out[f] = {"expected": e, "observed": o, "match": match, "state": state}
        if match is False:
            mismatched.append(f)
        if f in REQUIRED_IDENTITY_FIELDS and match is not True:
            unverified_required.append(f)
        if match is None:
            unpinned.append(f)
    return {"fields": out, "mismatched_fields": mismatched, "unverified_required_fields": unverified_required,
            "unpinned_fields": unpinned, "required_fields": list(REQUIRED_IDENTITY_FIELDS),
            "all_required_verified": not unverified_required and not mismatched}


def _route_binding(route, whole_road_check):
    """Is the whole-road check about this route? Compares the check's mission arrival with the route arrival."""
    if route is None or not isinstance(whole_road_check, dict):
        return {"route_arrival": None if route is None else route.get("arrival"), "check_mission_arrival": None, "match": None}
    mission = whole_road_check.get("mission")
    if not isinstance(mission, dict) and isinstance(whole_road_check.get("checked_result"), dict):
        mission = whole_road_check["checked_result"].get("mission")
    ca = _exact(mission.get("arrival")) if isinstance(mission, dict) else None
    ra = _exact(route.get("arrival"))
    if ca is None or ra is None:
        return {"route_arrival": route.get("arrival"), "check_mission_arrival": None if ca is None else str(ca), "match": None}
    return {"route_arrival": route.get("arrival"), "check_mission_arrival": str(ca), "match": ca == ra}


def _summ_search(sr):
    if not isinstance(sr, dict):
        return {"present": False}
    m = sr.get("metrics") if isinstance(sr.get("metrics"), dict) else {}
    return {"present": True, "status": sr.get("status"), "reason": sr.get("reason"), "solver_status": sr.get("solver_status"),
            "arrival": sr.get("arrival"), "destination": sr.get("destination"), "n_legs": len(sr.get("legs") or []),
            "hazard_version": sr.get("hazard_version"), "request_generation": sr.get("request_generation"),
            "certificate_conditions": sr.get("certificate_conditions"),
            "per_member": {k: {"dose": v.get("dose"), "peak": v.get("peak")} for k, v in (sr.get("per_member") or {}).items()
                           if isinstance(v, dict)},
            "metrics": {k: m.get(k) for k in ("labels", "expansions", "wall_s", "peak_rss_mb") if k in m},
            "role": "raw centre-surrogate search sub-result; not an application outcome"}


def _summ_incumbent(sr):
    inc = sr.get("checked_incumbent") if isinstance(sr, dict) else None
    if not isinstance(inc, dict):
        return None
    return {"status": inc.get("status"), "arrival": inc.get("arrival"), "destination": inc.get("destination"),
            "n_legs": len(inc.get("legs") or []), "proof_level": inc.get("proof_level")}


def _summ_check(w):
    if not isinstance(w, dict):
        return {"present": False, "status": None, "reason": "NO_WHOLE_ROAD_CHECK_RECORD"}
    rad = w.get("radiation") if isinstance(w.get("radiation"), dict) else {}
    mission = w.get("mission") if isinstance(w.get("mission"), dict) else {}
    contact = w.get("contact") if isinstance(w.get("contact"), dict) else {}
    out = {"present": True, "status": w.get("status"), "reason": w.get("reason"), "schema": w.get("schema"),
           "contact_status": contact.get("status"), "mission_status": mission.get("status"),
           "radiation_status": rad.get("status"), "per_member_bounds": rad.get("per_member"),
           "fixed_path_only": w.get("fixed_path_only"),
           "global_optimality_or_infeasibility_claim": w.get("global_optimality_or_infeasibility_claim"),
           "elapsed_s": w.get("elapsed_s"), "source_identity": w.get("source_identity"),
           "graph_identity": w.get("graph_identity"), "settings_identity": w.get("settings_identity")}
    ad = w.get("adaptive_fallback")
    if isinstance(ad, dict):
        out["adaptive_fallback_status"] = ad.get("status")
    if isinstance(w.get("checked_result"), dict):
        out["secondary_checked_result"] = {"status": w["checked_result"].get("status"), "reason": w["checked_result"].get("reason"),
                                           "is_secondary": True}
    return out


def _check_category(w):
    """CERTIFIED / REJECTED / NOT_STARTED / INTERRUPTED / UNRESOLVED for a whole-road check record."""
    if not isinstance(w, dict) or w.get("status") is None:
        return "NOT_STARTED"
    s, r = w.get("status"), str(w.get("reason") or "")
    if s == "CERTIFIED_ADMISSIBLE":
        return "CERTIFIED"
    if s == "DEFINITE_REJECT":
        return "REJECTED"
    if s == "NOT_RUN":
        return "NOT_STARTED"
    if s == "UNRESOLVED" and (r in INTERRUPTED_CHECK_REASONS or r.startswith(_INTERRUPTED_PREFIXES)):
        return "INTERRUPTED"
    return "UNRESOLVED"


def _valid_optimality_certificate(cert, arrival):
    if not isinstance(cert, dict):
        return False, "NOT_A_MAPPING"
    if not isinstance(cert.get("relaxation_kind"), str) or not cert["relaxation_kind"].strip():
        return False, "RELAXATION_KIND_NOT_DECLARED"
    if cert.get("complete") is not True:
        return False, "RELAXATION_NOT_COMPLETE"
    lb, a = _exact(cert.get("lower_bound_arrival")), _exact(arrival)
    if lb is None or a is None:
        return False, "LOWER_BOUND_OR_ARRIVAL_NOT_A_FINITE_NUMBER"
    if lb != a:
        return False, "LOWER_BOUND_%s_NOT_EQUAL_ARRIVAL_%s" % (lb, a)
    return True, "LOWER_BOUND_EQUALS_ARRIVAL"


def _valid_refusal_certificate(cert):
    if not isinstance(cert, dict):
        return False, "NOT_A_MAPPING"
    if not isinstance(cert.get("relaxation_kind"), str) or not cert["relaxation_kind"].strip():
        return False, "RELAXATION_KIND_NOT_DECLARED"
    if cert.get("complete") is not True:
        return False, "RELAXATION_NOT_COMPLETE"
    if not isinstance(cert.get("scope"), str) or not cert["scope"].strip():
        return False, "SCOPE_NOT_DECLARED"
    return True, "COMPLETE_DECLARED_RELAXATION"


def decide(search_result, whole_road_check, *, published_before_deadline, identity_expected, identity_observed,
           optimality_certificate=None, refusal_certificate=None, timing=None, extra_diagnostics=None):
    """Return the authoritative decision dict (schema wfg.journey-decision/1). See API_CONTRACT.md."""
    sr = copy.deepcopy(search_result); wr = copy.deepcopy(whole_road_check)
    ie = copy.deepcopy(identity_expected); io = copy.deepcopy(identity_observed)
    oc = copy.deepcopy(optimality_certificate); rc = copy.deepcopy(refusal_certificate)
    timing = copy.deepcopy(timing) if isinstance(timing, dict) else {}
    srd = sr if isinstance(sr, dict) else {}
    s_status = srd.get("status")
    route, role = route_of(srd)
    ident = _identity_block(ie, io)
    rbind = _route_binding(route, wr)
    cat = _check_category(wr)
    contributing = []
    if s_status == "TIMEOUT":
        contributing.append("SEARCH_TIMEOUT")
    if ident["unverified_required_fields"] and not ident["mismatched_fields"]:
        contributing.append("IDENTITY_UNVERIFIED:" + ",".join(ident["unverified_required_fields"]))
    late = published_before_deadline is not True
    cert_diag = {"optimality_certificate": None, "refusal_certificate": None}

    status, reason, detail = None, None, None
    # 1. identity mismatch (including a whole-road check bound to a different route) overrides everything
    if ident["mismatched_fields"] or rbind["match"] is False:
        status, reason = "UNRESOLVED", "STALE_OR_IDENTITY_MISMATCH"
        detail = {"mismatched_fields": ident["mismatched_fields"] + (["route_binding"] if rbind["match"] is False else [])}
    # 2. late (or unproven) publication overrides everything else
    elif late:
        status, reason = "UNRESOLVED", "LATE_RESULT"
        detail = {"published_before_deadline": published_before_deadline}
    # 3. search pass-through statuses (no route)
    elif route is None and s_status in PASS_THROUGH:
        status = reason = PASS_THROUGH[s_status]
    elif route is None and s_status == "UNKNOWN" and "UNSUPPORTED" in str(srd.get("reason") or ""):
        status = reason = "UNSUPPORTED_INPUT"
    # 4. a route (primary or checked incumbent) exists: only the whole-road check decides
    elif route is not None:
        if cat == "CERTIFIED":
            refusal_ok = _valid_refusal_certificate(rc)[0] if rc is not None else False
            if refusal_ok:
                status, reason = "UNRESOLVED", "CONTRADICTORY_EVIDENCE"
                cert_diag["refusal_certificate"] = {"supplied": rc, "applied": False, "note": "contradicts a certified route"}
            elif ident["unverified_required_fields"]:
                status, reason = "UNRESOLVED", "STALE_OR_IDENTITY_MISMATCH"
                detail = {"unverified_required_fields": ident["unverified_required_fields"]}
            else:
                claim = srd.get("status") if role == "PRIMARY" else "CHECKED_TIMEOUT_INCUMBENT"
                status = "CHECKED_JOURNEY_CENTRE_OPTIMUM" if (role == "PRIMARY" and claim in CENTRE_OPTIMUM_CLAIMS) else "CHECKED_JOURNEY_FEASIBLE"
                if oc is not None:
                    ok, why = _valid_optimality_certificate(oc, route.get("arrival"))
                    cert_diag["optimality_certificate"] = {"supplied": oc, "accepted": ok, "evaluation": why,
                                                           "provenance": oc.get("provenance") if isinstance(oc, dict) else None,
                                                           "mathematics_reverified_here": False}
                    if ok:
                        status = "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN"
        elif cat == "REJECTED":
            status, reason = "UNRESOLVED", "CANDIDATE_REJECTED_BY_WHOLE_ROAD"
            detail = {"note": "not a refusal; alternatives may exist", "whole_road_reason": (wr or {}).get("reason")}
        elif cat == "INTERRUPTED":
            status, reason = "UNRESOLVED", "WHOLE_ROAD_CHECK_INTERRUPTED"
            detail = {"whole_road_reason": (wr or {}).get("reason")}
        elif cat == "NOT_STARTED":
            status, reason = "UNRESOLVED", "WHOLE_ROAD_CHECK_NOT_STARTED"
            detail = {"whole_road_reason": (wr or {}).get("reason") if isinstance(wr, dict) else "NO_WHOLE_ROAD_CHECK_RECORD"}
        else:
            status, reason = "UNRESOLVED", "WHOLE_ROAD_CHECK_UNRESOLVED"
            detail = {"whole_road_status": (wr or {}).get("status"), "whole_road_reason": (wr or {}).get("reason")}
    # 5. no route
    elif s_status == "TIMEOUT":
        status, reason = "UNRESOLVED", "SEARCH_TIMEOUT"
        detail = {"note": "a timeout is never a refusal"}
        if rc is not None:
            cert_diag["refusal_certificate"] = {"supplied": rc, "applied": False, "note": "TIMEOUT never becomes a refusal"}
    elif s_status == "PROVEN_INFEASIBLE":
        ok, why = _valid_refusal_certificate(rc) if rc is not None else (False, "NOT_SUPPLIED")
        cert_diag["refusal_certificate"] = {"supplied": rc, "accepted": ok, "evaluation": why, "mathematics_reverified_here": False}
        status = "FULL_MODEL_REFUSAL_PROVEN" if ok else "CENTRE_MODEL_REFUSAL_ONLY"
    else:
        status, reason = "UNRESOLVED", "NO_SOLVER_WITNESS"
        detail = {"search_status": s_status, "search_reason": srd.get("reason")}

    success = status in SUCCESS_STATUSES
    assert status in AUTHORITATIVE_STATUSES
    if success:
        # defensive invariants (cannot be violated by construction)
        assert (wr or {}).get("status") == "CERTIFIED_ADMISSIBLE" and not late and route is not None
        assert ident["all_required_verified"] and rbind["match"] is not False
    journey = None
    if success:
        journey = {"route_role": role, "destination": route.get("destination"), "arrival": route.get("arrival"),
                   "legs": route.get("legs", []),
                   "per_member": {k: {"dose": v.get("dose"), "peak": v.get("peak")} for k, v in (route.get("per_member") or {}).items()
                                  if isinstance(v, dict)}}
    decision = {
        "authoritative_status": status,
        "is_successful_journey": success,
        "unresolved_reason": None if success or status in ("FULL_MODEL_REFUSAL_PROVEN", "CENTRE_MODEL_REFUSAL_ONLY") else reason,
        "unresolved_reason_text": None if success or reason is None else UNRESOLVED_REASONS.get(reason),
        "unresolved_detail": detail,
        "contributing_reasons": contributing,
        "claim_scope": CLAIM_SCOPES[status],
        "physical_safety_claim": False,
        "schema": SCHEMA,
        "module_version": MODULE_VERSION,
        "journey": journey,
        "binding": binding_of(srd),
        "identity": ident,
        "route_binding": rbind,
        "timing": dict(timing, published_before_deadline=published_before_deadline),
        "certificates": cert_diag,
        "diagnostics": {"search": _summ_search(sr), "whole_road_check": _summ_check(wr), "checked_incumbent": _summ_incumbent(srd),
                        "whole_road_category": cat,
                        "note": "Raw statuses are preserved here under their documented meanings and are not application outcomes."},
    }
    if extra_diagnostics is not None:
        decision["diagnostics"]["extra"] = copy.deepcopy(extra_diagnostics)
    return copy.deepcopy(decision)


# ------------------------------------------------------------------ frozen worker records ----
WORKER_SCHEMAS = ("wfg.audit.cand-worker/1", "wfg.broader.cold-worker/1", "wfg.ablation.worker/1")


def decision_from_worker_record(result_json, receipt_json, job_json, *, optimality_certificate=None, refusal_certificate=None):
    """Same decision from frozen worker raw records (RESULT.json, COMPLETE_PROCESS_RECEIPT.json, JOB.json dicts).

    Publication: the outer receipt's on_time_complete_publication AND the worker's final authority re-binding
    (authority_final) AND no incomplete publication. Identities: JOB pins (expected) vs RESULT identities bound by the
    worker and the identities reported by the whole-road checker (observed). The ablation format carries no mandatory
    whole-road check on the original packet (its arm_check is planning-hazard scoped), so it maps to NOT_STARTED and the
    arm check is preserved under diagnostics.extra only.
    """
    res = copy.deepcopy(result_json) if isinstance(result_json, dict) else {}
    rc = copy.deepcopy(receipt_json) if isinstance(receipt_json, dict) else {}
    job = copy.deepcopy(job_json) if isinstance(job_json, dict) else {}
    schema = res.get("schema")
    sr = res.get("result") if isinstance(res.get("result"), dict) else {"status": res.get("primary_status"), "legs": [], "destination": None}
    wr = res.get("whole_road_check") if schema in ("wfg.audit.cand-worker/1", "wfg.broader.cold-worker/1") else None
    published = (rc.get("on_time_complete_publication") is True and res.get("authority_final") is True
                 and res.get("publication_complete", True) is not False)
    ids = res.get("identities") or {}
    g = ids.get("graph_path") or {}; h = ids.get("hazard_path") or {}
    rep = ids.get("source:REPORT.json") or {}; npz = ids.get("source:constructed_arrays.npz") or {}
    isha = job.get("input_sha256") or {}; ssha = job.get("source_sha256") or {}
    w = wr if isinstance(wr, dict) else {}
    mission = w.get("mission") if isinstance(w.get("mission"), dict) else {}
    route, _ = route_of(sr)
    certified = w.get("status") == "CERTIFIED_ADMISSIBLE"
    obs_checker_module = (res.get("checker_module") or {}).get("sha256")
    # Checker-derived identities are compared whenever the checker reported them, and are mandatory (fail closed)
    # whenever the record claims a certified whole-road check; a check that never ran leaves them unpinned.
    def pin(value, observed_value):
        return value if (observed_value is not None or certified) else None
    expected = {"graph_file_sha256": isha.get("graph_path"), "hazard_file_sha256": isha.get("hazard_path"),
                "source_report_sha256": ssha.get("REPORT.json"), "source_npz_sha256": ssha.get("constructed_arrays.npz"),
                "graph_canonical_sha256": pin(g.get("canonical_sha256"), w.get("graph_identity")),
                "checker_source_identity": pin("%s:%s" % (ssha.get("constructed_arrays.npz"), ssha.get("REPORT.json"))
                                               if "constructed_arrays.npz" in ssha and "REPORT.json" in ssha else None,
                                               w.get("source_identity")),
                "checker_module_sha256": pin(job.get("checker_sha256") or None, obs_checker_module),
                "member_ids": pin(sorted((route or {}).get("per_member") or {}) or None, mission.get("scenario_ids"))}
    observed = {"graph_file_sha256": g.get("sha256"), "hazard_file_sha256": h.get("sha256"),
                "source_report_sha256": rep.get("sha256"), "source_npz_sha256": npz.get("sha256"),
                "graph_canonical_sha256": w.get("graph_identity"), "checker_source_identity": w.get("source_identity"),
                "checker_module_sha256": obs_checker_module if job.get("checker_sha256") else None,
                "member_ids": mission.get("scenario_ids")}
    timing = {"complete_budget_s": rc.get("complete_budget_s", res.get("complete_budget_s")),
              "external_launch_to_completion_wall_s": rc.get("external_launch_to_completion_wall_s"),
              "worker_elapsed_before_publication_s": res.get("worker_elapsed_before_publication_s"),
              "on_time_complete_publication": rc.get("on_time_complete_publication"),
              "authority_final": res.get("authority_final"), "deadline_termination_requested": rc.get("deadline_termination_requested")}
    extra = {"source_record": {"schema": schema, "job_id": res.get("job_id"), "case_id": res.get("case_id"), "arm": res.get("arm"),
                               "repetition": res.get("repetition"), "worker_failure": res.get("worker_failure"),
                               "returned_witness_role": res.get("returned_witness_role")}}
    if schema == "wfg.ablation.worker/1":
        ac = res.get("arm_check") if isinstance(res.get("arm_check"), dict) else {}
        extra["arm_check"] = {"status": ac.get("status"), "reason": ac.get("reason"), "scope": ac.get("scope"), "arm": ac.get("arm"),
                              "note": "planning-hazard scoped arm check; not the mandatory whole-road check on the original packet"}
    if schema not in WORKER_SCHEMAS:
        extra["unknown_schema"] = True
    return decide(sr, wr, published_before_deadline=published, identity_expected=expected, identity_observed=observed,
                  optimality_certificate=optimality_certificate, refusal_certificate=refusal_certificate, timing=timing,
                  extra_diagnostics=extra)
