"""The author's email replies become verifiable closures, and only once.

docs/auto/NEEDS_HUMAN.md is the loop's escalation ledger; NH-017 found three closures
quoted from replies the repository could not see. scripts/auto/decisions.py turns a
reply line (`NH-018: B`) into a closure that carries channel, date, the Gmail message id
and the author's words verbatim, and refuses to apply the same message twice.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("_wfg_decisions", REPO / "scripts" / "auto" / "decisions.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


LEDGER = """# Needs a human

## NH-101 · DECISION · open · Pick the cadence

**What:** dev every 3 h or every 6 h.

**Options:** A) every 3 h  B) every 6 h

## NH-102 · FYI · open · Nothing to decide

**What:** informational.
"""


def _sandbox(tmp_path, monkeypatch):
    d = _load()
    needs = tmp_path / "NEEDS_HUMAN.md"; needs.write_text(LEDGER, encoding="utf-8")
    state = tmp_path / "STATE.json"; state.write_text(json.dumps({"open_needs_human": 2}))
    seen = tmp_path / "seen.json"
    monkeypatch.setattr(d, "NEEDS", needs); monkeypatch.setattr(d, "STATE", state); monkeypatch.setattr(d, "SEEN", seen)
    return d, needs, state, seen


def test_parse_reads_reply_lines_and_ignores_quoted_text():
    d = _load()
    got = d.parse_reply("ok\n\nNH-101: A\n> NH-102: no (quoted)\nnh-102 - noted\n")
    assert got == [{"id": "NH-101", "text": "A"}, {"id": "NH-102", "text": "noted"}]


def test_apply_closes_the_entry_with_channel_date_ref_and_verbatim(tmp_path, monkeypatch):
    d, needs, state, seen = _sandbox(tmp_path, monkeypatch)
    text, msg = d.apply_one(needs.read_text(), "NH-101", "A", "email reply", "2026-09-05", "msg-1")
    assert "## NH-101 · DECISION · closed ·" in text
    assert 'channel: email reply · received: 2026-09-05 · ref: msg-1 · verbatim: "A"' in text
    assert "## NH-102 · FYI · open ·" in text  # untouched
    assert msg.startswith("NH-101: closed")


def test_the_same_message_is_never_applied_twice_and_state_counts_open(tmp_path, monkeypatch):
    d, needs, state, seen = _sandbox(tmp_path, monkeypatch)
    j = tmp_path / "r.json"
    j.write_text(json.dumps([{"id": "NH-101", "text": "B", "received": "2026-09-05", "ref": "msg-9", "channel": "email reply"}]))
    class A: from_json = str(j); id = None; text = None
    assert d.cmd_apply(A) == 0
    assert json.loads(state.read_text())["open_needs_human"] == 1
    before = needs.read_text()
    assert d.cmd_apply(A) == 0  # second run: skipped
    assert needs.read_text() == before
    assert json.loads(seen.read_text())["applied"] == ["msg-9:NH-101"]


def test_a_reply_to_an_already_closed_entry_is_noted_not_lost(tmp_path, monkeypatch):
    d, needs, *_ = _sandbox(tmp_path, monkeypatch)
    text, _ = d.apply_one(needs.read_text(), "NH-101", "A", "email reply", "2026-09-05", "m1")
    text, msg = d.apply_one(text, "NH-101", "actually B", "email reply", "2026-09-06", "m2")
    assert "NOTED (entry already closed) 2026-09-06" in text and 'verbatim: "actually B"' in text


def test_an_unknown_id_is_reported_and_nothing_is_written(tmp_path, monkeypatch):
    d, needs, *_ = _sandbox(tmp_path, monkeypatch)
    text, msg = d.apply_one(needs.read_text(), "NH-999", "x", "email reply", "2026-09-05", "m")
    assert text == needs.read_text() and "no such entry" in msg
