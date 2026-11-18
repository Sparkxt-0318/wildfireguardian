"""Shared paths, settings, time helpers, HTTP and the notice text (live/PROTOCOL.md)."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1]
REPO = LIVE.parent
ROADLAYER = REPO / "product/wfg-roadlayer"
for p in (REPO / "research/kcf-replay", REPO / "research/kcf-abstain", REPO / "research/kcf-aloft",
          REPO / "research/kcf-margin", ROADLAYER):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

UA = "wfg-live/1.0 (+https://github.com/Sparkxt-0318/wildfireguardian/tree/Main/live)"
KST = timezone(timedelta(hours=9))
UTC = timezone.utc

NOTICE = {
    "ko": "모델 출력 · 참고용 · 공식 명령 아님. 당국의 안내에 따르십시오. 공식 사용을 주장하지 않습니다.",
    "en": "Model output, advisory, not an official order; follow instructions from authorities. No official use is claimed.",
}


def settings(path: Path | None = None) -> dict:
    p = path or LIVE / "config/live.toml"
    return tomllib.loads(p.read_text(encoding="utf-8"))


def settings_sha256(path: Path | None = None) -> str:
    return sha256((path or LIVE / "config/live.toml").read_bytes())


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(t: datetime | None) -> str | None:
    return None if t is None else t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def kst(t: datetime) -> str:
    return t.astimezone(KST).strftime("%Y-%m-%d %H:%M")


def stamp(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y%m%dT%H%MZ")


def http(url: str, data: bytes | None = None, headers: dict | None = None, timeout=60, attempts=3, wait=10):
    """-> (status, body bytes or None, error text). Retries network errors and 5xx; never 4xx."""
    err = ""
    for i in range(attempts):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), ""
        except urllib.error.HTTPError as e:
            err = "HTTP %d" % e.code
            if e.code < 500:
                return e.code, None, err
        except Exception as e:  # noqa: BLE001 - every network failure is recorded, not raised
            err = "%s: %s" % (type(e).__name__, e)
        if i + 1 < attempts:
            time.sleep(wait)
    return 0, None, err


def dump(path: Path, obj) -> bytes:
    b = (json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b)
    return b
