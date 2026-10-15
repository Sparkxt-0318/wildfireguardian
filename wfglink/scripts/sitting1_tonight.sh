#!/usr/bin/env bash
# Tonight: built-in Mac camera + iPhone screen, no new camera or LED rig.
# Run from wfglink/: ./scripts/sitting1_tonight.sh
# Fresh report.txt, combined report.json and an isolated tonight.yaml per run.
set -u
cd "$(dirname "$0")/.." || exit 1
BASE="$(pwd)/results/runs/sitting1"
mkdir -p "$BASE" || exit 1
OUT="$(mktemp -d "$BASE/$(date '+%Y%m%d-%H%M%S')-XXXXXX")" || exit 1
REPORT="$OUT/report.txt"
STEPS="$OUT/steps.tsv"
CFG="$OUT/tonight.yaml"
PY=".venv/bin/python"
SERVER=""
INTERRUPTED=0
FAILED=0
SKIPPED=0
: >"$STEPS"
printf '{"status":"INCOMPLETE","steps":[]}\n' >"$OUT/report.json"
say() { printf '\n== %s\n' "$*"; }
log() { printf '%s\n' "$*" | tee -a "$REPORT"; }
wait_enter() {
  printf '\n%s\nPress Enter to start (or type s and Enter to skip): ' "$1"
  local ans
  read -r ans && [[ "$ans" != "s" ]]
}
record_step() {
  local name="$1" status="$2" rc="$3" command="$4"
  printf '%s\t%s\t%s\t%s\n' "$name" "$status" "$rc" "$command" >>"$STEPS"
  log "$name: $status (exit $rc)"
  [[ "$status" != "FAIL" ]] || FAILED=1
  [[ "$status" != "SKIPPED" ]] || SKIPPED=1
}
skip() { record_step "$1" SKIPPED - "user skipped or prerequisite unavailable"; }
run_step() {
  local name="$1"; shift
  local command rc
  printf -v command '%q ' "$@"
  "$@" 2>&1 | tee "$OUT/$name.txt"
  rc=${PIPESTATUS[0]}
  if (( rc == 0 )); then record_step "$name" OK "$rc" "$command";
  else record_step "$name" FAIL "$rc" "$command"; fi
  return "$rc"
}
check_live() {
  run_step "${1}_report" "$PY" - "$OUT/$1.json" "$1" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    r = json.load(f)
errors = r.get("error_count", r.get("errors", 0))
if errors or not r.get("frames") or not r.get("paints"):
    raise SystemExit(f"No healthy analysed/painted frames, or app errors: {errors!r}; inspect the app report.")
if sys.argv[2] == "fire" and not (r.get("states") or {}).get("playing"):
    raise SystemExit("The approved fire clip did not play; synthetic fallback does not pass this check.")
if sys.argv[2] == "ember" and r.get("camera_state") != "ok":
    raise SystemExit(f"Ember camera is {r.get('camera_state')!r}, not ok; inspect permission and camera output.")
print("App report: frames painted and analysed, no app errors, requested source available.")
PY
}
note() {
  local name="$1" prompt="$2" ans
  printf '%s ' "$prompt"
  read -r ans || ans="not answered"
  printf '%s\n' "$ans" >"$OUT/$name.note"
  log "$name, your note: $ans"
}
finish() {
  local rc="$1"
  if [[ -n "$SERVER" ]]; then kill "$SERVER" 2>/dev/null || true; wait "$SERVER" 2>/dev/null || true; fi
  # Standard library only, so dependency-install failures can still be reported.
  local report_py="$PY"
  if [[ ! -x "$report_py" ]]; then report_py="$(command -v python3.12 || command -v python3 || true)"; fi
  if [[ -n "$report_py" ]]; then
    "$report_py" - "$OUT" "$rc" "$INTERRUPTED" <<'PY'
import datetime, json, pathlib, sys
out = pathlib.Path(sys.argv[1])
steps = []
for line in (out / "steps.tsv").read_text().splitlines():
    name, status, code, command = line.split("\t", 3)
    step = {"name": name, "status": status, "exit_code": None if code == "-" else int(code), "command": command}
    path = out / f"{name}.txt"
    if path.exists():
        step["output"] = path.read_text(errors="replace")
    steps.append(step)
status = ("INTERRUPTED" if sys.argv[3] == "1" else "FAIL" if any(s["status"] == "FAIL" for s in steps)
          else "INCOMPLETE" if int(sys.argv[2]) or any(s["status"] == "SKIPPED" for s in steps) else "COMPLETED")
report = {"status": status, "scope": "Tonight smoke check; camera and accuracy validation require human review.",
          "finished_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
          "run_dir": str(out), "tonight_config": str(out / "tonight.yaml"), "steps": steps,
          "observations": {p.stem: p.read_text().strip() for p in out.glob("*.note")}}
for name in ("fire", "ember"):
    p = out / f"{name}.json"
    if p.exists():
        try:
            report[name] = json.loads(p.read_text())
        except (OSError, ValueError) as exc:
            report[name] = {"report_error": str(exc)}
(out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
with (out / "report.txt").open("a") as f:
    f.write(f"\nTonight status: {status}. This is a smoke check, not accuracy validation.\n")
    for name in ("doctor", "cameras", "calibrate"):
        p = out / f"{name}.txt"
        if p.exists():
            f.write(f"\n{name}:\n{p.read_text(errors='replace')}\n")
    for step in steps:
        if step["status"] == "FAIL" and step["name"] not in ("doctor", "cameras", "calibrate"):
            tail = "\n".join(step.get("output", "").splitlines()[-15:])
            f.write(f"\n{step['name']} failure (last lines):\n{tail}\n")
    for name in ("fire", "ember"):
        r = report.get(name)
        if isinstance(r, dict):
            f.write(f"{name} app report: " + json.dumps({k: r.get(k) for k in ("frames", "paints", "errors", "camera_state", "last")}, ensure_ascii=False) + "\n")
PY
  fi
  printf '\nPaste this report back: %s\nCombined JSON: %s/report.json\n\n' "$REPORT" "$OUT"
  cat "$REPORT"
}
trap 'INTERRUPTED=1; exit 130' INT TERM
trap 'finish "$?"' EXIT

log "wfglink sitting 1 tonight $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M %z')"
log "commit $(git -C .. rev-parse --short HEAD 2>/dev/null); host $(uname -s) $(uname -m)"
log "fresh run: $OUT"
log "Existing configs/booth_local.yaml is preserved. Tonight uses its own explicit override."

say "1 setup"
if wait_enter "Install dependencies and approved clips. If macOS asks for camera permission, click Allow."; then
  run_step setup ./scripts/setup_mac.sh || true
else skip setup; fi
[[ -x "$PY" ]] || { log "No .venv: setup did not finish. Fix the setup error and rerun this script."; exit 1; }

say "2 doctor"
run_step doctor "$PY" -m wfglink doctor || true
log "Doctor checks the normal booth settings. The following camera checks use tonight's built-in override."

say "3 built-in camera"
if run_step camera_selection "$PY" - "$CFG" <<'PY'
import json, pathlib, sys
from wfglink.io.camera import list_cameras
name = next((d["name"] for d in list_cameras() if d.get("usable") and d.get("kind") == "builtin"), None)
if name is None:
    raise SystemExit("No built-in camera found. Check permission and rerun setup. No USB or iPhone camera is substituted.")
cfg = {"camera": {"name": name, "focal_px": None, "mask": []},
       "ember": {"distance_m": 2.0, "calibration": None}, "booth": {"ember_page_url": ""}}
pathlib.Path(sys.argv[1]).write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
print(f"Tonight selects built-in camera: {name}")
print("Previous calibration and camera masks are disabled only in this isolated override.")
PY
then
  run_step cameras "$PY" -m wfglink cameras --request --open 3 --config "$CFG" || true
else skip cameras; fi

say "4 fire mode"
if wait_enter "C5 (approved NIST clip), 60 s. Press A twice (raw/analysed), L twice. Esc twice quits early. Check trails and counters."; then
  run_step fire "$PY" -m wfglink live --clip data/clips/C5_nist_emberometer.yaml --duration 60 --report "$OUT/fire.json" || true
  check_live fire || true
  note fire "Did fire mode look right? (y/n and details):"
else skip fire; fi

say "5 phone page and ember mode"
if [[ -s "$CFG" ]] && wait_enter "Use the same Wi-Fi on Mac and iPhone. The local address and QR appear next; allow incoming connections if macOS asks."; then
  "$PY" -u scripts/serve_page.py >"$OUT/page_server.txt" 2>&1 &
  SERVER=$!
  for _ in {1..50}; do
    grep -q '^Ctrl-C to stop' "$OUT/page_server.txt" && break
    kill -0 "$SERVER" 2>/dev/null || break
    sleep 0.1
  done
  cat "$OUT/page_server.txt"
  URL="$(sed -n 's/^Ember page: //p' "$OUT/page_server.txt" | head -1)"
  if kill -0 "$SERVER" 2>/dev/null && [[ -n "$URL" ]] && [[ "$URL" != *127.0.0.1* ]]; then
    record_step page_server OK 0 "python -u scripts/serve_page.py"
    log "Phone page (local Wi-Fi only): $URL"
    if run_step page_config "$PY" - "$CFG" "$URL" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); cfg = json.loads(p.read_text())
cfg["booth"]["ember_page_url"] = sys.argv[2]
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
PY
    then
    note page "Scan/open the address on iPhone, brightness max, Low Power Mode off, tap once. Does it glow? (y/n):"
    if wait_enter "60 s ember mode: stand 2.0 m from built-in camera. Move slowly/quickly, hold still, turn away. Turn camera video effects off in menu bar."; then
      run_step ember "$PY" -m wfglink live --ember --duration 60 --report "$OUT/ember.json" --config "$CFG" || true
      check_live ember || true
      note ember "ID/trail/speed visible? False lamps/windows? (details):"
    else skip ember; fi
    else skip ember; fi
  else
    record_step page_server FAIL 1 "python -u scripts/serve_page.py"
    log "Server did not start or no LAN address. Check Wi-Fi; port 8000 may be busy. See page_server.txt."
    skip ember
  fi
else skip page_server; skip ember; fi

say "6 A4 calibration"
if [[ -s "$CFG" ]] && wait_enter "Print booth/ember/calibration_target_A4.pdf on A4 at 100% (not Fit). Its 100 mm line must measure 100 mm. Hold flat with all markers visible, centre 2.0 m from lens. Saves ONLY tonight.yaml."; then
  note print "Measured length of the 100 mm print line in mm:"
  if run_step print_scale "$PY" - "$OUT/print.note" <<'PY'
import pathlib, sys
text = pathlib.Path(sys.argv[1]).read_text().strip().lower().removesuffix("mm").strip()
try:
    correct = float(text) == 100.0
except ValueError:
    correct = False
if not correct:
    raise SystemExit("Print scale not confirmed as 100 mm. Reprint at actual size and check again.")
print("100 mm print scale confirmed by the user.")
PY
  then
    run_step calibrate "$PY" -m wfglink calibrate --distance-m 2.0 --out "$CFG" --config "$CFG" || true
  else
    log "Print scale not confirmed as 100 mm. Reprint/check before calibration."
    skip calibrate
  fi
else skip calibrate; fi

log "To reuse tonight's camera/calibration: $PY -m wfglink live --ember --config \"$CFG\""
log "Phone page stops when script ends. Restart with: $PY -u scripts/serve_page.py"
(( FAILED == 0 && SKIPPED == 0 )) || exit 1
