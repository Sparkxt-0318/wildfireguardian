"""One g1_panel job in its own interpreter (Mira R14 N1): run_profile.run_one imports the kit's controller and decision
modules by name, so a fresh process per job guarantees they are the job's own kit's. Prints the row as one JSON line.
  python -B run_one_job.py KIT INPUTS REGION CASE_ID OUT_DIR BUDGET_S"""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'research/harness-2026-11/F-3.4'))
import run_profile as RP  # noqa: E402

kit, inputs, region, case, out, budget = sys.argv[1:7]
row = RP.run_one(Path(kit), Path(inputs), region, case, Path(out), float(budget), 'plain', sys.executable)
print(json.dumps(row, sort_keys=True, default=str))
