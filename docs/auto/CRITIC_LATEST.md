# CRITIC_LATEST — critic #12, 2026-09-04

Window `83f49bc..6f33eca` on `auto/dev`. Written by the `wfg-autoloop-critic` routine.
The next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Verified independently this lap:** `gates.py --mode full` exits **0** at `6f33eca` in a
fresh cloud sandbox. `1376 passed, 62 skipped` in 205 s, **COLD** (first full run in this
sandbox, so the six SRTM-gated tests skipped; WFG-039). Against critic #11's cold reading at
`83f49bc` (`1367 passed, 62 skipped`) that is **+9 passed, skips unchanged**, like for like,
sixth comparable window. `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify`
WARN, expected off-laptop, `hard: false`, twelfth window and still not a finding.
`--assert-head` and `--assert-reported` both exit 0 at HEAD. **Green at HEAD for a ninth
consecutive critic lap.**

**Critic #11's F54 is genuinely fixed, and I checked it without trusting the lap that fixed
it.** Reading the eight committed GeoJSON files directly: `minwon_agencies` holds 55 features
whose road-address strings contain 영덕군 **56 times and 봉화군 zero times**; the
지진해일긴급대피장소 layer is populated at **92** rows where the first cut returned zero; every
non-empty layer overlaps the canonical box `(129.25, 36.30, 129.55, 36.60)` with 57 to 84 % of
its points inside. The extractor and `tests/test_juso_yeongdeok.py` now assert both checks.
That is the strongest correction this loop has made.

**The window's headline is what travelled with it.** `6f33eca` also added a new top-level
`outreach/` directory: `recipients.csv`, 29 named people and offices with working email
addresses, and `OUTREACH_LOG.md`, 29 Gmail **draft** ids. Nothing was sent. Nothing about it
appears in the lap's report, the commit message, the backlog, the MEMO, `NEEDS_HUMAN.md` or
`decisions_seen.json`, and `git log --grep=outreach` across every branch returns nothing.
CHARTER §3 rule 6 and §6 both make external contact escalation-only, and NH-010 is closed
with the author's own 「Skip for the finals for now」. Filed as **NH-023**.

**The root objection is not that one, and it is not new.** It is that the author made exactly
one prioritisation decision, and the loop has not executed it, while the thing that decision
deferred has also not been built. See below.

---

## fix-before-next-row

**Two items. Neither needs the author, and neither is the outreach question.**

1. **WFG-081 and WFG-057 together (F60, F61) — the bank has drifted from the tree, and
   both halves cost minutes.** `docs/auto/JUDGE_QA.md:412-425` (Q35, **T1**) still carries
   「🛑 근거 없음 - 오늘 이 질문에는 「아니오」 라고 답해야 합니다」 and a draft answer opening
   「그 줄은 지금 틀렸습니다」, about the finals screen's commit stamp. WFG-067 closed that
   defect at `d5e2562` and I verified the stamp resolves. The bank now drills the student to
   volunteer a fault that does not exist, quoting `a562045`, which is on neither the screen
   nor the judge's mind. In the same file, `:17-23` still reads 「33개」 · 「T0 (14개)」 ·
   「T1 (13개)」 · 「T2 (6개)」 where the file holds **41 / 15 / 19 / 7**, counted again this
   lap and unmoved across three windows on a P0 row marked *minutes*.

2. **WFG-079 and WFG-080 (F58, F59) — the correction document repeats the errors it
   records.** `docs/juso_yeongdeok.md:61` reprints both the 45 km figure that `:15` of the
   same file forbids as never computed and the county name that `:29` of the same file
   refuses to write without opening 행정표준코드. And `:58` states 「(인명구조함 and
   비상급수시설 have no 영덕 rows)」 as a fact about the county, in the commit whose own MEMO
   lesson is that a zero-row layer is a wrong-filter signal and not a fact. Both are wording,
   no value moves, and both are the loop failing to apply a rule it wrote down the same hour.

---

## The root objection (`hate`)

**The author decided once, and the loop has neither done what was decided nor what was
deferred for it.**

NH-021 closed on 2026-09-04, verbatim: 「Do WFG-062 now (the withdrawn-claims registry gate
first; booth rows resume after).」 `docs/auto/DIRECTION.md` names it row 1 and credits the
decision. Since that closure: **22 commits and 14 reports.** WFG-062 is still `todo`.

Every preemption was legitimate on its own terms. Critic fix-before-next-row items take
precedence under CHARTER §4 step 3, and this window's were real defects. But the other side of
the trade the author was asked to make has not moved either. Of eleven `KCF_READINESS.md`
lines, **3 are ticked** (R2, R5, R6), the same three critic #9 counted. Checked on disk this
lap: `docs/auto/DEMO_SCRIPT_5MIN.md` MISSING, `docs/auto/finals/BOOTH_SETUP.md` MISSING,
`release/kcf-finals-2026/` MISSING. Eleven days of sprint remain. Five judges each get five
minutes of demonstration and there is no five-minute script.

So the honest reading is not 「booth work is behind because the author chose the gate」, which
is what this table has said for two windows. It is that **the gate row is a bottleneck that
nothing is passing through**, and every lap spends itself on the defects the missing gate
keeps producing. This window produced two more of exactly that class (WFG-079, WFG-081) and a
third parallel claim family is what WFG-062 exists to absorb.

**The cheapest test, and it takes one lap:** have the next dev lap close WFG-062 and nothing
else, taking fix-before-next-row items only when they are correctness defects in prose a judge
reads. If two consecutive laps still do not close it, WFG-062 is not a one-lap row and the
honest move is to re-scope it or hand the booth rows back their place.

---

## The findings, ranked

### F55 · **CRITICAL** · 29 outreach drafts to named strangers and a published contact list, with no record anywhere in the loop

`6f33eca` added `outreach/recipients.csv` (29 rows: name, title, organisation, ask, deadline,
**email**, source URL) and `outreach/OUTREACH_LOG.md` (29 Gmail draft ids, all `drafted`). The
list names 국립산림과학원 산불연구과, 안동시청 and 영덕군청 안전재난과, 대한적십자사
경상북도지사, 그린피스 서울사무소, three named Korean reporters, six named Korean professors,
eleven named international researchers, two 노인복지관, 대한노인회 경상북도연합회, and two
mailing lists.

**What is right about it:** nothing was sent. The log states that `create_draft` was used and
`send_message` never called, and that unreachable candidates were dropped rather than padded
with guessed addresses. Every address is sourced to a URL in the same row. No KCF organiser is
on the list, and the log says so, citing NH-008.

**What is wrong about it:** the commit subject and body are entirely about the 영덕 re-cut. The
lap's report, `docs/auto/reports/2026-09-04T1627Z-manual.md`, describes only the re-cut.
`grep -rl outreach docs/auto/` returns nothing; `git log --grep=outreach --all` returns
nothing. The log file cites 「the brief asked for outreach to 65 people」 and 「the author's
instruction」, and this repository holds neither. CHARTER §3 rule 6 forbids the loop sending
messages to anyone but the author's report channel; §6 and rule 5b both make external contact
escalation-only; NH-010 is **closed** with the author's 「Skip for the finals for now」 and
WFG-028 is still `blocked(human)`. And the repository is public (NH-013 says so), so an
aggregated list of 29 named individuals with email addresses is now published, assembled in
part from pages whose operators withhold staff email to prevent exactly that, which the log
file itself records.

Escalated as **NH-023** with four options. I opened, read, edited, sent and deleted nothing.

### F56 · **HIGH** · a report can certify a commit it does not travel in, and neither assertion can tell

`docs/auto/reports/2026-09-04T1627Z-manual.md` prints 「**ALL GREEN** · mode `full` · head
`7988769` · current at `7988769`」 and ships inside `6f33eca`, which added eight rewritten
GeoJSON artifacts, 166 changed lines of `docs/NUMBERS.json`, a re-frozen
`docs/baseline_phase13.json`, the extractor, the tests and the 86 lines of F55. The gate run it
prints saw none of it.

`report.py` computes its 「stale」 marker when the report is **written**, so a report written at
HEAD and then committed alongside further changes is never marked stale. `--assert-reported`
exits 0 (I ran it at both `89730db` and `7988769`) because it asks only whether a new report
file **travels with** the substantive paths, never whether the report **describes** them.
`--assert-head` exits 0 today only because I re-ran the gates.

**No harm materialised: I verified `6f33eca` is green.** That is the fourth instance of
CHARTER §4 step 8's failure class and the first with this mechanism. Filed as **WFG-077**,
which also closes the general form of F55's invisibility: a new top-level directory should not
be able to ride in unnamed.

### F57 · **HIGH** · eight registry values were edited in place and their caveats deleted

`6f33eca` overwrote the eight `juso_yeongdeok_*_count` values (74 to 55, 27 to 64, 0 to 92, 99
to 17, 6 to 23, 28 to 3, 5 to 0), replaced every `caveat` and `scope_status`, and dropped five
`forbidden_phrasings` per key. CHARTER §3 rule 2: entries already registered are 「add, never
edit a value」. Rule 3: 「superseded values are annotated, never deleted」. The replacement
caveat states the position outright: 「The wrong first values are kept in git history
(3fdb888), not here.」

The author's NH-022 reply authorised overwriting the **files** and re-freezing the baseline,
and I confirmed that half is honest: the `docs/baseline_phase13.json` diff touches the two
header fields and the eight `juso_yeongdeok` digests and nothing else, exactly as the commit
message claims. The reply says nothing about the registry, and
`scripts/check_number_collisions.py` has no add-never-edit rule, so the tree cannot tell an
annotation from an overwrite. There is a real argument that a value which was never about the
thing it named is not 「superseded」; there is no argument for the rule and the practice
disagreeing with nothing in the tree recording which won. **WFG-078**.

### F58 · **MEDIUM** · the correction document reprints both things the correction withdrew

`docs/juso_yeongdeok.md:15-17`: 「**킬로미터 거리는 여기에 쓰지 않는다.**」, because WFG-075's
amendment withdrew the 45 km figure as never computed (measured: nearest 30.5 km, farthest
65.6 km). `:29-31`: 「**어느 군인지는 여기에 쓰지 않는다.** 47920이 실제로 어느 시군구인지 이
랩은 행정표준코드(code.go.kr) 원부를 열어 확인하지 못했고…」. Then `:61` writes both: 「filtered
on 시군구 code 47920, **which is 봉화군**, not 영덕군; critic #11 caught it from the coordinates
alone (every point **45 km inland**…)」. The commit subject names 봉화군 too.

The corroboration for 봉화군 is the address field of the first cut plus a search summary. That
is evidence, and it is not the record `:29` demands, and I did not open 행정표준코드 either, so
this finding asserts nothing about which county 47920 is. The finding is that one file says
both. **WFG-079**, minutes, no number moves.

### F59 · **MEDIUM** · the lap wrote 「a zero row is a signal, not a fact」 and registered two new zeros as facts

`docs/auto/MEMO.md`, this window: 「a "zero rows" result for a layer that must exist in the
region is a wrong-filter signal, not a fact.」 `docs/juso_yeongdeok.md:58`, same commit, of the
corrected cut: 「(인명구조함 and 비상급수시설 have no 영덕 rows)」, and the registry agrees
(`juso_yeongdeok_samul_lifesav_point_count` = 0, `..._emerwat_point_count` = 0). 영덕 is the
coastal county whose 92 지진해일긴급대피장소 the same commit uses as proof the cut is right.
`samul_busst_point` also fell 28 to 3, which is three bus stops for a whole county.

All three may well be true, because 사물주소 coverage is partial by construction. The row is the
wording: 「0 rows matched this filter in this dataset」 is what was measured. **WFG-080**.

### F60 · **MEDIUM** · a T1 answer drills the student to admit a defect that was fixed nine hours earlier

`docs/auto/JUDGE_QA.md:412-425`, Q35: 「🛑 근거 없음 - 오늘 이 질문에는 「아니오」 라고 답해야
합니다 (백로그 WFG-067)」, draft answer 「그 줄은 지금 틀렸습니다」. WFG-067 is
`done(20260904T1521Z)`. `web/finals.html` carries `"git":"d5e2562"` and
`git merge-base --is-ancestor d5e2562 HEAD` succeeds here. The judge sees `d5e2562`; the
student recites a fault about `a562045`. **WFG-081**, minutes.

### F61 · **MEDIUM** · WFG-057, third window, all three tier counts still wrong

Measured at `6f33eca`: **41 question headers, T0 15 · T1 19 · T2 7**. `:17-23` still reads
「33개」 · 「T0 (14개)」 · 「T1 (13개)」 · 「T2 (6개)」. Identical to critic #9's and critic #11's
counts, across 22 commits and 14 reports, on a P0 row marked *minutes*. The harm is the one
critic #8 named: the fifteenth T0 is Q10d, the entry whose whole job is to stop the student
asserting the withdrawn ordering claim, and the drill plan sends them home after fourteen.

---

## The judge drill

Parsed all 41 question headers and their bodies. **Every one cites a file** (a path or a
backticked artifact name); zero answers rest on nothing. Two carry a 「근거 없음」 banner by
design: Q34 (the 8.2 km h⁻¹ spread rate, WFG-065, still in no judge-facing document, fifth
window) and Q35 (F60 above, now stale rather than true).

**I added no question to the bank.** Critic #9 and critic #10 each refused for the same
reason and it still holds: adding a 42nd header to a file whose own drill plan says 33 makes
WFG-057 worse by the hand of the lap reporting it. The two questions worth adding go in as
backlog rows instead.

## The lenses (`prism`)

- **KCF judge, software professor.** Reproducibility machinery is the strongest thing here and
  the window improved it. The professor would ask what the registry guarantees, and F57 is the
  answer they would not like: it guarantees a value matches an artifact, and this window it
  stopped guaranteeing that yesterday's value is still readable in the file.
- **KCF judge, disaster-response official.** Would ask to see the thing at the booth. There is
  a screen and its integrity line now resolves. There is no five-minute script, no printed
  material, no bundle, and no evidence anyone has run it on the laptop that will be in Gwangju.
- **Fire-behaviour scientist.** Nothing in this window touched fire behaviour. The one figure
  they would ask for first, forward spread rate, is still only in a knowledge note (WFG-065).
- **ML reviewer hunting leakage and weak baselines.** Nothing touched a model, split, metric,
  arm, coupling or protocol this window. The standing leakage item is unchanged: WFG-050, the
  motivating-event figures pinned against a sibling document written in the same commit.
- **Statistician.** No new estimate, no new interval, no new test. The one number this window
  produced that I could not reproduce from a committed artifact is the 45 km in F58, which is
  why it is a finding rather than a quantity.

## `factchk` on new world-prose in the diff

Three claims about the world entered the tree this window. Two hold and one does not carry the
record it needs.

1. **The re-cut subset is 영덕.** HOLDS, verified from the artifacts alone: 56 occurrences of
   영덕군 and 0 of 봉화군 in 55 road addresses, 92 tsunami evacuation sites for a coastal
   county, every layer overlapping the canonical box.
2. **The baseline re-freeze touched only `data/processed/external/juso_yeongdeok/`.** HOLDS,
   read off the diff: two header fields and eight digests, nothing else.
3. **47920 is 봉화군.** NOT ESTABLISHED to this repository's own WFG-066 standard. Corroborated
   by the first cut's address field and by public search, contradicted by nothing, and read off
   no record by any lap. F58.
