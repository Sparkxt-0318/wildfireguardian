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
.PHONY: help verify verify-numbers check-forbidden check-region-literals \
	snapshot snapshot-verify \
        env-check config-hash test baseline-verify baseline-freeze all-checks \
        finals

help:
	@echo "WildfireGuardian — verification targets"
	@echo
	@echo "  make verify           NUMBERS.json re-derived from artifacts + forbidden-string scan"
	@echo "  make verify-numbers   just the NUMBERS.json re-derivation"
	@echo "  make check-forbidden  just the forbidden-string scan"
	@echo "  make check-region-literals  one region's values typed into shared text"
	@echo "  make snapshot         preserve external inputs (OSM + FIRMS manifests)"
	@echo "  make snapshot-verify  re-hash the snapshot store against MANIFEST.json"
	@echo "  make env-check        installed packages vs the pins in requirements.txt"
	@echo "  make baseline-verify  every data/processed artifact + the git-ignored"
	@echo "                        manifests, against docs/baseline_phase13.json"
	@echo "  make baseline-freeze  RE-record that baseline (deliberate)"
	@echo "  make config-hash      print the current config hash"
	@echo "  make finals           rebuild web/finals.html and record the gates"
	@echo "  make test             pytest"
	@echo "  make all-checks       everything above except snapshot"
	@echo
	@echo "PYTHON = $(PYTHON)"

# --- the headline gate -------------------------------------------------------
# Every registered number is re-derived from its artifact, then the prose is
# scanned for retired values. Either failing is a hard stop.
verify: verify-numbers check-forbidden check-region-literals
	@echo
	@echo "=== make verify: PASSED ==="

verify-numbers:
	@echo "=== NUMBERS.json <-> artifacts ==="
	@$(PYTHON) $(SCRIPTS)/verify_numbers.py

check-forbidden:
	@echo
	@echo "=== forbidden strings ==="
	@$(PYTHON) $(SCRIPTS)/check_forbidden.py

check-region-literals:
	@echo
	@echo "=== region literals in user-visible text ==="
	@$(PYTHON) $(SCRIPTS)/check_region_literals.py

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

# --- the Korean baseline -----------------------------------------------------
# `make verify` re-derives each registered number FROM its artifact, so an
# artifact and its registry entry can move TOGETHER and still agree. This is
# the check that notices. It also covers the four PROTECTED paths (which only
# run_multi_region_routing.py digests today) and the sha256 of the git-IGNORED
# fire_manifest.json, which defines the training set and would otherwise be
# changeable with no diff at all.
baseline-verify:
	@echo "=== Korean baseline <-> docs/baseline_phase13.json ==="
	@$(PYTHON) $(SCRIPTS)/freeze_baseline.py --check

baseline-freeze:
	@$(PYTHON) $(SCRIPTS)/freeze_baseline.py --freeze

config-hash:
	@$(PYTHON) -m wildfireguardian.config

# --- the finals presentation screen -----------------------------------------
# `--verify` runs the fast gates and records their real results in the screen's
# SYSTEM INTEGRITY panel. Without it the panel lists the commands and claims no
# result, which is the honest rendering of a build that checked nothing.
# The preflight exists because the failure it replaces is a 30-line traceback
# from deep inside the package import chain, and the real cause is one line:
# `python` resolved to an interpreter without the geospatial stack. That is the
# wrong thing to read on a competition morning.
finals:
	@$(PYTHON) -c "import networkx, numpy, pyproj, rasterio, PIL" 2>/dev/null \
	  || { echo "$(PYTHON) lacks the geospatial stack (networkx/pyproj/rasterio/PIL)."; \
	       echo "Use the reference environment (docs/ENVIRONMENT.md):"; \
	       echo "    conda activate wfg311 && make finals"; \
	       echo "or point this target straight at it:"; \
	       echo "    make finals PYTHON=\$$(conda run -n wfg311 which python)"; \
	       exit 1; }
	@echo "=== building web/finals.html ==="
	@$(PYTHON) $(SCRIPTS)/build_finals.py --verify
	@$(PYTHON) $(SCRIPTS)/check_screen_assets.py web/finals.html

test:
	@$(PYTHON) -m pytest -q

all-checks: verify baseline-verify snapshot-verify env-check test
	@echo
	@echo "=== all checks PASSED ==="
