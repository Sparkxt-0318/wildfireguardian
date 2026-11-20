"""Fireline intensity from satellite fire radiative power (METHOD.md section 6; PROTOCOL.md section 5).

For an active-fire pixel with radiative power FRP (MW), the dry-matter combustion rate is
    m_dot = C_e * FRP          (kg/s; C_e = 0.368 kg/MJ, Wooster et al. 2005)
and the heat release rate H * m_dot. Spread over the length of front inside the pixel, L_f (m), this is a
fireline intensity
    I_FRP = H * C_e * FRP / L_f      (H in kJ/kg, C_e in kg/MJ, FRP in MW = MJ/s: kJ/s per m = kW/m)
L_f is not observed. The pixel's along-scan x along-track footprint (``scan``, ``track`` columns, km) bounds it:
a straight front crossing the pixel has L_f between the shorter and the longer side, and a front can also be
shorter (partly burning pixel). The protocol uses L_f = sqrt(scan * track) * 1000 and reports the factor of
uncertainty this implies (METHOD.md 6).
"""
from __future__ import annotations

import csv
import math
from datetime import datetime, timezone
from pathlib import Path

C_E_KG_PER_MJ = 0.368  # Wooster et al. (2005), JGR 110, D24311


def read_firms(paths):
    out = []
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                t = datetime.strptime(r["acq_date"] + r["acq_time"].zfill(4), "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
                out.append({"lat": float(r["latitude"]), "lon": float(r["longitude"]), "t": t, "frp_mw": float(r["frp"]),
                            "scan_km": float(r["scan"]), "track_km": float(r["track"]), "sat": r["satellite"],
                            "instrument": r["instrument"], "confidence": r["confidence"], "daynight": r.get("daynight", ""),
                            "type": r.get("type", ""), "file": Path(p).name})
    return out


def intensity_from_frp(frp_mw, scan_km, track_km, heat_kj_kg=18000.0, c_e=C_E_KG_PER_MJ):
    L_f = math.sqrt(scan_km * track_km) * 1000.0
    return heat_kj_kg * c_e * frp_mw / L_f, L_f
