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
