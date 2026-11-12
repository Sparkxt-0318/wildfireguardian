# F-3.2 primal-dual certificates for the contact-relaxation router (work in progress)

- `CERTIFICATE_SPEC.md` — certificate definition, soundness argument, scope boundary (under review).
- `FORMAT.md` — `.wfgc` bundle format (integers and keywords only).
- `generate.py` — solver side: SIPP answer + exact truncated forward-reachable interval sets.
- `check_py.py` — checker 1 (Python, stdlib only, no solver imports).
- `checker_c/` — checker 2 (C99, integer only), written independently from the spec only.
- `cases.py`, `run_panel.py` — the 20 Korean native-panel missions on the frozen inputs (`tools/fetch_routing_inputs.py`).

Reproduce (from repository root, after `python3 tools/fetch_routing_inputs.py`; needs numpy):

```sh
export PYTHONPATH=experimental/sipp-routing/src:experimental/scenario-members/src:experimental/synthetic-truth/src
python3 research/harness-2026-11/F-3.2/run_panel.py --out /tmp/f32-panel
```

Bundles (0.06–7 MB each) are written outside git; `results/` holds the summaries.
