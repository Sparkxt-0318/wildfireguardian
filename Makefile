# WildfireGuardian — verification and provenance targets.
#
# Round-3 PHASE 1-E. These targets exist because Round 2 had no way to answer
# "is this number still true?" without checking by hand.
#
# Reference environment is the conda env `wfg311` (docs/ENVIRONMENT.md).
# Override with:  make verify PYTHON=/path/to/python

PYTHON ?= python
SCRIPTS := scripts

# A pipeline's exit status is its LAST command's. Session 10 ran the gates as
# `gate | tail` inside an && chain, the shell read tail's zero, and a commit
# landed on top of a red gate. `pipefail` makes a recipe fail on the gate
# instead of on the tail of the pipe; `-e` stops the recipe at the first
# failing command. `-u` is deliberately NOT set: recipes here legitimately
# reference variables that may be empty.
SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -e -c

.DEFAULT_GOAL := help
.PHONY: help verify verify-numbers check-forbidden check-withdrawn-claims \
	check-region-literals check-readme-figures \
	snapshot snapshot-verify check-arm-isolation check-gate-invocations \
	check-arm-controls \
        env-check config-hash test baseline-verify baseline-freeze all-checks \
        finals

help:
	@echo "WildfireGuardian — verification targets"
	@echo
	@echo "  make verify           NUMBERS.json re-derived from artifacts + forbidden-string scan"
	@echo "  make verify-numbers   just the NUMBERS.json re-derivation"
	@echo "  make check-forbidden  just the forbidden-string scan"
	@echo "  make check-withdrawn-claims  every tracked doc vs docs/auto/withdrawn_claims.json"
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
verify: verify-numbers check-forbidden check-withdrawn-claims check-region-literals \
        check-arm-isolation check-gate-invocations check-arm-controls \
        check-declared-deps check-artifact-manifest check-number-collisions \
        check-readme-figures
	@echo
	@echo "=== make verify: PASSED ==="

verify-numbers:
	@echo "=== NUMBERS.json <-> artifacts ==="
	@$(PYTHON) $(SCRIPTS)/verify_numbers.py

check-forbidden:
	@echo
	@echo "=== forbidden strings ==="
	@$(PYTHON) $(SCRIPTS)/check_forbidden.py

check-withdrawn-claims:
	@echo
	@echo "=== withdrawn claims (registry, whole tree) ==="
	@$(PYTHON) $(SCRIPTS)/check_withdrawn_claims.py

check-region-literals:
	@echo
	@echo "=== region literals in user-visible text ==="
	@$(PYTHON) $(SCRIPTS)/check_region_literals.py

# --- arm isolation and gate hygiene (Session 10) -----------------------------
check-arm-isolation:
	@echo
	@echo "=== Arm A entries unchanged ==="
	@$(PYTHON) $(SCRIPTS)/check_arm_isolation.py

check-gate-invocations:
	@echo
	@echo "=== no gate piped without pipefail ==="
	@$(PYTHON) $(SCRIPTS)/check_gate_invocations.py

check-arm-controls:
	@echo
	@echo "=== every feature-count change has a matched control ==="
	@$(PYTHON) $(SCRIPTS)/check_arm_controls.py

# --- clean-clone boot (Session 18) -------------------------------------------
# Catches the failure that only appears on a laptop that has never seen this
# repo: a module imported at runtime and declared in no dependency file. Also
# scans engine=/driver= literals, because h5netcdf and h5py were reached only
# through xr.open_dataset(engine="h5netcdf") and appear in no import statement.
check-declared-deps:
	@echo
	@echo "=== every runtime import is declared ==="
	@$(PYTHON) $(SCRIPTS)/check_declared_deps.py

# Every artifact a document or NUMBERS.json cites must be IN the repository —
# tracked, or carried in docs/artifact_manifest.json with a digest and a
# regeneration command. A cited number whose artifact exists only on one laptop
# cannot be checked by anyone else.
check-artifact-manifest:
	@echo
	@echo "=== cited artifacts match the manifest ==="
	@$(PYTHON) $(SCRIPTS)/build_artifact_manifest.py --check

# A registered quantity appearing elsewhere with a DIFFERENT value and nothing
# saying which superseded which. check-forbidden holds a curated list of retired
# values; this one is registry-anchored and finds collisions nobody has curated.
check-number-collisions:
	@echo
	@echo "=== no registered quantity contradicts itself ==="
	@$(PYTHON) $(SCRIPTS)/check_number_collisions.py

# The README's opening figures (the March 2025 fire's scale) were rewritten wrongly
# twice with every gate green, because they had no key (WFG-049). Now each is a
# fire2025_* registry entry read from data/processed/external/fire_2025_scale.json,
# and this gate refuses a paragraph that omits a final figure, states an interim
# tally as final, or carries a retired value.
check-readme-figures:
	@echo
	@echo "=== README opening figures <-> registry ==="
	@$(PYTHON) $(SCRIPTS)/register_fire2025_figures.py --check
	@$(PYTHON) $(SCRIPTS)/check_readme_figures.py

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
