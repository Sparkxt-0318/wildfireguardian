#!/usr/bin/env python
"""Serve the WildfireGuardian API. Round-3 PHASE 22.

    python scripts/run_api.py                 # 127.0.0.1:8000
    python scripts/run_api.py --port 8080

⚠ Binds to LOCALHOST by default and that is deliberate. This serves an operator
console for one machine in one room; a wider bind would put an unauthenticated
dispatch generator on whatever network the hall provides.

Start-up preloads every registered region's walk graph, hazard field and refuge
POIs, so the first request pays no load. Expect a few seconds before the port
answers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--log-level", default="warning")
    args = ap.parse_args()

    import uvicorn

    from wildfireguardian.api import create_app

    print(f"자원 사전 적재 후 http://{args.host}:{args.port} 에서 응답합니다.")
    uvicorn.run(create_app(), host=args.host, port=args.port,
                log_level=args.log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
