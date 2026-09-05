# The fair opponent: present perimeter + a fixed buffer

**Row:** WFG-114 · **Decision:** NH-027 option A (author, 2026-09-05) —
「Run it in the sprint now, P0 … report the number whatever it says」
**Method proposed by:** the loop (three consecutive critic laps wrote the objection);
**run authorised by:** the author.
**Artifact:** `data/processed/present_perimeter_arm_uiseong_andong_2025.json`
**Script:** `scripts/run_present_perimeter_arm.py` · **Registry:** `pp_uiseong_*` (57 keys)

---

## 1. The objection this answers

Every comparison the project ships is future-aware routing against `naive`, and
`naive` is **fire-blind**: it walks the shortest path to the nearest refuge and is
only told afterwards whether that path burned
(`src/wildfireguardian/routing/evacuation.py`, `naive_route`). So the headline —
「의성·안동 368곳 중 91곳은 예보를 본 경로에서만 안전했다」 — credits the
**forecast** with everything that merely **seeing the fire** would already have
bought. Three critic laps in a row wrote that objection down. It is the single
most damaging question a judge or a reviewer can ask, and until now the project
had no measurement to answer it with.

The fair opponent is the policy a county office can run today with no model at
all: **refuse everything that is burning now, plus a fixed safety buffer, then
take the shortest path through what is left.**

## 2. What was run

| arm | what it knows | route choice |
|---|---|---|
| fire-blind (control) | nothing | shortest path by `length_m` on the full network |
| **present perimeter + buffer (new)** | **where the fire is at slice 0** | the same, on the network minus the buffered perimeter |
| forecast-aware | the whole predicted hazard, in time | exposure-minimising on the time-expanded graph |

All three run on the **canonical arm** — slope 60 m sampling, DiGraph, `|slope|`
clipped at 0.6, distance-ranked, `p_cut` 0.5, 600-minute budget, stride-18 origin
scan — the arm the headline's **91** comes from. Every node within 1 km of the
centre of a slice-0 cell at `p >= 0.5` is refused; a refuge inside the buffer is
not a refuge and is dropped (31 → 29). The result is scored against the **full**
hazard sequence by the same `_evaluate_path` the other two arms use, so "safe"
means one thing in all three columns: reached a refuge, never stood on a cell at
`p >= 0.5` while it was at `p >= 0.5`, **and arrived inside the 600-minute
budget**.

⚠ That last clause is a correction this document had to make to itself. The
committed classification scores the fire-blind route with **no** time budget,
while the forecast-aware router enforces one internally and the present-aware arm
is held to it. Comparing the three as they stand is two rules in one table, and
the asymmetry runs in this project's favour twice over: it inflates the control,
and because those origins count as "already safe" it also inflates the damage the
buffer appears to do. Two fire-blind routes arrive at 624.8 and 628.2 minutes. So
the budget is applied to all three columns — the control is **263**, not 265, and
the buffer breaks **4**, not 6 (the withdrawn 6 is the current 4 plus those same 2
late origins, and has no key of its own). The committed unbudgeted figure is kept
in the artifact as `safe_fire_blind_unbudgeted`.

**And the two late origins turn out to be a committed number's whole story.** They
are exactly the committed `fa_exceeds_budget` bucket, member for member — the
bucket whose registered meaning (`mr_uiseong_fa_exceeds_budget` = 2) is 「the
fire-blind route is safe but the future-aware route is not」. Under one budget rule
they are not that: their fire-blind routes arrive at 624.8 and 628.2 minutes, so no
arm saves them, and the bucket is **empty**. That is why the budgeted control (263)
equals `both_safe` exactly — a consequence, not a coincidence. **This qualifies a
committed, registered, judged number, so this document does not change it**: it is
`NH-031` for the author to decide, and the value stands untouched meanwhile.

**The reproduction gate.** The script refuses to write unless it first reproduces
the committed canonical arm: all seven bucket counts, and the origin ids of every
bucket the committed artifact actually stores a list for (3 non-empty buckets,
105 ids). `both_safe` has no stored list and is pinned by complement, because the
counts and the scan size both match. `--verify-only` runs that check alone. That
reproduction is the entire warrant for the third column — without it these
numbers would be about the harness rather than about the question.

### 2b. Two origin rules, and the convention is worth more than the result

Eighteen scanned origins stand **inside** the buffer: outside the fire at slice 0
(the origin rule guarantees that) but within a kilometre of it. What the arm may
tell them is a modelling convention, and it turned out to matter more than the
headline does, so both conventions are computed for every origin:

| rule | what an origin inside the buffer may do | safe total | forecast's margin |
|---|---|---|---|
| **`walk_out`** (primary) | move within the buffer to get out; never re-enter once outside | **345** | **9** |
| `strict` | keep only its own node; neighbours inside the buffer are closed | 335 | 19 |

`walk_out` is primary because it is what a present-aware operator would actually
say to someone standing inside the buffer, and because `strict` biases the experiment **in
this project's favour**: every origin it strands is scored against the fair
opponent and inflates the forecast's apparent margin. The difference between the
two rules is larger than the margin itself, so reporting only one of them would
have been choosing the answer. Both are in the artifact.

## 3. The result

| | origins safe (of 368) |
|---|---|
| fire-blind | **263** |
| present perimeter + 1 km | **345** |
| forecast-aware | **354** |

Of the **91** origins that were safe *only* on the forecast-aware route, the
present-aware arm recovers **86**. Five remain forecast-only. The buffer also
**breaks 4** origins the fire-blind control already got to safety: 3 lose every
route to a refuge, and 1 is pushed onto a detour that walks into the fire.

**So the forecast's margin over the fair opponent on this fire is 9 origins of
368 — not 91.** That is the number the author asked for, and it is far smaller
than the one the project has been quoting.

The recovered routes are not free: paired against the same origins' fire-blind
routes they are **3382.8 m longer on average**, and the worst is **10424.3 m**
longer, on foot, by elderly walkers.

## 4. Why 1 km is not a constant, and why that matters more than the 9

Nothing in the data chose 1 km, so the same counts were measured at four other
widths in the same run:

| buffer | recovered of 91 | already-safe broken | safe total | **walks into the fire** | no route | too slow |
|---|---|---|---|---|---|---|
| 250 m | 12 | 0 | 275 | **91** | 0 | 2 |
| 500 m | 23 | 2 | 284 | **80** | 2 | 2 |
| **1 km** | **86** | 4 | **345** | **3** | 4 | 16 |
| 2 km | 19 | 7 | 275 | 5 | 8 | **80** |
| 3 km | 24 | 4 | 283 | 3 | 9 | **73** |

The 1 km row is a **spike, not a plateau**, and the last three columns say why.
The arm has two ways to fail and they trade off against each other:

- **Too thin** (250 m, 500 m): the buffer is inside the fire's own growth. The
  route dodges the perimeter as it stands and the fire arrives anyway — **91 and
  80 origins walk into it.**
- **Too thick** (2 km, 3 km): the fire nearly stops catching people, though **not
  monotonically** — widening from 1 km to 2 km puts *more* walkers in the fire
  (3 → 5), because the detour grows long enough for the fire to reach them on it.
  The dominant failure changes anyway: the detour it forces is one an elderly walker cannot
  finish. **80 and 73 origins reach a refuge without ever entering the hazard
  and arrive after the 600-minute budget**, which for an evacuation is not a
  success. A handful more (8 and 9) have no route at all.

1 km happens to sit on the crossing: narrow enough that the detours are still
walkable, wide enough that the fire has almost stopped catching people.

**This is the honest defence of the forecast, and it is a better one than the 91
ever was.** A present-aware policy can nearly match the forecast on this fire —
*if you already know which buffer to use*. An operator standing in front of a
burning hillside does not know that. Choose 500 m and 80 origins walk into the
fire; choose 2 km and 80 cannot finish the walk in time. The forecast-aware arm
reaches 354 with no width to choose, because the thing the buffer is a crude
proxy for — how far the fire will get, and in which direction, before people
finish walking — is what the forecast actually computes.

## 5. What this does NOT show

- **⚠ The forecast-aware arm carries no forecast error here.** It plans on the
  same hazard field it is scored against, so 9 is the margin a **perfect**
  forecast buys over a present-perimeter policy. The margin of this project's
  actual model is smaller by an amount this run does not measure. That is a
  property the 91 has always had, inherited not introduced — but a fire scientist
  will ask about it, and the honest answer is this paragraph, not a number.
- **One fire, one ignition, one departure time, one region.** The buffer band is
  a sensitivity check on a single run. Nothing here says 1 km is the crossing
  point for any other fire — and §4's whole argument is that it would not be.
- **It is not a claim about survival.** "Safe" is the committed routing
  definition, on a simulated hazard field, for a scanned grid of origins that are
  not households.
- **It does not license「예보는 필요 없다」or「1 km가 최적」.** Both are registered
  as forbidden phrasings on all 57 `pp_uiseong_*` keys.

## 6. A limitation this document invented, and then withdrew

The first version of this run was built on the **flat/DiGraph** arm, and said in
prose that the canonical arm could not be reached from a cloud lap because its
SRTM raster lives at `data/raw/firms_data/uiseong_andong_2025_dem.tif`, which is
git-ignored. **That was false.** The lap's own independent reviewer falsified it
in 103 seconds: the same raster, byte for byte, is committed to the snapshot
store as `data/snapshots/srtm-dem_uiseong-andong-2025_20260802_e4df23a9.tif`,
whose `MANIFEST.json` entry records that exact `origin_path` and the same
sha256 — and CHARTER §4 "Sandbox facts" tells every lap to work from
`data/snapshots/` for precisely this reason.

It is recorded here rather than quietly deleted, because a limitation invented by
not looking is the same defect as a result invented by not measuring
(CHARTER §3.5), and because it changed the answer: on the flat arm with the
strict origin rule the margin read 17, and the canonical arm with the honest
origin rule gives **9**. ⚠ That 17 is **not re-derivable from this tree** and has
no registry key: the v1 artifact was never committed. It is not the same quantity
as `pp_uiseong_strict_rule_margin_1km` = 19, which is the strict rule on the
*canonical* arm. Do not try to reconcile them. The flat arm's own bucket (96 origins, 90 of them shared
with the canonical 91) stays in the artifact under `flat_arm_crosswalk` so the
withdrawal is checkable rather than merely asserted.

## 7. Reproducing it

```bash
python scripts/run_present_perimeter_arm.py --verify-only   # the reproduction gate alone
python scripts/run_present_perimeter_arm.py                 # ~4 min, writes the artifact
python scripts/register_present_perimeter.py --check        # registry matches the artifact
```

No API key and no network access are needed: the walk graph, the refuges **and
the SRTM raster** all come from `data/snapshots/` through `MANIFEST.json`, and the
hazard from the committed `hazard_uiseong_andong_2025.npz` under
`data/processed/` (its full path and sha256 are in the artifact's `sources`).

Every cell of the §4 table is a registry key, not only the ones the prose names:
the band is this document's whole argument, so all six counts at all five widths
are registered (`pp_uiseong_w250m_*` … `pp_uiseong_w3000m_*`) and re-derived by
`make verify` like any other number.

## 8. What this changes elsewhere

- **WFG-104** (the Q&A card) was told by its own row to write 「the
  present-perimeter arm has **not** been run」. It has now, so that instruction
  was corrected in the same commit — writing it unchanged would have put a
  fabricated limitation into the Q&A bank in the student's voice. The card itself
  is still WFG-104's to write, and is not in this document.
- The 91 keeps its meaning and its wording: it is the count of origins safe only
  on the forecast-aware route **against a fire-blind control**, which is what it
  has always said. What changes is that the project now also states, in the same
  breath, what the number is against a *present-aware* control. Neither figure is
  withdrawn; the second is the one that was missing.
