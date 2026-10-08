#!/usr/bin/env python3
"""Compatibility entry point for the routing JSON CLI."""
from routing.checks import PACKAGE_ROOT as ROOT, check
from routing.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
