#!/usr/bin/env python3
"""Deterministic generator for the bundled demo scenario (spec section 4).

Writes ``guardian_app/demo_data/scenario_yeongdeok.json``: a ~6-simulated-hour
SYNTHETIC wildfire near Yeongdeok (36.42 N, 129.37 E), 72 timesteps at 5-minute
spacing.  The fire starts small SW of that point and is driven NE by a strong
west/WSW wind (8-12 m/s), mirroring the real 2025 Yeongdeok fire's SW->NE run
direction — but every number here is invented.  The file carries
``"synthetic": true`` and bilingual notices; the API stamps ``"mode": "demo"``
on every response built from it.

Everything is seeded (``SEED``) and uses only the Python standard library, so
re-running this script reproduces the committed JSON byte-for-byte.

Demo heuristics (NOT research claims, none of this comes from the research
pipeline):

* front speed        : ``front_speed_kmh = 0.3 + 0.25 * wind_speed_ms``
* burned-area guess  : ``area_ha_est = detections * 14`` (a VIIRS pixel is
                       roughly 375 m across, ~14 ha)
* spread rings       : ellipses elongated downwind from the fire head; for
                       each horizon h in {1,3,6} hours the reach is
                       ``front_speed_kmh * h``.  Two rings per horizon, in
                       this order: index 0 = "likely", index 1 = "possible"
                       (1.6x the likely reach).  See ``spread_ring_order``.

Usage::

    python3 app/backend/scripts/make_scenario.py            # write the file
    python3 app/backend/scripts/make_scenario.py --check    # verify committed file matches
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

SEED = 20260807
STEPS = 72
STEP_MINUTES = 5
START_UTC = "2026-04-01T03:00:00Z"  # synthetic timestamp, matches nothing real

# Fire origin: SW of (36.42 N, 129.37 E).
ORIGIN_LAT = 36.398
ORIGIN_LON = 129.338

OUT_PATH = Path(__file__).resolve().parents[1] / "guardian_app" / "demo_data" / "scenario_yeongdeok.json"

SHELTERS = [
    {
        "name_ko": "영덕읍민 대피소 (가상)",
        "name_en": "Yeongdeok-eup Community Shelter (synthetic)",
        "lat": 36.362,
        "lon": 129.368,
    },
    {
        "name_ko": "강구항 체육관 (가상)",
        "name_en": "Ganggu Harbor Gymnasium (synthetic)",
        "lat": 36.352,
        "lon": 129.396,
    },
    {
        "name_ko": "남정면 복지회관 (가상)",
        "name_en": "Namjeong-myeon Welfare Center (synthetic)",
        "lat": 36.330,
        "lon": 129.360,
    },
    {
        "name_ko": "해맞이 마을회관 (가상)",
        "name_en": "Haemaji Village Hall (synthetic)",
        "lat": 36.383,
        "lon": 129.432,
    },
]


def dest_point(lat: float, lon: float, bearing_deg: float, dist_km: float) -> tuple[float, float]:
    """Small-distance flat-earth destination point (fine for a <30 km scene)."""
    b = math.radians(bearing_deg)
    dlat = dist_km * math.cos(b) / 110.574
    dlon = dist_km * math.sin(b) / (111.320 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def ellipse_ring(
    c_lat: float, c_lon: float, semi_major_km: float, semi_minor_km: float, bearing_deg: float, n: int = 24
) -> list[list[float]]:
    """Closed polygon ring ([lon, lat] pairs) for an ellipse whose major axis
    points along ``bearing_deg``."""
    ring: list[list[float]] = []
    for k in range(n):
        theta = 2.0 * math.pi * k / n
        along = semi_major_km * math.cos(theta)
        across = semi_minor_km * math.sin(theta)
        dist = math.hypot(along, across)
        ang = bearing_deg + math.degrees(math.atan2(across, along))
        lat, lon = dest_point(c_lat, c_lon, ang, dist)
        ring.append([round(lon, 5), round(lat, 5)])
    ring.append(list(ring[0]))
    return ring


def spread_rings(head_lat: float, head_lon: float, downwind_deg: float, reach_km: float) -> list[list[list[float]]]:
    """[likely_ring, possible_ring] — elliptical, elongated downwind of the head."""
    rings = []
    for scale in (1.0, 1.6):
        r = reach_km * scale
        c_lat, c_lon = dest_point(head_lat, head_lon, downwind_deg, r * 0.5)
        rings.append(ellipse_ring(c_lat, c_lon, r * 0.62, r * 0.28 + 0.3, downwind_deg))
    return rings


def build_scenario() -> dict:
    rng = random.Random(SEED)

    timesteps: list[dict] = []
    detections: list[dict] = []
    head_km = 0.0  # cumulative head-fire run distance from the origin

    # Three initial detections clustered at the origin.
    for _ in range(3):
        lat, lon = dest_point(
            ORIGIN_LAT, ORIGIN_LON, rng.uniform(0, 360), abs(rng.gauss(0.0, 0.25))
        )
        detections.append(
            {
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "frp_mw": round(rng.uniform(4, 15), 1),
                "confidence": "h",
                "sensor": "VIIRS",
            }
        )

    for i in range(STEPS):
        t_min = i * STEP_MINUTES
        frac = i / (STEPS - 1)

        # West/WSW wind, 8 -> 12 m/s ramp with seeded wobble.
        wind_speed = 8.0 + 4.0 * frac + rng.uniform(-0.4, 0.4)
        wind_speed = round(min(12.0, max(8.0, wind_speed)), 1)
        wind_dir = 250.0 + 8.0 * math.sin(frac * math.pi * 2.0) + rng.uniform(-3, 3)
        wind_dir = round(wind_dir % 360.0, 0)
        downwind = (wind_dir + 180.0) % 360.0

        # RH 30 -> 15 %, temperature 23 -> 29 C, 14 days since rain.
        rh = 30.0 - 15.0 * frac + rng.uniform(-0.7, 0.7)
        rh = round(min(30.0, max(15.0, rh)), 1)
        if i == 0:
            rh = 30.0
        if i == STEPS - 1:
            rh = 15.0
        temp = round(23.0 + 6.0 * frac + rng.uniform(-0.5, 0.5), 1)

        # Head-fire advance this step (demo heuristic, see module docstring).
        front_speed_kmh = 0.3 + 0.25 * wind_speed
        head_km += front_speed_kmh * (STEP_MINUTES / 60.0)
        head_lat, head_lon = dest_point(ORIGIN_LAT, ORIGIN_LON, 70.0, head_km)

        # Grow the detection field toward a ~46-detection total.
        n_target = 3 + round(43 * frac**1.1)
        while len(detections) < n_target:
            u = rng.uniform(0.45, 1.0)  # bias new pixels toward the head
            base_lat, base_lon = dest_point(ORIGIN_LAT, ORIGIN_LON, 70.0, head_km * u)
            lateral = rng.gauss(0.0, 0.3 + 0.03 * head_km)
            lat, lon = dest_point(base_lat, base_lon, 70.0 + 90.0, lateral)
            detections.append(
                {
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "frp_mw": round(rng.uniform(5, 90), 1),
                    "confidence": "h" if rng.random() < 0.72 else "n",
                    "sensor": "VIIRS" if rng.random() < 0.8 else "MODIS",
                }
            )

        spread = {
            f"h{h}": spread_rings(head_lat, head_lon, downwind, front_speed_kmh * h)
            for h in (1, 3, 6)
        }

        # 2-3 pathway arrows fanning NE from the head (here: 3).
        pathways = []
        for offset in (-15.0, 0.0, 18.0):
            b0 = (downwind + offset) % 360.0
            coords = [[round(head_lon, 5), round(head_lat, 5)]]
            lat, lon, b = head_lat, head_lon, b0
            for _seg in range(5):
                lat, lon = dest_point(lat, lon, b, 2.8)
                coords.append([round(lon, 5), round(lat, 5)])
                b += 3.0  # gentle curve
            pathways.append({"bearing_deg": round(b0, 0), "coords": coords})

        timesteps.append(
            {
                "t_min": t_min,
                "detections": [dict(d) for d in detections],
                "wind": {"speed_ms": wind_speed, "dir_deg": wind_dir},
                "weather": {"temp_c": temp, "rh_pct": rh, "days_since_rain": 14},
                "front": {"lat": round(head_lat, 5), "lon": round(head_lon, 5)},
                "area_ha_est": round(len(detections) * 14.0, 1),
                "spread": spread,
                "pathways": pathways,
            }
        )

    return {
        "synthetic": True,
        "_notice_en": (
            "SYNTHETIC DEMO SCENARIO. Generated by app/backend/scripts/make_scenario.py "
            "(seeded). Geographically plausible for the Yeongdeok area but numerically "
            "invented — NOT observations, NOT a research output, NOT a forecast."
        ),
        "_notice_ko": (
            "훈련용 가상 시나리오입니다. app/backend/scripts/make_scenario.py로 생성한 "
            "합성 자료이며 실제 관측이나 예측이 아닙니다."
        ),
        "seed": SEED,
        "region_ko": "경상북도 영덕군 일대 (가상)",
        "region_en": "Yeongdeok County area, North Gyeongsang (synthetic)",
        "start_utc": START_UTC,
        "step_minutes": STEP_MINUTES,
        "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON},
        "spread_ring_order": ["likely", "possible"],
        "shelters": SHELTERS,
        "timesteps": timesteps,
    }


def serialize(scenario: dict) -> str:
    """Header fields pretty, one timestep per line: small file, sane diffs."""
    head = {k: v for k, v in scenario.items() if k != "timesteps"}
    lines = ["{"]
    head_json = json.dumps(head, ensure_ascii=False, indent=1)
    # splice the header object's inner lines
    inner = head_json.splitlines()[1:-1]
    lines.extend(line.rstrip() for line in inner)
    lines[-1] = lines[-1] + ","
    lines.append(' "timesteps": [')
    steps = scenario["timesteps"]
    for i, ts in enumerate(steps):
        row = json.dumps(ts, ensure_ascii=False, separators=(",", ":"))
        lines.append("  " + row + ("," if i < len(steps) - 1 else ""))
    lines.append(" ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    scenario = build_scenario()
    text = serialize(scenario)
    if "--check" in sys.argv:
        current = OUT_PATH.read_text(encoding="utf-8")
        if current != text:
            print("MISMATCH: committed scenario differs from generator output")
            return 1
        print("OK: committed scenario matches generator output")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    last = scenario["timesteps"][-1]
    print(f"wrote {OUT_PATH}")
    print(
        f"steps={len(scenario['timesteps'])} final_detections={len(last['detections'])} "
        f"final_front=({last['front']['lat']},{last['front']['lon']}) "
        f"bytes={len(text.encode('utf-8'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
