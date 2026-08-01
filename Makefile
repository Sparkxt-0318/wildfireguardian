# WildfireGuardian — verification and provenance targets.
#
# Round-3 PHASE 1-E. These targets exist because Round 2 had no way to answer
# "is this number still true?" without checking by hand.
#
# Reference environment is the conda env `wfg311` (docs/ENVIRONMENT.md).
# Override with:  make verify PYTHON=/path/to/python

PYTHON ?= python
SCRIPTS := scripts

.DEFAULT_GOAL := help
.PHONY: help verify verify-numbers check-forbidden snapshot snapshot-verify \
        env-check config-hash test all-checks

help:
	@echo "WildfireGuardian — verification targets"
	@echo
	@echo "  make verify           NUMBERS.json re-derived from artifacts + forbidden-string scan"
	@echo "  make verify-numbers   just the NUMBERS.json re-derivation"
	@echo "  make check-forbidden  just the forbidden-string scan"
	@echo "  make snapshot         preserve external inputs (OSM + FIRMS manifests)"
	@echo "  make snapshot-verify  re-hash the snapshot store against MANIFEST.json"
	@echo "  make env-check        installed packages vs the pins in requirements.txt"
	@echo "  make config-hash      print the current config hash"
	@echo "  make test             pytest"
	@echo "  make all-checks       everything above except snapshot"
	@echo
	@echo "PYTHON = $(PYTHON)"

# --- the headline gate -------------------------------------------------------
# Every registered number is re-derived from its artifact, then the prose is
# scanned for retired values. Either failing is a hard stop.
verify: verify-numbers check-forbidden
	@echo
	@echo "=== make verify: PASSED ==="

verify-numbers:
	@echo "=== NUMBERS.json <-> artifacts ==="
	@$(PYTHON) $(SCRIPTS)/verify_numbers.py

check-forbidden:
	@echo
	@echo "=== forbidden strings ==="
	@$(PYTHON) $(SCRIPTS)/check_forbidden.py

# --- provenance --------------------------------------------------------------
snapshot:
	@echo "=== preserving external inputs ==="
	@$(PYTHON) $(SCRIPTS)/snapshot_external.py --preset all --include-httpcache

snapshot-verify:
	@echo "=== snapshot store <-> MANIFEST.json ==="
	@$(PYTHON) $(SCRIPTS)/snapshot_external.py --verify

# --- environment -------------------------------------------------------------
# Catches the Round-2 failure mode directly: a dependency DECLARED in
# requirements.txt but absent from the environment, which turned five real-OSM
# tests into silent skips.
env-check:
	@echo "=== installed packages vs requirements.txt pins ==="
	@$(PYTHON) $(SCRIPTS)/env_check.py

config-hash:
	@$(PYTHON) -m wildfireguardian.config

test:
	@$(PYTHON) -m pytest -q

all-checks: verify snapshot-verify env-check test
	@echo
	@echo "=== all checks PASSED ==="
