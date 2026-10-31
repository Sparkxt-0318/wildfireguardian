# hazard_contract/ — the shared interface: Track A produces it, Track C consumes it

Tiny package, dependencies **numpy and pydantic only**. The code and its tests are the
definition of the contract; `README.md` here summarizes it.

## Ground rules (identical in every program folder; they override this repo's older audit conventions)

1. **Allowed folders.** Create and edit files only in `evacplan/`, `firecast-lab/`,
   `hazard_contract/` and `program/`. Never edit, move or delete anything else: the rest of
   the repo is the frozen research release. Import from `integration/` (`wfg_latest`) and
   `forecast/` (`wildfire`) instead of copying them. Adding these tracks to CI needs
   Siyeong's approval.
2. **Light rigor, no bureaucracy.** Every result row records the git commit, seed, config and
   host. That's all. No SHA ledgers, custody receipts, gate JSON files, "HOLD" taxonomies or
   reviews of reviews. If you want a verification document, write a test instead.
3. **One feasibility oracle**, `evacplan.oracle`. It is the only code that may declare a
   vehicle itinerary `checked`, `model_no_route` (model-infeasible, scoped to model and
   horizon) or `unresolved`. Fast relaxed checks are allowed inside search loops, but final
   answers and Track A's decision metric go through the oracle.
4. **Unknown is not unburned.** Missing hazard data flows through as `unsupported`, which
   leads to `unresolved`. It never defaults to safe. `unresolved` never counts as safe or
   delivered.
5. **Splits before methods.** Track C: frozen `dev` and `test` instance sets. Track A:
   `firecast-lab/SPLITS.json`, split by whole fire, never by cell or window. Touch `test`
   sets or held-out fires only at milestones, after Siyeong approves. Track A reports
   uncertainty with whole-fire bootstrap intervals; repeated windows are not independent fires.
6. **Fair timing.** Agents may write code in parallel. Timed benchmark runs must not overlap
   other heavy computation: run them through the shared lock,
   `python program/benchlock.py -- <command>` (lock file `program/.bench.lock` in the main
   checkout, shared by all worktrees). Always compare methods at equal wall-clock budgets.
7. **Data and licenses.** Keep OSM attribution (ODbL). Choi et al. 2026 reconstructions and
   NIROPS perimeters are CC BY 4.0; CMS provider data is public. Label synthetic data as
   SYNTHETIC everywhere, including figures. Ask before any download over 1 GB, any scraping,
   or committing anything over 20 MB. Never commit raw rasters, weights or personal data
   (use the folder's `.gitignore`).
8. **Stack.** Python 3.12. Track C: numpy, networkx, osmnx, OR-Tools, HiGHS (`highspy`),
   pydantic, pytest, matplotlib. Track A: also PyTorch (CPU or Apple MPS), scipy,
   scikit-image, rasterio or xarray. CPU or MPS only. Ask before adding other major
   dependencies.
9. **Time-box.** Each experiment states its budget and ends with one decision: KEEP, KILL or
   ITERATE. Negative results are reported in the same format as positive ones.
10. **Git.** Never commit to or push `Main`. Never force-push. Never create GitHub repos. Push
    only `next/integration`, the track branches `evacplan/phase0` and `firecast-lab/phase0`,
    and short-lived experiment branches (`evacplan/exp-<ID>-<slug>`,
    `firecast-lab/exp-<ID>-<slug>`) to `origin`. Experiments merge into their track branch,
    track branches into `next/integration`; Siyeong merges `next/integration` into `Main`
    through pull requests. Commit small and often, with clear messages.

**Always ask Siyeong before:** changing either problem definition or the `hazard_contract`
interface; touching test sets or held-out fires; downloads over 1 GB; adding a major
dependency; any single run longer than 2 hours; editing anything outside the four folders;
opening a pull request to `Main`.

## Change control

- Only the orchestrator changes this package. Track agents that need a change write the
  request under "Blockers" in `program/STATUS.md` and continue with what exists.
- Every interface change: ask Siyeong first, record it in `program/DECISIONS.md` with a
  one-line reason, and bump `hazard_contract.CONTRACT_VERSION` (written into every
  `meta.json`). Readers refuse a major version they do not know.
- Bug fixes that do not change the format or the meaning of a query result do not bump the
  version, but still need a test.

## Invariants that must never be weakened

- `nan` arrival = unknown → `supported = False`. Unknown is never unburned.
- Any query touching an unsupported cell returns `supported = False` (and `contact = None`
  unless contact is already certain from supported cells).
- Adding burning cells (earlier ignition, later extinction, more burning area) can never
  turn `contact = True` into `False`, and can never lower `flux_upper`.
- A stationary position (waiting or a destination stay) is a zero-length geometry over the
  occupancy interval — it is checked exactly like a moving segment.

## Contract v1 in one screen (details: `README.md`; definition: code + tests)

- Folder = `members.npz` (`ignite_s`, `extinguish_s` float `[K,H,W]` s after issue; `supported`
  bool) + `meta.json` (`ScenarioMeta`). Burning = `[ignite, extinguish)`; `inf` = no burning
  within the horizon; `nan` = unknown ⇒ unsupported. Nothing is known for `t > horizon_s` or
  outside the grid.
- `member.segment(geom, t_in, t_out)` (any speed profile) / `segment_uniform` (uniform motion,
  the router's rule) → `SegmentHazard(contact, flux_lower, flux_upper, supported, dose_lower,
  dose_upper)`. Closed cells ("whole-road" contact). Units kW/m², kJ/m².
- Flux law `sheet_solid_angle_v1` = the `wfg_latest` finite-cell sheet law; peak ≤ q_rad/2.
- `dose_lower`/`dose_upper` were added to the specified `SegmentHazard` so the oracle can bound
  cumulative exposure (recorded in `program/DECISIONS.md`).
