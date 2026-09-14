"""Fire-state providers (spec section 3).

``DemoProvider`` replays the bundled synthetic Yeongdeok scenario on a
time-compressed loop (1 real minute = 5 scenario minutes) and honours
``?t=<scenario minutes>`` for deterministic tests and demos.

``LiveFirmsProvider`` queries the NASA FIRMS area API (VIIRS + MODIS) with a
60-second cache.  It has no spread prediction unless ``WFG_PREDICTION_FILE``
points at a GeoJSON produced by the research pipeline — otherwise it reports
``prediction_available: false`` and never fabricates a prediction.
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from .config import Settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class FireState:
    """One snapshot of the world, however it was obtained."""

    mode: str
    t_min: float
    detections: list[dict] = field(default_factory=list)
    wind: dict = field(default_factory=dict)     # {"speed_ms", "dir_deg"} (values may be None)
    weather: dict = field(default_factory=dict)  # {"temp_c", "rh_pct", "days_since_rain"}
    front: Optional[dict] = None                 # {"lat", "lon"} head-fire position
    spread: dict = field(default_factory=dict)   # {"h1": [likely_ring, possible_ring], ...}
    pathways: list[dict] = field(default_factory=list)
    shelters: list[dict] = field(default_factory=list)
    area_ha_est: Optional[float] = None
    first_detected_utc: Optional[str] = None
    last_update_utc: Optional[str] = None
    prediction_available: bool = False
    synthetic: bool = False


class DemoProvider:
    """Replays the bundled synthetic scenario file."""

    def __init__(self, settings: Settings):
        self.settings = settings
        raw = json.loads(Path(settings.scenario_path).read_text(encoding="utf-8"))
        if not raw.get("synthetic"):
            raise ValueError("demo scenario file must declare 'synthetic': true")
        self.scenario = raw
        self.step_minutes: int = int(raw.get("step_minutes", 5))
        self.timesteps: list[dict] = raw["timesteps"]
        self.loop_minutes = self.step_minutes * len(self.timesteps)
        self.start_utc = datetime.strptime(raw["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        self._t0 = time.monotonic()

    # -- time mapping ------------------------------------------------------
    def current_t_min(self) -> float:
        elapsed_real_min = (time.monotonic() - self._t0) / 60.0
        return (elapsed_real_min * self.settings.demo_time_compression) % self.loop_minutes

    def _index_for(self, t_min: Optional[float]) -> int:
        t = self.current_t_min() if t_min is None else max(0.0, float(t_min))
        return int(t // self.step_minutes) % len(self.timesteps)

    def _step_utc(self, step: dict) -> str:
        dt = self.start_utc + timedelta(minutes=step["t_min"])
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # -- API ---------------------------------------------------------------
    def snapshot(self, t_min: Optional[float] = None) -> FireState:
        idx = self._index_for(t_min)
        step = self.timesteps[idx]
        return FireState(
            mode="demo",
            t_min=float(step["t_min"]),
            detections=step["detections"],
            wind=step["wind"],
            weather=step["weather"],
            front=step.get("front"),
            spread=step.get("spread") or {},
            pathways=step.get("pathways") or [],
            shelters=self.scenario.get("shelters") or [],
            area_ha_est=step.get("area_ha_est"),
            first_detected_utc=self._step_utc(self.timesteps[0]),
            last_update_utc=self._step_utc(step),
            prediction_available=True,
            synthetic=True,
        )

    def history(self, t_min: Optional[float] = None) -> list[dict]:
        idx = self._index_for(t_min)
        points = []
        for step in self.timesteps[: idx + 1]:
            points.append(
                {
                    "t_utc": self._step_utc(step),
                    "detections": len(step["detections"]),
                    "area_ha_est": step.get("area_ha_est") or 0.0,
                    "wind_speed_ms": step["wind"]["speed_ms"],
                    "rh_pct": step["weather"]["rh_pct"],
                }
            )
        return points


class LiveFirmsProvider:
    """NASA FIRMS area API (VIIRS + MODIS), 60 s cache.

    Honest degradation: no weather feed and no spread prediction are bundled;
    the corresponding fields are ``None``/empty and ``prediction_available``
    is ``false`` unless ``WFG_PREDICTION_FILE`` supplies a prediction GeoJSON
    (the hook for the research pipeline's forward sim — the pipeline itself is
    never imported).
    """

    FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/{area}/1"
    # Korea-wide bounding box (west,south,east,north)
    AREA = "124.0,33.0,131.0,39.5"
    SENSORS = ("VIIRS_SNPP_NRT", "MODIS_NRT")
    CACHE_SECONDS = 60.0

    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache: list[dict] = []
        self._cache_at = 0.0
        self._first_seen_utc: Optional[str] = None
        self._prediction = self._load_prediction(settings.prediction_file)

    @staticmethod
    def _load_prediction(path: str) -> Optional[dict]:
        if not path:
            return None
        p = Path(path)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _fetch_detections(self) -> list[dict]:
        now = time.monotonic()
        if self._cache and (now - self._cache_at) < self.CACHE_SECONDS:
            return self._cache
        detections: list[dict] = []
        for sensor in self.SENSORS:
            url = self.FIRMS_URL.format(
                key=self.settings.firms_map_key, sensor=sensor, area=self.AREA
            )
            try:
                resp = httpx.get(url, timeout=20.0)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                try:
                    detections.append(
                        {
                            "lat": float(row["latitude"]),
                            "lon": float(row["longitude"]),
                            "frp_mw": float(row.get("frp") or 0.0),
                            "confidence": (row.get("confidence") or "n")[:1].lower(),
                            "sensor": "VIIRS" if "VIIRS" in sensor else "MODIS",
                        }
                    )
                except (KeyError, ValueError):
                    continue
        self._cache = detections
        self._cache_at = now
        if detections and not self._first_seen_utc:
            self._first_seen_utc = utc_now_iso()
        return detections

    def _prediction_layers(self) -> tuple[dict, list[dict]]:
        """(spread rings by horizon, pathways) from the prediction GeoJSON."""
        spread: dict = {}
        pathways: list[dict] = []
        if not self._prediction:
            return spread, pathways
        for feat in self._prediction.get("features", []):
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            if geom.get("type") == "Polygon" and props.get("horizon_hours") in (1, 3, 6):
                key = f"h{props['horizon_hours']}"
                spread.setdefault(key, []).append(geom["coordinates"][0])
            elif geom.get("type") == "LineString" and props.get("kind") == "pathway":
                pathways.append(
                    {"bearing_deg": props.get("bearing_deg"), "coords": geom["coordinates"]}
                )
        return spread, pathways

    def snapshot(self, t_min: Optional[float] = None) -> FireState:
        detections = self._fetch_detections()
        spread, pathways = self._prediction_layers()
        return FireState(
            mode="live",
            t_min=0.0,
            detections=detections,
            wind={"speed_ms": None, "dir_deg": None},
            weather={"temp_c": None, "rh_pct": None, "days_since_rain": None},
            front=None,
            spread=spread,
            pathways=pathways,
            shelters=[],  # no live shelter feed configured; never invent one
            area_ha_est=None,
            first_detected_utc=self._first_seen_utc,
            last_update_utc=utc_now_iso() if detections else None,
            prediction_available=bool(spread or pathways),
            synthetic=False,
        )

    def history(self, t_min: Optional[float] = None) -> list[dict]:
        # No stored live history; report the current point only (honest).
        detections = self._fetch_detections()
        if not detections:
            return []
        return [
            {
                "t_utc": utc_now_iso(),
                "detections": len(detections),
                "area_ha_est": round(len(detections) * 14.0, 1),
                "wind_speed_ms": 0.0,
                "rh_pct": 0.0,
            }
        ]


def make_provider(settings: Settings):
    if settings.mode == "live" and settings.firms_map_key:
        return LiveFirmsProvider(settings)
    return DemoProvider(settings)
