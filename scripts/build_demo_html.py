#!/usr/bin/env python
"""Inline data/processed/demo_data.json into demo/wildfire_demo.html.

Keeps the demo a single self-contained file that opens on file:// while staying
fully reproducible: the pipeline is

    scripts/export_demo_data.py  ->  data/processed/demo_data.json
    scripts/build_demo_html.py   ->  demo/wildfire_demo.html  (data inlined)

The committed data bundle is copied verbatim between the two sentinels inside the
``<script type="application/json" id="demo-data">`` block. No number is edited
here; this only transports the committed JSON into the offline page.

Run:  python scripts/build_demo_html.py
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "processed" / "demo_data.json"
HTML = REPO / "demo" / "wildfire_demo.html"

START = "/*__DEMO_DATA_START__*/"
END = "/*__DEMO_DATA_END__*/"
# Anchor on the data <script> tag so only its inner content is ever replaced —
# never any other script (the app JS must not reference the sentinel strings).
BLOCK = re.compile(r'(<script type="application/json" id="demo-data">)'
                   r'.*?(</script>)', re.DOTALL)


def main() -> int:
    payload = DATA.read_text(encoding="utf-8").strip()
    html = HTML.read_text(encoding="utf-8")
    if not BLOCK.search(html):
        raise SystemExit('data block <script id="demo-data"> not found in ' + str(HTML))
    inner = "\n" + START + "\n" + payload + "\n" + END + "\n"
    html = BLOCK.sub(lambda m: m.group(1) + inner + m.group(2), html, count=1)
    HTML.write_text(html, encoding="utf-8")
    print(f"inlined {len(payload)} bytes of demo_data.json into {HTML.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
