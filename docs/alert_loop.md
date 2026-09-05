# Alert / notification loop — design

Session 8, Phase 3. **Design first, code second** — this document specifies the
loop; `src/wildfireguardian/delivery/alert_loop.py` implements exactly what §3
specifies and nothing more.

**Motivation (현장 실무자 자문, N = 1, qualitative —
`firefighter_consultation.md` §3; a statement, not a measurement):** 「연세
있으심, 말 잘 안 듣는다. 지금 불이 안 보이니까 도망 안 간다」, 「연락 전달이
제일 중요하다」. The mechanism is known in the literature: Lindell & Perry's
Protective Action Decision Model (2012, *Risk Analysis* 32(4)) shows people
delay protective action until an **environmental cue** plus **social
confirmation** arrive; Mileti & Sorensen (1990, ORNL-6609) establish that
warning compliance rises with message **specificity**, **certainty**, and
**source credibility**.

⚠ Scope honesty, up front: this system improves **delivery** and computes
**rescue priority**. It does not model compliance, and nothing in this tree
supports a claim that it raises compliance (consultation §3.2 — the 순응
problem is out of scope). The loop below is designed so that *if* a resident
acts, the system reacts; whether they act is not ours to claim.

---

## 1. The escalation ladder

Four rungs, each served by an artifact Layer 4 already produces. No new
channel is created (consultation §7.2: channel composition stays; the four
channels of `delivery_channels.md` §1 are the universe).

| rung | channel | Layer 4 artifact serving it | audience / rationale |
|---|---|---|---|
| 1 | 재난문자 (cell broadcast) | `sms.py` draft text (place names, no coordinates) | broadest reach; 2025 Yeongnam survey put emergency-SMS reception in Yeongdeok at 48 % — rung 1 is necessary, never sufficient |
| 2 | TTS 자동전화 (landline) | the same landmark-anchored template rendered by `alert_loop.build_tts_call` — landlines are the elderly non-smartphone case the A4/PA channels were already designed around | reaches the resident who owns no smartphone; adds the keypress confirmation (§3) |
| 3 | 이장 마을방송 | `broadcast.py` script (≤ 15 chars/sentence, repetition, place names only) | the PA carried more evacuation information than SMS in the same survey; adds **social confirmation** (a known voice) per PADM |
| 4 | neighbour door-knock list | the A4 sheet's dispatch table, **ordered by the Layer 3 dispatch priority** (closing window ascending) | the last physical rung; ordering by the same priority as the responder queue means the scarcest resource — a neighbour's trip — goes to the household the model says closes first |

Escalation is downward through the table: a rung fires when the previous
rung has produced no confirmation for the household within the rung's dwell
time. Dwell times are operator policy, not model output — the implementation
takes them as parameters and defaults are labelled assumptions.

**No real telephony or SMS service is integrated.** Rungs are served as
*text artifacts + a simulated confirmation stream*; transmission stays behind
the `delivery_channels.md` §0 approval statement. Claiming live telephony
would be unverifiable, so it is out of scope by design.

## 2. Message template spec

The differentiator this model actually has: the spread model computes, per
village cluster, a **landmark-anchored arrival estimate** — not "산불 발생,
대피 바람" but "○○공원 방면으로 약 N분 뒤". Specificity and certainty are the
two levers Mileti & Sorensen name that a model can move.

Template shape (all rungs, formal 합니다체, never 한다체):

```
{landmark} + {time-to-arrival} + {explicit instruction} + {counter-cue line}
```

- **landmark**: the cluster's coordinate-free name (nearest named refuge,
  `delivery/villages.py` naming rules — never coordinates; consultation §7's
  equipment-level constraint).
- **time-to-arrival**: the hazard field's earliest walk-cutoff crossing time
  at the cluster centroid, rounded DOWN to the forecast slice (conservative:
  stated arrival is never later than modelled arrival). Overpass-scale
  resolution — minutes are quoted as 「약 N분」, never as a precise clock.
- **explicit instruction**: destination by name + the action, imperative
  합쇼체 (「지금 즉시 …로 대피하십시오」).
- **counter-cue line**: 「연기가 보이면 이미 늦습니다.」 — the direct answer
  to 「지금 불이 안 보이니까 도망 안 간다」: it pre-empts the absent
  environmental cue by naming the cue's arrival as the point of no return.
- rung 2 (TTS) appends the confirmation prompt:
  「대피를 시작하셨으면 1번을 눌러 주십시오.」

Constraints per rung: SMS ≤ 90 code points (`sms.MAX_CHARS`); broadcast
sentences ≤ 15 chars (`broadcast.MAX_SENTENCE_CHARS`); TTS text has no hard
cap but one confirmation prompt exactly.

Filled examples: **generated from real model output** by
`scripts/generate_alert_examples.py` → `data/processed/alert_examples.json`
(committed). Three of them are quoted in §4 below — quoted *from the
artifact*, not hand-written.

## 3. The confirmation loop (the novel systems claim — specified precisely)

**Claim being made:** a keypress-confirmed self-evacuation removes that
household from the *active* dispatch queue in real time, and Layer 3 re-ranks
the remainder. **Claim NOT being made:** that a confirmation means the
resident is safe.

Event model (`alert_loop.ConfirmationEvent`): `home_node`, `t_min` (clock),
`rung` (which rung elicited it), `source` — **every simulated event carries
`source = "synthetic"`**, and the simulator refuses to emit anything else.

Re-ranking rule (`alert_loop.apply_confirmations`):

1. The dispatch queue keeps its committed ordering key (closing window
   ascending). Re-ranking = **partition**, not re-scoring: confirmed
   households move from the **active queue** to a **follow-up list**; the
   active queue's relative order is unchanged (deterministic, no RNG).
2. A confirmation can only **lower** priority (active → follow-up). No event
   type raises priority or marks a household safe. The follow-up list retains
   every field the active entry had, plus the event, flagged
   `needs_verification = True`.
3. Failure modes, handled conservatively:

| failure mode | handling |
|---|---|
| **no answer** | ≠ refusal, ≠ absence: the household simply **stays in the active queue** at its position. Silence changes nothing. |
| **false confirmation** (keypress, then no evacuation) | the household is in the follow-up list, `needs_verification = True` — rung 3/4 (PA + door-knock) still cover it, and a door-knock non-confirmation event (`kind = "doorknock_not_evacuated"`) moves it **back** to the active queue at its original key. Moving back is the ONE upward transition, and it restores, never raises, priority. |
| **confirmation then failure to move** | same as false confirmation — verification is physical (rung 4), never inferred. |
| **duplicate / out-of-order events** | idempotent: the first confirmation partitions; later duplicates are no-ops; a return event after a duplicate confirmation still returns. |

4. Determinism: given the same dispatch list, the same event stream and the
   same seed for the simulator, active/follow-up partitions are identical
   (pinned by test).

**Why this is conservative by construction:** the responder never loses a
household the system merely *hoped* had left. The only way out of the active
queue is an affirmative resident action, and the only thing that action buys
is a lower place in line — plus a mandatory physical verification tail.

## 4. Filled examples (quoted from `data/processed/alert_examples.json`)

Generated from the real-OSM scenario (arm-B network vintage, synthetic
hazard — every quoted minute is a model output, not authored):

> **SMS (rung 1) — 우곡공원 일대 cluster (16 dispatch homes, arrival 45 min):**
> 「[영덕군 안내] 산불이 약 45분 뒤 우곡공원 일대 방면에 도달할 것으로
> 예측됩니다. 지금 즉시 대피하십시오. 연기가 보이면 이미 늦습니다.」

> **TTS 자동전화 (rung 2) — 같은 cluster:**
> 「영덕군 재난안전대책본부입니다. 산불이 약 45분 뒤 우곡공원 일대 방면에
> 도달할 것으로 예측됩니다. 지금 즉시 우곡공원(으)로 대피하십시오. 연기가
> 보이면 이미 늦습니다. 대피를 시작하셨으면 1번을 눌러 주십시오.」

> **마을방송 (rung 3) — 같은 cluster (≤ 15자/문장):**
> 「주민 여러분께 알립니다. / 산불이 오고 있습니다. / 약 45분 뒤 도달합니다. /
> 지금 대피하십시오. / 우곡공원(으)로 / 가시기 바랍니다. / 연기가 보이면 /
> 이미 늦습니다. / 지금 대피하십시오.」

(The exact strings for all three example clusters — including a
long-landmark case that exercises the SMS compaction and broadcast
word-wrapping rules — live in the committed artifact; the three above are
copied from it verbatim. If this paragraph and the artifact ever disagree,
the artifact wins. The 45 is a model output on labelled-synthetic hazard,
arm-B network vintage — not a measured arrival.)

## 5. What was implemented vs deferred

Implemented (`delivery/alert_loop.py`, `tests/test_alert_loop.py`): template
builders with per-rung constraints; the confirmation-event model; the
partition/return re-ranking with the invariants of §3; a `synthetic`-tagged
event simulator; the example generator script.

Deferred, deliberately: real telephony/SMS integration (out of scope,
unverifiable — §1); dwell-time policy values (operator policy, parameters
only); any compliance-effect claim (no evidence in this tree, consultation
§3.2).

## 6. References

- Lindell, M. K. & Perry, R. W. (2012). The Protective Action Decision Model:
  theoretical modifications and additional evidence. *Risk Analysis*, 32(4).
- Mileti, D. S. & Sorensen, J. H. (1990). Communication of emergency public
  warnings. ORNL-6609.
- Cova, T. J., Dennison, P. E., Kim, T. H. & Moritz, M. A. (2005). Setting
  wildfire evacuation trigger points using fire spread modeling and GIS.
  *Transactions in GIS*, 9(4). (arrival-time framing)
