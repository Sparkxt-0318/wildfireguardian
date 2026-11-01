"""Real-region instance builders. US region 1: Caldor Fire 2021, South Lake Tahoe
(:mod:`evacplan.regions.caldor`).

* roads: OpenStreetMap through osmnx (:mod:`.osm`; "(c) OpenStreetMap contributors, ODbL 1.0" kept);
* care facilities: the CMS Provider Data Catalog nursing-home provider file (:mod:`.cms`),
  geocoded with the US Census geocoder (:mod:`.geocode`) unless the file carries coordinates;
* fire: observed perimeters through ``hazard_contract.from_perimeters`` (:mod:`.perimeters`);
* residents' mobility mix, fleet and (by default) shelters: SYNTHETIC, documented (:mod:`.people`).

Every assumption is in ``docs/ASSUMPTIONS.md``. When an input is neither given as a file nor
downloadable, builders raise :class:`BuildBlocked` naming exactly the hosts or files they need;
they never substitute synthetic data for real inputs.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Missing:
    item: str          # what is missing
    needs: str         # the host(s) to reach or the file(s) to provide


class BuildBlocked(RuntimeError):
    """A real-region build cannot proceed: inputs are missing and their hosts are unreachable."""

    def __init__(self, missing: list[Missing], region: str = ""):
        self.missing = list(missing)
        self.region = region
        super().__init__(self.report())

    def report(self) -> str:
        head = f"BLOCKED: {self.region} cannot be built here" if self.region else "BLOCKED"
        return "\n".join([head + "; it needs:"] + [f"  - {m.item}: {m.needs}" for m in self.missing])


__all__ = ["BuildBlocked", "Missing"]
