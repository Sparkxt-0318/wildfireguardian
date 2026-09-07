"""Which card on the finals screen draws which registry key (WFG-110).

Readiness line R1 asks that every on-screen number map to a `docs/NUMBERS.json`
key with the mapping table committed. The table that already existed runs the
other way round: `docs/auto/DEMO_SCRIPT_5MIN.md` §3 maps *what the student says*
to a key. R1 asks screen -> key, which is the direction that answers a judge
pointing at a card and asking 「이 숫자는 어디서 나온 겁니까」.

This module derives that direction mechanically from `scripts/finals.template.html`,
which is the file `docs/auto/DEMO_SCRIPT_5MIN.md` §3 already names as the arbiter
of what is 화면 (the built `web/finals.html` embeds the whole registry slice as
one JSON blob, so presence there proves nothing).

How a key is attributed to a card
---------------------------------
Cards are created by exactly two calls: `evCard(grid, kicker, ...)` in the
근거 (EVIDENCE) view and `rel(title, ...)` in the 신뢰성 (RELIABILITY) view. A
registry key appears in the template in one of two positions, and both are
handled:

  * inside a card call's own parentheses (`...regProv('lofo_mean_of_folds_auc')`),
    in which case it belongs to that card; or
  * in the `const e = regEntry('...')` preamble of the braced block that builds
    one card, in which case it belongs to the next card call in the file.

⚠ What this derivation is NOT. It reads the template's *source*, not a rendered
page, so it cannot see a card that is built by some third mechanism, and it
cannot tell you that an attribution is correct - only that it is the one the
template's structure implies. The committed table in
`docs/finals_screen_numbers.md` was written by reading all card blocks by hand
and this derivation was run afterwards as a cross-check; they agreed on all 28
keys. The test that guards the pair is `tests/test_finals_screen_numbers.py`.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import bisect
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "scripts" / "finals.template.html"
REGISTRY = REPO / "docs" / "NUMBERS.json"

# `evCard(` and `rel(` where they are called, never where `rel` is declared.
_CALL_RE = re.compile(r"(?<![A-Za-z0-9_.])(evCard|rel)\s*\(")
_STRING_RE = r"('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"

VIEW_OF_CALL = {"evCard": "근거", "rel": "신뢰성"}


def _line_index(text: str) -> list[int]:
    offsets = [0]
    for line in text.split("\n"):
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


def _close_paren(text: str, open_at: int) -> int:
    """Index of the `)` matching the `(` at `open_at`, skipping string bodies."""
    depth = 0
    quote = None
    i = open_at
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unbalanced parenthesis opened at offset {open_at}")


def cards(template_text: str | None = None) -> list[dict]:
    """Every card call in the template, in file order."""
    text = TEMPLATE.read_text(encoding="utf-8") if template_text is None else template_text
    offsets = _line_index(text)
    out: list[dict] = []
    for m in _CALL_RE.finditer(text):
        line_no = bisect.bisect_right(offsets, m.start())
        if text.split("\n")[line_no - 1].lstrip().startswith("function "):
            continue  # the declaration of rel(), not a call
        end = _close_paren(text, m.end() - 1)
        args = text[m.end():end]
        # evCard's title is its SECOND argument, rel's is its first.
        pattern = r",\s*" + _STRING_RE if m.group(1) == "evCard" else r"\s*" + _STRING_RE
        title_m = re.search(pattern, args)
        out.append(
            {
                "kind": m.group(1),
                "view": VIEW_OF_CALL[m.group(1)],
                "title": title_m.group(1)[1:-1] if title_m else "",
                "line": line_no,
                "start": m.start(),
                "end": end,
            }
        )
    return out


def derive(template_text: str | None = None, keys: list[str] | None = None) -> dict[str, dict]:
    """Map every registry key the template references to the card that draws it.

    Returns `{key: {"view": ..., "card": ..., "lines": [...]}}`. A key attributed
    to no card at all is returned with `card: None` rather than dropped, because
    an unattributable key is exactly the failure this is meant to surface.
    """
    text = TEMPLATE.read_text(encoding="utf-8") if template_text is None else template_text
    if keys is None:
        keys = list(json.loads(REGISTRY.read_text(encoding="utf-8"))["numbers"])
    offsets = _line_index(text)
    all_cards = cards(text)
    found: dict[str, dict] = {}
    for key in keys:
        for m in re.finditer(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])", text):
            inside = [c for c in all_cards if c["start"] <= m.start() <= c["end"]]
            if inside:
                card = min(inside, key=lambda c: c["end"] - c["start"])
            else:
                after = [c for c in all_cards if c["start"] > m.start()]
                card = after[0] if after else None
            entry = found.setdefault(
                key,
                {"view": card["view"] if card else None,
                 "card": card["title"] if card else None,
                 "lines": []},
            )
            entry["lines"].append(bisect.bisect_right(offsets, m.start()))
            if card is not None and entry["card"] not in (None, card["title"]):
                entry["card"] = "AMBIGUOUS: " + entry["card"] + " / " + card["title"]
    return found


def main() -> None:
    print(json.dumps(derive(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
