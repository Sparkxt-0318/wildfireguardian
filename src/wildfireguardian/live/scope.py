"""The scope statement — what is real-time here and what is not.

Round-3 PHASE 6.

THE ONE THING THIS MODULE EXISTS TO PREVENT
-------------------------------------------
"Live wildfire detection with automatic routing" reads, to anyone who has not
read the code, as *forecasting today's fire from today's weather*. It is not,
and it cannot be:

* **Detection is real-time.** NASA FIRMS NRT publishes VIIRS/MODIS hotspots
  within roughly three hours of the overpass.
* **Weather is not.** ERA5 reanalysis is published on an approximately five-day
  lag. Today's weather does not exist as a downloadable field, so no hazard
  surface can be simulated for today.

The hazard surface this pipeline routes on was therefore simulated ONCE, from
the weather of the fire it was built for, and is held fixed. A new detection
decides *whether* and *where* to act; it does not move the surface. Blurring
that distinction would be claiming a capability the project does not have, so
every screen, sheet, broadcast script and JSON record carries the two lines
:func:`scope_lines` returns.

The strings are here, in one place, rather than formatted at each call site,
because a caveat that is retyped is a caveat that eventually is not.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: The published lag on ERA5 reanalysis, in days. Not a tunable — it is a
#: property of the Copernicus release schedule.
ERA5_PUBLICATION_LAG_DAYS: int = 5

#: Verbatim, and never paraphrased.
DETECTION_LINE_KO: str = "화점 탐지: 실시간 (FIRMS NRT)"
WEATHER_LINE_KO_TEMPLATE: str = "기상 자료: {basis} 기준 (ERA5는 약 5일 지연 발행)"

#: Where the ignition point came from. The weather half of the scope statement
#: is identical for all three — the surface is pre-computed whatever triggered
#: it — but the DETECTION half is not, and must not be faked.
#:
#: ``manual`` exists because in real operation a fire's location arrives from a
#: 119 call, a watch-tower or a CCTV operator long before a satellite sees it.
#: Waiting for an overpass is a property of the demo, not of the problem.
TRIGGER_SOURCES: tuple[str, ...] = ("firms_nrt", "replay", "manual")

MANUAL_LINE_KO_TEMPLATE: str = "발화점: 수동 입력 · {when}"
REPLAY_LINE_KO_TEMPLATE: str = "화점 탐지: 재생 모드 · {when}"

MANUAL_BANNER_KO: str = (
    "■ 수동 입력 ■ 119 신고·감시원·CCTV 등으로 접수된 발화점 좌표입니다. "
    "위성 탐지를 기다리지 않았습니다.")

#: The banner every operational artifact carries above its numbers.
SCOPE_BANNER_KO: str = (
    "본 산출물은 「실시간 탐지 + 사전 계산 위험면 기반 결정」입니다. "
    "「실시간 예보 기반 예측」이 아닙니다.")
SCOPE_BANNER_EN: str = (
    "REAL-TIME DETECTION over a PRE-COMPUTED risk surface. This is NOT a "
    "real-time forecast: ERA5 reanalysis publishes on a ~5-day lag, so no "
    "hazard field exists for today.")

#: Replay mode says so on its face, everywhere. A recorded run that is mistaken
#: for a live one is the single worst outcome of a demo.
REPLAY_BANNER_KO: str = (
    "■ 재생 모드 ■ 과거 화재의 화점 기록을 시간 순으로 재생한 것이며, "
    "지금 발생 중인 화재가 아닙니다.")
LIVE_BANNER_KO: str = "■ 실시간 모드 ■ FIRMS NRT 조회 결과입니다."

#: ⚠ THIS USED TO BE A CONSTANT NAMING 영덕 AND 32.6 %, AND IT WENT ON EVERY
#: REGION'S PAPER.
#:
#: Measured 2026-08-07: **273** A4 dispatch sheets for 의성·안동 and 울진·삼척
#: carried 「영덕 수치는 … 32.6 %만 덮는 …」, and neither region's own coverage
#: figure (99.2 %, 81.5 %) appeared anywhere on its own sheet. The sentence was
#: not a false claim about those regions — it says 「영덕 수치는」 — but it is the
#: wrong region's caveat on a single-village dispatch sheet, and it displaced
#: the one that belonged there.
#:
#: It is now built per region from the committed artifacts. The values are READ,
#: never retyped: this defect existed in three places, and every one of them was
#: a figure somebody had typed a second time.
#:
#: docs/HANDOFF_ROUND3.md §2-A is the decision record for the caveat itself.
#: ``build_numbers.COVERAGE_CAVEAT`` is a SEPARATE, longer bilingual string for
#: the registry, correctly applied to Yeongdeok-only entries; it is not this.

#: Committed artifacts these strings are assembled from. Both are tracked.
_COMPARISON = "data/processed/multi_region_comparison.json"
_COMPLETENESS = "data/processed/osm_completeness.json"


@lru_cache(maxsize=None)
def _artifact(rel: str) -> dict:
    path = Path(__file__).resolve().parents[3] / rel
    if not path.exists():
        raise CoverageUnavailable(
            f"{rel} is missing; per-region operational wording cannot be built "
            "from it. It is a committed artifact: restore it rather than "
            "typing the figures in.")
    return json.loads(path.read_text(encoding="utf-8"))


class CoverageUnavailable(RuntimeError):
    """A per-region figure has no committed source. Never guess one."""


@lru_cache(maxsize=None)
def _region_row(region: str) -> dict:
    for row in _artifact(_COMPARISON)["regions"]:
        if row["region"] == region:
            return row
    raise CoverageUnavailable(
        f"{region!r} is not in {_COMPARISON}, so its coverage figure and Korean "
        "label have no committed source.")


def region_label_kr(region: str) -> str:
    """The Korean label the committed comparison table uses for this region."""
    return _region_row(region)["label_kr"]


def region_coverage_pct(region: str) -> float:
    """Walk-bbox coverage of the predicted core, from the committed table."""
    return round(float(_region_row(region)["envelope_coverage_final_slice"]) * 100.0, 1)


def coverage_caveat_ko(region: str) -> str:
    """The standing coverage qualifier, for THIS region.

    Carried by every absolute rate or raw origin count that reaches an
    operational artifact. The structure is the one PHASE 3 settled on; only the
    region and the two figures follow the region.
    """
    label = region_label_kr(region)
    cov = region_coverage_pct(region)
    rest = round(100.0 - cov, 1)
    return (
        f"{label} 수치는 정본 화재 핵심의 {cov} %만 덮는 보행망에서 "
        f"산출되었습니다. 나머지 {rest} %에 있는 출발지들의 거동은 측정되지 "
        "않았으며, 편향의 방향도 알려져 있지 않습니다. 지역 간 비교에서 "
        f"{label} 행을 인용할 때는 이 열을 반드시 함께 제시하십시오.")


_WALK_EXTENT = re.compile(r"^walk_bbox_([\d,]+)km2$")
_MANIFEST_EXTENT = re.compile(r"^manifest_bbox_([\d,]+)km2$")


def _extent_counts(region: str) -> tuple[tuple[int, int] | None,
                                         tuple[int, int] | None]:
    """``((walk_km2, n), (manifest_km2, n))`` from `osm_completeness.json`.

    ⚠ THE AREA IS ENCODED IN THE KEY NAME, e.g. ``walk_bbox_919km2: 0``. That is
    awkward and it is still the committed record, so it is PARSED rather than
    retyped. The alternative would be a fourth hand-written copy of 919, which
    is the exact shape of the defect this function exists to remove.
    ⚠ These are the PLANAR areas the operator-facing text uses. The geodesic
    ones (896.5 / 889.5 / 895.3) live in ``regions[].bbox_area_km2``; not
    updating the operational wording to them is a recorded decision,
    docs/multi_region.md "planar vs geodesic".

    Returned as INTEGERS so the caller can group the thousands itself: the key
    spells 3926 and the mandated wording is **3,926**, so passing the raw digits
    through would quietly drop the separator rule 11 states.
    """
    table = _artifact(_COMPLETENESS).get("fire_station_counts_by_extent", {})
    row = table.get(region)
    if not row:
        return None, None
    walk = manifest = None
    for key, value in row.items():
        if not isinstance(value, int) or isinstance(value, bool):
            continue
        m = _WALK_EXTENT.match(key)
        if m:
            walk = (int(m.group(1).replace(",", "")), value)
        m = _MANIFEST_EXTENT.match(key)
        if m:
            manifest = (int(m.group(1).replace(",", "")), value)
    return walk, manifest


def responder_status_ko(region: str, n_depot_pois: int) -> str:
    """What the screens say about the responder side, for THIS region.

    ⚠ RULE 11. The claim is that no ``amenity=fire_station`` is MAPPED IN OSM
    inside this region's walk bbox. It is never "this region has no fire
    stations", and the wider extent's count is stated whenever it was measured.

    ⚠ WHERE A NUMBER DOES NOT EXIST, IT IS NOT INVENTED. The wider manifest-bbox
    count was measured for ``uiseong_andong_2025`` only. For any other region
    with zero depots the sentence says the wider extent has not been counted,
    rather than borrowing Uiseong-Andong's 3,926 km² and its six.
    """
    if n_depot_pois > 0:
        return (f"차고지 {n_depot_pois}곳이 매핑되어 있으나, 459 계열은 "
                "주민 측만 산출합니다")
    walk, manifest = _extent_counts(region)
    where = f"walk bbox({walk[0]:,} km²) 내에" if walk else "walk bbox 내에"
    head = (f"이 지역은 {where} OSM에 매핑된 소방서가 없어 "
            "구조자 측 산출이 불가합니다.")
    if manifest:
        return f"{head} 더 넓은 {manifest[0]:,} km² 범위에는 {manifest[1]}곳"
    return (f"{head} 더 넓은 범위의 소방서 수는 이 지역에 대해 측정되지 "
            "않았습니다.")


@dataclass(frozen=True)
class Scope:
    """The scope statement for one run, resolved against real inputs.

    ``weather_basis`` is not a literal: it is read from the committed detection
    record that anchors the pre-computed field's t = 0, so it cannot drift away
    from the field it describes.
    """

    mode: str                       # "replay" | "live" | "manual"
    weather_basis: str              # e.g. "2025-03-25 12:25 UTC"
    hazard_field: str               # repo-relative path to the npz
    region: str
    #: Where the ignition point came from. Defaults to FIRMS so every existing
    #: caller keeps its exact wording.
    trigger_source: str = "firms_nrt"
    #: For manual and replay, WHEN the trigger happened, already formatted.
    #:
    #: ⚠ For a manual trigger this is the moment the COORDINATE WAS ENTERED —
    #: a 119 call, a watch-tower, a CCTV operator. It is NOT a satellite
    #: overpass time, and the two must never be presented as the same kind of
    #: thing: one is when a person reported a fire, the other is when an
    #: instrument observed one.
    trigger_at: str = ""

    @property
    def is_replay(self) -> bool:
        return self.mode == "replay"

    @property
    def is_manual(self) -> bool:
        return self.trigger_source == "manual"

    def detection_line(self) -> str:
        """The first mandated line, worded for the source that actually fired.

        A manual report is not a FIRMS detection, and saying 「화점 탐지: 실시간
        (FIRMS NRT)」 over a coordinate someone phoned in would claim an
        instrument that was never involved.
        """
        if self.trigger_source == "manual":
            return MANUAL_LINE_KO_TEMPLATE.format(when=self.trigger_at or "시각 미상")
        if self.trigger_source == "replay":
            return (REPLAY_LINE_KO_TEMPLATE.format(when=self.trigger_at)
                    if self.trigger_at else DETECTION_LINE_KO)
        return DETECTION_LINE_KO

    def lines(self) -> list[str]:
        """The two mandated lines, in order, exactly as they must be shown."""
        return [self.detection_line(),
                WEATHER_LINE_KO_TEMPLATE.format(basis=self.weather_basis)]

    def mode_banner(self) -> str:
        if self.is_manual:
            return MANUAL_BANNER_KO
        return REPLAY_BANNER_KO if self.is_replay else LIVE_BANNER_KO

    def banner_block(self) -> str:
        """One-line form for a place that has room for exactly one string."""
        return " · ".join([self.mode_banner(), *self.lines()])

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "mode_banner_ko": self.mode_banner(),
            "trigger_source": self.trigger_source,
            "trigger_at": self.trigger_at,
            "trigger_at_meaning": (
                "the moment the coordinate was ENTERED by an operator (119 "
                "call / watch-tower / CCTV). NOT a satellite overpass time."
                if self.is_manual else
                "the satellite overpass whose batch fired the trigger"),
            "detection": ("manual report — no satellite involved"
                          if self.is_manual else "real-time (FIRMS NRT)"),
            "detection_line_ko": self.detection_line(),
            "weather": "NOT real-time",
            "weather_basis": self.weather_basis,
            "weather_line_ko": self.lines()[1],
            "era5_publication_lag_days": ERA5_PUBLICATION_LAG_DAYS,
            "scope_ko": SCOPE_BANNER_KO,
            "scope_en": SCOPE_BANNER_EN,
            "hazard_field": self.hazard_field,
            "hazard_field_is_precomputed": True,
            "region": region_note(self.region),
            # Per region, from the committed table. This key is read by every
            # viz.json / RUN.json consumer, so it is the third of the three
            # paths the caveat travels (A4, email, JSON).
            "coverage_caveat_ko": self.coverage_caveat(),
        }

    def coverage_caveat(self) -> str:
        """This run's region's coverage qualifier."""
        return coverage_caveat_ko(self.region)


def region_note(region: str) -> str:
    return region


def scope_lines(weather_basis: str) -> list[str]:
    """The two lines, for callers that have no :class:`Scope` to hand."""
    return [DETECTION_LINE_KO,
            WEATHER_LINE_KO_TEMPLATE.format(basis=weather_basis)]


__all__ = [
    "CoverageUnavailable", "DETECTION_LINE_KO", "ERA5_PUBLICATION_LAG_DAYS",
    "LIVE_BANNER_KO", "MANUAL_BANNER_KO", "MANUAL_LINE_KO_TEMPLATE",
    "REPLAY_BANNER_KO", "REPLAY_LINE_KO_TEMPLATE", "SCOPE_BANNER_EN",
    "SCOPE_BANNER_KO", "Scope", "TRIGGER_SOURCES",
    "WEATHER_LINE_KO_TEMPLATE", "coverage_caveat_ko", "region_coverage_pct",
    "region_label_kr", "responder_status_ko", "scope_lines",
]
