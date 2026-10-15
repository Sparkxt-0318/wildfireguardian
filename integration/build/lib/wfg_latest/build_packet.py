"""Build one latest-forecast regional hazard packet (wfg.latest-regional-packet/2.1) from one clock-bound export.

The inherited radiation operator is the vendored copy in radiation/ (release v4 forecast/wildfire/wildfire/heat.py,
SHA-256 f52b4c31...), loaded as the namespace package 'wildfire' WITHOUT executing any wildfire __init__, so the packet
radiation is the operator the inherited scalar checkers recompute. The emitted edge-grid is validated by the router's own
validator, vendored in router_validation/ (59fa kit routing_candidate/baseline/routing-package/routing/validation.py
ed5f2800... and admission_geometry.py 7d548dee...) and loaded as the namespace package 'routing'. Run it in its own process
(python -I -B). Usage:
  build_packet.py --graph G.json --export-dir DIR --event KFS_xx --cutoff ISO --region NAME [--window-json '{"r0":..}'] --out DIR
Writes HAZARD.json, REPORT.json, NATIVE_METADATA.json, constructed_arrays.npz and BUILD_SUMMARY.json (write-once)."""
import argparse, hashlib, json, sys, time, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
RADIATION_SHA256 = {"heat.py": "f52b4c31ba83d59c9a9b29e669c738e94d7de3b8bff723b1108ebcc11984acfb",
                    "coordinates.py": "9a9f56a60083bdb9e2990ca710280bfd75b7c004f2648d0af3d45a4f5c5a3dd3",
                    "paths.py": "37c1a19a4ff191641d2980b7bd6576a1e738b6d7cf56876677b9ad650010d6fd"}
ROUTER_VALIDATION_SHA256 = {"validation.py": "ed5f28007aec47eb0b0361fbd0a3bf704c9db5b9e7a5fc8d4dd31db63ce586a3",
                            "admission_geometry.py": "7d548dee459b7d6c8c08e227a6f32fbfb759bec99648847ef66462265956fa96"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def install_namespace(name, folder, pins):
    d = HERE / folder
    bad = {n: sha(d / n) for n in pins if sha(d / n) != pins[n]}
    if bad:
        raise SystemExit("VENDORED_IDENTITY %s %s" % (folder, bad))
    if name in sys.modules:
        raise SystemExit("%s_ALREADY_IMPORTED (run build_packet in its own process)" % name.upper())
    pkg = types.ModuleType(name); pkg.__path__ = [str(d)]; sys.modules[name] = pkg


def install_radiation():
    install_namespace("wildfire", "radiation", RADIATION_SHA256)
    install_namespace("routing", "router_validation", ROUTER_VALIDATION_SHA256)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("--graph", "--export-dir", "--event", "--cutoff", "--region", "--out"):
        ap.add_argument(k, required=True)
    ap.add_argument("--window-json", default=None)
    a = ap.parse_args(argv)
    install_radiation()
    sys.path.insert(0, str(HERE))
    import contract as CT
    import packets as P
    iso, _ = CT.normalize_cutoff(a.cutoff)
    exp = Path(a.export_dir); tag = CT.tag(iso)
    npz = exp / ("FORECAST_%s.npz" % tag); recp = exp / ("FORECAST_RECORD_%s.json" % tag)
    rec = json.loads(recp.read_text())
    graph = json.loads(Path(a.graph).read_text())
    crs = graph.get("crs", "")
    if not crs.startswith("EPSG:"):
        raise SystemExit("GRAPH_CRS_NOT_EPSG %r" % crs)
    epsg = int(crs.split(":", 1)[1])
    win = json.loads(a.window_json) if a.window_json else None
    t0 = time.perf_counter()
    out, hz, summ = P.write_regional_packet(graph, a.graph, npz, rec, sha(recp), iso, epsg, a.out,
                                            event_id=a.event, region_id=a.region, window=win)
    wall = time.perf_counter() - t0
    mods = sorted(n for n, m in sys.modules.items() if n.startswith(("wildfire", "routing")) and getattr(m, "__file__", None))
    summ.update(region=a.region, event_id=a.event, cutoff=iso, graph_file=str(a.graph), graph_sha256=sha(a.graph),
                forecast_npz_sha256=sha(npz), forecast_record_sha256=sha(recp), hazard_construction_wall_s=wall,
                source_sha256={n: sha(HERE / n) for n in ("contract.py", "bridge.py", "packets.py", "build_packet.py")},
                vendored_sha256={**{"radiation/" + n: h for n, h in RADIATION_SHA256.items()}, **{"router_validation/" + n: h for n, h in ROUTER_VALIDATION_SHA256.items()}},
                radiation_modules_loaded=mods, window=win, status="BUILT")
    with (Path(out) / "BUILD_SUMMARY.json").open("x") as f:
        json.dump(summ, f, indent=1, default=str); f.write("\n")
    print(json.dumps({k: summ.get(k) for k in ("region", "cutoff", "shape", "ignitions_per_member", "present_fire_cells",
                                                "initial_remaining_s", "max_flux_kW_m2", "hazard_construction_wall_s")}, default=str))


if __name__ == "__main__":
    main()
