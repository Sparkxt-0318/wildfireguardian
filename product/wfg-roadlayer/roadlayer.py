#!/usr/bin/env python3
"""Launcher: python3 roadlayer.py setup | run ... | example | verify ...  (same as python3 -m wfg_roadlayer)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wfg_roadlayer.cli import main  # noqa: E402

sys.exit(main())
