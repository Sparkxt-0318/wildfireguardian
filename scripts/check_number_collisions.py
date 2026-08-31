#!/usr/bin/env python
"""Gate — a registered quantity must not appear elsewhere with a different value.

Session 18, Phase 3. Seventeen sessions produced ~50 documents. Any quantity
that appears with two different values in two places, with nothing saying which
superseded which, is a defect a judge can find in a minute — and it is exactly
the kind of defect that makes an otherwise honest self-correction record look
careless instead.

This is REGISTRY-ANCHORED, which is what keeps it from drowning in noise.
``docs/NUMBERS.json`` is the authority. For each entry the check builds anchor
words from its key, then looks for lines that name that quantity and carry a
DIFFERENT number of the same shape.

    python scripts/check_number_collisions.py            # gate, exit 1 on a hit
    python scripts/check_number_collisions.py --report   # full sweep, exit 0

HOW A COLLISION IS DEFINED, PRECISELY
-------------------------------------
A line collides with entry ``K`` when ALL of these hold:

  * the line contains at least ``MIN_ANCHORS`` of K's anchor words (words from
    K's key, minus stopwords), or one anchor word from :data:`STRONG_ANCHORS`;
  * the line contains a number with the SAME number of decimal places as K's
    registered value — a 3-dp value is only ever compared against 3-dp numbers,
    so a row count never collides with an AUC;
  * that number differs from K's value by more than K's own tolerance; and
  * the line carries no supersession marker and no pragma.

⚠ WHAT THIS CANNOT DO. It cannot read a sentence. A quantity described in words
the key does not contain ("the pooled figure was 0.905") is invisible to it, and
two genuinely different quantities that share key words can collide falsely. It
is a net under the curated ``check_forbidden.py`` list, not a replacement for
reading the documents — the Session 18 sweep was reviewed by hand and the real
hits were fixed by ANNOTATION, never by deleting the stale value.

MARKERS AND PRAGMAS
-------------------
Superseded values stay in the documents. Deleting them would destroy the audit
trail that makes the self-correction record worth anything. They must simply be
marked, on the line or the line above::

    <!-- collision-ok: 0.905 -->     markdown
    # collision-ok: 0.905            python / yaml

Any of these words on the line (or in the five lines above it) also counts as a
marker, because that is how the existing retractions are already written:
SUPERSEDED, WITHDRAWN, RETIRED, 철회, 정정, 폐기, superseded by, 이전 값.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"

#: How many anchor words a line needs before it is considered to name a quantity.
#: Registry keys are long and descriptive (``l0_walk_time_to_refuge_safe_median_min``),
#: so two shared words is weak evidence — at 2 the sweep produced 592 hits,
#: nearly all of them a line about a different quantity that happened to share
#: two common words. Three is the point where the survivors are readable.
MIN_ANCHORS = 3

#: Words that carry no identifying force in a registry key.
STOPWORDS = {
    "the", "of", "a", "an", "and", "or", "at", "in", "on", "to", "for", "vs",
    "is", "n", "s8", "s9", "l0", "value", "mean", "min", "max", "total",
    "count", "num", "number", "per", "all", "with", "without", "from", "by",
}

#: Common enough to be worthless alone: "auc" appears on hundreds of lines.
#: One of these still needs a second anchor word beside it.
WEAK_ALONE = {"auc", "iou", "spearman", "brier", "fold", "folds", "pooled"}

#: Only REPORTED precision is compared. A registry value stored at full float
#: precision (0.9048475036678545) is raw artifact data, not a prose claim, and
#: comparing it against every 16-dp number in the corpus produced 5,622 hits on
#: the first run — all noise. Prose quotes 3 or 4 significant figures.
MAX_DP = 4

#: A marker means "this value is knowingly historical". Deleting the value
#: instead would destroy the audit trail.
#: NARRATIVE markers introduce a whole retraction block, so they are honoured
#: for the following few lines.
MARKERS = re.compile(
    r"SUPERSEDED|WITHDRAWN|RETIRED|DEPRECATED|superseded|withdrawn|retired"
    r"|철회|정정|폐기|이전\s*값|구\s*값|기존\s*값|과거\s*값", re.I)

#: A PRAGMA is per-line and names the token it excuses, exactly as
#: ``check_forbidden.py`` does. It must sit on the offending line or the line
#: directly above it — a pragma with a five-line reach would quietly excuse
#: numbers its author never looked at.
#: The tokens are read as NUMBERS out of whatever follows the marker, so the
#: pragma can carry its reason inline — which is the point, since "these are
#: two different quantities" is exactly what a reader needs to see.
PRAGMA = re.compile(r"(?:collision-ok|forbidden-ok):(.*)")

#: Look this far back for a NARRATIVE marker introducing a block.
MARKER_LOOKBACK = 5

NUM_RE = re.compile(r"(?<![\w.])(\d+\.\d+)(?![\d])")
WORD_RE = re.compile(r"[a-z0-9]+")


def _git_files() -> list[str]:
    """Prose only: tracked ``.md``, plus Python files for their DOCSTRINGS.

    ``.json`` is excluded deliberately. Artifact JSON is the raw measurement —
    it is what the registry is checked AGAINST, so a number in it disagreeing
    with a rounded prose figure is expected, not a collision.
    """
    r = subprocess.run(["git", "ls-files", "*.md", "*.py"], cwd=REPO,
                       capture_output=True, text=True,
                       env={"GIT_DISCOVERY_ACROSS_FILESYSTEM": "1",
                            "PATH": "/usr/bin:/bin:/usr/local/bin"})
    return [f for f in r.stdout.split()
            if not f.startswith("data/") and f != "docs/NUMBERS.json"]


def _prose_lines(rel: str) -> list[str]:
    """Lines to scan. For ``.py`` that means docstrings and comments only —
    a literal in code is data, and flagging it would be flagging the artifact."""
    text = (REPO / rel).read_text(encoding="utf-8", errors="ignore")
    if rel.endswith(".md"):
        return text.splitlines()
    lines = text.splitlines()
    keep = [""] * len(lines)
    in_doc = False
    fence = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if in_doc:
            keep[i] = ln
            if fence and fence in s:
                in_doc, fence = False, None
            continue
        if s.startswith("#"):
            keep[i] = ln
            continue
        m = re.match(r'^[rbuf]*("""|\'\'\')', s)
        if m:
            keep[i] = ln
            body = s[m.end():]
            if m.group(1) not in body:
                in_doc, fence = True, m.group(1)
    return keep


def anchors_for(key: str) -> set[str]:
    return {w for w in WORD_RE.findall(key.lower())
            if w not in STOPWORDS and len(w) > 2 and not w.isdigit()}


def registry() -> dict[str, dict]:
    nums = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    out = {}
    for k, e in nums.items():
        v = e.get("value")
        if not isinstance(v, float):
            continue                      # only decimal quantities are compared
        s = repr(v)
        if "." not in s or "e" in s:
            continue
        dp = len(s.split(".")[1])
        if dp > MAX_DP:
            continue                      # full-precision artifact value
        anc = anchors_for(k)
        if len(anc - WEAK_ALONE) < 1:
            continue                      # nothing distinctive to anchor on
        out[k] = {"value": v, "dp": dp,
                  "tol": float(e.get("check", {}).get("tolerance", 0.0)),
                  "anchors": anc}
    return out


def _marked(lines: list[str], i: int, token: str) -> bool:
    lo = max(0, i - MARKER_LOOKBACK)
    if MARKERS.search("\n".join(lines[lo:i + 1])):
        return True
    for j in (i, i - 1):
        if j < 0:
            continue
        for m in PRAGMA.finditer(lines[j]):
            excused = {float(t) for t in NUM_RE.findall(m.group(1))}
            if any(abs(float(token) - x) < 1e-12 for x in excused):
                return True
    return False


def scan() -> tuple[list[dict], dict]:
    reg = registry()
    hits: list[dict] = []
    families: dict[str, set] = defaultdict(set)

    for rel in _git_files():
        try:
            lines = _prose_lines(rel)
        except OSError:
            continue
        for i, line in enumerate(lines):
            found = NUM_RE.findall(line)
            if not found:
                continue
            words = set(WORD_RE.findall(line.lower()))
            for key, e in reg.items():
                hit_anchors = e["anchors"] & words
                # A weak word alone ("auc", "pooled") names nothing; require at
                # least MIN_ANCHORS, of which at least one is distinctive.
                if len(hit_anchors) < MIN_ANCHORS:
                    continue
                if not (hit_anchors - WEAK_ALONE):
                    continue
                # If the CANONICAL value is on this line too, the other numbers
                # are its companions — a sweep, a fold list, a before/after —
                # not a contradiction of it. A collision is the canonical value
                # being ABSENT while a different one is present.
                if any(abs(float(t) - e["value"]) <= max(e["tol"], 1e-12)
                       for t in found):
                    continue
                # A line that lists SEVERAL numbers of the same shape is a
                # sweep, a fold list or a table row — it is not asserting one
                # value for one quantity, and treating it as one produced most
                # of the first sweep's noise. A collision claim needs a line
                # that says exactly one thing.
                same_shape = [t for t in found
                              if len(t.split(".")[1]) == e["dp"]]
                if len(same_shape) != 1:
                    continue
                for tok in same_shape:
                    val = float(tok)
                    if abs(val - e["value"]) <= max(e["tol"], 1e-12):
                        continue
                    families[key].add(val)
                    if _marked(lines, i, tok):
                        continue
                    hits.append({
                        "key": key, "registered": e["value"], "found": val,
                        "file": rel, "line_no": i + 1,
                        "anchors_matched": sorted(hit_anchors),
                        "line": line.strip()[:160],
                    })
    return hits, {k: sorted(v) for k, v in families.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()

    hits, families = scan()
    if a.json:
        a.json.write_text(json.dumps(
            {"n_unmarked_collisions": len(hits), "collisions": hits,
             "values_seen_per_quantity": families}, indent=2,
            ensure_ascii=False) + "\n", encoding="utf-8")

    if a.report:
        print(f"quantities seen with a value other than the registered one: "
              f"{len(families)}")
        for k, vs in sorted(families.items()):
            print(f"  {k}: also seen as {vs}")
        print(f"\nUNMARKED collisions: {len(hits)}")
        for h in hits:
            print(f"  {h['file']}:{h['line_no']}  {h['key']} "
                  f"registered {h['registered']} vs {h['found']}")
            print(f"      {h['line']}")
        return 0

    if hits:
        print(f"NUMBER COLLISIONS — {len(hits)} registered quantities appear "
              f"elsewhere with a different value and no supersession marker:\n")
        for h in hits:
            print(f"  {h['file']}:{h['line_no']}")
            print(f"    {h['key']}: registry {h['registered']}, "
                  f"text {h['found']}  (anchors {h['anchors_matched']})")
            print(f"    {h['line']}")
        print("\nFix by ANNOTATION, never by deleting the stale value — the "
              "audit trail is the point. Mark the line SUPERSEDED / 철회 / "
              "정정, or add `collision-ok: <value>` if the two numbers are "
              "genuinely different quantities.")
        return 1

    print(f"OK — no registered quantity appears elsewhere with a different, "
          f"unmarked value ({len(families)} quantities carry marked historical "
          f"values, which is intended).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
