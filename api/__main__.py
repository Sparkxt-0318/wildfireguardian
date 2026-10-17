"""Run the Route-Check API locally: python -m api  (http://127.0.0.1:8765/v1, docs at /docs)."""
import sys

import uvicorn

from .config import load_settings


def main():
    s = load_settings()
    if s.host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: WFG_API_HOST=%s is not a loopback address. The API has no authentication and is meant for local "
              "use only; anyone who can reach this address can submit jobs." % s.host, file=sys.stderr)
    uvicorn.run("api.app:app", host=s.host, port=s.port, log_level="info", workers=1)


if __name__ == "__main__":
    main()
