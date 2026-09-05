"""GK2A/AMI sub-daily fire-detection loader — SCAFFOLD ONLY (no data path yet).

Session 8, Phase 5. The preregistered analysis plan this loader will serve is
``docs/gk2a_direction_experiment.md``; the access blocker (KMA API Hub 인증키
required for the L2 FF 산불탐지 product) is recorded in ``docs/BLOCKERS.md``
with the exact signup URL.

⚠ Deliberately unimplemented. The plan's rules: no stub data, no placeholder
arrays, no synthetic GK2A-like detections, and no number derived from any of
those. Until a key exists (primary arm) or the L1B fallback arm is
deliberately chosen with its added confounder, every entry point raises.
"""

from __future__ import annotations

#: The two preregistered access arms (docs/gk2a_direction_experiment.md §2).
ARMS: tuple[str, str] = ("kma_apihub_l2_ff", "nodd_l1b_derived")


def load_fire_detections(fire_id: str, *, arm: str = "kma_apihub_l2_ff",
                         window_hours: float = 3.0):
    """Load sub-daily GK2A fire detections for one fire. NOT IMPLEMENTED.

    Parameters are the preregistered ones (``docs/gk2a_direction_experiment.md``
    §3): 3-hour aggregation windows primary, 1-hour as sensitivity check.

    Raises
    ------
    NotImplementedError
        Always, until the access blocker is resolved. The primary arm needs a
        KMA API Hub 인증키 (see ``docs/BLOCKERS.md``, Session 8); the fallback
        arm (NOAA NODD ``s3://noaa-gk2a-pds`` L1B, keyless, 2023-02→) requires
        an in-house hotspot derivation the plan treats as an added confounder.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; preregistered arms: {ARMS}")
    raise NotImplementedError(
        "GK2A loading is scaffolded but not implemented. The preregistered "
        "plan is docs/gk2a_direction_experiment.md; the primary data arm is "
        "blocked on a KMA API Hub key (docs/BLOCKERS.md, Session 8). No stub "
        "data is provided on purpose — a synthetic stand-in here could leak "
        "into a direction-importance number, which the plan forbids.")


def build_subdaily_labels(fire_id: str, *, window_hours: float = 3.0):
    """Window-resolution transition labels on the 500 m grid. NOT IMPLEMENTED.

    Raises
    ------
    NotImplementedError
        Always — see :func:`load_fire_detections`.
    """
    raise NotImplementedError(
        "label construction follows docs/gk2a_direction_experiment.md §3 and "
        "cannot run before load_fire_detections has a real data arm.")


__all__ = ["ARMS", "load_fire_detections", "build_subdaily_labels"]
