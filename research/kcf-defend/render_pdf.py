"""pages/*.md -> pages/pages_ko_en.pdf, one A4 landscape page per issue hour and language (Korean first)."""
import re
from pathlib import Path
import markdown
import subprocess, tempfile
D = Path(__file__).resolve().parent / "pages"
files = []
for f in sorted(D.glob("*_KST.ko.md")):
    files += [f, f.with_name(f.name.replace(".ko.", ".en."))]
css = """@page{size:A4 landscape;margin:7mm}body{font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;font-size:7pt;line-height:1.22;color:#111}
h1{font-size:10pt;margin:0 0 4px}p{margin:3px 0}table{border-collapse:collapse;width:100%;margin:4px 0}
td,th{border:1px solid #999;padding:2px 3px;vertical-align:top}th{background:#eee}ul{margin:2px 0 2px 14px;padding:0}li{margin:0}
.pg{page-break-after:always}sub{font-size:6.5pt}"""
body = "".join(f'<div class="pg">{markdown.markdown(f.read_text(), extensions=["tables"])}</div>' for f in files)
html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
tmp = Path(tempfile.mkdtemp()) / "pages.html"
tmp.write_text(html)
js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();"
      f"await p.goto('file://{tmp}');await p.pdf({{path:'{D / 'pages_ko_en.pdf'}',format:'A4',landscape:true,printBackground:true,scale:0.8}});"
      "const n=await p.evaluate(()=>[...document.querySelectorAll('.pg')].map(e=>e.scrollHeight).join(','));console.log(n);await b.close();})();")
subprocess.run(["node", "-e", js], check=True)
print(len(files), "pages in")
