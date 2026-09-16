# Research program taskboard

Single source of truth for task status. The orchestrator maintains this file;
agents report into `research/reports/<agent>/` and the orchestrator brings the
status back here.

Last updated: 2026-09-16, end of round 2.

## Waiting on John

Each item is one action. They are batched so they can be cleared in a single
sitting. Round 1 added WJ-008 through WJ-016.

**If you clear only one thing, clear WJ-001.** After that, WJ-017.
**Where the data actually stands:** 3 of 18 registry entries are verified, and all
three are the ones that needed no key and no consent click. 7 are blocked on
WJ-001, and 8 need a human to click through a consent form, file an application,
or register an account. No agent may do any of those. It unblocks the API probe,
Sentinel-2, the active-fire archive, KMA and VWorld in a single action, and two
of the three directions cannot be fitted without it.

| id | severity | action | why it needs a human |
|---|---|---|---|
| WJ-001 | BLOCKER | Provide the six API keys as environment variables: `DATA_GO_KR_KEY`, `KMA_APIHUB_KEY`, `VWORLD_KEY`, `FIRMS_MAP_KEY`, `EARTHDATA_TOKEN`, and `COPERNICUS_USER` with `COPERNICUS_PASS` | All six unset, confirmed by probe. The KFS statistics API answers 401. Agents must never create accounts or accept terms |
| WJ-002 | DECISION | Approve moving the ten research claim rules from `research/shared/check_research_claims.py` into `scripts/check_forbidden.py` | Editing `scripts/` is a change outside `research/`. Rules are written and validated; only the move needs the word |
| WJ-003 | DECISION | Confirm the branch: keep research work on `claude/wonderful-gates-jlutm9`, or re-cut onto `research/<direction>-<topic>` | The brief asks for per-direction branches; this session may push only to its designated branch. See DECISIONS D-003 |
| WJ-004 | BLOCKER | Open the NIFoS press release of 2025-04-25 in a browser and save attachment 2-2 to `research/lit/sources/` | Session-bound download. **One question in it changes the roads design: which width the 6 m claim means, running surface or the full cleared gap including cut slope, fill slope and shoulder.** On a Korean mountain forest road those differ by a multiple, and testing the wrong one is not a test of the claim |
| WJ-005 | DECISION | Send the drafted Sancheong landslide inventory request to the Pukyong National University group | Outgoing email is a human gate. Draft is in `research/reports/requests/`. Author contact details still need filling in from the paper |
| WJ-006 | DECISION | If the KFS Open API does not reach back to 1991, send the drafted records request to KFS or NIFoS | Outgoing email is a human gate. Blocked behind WJ-001 |
| WJ-007 | FYI | The FIRMS NOAA-20/21 branch is not yet cut. It touches finals code, so it lands on `fix/firms-noaa20-21` for review and is never merged by an agent | Suomi NPP delivery ends 2026-11-01 |
| WJ-008 | DECISION | Research work on a `claude/**` branch gets **no CI**. Either rename the branch to `auto/**` (which also settles WJ-003) or widen the branch filter in `.github/workflows/auto-gates.yml` | `auto-gates.yml` triggers only on push to `auto/**` and `Main`. Verified: PR 50 has zero check runs and always will. Gates are being run locally on each exact commit as the substitute. Widening the filter is a change outside `research/` |
| WJ-009 | BLOCKER | Confirm a source of high-resolution **pre-fire** Korean orthoimagery, about 50 cm or better, with per-tile vintage, on terms permitting programmatic tile access and derived measurement. Candidates: VWorld orthoimagery, 국토정보플랫폼 | The forest road layer has no width attribute, so width must be measured from imagery. This is now the primary path for the roads direction, not a fallback. Neither candidate is verified |
| WJ-010 | DECISION | Decide whether to request suppression resource placement records for the five study fires | A road that held partly measures that a crew was standing on it. This is the strongest objection to the roads direction and there is no data fix without these records |
| WJ-011 | DECISION | Decide whether to pursue NGII access for the 5 m DEM and the national base map | NGII returned HTTP 400 to automated fetch on two separate attempts. Without it the DEM is Copernicus GLO-30 at 30 m, which makes the ridge sample systematically incomplete and skewed toward large ridges |
| WJ-012 | DECISION | Read the KOGL Type 3 (no modification) licence on the forest type map, data.go.kr id 15093362, against the plan to derive a pine and broadleaf covariate from it | A derived layer from a no-modification source is a licence question, not an engineering one. The species contrast is the landslide direction's core arm |
| WJ-013 | FYI | Supply the correct reference for what the brief calls **"Keeling et al. 2001"** | No paper matching that author and year exists in any plausible context for this program. Verified against Crossref independently of the agent that first found it. Not in the bibliography; search log in `research/lit/UNVERIFIED.md` |
| WJ-014 | FYI | The brief's **"Anderegg et al. 2021"** is mislabelled | The relevant paper is Trugman, Anderegg, Anderegg, Das and Stephenson 2021, DOI 10.1016/j.tree.2021.02.001. Entered under correct authorship with the correction noted. Mislabelled upstream, not fabricated |
| WJ-015 | DECISION | Agents here never run git, so a registered number cannot bind itself to a commit hash. Decide whether the orchestrator stamping the commit at registration time is acceptable provenance | Raised by A6. Currently the number-to-commit link is only a script and input hash |
| WJ-016 | DECISION | A6 re-runs numbers it has already seen produced, so it is not blind at re-run time | Raised by A6 as a known weakness of single-repository validation. Worth deciding whether that is acceptable or whether a stronger arrangement is wanted |
| WJ-017 | BLOCKER | Download the forest road SHP yourself: data.go.kr id 3045621 bounces to forest.go.kr, whose zip is served only behind a personal-information consent checkbox. Click through and drop the zip in `research/data/raw/kfs_forest_roads/` | **Now the highest-priority item for the roads direction, ahead of WJ-009.** The consent gate is server-enforced, not cosmetic: a direct GET of the static zip returns HTTP 307 to an error page. Until the file lands, nobody knows the layer's field list, so A3 cannot tell whether the encounter dataset can be dated at all. A road built in 2023 scored as a barrier that held at Uljin in 2022 is a fabricated observation, not a noisy one |
| WJ-018 | DECISION | Download the forest type map through the FGIS application flow (map.forest.go.kr, a named 신청 with a stated purpose) | Same underlying system as the WJ-012 licence question, so both clear in one sitting. The species contrast is the landslide direction's core arm |

## Status legend

`dispatched` sent to an agent, running. `done` delivered and checked against the
definition of done. `blocked` cannot proceed, with a WJ id or a task id that
must clear first. `not started` queued behind its phase.

## Phase 0, setup (orchestrator)

| task | agent | status | blocker | report |
|---|---|---|---|---|
| T0.1 Create the `research/` layout | orchestrator | done | none | this file |
| T0.2 Registry skeleton, 17 datasets in priority order | orchestrator | done | none | `research/data/REGISTRY.yaml` |
| T0.3 Forbidden-claims entries in hypothesis wording | orchestrator | done | WJ-002 for the repository-wide move | `research/FORBIDDEN_CLAIMS.md` |
| T0.4 Claims and em-dash checker, validated both directions | orchestrator | done | none | 10 rules, 28/28 catches, 27/27 spares |
| T0.5 Confirm the existing gates still run | orchestrator | dispatched | none | see round 1 summary |

## Phase 1, data and prior art

| task | agent | status | blocker | report |
|---|---|---|---|---|
| T1.1 Verify the committed KFS statistics CSV, register it, write its check | A1 | done | none | `reports/A1/2026-09-16_round1.md` |
| T1.2 Confirm dataset ids, endpoints and licences for priority 1 and 2 | A1 | done | NGII blocked, see WJ-011 | same |
| T1.3 KFS API probe for 1991 to 2001 | A1 | blocked | WJ-001 | probe script written and tested |
| T1.4 Draft the request letters | A1 | done | WJ-005, WJ-006 to send | `reports/requests/` |
| T1.5 Solar times, complex rule, timestamp QC, geocoding precision, CRS | A2 | done | none | `reports/A2/2026-09-16_round1.md` |
| T1.5f Settle the brief's 41-negative-duration claim | A2 | blocked | fire state history CSV not on disk | transform written and tested on synthetic frames |
| T1.6 Roads prior-art note and verified bibliography | A7 | done | none | `reports/A7/2026-09-16_round1.md` |
| T1.7 Verify Wilson 1988 and Sidle 1992 | A7 | done | none | both verified, DOIs recorded |
| T1.8 Korean-language sweep, roads | A7 | done | none | no paper found that answers the roads question |

**Measured, not assumed.** The KFS statistics CSV is 2020 rows covering 2022 to
2025 only. Negative durations: 12, which agrees with the brief and was counted
independently twice. Impossible end years: 2 (2055 and 2223). The brief's second
claim of 41 negative durations in the state-history file could NOT be tested,
because that file is not on disk, and it stays unverified rather than assumed.

## Phase 2, design

| task | agent | status | blocker | report |
|---|---|---|---|---|
| T2.1 Sign-off protocol, leakage checklist, shared splits, kill-shot template, numbers protocol | A6 | done | none | `reports/A6/2026-09-16_round1.md` |
| T2.2 Roads pre-registration draft | A3 | done | none | `reports/A3/2026-09-16_round1.md` |
| T2.3 A6 signs the roads pre-registration | A6 | **done, verdict `refused`** | none | `eval/signoffs/roads_v0.1b.md` |
| T2.6 Keyless open-data downloads | A1 | done | 2 of 4 landed; 2 need WJ-017 and WJ-018 | `reports/A1/2026-09-16_round2.md` |
| T2.7 Forest road attribute schema | A1 | blocked | WJ-017, the SHP never landed | same |
| T2.11 Roads pre-registration v0.2, conditions R1 to R7 | A3 | dispatched | none, R1 is design work and needs no data | |
| T2.4 Landslides pre-registration | A4 | not started | roads reaches phase 3 | |
| T2.5 Suppression pre-registration | A5 | not started | landslides reaches phase 3, and WJ-001 | |

**Sign-off ledger:** `research/eval/signoffs/LEDGER.md`, three rows, all
`unsigned`. Nothing may be fitted until a row says otherwise.

## Phase 3 to 6

Not started. Phases 1 to 4 run for roads first, then landslides, then
suppression. Phase 5 scenarios and phase 6 integration are gated on John.

## Definition of done for the program

Each direction needs a pre-registration, a verified dataset chain from raw
download to model, a fitted model with uncertainty, a simple-baseline
comparison, an A6 sign-off, and a prior-art note stating what is new. Every
reported number traces to a script and a registry entry. The em-dash count is
zero, all gates pass, and the finals build is untouched.
