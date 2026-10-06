"""Support `python -m routing` alongside the compatible run.py entry point."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
