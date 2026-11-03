"""Command line: generate and validate deadline explanations (wfg.explanation/1).

    python -m tools.explain_deadlines generate            # all cache files listed in planner/cache/INDEX.json
    python -m tools.explain_deadlines generate --only uiseong_andong_2025/20250323T010000Z.json
    python -m tools.explain_deadlines check               # re-validate the written files against their inputs

Inputs are never trusted by name: the cache file must match its INDEX.json sha256; the graph and every packet file must
match the hashes recorded in INPUT_FILES.json of the fetched release archive AND the ``input_hashes`` that every cached
route check, travel-only check and dispatch plan recorded at computation time (verify_cache_provenance, before any
replay). Any mismatch stops the run before the explanation file of that cache file is written (files of cache files
processed earlier in the same run are complete and stay written). So does any recorded route whose replay disagrees
with its recorded result (validate.replay_recorded_routes).

The route checks are recorded results of the evaluated host; everything else in an explanation is computed by this
tool on the machine that runs it, recorded in ``provenance.computed_on``. ``provenance.evaluated_host`` is false unless
``--evaluated-host`` is given, which is accepted only on native macOS arm64 and is meant only for a run on the evaluated
host itself (README "Recorded and computed").
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from . import SCHEMA, VERSION
from .explain import Context, explain_plan
from .labels import PlaceIndex
from .packet import Packet, sha256_file
from .plans import CacheModel
from .reach import ContactIndex
from .roads import RoadGraph
from .validate import apply_checks, kit_crosscheck, load_kit_checker, replay_recorded_routes, require_replays_clean, validate

REPO = Path(__file__).resolve().parents[2]
INPUTS_ARCHIVE_SHA256 = "d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202"
CONTACT_RULE = ("closed road segment vs closed 375 m cell rectangle, closed occupancy vs half-open phase [birth, birth+T) "
                "(present fire [0, R)), any of the members (runtime whole-road check, contact_first.py); router cell-piece "
                "sampling on HAZARD.json reported alongside (routing/core.py evaluate_occupancy)")
# the evaluated host computed planner/cache natively on macOS arm64 (planner/cache/INDEX.json "host")
EVALUATED_HOST_PLATFORM = ("Darwin", "arm64")
# provenance fields that describe one run, not the content (ignored by ``check`` and the regeneration test)
RUN_STAMPS = ("generated_at", "code_commit", "code_dirty", "computed_on")


class InputError(RuntimeError):
    pass


def host_record() -> dict:
    """Where this run computes: the same platform / machine / python fields as the API's host record (api/provenance.py),
    plus the numerical libraries the replay and the labels use."""
    import numpy
    import pyproj
    return {"platform": platform.platform(), "system": platform.system(), "machine": platform.machine(),
            "python": platform.python_version(), "numpy": numpy.__version__, "pyproj": pyproj.__version__}


def evaluated_host_flag(requested: bool, host: dict) -> bool:
    """``evaluated_host`` is true only on explicit request, and the request is refused off native macOS arm64."""
    if not requested:
        return False
    if (host["system"], host["machine"]) != EVALUATED_HOST_PLATFORM:
        raise InputError("--evaluated-host is accepted only on native macOS arm64 (this run: %s %s)" % (host["system"], host["machine"]))
    return True


def compact(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    return t.strftime("%Y%m%dT%H%M%SZ")


def git_state(repo: Path) -> dict:
    try:
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--", "tools/explain_deadlines"],
                               capture_output=True, text=True, check=True).stdout.strip() != ""
        return {"code_commit": head, "code_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"code_commit": None, "code_dirty": None}


def transformers():
    from pyproj import Transformer
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    inv = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    return (lambda lon, lat: fwd.transform(lon, lat)), (lambda x, y: inv.transform(x, y))


def input_rows(data_root: Path) -> dict:
    rows = json.loads((data_root / "INPUT_FILES.json").read_text())
    return {r["path"]: r["sha256"] for r in rows}


def check_identity(what: str, key: str, job, policy: str, *, region: str, input_time: str, sset: str, want: dict,
                   members: list) -> None:
    """One cached route check or travel-only check must have been computed on this graph and this hazard packet, for
    this scenario set, region and input time and the packet's members, from recorded fire input under ``policy``.
    ``want``: the sha256 of the graph and the packet files under their ``input_hashes`` names. The graph and hazard
    hashes are required of every job (the API records both when it accepts a job), the three ``packet/*`` hashes of
    every job with a result (recorded on completion); every recorded one must equal the file used here."""
    if not isinstance(job, dict):
        raise InputError("%s %s: not a job record" % (what, key))
    res = job.get("result") or {}
    prov = res.get("provenance") or job.get("provenance") or {}
    ih = prov.get("input_hashes") or {}
    for k, v in want.items():
        if k not in ih:
            if k in ("graph", "hazard") or res:
                raise InputError("%s %s: no %s hash recorded" % (what, key, k))
        elif ih[k] != v:
            raise InputError("%s %s: %s hash differs" % (what, key, k))
    if prov.get("scenario_set_id") != sset or prov.get("region") != region or prov.get("input_time") != input_time:
        raise InputError("%s %s: scenario set / region / input time differ" % (what, key))
    if list(prov.get("scenario_ids") or []) != members:
        raise InputError("%s %s: scenario ids differ from the packet members" % (what, key))
    if prov.get("fire_input_type") != "recorded" or prov.get("policy") != policy:
        raise InputError("%s %s: not a recorded %s-policy check" % (what, key, policy))


def verify_cache_provenance(doc: dict, region: str, input_time: str, sset: str, graph_sha: str, pk: Packet) -> dict:
    """Before anything of the cache file is used: every cached route check (policy ``full``) and every travel-only check
    (policy ``travel_only``; their routes and recorded contact flags are replayed, validate.replay_recorded_routes) must
    name this graph, this hazard packet, this scenario set, region, input time and members (``check_identity``), and every
    dispatch plan this graph, hazard and scenario set. Returns the counts verified (``provenance.hash_checks``)."""
    hz = pk.sha256
    want = {"graph": graph_sha, "hazard": hz["HAZARD.json"], "packet/REPORT.json": hz["REPORT.json"],
            "packet/NATIVE_METADATA.json": hz["NATIVE_METADATA.json"], "packet/constructed_arrays.npz": hz["constructed_arrays.npz"]}
    ident = {"region": region, "input_time": input_time, "sset": sset, "want": want, "members": pk.member_ids}
    n_rc = n_to = n_plan = 0
    for key, job in (doc.get("route_checks") or {}).items():
        check_identity("route check", key, job, "full", **ident)
        n_rc += 1
    for key, job in (doc.get("travel_only") or {}).items():
        if not isinstance(job, dict):
            continue                  # not a job record: never replayed (replay_recorded_routes) nor shown (planner cache.ts)
        check_identity("travel-only check", key, job, "travel_only", **ident)
        n_to += 1
    for job in doc.get("plans") or []:
        if not isinstance(job, dict):
            continue
        prov = (job.get("result") or {}).get("provenance") or job.get("provenance") or {}
        ih = prov.get("input_hashes") or {}
        if ih.get("graph") != graph_sha or ih.get("hazard") != hz["HAZARD.json"] or prov.get("scenario_set_id") != sset:
            raise InputError("dispatch plan %s: inputs differ" % job.get("job_id"))
        n_plan += 1
    return {"route_checks_verified": n_rc, "travel_only_verified": n_to, "dispatch_plans_verified": n_plan}


def summarise(origins: dict, replays: dict | None = None) -> dict:
    """Totals per status and reason, and ``validation``: per-origin assertion counts (applicable/passed/failed origins)
    merged with the route-level replays of the whole cache file (``replays``; unit "route")."""
    st = collections.Counter(r["status"] for r in origins.values())
    by_reason = collections.Counter(r["reason_code"] for r in origins.values())
    by_sr = collections.Counter("%s/%s" % (r["status"], r["reason_code"]) for r in origins.values())
    by_detail = collections.Counter("%s/%s" % (r["reason_code"], r.get("detail_code")) for r in origins.values())
    val = {}
    for r in origins.values():
        for k, v in (r.get("checks") or {}).items():
            d = val.setdefault(k, {"applicable": 0, "passed": 0, "failed": 0})
            d["applicable"] += 1
            d["passed" if v else "failed"] += 1
    for k, v in (replays or {}).items():
        if k in val:
            raise ValueError("validation id %s used twice" % k)
        val[k] = dict(sorted(v.items()))
    return {"origins": len(origins), "explained": st.get("explained", 0), "explained_partial": st.get("explained_partial", 0),
            "not_explainable": st.get("not_explainable", 0), "by_reason": dict(sorted(by_reason.items())),
            "by_status_reason": dict(sorted(by_sr.items())), "by_detail": dict(sorted(by_detail.items())),
            "validation": dict(sorted(val.items()))}


def generate(args) -> int:
    repo = Path(args.repo).resolve()
    cache_dir = repo / args.cache_dir
    data_root = repo / args.data_root
    out_dir = repo / args.out
    index = json.loads((cache_dir / "INDEX.json").read_text())
    entries = [e for e in index if not args.only or e["path"] in args.only]
    rows = input_rows(data_root)
    to_5179, to_lonlat = transformers()
    git = git_state(repo)
    host = host_record()
    on_evaluated_host = evaluated_host_flag(getattr(args, "evaluated_host", False), host)
    kit = None
    if not args.no_kit:
        kit = load_kit_checker()
    written = []
    for region in sorted({e["region_id"] for e in entries}):
        t0 = time.time()
        graph_rel = "graphs/%s/graph.json" % region
        graph_path = data_root / graph_rel
        graph_sha = sha256_file(graph_path)
        if rows.get(graph_rel) != graph_sha:
            raise InputError("graph %s differs from INPUT_FILES.json" % graph_rel)
        raw_graph = json.loads(graph_path.read_text())
        G = RoadGraph(raw_graph)
        KG = kit[0].Graph(raw_graph) if kit else None
        del raw_graph
        places_path = repo / "planner" / "data" / "osm" / ("%s.overpass.json" % region)
        places = PlaceIndex(places_path, to_5179) if places_path.is_file() else None
        chord_cache = {}                      # router-cell geometry per edge of this region's graph (replays)
        for e in sorted((x for x in entries if x["region_id"] == region), key=lambda x: x["input_time"]):
            cache_path = cache_dir / e["path"]
            raw = cache_path.read_bytes()
            cache_sha = __import__("hashlib").sha256(raw).hexdigest()
            if cache_sha != e["sha256"]:
                raise InputError("%s differs from its INDEX.json sha256" % e["path"])
            doc = json.loads(raw)
            del raw
            if doc.get("schema") != "wfg.planner.cache/1" or doc["region_id"] != region or \
                    doc["scenario_set_id"] != e["scenario_set_id"] or doc["input_time"] != e["input_time"]:
                raise InputError("%s: header differs from INDEX.json" % e["path"])
            tag = compact(doc["input_time"])
            packet_rel = "latest_inputs_try02/packets/%s/%s" % (region, tag)
            pk = Packet(data_root / packet_rel, G.grid)
            for name, h in pk.sha256.items():
                if rows.get("%s/%s" % (packet_rel, name)) != h:
                    raise InputError("packet file %s/%s differs from INPUT_FILES.json" % (packet_rel, name))
            if pk.member_ids != ["%s:%d" % (doc["scenario_set_id"], i) for i in range(pk.S)]:
                raise InputError("packet members are not the scenario set %s" % doc["scenario_set_id"])
            if compact(pk.time_origin) != tag:
                raise InputError("packet time origin differs from the input time")
            if pk.crs != G.crs:
                raise InputError("packet CRS %r differs from the graph CRS %r" % (pk.crs, G.crs))
            # every route check, travel-only check and plan must name this graph and packet before any of them is used
            hash_checks = verify_cache_provenance(doc, region, doc["input_time"], doc["scenario_set_id"], graph_sha, pk)
            # every recorded checked route must replay flame-free, every travel-only route must reproduce the API's
            # per-member contact flags -- otherwise the contact semantics differ and nothing is written
            replays, problems = replay_recorded_routes(G, pk, doc, int(pk.horizon), chord_cache)
            require_replays_clean(replays, problems, e["path"])
            model = CacheModel(doc)
            ctx = Context(region_id=region, input_time=doc["input_time"], scenario_set_id=doc["scenario_set_id"], graph=G,
                          packet=pk, index=ContactIndex(G, pk), places=places, model=model, to_lonlat=to_lonlat,
                          horizon=int(pk.horizon))
            KP = kit[0].Packet(data_root / packet_rel, KG) if kit else None
            origins = {}
            for oid in sorted(model.plans):
                rec, ev = explain_plan(ctx, model.plans[oid])
                checks = validate(ctx, rec, ev)
                if kit:
                    checks.update(kit_crosscheck(kit[0], KG, KP, pk, rec, ev, int(pk.horizon)))
                origins[oid] = apply_checks(rec, checks)
            out = {"schema": SCHEMA, "region_id": region, "input_time": doc["input_time"], "scenario_set_id": doc["scenario_set_id"],
                   "provenance": {"cache_file": "planner/cache/" + e["path"], "cache_sha256": cache_sha,
                                  "packet_dir": "data/routing/" + packet_rel, "packet_hashes": dict(sorted(pk.sha256.items())),
                                  "graph_sha256": graph_sha, "graph_revision": G.revision,
                                  "inputs_release": {"asset": "WFG-evaluated-routing-inputs-20261015.zip", "sha256": INPUTS_ARCHIVE_SHA256,
                                                     "fetch": "python tools/fetch_routing_inputs.py"},
                                  "places_file": "planner/data/osm/%s.overpass.json" % region if places else None,
                                  "places_sha256": sha256_file(places_path) if places else None,
                                  "places_osm_base": places.osm_base if places else None,
                                  **git, "generator": "tools/explain_deadlines %s" % VERSION,
                                  "kit_checker_sha256": kit[1] if kit else None,
                                  "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                  "computed_on": host, "evaluated_host": on_evaluated_host,
                                  "hash_checks": {**hash_checks, "hazard_vs_npz": pk.consistency},
                                  "horizon_s": int(pk.horizon), "members": pk.member_ids,
                                  "contact_rule": CONTACT_RULE, "method": "tools/explain_deadlines/README.md"},
                   "summary": summarise(origins, replays), "origins": origins}
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / ("%s__%s.json" % (region, tag))
            path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
            written.append(path)
            s = out["summary"]
            print("%s  %d origins  explained %d  partial %d  not_explainable %d  %s  validation %s  (%d B)"
                  % (path.relative_to(repo) if path.is_relative_to(repo) else path, s["origins"], s["explained"], s["explained_partial"], s["not_explainable"],
                     json.dumps(s["by_status_reason"]), json.dumps(s["validation"]), path.stat().st_size), flush=True)
        del G, KG
        print("  region %s done in %.1f s" % (region, time.time() - t0), flush=True)
    return 0


def check(args) -> int:
    """Re-run generation into ``--tmp`` and compare with the written files: every field but the run stamps
    (RUN_STAMPS: generated_at, code_commit, code_dirty, computed_on). ``evaluated_host`` is compared."""
    repo = Path(args.repo).resolve()
    out_dir = repo / args.out
    tmp = Path(args.tmp).resolve()
    sub = argparse.Namespace(**vars(args))
    sub.out = str(tmp.relative_to(repo)) if tmp.is_relative_to(repo) else str(tmp)
    if not tmp.is_relative_to(repo):
        sub.repo = str(repo)
        sub.out = str(tmp)
    generate(sub)
    bad = 0
    for f in sorted(Path(sub.out if Path(sub.out).is_absolute() else repo / sub.out).glob("*.json")):
        a = json.loads(f.read_text())
        b = json.loads((out_dir / f.name).read_text())
        hosts = [d["provenance"].get("computed_on") for d in (a, b)]
        for d in (a, b):
            for k in RUN_STAMPS:
                d["provenance"].pop(k, None)
        same = a == b
        bad += not same
        note = "" if hosts[0] == hosts[1] else "  (written on %s, checked on %s)" % (
            (hosts[1] or {}).get("platform"), (hosts[0] or {}).get("platform"))
        print("%s %s%s" % ("SAME" if same else "DIFFERENT", f.name, note))
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.explain_deadlines", description=__doc__.splitlines()[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("generate", "check"):
        p = sp.add_parser(name)
        p.add_argument("--repo", default=str(REPO))
        p.add_argument("--cache-dir", default="planner/cache")
        p.add_argument("--data-root", default="data/routing")
        p.add_argument("--out", default="planner/public/data/explanations")
        p.add_argument("--only", nargs="*", help="cache paths relative to the cache dir (as in INDEX.json)")
        p.add_argument("--no-kit", action="store_true", help="skip the kit independent-checker cross-check")
        p.add_argument("--evaluated-host", action="store_true",
                       help="mark the output as computed on the evaluated host (provenance.evaluated_host true); refused "
                            "off native macOS arm64 -- use it only on the evaluated host itself (README)")
        if name == "check":
            p.add_argument("--tmp", required=True, help="scratch directory for the regenerated files")
    a = ap.parse_args(argv)
    if a.evaluated_host:
        # refused off native macOS arm64 before anything is read or written: one line, exit status 2 (generate() itself
        # refuses as well, for callers that bypass the command line)
        try:
            evaluated_host_flag(True, host_record())
        except InputError as exc:
            print("%s: error: %s" % (ap.prog, exc), file=sys.stderr)
            return 2
    return generate(a) if a.cmd == "generate" else check(a)


if __name__ == "__main__":
    sys.exit(main())
