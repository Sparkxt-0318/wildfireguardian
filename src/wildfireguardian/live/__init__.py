"""Live detection pipeline: FIRMS NRT -> routing -> operational outputs.

Round-3 PHASE 6.

THE SCOPE STATEMENT COMES FIRST, HERE AND EVERYWHERE
----------------------------------------------------
This package performs **real-time detection over a pre-computed risk surface**.
It is *not* real-time forecasting, and the difference is not a nuance:

* FIRMS NRT publishes hotspots within ~3 hours of overpass — that part is live;
* ERA5 reanalysis publishes on a ~5-day lag, so **there is no weather field for
  today**, and therefore no hazard surface can be simulated for today.

The surface routed on was simulated once, from the weather of the fire it was
built for, and is held fixed. A new detection decides whether and where to act.
:mod:`.scope` owns the strings that say so; every artifact carries them, and
``tests/test_live_pipeline.py`` fails if one does not.

MODULES
-------
:mod:`.scope`     the two mandated lines, the mode banners, the coverage caveat
:mod:`.firms`     NRT acquisition, parsing, de-duplication (the only live part)
:mod:`.replay`    offline replay of a past fire — the demonstration path
:mod:`.state`     the persistent seen-set and the per-run audit record
:mod:`.pipeline`  trigger -> 459-series routing -> the three PHASE-3 formats

NOTHING IS EVER SENT. The SMS layer composes drafts and writes files;
``delivery.sms.send`` is not called from anywhere in this package.
"""

from __future__ import annotations

from . import firms, pipeline, replay, scope, state

__all__ = ["firms", "pipeline", "replay", "scope", "state"]
