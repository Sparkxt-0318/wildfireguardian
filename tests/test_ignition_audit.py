"""Tests for the data-audit + overpass-clustering layer (Deliverable 0)."""

from __future__ import annotations

import pandas as pd
import pytest

from wildfireguardian.ignition_model.audit import cluster_overpasses, run_audit
from wildfireguardian.ignition_model.config import PipelineConfig

_DATA = PipelineConfig().data_dir
_HAVE_DATA = (_DATA / "fire_manifest.json").exists()


def _ts(*isos):
    return pd.Series(pd.to_datetime(list(isos), utc=True))


def test_cluster_overpasses_splits_on_large_gap():
    # three bursts separated by > 60 min, with sub-gaps < 60 min inside each
    ts = _ts(
        "2022-03-04T03:00:00Z",
        "2022-03-04T03:10:00Z",  # +10 min -> same cluster
        "2022-03-04T05:00:00Z",  # +110 min -> new cluster
        "2022-03-04T13:00:00Z",  # +8 h -> new cluster
    )
    ends = cluster_overpasses(ts, gap_minutes=60.0)
    assert len(ends) == 3


def test_cluster_overpasses_merges_coincident_sensors():
    # NOAA-20 / SNPP ~50 min apart must merge at a 60-min gap
    ts = _ts("2025-03-22T04:00:00Z", "2025-03-22T04:50:00Z")
    assert len(cluster_overpasses(ts, gap_minutes=60.0)) == 1
    # ...but split at a 45-min gap
    assert len(cluster_overpasses(ts, gap_minutes=45.0)) == 2


def test_cluster_overpasses_empty():
    assert cluster_overpasses(pd.Series([], dtype="datetime64[ns, UTC]"), 60.0) == []


@pytest.mark.skipif(not _HAVE_DATA, reason="FIRMS data not unzipped")
def test_audit_flags_broken_fuel_and_drops_sparse():
    audit = run_audit()
    by_id = {f["fire_id"]: f for f in audit["fires"]}

    # yeongdeok + gangneung_donghae cross the WorldCover 129E tile boundary
    assert by_id["yeongdeok_2025"]["fuel_decision"] == "FLAG_FUEL_BLIND"
    assert by_id["yeongdeok_2025"]["frac_detections_in_fuel"] < 0.2
    assert by_id["gangneung_donghae_2022"]["fuel_decision"] == "FLAG_FUEL_BLIND"

    # the 2-overpass fire is dropped
    assert by_id["gangneung_2023"]["fuel_decision"] == "DROP"

    # well-covered fires kept
    assert by_id["uljin_samcheok_2022"]["fuel_decision"] == "KEEP"
    assert by_id["uljin_samcheok_2022"]["frac_detections_in_fuel"] > 0.95

    # every fire's timestamps must parse
    assert all(f["timestamps_parseable"] for f in audit["fires"])
