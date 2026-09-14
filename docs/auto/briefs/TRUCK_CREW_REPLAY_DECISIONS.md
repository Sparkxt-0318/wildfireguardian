# HQ decisions on the truck-crew replay report (2026-09-14)

Answers from the author's HQ session to `docs/auto/briefs/TRUCK_CREW_REPLAY_REPORT.md`
(PR #35, branch `auto/red/2026-09-13T2010Z`). The build agent should rebase onto this
commit's `auto/dev`, which is green on GitHub again (NH-061 fixed here), and open one PR.

## NH-061 — option A, applied on `auto/dev` in this commit

`tests/test_finals_payload_rederives.py` now decodes embedded `data:image/png` payloads and
compares pixels; bytes are encoder-dependent and were never what the screen shows. Root
cause: commit `7750d8f` (the author's laptop session, 2026-09-12) rebuilt `web/finals.html`
with this laptop's PNG encoder. Every 「ALL GREEN on the laptop」 message since was true
locally and red on GitHub's runner; CHARTER §4b's rule that a lap checks GitHub's own run
was not followed by the laptop sessions, and that is recorded here as the lesson.

## The six open questions

1. **Corridor count with the success line.** Neither goes anywhere yet. When either does,
   they go together, in one sentence, on the same surface; the success line may not travel
   alone. Until the abort rule is v2 (below) the line is not quotable at all.
2. **Abort rule v2.** Rebuild it on the vehicle's own passage: for each edge of the ingress
   route, the minute the vehicle is on it versus the minute that edge's cells reach the
   vehicle cutoff, with the cutoff crossing interpolated **linearly in time between the five
   forecast slices** (the sampler already interpolates; use its interpolation, not the slice
   index). Abort minute = latest departure from the depot at which every edge is still
   below the cutoff when the vehicle reaches it, minus the 12-min margin. This is one
   quantity in continuous minutes, consistent with the router's own test. Keep v1's numbers
   as a record, labelled 「slice-boundary version」.
3. **Population.** The 30 % immobile draw is a config assumption and must not drive the
   replay's headline. Run three populations and report all three: (a) the 24 credible
   no-safe-walk nodes and the 10-node cluster (the honest core), (b) the 54 no-safe-walk
   nodes, (c) the immobile draw at 10 % and 30 % as a labelled sensitivity. The finals
   sentence is written from (a) and (b) only.
4. **Footnote the two scheduler defects** on `docs/vehicle_pickup_intervention.md` §4 (a
   dated note, no number moved) and fix both in the scheduler under a new function name;
   re-run the intervention under a new artifact name and report whether the 9-of-24 /
   40-of-74 result moves.
5. **Re-cut policy.** Agreed; one PR from the green head, then stop re-cutting until HQ
   answers again.
6. **Leak-free field.** Yes: run the replay on `routing_demo_leakfree.npz` as a sensitivity
   arm with the same rules, new artifact name, and report the four counts side by side.
   Do not switch the base; the canonical field stays the base until the author decides.

## Registration
Nothing from the replay is registered or placed on a judge-facing surface by the build
agent. Registration, if any, is an HQ action after the v2 numbers exist.
