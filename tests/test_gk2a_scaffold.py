"""The GK2A scaffold must refuse to run — no stub data, no silent fallback."""

from __future__ import annotations

import pytest

from wildfireguardian.fire_detection.gk2a import (
    ARMS,
    build_subdaily_labels,
    load_fire_detections,
)


def test_loader_raises_not_implemented_never_returns_stub_data():
    with pytest.raises(NotImplementedError) as exc:
        load_fire_detections("yeongdeok_2025")
    # the exception itself routes the reader to the plan and the blocker
    assert "gk2a_direction_experiment" in str(exc.value)
    assert "BLOCKERS" in str(exc.value)


def test_labels_raise_too():
    with pytest.raises(NotImplementedError):
        build_subdaily_labels("yeongdeok_2025")


def test_unknown_arm_is_a_value_error_not_a_guess():
    with pytest.raises(ValueError):
        load_fire_detections("yeongdeok_2025", arm="modis")
    assert ARMS == ("kma_apihub_l2_ff", "nodd_l1b_derived")
