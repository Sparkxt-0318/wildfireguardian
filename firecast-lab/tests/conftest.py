"""Shared test setup. All arrays built in tests are SYNTHETIC unless a test reads repo metadata."""
import sys

# Importing `wildfire` must not write __pycache__ into the frozen forecast/ package.
sys.dont_write_bytecode = True
