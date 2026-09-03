#!/usr/bin/env python
"""Assemble one loop report from what actually happened, and optionally email it.

    python scripts/auto/report.py --kind dev --summary .auto/summary.md
    python scripts/auto/report.py --kind kickoff --summary path.md --title "..."
    python scripts/auto/report.py --kind dev --summary s.md --email     # SMTP_* env

Inputs it reads (all optional, all reported as absent if missing):
  .auto/gates.json, .auto/bootstrap.json        from bootstrap.sh / gates.py
  docs/auto/NEEDS_HUMAN.md                      open items (## NH-… headers)
  docs/auto/BACKLOG.md                          status counts
  git log since the previous report's commit
Output: docs/auto/reports/<UTC>-<kind>.md and docs/auto/STATE.json (updated).

Email is sent only when SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD and REPORT_TO are
all set; otherwise the report is written and the GitHub workflow
.github/workflows/report-email.yml delivers it on push. This script imports
only the standard library, so it runs before the venv exists.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import smtplib
import subprocess
import sys
from email.mime.text import MIMEText
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "docs" / "auto" / "reports"
STATE = REPO / "docs" / "auto" / "STATE.json"
NEEDS = REPO / "docs" / "auto" / "NEEDS_HUMAN.md"
BACKLOG = REPO / "docs" / "auto" / "BACKLOG.md"


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def load_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def open_needs() -> list[str]:
    if not NEEDS.exists():
        return []
    out = []
    for line in NEEDS.read_text().splitlines():
        m = re.match(r"^## (NH-\d+)\s*·\s*(\w+)\s*·\s*(\w+)\s*·\s*(.*)$", line)
        if m and m.group(3).lower() == "open":
            out.append(f"{m.group(1)} [{m.group(2)}] {m.group(4).strip()}")
    return out


def backlog_counts() -> dict:
    if not BACKLOG.exists():
        return {}
    counts: dict[str, int] = {}
    for line in BACKLOG.read_text().splitlines():
        # The status word may carry a parenthesised argument: `in-progress(<stamp>)`,
        # `done(<commit>)`, `blocked(NH-###)`, `dropped(why)` (CHARTER §5). Without
        # the optional group only bare `todo` matched, so every row the loop had
        # started or finished vanished from the counts in its own report.
        m = re.match(r"^\|\s*WFG-\d+\s*\|[^|]*\|[^|]*\|[^|]*\|\s*([a-z\-]+)(?:\([^)|]*\))?\s*\|", line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["dev", "critic", "research", "kickoff", "red", "manual"])
    ap.add_argument("--summary", help="markdown file written by the agent: what it did and why")
    ap.add_argument("--title", default=None)
    ap.add_argument("--email", action="store_true")
    ap.add_argument("--stdout", action="store_true", help="also print the report")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H%MZ")
    kst = (now + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
    head, branch = git("rev-parse", "--short", "HEAD"), git("rev-parse", "--abbrev-ref", "HEAD")

    state = load_json(STATE) or {}
    since = state.get("last_report_commit")
    log_range = f"{since}..HEAD" if since and git("cat-file", "-t", since) == "commit" else "-15"
    commits = git("log", "--no-merges", "--format=- %h %s", log_range) or "(no new commits)"

    gates = load_json(REPO / ".auto" / "gates.json")
    boot = load_json(REPO / ".auto" / "bootstrap.json")
    summary = Path(args.summary).read_text().strip() if args.summary and Path(args.summary).exists() else "(no summary supplied)"
    title = args.title or f"WildfireGuardian autoloop · {args.kind} · {stamp}"
    needs = open_needs()
    counts = backlog_counts()

    gate_block = "(gates not run this lap)"
    if gates:
        rows = "\n".join(f"| {s['name']} | {'PASS' if s['passed'] else ('FAIL' if s['hard'] else 'WARN')} | {s['seconds']} s | {s['tail'][-1] if s['tail'] else ''} |" for s in gates["steps"])
        gate_block = (f"**{'ALL GREEN' if gates['passed'] else 'RED'}** · mode `{gates['mode']}` · head `{gates['git_head']}` · {gates['written_at_utc']}\n\n"
                      f"| step | result | time | last line |\n|---|---|---|---|\n{rows}")
    boot_line = (f"python {boot.get('python_version')} · pins_ok={boot.get('pins_ok')} · stack_ok={boot.get('stack_ok')} · {boot.get('platform')}" if boot else "(no bootstrap record)")

    body = f"""# {title}

| | |
|---|---|
| when | {now.strftime('%Y-%m-%d %H:%M UTC')} · {kst} |
| branch / head | `{branch}` / `{head}` |
| kind | {args.kind} |
| environment | {boot_line} |
| backlog | {', '.join(f'{k}: {v}' for k, v in sorted(counts.items())) or '(no backlog table found)'} |

## What happened this lap

{summary}

{"" if "## In plain terms" in summary else "## In plain terms\n\n(The lap did not write this section. It should say, in three lines for the author: what changed for the project, why it matters to the judges, what you should do.)"}

## Gates

{gate_block}

## Commits since the previous report ({log_range})

{commits}

## Needs a human ({len(needs)} open)

{chr(10).join('- ' + n for n in needs) if needs else '- nothing — the loop is not blocked'}

---
Generated by `scripts/auto/report.py`. Charter: `docs/auto/CHARTER.md`. Backlog: `docs/auto/BACKLOG.md`.
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{stamp}-{args.kind}.md"
    out.write_text(body)
    state.update({"last_report": str(out.relative_to(REPO)), "last_report_commit": git("rev-parse", "HEAD"),
                  "last_report_kind": args.kind, "last_report_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "last_gates_passed": gates["passed"] if gates else None, "open_needs_human": len(needs)})
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    print(f"[report] wrote {out.relative_to(REPO)}")
    # the author's one-page visual board is rebuilt from the same files every lap
    try:
        subprocess.run([sys.executable, str(REPO / "scripts" / "auto" / "dashboard.py")], cwd=REPO, check=False)
    except Exception as e:  # noqa: BLE001
        print(f"[report] dashboard not rebuilt: {e}")
    if args.stdout:
        print(body)

    if args.email:
        env = {k: os.environ.get(k, "") for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "REPORT_TO")}
        if all(env[k] for k in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "REPORT_TO")):
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"], msg["From"], msg["To"] = title, env["SMTP_USERNAME"], env["REPORT_TO"]
            with smtplib.SMTP_SSL(env["SMTP_HOST"], int(env["SMTP_PORT"] or 465)) as s:
                s.login(env["SMTP_USERNAME"], env["SMTP_PASSWORD"])
                s.sendmail(env["SMTP_USERNAME"], [env["REPORT_TO"]], msg.as_string())
            print(f"[report] emailed to {env['REPORT_TO']}")
        else:
            print("[report] SMTP_* not set; leaving delivery to .github/workflows/report-email.yml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
