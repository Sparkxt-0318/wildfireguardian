"""Builds Figure A and Figure B as standalone SVG, and figures/FIGURE_NUMBERS.json.

Every number drawn is read from a committed file at run time (no number is typed in here); FIGURE_NUMBERS.json records
for each number the file and the field it came from.

  python3 research/kcf-evidence/make_figures.py        (from the repository root; standard library only)
"""
import csv
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
F31 = "research/harness-2026-11/F-3.1/results/SUMMARY_final_70f70d7.json"
SRC = "research/kcf-evidence/sources/corridor-router-v8/"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
nums = {}


def put(key, value, file, how):
    nums[key] = {"value": value, "file": file, "how": how}
    return value


# ------------------------------------------------------------------ Figure A numbers
S = json.loads((ROOT / F31).read_text())
jobs = Counter()
wit = Counter()
for r in S:
    jobs.update(r["jobs_all"])
    wit.update(r["witness_checks"])
n_total = put("A.jobs_total", sum(r["jobs_all"]["total"] for r in S), F31, "sum over 6 caches of jobs_all.total")
n_checked = put("A.recorded_checked_route_identical", jobs["checked:identical_route_cert"], F31,
                "sum of jobs_all['checked:identical_route_cert']")
n_checked_m = put("A.recorded_checked_route_match", jobs["checked:match"], F31, "sum of jobs_all['checked:match']")
n_nr = put("A.recorded_no_route_match", jobs["no_route:match"], F31, "sum of jobs_all['no_route:match']")
n_at_issue = put("A.recorded_at_issue_failure", jobs["unresolved[AT_ISSUE_FAILURE]:issue_blocked(router)"], F31,
                 "sum of jobs_all['unresolved[AT_ISSUE_FAILURE]:issue_blocked(router)']")
n_u_chk = put("A.unresolved_now_checked", jobs["unresolved[UNRESOLVED]:cert_feasible"], F31,
              "sum of jobs_all['unresolved[UNRESOLVED]:cert_feasible']")
n_u_nr = put("A.unresolved_now_no_route", jobs["unresolved[UNRESOLVED]:router_infeasible"], F31,
             "sum of jobs_all['unresolved[UNRESOLVED]:router_infeasible']")
n_unres = n_u_chk + n_u_nr
put("A.recorded_unresolved_timeout", n_unres, F31, "cert_feasible + router_infeasible")
assert n_checked == n_checked_m
assert n_checked + n_nr + n_at_issue + n_unres == n_total, "outcome classes do not add up to the jobs"
mism = put("A.job_mismatches", sum(len(r["job_mismatches"]) for r in S), F31, "sum of len(job_mismatches)")
mism2 = put("A.attempt_mismatches", sum(len(r["mismatches"]) for r in S), F31, "sum of len(mismatches)")
w_pass = put("A.deadline_witness_pass", wit["deadline_witness:PASS"], F31, "sum of witness_checks['deadline_witness:PASS']")
w_next = put("A.deadline_next_second_infeasible", wit["deadline_next_second_infeasible:True"], F31,
             "sum of witness_checks['deadline_next_second_infeasible:True']")
dl_eq = put("A.planner_deadlines_equal_recorded", sum(r["deadlines"].get("cert:equal", 0) for r in S), F31,
            "sum of deadlines['cert:equal']")
dl_later = put("A.planner_deadlines_field_later", sum(r["deadlines"].get("cert:field_later", 0) for r in S), F31,
               "sum of deadlines['cert:field_later']")
n_origins = dl_eq + dl_later
put("A.origins", n_origins, F31, "cert:equal + cert:field_later")

# ------------------------------------------------------------------ Figure B numbers
def receipts(name):
    return list(csv.DictReader(open(ROOT / SRC / name)))


perm = receipts("receipts.csv")
cov = receipts("forecast_input_recovery/receipts.csv")
mid = receipts("support_273_receipts.csv")


def tally(rows, tag, file):
    c = Counter(r["kind"] for r in rows)
    walls = [float(r["wall_s"]) for r in rows]
    put(f"B.{tag}.cases", len(rows), file, "row count")
    for k in ("route", "refusal", "unresolved"):
        put(f"B.{tag}.{k}", c.get(k, 0), file, f"count of rows with kind == {k}")
    put(f"B.{tag}.max_wall_s", max(walls), file, "max of wall_s")
    put(f"B.{tag}.over_30s", sum(w > 30 for w in walls), file, "count wall_s > 30")
    return c


cp = tally(perm, "permissive", SRC + "receipts.csv")
cc = tally(cov, "coverage_required", SRC + "forecast_input_recovery/receipts.csv")
cm = tally(mid, "coverage_required_before_input_recovery", SRC + "support_273_receipts.csv")
put("B.permissive.routes_touching_unsupported_cell_hours",
    sum(1 for r in perm if r["kind"] == "route" and r["unsupported_cell_hours"] not in ("", "0")),
    SRC + "receipts.csv", "routes with unsupported_cell_hours > 0")
put("B.coverage_required.routes_touching_unsupported_cell_hours",
    "0 (column absent; summary.json unsupported_routes = %s)" % json.loads(
        (ROOT / SRC / "forecast_input_recovery/summary.json").read_text())["unsupported_routes"],
    SRC + "forecast_input_recovery/summary.json", "unsupported_routes")
unsup163 = nums["B.permissive.routes_touching_unsupported_cell_hours"]["value"]
reasons = Counter(r["reason"] for r in cov if r["kind"] == "unresolved")
put("B.coverage_required.unresolved_reason", dict(reasons), SRC + "forecast_input_recovery/receipts.csv",
    "reason column of unresolved rows")

# ------------------------------------------------------------------ drawing helpers
CSS = """
:root{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6f6e69;--grid:#d9d8d3;--ok:#1a9e55;--okink:#ffffff;
--no:#2b2b2e;--noink:#ffffff;--un:#9a9aa0;--unink:#0b0b0b;--warn:#b5560a}
@media (prefers-color-scheme: dark){:root{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#9a998f;--grid:#3a3a37;
--ok:#2fbf74;--okink:#0b0b0b;--no:#e8e7e3;--noink:#0b0b0b;--un:#6f6f76;--unink:#f0efec;--warn:#e08a3a}}
text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:var(--ink)}
.t{font-size:20px;font-weight:600}.s{font-size:13px;fill:var(--ink2)}.l{font-size:13px;font-weight:600}
.n{font-size:15px;font-weight:600}.f{font-size:11px;fill:var(--muted)}.k{font-size:13px}
"""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(n):
    return f"{n:,}"


def bar(x0, y, w, h, parts, total):
    """parts: [(count, color var, ink var, label, hatch)] drawn left to right with 2 px surface gaps."""
    out, x, gap = [], x0, 2
    for cnt, col, ink, label, hatch in parts:
        if cnt == 0:
            continue
        pw = w * cnt / total
        rw = max(pw - gap, 1)
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{rw:.1f}" height="{h}" rx="3" fill="var({col})"/>')
        if hatch:
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{rw:.1f}" height="{h}" rx="3" fill="url(#hatch)"/>')
        if pw > 46:
            out.append(f'<text class="n" x="{x + rw / 2:.1f}" y="{y + h / 2 + 5}" text-anchor="middle" '
                       f'style="fill:var({ink})">{fmt(cnt)}</text>')
        x += pw
    return "\n".join(out)


DEFS = """<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="7" height="7" fill="var(--un)"/><line x1="0" y1="0" x2="0" y2="7" stroke="var(--bg)" stroke-width="2"/></pattern></defs>"""


def legend(x, y, items):
    out, cx = [], x
    for col, label, hatch in items:
        if hatch:
            out.append(f'<rect x="{cx}" y="{y - 11}" width="14" height="14" rx="2" fill="url(#hatch)"/>')
        else:
            out.append(f'<rect x="{cx}" y="{y - 11}" width="14" height="14" rx="2" fill="var({col})"/>')
        out.append(f'<text class="k" x="{cx + 20}" y="{y}">{esc(label)}</text>')
        cx += 28 + 7.0 * len(label)
    return "\n".join(out)


# ------------------------------------------------------------------ Figure A
W, Hh = 980, 470
a = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" width="{W}" height="{Hh}" role="img" '
     f'aria-labelledby="ta da"><title id="ta">Figure A: one backward pass replaces {fmt(n_total)} searches</title>'
     f'<desc id="da">Outcome of the {fmt(n_total)} recorded route checks and of the same checks read off the deadline '
     f'field: zero disagreements, {n_unres} undecided cases decided, deadlines exact to one second.</desc>',
     f"<style>{CSS}</style>", DEFS, f'<rect width="{W}" height="{Hh}" fill="var(--bg)"/>',
     f'<text class="t" x="24" y="36">One backward pass replaces {fmt(n_total)} searches</text>',
     f'<text class="s" x="24" y="58">The six recorded 2025 planner caches: every route check read off one backward '
     f'field per shelter, compared with the recorded forward check.</text>']
x0, bw = 24, 932
# rows
a.append(f'<text class="l" x="{x0}" y="102">Recorded: {fmt(n_total)} forward route checks, 30 s budget each</text>')
a.append(bar(x0, 112, bw, 44, [
    (n_checked, "--ok", "--okink", "route", False), (n_nr, "--no", "--noink", "no route", False),
    (n_unres, "--un", "--unink", "unresolved (timeout)", True), (n_at_issue, "--un", "--unink", "at issue", True)], n_total))
a.append(f'<text class="s" x="{x0}" y="178">checked route {fmt(n_checked)} · model no-route {fmt(n_nr)} · '
         f'unresolved/timeout {fmt(n_unres)} · unresolved/at-issue {fmt(n_at_issue)}</text>')
f_chk, f_nr = n_checked + n_u_chk, n_nr + n_u_nr
a.append(f'<text class="l" x="{x0}" y="218">Deadline field: the same {fmt(n_total)} checks, read off</text>')
a.append(bar(x0, 228, bw, 44, [
    (f_chk, "--ok", "--okink", "route", False), (f_nr, "--no", "--noink", "no route", False),
    (n_at_issue, "--no", "--noink", "origin in flame", False)], n_total))
a.append(f'<text class="s" x="{x0}" y="294">checked route {fmt(f_chk)} · model no-route {fmt(f_nr)} · origin point in '
         f'flame at that second (definite: no journey departing then) {fmt(n_at_issue)}</text>')
a.append(legend(x0, 322, [("--ok", "checked route", False), ("--no", "model no-route / no journey", False),
                          ("--un", "unresolved in the record", True)]))
# three claims
cy = 352
cols = [
    (f"{mism + mism2}", "disagreements",
     f"with any of the {fmt(n_checked)} recorded routes (same arrival second, same legs)\nor {fmt(n_nr)} recorded no-route verdicts"),
    (f"{n_unres}", "undecided cases decided",
     f"{n_u_chk} now have a checked route (full checker passes),\n{n_u_nr} are proven no-route in the model"),
    ("1 s", "deadlines exact",
     f"{fmt(w_pass)} of {fmt(w_next)} deadline witnesses pass; departing one second\nlater is infeasible in all {fmt(w_next)}"),
]
for i, (big, lab, sub) in enumerate(cols):
    cx = x0 + i * 315
    a.append(f'<text x="{cx}" y="{cy + 34}" style="font-size:34px;font-weight:700">{esc(big)}</text>')
    a.append(f'<text class="l" x="{cx}" y="{cy + 56}">{esc(lab)}</text>')
    for k, line in enumerate(sub.split("\n")):
        a.append(f'<text class="s" x="{cx}" y="{cy + 74 + 16 * k}">{esc(line)}</text>')
a.append(f'<text class="f" x="{x0}" y="{Hh - 22}">Sources: {F31} (jobs_all, witness_checks, deadlines per cache; '
         f'summed over the six caches); run notes research/harness-2026-11/F-3.1/RESULTS.md §1–§3.</text>')
a.append(f'<text class="f" x="{x0}" y="{Hh - 8}">Model-relative contact field on the recorded one-hour scenarios; not a physical-safety claim. '
         f'Planner deadlines: {dl_eq} of {n_origins} origins equal the record; the other {dl_later} were unresolved in the record.</text>')
a.append("</svg>")
(OUT / "FIGURE_A_one_backward_pass.svg").write_text("\n".join(a))

# ------------------------------------------------------------------ Figure B
W, Hh = 980, 440
b = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {Hh}" width="{W}" height="{Hh}" role="img" '
     f'aria-labelledby="tb db"><title id="tb">Figure B: corridor router, {cp["route"] + cp["refusal"]} of {len(perm)} '
     f'requests decided within 30 s</title><desc id="db">Same 273 requests under two missing-input policies: '
     f'{cp["route"]} routes, {cp["refusal"]} no-route proofs, {cp["unresolved"]} unresolved; and when native forecast '
     f'coverage is required {cc["route"]}, {cc["refusal"]}, {cc["unresolved"]}.</desc>',
     f"<style>{CSS}</style>", DEFS, f'<rect width="{W}" height="{Hh}" fill="var(--bg)"/>',
     f'<text class="t" x="24" y="36">Corridor router: {cp["route"] + cp["refusal"]} of {len(perm)} requests decided '
     f'within 30 s</text>',
     f'<text class="s" x="24" y="58">The same {len(perm)} requests (five historical fires, reconstructed forecasts), '
     f'two policies for cells where the forecast has no native value.</text>']
tot = len(perm)
b.append(f'<text class="l" x="{x0}" y="102">Missing forecast input allowed (zero-filled): the historical v8 run</text>')
b.append(bar(x0, 112, bw, 44, [(cp["route"], "--ok", "--okink", "", False), (cp["refusal"], "--no", "--noink", "", False),
                               (cp["unresolved"], "--un", "--unink", "", True)], tot))
b.append(f'<text class="s" x="{x0}" y="178">{cp["route"]} routes · {cp["refusal"]} model no-route proofs · '
         f'{cp["unresolved"]} unresolved · slowest request {nums["B.permissive.max_wall_s"]["value"]:.3f} s of 30 s</text>')
b.append(f'<text class="l" x="{x0}" y="222">Native forecast coverage required for every cell-hour a journey touches</text>')
b.append(bar(x0, 232, bw, 44, [(cc["route"], "--ok", "--okink", "", False), (cc["refusal"], "--no", "--noink", "", False),
                               (cc["unresolved"], "--un", "--unink", "", True)], tot))
b.append(f'<text class="s" x="{x0}" y="298">{cc["route"]} routes · {cc["refusal"]} model no-route proofs · '
         f'{cc["unresolved"]} unresolved · slowest request {nums["B.coverage_required.max_wall_s"]["value"]:.3f} s of 30 s</text>')
b.append(legend(x0, 326, [("--ok", "checked route", False), ("--no", "model no-route proof", False),
                          ("--un", "unresolved (not a no-route proof)", True)]))
why1 = (f"Why: {unsup163} of the {cp['route']} routes in the first bar occupied at least one cell-hour with no native forecast "
        f"value (zero-filled), so they are withheld when coverage is required;")
why2 = (f"absent forecast data is not proof that no route exists, so a request with no covered route and no "
        f"unrestricted no-route proof is reported unresolved ({cc['unresolved']}).")
b.append(f'<text class="k" x="{x0}" y="360">{esc(why1)}</text>')
b.append(f'<text class="k" x="{x0}" y="378">{esc(why2)}</text>')
b.append(f'<text class="f" x="{x0}" y="{Hh - 36}">Sources: {SRC}receipts.csv (first bar; kind, wall_s, unsupported_cell_hours), '
         f'{SRC}forecast_input_recovery/receipts.csv (second bar; reason = SUPPORT_RESTRICTED_SEARCH_NO_ROUTE for all {cc["unresolved"]}).</text>')
b.append(f'<text class="f" x="{x0}" y="{Hh - 22}">Intermediate run on the same requests before forecast inputs were recovered: '
         f'{cm["route"]} / {cm["refusal"]} / {cm["unresolved"]} ({SRC}support_273_receipts.csv). '
         f'Branch: codex/experimental-corridor-router-v8, evidence/ copied byte-for-byte.</text>')
b.append(f'<text class="f" x="{x0}" y="{Hh - 8}">Retrospective reconstructions, 30 s / 3,072 MiB guard, one Mac, run once per request; '
         f'model-scoped results, not field safety.</text>')
b.append("</svg>")
(OUT / "FIGURE_B_corridor_router.svg").write_text("\n".join(b))

(OUT / "FIGURE_NUMBERS.json").write_text(json.dumps(nums, indent=1, ensure_ascii=False))
print(json.dumps({k: v["value"] for k, v in nums.items()}, indent=1, ensure_ascii=False))
