"""Premise P1 / stronger O2: are the per-cell flame-activity sets the same in three independent derivations?

 (i)   HAZARD.json — what the frozen full-policy checker samples: member row k is active on [bp_k, bp_{k+1}); the frozen packets
       have len(rows) = len(bps) − 1 with bp_last = H, so the comparison on [0, H) needs no closing point (Mira note). Union over members.
 (ii)  RAW — own re-derivation from constructed_arrays.npz and REPORT.json assumptions, without ContactModel:
       member s, cell with finite first-new ignition b: [b, b + T); present-fire cells: [0, R). Native north-up row r
       -> graph row (H_grid - 1 - r). Union over members.
 (iii) ContactModel.cell_intervals (what the instance builder uses).
Compared exactly (Fraction of the stored binary64 values) on [0, horizon) per graph cell. Usage: python p1_check.py
"""
from __future__ import annotations

import json
import os
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(os.path.abspath(__file__)).parent
sys.path.insert(0, str(HERE))
import cases  # noqa: E402
from wfg_scenario_members.contact import ContactModel  # noqa: E402


def merge(ivs, lo, hi):
    """Union of half-open intervals clipped to [lo, hi), merged (touching intervals joined)."""
    out = []
    for a, b in sorted((max(a, lo), min(b, hi)) for a, b in ivs):
        if a >= b:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def writer_identity(hz):
    """The packet writer identity every packet comparison must print (orchestrator condition for F-9.3 masked packets,
    which keep their v1 scenario ids): packet_writer_sha256, base_packet_writer_sha256 and support_writer if present."""
    ident = (hz.get("provenance") or {}).get("identity") or {}
    return {k: ident[k] for k in ("packet_writer_sha256", "base_packet_writer_sha256", "support_writer") if k in ident}


def from_hazard(hz, Hs):
    out = {}
    for m in hz["members"]:
        bps = [F(x) for x in m["breakpoints"]]
        for k, row in enumerate(m["flame"]):
            a = bps[k]
            b = bps[k + 1] if k + 1 < len(bps) else bps[-1]
            for cell, on in enumerate(row):
                if on:
                    out.setdefault(cell, []).append((a, b))
    return {c: merge(v, F(0), Hs) for c, v in out.items()}


HAZARD_ONLY_MARKER = "per_cell_law_HAZARD_only"


def require_routable_arrays(a, packet):
    """Refuse a packet whose constructed_arrays are not a routable hazard (Leo 588f74e / PACKET_CONSISTENCY_RULE.md):
    the per-cell-law marker, or a NaN / -inf birth. +inf is the valid "never ignites" value and is accepted.
    Raises ValueError: fail loudly, never skip cells."""
    if HAZARD_ONLY_MARKER in a.files and bool(np.asarray(a[HAZARD_ONLY_MARKER]).any()):
        raise ValueError("%s: %s set; the per-cell law is in HAZARD.json only, the arrays are not a routable hazard"
                         % (Path(packet).name, HAZARD_ONLY_MARKER))
    if "ignition_time_s" in a.files:
        ign = a["ignition_time_s"]
        if np.isnan(ign).any() or np.isneginf(ign).any():
            raise ValueError("%s: %d NaN and %d -inf ignition_time_s; the arrays are not a routable hazard"
                             % (Path(packet).name, int(np.isnan(ign).sum()), int(np.isneginf(ign).sum())))


def routable_contact_model(packet, **kw):
    """ContactModel.from_packet behind require_routable_arrays. contact.py is hash-pinned (SOURCE_SHA256.json and frozen
    evidence bundles), so the HAZARD-only marker guard lives here: every F-3.2 reader goes through this wrapper."""
    with np.load(Path(packet) / "constructed_arrays.npz", allow_pickle=False) as a:
        require_routable_arrays(a, packet)
    return ContactModel.from_packet(packet, **kw)


def from_raw(packet, Hs):
    rep = json.loads((Path(packet) / "REPORT.json").read_text())
    asm = rep["native_metadata"]["construction"]["assumptions"]
    T, R = F(float(asm["burning_duration_s"])), F(float(asm["initial_remaining_s"]))
    with np.load(Path(packet) / "constructed_arrays.npz", allow_pickle=False) as a:
        require_routable_arrays(a, packet)
        ign, cur = a["ignition_time_s"], a["current_active"].astype(bool)
    S, Hn, W = ign.shape
    g = lambda r, c: (Hn - 1 - int(r)) * W + int(c)
    out = {}
    for s in range(S):
        for r, c in zip(*np.nonzero(np.isfinite(ign[s]))):
            b = F(float(ign[s, r, c]))
            out.setdefault(g(r, c), []).append((b, b + T))
    if R > 0:
        for r, c in zip(*np.nonzero(cur)):
            out.setdefault(g(r, c), []).append((F(0), R))
    return {c: merge(v, F(0), Hs) for c, v in out.items()}


def main():
    rows, seen = [], set()
    for c in cases.korean_cases():
        key = c["packet"]
        if key in seen:
            continue
        seen.add(key)
        hz = json.loads((Path(c["packet"]) / "HAZARD.json").read_text())
        Hs = F(float(hz["valid_until"]))
        A = from_hazard(hz, Hs)
        B = from_raw(c["packet"], Hs)
        Cm = routable_contact_model(c["packet"]).cell_intervals
        C = {k: merge(v, F(0), Hs) for k, v in Cm.items()}
        A = {k: v for k, v in A.items() if v}; B = {k: v for k, v in B.items() if v}; C = {k: v for k, v in C.items() if v}
        diff = lambda X, Y: sorted(k for k in set(X) | set(Y) if X.get(k) != Y.get(k))
        row = dict(packet=c["region"] + "/" + c["mission"].split("_")[0], active_cells=len(C),
                   hazard_vs_raw=len(diff(A, B)), hazard_vs_contact=len(diff(A, C)), raw_vs_contact=len(diff(B, C)))
        d = diff(A, C)
        if d:
            k = d[0]
            row["example"] = {"cell": k, "hazard": [[str(x), str(y)] for x, y in A.get(k, [])][:3],
                              "contact": [[str(x), str(y)] for x, y in C.get(k, [])][:3]}
        rows.append(row)
        print(json.dumps(row), flush=True)
    (HERE / "results" / "p1_flame_sets.json").write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    main()
