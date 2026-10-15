#!/usr/bin/env python3
"""Screenshots for the M1/M2 visual check (spec test 11): every state in Korean and English at 1512 x 982 and
1728 x 1117, and each state that has a mockup next to it.

  python3 tools/screenshots.py                      -> out/screenshots/
  python3 tools/screenshots.py --sizes 1512x982 --langs ko

The app runs from a temporary copy with the simulated logger (states: start, the key help, replay mid-stop with the
close-up, summary, device connect card, test in progress, result, the P menu, LIVE without a fix and LIVE walking with
a fix), so nothing is written into sessions/. Mockups are read from ../demo_live_v2_1/mockup/ when the planning
package is next to this folder. Needs Playwright's Chromium.
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
GL = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
MOCKUPS = ROOT.parent / "demo_live_v2_1" / "mockup"
MATCH = {"start": "start", "replay": "booth", "summary": "summary", "device_connect": "device_connect",
         "device_test": "device_check", "device_result": "device_result"}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(base, path):
    with _opener().open(base + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(base, path, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with _opener().open(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


class Server:
    def __init__(self, flag):
        self.work = Path(tempfile.mkdtemp(prefix="wfg_shots_"))
        for d in ("app", "web", "mapdata"):
            shutil.copytree(ROOT / d, self.work / d, ignore=shutil.ignore_patterns("__pycache__"))
        (self.work / "sessions").mkdir()
        shutil.copytree(ROOT / "sessions" / "sim", self.work / "sessions" / "sim",
                        ignore=shutil.ignore_patterns("device_double"))
        shutil.copy(ROOT / "sessions" / "sessions.json", self.work / "sessions" / "sessions.json")
        self.port = _free_port()
        self.base = "http://127.0.0.1:%d" % self.port
        self.proc = subprocess.Popen([sys.executable, "-m", "app.main", "--port", str(self.port), "--quiet", flag],
                                     cwd=self.work, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):
            try:
                _get(self.base, "/api/health")
                return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("the server did not start")

    def stop(self):
        self.proc.terminate()
        self.proc.wait(5)
        shutil.rmtree(self.work, ignore_errors=True)


def _page(browser, base, size, lang):
    pg = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=1)
    pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base + "/") else r.abort())
    pg.goto("%s/?test&lang=%s" % (base, lang))
    pg.wait_for_selector("#scr-start.on .sc", timeout=15000)
    time.sleep(0.6)
    return pg


def _settle(pg, s=1.2):
    time.sleep(s)


def shoot_basic(browser, srv, size, lang, out):
    base = srv.base
    shots = {}
    pg = _page(browser, base, size, lang)
    pg.screenshot(path=str(out / ("start_%s.png" % lang)))
    shots["start"] = out / ("start_%s.png" % lang)
    pg.keyboard.press("h")
    pg.wait_for_selector(".sheet.help", timeout=5000)
    _settle(pg, 0.6)
    pg.screenshot(path=str(out / ("help_%s.png" % lang)))
    shots["help"] = out / ("help_%s.png" % lang)
    pg.keyboard.press("h")
    # replay mid-stop with the close-up (key 1, stop 3, 22 s in), as in the mockup
    payload = _get(base, "/api/session?key=1")
    st = next(s for s in payload["stops"] if s["n"] == 3)
    pg.keyboard.press("1")
    pg.wait_for_function("window.__app.booth.playing", timeout=15000)
    pg.evaluate("(tt) => { const b = window.__app.booth; b.pause(); b.tau = tt; b._rebuildConsole(); b._render(true, true); }",
                st["t0"] + 22)
    _settle(pg, 2.5)
    pg.evaluate("() => { const b = window.__app.booth; b._render(true, false); b.console.flush(); }")
    _settle(pg, 1.0)
    pg.screenshot(path=str(out / ("replay_%s.png" % lang)))
    shots["replay"] = out / ("replay_%s.png" % lang)
    pg.evaluate("() => { const b = window.__app.booth; b.tau = b.tEnd - 0.5; b._rebuildConsole(); b._render(true, true); b.play(); }")
    pg.wait_for_selector("#scr-summary.on .tile", timeout=30000)
    _settle(pg, 3.0)
    pg.screenshot(path=str(out / ("summary_%s.png" % lang)))
    shots["summary"] = out / ("summary_%s.png" % lang)
    # the device segment: connect card, test in progress, result, P menu
    pg.keyboard.press("Escape")
    pg.keyboard.press("d")
    pg.wait_for_selector("#scr-device.on .prow", timeout=10000)
    _settle(pg, 0.8)
    pg.screenshot(path=str(out / ("device_connect_%s.png" % lang)))
    shots["device_connect"] = out / ("device_connect_%s.png" % lang)
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#scr-device .dpage .dname", timeout=15000)
    pg.keyboard.press("t")
    pg.wait_for_selector("#scr-device .tcard .step.now", timeout=5000)
    _post(base, "/api/device/double/press", {"kind": "long"})
    pg.wait_for_function("document.querySelectorAll('#scr-device .tcard .step.done').length >= 1", timeout=8000)
    _post(base, "/api/device/double/press", {"kind": "short"})
    pg.wait_for_function("document.querySelectorAll('#scr-device .tcard .step.done').length >= 2", timeout=8000)
    _settle(pg, 9.0)                                    # part of the 30 s wait, with the record count climbing
    pg.screenshot(path=str(out / ("device_test_%s.png" % lang)))
    shots["device_test"] = out / ("device_test_%s.png" % lang)
    pg.wait_for_function("document.querySelectorAll('#scr-device .tcard .step.done').length >= 3", timeout=40000)
    _post(base, "/api/device/double/press", {"kind": "long"})
    pg.wait_for_selector("#scr-device .rcard", timeout=20000)
    pg.click("#scr-device .b-scr[data-v='1']")
    _settle(pg, 1.2)
    pg.screenshot(path=str(out / ("device_result_%s.png" % lang)))
    shots["device_result"] = out / ("device_result_%s.png" % lang)
    _post(base, "/api/device/double/samples", {})
    pg.keyboard.press("p")
    pg.wait_for_selector(".sheet .ptable", timeout=15000)
    _settle(pg, 0.8)
    pg.screenshot(path=str(out / ("p_menu_%s.png" % lang)))
    shots["p_menu"] = out / ("p_menu_%s.png" % lang)
    pg.keyboard.press("Escape")
    _post(base, "/api/device/disconnect", {})
    pg.close()
    return shots


def shoot_live(browser, srv, size, lang, out):
    base = srv.base
    pg = _page(browser, base, size, lang)
    pg.keyboard.press("d")
    pg.wait_for_selector("#scr-device.on .prow", timeout=10000)
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#scr-device .mapwrap .stats", timeout=15000)
    _post(base, "/api/device/double/press", {"kind": "long"})
    _settle(pg, 4.0)
    p = out / ("live_nofix_%s.png" % lang)
    pg.screenshot(path=str(p))
    _post(base, "/api/device/double/press", {"kind": "long"})            # stop that recording
    _settle(pg, 2.0)
    _post(base, "/api/device/double/gnss", {"mode": "fix"})               # outdoors: walk round the block
    _post(base, "/api/device/double/press", {"kind": "long"})
    pg.wait_for_function("(window.__app.live.rows || []).filter(r => r.f).length >= 25", timeout=60000)
    _settle(pg, 2.0)
    q = out / ("live_fix_%s.png" % lang)
    pg.screenshot(path=str(q))
    _post(base, "/api/device/double/press", {"kind": "long"})
    _post(base, "/api/device/disconnect", {})
    pg.close()
    return {"live_nofix": p, "live_fix": q}


def side_by_side(app_png, mock_png, dst):
    from PIL import Image, ImageDraw
    a = Image.open(app_png).convert("RGB")
    m = Image.open(mock_png).convert("RGB")
    m = m.resize((a.width, round(m.height * a.width / m.width)))
    pad, head = 24, 40
    W, H = a.width * 2 + pad * 3, max(a.height, m.height) + pad * 2 + head
    img = Image.new("RGB", (W, H), (245, 245, 247))
    d = ImageDraw.Draw(img)
    d.text((pad, pad), "mockup: " + mock_png.name, fill=(60, 60, 67))
    d.text((pad * 2 + a.width, pad), "app: " + app_png.name, fill=(60, 60, 67))
    img.paste(m, (pad, pad + head))
    img.paste(a, (pad * 2 + a.width, pad + head))
    img.save(dst, quality=88)


def main(argv=None):
    ap = argparse.ArgumentParser(description="screenshots for the visual check")
    ap.add_argument("--out", default=str(ROOT / "out" / "screenshots"))
    ap.add_argument("--sizes", default="1512x982,1728x1117")
    ap.add_argument("--langs", default="ko,en")
    a = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright
    out = Path(a.out)
    sizes = [tuple(int(v) for v in s.split("x")) for s in a.sizes.split(",")]
    langs = a.langs.split(",")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=GL)
        for size in sizes:
            d = out / ("%dx%d" % size)
            d.mkdir(parents=True, exist_ok=True)
            for lang in langs:
                srv = Server("--dev-device-double")
                try:
                    shots = shoot_basic(browser, srv, size, lang, d)
                finally:
                    srv.stop()
                srv = Server("--dev-double-live")
                try:
                    shots.update(shoot_live(browser, srv, size, lang, d))
                finally:
                    srv.stop()
                for state, png in shots.items():
                    mock = MOCKUPS / ("%s_%s.png" % (MATCH.get(state, ""), lang))
                    if state in MATCH and mock.exists() and size == sizes[0]:
                        side_by_side(png, mock, out / ("compare_%s_%s.jpg" % (state, lang)))
                print("%dx%d %s: %s" % (size + (lang, ", ".join(sorted(shots)))))
        browser.close()
    print("written to", out)


if __name__ == "__main__":
    main()
