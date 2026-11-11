#!/usr/bin/env python3
"""Offline judge demonstration: "the second vehicle will arrive ten minutes late".

    python3 demo.py                    # local page on http://127.0.0.1:8765 (no internet, no map tiles)
    python3 demo.py --text --delay 10  # same computation in the terminal (Korean + English)
    python3 demo.py --text --case shuttle --delay 5
    python3 demo.py --export DIR       # self-contained HTML with every 0..60 minute delay precomputed

Every number shown is computed by the planner on the fictional fixtures in fixtures/ and independently replayed.
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from kcf_planner import explain as X  # noqa: E402
from kcf_planner.io import write_json_atomic  # noqa: E402
from kcf_planner.run import run_case  # noqa: E402

CASES = {
    "two": {"file": "fixtures/demo_two_vehicle.json", "delayed_vehicle": 1,
            "label_ko": "주 사례: 차량 2대 동시 이송", "label_en": "Primary: two vehicles in parallel"},
    "shuttle": {"file": "fixtures/demo_shuttle.json", "delayed_vehicle": 0,
                "label_ko": "별도 사례: 차량 1대 왕복", "label_en": "Separate case: one-vehicle shuttle"},
}
MAX_DELAY_MIN = 60
_cache = {}


def load(key):
    return json.loads((ROOT / CASES[key]["file"]).read_text(encoding="utf-8"))


def plan(key, delay_s):
    delay_s = max(0, min(int(delay_s), MAX_DELAY_MIN * 60))
    ck = (key, delay_s)
    if ck in _cache:
        return _cache[ck]
    spec = CASES[key]
    raw = load(key)
    vi = spec["delayed_vehicle"]
    before = run_case(json.loads(json.dumps(raw)))
    after_raw = X.apply_delay(raw, vi, delay_s)
    after = run_case(json.loads(json.dumps(after_raw)))
    vid = raw["vehicles"][vi]["id"]
    out = {
        "case_key": key, "case_label_ko": spec["label_ko"], "case_label_en": spec["label_en"],
        "delay_s": delay_s, "delayed_vehicle_id": vid,
        "delayed_vehicle_ko": raw["vehicles"][vi].get("name_ko", vid),
        "fixture": {k: raw.get(k) for k in ("title", "title_ko", "note", "note_ko", "node_labels_ko", "node_xy",
                                             "horizon_s", "destination_window", "board_s", "unload_s", "origin",
                                             "destination", "vehicles", "groups", "forbidden_turns", "mode",
                                             "fictional", "provenance")},
        "edges": raw["edges"],
        "before": before, "after": after,
        "compare": X.compare(raw, before, after_raw, after, vid),
        "checks_before": X.human_checks(raw, before), "checks_after": X.human_checks(after_raw, after),
        "status_ko": {k: X.STATUS_KO.get(r["status"], r["status"]) for k, r in (("before", before), ("after", after))},
        "reason_ko": {k: [X.REASON_KO.get(c, c) for c in r.get("reason_codes", [])]
                      for k, r in (("before", before), ("after", after))},
    }
    _cache[ck] = out
    return out


# -------------------------------------------------------------------------------------------------- terminal
def text_report(key, delay_s):
    p = plan(key, delay_s)
    L = []
    L.append("=" * 78)
    L.append("%s / %s  (가상 사례 · FICTIONAL)" % (p["case_label_ko"], p["case_label_en"]))
    L.append("변경: %s %d분 지연 / change: %s arrives %d min late" % (p["delayed_vehicle_ko"], delay_s // 60,
                                                                  p["delayed_vehicle_id"], delay_s // 60))
    L.append("=" * 78)
    for tag, name in (("before", "원래 계획 / original"), ("after", "지연 반영 / delayed")):
        r = p[tag]
        L.append("")
        L.append("[%s] %s — %s" % (name, r["status"], p["status_ko"][tag]))
        L.append("  마지막 하차 완료 final unloading: %s (%ss)" % (X.fmt(r["final_unload_s"]), r["final_unload_s"]))
        L.append("  확인된 이송 인원 people with checked transport: %d / %d   대기 awaiting: %d" % (
            r["people_with_checked_transport"], r["people_total"], r["people_total"] - r["people_with_checked_transport"]))
        for t in r["trips"]:
            L.append(_trip_line(t))
        for t in r.get("conditional_trips", []):
            L.append(_trip_line(t, "  (조건부·미확인 입력 필요 conditional) "))
        for c in p["reason_ko"][tag]:
            L.append("  · " + c)
    c = p["compare"]
    L.append("")
    L.append("바뀐 이유 / binding constraint:")
    for m in c.get("binding", []):
        L.append("  - " + m["text_ko"])
        L.append("    " + m["text_en"])
    L.append("")
    L.append("사람이 확인할 부분 / needs a person:")
    for h in p["checks_after"]:
        L.append("  - " + h["text_ko"])
    return "\n".join(L)


def _trip_line(t, prefix="  "):
    kind = {"outbound": "이송", "empty_return": "빈 차 복귀"}[t["kind"]]
    route = " → ".join(s["edge_id"] for s in t["edges"])
    s = "%s%s %s %s: 가용 %s" % (prefix, t.get("trip_id", ""), t["vehicle_id"], kind, X.fmt(t["ready_s"]))
    if t["kind"] == "outbound":
        s += " | 탑승 %s~%s" % (X.fmt(t["boarding_start_s"]), X.fmt(t["boarding_end_s"]))
    s += " | 출발 %s | 도착 %s" % (X.fmt(t["departure_s"]), X.fmt(t["arrival_s"]))
    if t["kind"] == "outbound":
        s += " | 하차 완료 %s | %s %d명" % (X.fmt(t["unloading_end_s"]), t["group_id"], t["people"])
    if "length_m" in t:
        s += " | %.1f km" % (t["length_m"] / 1000)
    return s + "\n      " + route


# -------------------------------------------------------------------------------------------------- web
def page(embed=None):
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    data = "null" if embed is None else json.dumps(embed, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/")
    return html.replace("/*__KCF_EMBED__*/null", data)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, page(), "text/html; charset=utf-8")
        if u.path == "/api/plan":
            q = parse_qs(u.query)
            key = q.get("case", ["two"])[0]
            if key not in CASES:
                return self._send(400, json.dumps({"error": "unknown case"}), "application/json")
            try:
                delay = int(float(q.get("delay_s", ["600"])[0]))
            except ValueError:
                return self._send(400, json.dumps({"error": "bad delay"}), "application/json")
            return self._send(200, json.dumps(plan(key, delay), ensure_ascii=False), "application/json; charset=utf-8")
        return self._send(404, "not found", "text/plain")


def serve(port, open_browser):
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = "http://127.0.0.1:%d/" % httpd.server_address[1]
    print("KCF facility planner demo (offline, fictional fixture): %s  — Ctrl+C to stop" % url, flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def export(out_dir):
    embed = {}
    for key in CASES:
        for m in range(0, MAX_DELAY_MIN + 1):
            embed["%s|%d" % (key, m * 60)] = plan(key, m * 60)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "kcf_demo.html"
    tmp = out / ".kcf_demo.html.tmp"
    tmp.write_text(page(embed), encoding="utf-8")
    os.replace(tmp, target)
    for key in CASES:
        write_json_atomic(out / ("%s_delay600.json" % key), plan(key, 600))
    print("wrote %s (%d precomputed plans)" % (target, len(embed)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", action="store_true", help="print the comparison in the terminal")
    ap.add_argument("--case", choices=sorted(CASES), default="two")
    ap.add_argument("--delay", type=float, default=10, help="delay in minutes (default 10)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--export", metavar="DIR", help="write a self-contained HTML with precomputed delays")
    a = ap.parse_args(argv)
    if a.text:
        print(text_report(a.case, int(round(a.delay * 60))))
        return 0
    if a.export:
        export(a.export)
        return 0
    serve(a.port, not a.no_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
