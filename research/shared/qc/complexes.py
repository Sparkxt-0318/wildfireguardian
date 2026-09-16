"""Fire-complex grouping, per the K-SPREAD complex rule (T1.5c).

WHY THIS MODULE EXISTS
-----------------------
Uiseong 2025 appears in the KFS statistics file as two same-day records
(52,707 ha and 46,575 ha), two rows for what was, on the ground, one
connected wildfire event that crossed county boundaries. Treating those two
rows (and the related 영덕/안동 records of the same event) as independent
fires would leak the same event across a train/test split in any of the
three research directions (roads, landslides, suppression), each of which
groups fire records for its own purposes. This module implements ONE
reusable grouping function so all three directions assign the same complex
id to the same records, rather than each direction re-deriving (and
possibly disagreeing on) the grouping.

THE RULE, AND WHERE IT CAME FROM
-----------------------------------
``docs/benchmark/K_SPREAD_2025.md``, section 2 ("Events and clocks"),
K-SPREAD-2025 protocol v0.1 (pre-registered 2026-09-14), states verbatim:

    "Complex rule: 영덕 2025 and 의성·안동 2025 are one complex and are never
    in an entrant's training set when the other is scored
    (``docs/leakfree_fold.md``)."

That is the entire rule this module implements: for the year 2025, any
record located in 영덕, 의성 or 안동 belongs to one single named complex,
``COMPLEX_YEONGDEOK_UISEONG_ANDONG_2025``. This module does not invent any
additional grouping logic (e.g. it does not try to auto-detect "same day,
same area" pairs elsewhere in the data); the K-SPREAD document names this
one complex explicitly, and the task requires implementing exactly that
rule, not a general same-event detector. If a later round adds another named
complex, add it to :data:`COMPLEX_MEMBERSHIP` rather than writing a second
function, so every caller keeps using the same one.

CONTRACT
--------
:func:`assign_complex_id` takes a DataFrame (already loaded; this module
never loads or parses raw KFS files itself; see ``research/shared/qc``
module docstring for why) plus the names of a year column and a
location-text column (any address-hierarchy column that contains the county
name as a substring, e.g. KFS's ``발생장소_시군구`` or ``발생장소_시도``).
It returns a ``pandas.Series`` of string complex ids, one per row, aligned to
``df``'s index. Every row gets an id: rows that are NOT part of any known
complex get a unique per-row STANDALONE id built from the row's own index,
so a downstream leave-one-complex-out split can group by this column
directly without a special case for "not in a complex".
"""

from __future__ import annotations

import pandas as pd

#: The one complex the K-SPREAD-2025 protocol names (see module docstring
#: for the exact source quotation). ``region_substrings`` are matched against
#: the location column with plain substring containment (``in``), so this
#: works whether the caller's location column spells the county
#: "의성" or "경상북도 의성군" or "의성군".
COMPLEX_MEMBERSHIP: list[dict] = [
    {
        "id": "kspread_yeongdeok_uiseong_andong_2025",
        "year": 2025,
        "region_substrings": ("영덕", "의성", "안동"),
        "source": (
            "docs/benchmark/K_SPREAD_2025.md section 2 (K-SPREAD-2025 "
            "protocol v0.1, pre-registered 2026-09-14): “영덕 "
            "2025와 의성·안동 2025는 하나"
            "의 complex이다” "
            "(\"영덕 2025 and 의성·안동 2025 are one complex\")"
        ),
    },
]

#: Prefix for the synthetic id given to a row that matches no known complex.
#: Never collides with a real complex id, which is always taken verbatim
#: from :data:`COMPLEX_MEMBERSHIP`.
STANDALONE_PREFIX = "standalone"


def assign_complex_id(
    df: pd.DataFrame,
    year_col: str,
    region_col: str,
    *,
    membership: list[dict] = COMPLEX_MEMBERSHIP,
) -> pd.Series:
    """Assign a K-SPREAD complex id to every row of ``df``.

    Parameters
    ----------
    df:
        Any table with a year column and a location-text column. Not
        mutated.
    year_col:
        Column holding the fire's year (int-like; compared with ``==``
        against each rule's ``"year"``).
    region_col:
        Column holding location text (e.g. 시군구 or 시도) that CONTAINS the
        county name as a substring. Missing/NaN values never match any rule
        and fall through to the standalone id.
    membership:
        The complex rules to apply, defaulting to :data:`COMPLEX_MEMBERSHIP`
        (the one rule the K-SPREAD-2025 protocol currently names). Passed
        explicitly so a future round can extend or test the rule table
        without editing this function.

    Returns
    -------
    pandas.Series
        ``str``, one complex id per row, aligned to ``df.index``. Two rows
        that match the same rule ALWAYS get the identical id string (this is
        what makes the grouping deterministic and identical across the
        three directions). A row matching no rule gets a unique
        ``"standalone::<index>"`` id, so every row still carries a
        (possibly singleton) complex group and no special-casing is needed
        downstream.
    """
    region = df[region_col].astype("string")
    year = df[year_col]

    ids = pd.Series(
        [f"{STANDALONE_PREFIX}::{idx}" for idx in df.index],
        index=df.index,
        dtype="string",
    )

    for rule in membership:
        year_match = year == rule["year"]
        region_match = region.apply(
            lambda text, subs=rule["region_substrings"]: (
                False if pd.isna(text) else any(sub in text for sub in subs)
            )
        )
        matched = year_match & region_match
        ids.loc[matched] = rule["id"]

    return ids
