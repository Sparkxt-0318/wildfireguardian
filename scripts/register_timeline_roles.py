#!/usr/bin/env python
"""Register the development-schedule figures in docs/NUMBERS.json (WFG-027).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its
own list and would drop the keys other registrars added (WFG-040); this script
loads the current file, replaces only the `timeline_` keys, and writes it back.

    python scripts/register_timeline_roles.py          # upsert + report
    python scripts/register_timeline_roles.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/timeline_roles/timeline_roles.json"
PREFIX = "timeline_"

#: The caveat every one of these keys carries. These counts describe a git
#: history, not effort, not authorship of ideas, and not hours worked.
BAND = (
    "COMMIT COUNTS FROM ONE BRANCH'S HISTORY, NOT A MEASURE OF WORK. Four facts "
    "travel with any of these figures or none may be quoted: (1) they count "
    "commits reachable from HEAD on auto/dev at the stated commit, so a rebased "
    "or parked branch's commits are not in them, and every count except the last "
    "phase's grows with every later lap — the figure is 'as of' its git_commit "
    "and nothing re-derives it forward; (2) `agent_trailer_commits` counts "
    "commits whose message carries the `Co-Authored-By: Claude` trailer, which "
    "is a mechanical string test and NOT a statement about who thought of what — "
    "the trailer convention only begins in July 2026, so an untrailered commit "
    "is not evidence that no tool was used; (3) a commit is not a unit of work — "
    "the autonomous loop commits several times per lap by design (a claim, the "
    "work, the report), so the 2026-09 counts are inflated relative to the "
    "hand-worked months and must never be read as 'more was done'; (4) the phase "
    "boundaries are the calendar gaps in the commit record, chosen because the "
    "record has them, and they are not project milestones anyone declared at the "
    "time."
)

FORBIDDEN = [
    "commits measure the work",
    "the AI wrote 513 commits",
    "AI가 513개를 작성했습니다",
    "커밋 수가 작업량입니다",
    "the student wrote 149 commits",
]

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("total_commits", "total_commits", "commits",
     "commits reachable from HEAD on auto/dev when the artifact was built"),
    ("active_days", "active_days", "days",
     "distinct UTC calendar dates carrying at least one commit"),
    ("agent_trailer_commits", "agent_trailer_commits", "commits",
     "commits whose message body carries the `Co-Authored-By: Claude` trailer"),
    ("other_commits", "other_commits", "commits",
     "the remainder — commits without that trailer, which is not the same as "
     "commits written without a tool"),
    ("commits_outside_phases", "commits_outside_phases", "commits",
     "commits whose date falls in none of the five phases; 0 is what makes the "
     "phase table a partition of the record rather than a selection from it"),
]

PHASE_FIELDS = [
    ("commits", "commits", "commits", "commits dated inside this phase"),
    ("active_days", "active_days", "days",
     "distinct UTC dates inside this phase carrying at least one commit"),
    ("agent_trailer_commits", "agent_trailer_commits", "commits",
     "commits inside this phase carrying the `Co-Authored-By: Claude` trailer"),
]


def phase_figures(art: dict) -> list[tuple[str, str, str, str]]:
    out = []
    for i, ph in enumerate(art["phases"]):
        for suffix, field, unit, derivation in PHASE_FIELDS:
            out.append((f"{ph['id']}_{suffix}", f"phases.{i}.{field}", unit,
                        f"{derivation} ({ph['start']} to {ph['end']})"))
    return out


def _dig(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in FIGURES + phase_figures(art):
        out[PREFIX + suffix] = {
            "value": _dig(art, path),
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            "derivation": derivation +
            ". Regenerate: python scripts/build_timeline_roles.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": f"auto/dev history, {art['first_commit_date']} to "
                      f"{art['last_commit_date']}",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/build_timeline_roles.py rebuilds the artifact "
                    "from `git log` alone, with no network and no data files. It "
                    "requires the FULL history: a shallow clone cannot resolve "
                    "2026-05-27 and the script exits 2 there rather than "
                    "guessing."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "process_record",
            "notes": "docs/auto/finals/TIMELINE_ROLES.md states the schedule, the "
                     "roles for a solo entrant, and what these counts do NOT "
                     "show. They are a record of a git history and are not a "
                     "result about wildfires.",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": path}}},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    art = json.loads((REPO / ARTIFACT).read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(art, head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"]
             or cur[k].get("caveat") != e.get("caveat")]
    if args.check:
        if stale:
            print("STALE timeline registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} timeline entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} timeline entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
