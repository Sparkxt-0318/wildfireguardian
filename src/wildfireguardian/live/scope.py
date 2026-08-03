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

from dataclasses import dataclass

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

#: Carried by every ABSOLUTE Yeongdeok rate or raw origin count that reaches an
#: operational artifact. Identical to the string build_numbers.py appends to the
#: registry; docs/HANDOFF_ROUND3.md §2-A is the decision record.
COVERAGE_CAVEAT_KO: str = (
    "영덕 수치는 정본 화재 핵심의 32.6 %만 덮는 보행망에서 산출되었습니다. "
    "나머지 3분의 2에 있는 출발지들의 거동은 측정되지 않았으며, 편향의 방향도 "
    "알려져 있지 않습니다. 지역 간 비교에서 영덕 행을 인용할 때는 이 열을 "
    "반드시 함께 제시하십시오.")


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
            "coverage_caveat_ko": COVERAGE_CAVEAT_KO,
        }


def region_note(region: str) -> str:
    return region


def scope_lines(weather_basis: str) -> list[str]:
    """The two lines, for callers that have no :class:`Scope` to hand."""
    return [DETECTION_LINE_KO,
            WEATHER_LINE_KO_TEMPLATE.format(basis=weather_basis)]


__all__ = [
    "COVERAGE_CAVEAT_KO", "DETECTION_LINE_KO", "ERA5_PUBLICATION_LAG_DAYS",
    "LIVE_BANNER_KO", "MANUAL_BANNER_KO", "MANUAL_LINE_KO_TEMPLATE",
    "REPLAY_BANNER_KO", "REPLAY_LINE_KO_TEMPLATE", "SCOPE_BANNER_EN",
    "SCOPE_BANNER_KO", "Scope", "TRIGGER_SOURCES",
    "WEATHER_LINE_KO_TEMPLATE", "scope_lines",
]
