"""Extract a survey subagent's final report (its hand-back text) from its JSONL transcript. Usage: extract_report.py IN OUT"""
import json, sys
best = ""
for line in open(sys.argv[1], errors="replace"):
    try:
        o = json.loads(line)
    except Exception:
        continue
    def walk(x):
        global best
        if isinstance(x, dict):
            if x.get("type") == "tool_use" and "andback" in str(x.get("name", "")):
                for v in x.get("input", {}).values():
                    if isinstance(v, str) and len(v) > len(best):
                        best = v
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(o)
open(sys.argv[2], "w").write(best)
print(sys.argv[2], len(best))
