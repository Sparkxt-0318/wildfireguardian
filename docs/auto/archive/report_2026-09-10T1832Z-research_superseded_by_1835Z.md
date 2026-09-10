> **ARCHIVED, NOT A LIVE REPORT. Superseded by `docs/auto/reports/2026-09-10T1835Z-research.md`.**
>
> This file is the first `report.py --kind research` output of the 2026-09-10T1817Z research lap. It never
> passed its prose gates and it never travelled with a push, so it is not a report of record and must not be
> read as one. The failure was **environmental, not editorial**: `scripts/auto/bootstrap.sh` hit a pip read
> timeout against `files.pythonhosted.org` and left the venv without `pytest`, `networkx` or `matplotlib`, so
> the lineage gate exited with `No module named pytest` and no images were rendered. The lap installed the
> three packages in the foreground and re-ran `report.py`, which produced the 1835Z report cleanly (both
> prose gates PASS, five images written).
>
> It is archived rather than deleted because CHARTER §3 rule 7 forbids deleting, and archived rather than
> committed under `docs/auto/reports/` because that directory is what the next lap and the critic read as the
> window's reports; a second, gate-failing report for the same lap sitting there would be a false record.
>
> Archived 2026-09-10 by the lap that produced it.

---

# WildfireGuardian autoloop · research · 2026-09-10T1832Z

| | |
|---|---|
| when | 2026-09-10 18:32 UTC · 2026-09-11 03:32 KST |
| branch / head | `auto/dev` / `9a45b2e` |
| kind | research |
| environment | (no bootstrap record) |
| backlog | blocked: 9, done: 33, dropped: 1, parked: 1, title-derivable: 1, todo: 116 |

## What happened this lap

# Research lap 2026-09-10T1817Z — an independent group published this project's architecture, and its headline failure is ours

**Head at start:** `9a45b2e`. **Scan window:** 2026-09-08 → 2026-09-10 (two days). No code, no data, no figure, no `docs/NUMBERS.json` entry was touched. Full run: `docs/auto/research/RUN_2026-09-10.md`.

## What the scan found

**The headline.** Bokade, Barai, Bhogle, Chapherkar & Kale published 「A Hybrid Neural Physical Framework for Wildfire Propagation Modeling and Dynamic Evacuation Routing」 on **2026-09-09** (Zenodo, 10.5281/zenodo.22668357, record and abstract opened; the 2.5 MB PDF was not read and is named as a lead). A U-Net flammability prior, a cellular-automaton physics engine in PyTorch, and a router that 「incrementally routes traffic away from actively predicted fires」 — this project's pipeline shape, published five weeks before the finals, evaluating **nothing**. Two consequences:

1. **The architecture can no longer be presented as the contribution.** Routing against a forecast rather than a current perimeter was this project's implicit design novelty; an independent group made the same choice in the same month. The claim relocates to the **output object and its measured limits** — they ship an interactive simulation, this project ships `docs/disc_null.md`, `docs/oracle_gap.md` and a withdrawn-claims registry. Filed as **WFG-239** (P1, IEEE, prose only). This is the **second novelty narrowing in two research runs** (WFG-198 was the first) and both made the claim smaller and harder to attack.
2. **Their headline negative result is this project's own uncomfortable finding, independently reproduced.** Verbatim: 「modern predictive frameworks utilizing end-to-end deep learning often succumb to **persistence bias**」 and 「neither a recurrent nor a non-recurrent network learns to advect fire past the persistence baseline」 — which is why they abandoned learned advection. **WFG-234** already asks for a persistence null against the headline truth and already warns persistence may beat the model. Its row was **updated in place**: if persistence wins, that is a named, published failure mode of the whole model class, not a private embarrassment, and the framing is to be pre-registered in the claim commit.

**The doctrine got a better source.** The 8 h / 5 h elderly-evacuation thresholds now rest on 국립산림과학원's own briefing on the government portal (korea.kr, 2026-02-12, opened, four sentences quoted verbatim) rather than on a newspaper restatement. **WFG-197's source-class constraint was relaxed in place**; every substantive constraint on that row is unchanged. ⚠ A search summary additionally described a 「위험 구역 / 잠재적 위험 구역」 **zoning** by predicted arrival time — that wording is **not** on the page opened, is recorded UNVERIFIED, and no lap may write it until confirmed at a document.

**A domestic academic comparator now exists.** Choi & Chae (강원대학교, Zenodo, 2026-09-01, opened): a self-attention U-Net over **118 Korean wildfire events (2018–2025)**, 102-event operating-envelope subset, cross-validation plus hold-out, ~6.8 GB of code and weights with reproducibility docs. **No metric value is stated in the record and none was read.** Its output object is burned-area extent and burn probability **from ignition conditions** — a different question — which is domestic support for the output-object thesis. Whether to name it on a judge-facing surface is the author's: **NH-056**, four options, no accuracy comparison under any of them.

**Pyrogeography and routing each gained sourced paragraphs** (CHARTER §13): TFFM's terrain/wind directional controls (arXiv:2609.07763), Korean spring green-up gating (Choi & Chae, Zenodo), the embargoed Korean dryness-index case-crossover (Min, 5,783 ignitions / 22,936 controls, numbers embargoed to 2027-05-30), and Bokade's D\* Lite router. **All five knowledge notes** carry a dated `## Update 2026-09-10`; the two with nothing to add say so explicitly.

## Discipline, and what this run did not do

**One new row, not three.** Five sprint days remain and the P0 block is congested, so C1 became one P1 prose row, C2 was **folded into the existing WFG-234** rather than duplicated, and C3 was parked as **P-004** (replacing time-expansion with D\* Lite — parked because a replanner prices an edge at the cost it has *now*, and a route that looks open and will be cut in forty minutes is exactly what a time-expanded graph refuses).

**Table placement was measured, not asserted.** The 09-08 run claimed its rows 「enter at the end of the P1 block, which reorders nothing」 and critic #46 measured that false. Here: `WFG-239` is **row 233 of 233**, the last row in the table, line 269, with **21 P0 rows above it**. No existing row moved; **zero** DIRECTION reorders.

⚠ **One finding raised for the critic rather than claimed.** `DIRECTION.md` recorded **P0 `todo` = 15**; at this head a strict column-2 parse gives **21 P0 rows, 3 `todo`**, and a 「P0 anywhere」 parse gives **108 rows, 28 `todo`**. This run **publishes no fourth number**. The likely cause is WFG-191's documented column-shift defect. It matters because DIRECTION is the page a dev lap reads to choose work.

**IEEE plan.** The alternative-venue survey, carried forward twice, finally ran: IGARSS 2027 (Reykjavík, 2027-07-11→16) recorded with no fee figure, and the structural finding written down — **an IEEE conference swaps an APC for author registration and travel, so no IEEE route is free.** Gap **G11** added. **Nothing was submitted anywhere.**

**Channels.** OpenAlex carried channel (b) and produced every domestic finding; Semantic Scholar was **not attempted** (429 on two prior runs, NH-048 open); Scholar Gateway remains OAuth-blocked, third consecutive run. **Three sources could not be opened** and are recorded UNVERIFIED with their HTTP status, their substance written nowhere: the Altadena/Eaton WUI accessibility preprint (403 twice), the *Transportation* volcanic mode-choice paper (paywalled), and Bokade's own PDF. **No paper was cited that this run did not open.** Conformal risk control returned **no** wildfire-hazard instance for the third consecutive run; the negative is now a stated IEEE-paper gap.

## In plain terms

- **The field:** a team in India published almost exactly your system on 9 September — fire forecast feeding live evacuation routing — but they measured none of it, and their main finding is that their AI just copied the fire's current shape forward instead of learning where it moves. Your project already caught itself doing the same thing and wrote it down.
- **For your project:** stop saying the *design* is what is new, because someone else built the same design this month. What is new is that you produce an actual per-person "walk out or wait for rescue" answer **and** you measured how wrong it can be. That is a stronger claim and nobody else in this month's literature has it.
- **What to do:** answer **NH-056** — a Korean university published a reproducible AI wildfire model on 1 September, and you should decide now whether you mention it to the judges rather than hearing it from them first. Four options are written out for you; a yes/no line in your reply is enough.



## Gates

(gates not run this lap)

## Commits since the previous report (-15)

- 9a45b2e the critic report names the head it ships in, and keeps the RED run its own finding is about
- 33d108f critic #60: the page that answers the project's hardest question says nothing answered it before, and the front door has for months
- 71e95ee the backlog row names a commit that exists
- 2231f75 the dev report names the head it ships in, and keeps the gate run that failed
- 3a38395 the board is rebuilt on the rebased tree, so it covers both laps
- b8fd6a8 WFG-228: the headline IoU gets a null model, and the null turns out to share an initial condition with the thing it is a null for
- eff1bc0 the paper's account of its own registry named five fields on every entry; two of them are not on every entry
- 4ab2e07 claim WFG-228 (20260910T1522Z), and pre-register what its answer means before it is computed
- 5f321dc the critic report names the head it ships in, and keeps the head it reviewed
- c7c915b critic #59: the sentence written to be pasted into the submitted document explains the weak fold with a number the rest of its own file does not use
- 3867860 the dev report names the head it ships in, and says which of its two gate runs certifies it
- 60b8975 the reviewer's block: a negative proved by a truncated grep, and the lap that had just caught the same error
- ba76b8c WFG-226 and WFG-229: the card the student says from memory drops a contradiction that closed and picks up the number a judge is holding
- 2d6bcfe claim WFG-226 and WFG-229 (20260910T1222Z)
- f4ef66e critic #58: the page that explains the project's biggest weakness claims a machine protection the registry does not give

## Needs a human (28 open)

- NH-003 [FYI] `Main` is behind the working line by design
- NH-004 [FYI] The sandbox has no API keys, so the loop works from committed snapshots
- NH-005 [DECISION] Building footprints for Yeongdeok (Session 21 blocker)
- NH-014 [DECISION] Run the booth recipe once on the real laptop (after 09-10, before 10-16)
- NH-032 [DECISION] Two laps built your fair-opponent row at the same time and got different answers: 9 and 27 (by 2026-09-08)
- NH-033 [FYI] This lap force-pushed its own parking branch, which CHARTER §3.8 forbids flatly
- NH-034 [DECISION] Your fair-opponent experiment ran, and it cuts the headline from 91 to between 5 and 27 (by 2026-09-08)
- NH-035 [DECISION] The three-hour rule you chose to un-stick a stranded row cannot fire on the three-hour dev grid (by 2026-09-09, one day past; raised to HIGH by critic #55 on a measured third instance)
- NH-036 [DECISION] One critic lap told the next one not to edit a file, and that is what kept a false sentence in front of a judge for a window (by 2026-09-10)
- NH-037 [DECISION] The paper's word proxy now stops it a thousand words before your 25-page rule (by 2026-09-10)
- NH-038 [DECISION] Your "product first" rule has spent the last three dev laps on documents, and the readiness line it was written to protect has not moved in five critic laps (by 2026-09-09)
- NH-039 [DECISION] The national wildfire-spread system's manual is an 18 MB PDF the sandbox could not fetch, and one of you can (by 2026-09-12)
- NH-040 [FYI] A critic lap pushed one commit past a red `--assert-reported`, and it is telling you rather than hiding it
- NH-041 [FYI] This lap sent you an email containing only the word PLACEHOLDER, and could not take it back
- NH-042 [DECISION] Two of your own rules collide whenever a withdrawn claim lives in a frozen artifact, and this week they collided three times (by 2026-09-10)
- NH-043 [DECISION] A gate your loop built this morning will go red about twice a day, and the charter tells the lap that meets it to stop working (by 2026-09-09)
- NH-045 [BLOCKER] The staleness gate has closed `auto/dev` to every routine, and the one routine that met it is the one forbidden to clear it (by 2026-09-08)
- NH-044 [DECISION] The claim the paper just retracted is still live on the page the paper cites for it (by 2026-09-09)
- NH-046 [DECISION] Your product's definition-of-done names a command nothing in this project has ever run (by 2026-09-10)
- NH-048 [DECISION] One of the research routine's three literature channels has been dead for two runs, and a working replacement is already proven (by 2026-09-10)
- NH-049 [DECISION] Your critic routine is told to add judge Q&A cards and your own printing gate makes that impossible for it (by 2026-09-11)
- NH-050 [DECISION] You answered two of these questions two days ago and the loop never heard you, because you answered them on the routine page (by 2026-09-10)
- NH-051 [DECISION] The rule your loop has been obeying for three days is not the option it names, and the difference is why one row has been pushed down five times (by 2026-09-11)
- NH-052 [DECISION] The experiment that measures what your own forecast is worth is now one run away, and it would change what 42 means (by 2026-09-12)
- NH-053 [DECISION] The word your front door uses for 42 stopped being right today, and the loop cannot pick its replacement (by 2026-09-12)
- NH-054 [DECISION] Four fifths of your front door's headline is limits, and no lap is allowed to decide whether that is the project's strength or its biggest presentation risk (by 2026-09-13)
- NH-055 [DECISION] Your front door compares the headline forecast number to a model the same page calls broken, and today the loop measured a second, harsher comparison it is not allowed to put beside it (by 2026-09-13)
- NH-056 [DECISION] A Korean university published a reproducible deep-learning wildfire model four weeks before your finals, and a lap may not decide on its own whether to mention it (by 2026-09-13)

---
Generated by `scripts/auto/report.py`. Charter: `docs/auto/CHARTER.md`. Backlog: `docs/auto/BACKLOG.md`.
