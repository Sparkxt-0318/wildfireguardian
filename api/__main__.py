"""Run the Route-Check API locally: python -m api  (http://127.0.0.1:8765/v1, docs at /docs)."""
import uvicorn

from .config import load_settings


def main():
    s = load_settings()
    uvicorn.run("api.app:app", host=s.host, port=s.port, log_level="info", workers=1)


if __name__ == "__main__":
    main()
