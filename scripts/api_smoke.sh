#!/usr/bin/env bash
# End-to-end smoke check of the WildfireGuardian Route-Check API against an ALREADY RUNNING server.
#
#   make api                     # terminal 1: start the server (http://127.0.0.1:8765/v1)
#   bash scripts/api_smoke.sh    # terminal 2 (or: make api-smoke)
#
# Environment:
#   WFG_API_BASE       base URL (default http://127.0.0.1:8765/v1)
#   WFG_SMOKE_TIMEOUT  seconds to wait for each job (default 300)
#
# Steps: health, regions, one recorded route check (Hongseong FD1), one spread_zones route check, summary.
# Exit 0 when both jobs reach status "done", whatever the verdict. Exit 1 when the server is unreachable, an endpoint
# answers with an error, a job ends "failed" (API internal error) or a job does not finish in time.
# A verdict is only printed, never interpreted: "unresolved" is never safe.
set -euo pipefail

BASE="${WFG_API_BASE:-http://127.0.0.1:8765/v1}"
BASE="${BASE%/}"
TIMEOUT_S="${WFG_SMOKE_TIMEOUT:-300}"
POLL_S=2

REGION="hongseong_2023"
INPUT_TIME="2023-04-02T23:00:00Z"
START_NODE="osm:437291784"
DEST_NODE="osm:436670987"
RECORDED_ARRIVAL_S=531   # recorded final-panel arrival of Hongseong FD1 (research/routing/INDEPENDENT_ROWS.csv)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYJ="$ROOT/.venv/bin/python"; else PYJ="python3"; fi
command -v curl >/dev/null 2>&1 || { echo "error: curl is required" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
BODY="$TMP/body.json"

# req METHOD PATH [JSON] -> prints the HTTP status; the response body is left in $BODY
req() {
  local method="$1" path="$2" data="${3:-}"
  local args=(-sS -o "$BODY" -w '%{http_code}' -X "$method" -H 'Accept: application/json' --max-time 60)
  if [[ -n "$data" ]]; then
    args+=(-H 'Content-Type: application/json' --data-binary "$data")
  fi
  curl "${args[@]}" "$BASE$path"
}

# js PYTHON_EXPR_OR_STATEMENTS: runs Python with `d` bound to the parsed $BODY (stdlib json only)
js() {
  "$PYJ" -c "import json,sys
d=json.load(open(sys.argv[1], encoding='utf-8'))
$1" "$BODY"
}

fail_http() {  # fail_http WHAT CODE
  echo "  FAIL: $1 returned HTTP $2" >&2
  js 'print("  " + json.dumps(d.get("error", d), ensure_ascii=False)[:600])' >&2 || head -c 600 "$BODY" >&2
  exit 1
}

# poll JOB_ID -> waits until the route check is done or failed; leaves the job JSON in $BODY
poll() {
  local id="$1" t0=$SECONDS status code
  while :; do
    code="$(req GET "/route-checks/$id")"
    [[ "$code" == 200 ]] || fail_http "GET /route-checks/$id" "$code"
    status="$(js 'print(d["status"])')"
    case "$status" in
      done|failed) echo "  job $id: $status after $((SECONDS - t0)) s"; return 0 ;;
    esac
    if (( SECONDS - t0 >= TIMEOUT_S )); then
      echo "  FAIL: job $id still $status after ${TIMEOUT_S} s" >&2
      exit 1
    fi
    sleep "$POLL_S"
  done
}

# Prints the verdict line of the job in $BODY. Only checked_route carries a route; unresolved is never safe.
VERDICT_PY='r = d.get("result") or {}
v = r.get("verdict") or "unresolved"
note = {"checked_route": "", "model_no_route": " (scoped refusal: no route in this model, not proof that no escape exists)",
        "unresolved": " (NOT safe: no checked route and no scoped refusal)"}.get(v, "")
def f(x):
    return "null" if x is None else ("%.3f" % x if isinstance(x, float) else str(x))
print("  verdict=%s%s" % (v, note))
print("  reason_code=%s arrival_s=%s lower_bound_L_s=%s compute_s=%s within_budget=%s" % (
    f(r.get("reason_code")), f(r.get("arrival_s")), f(r.get("lower_bound_L_s")), f(r.get("compute_s")), r.get("within_budget")))
if d.get("error"):
    print("  job error: %s" % json.dumps(d["error"], ensure_ascii=False)[:400])'

# ------------------------------------------------------------------------------------------------ (a) health
echo "[1/5] GET $BASE/health"
if ! code="$(req GET /health 2>"$TMP/curl.err")"; then
  echo "  cannot connect to $BASE ($(tr -d '\n' <"$TMP/curl.err"))" >&2
  echo "  Start the server first, from the repository root:  make api   (or: .venv/bin/python -m api)" >&2
  echo "  then rerun:  bash scripts/api_smoke.sh   (set WFG_API_BASE for another address)" >&2
  exit 1
fi
[[ "$code" == 200 ]] || fail_http "GET /health" "$code"
js 'print("  status=%s package=%s %s kit=%s checkpoint=%s git_commit=%s workers=%s" % (
    d["status"], d["package"], d["package_version"], d["kit"], d["checkpoint"][:12], d["git_commit"], d.get("workers")))
print("  regions=%s" % ",".join(d["regions"]))
for i in d.get("issues") or []:
    print("  issue: %s" % i)'
if [[ "$(js 'print(len(d["regions"]))')" == 0 ]]; then
  echo "  FAIL: no regions loaded; fetch the recorded inputs with: python tools/fetch_routing_inputs.py" >&2
  exit 1
fi

# ------------------------------------------------------------------------------------------------ (b) regions
echo "[2/5] GET $BASE/regions"
code="$(req GET /regions)"
[[ "$code" == 200 ]] || fail_http "GET /regions" "$code"
js 'for r in d["regions"]:
    print("  %-20s %-6s input_times=%d scenario_sets=%d" % (r["id"], r["name_ko"], len(r["input_times"]), len(r["scenario_sets"])))'
SSET="$(js "
want = [s['scenario_set_id'] for r in d['regions'] if r['id'] == '$REGION'
        for s in r['scenario_sets'] if s['input_time'] == '$INPUT_TIME']
print(want[0] if want else '')")"
if [[ -z "$SSET" ]]; then
  echo "  FAIL: no recorded scenario set for $REGION at $INPUT_TIME" >&2
  exit 1
fi
echo "  using $REGION $INPUT_TIME scenario_set_id=$SSET"

# ------------------------------------------------------------------------------------------------ (c) recorded
echo "[3/5] POST $BASE/route-checks (recorded fire input; mission Hongseong FD1)"
REC_BODY="$(cat <<EOF
{"region": "$REGION", "input_time": "$INPUT_TIME",
 "start": {"node_id": "$START_NODE"}, "destination": {"node_id": "$DEST_NODE"},
 "destination_window": [0, 847], "dwell_s": 120,
 "fire_input": {"type": "recorded", "scenario_set_id": "$SSET"},
 "client_ref": "api_smoke recorded FD1"}
EOF
)"
code="$(req POST /route-checks "$REC_BODY")"
[[ "$code" == 202 ]] || fail_http "POST /route-checks (recorded)" "$code"
REC_ID="$(js 'print(d["job_id"])')"
echo "  accepted job_id=$REC_ID"
poll "$REC_ID"
REC_STATUS="$(js 'print(d["status"])')"
REC_VERDICT="$(js 'print((d.get("result") or {}).get("verdict") or "unresolved")')"
js "$VERDICT_PY"
js 'p = (d.get("result") or {}).get("provenance") or {}
print("  recorded_mission_match=%s evaluated_configuration=%s" % (p.get("recorded_mission_match"), p.get("evaluated_configuration")))'
echo "  recorded final-panel arrival for FD1: ${RECORDED_ARRIVAL_S} s"

# ------------------------------------------------------------------------------------------------ (d) spread_zones
echo "[4/5] POST $BASE/route-checks (spread_zones fire input: nested 5 h / 8 h zones, issued 2023-04-02T22:00:00Z)"
SZ_BODY="$(cat <<EOF
{"region": "$REGION", "input_time": "$INPUT_TIME",
 "start": {"node_id": "$START_NODE"}, "destination": {"node_id": "$DEST_NODE"},
 "destination_window": [0, 847], "dwell_s": 120,
 "fire_input": {"type": "spread_zones", "issued_at": "2023-04-02T22:00:00Z",
   "zones": {"type": "FeatureCollection", "features": [
     {"type": "Feature", "properties": {"arrival_h_max": 5},
      "geometry": {"type": "Polygon", "coordinates": [[[126.49, 36.55], [126.51, 36.55], [126.51, 36.57], [126.49, 36.57], [126.49, 36.55]]]}},
     {"type": "Feature", "properties": {"arrival_h_max": 8},
      "geometry": {"type": "Polygon", "coordinates": [[[126.48, 36.54], [126.52, 36.54], [126.52, 36.58], [126.48, 36.58], [126.48, 36.54]]]}}]}},
 "client_ref": "api_smoke spread_zones"}
EOF
)"
code="$(req POST /route-checks "$SZ_BODY")"
[[ "$code" == 202 ]] || fail_http "POST /route-checks (spread_zones)" "$code"
SZ_ID="$(js 'print(d["job_id"])')"
echo "  accepted job_id=$SZ_ID"
poll "$SZ_ID"
SZ_STATUS="$(js 'print(d["status"])')"
SZ_VERDICT="$(js 'print((d.get("result") or {}).get("verdict") or "unresolved")')"
js "$VERDICT_PY"
js 'p = (d.get("result") or {}).get("provenance") or {}
print("  provenance.approximation=%s" % json.dumps(p.get("approximation"), ensure_ascii=False))'

# ------------------------------------------------------------------------------------------------ (e) summary
echo "[5/5] summary"
echo "  recorded     $REC_ID  status=$REC_STATUS verdict=$REC_VERDICT"
echo "  spread_zones $SZ_ID  status=$SZ_STATUS verdict=$SZ_VERDICT"
if [[ "$REC_VERDICT" == unresolved || "$SZ_VERDICT" == unresolved ]]; then
  echo "  note: unresolved is never safe; it means no checked route and no scoped refusal were established."
fi
if [[ "$REC_STATUS" == done && "$SZ_STATUS" == done ]]; then
  echo "SMOKE OK: both jobs finished"
  exit 0
fi
echo "SMOKE FAILED: a job ended with status failed (API internal error)" >&2
exit 1
