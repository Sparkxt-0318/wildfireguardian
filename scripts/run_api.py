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

⚠ The port is probed BEFORE anything else. uvicorn binds only after the
lifespan preload, so a taken port used to mean: this process prints the
ready-when-loaded message, works for several seconds, then dies on bind —
while the browser quietly talks to whatever old process holds the port. That
is the stale-server trap docs/api_layer.md §1.10 records falling into during
verification. Now a taken port fails in under a second, on stderr, with the
command that shows the occupant, and the ready message is never printed.
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

    # ⚠ Probe the exact (host, port) FIRST, before the ready message and before
    # any heavy import. A bound-and-closed probe is not a perfect reservation
    # (another process could take the port in the gap), but the failure this
    # exists to catch is a server from the last rehearsal still holding the
    # port for minutes, and that one it catches every time. No SO_REUSEADDR:
    # the probe must fail exactly when uvicorn's own bind would.
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((args.host, args.port))
    except OSError as exc:
        print(f"포트를 열 수 없습니다: {args.host}:{args.port} "
              f"({exc.strerror}).", file=sys.stderr)
        print("이미 실행 중인 서버가 이 포트를 잡고 있으면, 지금 브라우저가 "
              "보는 화면은 그 옛 프로세스의 것입니다.", file=sys.stderr)
        print(f"확인: lsof -nP -iTCP:{args.port} -sTCP:LISTEN    "
              "종료 후 다시 실행하십시오.", file=sys.stderr)
        return 2
    finally:
        probe.close()

    import uvicorn

    from wildfireguardian.api import create_app

    url = f"http://{args.host}:{args.port}/"
    # ⚠ This message was previously a promise the server did not keep: it named
    # the root URL while GET / returned 404 and the console lived at
    # /console.html. The route is mapped now, and the message names the address
    # that is actually served — checked by tests/test_api.py, so the two cannot
    # drift apart again.
    print(f"자원 사전 적재 중… 완료되면 {url} 에서 운영자 콘솔이 열립니다.",
          flush=True)
    uvicorn.run(create_app(), host=args.host, port=args.port,
                log_level=args.log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
