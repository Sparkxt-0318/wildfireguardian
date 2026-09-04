#!/usr/bin/env python
"""The author's decisions, taken from an email reply and recorded verifiably.

The loop escalates in docs/auto/NEEDS_HUMAN.md; the author decides by REPLYING to a
report email with one line per item:

    NH-018: B
    NH-016: yes, change the cadence as recommended
    NH-013: skip

A routine reads the reply through the Gmail connector and calls this script once per
line. The closure it writes carries channel, received date, the Gmail message id and
the author's words verbatim, so the repository can point at the message instead of
quoting something it cannot see (NH-017). A decision the loop does not understand is
still recorded, as `noted`, never guessed at.

    python scripts/auto/decisions.py list                         # open items + reply lines
    python scripts/auto/decisions.py apply --id NH-018 --text "B" \\
        --channel "email reply" --received 2026-09-05 --ref <gmail-message-id>
    python scripts/auto/decisions.py apply --from-json .auto/replies.json   # [{id,text,received,ref,channel}]
    python scripts/auto/decisions.py seen <gmail-message-id>              # exit 1 if already applied

Python 3.11, standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NEEDS = REPO / "docs" / "auto" / "NEEDS_HUMAN.md"
STATE = REPO / "docs" / "auto" / "STATE.json"
SEEN = REPO / "docs" / "auto" / "decisions_seen.json"
HEADER = re.compile(r"^## (NH-\d+)\s*·\s*(\w+)\s*·\s*(\w+)\s*·\s*(.*)$", re.M)


def entries(text: str) -> list[dict]:
    out = []
    heads = list(HEADER.finditer(text))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[m.end():end]
        opts = re.search(r"\*\*Options:\*\*\s*(.*?)(?:\n\n|\Z)", body, flags=re.S)
        out.append(dict(id=m.group(1), sev=m.group(2), status=m.group(3).lower(), title=m.group(4).strip(),
                        start=m.start(), end=end, options=(opts.group(1).strip().replace("\n", " ") if opts else "")))
    return out


def cmd_list(args) -> int:
    text = NEEDS.read_text(encoding="utf-8")
    open_ = [e for e in entries(text) if e["status"] == "open"]
    if args.json:
        print(json.dumps([{k: e[k] for k in ("id", "sev", "title", "options")} for e in open_], ensure_ascii=False, indent=1))
        return 0
    for e in open_:
        print(f"{e['id']} [{e['sev']}] {e['title']}")
        if e["options"]:
            print(f"    options: {e['options']}")
        print(f"    reply with:  {e['id']}: <your decision>")
    return 0


def apply_one(text: str, nid: str, decision: str, channel: str, received: str, ref: str) -> tuple[str, str]:
    es = {e["id"]: e for e in entries(text)}
    if nid not in es:
        return text, f"{nid}: no such entry; recorded nowhere"
    e = es[nid]
    verb = "CLOSED" if e["status"] == "open" else "NOTED (entry already closed)"
    block = (f"\n**{verb} {received} by the author** · channel: {channel} · received: {received} · "
             f"ref: {ref or 'none'} · verbatim: \"{decision.strip()}\"\n")
    new_body = text[e["start"]:e["end"]].rstrip("\n") + "\n" + block
    if e["status"] == "open":
        new_body = new_body.replace(f"## {nid} · {e['sev']} · open ·", f"## {nid} · {e['sev']} · closed ·", 1)
    text = text[:e["start"]] + new_body + ("\n" if e["end"] < len(text) else "") + text[e["end"]:]
    return text, f"{nid}: {verb.lower()} with \"{decision.strip()[:60]}\""


def cmd_apply(args) -> int:
    text = NEEDS.read_text(encoding="utf-8")
    items = []
    if args.from_json:
        items = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        if not (args.id and args.text):
            print("apply needs --id and --text, or --from-json"); return 2
        items = [dict(id=args.id, text=args.text, channel=args.channel, received=args.received, ref=args.ref)]
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {"applied": []}
    for it in items:
        nid = it["id"].strip().upper()
        if not re.fullmatch(r"NH-\d+", nid):
            print(f"skip: {it['id']!r} is not an NH id"); continue
        ref = it.get("ref") or ""
        key = f"{ref}:{nid}" if ref else None
        if key and key in seen["applied"]:
            print(f"{nid}: already applied from {ref}"); continue
        text, msg = apply_one(text, nid, it["text"], it.get("channel") or "email reply",
                              it.get("received") or dt.date.today().isoformat(), ref)
        print(msg)
        if key:
            seen["applied"].append(key)
    NEEDS.write_text(text, encoding="utf-8")
    SEEN.write_text(json.dumps(seen, indent=1) + "\n", encoding="utf-8")
    n_open = sum(1 for e in entries(text) if e["status"] == "open")
    try:
        st = json.loads(STATE.read_text()); st["open_needs_human"] = n_open
        STATE.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"STATE.json not updated: {exc}")
    print(f"open entries now: {n_open}")
    return 0


def cmd_seen(args) -> int:
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {"applied": []}
    hit = any(k.startswith(args.ref + ":") for k in seen["applied"])
    print("seen" if hit else "new")
    return 1 if hit else 0


def parse_reply(body: str) -> list[dict]:
    """Lines like `NH-018: B` or `NH-016 - yes` anywhere in a reply body (quoted text is
    ignored: lines starting with `>`)."""
    out = []
    for line in body.splitlines():
        if line.lstrip().startswith(">"):
            continue
        m = re.match(r"^\s*(NH-\d+)\s*[:\-–]\s*(.+?)\s*$", line, flags=re.I)
        if m:
            out.append(dict(id=m.group(1).upper(), text=m.group(2)))
    return out


def cmd_parse(args) -> int:
    body = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    print(json.dumps(parse_reply(body), ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("--json", action="store_true")
    a = sub.add_parser("apply")
    a.add_argument("--id"); a.add_argument("--text"); a.add_argument("--channel", default="email reply")
    a.add_argument("--received", default=dt.date.today().isoformat()); a.add_argument("--ref", default="")
    a.add_argument("--from-json")
    s = sub.add_parser("seen"); s.add_argument("ref")
    p = sub.add_parser("parse"); p.add_argument("--file")
    args = ap.parse_args()
    return {"list": cmd_list, "apply": cmd_apply, "seen": cmd_seen, "parse": cmd_parse}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
