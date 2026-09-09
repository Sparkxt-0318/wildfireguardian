"""Grade the WFG-210 gates in tests/test_creativity_card.py by mutation.

Run it: ``python scripts/mutate_creativity_gates.py`` from the repository root.
Every mutation is applied to a file, graded, and restored in a ``finally``; the
script prints RED/GREEN **and which test failed**, because a red that comes from
a different assertion than the one under test is a false positive of the grading
itself (MEMO 2026-09-09T0630Z).

It ships because ``docs/creativity_card.md`` §8 claims nine mutations and their
verdicts, and a claim about this repository's own state needs something a
stranger can re-run (CHARTER §3.3). The lap that wrote the gates also wrote this
set, which is ``mandela`` pattern #5 — verifier = designer — and §6 of that same
document is why the independent review supplies a second, differently-designed
set rather than re-running this one.

⚠ **Bytecode writing is off, and that is not tidiness.** CPython invalidates a
cached ``.pyc`` on ``(mtime, size)``. Two of these mutations change a single
character inside a constant, so mutant and original are the same size, and a
restore inside the same second is invisible: the mutant then runs on every later
import while the file on disk reads correctly. It happened, for twenty minutes,
and two tests went red on a correct tree with a message naming the wrong cause.
``-B`` plus ``PYTHONDONTWRITEBYTECODE=1`` plus clearing ``tests/__pycache__``
between mutations is what makes these verdicts evidence.
"""

import os, pathlib, re, shutil, subprocess

pat = re.compile(r'^FAILED tests/\S+::(test_\w+)', re.M)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

SHEET = "outputs/dispatch/20260801T163042Z/01-거무역리공원-북쪽/dispatch_a4.html"
CARD_ROW_NEW = ("`outputs/dispatch/README.md` and the committed sheets beside it, e.g. "
                "`" + SHEET + "` (an instance of the object); "
                "`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3 "
                "(why the choice is not to compete on accuracy)")

MUTS = [
 ("M1 README item 1 reverted to the landscape note alone", "README.md",
  "  → 실물과 그 한계: [`outputs/dispatch/README.md`](outputs/dispatch/README.md)\n  → 정확도로 겨루지 않기로 한 판단의 근거:\n", "  → "),
 ("M2 screen CREATIVE[0].doc reverted", "scripts/finals.template.html",
  "doc: '" + SHEET + " · outputs/dispatch/README.md · docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md §3',",
  "doc: 'docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md §3',"),
 ("M3 card row 1 reverted", "docs/creativity_card.md",
  "| " + CARD_ROW_NEW + " |", "| `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3 |"),
 ("M4 bank evidence line reverted", "docs/auto/JUDGE_QA.md",
  "근거: `outputs/dispatch/README.md` 과 그 옆의 커밋된 지시서\n(예: `" + SHEET + "` — 첫째 항목이\n말하는 산출물의 실물), `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3\n(정확도로 겨루지 않기로 한 판단의 근거이고, 산출물의 실물이 아닙니다),\n",
  "근거: `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3,\n"),
 ("M5 card row 1 names the directory as prose, no resolvable instance file", "docs/creativity_card.md",
  "`outputs/dispatch/README.md` and the committed sheets beside it, e.g. `" + SHEET + "` (an instance of the object); ",
  "the sheets under `outputs/dispatch/`; "),
 ("M6 item-1 anchor swapped for a second document about the other systems", "docs/creativity_card.md",
  CARD_ROW_NEW, "`docs/related_work.md` and `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3"),
 ("M7 premise check pointed at a directory holding no committed sheets", "tests/test_creativity_card.py",
  'OBJECT_INSTANCE_ROOT = "outputs/dispatch/"', 'OBJECT_INSTANCE_ROOT = "outputs/live/"'),
 ("M8 classifier threshold raised above the landscape note's own count", "tests/test_creativity_card.py",
  "_ABOUT_OTHERS_MIN = 5", "_ABOUT_OTHERS_MIN = 500"),
 ("M9 classifier threshold lowered until every file classifies", "tests/test_creativity_card.py",
  "_ABOUT_OTHERS_MIN = 5", "_ABOUT_OTHERS_MIN = 0"),
]

def clear():
    for d in pathlib.Path("tests").rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)

for name, path, old, new in MUTS:
    p = pathlib.Path(path); orig = p.read_text(encoding="utf-8")
    assert old in orig, "anchor text not found for " + name
    p.write_text(orig.replace(old, new, 1), encoding="utf-8")
    clear()
    try:
        r = subprocess.run([".auto/venv/bin/python", "-B", "-m", "pytest",
                            "tests/test_creativity_card.py", "-q", "--no-header",
                            "-p", "no:cacheprovider"],
                           capture_output=True, text=True, env=env)
        which = sorted(set(pat.findall(r.stdout))) or ["n/a"]
        print(("RED" if r.returncode else "GREEN").ljust(5), "|", name)
        print("       ", ", ".join(which))
    finally:
        p.write_text(orig, encoding="utf-8"); clear()

r = subprocess.run([".auto/venv/bin/python", "-B", "-m", "pytest",
                    "tests/test_creativity_card.py", "-q", "--no-header",
                    "-p", "no:cacheprovider"], capture_output=True, text=True, env=env)
print("\nrestored tree:", r.stdout.strip().splitlines()[-1])
