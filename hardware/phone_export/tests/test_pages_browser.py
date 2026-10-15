#!/usr/bin/env python3
"""HOST/SIMULATED browser tests (headless Chromium via Playwright; NOT a real iPhone/Android test).

1. viewer.html: loads the sample CSV and GPX, checks computed stats, saves screenshots (phone-sized viewport).
2. firmware/web/device_page.html: served by a tiny Python mock of the device HTTP API (same endpoints/JSON as
   firmware/src/web_export.cpp) over plain HTTP; clicks "Save raw .wfg", checks the in-page JS SHA-256 + per-record
   CRC verification, and that "Confirm export" then reaches the mock with the correct hash.
Requires: pip install playwright && python3 -m playwright install chromium
Run: python3 phone_export/tests/test_pages_browser.py [screenshot_dir]
"""
import hashlib
import http.server
import json
import os
import sys
import threading
import urllib.parse

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
PE = os.path.dirname(HERE)
FW = os.path.join(os.path.dirname(PE), "firmware")
sys.path.insert(0, PE)
import usb_export as ue  # noqa: E402

SAMPLES = os.path.join(PE, "samples")
passed = failed = 0


def check(c, m):
    global passed, failed
    if c:
        passed += 1
    else:
        failed += 1
        print("FAIL:", m)


def test_viewer(p, shots):
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    requests = []
    pg.on("request", lambda r: requests.append(r.url))
    pg.goto("file://" + os.path.join(PE, "viewer.html"))
    csv = open(os.path.join(SAMPLES, "S000001_WALK.csv")).read()
    st = pg.evaluate("([t,n])=>window.__wfgLoad(t,n)", [csv, "S000001_WALK.csv"])
    check(st["points"] == 60, "csv points %r" % st["points"])
    check(st["events"] == 3 and st["evLoc"] == 1, "events %r/%r" % (st["events"], st["evLoc"]))
    check(st["nofix"] == 17, "nofix rows %r" % st["nofix"])
    check(1.0 <= st["maxGap"] <= 1.6, "max recording gap %r" % st["maxGap"])
    check(13.0 <= st["maxFixGap"] <= 15.0, "max fix gap %r" % st["maxFixGap"])
    check(15 < st["pctNoFix"] < 25, "pct no fix %r" % st["pctNoFix"])
    check(st["statusRows"] == 2 and st["startReason"] == "OWNER_BUTTON", "status rows/start reason %r" % st)
    txt = pg.inner_text("#stats")
    check("3988 mV at start" in txt, "battery stat shown")
    # older CSV (firmware 0.1.0, no STATUS/start columns) still loads
    old = open(os.path.join(SAMPLES, "format_v1", "S000001_WALK_v1_as_exported_by_fw0.1.0.csv")).read()
    st0 = pg.evaluate("([t,n])=>window.__wfgLoad(t,n)", [old, "old.csv"])
    check(st0["points"] == 60 and st0["statusRows"] == 0, "v1 CSV loads in viewer")
    rs = open(os.path.join(SAMPLES, "S000002_WALK_autoresumed.csv")).read()
    st3 = pg.evaluate("([t,n])=>window.__wfgLoad(t,n)", [rs, "r.csv"])
    check(st3["startReason"] == "AUTO_RESUMED_AFTER_RESET", "resumed CSV start reason")
    if shots:
        pg.screenshot(path=os.path.join(shots, "viewer_autoresumed_phone.png"), full_page=True)
    pg.evaluate("([t,n])=>window.__wfgLoad(t,n)", [csv, "S000001_WALK.csv"])
    if shots:
        pg.screenshot(path=os.path.join(shots, "viewer_csv_phone.png"), full_page=True)
    gpx = open(os.path.join(SAMPLES, "S000001_WALK.gpx")).read()
    st2 = pg.evaluate("([t,n])=>window.__wfgLoad(t,n)", [gpx, "S000001_WALK.gpx"])
    check(st2["points"] == 60 and st2["events"] == 3 and st2["evLoc"] == 1, "gpx stats %r" % st2)
    if shots:
        pg.emulate_media(color_scheme="dark")
        pg.screenshot(path=os.path.join(shots, "viewer_gpx_phone_dark.png"), full_page=True)
    check(not errors, "viewer JS errors %r" % errors)
    check(all(u.startswith("file://") or u.startswith("data:") for u in requests), "viewer made network requests %r" % requests)
    b.close()


class Mock(http.server.BaseHTTPRequestHandler):
    data = b""
    confirmed = None

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, fmt):
        d = Mock.data
        return {"wfg": d, "csv": ue.to_csv(d).encode(), "gpx": ue.to_gpx(d).encode(),
                "geojson": ue.to_geojson(d).encode()}[fmt]

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/":
            html = open(os.path.join(FW, "web", "device_page.html"), encoding="utf-8").read()
            return self._send(200, html, "text/html; charset=utf-8")
        if u.path == "/api/status":
            return self._send(200, json.dumps({"device": "1A2B3C4D", "board": "MOCK", "fw": "0.1.0", "state": "IDLE",
                                               "used": 40960, "total": 6750208, "last_delete": ""}))
        if u.path == "/api/list":
            return self._send(200, json.dumps([{"name": "S000001.wfg", "session_id": "WFG-1A2B3C4D-000001",
                                                "mode": "WALK", "size": len(Mock.data), "records": len(Mock.data) // 48,
                                                "closed": True, "end_reason": "USER_STOP",
                                                "exported": Mock.confirmed is not None, "ok_sha": Mock.confirmed or "",
                                                "active": False}]))
        if u.path == "/api/sha":
            b = self._file(q["fmt"])
            return self._send(200, json.dumps({"sha256": hashlib.sha256(b).hexdigest(), "size": len(b)}))
        if u.path == "/dl":
            return self._send(200, self._file(q["fmt"]), "application/octet-stream")
        self._send(404, "{}")

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/api/confirm":
            ok = q.get("sha") == hashlib.sha256(Mock.data).hexdigest()
            if ok:
                Mock.confirmed = q["sha"]
            return self._send(200 if ok else 409, json.dumps({"ok": ok, "why": "" if ok else "hash"}))
        self._send(404, "{}")


def test_device_page(p, shots):
    Mock.data = open(os.path.join(SAMPLES, "S000001_WALK.wfg"), "rb").read()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(url)
    pg.wait_for_selector("text=WFG-1A2B3C4D-000001")
    check(pg.evaluate("window.isSecureContext") in (True, False), "secure context query")
    with pg.expect_download() as dl:
        pg.click("text=Save raw .wfg")
    path = dl.value.path()
    got = open(path, "rb").read()
    check(got == Mock.data, "downloaded .wfg identical")
    check(dl.value.suggested_filename == "WFG-1A2B3C4D-000001_WALK.wfg", "filename %s" % dl.value.suggested_filename)
    pg.wait_for_selector("text=wfg verified")
    txt = pg.inner_text("body")
    check(hashlib.sha256(Mock.data).hexdigest() in txt, "page shows the SHA-256 it computed in JS")
    check("CRC errors 0" in txt, "page checked per-record CRC")
    for fmt, label in (("csv", "Save CSV"), ("gpx", "Save GPX"), ("geojson", "Save GEOJSON")):
        with pg.expect_download() as d2:
            pg.click("text=" + label)
        conv = {"csv": ue.to_csv, "gpx": ue.to_gpx, "geojson": ue.to_geojson}[fmt]
        check(open(d2.value.path(), "rb").read() == conv(Mock.data).encode(), "%s download content" % fmt)
        pg.wait_for_selector("text=%s verified" % fmt)
    pg.click("text=Confirm export")
    pg.wait_for_selector("text=export confirmed")
    check(Mock.confirmed == hashlib.sha256(Mock.data).hexdigest(), "device received matching confirmation")
    if shots:
        pg.screenshot(path=os.path.join(shots, "device_page_phone.png"), full_page=True)
    check(not errors, "device page JS errors %r" % errors)
    b.close()
    srv.shutdown()


if __name__ == "__main__":
    shots = sys.argv[1] if len(sys.argv) > 1 else None
    if shots:
        os.makedirs(shots, exist_ok=True)
    with sync_playwright() as p:
        test_viewer(p, shots)
        test_device_page(p, shots)
    print("BROWSER HOST TESTS (headless Chromium, simulated device): %d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)
