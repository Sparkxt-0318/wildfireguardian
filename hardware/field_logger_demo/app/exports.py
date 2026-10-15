"""Exports (key E, spec section 9): summary_ko.png and summary_en.png (3200 x 2000, white), stops.csv, summary.json.

The PNGs are made by headless Chromium (Playwright) from the same front end in its export mode. Headless Chromium
may have no WebGL, which would give a blank map, so it is launched with a software GL and every PNG is checked for a
non-blank map before it is kept.
"""
import csv
import datetime as dt
import json
import subprocess
import time
from zoneinfo import ZoneInfo

from . import __version__, config, replay

GL_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
MAP_BOX = (48, 210, 950, 828)   # map card in CSS pixels on the 1600 x 1000 export page (see summary.css)


def _git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT, capture_output=True, text=True,
                             timeout=5)
        return out.stdout.strip() or "not in git"
    except (OSError, subprocess.SubprocessError):
        return "not in git"


def _iso(utc_ms, tz):
    if utc_ms is None:
        return ""
    return dt.datetime.fromtimestamp(utc_ms / 1000.0, tz=ZoneInfo(tz)).isoformat(timespec="seconds")


def _row_utc(payload, t):
    best = None
    for r in payload["rows"]:
        if r["u"] is not None and abs(r["t"] - t) < 1e-6:
            return r["u"]
        if r["u"] is not None and r["t"] <= t:
            best = r["u"] + int(round((t - r["t"]) * 1000))
    return best


def write_tables(payload, out_dir):
    tz = payload["meta"]["tz"]
    with open(out_dir / "stops.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stop_no", "start_utc_est", "end_utc_est", "duration_s", "lat", "lon", "n_rows", "median_hdop",
                    "matched_event_no"])
        for s in payload["stops"]:
            w.writerow([s["n"], _iso(_row_utc(payload, s["t0"]), tz), _iso(_row_utc(payload, s["t1"]), tz),
                        "%.0f" % s["dur"], "" if s["la"] is None else "%.7f" % s["la"],
                        "" if s["lo"] is None else "%.7f" % s["lo"], s["nr"], "" if s["hd"] is None else s["hd"],
                        "" if s["me"] is None else s["me"]])
    summ = replay.summary_numbers(payload)
    summ.update({"app_version": __version__, "git_commit": _git_commit(),
                 "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "time_zone": tz})
    (out_dir / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")


def _map_not_blank(png_path):
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    sx = im.width / 1600.0
    box = tuple(int(v * sx) for v in MAP_BOX)
    crop = im.crop(box).resize((200, 140))
    colours = crop.getcolors(200 * 140) or []
    return len(colours) > 12


def export(base_url, query, payload, langs=("ko", "en")):
    """query: 'key=1' or 'file=real/...'. Returns a dict of written paths."""
    sid = payload["meta"]["sid"] or "session"
    out_dir = config.OUT / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    write_tables(payload, out_dir)
    written = [str(out_dir / "stops.csv"), str(out_dir / "summary.json")]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(args=GL_ARGS)
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base_url)
                   else route.abort())
        for lang in langs:
            page.goto("%s/?export=summary&%s&lang=%s" % (base_url, query, lang))
            page.wait_for_function("window.__exportReady === true", timeout=60000)
            time.sleep(0.3)
            dst = out_dir / ("summary_%s.png" % lang)
            page.screenshot(path=str(dst))
            if not _map_not_blank(dst):
                dst.unlink()
                browser.close()
                raise RuntimeError("the exported map came out blank (no WebGL in headless Chromium?)")
            written.append(str(dst))
        browser.close()
    return {"dir": str(out_dir), "files": written}
