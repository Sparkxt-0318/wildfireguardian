"""Persistent seen-set and per-run state records.

Round-3 PHASE 6-A / 6-D.

"A new hotspot is one that was not in the previous query" only means something
if the previous query survived the process that made it. So the seen-set is a
file, not a variable, and it is written before any routing begins — a crash
during routing must not cause the same hotspot to trigger again on restart.

WHAT A RUN RECORD HAS TO ANSWER
-------------------------------
Six months from now, looking at one directory under ``outputs/live/``, a reader
must be able to say without running anything:

* what was fed in (which hotspots, from which source, at what time),
* which hotspot actually pulled the trigger,
* which hazard field was routed on, by path AND digest,
* what the weather basis of that field was,
* how long each stage took,
* what came out, and whether anything was transmitted (never).

:func:`RunRecord.as_dict` is that list, in that order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .firms import Hotspot

#: Schema version for the on-disk state file.
STATE_SCHEMA_VERSION: int = 1


@dataclass
class SeenState:
    """The hotspots this region has already been told about."""

    region: str
    keys: set[str] = field(default_factory=set)
    points: list[tuple[float, float]] = field(default_factory=list)
    last_trigger_utc: datetime | None = None
    last_poll_utc: datetime | None = None
    n_polls: int = 0
    n_triggers: int = 0
    path: Path | None = None

    @classmethod
    def load(cls, path: Path, region: str) -> "SeenState":
        p = Path(path)
        if not p.exists():
            return cls(region=region, path=p)
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw.get("region") != region:
            # A state file from another region would silently suppress this
            # region's first real detection. Start clean and say so.
            return cls(region=region, path=p)
        return cls(
            region=region,
            keys=set(raw.get("keys") or []),
            points=[(float(a), float(b)) for a, b in (raw.get("points") or [])],
            last_trigger_utc=_parse(raw.get("last_trigger_utc")),
            last_poll_utc=_parse(raw.get("last_poll_utc")),
            n_polls=int(raw.get("n_polls") or 0),
            n_triggers=int(raw.get("n_triggers") or 0),
            path=p,
        )

    def observe(self, hotspots: list[Hotspot]) -> None:
        for h in hotspots:
            self.keys.add(h.key())
            self.points.append((h.lat, h.lon))

    def save(self, path: Path | None = None) -> Path:
        p = Path(path or self.path or "")
        if not str(p):
            raise ValueError("SeenState has no path to save to")
        p.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "schema_version": STATE_SCHEMA_VERSION,
            "region": self.region,
            "updated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_keys": len(self.keys),
            "keys": sorted(self.keys),
            "points": [[a, b] for a, b in self.points],
            "last_trigger_utc": _fmt(self.last_trigger_utc),
            "last_poll_utc": _fmt(self.last_poll_utc),
            "n_polls": self.n_polls,
            "n_triggers": self.n_triggers,
            "note": "Seen-set for the live detection pipeline. A hotspot whose "
                    "key is here has already been reported and does not "
                    "re-trigger. Delete this file to replay a region from "
                    "scratch.",
        }
        p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        self.path = p
        return p


@dataclass
class StageTimings:
    """Wall-clock cost of each stage, in seconds. The basis for saying
    "a few seconds" out loud at a demonstration."""

    load_hazard_s: float = 0.0
    load_network_s: float = 0.0
    load_pois_s: float = 0.0
    route_s: float = 0.0
    cluster_s: float = 0.0
    #: Writing HTML, the broadcast script and the SMS drafts. Milliseconds.
    render_s: float = 0.0
    #: Headless-Chrome PDF conversion. SEPARATE, and excluded from the totals
    #: below, because it is a rendering convenience that happens AFTER the
    #: dispatch list already exists — roughly 2.7 s per sheet, so 29 villages
    #: cost about 78 s and would otherwise swamp a figure that is meant to
    #: answer "how long until an operator has the list?".
    pdf_s: float = 0.0

    @property
    def deliver_s(self) -> float:
        """Total delivery cost including PDF conversion. Reported, not headline."""
        return self.render_s + self.pdf_s

    @property
    def warm_total_s(self) -> float:
        """Trigger -> the dispatch list exists, in every text format.

        Excludes PDF conversion (see :attr:`pdf_s`) and excludes loading, which
        a running service does once at start-up. This is the number to quote.
        """
        return self.route_s + self.cluster_s + self.render_s

    @property
    def cold_total_s(self) -> float:
        """Process start -> the dispatch list, including first-time loading."""
        return (self.load_hazard_s + self.load_network_s + self.load_pois_s
                + self.warm_total_s)

    @property
    def warm_total_with_pdf_s(self) -> float:
        return self.warm_total_s + self.pdf_s

    def as_dict(self) -> dict:
        return {
            "load_hazard_s": round(self.load_hazard_s, 3),
            "load_network_s": round(self.load_network_s, 3),
            "load_pois_s": round(self.load_pois_s, 3),
            "route_s": round(self.route_s, 3),
            "cluster_s": round(self.cluster_s, 3),
            "render_s": round(self.render_s, 3),
            "pdf_s": round(self.pdf_s, 3),
            "deliver_s": round(self.deliver_s, 3),
            "warm_total_s": round(self.warm_total_s, 3),
            "cold_total_s": round(self.cold_total_s, 3),
            "warm_total_with_pdf_s": round(self.warm_total_with_pdf_s, 3),
            "definition": {
                "warm_total_s": "trigger -> the dispatch list exists in every "
                                "text format (HTML sheet, broadcast script, "
                                "SMS drafts). Hazard field and walk graph "
                                "already resident, as in a running service. "
                                "THE NUMBER TO QUOTE.",
                "cold_total_s": "process start -> the dispatch list, including "
                                "loading the field, the graph and the POIs.",
                "pdf_s": "headless-Chrome A4 conversion, EXCLUDED from the "
                         "totals: it runs after the list already exists and "
                         "costs ~2.7 s per sheet, so it scales with the number "
                         "of villages rather than with the decision.",
                "warm_total_with_pdf_s": "warm_total_s + pdf_s, for when the "
                                         "printed sheets are what is being "
                                         "waited on.",
            },
        }


@dataclass
class RunRecord:
    """Everything one triggered run needs to be auditable later."""

    run_id: str
    started_utc: datetime
    mode: str
    region: str
    scope: dict
    trigger: dict
    inputs: dict
    counts: dict
    outputs: dict
    timings: StageTimings
    field_applicability: dict
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "started_utc": self.started_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": self.mode,
            "region": self.region,
            # Lifted out of `scope` so "which trigger produced this?" is
            # answerable without reading a nested block. FIRMS, replay and
            # manual all write here; only the value differs.
            "trigger_source": self.scope.get("trigger_source", "firms_nrt"),
            "scope": self.scope,
            "trigger": self.trigger,
            "inputs": self.inputs,
            "counts": self.counts,
            "field_applicability": self.field_applicability,
            "timings_s": self.timings.as_dict(),
            "outputs": self.outputs,
            # Scope: this AUTOMATIC pipeline. Since PHASE 7 the email channel
            # can transmit, but only from the manually invoked
            # scripts/send_dispatch_email.py behind a typed confirmation, and
            # its record is email_sent.json beside this file.
            "nothing_was_sent": True,
            "nothing_was_sent_scope": "the automatic pipeline; see "
                                      "docs/delivery_channels.md",
            "notes": self.notes,
        }

    def write(self, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / "RUN.json"
        p.write_text(json.dumps(self.as_dict(), indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        return p


def _parse(s: object) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _fmt(d: datetime | None) -> str | None:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


__all__ = ["RunRecord", "STATE_SCHEMA_VERSION", "SeenState", "StageTimings"]
