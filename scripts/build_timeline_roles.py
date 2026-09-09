#!/usr/bin/env python
"""Reconstruct the development schedule from `git log` (WFG-027).

설계와 방법론 names 「일정 및 팀원(개인의 경우 제외) 역할 배분의 타당성」 as one of its
four sub-items and it is worth 20 points on both KCF scoring tables. Until this
script the repository answered 「어떤 일정으로 만드셨습니까?」 with nothing: the raw
string 일정 counted 0 on README.md, web/finals.html and docs/auto/JUDGE_QA.md.

The answer already existed in `git log`; what was missing was a surface. This
script builds the machine half of that surface — a committed artifact every date
and count in `docs/auto/finals/TIMELINE_ROLES.md` is checked against — so the
prose cannot rot the way hand-typed counts in this repository have three times
(WFG-117, and the 「여섯 개」 that survived its own correcting commit).

    python scripts/build_timeline_roles.py           # rebuild the artifact
    python scripts/build_timeline_roles.py --check   # exit 1 if it is stale

⚠ It needs the FULL history. A shallow clone cannot see 2026-05-27, so both
modes exit 2 with 「shallow」 on a clone that cannot resolve the first commit;
the test that reads the artifact skips on the same predicate rather than failing,
because CHARTER §4's clone depth is not a constant (measured 50, 51, 149, 294 and
531 on different laps).

**What the agent/other split is and is not.** `agent_trailer_commits` counts
commits whose message carries the `Co-Authored-By: Claude` trailer, which is the
mechanical fact this repository can check. It is NOT a measure of who thought of
what, and a commit without the trailer is not evidence that no tool was used —
the trailer convention only starts in July 2026 (CHARTER §9).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "processed" / "timeline_roles" / "timeline_roles.json"

TRAILER = "Co-Authored-By: Claude"

#: Phase boundaries are the calendar gaps in the record, not a narrative imposed
#: on it: the commit dates jump 06-15 -> 07-18, 07-26 -> 08-01, 08-12 -> 08-28
#: and 09-01 -> 09-03, and each phase below is one of the resulting blocks. The
#: `anchor` is a path whose FIRST appearance dates the phase, or a tag; it is
#: resolved from git, never typed.
PHASES = [
    {
        "id": "p1",
        "name_ko": "1기 · 착수와 물리 모델",
        "start": "2026-05-27", "end": "2026-06-15",
        "anchor_kind": "path", "anchor": "README.md",
        "what_ko": "Rothermel 점 모델과 Huygens 타원 CA 뼈대, CRS 인지 FireGrid, "
                   "SRTM 지형, 영덕 검증 하네스",
    },
    {
        "id": "p2",
        "name_ko": "2기 · 1차 정리와 Round 2 제출",
        "start": "2026-07-18", "end": "2026-07-26",
        "anchor_kind": "tag", "anchor": "round2-submitted",
        "what_ko": "Round 2 보고서 두 편, 제출 시점의 트리에 태그",
    },
    {
        "id": "p3",
        "name_ko": "3기 · Round 3 개발",
        "start": "2026-08-01", "end": "2026-08-12",
        "anchor_kind": "path", "anchor": "docs/HANDOFF_ROUND3.md",
        "what_ko": "구조 라우팅, 배차 산출물, 인수인계 문서와 그 24개 규칙",
    },
    {
        "id": "p4",
        "name_ko": "4기 · 세션 기록 정리와 재현성",
        "start": "2026-08-28", "end": "2026-09-01",
        "anchor_kind": "path", "anchor": "docs/SESSION22_REPORT.md",
        "what_ko": "세션 보고서 정리, 숫자 등록부와 게이트 정비",
    },
    {
        "id": "p5",
        "name_ko": "5기 · 자율 루프 스프린트",
        "start": "2026-09-03", "end": None,
        "anchor_kind": "path", "anchor": "docs/auto/CHARTER.md",
        "what_ko": "헌장·백로그·리포트 루프, 결선 화면과 인쇄물, 논문 원고",
    },
]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True, env={"TZ": "UTC", "PATH": "/usr/bin:/bin",
                                          "HOME": str(Path.home())}).stdout.strip()


def is_shallow() -> bool:
    return _git("rev-parse", "--is-shallow-repository") == "true"


def commits() -> list[dict]:
    raw = _git("log", "--format=%H%x1f%ad%x1f%b%x1e",
               "--date=format-local:%Y-%m-%d", "HEAD")
    out = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, date, body = rec.split("\x1f", 2)
        out.append({"sha": sha, "date": date, "agent": TRAILER in body})
    return out


def anchor_commit(phase: dict) -> str:
    """The short sha that dates this phase, resolved from git rather than typed."""
    if phase["anchor_kind"] == "tag":
        return _git("rev-list", "-n", "1", "--abbrev-commit", phase["anchor"])
    line = _git("log", "--diff-filter=A", "--format=%h", "--", phase["anchor"])
    return line.splitlines()[-1] if line else ""


def build() -> dict:
    rows = commits()
    dates = sorted({c["date"] for c in rows})
    phases = []
    for spec in PHASES:
        end = spec["end"] or dates[-1]
        inside = [c for c in rows if spec["start"] <= c["date"] <= end]
        phases.append({
            "id": spec["id"],
            "name_ko": spec["name_ko"],
            "what_ko": spec["what_ko"],
            "start": spec["start"],
            "end": end,
            "end_is_open": spec["end"] is None,
            "commits": len(inside),
            "agent_trailer_commits": sum(c["agent"] for c in inside),
            "active_days": len({c["date"] for c in inside}),
            "anchor": spec["anchor"],
            "anchor_kind": spec["anchor_kind"],
            "anchor_commit": anchor_commit(spec),
        })
    covered = sum(p["commits"] for p in phases)
    return {
        "_readme": "Built by scripts/build_timeline_roles.py from git log on HEAD "
                   "(WFG-027). Every date and count in "
                   "docs/auto/finals/TIMELINE_ROLES.md is checked against this "
                   "file by tests/test_timeline_roles.py.",
        "ref": "HEAD",
        "first_commit_date": dates[0],
        "last_commit_date": dates[-1],
        "total_commits": len(rows),
        "active_days": len(dates),
        "agent_trailer_commits": sum(c["agent"] for c in rows),
        "other_commits": len(rows) - sum(c["agent"] for c in rows),
        "commits_inside_phases": covered,
        "commits_outside_phases": len(rows) - covered,
        "phases": phases,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if is_shallow():
        print("shallow clone: the full history is not present, so the timeline "
              "cannot be rebuilt or checked here. Run "
              "`git fetch --unshallow origin` first.")
        return 2
    fresh = build()
    if args.check:
        if not OUT.exists():
            print(f"MISSING {OUT.relative_to(REPO)}")
            return 1
        have = json.loads(OUT.read_text(encoding="utf-8"))
        # The tree grows every lap, so the LAST phase's counts and the two
        # totals move under a stale-but-correct artifact; that is growth, not
        # drift, and CHARTER §3d draws the same line for the baseline freeze.
        # What must never move is the settled past: the first commit's date and
        # every phase's start and anchor commit.
        drift = []
        if have.get("first_commit_date") != fresh["first_commit_date"]:
            drift.append("first_commit_date")
        def spine(doc):
            return [(p["id"], p["start"], p["anchor_commit"]) for p in doc["phases"]]
        if spine(have) != spine(fresh):
            drift.append("phase starts or anchor commits")
        for h, f in zip(have["phases"][:-1], fresh["phases"][:-1]):
            if (h["commits"], h["active_days"]) != (f["commits"], f["active_days"]):
                drift.append(f"{h['id']} counts")
        if drift:
            print("STALE timeline artifact: " + ", ".join(drift))
            return 1
        print(f"OK — timeline artifact agrees with git log "
              f"({fresh['total_commits']} commits, {fresh['active_days']} active days)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fresh, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} — {fresh['total_commits']} commits, "
          f"{fresh['active_days']} active days, "
          f"{fresh['agent_trailer_commits']} with the Claude trailer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
