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


RAW = "https://raw.githubusercontent.com/Sparkxt-0318/wildfireguardian/auto/dev"
BLOB = "https://github.com/Sparkxt-0318/wildfireguardian/blob/auto/dev"
PREVIEW = "https://htmlpreview.github.io/?https://github.com/Sparkxt-0318/wildfireguardian/blob/auto/dev/docs/auto/dashboard.html"

CAPTIONS = [
    ("01_full_map.png", "The whole system. Highlighted boxes are where this lap worked; everything else was untouched."),
    ("02_changes.png", "What changed in this lap, by area of the system."),
    ("03_backlog.png", "The plan: how much of each priority band is done, in progress, waiting, or blocked."),
    ("04_rubric.png", "The loop's estimate of the five judging rows (Track B). Not a judge's score."),
    ("05_timeline.png", "Every lap so far on the road to the freeze and the finals."),
]


def write_email_html(path: Path, title: str, summary: str, stamp: str, branch: str, head: str, gates: dict | None, needs: list[str], report_path: Path) -> None:
    """The HTML body the routine sends. Images are referenced by their GitHub raw
    URL on auto/dev (public repository), so the email carries no attachment and
    shows this lap's own images once the push has landed."""
    m = re.search(r"## In plain terms\s*\n(.*?)(?:\n## |\Z)", summary, flags=re.S)
    plain = (m.group(1).strip() if m else "").replace("**", "")
    plain_html = "".join(f"<p style='margin:0 0 10px'>{html_escape(p)}</p>" for p in re.split(r"\n\s*\n", plain) if p.strip()) or "<p><i>This lap did not write a plain-terms note.</i></p>"
    gate_line = "gates: " + ("ALL GREEN" if gates and gates.get("passed") else "RED" if gates else "not run")
    imgs = "".join(
        f"<figure style='margin:18px 0'><img src='{RAW}/docs/auto/images/{stamp}/{fn}' alt='{html_escape(cap)}' style='max-width:100%;border:1px solid #DDD8CE;border-radius:4px'>"
        f"<figcaption style='font:13px/1.4 -apple-system,Segoe UI,Arial,sans-serif;color:#6F6A62;margin-top:6px'>{html_escape(cap)}</figcaption></figure>"
        for fn, cap in CAPTIONS)
    needs_html = "".join(f"<li>{html_escape(n)}</li>" for n in needs) or "<li>nothing; the loop is not blocked</li>"
    decisions = decisions_block()
    rel = report_path.relative_to(REPO) if report_path.is_relative_to(REPO) else report_path
    body = f"""<div style="font:15px/1.5 -apple-system,Segoe UI,Arial,sans-serif;color:#1B1F23;max-width:760px">
<h2 style="font-weight:600;margin:0 0 4px">{html_escape(title)}</h2>
<p style="color:#6F6A62;margin:0 0 16px">{branch} @ {head} · {gate_line} · <a href="{PREVIEW}">open the visual board</a> · <a href="{BLOB}/{rel}">full report on GitHub</a></p>
<div style="border-left:4px solid #B4471B;background:#F3E3D9;padding:12px 16px;margin:0 0 18px"><b>In plain terms</b><div style="margin-top:6px">{plain_html}</div></div>
{decisions}
{imgs}
<h3 style="font-weight:600;margin:22px 0 6px">Needs you ({len(needs)} open)</h3><ul>{needs_html}</ul>
<p style="color:#6F6A62;font-size:13px;margin-top:22px">Images and the board are files in the repository (docs/auto/images/{stamp}/, docs/auto/dashboard.html); if an image does not load yet, the push is still propagating. Reply to this email with a decision and the next lap folds it in.</p>
</div>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print(f"[report] email body -> {path.relative_to(REPO)}")


def decisions_block() -> str:
    """Open DECISION/BLOCKER entries as a reply form: one line per item closes it.

    The routine that sends this email also reads the mailbox, so a reply of the form
    `NH-018: B` is picked up by the next lap, recorded through
    scripts/auto/decisions.py with the Gmail message id, and acted on."""
    try:
        text = NEEDS.read_text(encoding="utf-8")
    except OSError:
        return ""
    items = []
    for m in re.finditer(r"^## (NH-\d+)\s*·\s*(DECISION|BLOCKER)\s*·\s*open\s*·\s*(.*)$", text, flags=re.M):
        nid, sev, title = m.group(1), m.group(2), m.group(3).strip()
        body = text[m.end(): text.find("\n## ", m.end()) if text.find("\n## ", m.end()) > 0 else len(text)]
        opts = re.search(r"\*\*Options:\*\*\s*(.*?)(?:\n\n|\Z)", body, flags=re.S)
        items.append((nid, sev, title, opts.group(1).strip().replace("\n", " ") if opts else ""))
    if not items:
        return ""
    rows = "".join(
        f"<li style='margin:0 0 8px'><b>{nid}</b> <span style='color:#6F6A62'>[{sev}]</span> {html_escape(title)}"
        + (f"<br><span style='color:#6F6A62'>options: {html_escape(o)}</span>" if o else "")
        + f"<br><code style='background:#EEE9DF;padding:1px 6px'>{nid}: &lt;your decision&gt;</code></li>"
        for nid, sev, title, o in items)
    return (f"<div style='border:1px solid #DDD8CE;border-radius:4px;padding:12px 16px;margin:0 0 18px'>"
            f"<b>Decisions needed ({len(items)})</b>"
            f"<p style='margin:6px 0 10px;color:#6F6A62'>Easiest: open Claude Code in the repository and say <code>decisions</code>; it asks each item as a button question and records your answers (NH-020). Or reply to this email with one line per item, exactly "
            f"<code>NH-###: your decision</code> (a letter, yes/no, or a sentence). The next lap reads the reply, "
            f"records it in NEEDS_HUMAN.md with the message id and date, acts on it, and confirms in its report. "
            f"Anything else in the reply is ignored.</p><ul style='margin:0;padding-left:18px'>{rows}</ul></div>")


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def prose_gate_commands() -> list[tuple[list[str], str]]:
    # The Makefile defaults to PYTHON=python, which need not exist in the sandbox
    # (python3.11 does). Splice this interpreter in the way gates.py does, quoted,
    # because make pastes it into a shell recipe verbatim and the author's laptop
    # keeps the repository under a path with a space in it.
    py = sys.executable
    make_py = "PYTHON=" + (f'"{py}"' if any(c.isspace() for c in py) else py)
    return [
        (["make", make_py, "check-forbidden"], "retired claims and unlabelled superseded numbers"),
        ([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_rescue_lineage_ssot.py"],
         "the rescue bracket's lineage label"),
    ]


def prose_gates(report_path: Path) -> int:
    """Run the seconds-long prose gates over the report this script just wrote.

    The report is tracked prose that the prose gates read, and it does not exist
    when `gates.py` runs at CHARTER §4 step 5 — which is how `24751fa` and `8d1decf`
    were pushed onto a red `auto/dev` (critic #2 and #3). The report is written
    first and then checked, so a lap that trips this still has the file to repair;
    only the exit code says do not commit it yet.

    Deliberately not the full suite: three minutes here would be worked around,
    and the head-level check that covers everything else is
    `gates.py --assert-head` (WFG-046 b).
    """
    bad = []
    for cmd, what in prose_gate_commands():
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        print(f"[report] prose gate {'PASS' if r.returncode == 0 else 'FAIL'}: {what}")
        if r.returncode != 0:
            bad.append((what, (r.stdout or r.stderr).strip().splitlines()[-25:]))
    if not bad:
        return 0
    print(f"\n[report] the report at {report_path.relative_to(REPO)} does not pass the prose gates.")
    print("[report] fix the report, re-run this script, and only then commit. Details:")
    for what, tail in bad:
        print(f"  --- {what} ---")
        for line in tail:
            print(f"  {line}")
    return 1


def gate_block_for(gates: dict | None, head: str) -> str:
    """Render the report's `## Gates` block, and say which commit it certifies.

    A report headed ALL GREEN is read as "this branch is green". What the table
    certifies is only the commit the gates actually read, and in two of the loop's
    first three laps that commit was several commits and hundreds of lines behind
    what the lap then pushed (critic #3, F14). The report is where a judge and the
    critic look, so the gap is named here in words rather than left to be
    reconstructed from two short hashes printed in different sections.
    """
    if not gates:
        return "(gates not run this lap)"
    rows = "\n".join(
        f"| {s['name']} | {'PASS' if s['passed'] else ('FAIL' if s['hard'] else 'WARN')} | {s['seconds']} s | {s['tail'][-1] if s['tail'] else ''} |"
        for s in gates["steps"]
    )
    if gates.get("git_head") == head:
        currency = f" · current at `{head}`"
    else:
        currency = (f" · ⚠ **stale: the gates read `{gates.get('git_head')}`, HEAD is `{head}`** — this table "
                    f"does not certify the pushed tree; re-run `gates.py --mode {gates.get('mode')}` and "
                    "`gates.py --assert-head` before pushing")
    return (f"**{'ALL GREEN' if gates['passed'] else 'RED'}** · mode `{gates['mode']}` · "
            f"head `{gates['git_head']}` · {gates['written_at_utc']}{currency}\n\n"
            f"| step | result | time | last line |\n|---|---|---|---|\n{rows}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["dev", "critic", "research", "kickoff", "red", "manual"])
    ap.add_argument("--summary", help="markdown file written by the agent: what it did and why")
    ap.add_argument("--title", default=None)
    ap.add_argument("--email", action="store_true")
    ap.add_argument("--stdout", action="store_true", help="also print the report")
    ap.add_argument("--dry-run", action="store_true", help="write everything under .auto/ instead of docs/auto/")
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

    gate_block = gate_block_for(gates, head)
    boot_line = (f"python {boot.get('python_version')} · pins_ok={boot.get('pins_ok')} · stack_ok={boot.get('stack_ok')} · {boot.get('platform')}" if boot else "(no bootstrap record)")

    # ⚠ Hoisted out of the body f-string ON PURPOSE. Python 3.11 — the sandbox
    # and CI interpreter — rejects a backslash anywhere inside an f-string
    # EXPRESSION, so the "\n" in this fallback was a SyntaxError at import time:
    # report.py could not run at all, and a lap that cannot write its report is
    # a failed lap. The relaxation landed in 3.12 (PEP 701), which is why this
    # parsed on the machine it was written on.
    plain_terms_fallback = "" if "## In plain terms" in summary else (
        "## In plain terms\n\n(The lap did not write this section. It should "
        "say, in three lines for the author: what changed for the project, why "
        "it matters to the judges, what you should do.)"
    )

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

{plain_terms_fallback}

## Gates

{gate_block}

## Commits since the previous report ({log_range})

{commits}

## Needs a human ({len(needs)} open)

{chr(10).join('- ' + n for n in needs) if needs else '- nothing — the loop is not blocked'}

---
Generated by `scripts/auto/report.py`. Charter: `docs/auto/CHARTER.md`. Backlog: `docs/auto/BACKLOG.md`.
"""
    reports_dir = (REPO / ".auto" / "dryrun" / "reports") if args.dry_run else REPORTS
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"{stamp}-{args.kind}.md"
    out.write_text(body)
    if not args.dry_run:
        state.update({"last_report": str(out.relative_to(REPO)), "last_report_commit": git("rev-parse", "HEAD"),
                  "last_report_kind": args.kind, "last_report_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "last_gates_passed": gates["passed"] if gates else None, "open_needs_human": len(needs)})
        STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    print(f"[report] wrote {out.relative_to(REPO)}")
    # the author's one-page visual board and the five images are rebuilt from the
    # same files every lap; images go to docs/auto/images/<stamp>/ so the email can
    # embed them by GitHub raw URL (hand-typed base64 attachments proved unreliable,
    # docs/auto/MEMO.md 2026-09-03)
    img_root = (REPO / ".auto" / "dryrun" / "images") if args.dry_run else (REPO / "docs" / "auto" / "images")
    board_out = (REPO / ".auto" / "dryrun" / "dashboard.html") if args.dry_run else (REPO / "docs" / "auto" / "dashboard.html")
    for cmd in ([sys.executable, str(REPO / "scripts" / "auto" / "dashboard.py"), "--out", str(board_out)],
                [sys.executable, str(REPO / "scripts" / "auto" / "render_images.py"), "--stamp", stamp, "--out", str(img_root),
                 *(["--since", since] if since else [])]):
        try:
            r = subprocess.run(cmd, cwd=REPO, check=False, capture_output=True, text=True)
            print((r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else f"[report] ran {cmd[1].rsplit('/', 1)[-1]}")
        except Exception as e:  # noqa: BLE001
            print(f"[report] {cmd[1]} failed: {e}")
    write_email_html(REPO / ".auto" / "email.html", title, summary, stamp, branch, head, gates, needs, out)
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

    return prose_gates(out)


if __name__ == "__main__":
    raise SystemExit(main())
