"""Re-key a frozen historical routing request onto a latest-forecast hazard packet (wfg.latest-request-rekey/1).

Only the member identifiers, the hazard version and as_of change: member k of the historical request (identifier suffix
':k') takes the latest packet's member k identifier, keeping its incurred exposure and dose budget unchanged. Position,
incoming edge, departure, horizon, destinations (dwell and open intervals), peak budget, objective, exposure scope, limits
and solver are copied unchanged. Budgets and incurred exposure are frozen request inputs; they are not re-derived from the
latest hazard (the historical stratum label describes how they were originally constructed)."""
import copy, json, re
from pathlib import Path

ID = re.compile(r"^ffb1:(\d{8}T\d{6}Z):([0-9a-f]{16}):(\d+)$")
UNCHANGED = ("position", "incoming_edge", "departure", "horizon", "destinations", "objective", "exposure_scope", "limits", "solver")


class RekeyError(ValueError):
    pass


def rekey(request, hazard, cutoff_iso):
    new_ids = [m["id"] for m in hazard["members"]]
    if new_ids != list(hazard["provenance"]["identity"]["scenario_ids"]):
        raise RekeyError("HAZARD_MEMBER_IDS_INCONSISTENT")
    old = sorted(request["incurred"], key=lambda s: int(ID.match(s).group(3)) if ID.match(s) else -1)
    if any(ID.match(s) is None for s in old) or sorted(request["budgets"]["dose"]) != sorted(old):
        raise RekeyError("REQUEST_MEMBER_IDS_MALFORMED")
    if [int(ID.match(s).group(3)) for s in old] != list(range(len(new_ids))):
        raise RekeyError("MEMBER_ORDINALS_DIFFER %d vs %d" % (len(old), len(new_ids)))
    tag = cutoff_iso.replace("-", "").replace(":", "")[:15] + "Z"
    if len({ID.match(s).group(1) for s in old}) != 1 or ID.match(old[0]).group(1) != tag:
        raise RekeyError("REQUEST_CUTOFF_DIFFERS")
    out = copy.deepcopy(request)
    out["incurred"] = {n: request["incurred"][o] for o, n in zip(old, new_ids)}
    out["budgets"] = {"peak": request["budgets"]["peak"], "dose": {n: request["budgets"]["dose"][o] for o, n in zip(old, new_ids)}}
    out["hazard_version"] = hazard["version"]
    out["as_of"] = cutoff_iso.replace("Z", "+00:00")
    for k in UNCHANGED:
        if out.get(k) != request.get(k):
            raise RekeyError("UNCHANGED_FIELD_ALTERED " + k)
    extra = set(request) - set(UNCHANGED) - {"incurred", "budgets", "hazard_version", "as_of"}
    if extra:
        raise RekeyError("UNEXPECTED_REQUEST_FIELDS %s" % sorted(extra))
    mapping = {"schema": "wfg.latest-request-rekey/1", "member_map": dict(zip(old, new_ids)),
               "unchanged_fields": list(UNCHANGED), "changed_fields": ["incurred keys", "budgets.dose keys", "hazard_version", "as_of"]}
    return out, mapping
