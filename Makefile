# WildfireGuardian Route-Check API (local only). Run from the repository root.
#   make api          set up on first use, then serve http://127.0.0.1:8765/v1 (Swagger UI at /docs)
#   make api-setup    create .venv (Python 3.12), install pinned dependencies, fetch recorded inputs if missing
#   make api-test     fast tests (no golden replays, no panel run)
#   make api-golden   recorded-mission replays
#   make api-panel    final-panel run through the API
#   make api-smoke    end-to-end smoke check against an already-running server

PY ?= .venv/bin/python
PYTHON312 ?= python3.12

.PHONY: api api-setup api-inputs api-tools api-test api-golden api-panel api-smoke

api-setup:
	@if [ ! -d .venv ]; then \
		command -v $(PYTHON312) >/dev/null 2>&1 || { echo "error: $(PYTHON312) not found; install Python 3.12 or run: make api-setup PYTHON312=/path/to/python3.12" >&2; exit 1; }; \
		echo "Creating .venv with $(PYTHON312)"; \
		$(PYTHON312) -m venv .venv; \
	fi
	$(PY) -m pip install -c constraints-routing.txt './integration[packets]' -r api/requirements.txt
	@$(MAKE) --no-print-directory api-inputs
	@$(MAKE) --no-print-directory api-tools

api-inputs:
	@if [ -d data/routing ]; then \
		echo "Recorded inputs present: data/routing"; \
	else \
		echo "Fetching recorded routing inputs into data/routing"; \
		$(PY) tools/fetch_routing_inputs.py; \
	fi

api-tools:
	@if [ ! -x /usr/bin/time ]; then \
		echo "WARNING: /usr/bin/time is missing. The kit controller needs GNU time (time -v) and every route check will fail without it." >&2; \
		echo "         Debian/Ubuntu: sudo apt-get install time   (macOS ships /usr/bin/time)" >&2; \
	fi
	@if [ ! -x /bin/ps ]; then \
		echo "WARNING: /bin/ps is missing. The kit controller needs it. Debian/Ubuntu: sudo apt-get install procps" >&2; \
	fi

api:
	@if [ ! -d .venv ]; then $(MAKE) --no-print-directory api-setup; fi
	@if [ -z "$${WFG_API_DATA_ROOT:-}" ] && [ ! -d data/routing ]; then $(MAKE) --no-print-directory api-inputs; fi
	@$(MAKE) --no-print-directory api-tools
	$(PY) -m api

api-test:
	$(PY) -m pytest tests/api -m "not golden and not panel" -rs

api-golden:
	$(PY) -m pytest tests/api -m golden -rs -s

api-panel:
	$(PY) -m pytest tests/api -m panel -rs -s

api-smoke:
	bash scripts/api_smoke.sh

# ---- Solve 2027 reviewer reproduction (docs/solve2027/REPRODUCE.md) ---------------------------------------------
#   make reproduce-linux  verify identities and frozen evidence, fetch the recorded inputs if missing, replay Uljin FX1
#                         with an EXTENDED budget (Linux reproduction, not the evaluated 30 s macOS benchmark; the
#                         same request at 30 s is reported, never asserted), then the API fast tests
#   make reproduce-uljin  only the extended-budget Uljin FX1 replay (needs the recorded inputs)
#                         Replay exit 3 = same route reproduced but the kit's 6 s stage-Z optimality proof did not
#                         finish on this host: reported as a warning, not a failure (docs/solve2027/REPRODUCE.md).
#   make docker-build     build the API and planner images (no push)
#   make docker-up        docker compose up --build: planner http://127.0.0.1:8080, API http://127.0.0.1:8765/v1
#   make docker-down      stop the containers (job records stay in the api-runtime volume)
REPRO_OUT ?= artifacts/solve2027/uljin-fx1-$(shell date -u +%Y%m%dT%H%M%SZ)
WFG_GIT_COMMIT ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)

.PHONY: reproduce-linux reproduce-uljin docker-build docker-up docker-down

REPRO_EXIT3 = echo "WARNING: replay exit 3 - same route reproduced, but the kit's 6 s stage-Z optimality proof did not finish on this host" >&2

reproduce-uljin:
	@rc=0; $(PY) docs/solve2027/reproduce/replay_uljin_fx1.py --out $(REPRO_OUT) || rc=$$?; \
	if [ $$rc -eq 3 ]; then $(REPRO_EXIT3); elif [ $$rc -ne 0 ]; then exit $$rc; fi

reproduce-linux:
	@if [ ! -d .venv ]; then $(MAKE) --no-print-directory api-setup; fi
	$(PY) tools/verify_release.py
	$(PY) tools/verify_postmerge_preservation.py
	@$(MAKE) --no-print-directory api-inputs
	@rc=0; $(PY) docs/solve2027/reproduce/replay_uljin_fx1.py --out $(REPRO_OUT) --also-evaluated-budget || rc=$$?; \
	if [ $$rc -eq 3 ]; then $(REPRO_EXIT3); elif [ $$rc -ne 0 ]; then exit $$rc; fi
	@$(MAKE) --no-print-directory api-test

docker-build:
	WFG_GIT_COMMIT=$(WFG_GIT_COMMIT) docker compose build

docker-up:
	WFG_GIT_COMMIT=$(WFG_GIT_COMMIT) docker compose up --build

docker-down:
	docker compose down
