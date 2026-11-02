#!/usr/bin/env python3
"""Save the recorded forecast cells of every cached scenario for the static demo (standard library only).

For each entry of planner/cache/INDEX.json this asks a running Route-Check API for

    GET /v1/regions/{region}/forecast?input_time={input_time}&only_nonzero=true

(exactly what the planner requests) and writes the response body unchanged to
planner/public/data/forecast/<region>__<YYYYMMDDTHHMMSSZ>.json, plus INDEX.json with provenance.

The endpoint is a data read, not a search: it reformats the recorded c651 forecast export
(FORECAST_<t>.npz, its record) and the recorded packet (constructed_arrays.npz) of that input time
(api/forecast.py). It is refused unless the response's scenario set, checkpoint and packet hashes
(packet/constructed_arrays.npz, packet/NATIVE_METADATA.json) equal those the cached route checks of
that scenario recorded, and never from the MOCK server (its fixtures hold the same values — south-up
rows, rounded coordinates — but are labelled MOCK, without the packet hashes this check compares).

    make api   # or: WFG_API_PORT=18766 python -m api   (repository root; recorded inputs from
               #     python tools/fetch_routing_inputs.py)
    python planner/scripts/save_forecasts.py --api http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PLANNER = Path(__file__).resolve().parents[1]
REPO = PLANNER.parent
PACKET_KEYS = ("packet/constructed_arrays.npz", "packet/NATIVE_METADATA.json")
# code that produces the response (route, forecast read, region registry, identity) — recorded by blob id
CODE_FILES = ("api/__init__.py", "api/app.py", "api/config.py", "api/forecast.py", "api/provenance.py", "api/regions.py",
              "integration/src/wfg_latest/packets.py")


def compact(iso: str) -> str:
    return dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y%m%dT%H%M%SZ")


def get(base: str, path: str) -> tuple[bytes, str]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # a local API: never through a proxy
    with opener.open(base.rstrip("/") + path, timeout=300) as r:
        return r.read(), r.headers.get("content-type", "")


def git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else None
    except OSError:
        return None


def cached_packet(cache_file: Path) -> dict:
    """Scenario set, checkpoint and packet hashes recorded by the cached route checks (all must agree)."""
    doc = json.loads(cache_file.read_text())
    seen: dict[tuple, int] = {}
    for job in doc.get("route_checks", {}).values():
        prov = ((job.get("result") or {}).get("provenance")) or job.get("provenance") or {}
        hashes = prov.get("input_hashes") or {}
        key = (prov.get("scenario_set_id"), prov.get("checkpoint"), prov.get("graph_id")) + tuple(hashes.get(k) for k in PACKET_KEYS)
        seen[key] = seen.get(key, 0) + 1
    if len(seen) != 1:
        raise SystemExit(f"{cache_file}: route checks disagree on their packet: {seen}")
    (key, n), = seen.items()
    booth_commit = (((doc.get("api") or {}).get("health")) or {}).get("git_commit")
    return {"scenario_set_id": key[0], "checkpoint": key[1], "graph_id": key[2], "packet": dict(zip(PACKET_KEYS, key[3:])), "route_checks": n,
            "booth_api_commit": booth_commit}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--api", default="http://127.0.0.1:8765", help="Route-Check API base (without /v1)")
    ap.add_argument("--out", type=Path, default=PLANNER / "public" / "data" / "forecast")
    a = ap.parse_args()

    health = json.loads(get(a.api, "/v1/health")[0])
    if health.get("mode") == "mock" or health.get("mock") is True:
        raise SystemExit("this is the MOCK server: its forecast fixtures hold the same values (south-up rows, "
                         "rounded coordinates) but are labelled MOCK; save from the real API — refusing")
    index = json.loads((PLANNER / "cache" / "INDEX.json").read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    files = []
    booth_commits: set[str] = set()
    for e in index:
        region, input_time = e["region_id"], e["input_time"]
        query = urllib.parse.urlencode({"input_time": input_time, "only_nonzero": "true"})
        path = f"/v1/regions/{urllib.parse.quote(region)}/forecast?{query}"
        body, ctype = get(a.api, path)
        fc = json.loads(body)
        prov = fc.get("provenance") or {}
        want = cached_packet(PLANNER / "cache" / e["path"])
        if want["booth_api_commit"]:
            booth_commits.add(want["booth_api_commit"])
        got_packet = {k: (prov.get("input_hashes") or {}).get(k) for k in PACKET_KEYS}
        checks = {
            "region": fc.get("region") == region,
            "input_time": fc.get("input_time") == input_time,
            "scenario_set_id": prov.get("scenario_set_id") == e["scenario_set_id"] == want["scenario_set_id"],
            "checkpoint": prov.get("checkpoint") == want["checkpoint"],
            "graph_id": prov.get("graph_id") == want["graph_id"],
            "packet_hashes": got_packet == want["packet"],
            "not_mock": prov.get("mock") is not True,
        }
        if not all(checks.values()):
            raise SystemExit(f"{region} {input_time}: response does not match the cached checks: {checks}")
        name = f"{region}__{compact(input_time)}.json"
        (a.out / name).write_bytes(body)
        files.append({
            "region_id": region, "input_time": input_time, "scenario_set_id": e["scenario_set_id"], "path": name,
            "request": "GET " + path, "content_type": ctype, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "cells": len(fc.get("features") or []), "input_hashes": prov.get("input_hashes"),
            "matches_cached_checks": {"cache_file": e["path"], "route_checks": want["route_checks"], **checks},
        })
        print(f"saved {name}: {len(body)} bytes, {len(fc.get('features') or [])} cells; packet = cached checks")

    head = git("rev-parse", "HEAD")
    code = {p: git("rev-parse", f"HEAD:{p}") for p in CODE_FILES}
    # the same files at the commit of the API that computed the booth cache (recorded in the cache files)
    same_as_booth = {c: all(git("rev-parse", f"{c}:{p}") == code[p] for p in CODE_FILES) for c in sorted(booth_commits)}
    out = {
        "schema": "wfg.planner.forecast-index/1",
        "description": ("Recorded c651 forecast cells (next-hour new-burn probability, validity, burning at the input "
                        "time) of every cached scenario, saved unchanged from the Route-Check API for the static demo. "
                        "A data read of recorded files: no forecast or route was computed. Values do not depend on the "
                        "host; host and generated_at in each file's provenance say where and when it was saved."),
        "generator": "planner/scripts/save_forecasts.py",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "request": "GET /v1/regions/{region}/forecast?input_time={input_time}&only_nonzero=true",
        "api": {k: health.get(k) for k in ("api_version", "package", "package_version", "kit", "kit_candidate_id", "checkpoint", "git_commit", "git_dirty")}
        | {"host": (health.get("provenance") or {}).get("host")},
        "code": {"commit": head, "dirty": bool(git("status", "--porcelain", "--untracked-files=no")), "files": code,
                 "same_files_as_booth_cache_api_commit": same_as_booth},
        "inputs": {"archive": "WFG-evaluated-routing-inputs-20261015.zip (release research-final-20261015)",
                   "archive_sha256": "d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202",
                   "fetched_with": "tools/fetch_routing_inputs.py (archive and per-file SHA-256 verified)"},
        "files": files,
    }
    (a.out / "INDEX.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {a.out / 'INDEX.json'} ({len(files)} forecasts)")


if __name__ == "__main__":
    sys.exit(main())
