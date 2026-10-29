"""Extended-horizon exploratory panel: derive 3 h and 6 h missions from the frozen 1 h missions.

Orchestrator decision (human): keep the 20 frozen missions as the primary result; add, separately, an
"extended-horizon exploratory panel, not frozen missions" with the same origins, destinations, thresholds and
destination rules but horizons of 3 h and 6 h. Its counts are never pooled with the frozen counts.

Derivation rule (exact, applied by `derive`):
  * horizon          3600 -> H (10800 or 21600 s);
  * open intervals   an interval whose upper end equals the frozen horizon ("open until the horizon") is extended to
                     end at H; every other bound is copied unchanged (fixed windows stay fixed);
  * everything else  (position, incoming edge, departure, destinations and dwell, budgets, incurred dose, peak limit,
                     exposure scope, objective, limits) is copied unchanged;
  * provenance       the SHA-256 of the canonical JSON of the source request and the rule version are recorded.
"""
from __future__ import annotations

import copy
import hashlib
import json

RULE = "wfg.extended-horizon-derivation/1"
HORIZONS = (10800, 21600)
LABEL = "extended-horizon exploratory panel, not frozen missions"


def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def derive(request, horizon, *, source_file_sha256=None, source_name=None):
    old = float(request["horizon"])
    if horizon <= old:
        raise ValueError("extended horizon must exceed the frozen horizon")
    out = copy.deepcopy(request)
    out["horizon"] = float(horizon)
    for d in out["destinations"]:
        d["open_intervals"] = [[a, horizon if float(b) == old else b] for a, b in d["open_intervals"]]
    provenance = {"rule": RULE, "label": LABEL, "source": source_name, "source_request_canonical_sha256": canonical_sha(request),
                  "source_request_file_sha256": source_file_sha256, "source_horizon_s": old, "horizon_s": float(horizon),
                  "changed_fields": ["horizon", "destinations[*].open_intervals upper ends equal to the source horizon"]}
    return out, provenance
