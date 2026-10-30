"""Retain exact current-run verification logs and source identities."""
from pathlib import Path
import hashlib
import json
import re
import shutil

REPO = Path(__file__).resolve().parents[3]
WORK = REPO.parent
DESTINATION = REPO / "research/forecast-v2/validation"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    names = ["1b-full-forecast-tests.log", "1b-full-forecast-tests-stable.log", "1b-full-forecast-tests-final.log",
             "1b-final-targeted-tests.log", "1b-support-repair-tests.log", "1b-utc-cutoff-test.log",
             "1b-blind-tool-tests.log", "1b-protocol-baseline-tests.log", "1b-blind-tool-tests-v2.log", "1b-cli-default-tests.log",
             "1b-wind-membership-coverage-tests.log", "1b-full-wind-membership.log"]
    DESTINATION.mkdir(exist_ok=True)
    rows = []
    for name in names:
        source = WORK / name
        if not source.exists():
            continue
        target = DESTINATION / name
        shutil.copyfile(source, target)
        text = target.read_text(errors="replace")
        summary = re.findall(r"[^\n]*(?:\d+ passed|\d+ failed)[^\n]*", text)
        rows.append(dict(file=str(target.relative_to(REPO)), sha256=digest(target), summary=summary[-1] if summary else None,
            interpretation="Initial custody failure retained separately" if name == names[0] else "Verification log"))
    source = {str(p.relative_to(REPO)): digest(p) for p in (REPO / "forecast/wildfire").rglob("*")
              if p.is_file() and p.suffix in (".py", ".json")}
    result = dict(logs=rows, current_forecast_source_sha256=source,
        full_suite_command="PYTHONPATH=forecast PYTHONUNBUFFERED=1 ../venv-forecast/bin/python -m pytest forecast/tests -q",
        source_capture_scope="Current source at log packaging; this capture is not a new test execution",
        initial_failure="Source-custody check overlapped a source edit; the first log remains preserved, then stable and final full reruns passed",
        evidence_boundary="Mechanism fixtures and regression checks, separate from real study-quality scores")
    (DESTINATION / "MANIFEST.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(logs=len(rows), destination=str(DESTINATION))))


if __name__ == "__main__":
    main()
