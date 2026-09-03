#!/usr/bin/env python
"""Build the one-page visual report the author reads: docs/auto/dashboard.html.

Reads the loop's own files (BACKLOG.md, NEEDS_HUMAN.md, STATE.json, reports/,
SCORECARD.md, git log) and draws, with no external library: the countdown and
four status tiles, the latest "in plain terms" note, a project map (the
pipeline as a layered graph with each stage's status and the backlog rows that
touch it), the backlog board, the rubric scorecard, the open decisions, and the
lap timeline. Self-contained HTML (inline CSS/SVG; Google Fonts with real
fallbacks) so it opens from an email attachment or from file:// with no network.

    python scripts/auto/dashboard.py            # writes docs/auto/dashboard.html
    python scripts/auto/dashboard.py --out x.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTO = REPO / "docs" / "auto"

STATUS_KIND = {"done": "done", "in-progress": "progress", "blocked": "blocked", "parked": "parked", "todo": "todo"}
PRIO_LABEL = {"P0": "P0 · before the freeze", "P1": "P1 · before the finals", "P2": "P2 · after the finals (ISEF)", "P3": "P3 · for the IEEE paper"}

# The project map: the pipeline the judges will be shown, as stages. Each stage
# lists keywords; a backlog row attaches to the first stage whose keyword it
# mentions. Order is the flow of data through the system.
STAGES = [
    ("data", "Public data", "FIRMS · SRTM · WorldCover · ERA5 · OSM", ["data", "footprint", "building", "OSM", "manifest", "survey", "greenpeace"]),
    ("spread", "Spread model", "P(ignite) per cell · LOGO-CV on 6 fires", ["recall", "operating", "LOFO", "fold", "threshold", "AUC", "spread", "leak"]),
    ("hazard", "Hazard field", "time-sliced probability surface", ["hazard", "wind", "uncertainty", "sweep"]),
    ("routing", "Routing (time-aware)", "walk-out routes that avoid where the fire will be", ["routing", "route", "refuge", "decimation", "coupling", "delay", "walking"]),
    ("rescue", "Rescue ingress", "which homes a crew can still reach, and until when", ["rescue", "dispatch", "ingress", "closure"]),
    ("decision", "Decision & delivery", "A4 sheet · 마을방송 script · SMS draft", ["email", "SMS", "delivery", "send", "operator"]),
    ("evidence", "Evidence registry", "NUMBERS.json · make verify · withdrawn claims", ["reconcil", "SSOT", "registry", "NUMBERS", "CITATION", "ledger", "number", "README", "abstract", "ISEF plan", "paper", "reproduc"]),
    ("booth", "Finals booth", "finals.html · 5-min demo · judge Q&A", ["finals", "demo", "judge", "Q&A", "rehears", "booth", "poster", "schedule", "consult", "detection-floor", "detection floor", "Playwright", "screen"]),
]


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def parse_backlog() -> list[dict]:
    rows = []
    for line in (AUTO / "BACKLOG.md").read_text().splitlines():
        m = re.match(r"^\|\s*(WFG-\d+)\s*\|\s*(P\d)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|\s*$", line)
        if not m:
            continue
        idn, p, goal, title, status, agent, effort, rub = m.groups()
        kind = next((v for k, v in STATUS_KIND.items() if status.startswith(k)), "todo")
        human = "false" in agent.lower() and "true" not in agent.lower()
        stage = "evidence"
        low = title.lower()
        for sid, _, _, kws in STAGES:
            if any(k.lower() in low for k in kws):
                stage = sid
                break
        rows.append(dict(id=idn, p=p, goal=goal, title=title, status=status, kind=kind, human=human, effort=effort, rubric=rub, stage=stage))
    return rows


def parse_needs() -> list[dict]:
    out = []
    txt = (AUTO / "NEEDS_HUMAN.md").read_text()
    for m in re.finditer(r"^## (NH-\d+)\s*·\s*(\w+)\s*·\s*(\w+)\s*·\s*(.*)$", txt, flags=re.M):
        nid, sev, st, title = m.groups()
        body = txt[m.end():]
        nxt = body.find("\n## ")
        body = body[:nxt if nxt > 0 else None]
        what = re.search(r"\*\*What:\*\*\s*(.*?)(?:\n\n|\*\*Why)", body, flags=re.S)
        out.append(dict(id=nid, sev=sev, open=st.lower() == "open", title=title.strip(), what=(what.group(1).strip() if what else "")))
    return out


def parse_reports() -> list[dict]:
    reps = []
    for f in sorted((AUTO / "reports").glob("*.md")):
        if f.name == "README.md":
            continue
        t = f.read_text()
        m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{4}Z)-(\w+)\.md", f.name)
        plain = re.search(r"## In plain terms\s*\n(.*?)(?:\n## |\Z)", t, flags=re.S)
        what = re.search(r"## What happened this lap\s*\n(.*?)(?:\n## |\Z)", t, flags=re.S)
        gates = "green" if "**ALL GREEN**" in t else ("red" if "**RED**" in t else "none")
        reps.append(dict(stamp=m.group(1) if m else f.stem, kind=m.group(2) if m else "?", gates=gates,
                         plain=(plain.group(1).strip() if plain else ""),
                         what=(what.group(1).strip() if what else ""), path=f.name))
    return reps


def parse_scorecard() -> list[tuple[str, float]]:
    """Latest row of docs/auto/SCORECARD.md if the critic has written one; else the
    2026-09-03 research-sweep estimate, labelled as such."""
    p = AUTO / "SCORECARD.md"
    rows_b = ["연구 목적", "설계와 방법론", "데이터 수집·분석·해석", "창의성", "제출 자료"]
    if p.exists():
        last = None
        for line in p.read_text().splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 6 and re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
                try:
                    last = [float(c) for c in cells[1:6]]
                except ValueError:
                    continue
        if last:
            return list(zip(rows_b, last)), "critic lap"
    return list(zip(rows_b, [17, 14, 14, 16, 15])), "research sweep estimate, 2026-09-03"


def first_sentence(md: str, n: int = 260) -> str:
    s = re.sub(r"[*`#>]", "", md).strip().replace("\n", " ")
    return (s[: n - 1] + "…") if len(s) > n else s


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def build() -> str:
    state = load_json(AUTO / "STATE.json")
    rows = parse_backlog()
    needs = parse_needs()
    reps = parse_reports()
    score, score_src = parse_scorecard()
    now = dt.datetime.now(dt.timezone.utc)
    finals = dt.date.fromisoformat(state.get("finals_date", "2026-10-18"))
    freeze = dt.date.fromisoformat(state.get("freeze_date", "2026-10-10"))
    days_finals = (finals - now.date()).days
    days_freeze = (freeze - now.date()).days
    head = git("rev-parse", "--short", "HEAD")
    commits_24h = git("rev-list", "--count", "--since=24 hours ago", "HEAD")
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in ("done", "progress", "todo", "blocked", "parked")}
    open_needs = [n for n in needs if n["open"]]
    latest = reps[-1] if reps else None
    latest_plain = next((r["plain"] for r in reversed(reps) if r["plain"]), "")
    gates_word = {"green": "green", "red": "RED", "none": "not run"}[latest["gates"] if latest else "none"]

    # ---- project map (SVG) ------------------------------------------------
    W, H = 1080, 300
    n = len(STAGES)
    bw, bh, gap = 118, 132, (W - 40 - 118 * n) / (n - 1)
    parts = []
    for i, (sid, name, sub, _) in enumerate(STAGES):
        x = 20 + i * (bw + gap)
        y = 60
        attached = [r for r in rows if r["stage"] == sid]
        kinds = {r["kind"] for r in attached}
        state_k = "blocked" if kinds == {"blocked"} and attached else ("progress" if "progress" in kinds else ("todo" if "todo" in kinds else ("done" if attached else "quiet")))
        p0 = sum(1 for r in attached if r["p"] == "P0" and r["kind"] not in ("done",))
        parts.append(f'<g class="stage {state_k}"><rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="6"/>'
                     f'<rect class="stripe" x="{x}" y="{y}" width="{bw}" height="5"/>'
                     f'<text class="sname" x="{x + 10}" y="{y + 28}">{esc(name)}</text>')
        # wrap subtitle into <= 3 lines of ~18 chars
        words, lines, cur = sub.split(" "), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 19 and cur:
                lines.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        for j, l in enumerate(lines[:3]):
            parts.append(f'<text class="ssub" x="{x + 10}" y="{y + 46 + j * 14}">{esc(l)}</text>')
        ids = [r["id"].replace("WFG-0", "").replace("WFG-", "") for r in attached if r["kind"] != "done"]
        label = ("rows " + ", ".join(ids[:6]) + ("…" if len(ids) > 6 else "")) if ids else ("done" if attached else "stable")
        parts.append(f'<text class="srows" x="{x + 10}" y="{y + bh - 26}">{esc(label)}</text>')
        parts.append(f'<text class="sp0" x="{x + 10}" y="{y + bh - 10}">{"P0 open: " + str(p0) if p0 else ""}</text></g>')
        if i < n - 1:
            x2 = x + bw
            parts.append(f'<path class="edge" d="M{x2 + 2},{y + bh / 2} L{x2 + gap - 4},{y + bh / 2}"/>'
                         f'<path class="edge" d="M{x2 + gap - 9},{y + bh / 2 - 4} L{x2 + gap - 3},{y + bh / 2} L{x2 + gap - 9},{y + bh / 2 + 4}"/>')
    # cross-cutting bracket: evidence registry and booth sit under all stages
    parts.append(f'<text class="axis" x="20" y="{H - 40}">flow of one fire: detection → forecast → decision → delivery; the last two stages stand under all of it</text>')
    parts.append(f'<text class="axis" x="20" y="{H - 22}">stripe colour = state of the backlog rows that touch the stage: amber in progress, ember blocked, ink still to do, green done, grey stable</text>')
    svg_map = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="project map">' + "".join(parts) + "</svg>"

    # ---- scorecard (SVG bars) -----------------------------------------------
    sw, sh = 520, 34 * len(score) + 30
    sp = []
    for i, (name, v) in enumerate(score):
        y = 10 + i * 34
        sp.append(f'<text class="slabel" x="0" y="{y + 16}">{esc(name)}</text>'
                  f'<rect class="track" x="180" y="{y + 4}" width="300" height="16" rx="3"/>'
                  f'<rect class="fill" x="180" y="{y + 4}" width="{300 * v / 20:.0f}" height="16" rx="3"/>'
                  f'<text class="sval" x="{490}" y="{y + 16}">{v:g}/20</text>')
    total = sum(v for _, v in score)
    svg_score = f'<svg viewBox="0 0 {sw} {sh}" role="img" aria-label="rubric scorecard">' + "".join(sp) + "</svg>"

    # ---- backlog board ---------------------------------------------------------
    cols = []
    for p in ("P0", "P1", "P2", "P3"):
        items = [r for r in rows if r["p"] == p]
        li = "".join(
            f'<li class="row {r["kind"]}{" human" if r["human"] else ""}"><span class="rid">{r["id"]}</span>'
            f'<span class="rtitle">{esc(re.sub(r"[*`]", "", r["title"]))}</span>'
            f'<span class="chip {r["kind"]}">{esc(r["status"].split("(")[0])}</span>'
            f'{"<span class=\"chip who\">you</span>" if r["human"] else ""}</li>'
            for r in items)
        cols.append(f'<section class="col"><h3>{esc(PRIO_LABEL[p])} <span class="count">{len(items)}</span></h3><ul>{li}</ul></section>')

    # ---- needs-you cards -------------------------------------------------------
    nd = "".join(
        f'<li class="need {n["sev"].lower()}"><span class="nid">{n["id"]} · {n["sev"]}</span>'
        f'<strong>{esc(n["title"])}</strong><p>{esc(first_sentence(n["what"], 320))}</p></li>'
        for n in open_needs)

    # ---- timeline ---------------------------------------------------------------
    tl = "".join(
        f'<li class="lap {r["gates"]}"><span class="stamp">{r["stamp"].replace("T", " ").replace("Z", " UTC")}</span>'
        f'<span class="kind">{r["kind"]}</span><span class="gate">gates {r["gates"] if r["gates"] != "none" else "not run"}</span>'
        f'<p>{esc(first_sentence(r["plain"] or r["what"], 300))}</p></li>'
        for r in reversed(reps))

    plain_block = (f'<blockquote class="plain">{esc(latest_plain)}</blockquote>' if latest_plain else
                   '<p class="plain-empty">The next lap will write a three-line "in plain terms" note here: what changed for the project, why it matters to the judges, and what you should do.</p>')

    return f'''<title>WildfireGuardian Loop Board</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--ground:#F4F2EC;--panel:#FFFFFF;--ink:#1B1F23;--muted:#6F6A62;--line:#DDD8CE;--accent:#B4471B;--accent-soft:#F3E3D9;
--done:#2E7D4F;--progress:#B7791F;--blocked:#B42318;--todo:#3B4149;--parked:#8A8580;--quiet:#B8B3AA;
--display:"Fraunces",Georgia,"Times New Roman",serif;--body:"Source Sans 3","Helvetica Neue",Arial,sans-serif;--mono:"IBM Plex Mono",Menlo,Consolas,monospace}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--ground:#12151A;--panel:#1A1F26;--ink:#E8E6E1;--muted:#9A958C;--line:#2B313A;--accent:#E0764A;--accent-soft:#3A2419;--todo:#C9CDD3;--quiet:#4A5059}}}}
:root[data-theme="dark"]{{--ground:#12151A;--panel:#1A1F26;--ink:#E8E6E1;--muted:#9A958C;--line:#2B313A;--accent:#E0764A;--accent-soft:#3A2419;--todo:#C9CDD3;--quiet:#4A5059}}
body{{margin:0;background:var(--ground);color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.45}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 24px 56px}}
header{{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:18px}}
h1{{font-family:var(--display);font-weight:500;font-size:34px;margin:0;letter-spacing:-.01em;text-wrap:balance}}
.sub{{color:var(--muted);margin:6px 0 0}}
.countdown{{font-family:var(--mono);text-align:right;color:var(--muted);font-size:13px}}
.countdown b{{display:block;font-family:var(--display);font-size:40px;font-weight:700;color:var(--accent);line-height:1}}
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}}
.tile{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px 16px}}
.tile .k{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}}
.tile .v{{font-family:var(--mono);font-size:26px;font-variant-numeric:tabular-nums;margin-top:4px}}
.tile .v.green{{color:var(--done)}} .tile .v.red{{color:var(--blocked)}}
.tile .n{{font-size:12px;color:var(--muted);margin-top:4px}}
h2{{font-family:var(--display);font-weight:500;font-size:22px;margin:34px 0 10px}}
h2 small{{font-family:var(--body);font-size:13px;color:var(--muted);font-weight:400;margin-left:10px}}
.plain{{margin:0;padding:16px 20px;border-left:4px solid var(--accent);background:var(--accent-soft);font-size:17px;line-height:1.5;white-space:pre-line}}
.plain-empty{{color:var(--muted);font-style:italic}}
.map{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px;overflow-x:auto}}
.map svg{{width:100%;min-width:900px;height:auto;display:block}}
.stage rect{{fill:var(--panel);stroke:var(--line)}} .stage .stripe{{stroke:none}}
.stage.done .stripe{{fill:var(--done)}} .stage.progress .stripe{{fill:var(--progress)}} .stage.blocked .stripe{{fill:var(--blocked)}} .stage.todo .stripe{{fill:var(--todo)}} .stage.quiet .stripe{{fill:var(--quiet)}}
.sname{{font-family:var(--body);font-weight:600;font-size:13px;fill:var(--ink)}} .ssub{{font-family:var(--body);font-size:11px;fill:var(--muted)}}
.srows{{font-family:var(--mono);font-size:10.5px;fill:var(--ink)}} .sp0{{font-family:var(--mono);font-size:10.5px;fill:var(--accent)}}
.edge{{fill:none;stroke:var(--muted);stroke-width:1.4}} .axis{{font-family:var(--body);font-size:11.5px;fill:var(--muted)}}
.board{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.col{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px}}
.col h3{{font-family:var(--body);font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;display:flex;justify-content:space-between}}
.col .count{{font-family:var(--mono)}}
.col ul{{list-style:none;margin:0;padding:0;display:grid;gap:8px}}
.row{{display:grid;grid-template-columns:auto 1fr;gap:4px 8px;font-size:13px;padding:8px;border-radius:4px;border:1px solid var(--line);border-left-width:4px}}
.row.done{{border-left-color:var(--done)}} .row.progress{{border-left-color:var(--progress)}} .row.blocked{{border-left-color:var(--blocked)}} .row.todo{{border-left-color:var(--todo)}} .row.parked{{border-left-color:var(--parked);opacity:.75}}
.row.human{{background:var(--accent-soft)}}
.rid{{font-family:var(--mono);font-size:11px;color:var(--muted)}} .rtitle{{grid-column:1/3}}
.chip{{font-family:var(--mono);font-size:10.5px;padding:1px 6px;border-radius:3px;border:1px solid var(--line);color:var(--muted);justify-self:start}}
.chip.done{{color:var(--done)}} .chip.progress{{color:var(--progress)}} .chip.blocked{{color:var(--blocked)}} .chip.who{{color:var(--accent);border-color:var(--accent)}}
.two{{display:grid;grid-template-columns:1.1fr 1fr;gap:18px}}
.score{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px}}
.score svg{{width:100%;height:auto}} .slabel{{font-family:var(--body);font-size:13px;fill:var(--ink)}} .sval{{font-family:var(--mono);font-size:12px;fill:var(--muted)}}
.track{{fill:var(--line)}} .fill{{fill:var(--accent)}}
.score .total{{font-family:var(--mono);color:var(--muted);font-size:12px;margin:6px 0 0}}
.needs{{list-style:none;margin:0;padding:0;display:grid;gap:10px}}
.need{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:4px;padding:10px 12px}}
.need.blocker{{border-left-color:var(--blocked)}} .need.fyi{{border-left-color:var(--quiet)}}
.need .nid{{font-family:var(--mono);font-size:11px;color:var(--muted);display:block}} .need strong{{display:block;margin:2px 0 4px}} .need p{{margin:0;font-size:13px;color:var(--muted)}}
.laps{{list-style:none;margin:0;padding:0;border-left:2px solid var(--line)}}
.lap{{position:relative;padding:4px 0 14px 18px}} .lap::before{{content:"";position:absolute;left:-6px;top:10px;width:10px;height:10px;border-radius:50%;background:var(--quiet)}}
.lap.green::before{{background:var(--done)}} .lap.red::before{{background:var(--blocked)}}
.lap .stamp{{font-family:var(--mono);font-size:12px;color:var(--muted)}} .lap .kind{{font-family:var(--mono);font-size:12px;margin-left:8px;color:var(--accent)}} .lap .gate{{font-family:var(--mono);font-size:12px;margin-left:8px;color:var(--muted)}}
.lap p{{margin:4px 0 0;font-size:14px}}
.legend{{font-size:13px;color:var(--muted);margin-top:8px}} .legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 12px;vertical-align:middle}}
footer{{margin-top:36px;border-top:1px solid var(--line);padding-top:14px;color:var(--muted);font-size:13px}}
footer code{{font-family:var(--mono);font-size:12px}}
@media (max-width:820px){{.tiles,.board,.two{{grid-template-columns:1fr 1fr}} header{{grid-template-columns:1fr}} .countdown{{text-align:left}}}}
@media (max-width:520px){{.tiles,.board,.two{{grid-template-columns:1fr}}}}
</style>
<div class="wrap">
<header>
  <div><h1>WildfireGuardian Loop Board</h1>
  <p class="sub">What the autonomous loop has done, what it will do next, and what needs you. Built {now.strftime("%Y-%m-%d %H:%M UTC")} from <code>auto/dev</code> at <code>{head}</code>.</p></div>
  <div class="countdown"><b>{days_finals}</b>days to the finals ({finals.isoformat()})<br>{days_freeze} days to the freeze ({freeze.isoformat()})</div>
</header>
<div class="tiles">
  <div class="tile"><div class="k">Gates on the last lap</div><div class="v {"green" if gates_word == "green" else ("red" if gates_word == "RED" else "")}">{gates_word}</div><div class="n">make verify + full test suite, clean Linux</div></div>
  <div class="tile"><div class="k">Backlog</div><div class="v">{counts["done"]} / {len(rows)}</div><div class="n">done · {counts["progress"]} in progress · {counts["todo"]} to do · {counts["blocked"]} blocked</div></div>
  <div class="tile"><div class="k">Needs you</div><div class="v">{len(open_needs)}</div><div class="n">open decisions in NEEDS_HUMAN.md</div></div>
  <div class="tile"><div class="k">Commits, last 24 h</div><div class="v">{commits_24h}</div><div class="n">{len(reps)} lap report{"s" if len(reps) != 1 else ""} so far</div></div>
</div>

<h2>In plain terms<small>the latest lap, for the author</small></h2>
{plain_block}

<h2>Project map<small>where the work is happening</small></h2>
<div class="map">{svg_map}</div>

<h2>Backlog board<small>every row, by when it must ship</small></h2>
<div class="board">{"".join(cols)}</div>
<p class="legend">Left stripe: <i style="background:var(--done)"></i>done <i style="background:var(--progress)"></i>in progress <i style="background:var(--todo)"></i>to do <i style="background:var(--blocked)"></i>blocked <i style="background:var(--parked)"></i>parked. Tinted rows are yours to do.</p>

<div class="two">
  <section><h2>Rubric scorecard<small>{esc(score_src)}</small></h2>
    <div class="score">{svg_score}<p class="total">total {total:g} / 100 · Track B (SW 연구); the critic lap re-scores daily into SCORECARD.md</p></div></section>
  <section><h2>Needs you<small>{len(open_needs)} open</small></h2><ul class="needs">{nd or "<li class='need fyi'><strong>Nothing open.</strong></li>"}</ul></section>
</div>

<h2>Laps<small>newest first</small></h2>
<ul class="laps">{tl or "<li class='lap'><p>No lap has reported yet.</p></li>"}</ul>

<footer>How to read this page: the four tiles say whether the last lap was green and how much is left; the project map shows which stage of the system each open row touches; the board is the full plan; the scorecard is the loop's own estimate of the judges' five rows, not a judge's score. Sources: <code>docs/auto/BACKLOG.md</code>, <code>NEEDS_HUMAN.md</code>, <code>STATE.json</code>, <code>reports/</code>, <code>SCORECARD.md</code>. Regenerate with <code>python scripts/auto/dashboard.py</code>.</footer>
</div>
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(AUTO / "dashboard.html"))
    a = ap.parse_args()
    out = Path(a.out)
    out.write_text(build(), encoding="utf-8")
    print(f"[dashboard] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
