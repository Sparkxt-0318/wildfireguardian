#!/usr/bin/env bash
# Full local verification: build, unit tests, A4 render of saved examples, offline viewer
# e2e, contract-fixture integration run, planner-tag probe. Writes qa/verify_log.txt.
set -uo pipefail
cd "$(dirname "$0")/.."
LOG=qa/verify_log.txt; mkdir -p qa; : > "$LOG"
fail=0
step() { echo "== $1" | tee -a "$LOG"; shift; if "$@" >>"$LOG" 2>&1; then echo "   PASS" | tee -a "$LOG"; else echo "   FAIL" | tee -a "$LOG"; fail=1; fi; }
step "build viewer + examples"            node tools/build.js
step "unit tests (node --test)"           node --test tests/core.test.js
step "render examples to A4 PDF/PNG"      node tools/render_examples.js
step "offline viewer e2e (Playwright)"    node tests/viewer.e2e.js
for c in delayed_vehicle unknown_input destination_pending; do
  step "integration: contract fixture $c" node tools/integrate.js --baseline fixtures/$c/baseline.json --revised fixtures/$c/revised.json --meta fixtures/$c/briefing_meta.json
done
Q=qa/planner-4169ccc/inputs
step "planner 4169ccc: demo pair + briefing meta (expect accept)" node tools/integrate.js --baseline $Q/demo_two_vehicle.result.json --revised $Q/demo_two_vehicle_v2plus600.result.json --meta $Q/demo_briefing_meta.json --out qa/planner-4169ccc/demo_pair_with_meta
step "planner 4169ccc: demo pair, no meta (expect accept)" node tools/integrate.js --baseline $Q/demo_two_vehicle.result.json --revised $Q/demo_two_vehicle_v2plus600.result.json --out qa/planner-4169ccc/demo_pair_no_meta
step "planner 4169ccc: shuttle sample (expect accept)" node tools/integrate.js --baseline $Q/sample_result_shuttle.json --out qa/planner-4169ccc/shuttle_single
step "planner 4169ccc: missing-input sample (expect accept)" node tools/integrate.js --baseline $Q/sample_result_missing_input.json --out qa/planner-4169ccc/missing_input_single
step "planner 4169ccc: contract normal vs delayed (expect REJECT: different case_id)" bash -c "! node tools/integrate.js --baseline $Q/contract_normal.result.json --revised $Q/sample_result_parallel_delayed.json --out qa/planner-4169ccc/contract_pair --no-pdf"
step "every saved A4 PDF (examples + integration runs) is one page" node -e "
const fs=require('fs'),path=require('path');let bad=[],n=0;
const r=require('./examples/RENDER_REPORT.json');r.pages.forEach(p=>{n++;if(p.pdf_pages!==1)bad.push(p.pdf)});
(function walk(d){for(const f of fs.readdirSync(d)){const q=path.join(d,f);if(fs.statSync(q).isDirectory())walk(q);else if(f==='integration_report.json'){const j=JSON.parse(fs.readFileSync(q));if(j.pdf&&j.pdf.county)for(const v of ['county','facility']){n++;if(j.pdf[v].pages!==1)bad.push(q+':'+v)}}}})('qa');
console.log(n+' PDFs checked');if(bad.length){console.log('NOT ONE PAGE:',bad);process.exit(1)}"
echo "== planner ready tag probe" | tee -a "$LOG"
tools/check_planner_tag.sh 2>&1 | tee -a "$LOG"; echo "   (exit ${PIPESTATUS[0]}; 3 = tag absent, informational)" | tee -a "$LOG"
[ $fail -eq 0 ] && echo "ALL PASS" | tee -a "$LOG" || echo "SOME FAILED — see $LOG" | tee -a "$LOG"
exit $fail
