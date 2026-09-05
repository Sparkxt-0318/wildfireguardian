#!/usr/bin/env python
"""Register the README's opening figures in docs/NUMBERS.json (WFG-049).

The March 2025 fire's scale opens the README in two languages. Those figures had no
artifact, no registry key and no URL, so the paragraph was rewritten wrongly twice
(116,000 ha, then 45,157 ha) while every gate stayed green. Now each figure lives in
``data/processed/external/fire_2025_scale.json`` with its agency, as-of date, scope,
status (final / interim / secondary) and the URL that was opened to verify it, and
this script upserts one registry entry per figure so ``scripts/verify_numbers.py``
re-derives them like any other number and ``scripts/check_readme_figures.py`` can
refuse an interim tally presented as final.

ADDITIVE ON PURPOSE. ``scripts/build_numbers.py`` rebuilds the registry from its own
list and would drop the ~140 keys other registrars added; this script loads the
current file, replaces only the ``fire2025_`` keys, and writes it back.

    python scripts/register_fire2025_figures.py          # upsert + report
    python scripts/register_fire2025_figures.py --check  # exit 1 if the registry is stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/external/fire_2025_scale.json"
PREFIX = "fire2025_"

# key suffix -> (figure name in the artifact, caveat, forbidden phrasings)
FIGURES = [
    ("chain_area_ha", "chain_area_ha",
     "FINAL burned area of the 의성발 경북 chain alone (경상북도, 2025-05-07). Not 116,000 ha "
     "(matches no scope) and not 45,157 ha (the 2025-03-27 interim tally). It is about 95 % "
     "of the nationwide 104,788 ha; the nationwide figure is NOT a different event.",
     ["116,000 ha", "약 116,000 ha"]),
    ("chain_hours_to_containment", "chain_hours_to_containment",
     "Ignition 2025-03-22 11:24 to 주불 진화 2025-03-28 17:15.", []),
    ("chain_deaths", "chain_deaths",
     "경북 5개 시군 합계 (중대본, 2025-03-30). The chain is 26, the whole spring season is 32, "
     "and 27 is neither.", ["사망 27명", "27 deaths"]),
    ("chain_deaths_yeongdeok", "chain_deaths_yeongdeok",
     "영덕군 공지 2025-04-29 as re-cited at p.9 of the 2026-03 joint damage survey (재인용값). The 중대본 "
     "breakdown of 2025-03-30 said 9 at that date; 8 is the retired pre-f2eecf9 value.",
     ["영덕 8명", "8 of them in 영덕"]),
    ("chain_homes_damaged", "chain_homes_damaged",
     "FINAL (경상북도, 2025-05-07). 150동 is the 2025-03-26 전소 interim tally; 4,000여 채 was the "
     "original README's unsourced value.", ["4,000여 채"]),
    ("chain_displaced_households", "chain_displaced_households", "경상북도, 2025-05-07.", []),
    ("chain_displaced_people", "chain_displaced_people", "경상북도, 2025-05-07.", []),
    ("chain_damage_krw_100m", "chain_damage_krw_100m",
     "Total damage confirmed by 중대본 (경상북도 release, 2025-05-07); the recovery budget "
     "(1조 8,310억 원) is a different quantity.", []),
    ("nationwide_fires", "nationwide_fires",
     "Whole 2025 spring season, 2025-01-24 to 2025-05-15 (산림청, 2025-05-16).", []),
    ("nationwide_area_ha", "nationwide_area_ha",
     "Whole 2025 spring season, 347 fires. The 의성발 chain is 99,289 ha of this, about 95 %: "
     "never describe this figure as a different event from the chain.",
     ["belongs to a different event", "다른 사건"]),
    ("nationwide_deaths", "nationwide_deaths",
     "Whole 2025 spring season (산림청, 2025-05-16); the chain alone is 26.", []),
    ("nationwide_injured", "nationwide_injured", "Whole 2025 spring season.", []),
    ("yeongnam_homes_damaged_secondary", "yeongnam_homes_damaged",
     "SECONDARY and NOT nationwide: the 산림청 2025-05-16 release carries no housing figure; "
     "3,848동 is the joint damage-survey report's figure for the 영남 초대형 산불 complex. Do not "
     "attribute it to 산림청 or to all 347 fires.", []),
    ("interim_chain_area_ha_20250327", "interim_chain_area_ha_20250327",
     "INTERIM. 중대본 2025-03-27 경북 도내 집계, one day before 주불 진화; understates the final "
     "99,289 ha by 54,132 ha. Registered so the README gate can refuse it as a final value.",
     ["45,157 ha 소실", "burned 45,157 ha"]),
    ("interim_homes_destroyed_20250326", "interim_homes_destroyed_20250326",
     "INTERIM. 산림청 2025-03-26 전소 count, two days before containment; the final is 3,819동.", []),
]


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    figs = art["figures"]
    out = {}
    for suffix, fig, caveat, forbidden in FIGURES:
        f = figs[fig]
        out[PREFIX + suffix] = {
            "value": f["value"],
            "unit": f["unit"],
            "source_file": ARTIFACT,
            "json_path": f"figures.{fig}.value",
            "derivation": (f"published figure; agency: {f['agency']}; as of {f['as_of']}; "
                           f"scope: {f['scope']}; status: {f['status']}; source: {f['url']}"),
            "config_hash": doc_hash,
            "config_hash_at_production": None,
            "git_commit": head,
            "sample": f["scope"],
            "caveat": caveat,
            "forbidden_phrasings": forbidden,
            "reproducible": False,
            "reproducibility": {
                "status": "external",
                "evidence": ("not produced by any pipeline; re-verification means opening the "
                             "URL again. Verified 2026-09-04: " + str(f.get("verified", ""))),
                "blocked_by": None,
            },
            "provenance": "external",
            "arm": "external",
            "figure_status": f["status"],
            "agency": f["agency"],
            "as_of": f["as_of"],
            "scope": f["scope"],
            "source_url": f["url"],
            "notes": "README opening paragraph (Korean and English) is bound to this key by "
                     "scripts/check_readme_figures.py and tests/test_readme_opening_figures.py.",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": f"figures.{fig}.value"}}},
        }
    a, b = figs["chain_area_ha"]["value"], figs["nationwide_area_ha"]["value"]
    out[PREFIX + "chain_share_of_nationwide_pct"] = {
        "value": round(a / b * 100, 1), "unit": "%", "source_file": ARTIFACT,
        "json_path": "figures.chain_area_ha.value / figures.nationwide_area_ha.value",
        "derivation": "100 * chain_area_ha / nationwide_area_ha = 100 * 99289 / 104788",
        "config_hash": doc_hash, "config_hash_at_production": None, "git_commit": head,
        "sample": "chain vs the whole 2025 spring season",
        "caveat": "Arithmetic record only: 100 * 99,289 / 104,788 over two final figures from "
                  "different releases (경상북도 2025-05-07; 산림청 season total 2025-05-16, period "
                  "2025-01-24 to 05-15). Whether the share may be printed is disputed between the "
                  "0037Z and 0100Z laps (NH-018); the README currently prints no share.",
        "forbidden_phrasings": ["belongs to a different event", "다른 사건"],
        "reproducible": False,
        "reproducibility": {"status": "external", "evidence": "arithmetic over two published figures",
                            "blocked_by": None},
        "provenance": "external", "arm": "external", "figure_status": "derived", "agency": "derived", "as_of": "2025-05-16",
        "scope": "chain / nationwide", "source_url": figs["nationwide_area_ha"]["url"],
        "check": {"kind": "expression",
                  "operands": {"a": {"file": ARTIFACT, "json_path": "figures.chain_area_ha.value"},
                               "b": {"file": ARTIFACT, "json_path": "figures.nationwide_area_ha.value"}},
                  "expr": "round(a / b * 100, 1)", "tolerance": 0.0},
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    art = json.loads((REPO / ARTIFACT).read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    new = build_entries(art, head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items() if k not in cur or cur[k]["value"] != e["value"]
             or cur[k].get("figure_status") != e.get("figure_status") or cur[k].get("source_url") != e.get("source_url")]
    if args.check:
        if stale:
            print("STALE fire2025 registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} fire2025 entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # keep the git_commit of the first registration; values must not silently move
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"upserted {len(new)} fire2025 entries ({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
