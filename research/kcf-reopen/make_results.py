"""RESULTS.md = RESULTS.src.md with every <<T:title>> marker replaced by the table of out/tables.md whose heading starts
with that title (and its notes, up to the next heading). Usage: python3 -I make_results.py"""
import re
from pathlib import Path

H = Path(__file__).resolve().parent
src = (H / "RESULTS.src.md").read_text(encoding="utf-8")
tab = (H / "out/tables.md").read_text(encoding="utf-8")
blocks = {}
for b in re.split(r"(?m)^### ", tab)[1:]:
    title, body = b.split("\n", 1)
    blocks[title] = "**" + title + "**\n" + body.rstrip() + "\n"


def sub(m):
    key = m.group(1)
    hits = [t for t in blocks if t.startswith(key)]
    if len(hits) != 1:
        raise SystemExit("marker %r matches %d tables" % (key, len(hits)))
    return blocks[hits[0]]


out = re.sub(r"<<T:([^>]+)>>", sub, src)
(H / "RESULTS.md").write_text(out, encoding="utf-8")
print("RESULTS.md written; unresolved markers:", re.findall(r"<<[A-Z0-9_]+>>", out))
