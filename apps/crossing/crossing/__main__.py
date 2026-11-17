"""Command line of the crossing app (DESIGN.md sections 9 and 10).

    python -m crossing --pi ws://10.42.0.1:8770/stream [--sim-link URL --region R] [--dem file.npz]
                       [--vehicle fire_engine] [--fuel GR1]
    python -m crossing --replay <Pi record dir | research-log session dir> [--speed 1] [--loop]

--sim-link is refused with --replay (exit 2) unless --sim-link-allow-replay is given; at run time any simulated
(sim=true) data disables the sim-link too (stated in the State's simlink.blocked_reason). When the routing API has
WFG_API_LIVE_TOKEN set, put the same token in the environment variable WFG_SIM_LINK_TOKEN (or name another variable
with --sim-link-token-env); it is never taken on the command line, never logged and never written to the research log.

Serves the web UI and the State WebSocket on http://127.0.0.1:8781/ . Verdicts are ADVISORY for trained crews;
every limit is a PLACEHOLDER. A research log of the session is written to apps/crossing/records/<session>/ unless
``--no-log``.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

DEFAULT_PI = "ws://10.42.0.1:8770/stream"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m crossing", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--pi", metavar="URL", help="roof unit WebSocket (default %s)" % DEFAULT_PI)
    src.add_argument("--replay", metavar="DIR", help="replay a Pi record dir or a research-log session dir")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed factor (default 1)")
    ap.add_argument("--loop", action="store_true", help="replay in a loop")
    ap.add_argument("--sim-link", metavar="URL", help="step 9: send CLOSED/REOPENED to the routing API WebSocket "
                    "(e.g. ws://127.0.0.1:8765/v1/live/closures); off unless given")
    ap.add_argument("--region", help="routing API region id (required with --sim-link)")
    ap.add_argument("--sim-link-token-env", metavar="VAR", default=None,
                    help="environment variable holding the routing API's live token (WFG_API_LIVE_TOKEN on the API "
                    "side), offered as the subprotocol wfg-token.<token>; default WFG_SIM_LINK_TOKEN if set")
    ap.add_argument("--sim-link-allow-replay", action="store_true",
                    help="allow --sim-link with --replay or simulated (sim=true) data; such messages are tagged "
                    "origin=replay/sim, which the routing API as built refuses (VALIDATION_ERROR, nothing applied) "
                    "(off: refused)")
    ap.add_argument("--dem", metavar="NPZ", help="DEM for the road profile (crossing.terrain.Dem npz)")
    ap.add_argument("--vehicle", help="vehicle profile (vehicles.yaml), default from crossing.yaml")
    ap.add_argument("--fuel", help="fuel code (FBFM40 code such as GR1, C064_GRASS, DEFAULT)")
    ap.add_argument("--config", metavar="YAML", help="config file (default apps/crossing/crossing.yaml)")
    ap.add_argument("--baseline", metavar="JSON", help="load a radar baseline saved earlier")
    ap.add_argument("--auto-baseline", action="store_true",
                    help="capture the radar baseline automatically once stationary with no flame pixels")
    ap.add_argument("--records", metavar="DIR", help="research log root (default apps/crossing/records)")
    ap.add_argument("--no-log", action="store_true", help="do not write a research log")
    ap.add_argument("--host", default=None, help="bind address (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=None, help="port (default 8781)")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sim_link and not args.region:
        print("--sim-link needs --region", file=sys.stderr)
        return 2
    if args.sim_link and args.replay and not args.sim_link_allow_replay:
        print("--sim-link with --replay would send recorded verdicts as live road closures; refused "
              "(add --sim-link-allow-replay to send them tagged origin=replay, never applied as live state)",
              file=sys.stderr)
        return 2
    if args.sim_link_allow_replay and not args.sim_link:
        print("--sim-link-allow-replay needs --sim-link", file=sys.stderr)
        return 2
    if args.sim_link_token_env and not args.sim_link:
        print("--sim-link-token-env needs --sim-link", file=sys.stderr)
        return 2
    sim_token = None
    if args.sim_link:
        from .simlink import TOKEN_ENV, _TOKEN_RE
        var = args.sim_link_token_env or TOKEN_ENV
        sim_token = (os.environ.get(var) or "").strip() or None
        if args.sim_link_token_env and sim_token is None:
            print("--sim-link-token-env %s: that environment variable is not set" % var, file=sys.stderr)
            return 2
        if sim_token is not None and not _TOKEN_RE.match(sim_token):
            print("the sim-link token in %s must be letters, digits, '-' or '_' only (value not shown)" % var,
                  file=sys.stderr)
            return 2
    if args.speed <= 0:
        print("--speed must be > 0", file=sys.stderr)
        return 2
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn

    from .config import load_config
    from .pipeline import Pipeline, is_research_log, load_dem
    from .research_log import ResearchLog, session_name
    from .server import Runtime, create_app

    over: dict = {}
    if args.auto_baseline:
        over.setdefault("radar", {})["auto_baseline"] = True
    if args.baseline:
        over.setdefault("radar", {})["baseline_file"] = args.baseline
    if args.records:
        over.setdefault("paths", {})["records_dir"] = args.records
    if args.host:
        over.setdefault("server", {})["host"] = args.host
    if args.port:
        over.setdefault("server", {})["port"] = args.port
    cfg = load_config(args.config, over)
    pi_url = None if args.replay else (args.pi or DEFAULT_PI)
    mode = "replay" if args.replay else "live"
    source = args.replay or pi_url
    if args.replay:
        from pathlib import Path
        p = Path(args.replay)
        if not p.is_dir():
            print("replay directory not found: %s" % p, file=sys.stderr)
            return 2
        if not is_research_log(p) and not list(p.glob("*.jsonl.gz")):
            print("%s is neither a research-log session (wire.jsonl.gz) nor a Pi record dir" % p, file=sys.stderr)
            return 2

    simlink = None
    if args.sim_link:
        from .simlink import SimLinkClient
        simlink = SimLinkClient(args.sim_link, args.region, mode="replay" if args.replay else "live",
                                allow_replay=args.sim_link_allow_replay, token=sim_token)

    rlog = None
    if cfg.log.enabled and not args.no_log:
        rlog = ResearchLog(cfg.paths.records_dir, session_name("CX-replay" if args.replay else "CX"),
                           info={"mode": mode, "source": source, "config": cfg.to_dict(),
                                 "sim_link": {"url": args.sim_link, "region": args.region,
                                              "token": "set (value not recorded)" if sim_token else "not set"}
                                 if args.sim_link
                                 else None, "dem": args.dem},
                           chunk_frames=cfg.log.chunk_frames, keep_wire=cfg.log.keep_wire,
                           health_every_s=cfg.log.health_every_s)
    pipe = Pipeline(cfg, args.vehicle or cfg.vehicle, args.fuel or cfg.fuel, dem=load_dem(args.dem),
                    research_log=rlog, simlink=simlink, mode=mode, source=source or "")
    if rlog is not None:
        rlog.update_info(vehicle=pipe.vehicle.to_dict(), fuel=pipe.fuel.to_dict())
        print("research log: %s" % rlog.dir)
    runtime = Runtime(pipe, pi_url=pi_url, replay_dir=args.replay, speed=args.speed, loop=args.loop,
                      simlink_client=simlink)
    app = create_app(runtime)
    print("Crossing app (ADVISORY ONLY, placeholder limits): http://%s:%d/  source: %s"
          % (cfg.server.host, cfg.server.port, source))
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    sys.exit(main())
