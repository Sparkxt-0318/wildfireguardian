#!/usr/bin/env python3
"""Download the approved clips listed in data/clips_manifest.yaml into data/raw/.

Polite to the hosts: one file at a time, a descriptive User-Agent, resume of partial files
with HTTP Range, and a 10 minute pause after any HTTP 429 (Wikimedia's rate limit). After
each download the file is hashed and probed, and its row is written to data/clips.csv
(replacing any earlier row for the same clip). SOURCES.md is updated by
scripts/fetch_clips.py --sources from clips.csv.

HTTPS certificates: python.org's macOS Python has no certificates of its own until its
"Install Certificates.command" has been run, so every download would fail with
CERTIFICATE_VERIFY_FAILED. The downloads therefore trust certifi's bundle (pinned for macOS in
requirements.txt, so setup_mac.sh installs it) and, on macOS, the system's /etc/ssl/cert.pem, on
top of Python's own defaults.

Usage:
  .venv/bin/python scripts/fetch_clips.py [--only C2_dolan ...] [--max-wait-min 60]
  .venv/bin/python scripts/fetch_clips.py --sources      # rewrite the clip table in SOURCES.md
  .venv/bin/python scripts/fetch_clips.py --probe [--only ...]   # can this Python reach the hosts? (exit 0 or 1)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wfglink.provenance import sha256_file  # noqa: E402
from wfglink.io.probe import probe_video  # noqa: E402

MANIFEST = ROOT / "data" / "clips_manifest.yaml"
RAW = ROOT / "data" / "raw"
CSV = ROOT / "data" / "clips.csv"
SOURCES = ROOT / "data" / "SOURCES.md"
UA = "wfglink/0.1 (WildfireGuardian student research; https://github.com/Sparkxt-0318/wildfireguardian)"
SHANGHAI = dt.timezone(dt.timedelta(hours=8))


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(SHANGHAI).strftime('%H:%M:%S')}] {msg}", flush=True)


CERT_FIX = ("this Python has no HTTPS certificates: run ./scripts/setup_mac.sh again (it installs certifi), "
            "or double-click 'Install Certificates.command' in /Applications/Python 3.12")


def ssl_context() -> ssl.SSLContext:
    """Python's default certificates, plus certifi's bundle when installed and, on macOS, the
    system's /etc/ssl/cert.pem (see the module docstring)."""
    ctx = ssl.create_default_context()
    extra = []
    try:
        import certifi

        extra.append(certifi.where())
    except ImportError:
        pass
    if sys.platform == "darwin":
        extra.append("/etc/ssl/cert.pem")
    for cafile in extra:
        if Path(cafile).is_file():
            try:
                ctx.load_verify_locations(cafile=cafile)
            except (OSError, ssl.SSLError):
                pass
    return ctx


def _cert_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)


def probe(url: str, timeout: float = 10.0) -> str | None:
    """None when this Python reaches the host over HTTPS (any HTTP answer counts), else why not."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()):
            return None
    except urllib.error.HTTPError:
        return None
    except Exception as exc:     # no network, DNS, TLS
        return CERT_FIX if _cert_error(exc) else f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"


def download(url: str, dest: Path, max_wait_min: float) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    waited = 0.0
    attempt = 0
    while True:
        attempt += 1
        have = part.stat().st_size if part.exists() else 0
        req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Range": f"bytes={have}-"} if have else {})})
        try:
            with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as resp:
                mode = "ab" if have and resp.status == 206 else "wb"
                total = resp.headers.get("Content-Length")
                log(f"  HTTP {resp.status}, {'resuming at ' + str(have) if mode == 'ab' else 'starting'}"
                    f"{', ' + str(round(int(total) / 1e6, 1)) + ' MB to go' if total else ''}")
                with open(part, mode) as f:
                    while chunk := resp.read(1 << 20):
                        f.write(chunk)
            part.replace(dest)
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                if waited >= max_wait_min * 60:
                    raise RuntimeError("rate limited for too long") from exc
                retry = int(exc.headers.get("Retry-After", "600") or 600)
                retry = max(600, min(retry, 1800))
                log(f"  HTTP 429, waiting {retry // 60} min as the host asks")
                time.sleep(retry)
                waited += retry
                continue
            if exc.code == 416 and part.exists():  # already complete
                part.replace(dest)
                return
            if attempt < 4 and exc.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if _cert_error(exc):
                raise RuntimeError(CERT_FIX) from exc
            if attempt < 6:
                log(f"  network error ({exc}); retrying in {2 ** attempt} s")
                time.sleep(2 ** attempt)
                continue
            raise


FIELDS = ["clip_id", "title", "source", "page_url", "media_url", "license", "credit_line", "permission_notes",
          "date_recorded", "date_accessed", "event_location", "duration_s", "width", "height", "fps", "codec",
          "sha256", "camera_type", "viewpoint", "day_night", "moving_static", "lane_markings", "ember_visibility",
          "split", "metrics_scope", "notes"]


def read_rows() -> dict[str, dict]:
    if not CSV.exists():
        return {}
    with open(CSV, newline="", encoding="utf-8") as f:
        return {r["clip_id"]: r for r in csv.DictReader(f)}


def write_rows(rows: dict[str, dict]) -> None:
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for key in sorted(rows):
            w.writerow({k: rows[key].get(k, "") for k in FIELDS})


def record(clip: dict, path: Path) -> dict:
    meta = probe_video(path)
    return {
        "clip_id": clip["id"], "title": clip["title"], "source": clip["page_url"].split("/")[2],
        "page_url": clip["page_url"], "media_url": clip["media_url"], "license": clip["license"],
        "credit_line": clip["credit"], "permission_notes": "conditional: kept only if real ember footage" if clip.get("conditional") else "",
        "date_recorded": "", "date_accessed": dt.datetime.now(SHANGHAI).date().isoformat(),
        "event_location": clip.get("event", ""), "duration_s": meta.get("duration_s"), "width": meta.get("width"),
        "height": meta.get("height"), "fps": meta.get("fps"), "codec": meta.get("codec"), "sha256": sha256_file(path),
        "split": clip.get("split", ""), "metrics_scope": clip.get("metrics_scope", "all"),
        "notes": f"file {path.name}; {path.stat().st_size} bytes" + (f"; use segments {clip['use_segments']}" if clip.get("use_segments") else ""),
    }


def update_sources(rows: dict[str, dict]) -> None:
    text = SOURCES.read_text(encoding="utf-8")
    marker = "| Clip | Title | License | Credit line | Page URL | Accessed | SHA-256 |"
    head, _, _ = text.partition(marker)
    lines = [marker, "|---|---|---|---|---|---|---|"]
    for key in sorted(rows):
        r = rows[key]
        lines.append(f"| {r['clip_id']} | {r['title']} | {r['license']} | {r['credit_line']} | {r['page_url']} | "
                     f"{r['date_accessed']} | {r['sha256'][:16]} |")
    SOURCES.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--max-wait-min", type=float, default=90)
    ap.add_argument("--sources", action="store_true", help="only rewrite the clip table in SOURCES.md")
    ap.add_argument("--probe", action="store_true",
                    help="only check that this Python reaches the clips' hosts over HTTPS (exit 0 or 1)")
    args = ap.parse_args()
    rows = read_rows()
    if args.sources:
        update_sources(rows)
        return 0
    clips = yaml.safe_load(MANIFEST.read_text())["clips"]
    if args.only:
        clips = [c for c in clips if c["id"] in args.only]
    if args.probe:
        bad = 0
        for host, url in {c["media_url"].split("/")[2]: c["media_url"] for c in clips}.items():
            why = probe(url)
            log(f"{host}: {'reachable' if why is None else 'NOT reachable: ' + why}")
            bad += why is not None
        return 1 if bad or not clips else 0
    RAW.mkdir(parents=True, exist_ok=True)
    failures = []
    for clip in clips:
        ext = Path(clip["media_url"].split("?")[0]).suffix or ".mp4"
        if "kaltura" in clip["media_url"]:
            ext = ".mp4"
        dest = RAW / f"{clip['id']}{ext}"
        if dest.exists() and clip["id"] in rows and rows[clip["id"]].get("sha256") == sha256_file(dest):
            log(f"{clip['id']}: already downloaded")
            continue
        if dest.exists():
            # A finished download is only ever renamed from its .part file, so a file that is
            # there and reads as video is complete, even when data/clips.csv (tracked, and reset
            # by a forced update) has no row for it: it is not downloaded again.
            try:
                if probe_video(dest).get("width"):
                    log(f"{clip['id']}: already in data/raw (no matching row in data/clips.csv); kept")
                    continue
            except Exception:
                pass
            log(f"{clip['id']}: the file in data/raw does not read as video; downloading it again")
        log(f"{clip['id']}: {clip['media_url']}")
        try:
            download(clip["media_url"], dest, args.max_wait_min)
        except Exception as exc:
            log(f"{clip['id']}: FAILED ({exc})")
            failures.append(clip["id"])
            continue
        rows = read_rows()  # another run may have added rows meanwhile
        rows[clip["id"]] = record(clip, dest)
        write_rows(rows)
        update_sources(rows)
        log(f"{clip['id']}: done, {dest.stat().st_size / 1e6:.1f} MB, sha256 {rows[clip['id']]['sha256'][:12]}")
        time.sleep(5)
    log("finished" + (f"; failed: {', '.join(failures)}" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
