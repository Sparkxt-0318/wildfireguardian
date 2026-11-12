"""Write FREEZE.json, stage 1 (A1 §9): the frozen identity of A1, the harness, the cohorts and every
pinned external file. It is run from a clean checkout and refuses on any pin mismatch.

External pins are checked by reading the file at its commit (`git show COMMIT:PATH`) and hashing
it, so a pin never relies on a hash copied by hand. Stage 2 (inputs, checkpoints, D2 wrappers,
rate-mixture form, part-c manifests) is added by amendment before part c opens; the list of what
it must contain is written here.

  python freeze/make_freeze.py --out FREEZE.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]          # research/harness-2026-11/S-D9
REPO = HERE.parents[2]

LOCAL_GLOBS = ["PREREGISTRATION_ADDENDUM.md", "INVENTORY.md", "README.md", "requirements.txt",
               "sd9bench/*.py", "tests/*.py", "ledger/*", "cohort/*.py", "cohort/*.csv", "cohort/*.md",
               "derive/*.py", "derive/*.json", "derive/*.md", "external/*.md"]

# (label, commit, repo path, expected sha256). Commit None = the file at this checkout's HEAD.
EXTERNAL = [
    ("forecast-v2 pipeline (unchanged)", None, "research/forecast-v2/scripts/pipeline.py",
     "88d376d2"),
    ("forecast-v2 RUN_PROTOCOL", None, "research/forecast-v2/RUN_PROTOCOL.json", "c2dce7f7"),
    ("forecast/wildfire prepare.py", None, "forecast/wildfire/prepare.py", "e2c70433"),
    ("forecast/wildfire train.py", None, "forecast/wildfire/train.py", "9c8a6215"),
    ("forecast/wildfire data.py", None, "forecast/wildfire/data.py", "8fb447ab"),
    ("forecast/wildfire search.py", None, "forecast/wildfire/search.py", "136442fa"),
    ("forecast/wildfire baselines.py", None, "forecast/wildfire/baselines.py", "325abbe7"),
    ("forecast/wildfire survival.py", None, "forecast/wildfire/survival.py", "c70db8ad"),
    ("S-D1 rebuilt-pipeline wrapper (§3.1)", "6dcf3f9d0dc3615bd14bef7d8780e3365e6513b7",
     "research/harness-2026-11/s-d1/refit/run_pipeline_rebuilt.py", "264deaea"),
    ("S-D1 refit receipt addendum writer (§4.1 rule 3)", "ab7a1f77b893c9497224f56bc0edb90860dd381f",
     "research/harness-2026-11/s-d1/refit/write_receipt_addendum.py", "54b0f957"),
    ("S-D1 c651 recipe wrapper (§3.2, item 26)", "81dc7c2ea76046d835f45805439630dc407842fd",
     "research/harness-2026-11/s-d1/refit/run_c651_recipe.py", "3e99f479"),
    ("S-D1 c651 recipe smoke test", "81dc7c2ea76046d835f45805439630dc407842fd",
     "research/harness-2026-11/s-d1/refit/smoke_c651_recipe.py", "56f7fbee"),
    ("S-D1 c651 sampling gate (§3.2)", "03b55002d9c488adfdd6eb350e2f2b631b2ad7a0",
     "research/harness-2026-11/s-d1/refit/c651_sampling_gate.py", "153bf393"),
    ("Daniel arrival-vs-union check (§4.1 rule 5)", "f5342c29d44a1ca1faf5e4448502f91300694c40",
     "research/harness-2026-11/data-fetch-3/arrival_vs_union/arrival_vs_union.py", "c847e3df"),
    ("Daniel arrival-vs-union output", "f5342c29d44a1ca1faf5e4448502f91300694c40",
     "research/harness-2026-11/data-fetch-3/arrival_vs_union/arrival_vs_union.csv", "32dd3982"),
    ("Daniel KR smoke check (KFS_02, KFS_03)", "3b2c2fbb920a255052fa5c08eeb2d0bdc7a6bb16",
     "research/harness-2026-11/data-fetch-3/kr_smoke/kr_check.py", "d3683886"),
    ("Daniel KR non-weather check (13 events)", "dd154036bad4b43f4d2e23157a2f1b13f7888239",
     "research/harness-2026-11/data-fetch-3/kr_nonweather_13/kr_check_all.py", "8099d39a"),
    ("events.json used for the c651 data root", "8d50f2e294f36e6a29a86d1b859cd4f02514ba3b",
     "forecast/data/environment/events.json", "607f831e"),
]

STAGE2_REQUIRED = [
    "rebuilt input manifest: data root layout, every input file sha256, rebuild_env.sh commit (Daniel)",
    "refit checkpoints and receipts: d4_wind_rebuilt, logistic_rebuilt, d4_wind_recal, c651 arms on/off "
    "(with REFIT_RECEIPT_ADDENDUM bound to each wrapper receipt)",
    "D2 wrapper shas: d2_nll_rebuilt, d2_bracket_rebuilt (Elena), recorded before each runs",
    "rate-mixture final form, if adopted by amendment",
    "§5.2 native cumulative marginals demonstrated on R for each D1/D2 candidate",
    "part-c manifests (incident list, perimeters by hash) verified before part c opens (§9)",
    "item 14 temperature and wind channels (AlderCreek, after rebuilt weather)",
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True).stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if git("status", "--porcelain", "--", str(HERE)).strip():
        raise SystemExit("refusing: uncommitted changes under S-D9; freeze from a clean checkout")
    local = {}
    for pattern in LOCAL_GLOBS:
        for f in sorted(HERE.glob(pattern)):
            if f.is_file() and f.name != "FREEZE.json":
                local[str(f.relative_to(HERE))] = sha(f.read_bytes())
    external = []
    for label, commit, path, prefix in EXTERNAL:
        data = git("show", f"{commit or 'HEAD'}:{path}")
        h = sha(data)
        if not h.startswith(prefix):
            raise SystemExit(f"pin mismatch for {label}: {h[:12]} does not start with {prefix}")
        external.append(dict(label=label, commit=commit or git("rev-parse", "HEAD").decode().strip(),
                             path=path, sha256=h))
    out = dict(
        schema="S-D9 FREEZE stage 1",
        status="STAGE 1 (A1 text, harness, cohorts and code pins). Not in force until Hannah verifies this "
               "commit and Iris re-assesses A1 (A1 §9). Stage 2 is added by amendment before part c opens.",
        frozen_from_commit_parent=git("rev-parse", "HEAD").decode().strip(),
        a1_sha256=local["PREREGISTRATION_ADDENDUM.md"],
        local_files=local, external_pins=external, stage2_required_before_part_c_opens=STAGE2_REQUIRED,
        sealed=dict(parts=["b", "c", "d"], h_test=["Windy", "SCU Lightning Complex", "Dolan", "Walker",
                                                   "W-5 Cold Springs", "Kincade", "McFarland"],
                    note="no perimeter of a sealed incident has been opened (ledger/ACCESS_CONTROL.md)"),
    )
    args.out.write_text(json.dumps(out, indent=1, sort_keys=False) + "\n")
    print(f"wrote {args.out}: {len(local)} local files, {len(external)} external pins, A1 {out['a1_sha256'][:12]}")


if __name__ == "__main__":
    main()
