"""docs/auto/STATE.json and LOOP_CONFIG.json must parse: a rebase once committed conflict markers into STATE.json (2026-09-04)."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_state_and_config_parse():
    for name in ("STATE.json", "LOOP_CONFIG.json", "decisions_seen.json"):
        p = REPO / "docs" / "auto" / name
        if p.exists():
            text = p.read_text(encoding="utf-8")
            assert "<<<<<<<" not in text and ">>>>>>>" not in text, name
            json.loads(text)
