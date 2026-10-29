# Claude Code prompt: orchestrator for tracks 1A, 1B and 1C as parallel subagents in one session

Use this instead of running the three prompts by hand. Before starting, copy the four prompt files into the repository at `docs/next/prompts/` (`00_SHARED_INTERFACES.md`, `01A_flame_front_radiation.md`, `01B_forecast_upgrades.md`, `01C_routing_members_sipp_validation.md`) and commit them on a branch `next/orchestrator`. Start Claude Code in the repository root on that branch and paste everything below the line.

---

You are the orchestrator for three parallel research tracks in the WildfireGuardian repository. You coordinate; you do not implement the tracks yourself. Your tools: `TaskCreate`/`TaskUpdate` for the plan, the `Agent` tool with `isolation: "worktree"` to run each track on its own branch and working tree, `SendMessage` to steer a running agent, `git` for inspection and merging, and `Bash` for running tests. Keep your own context small: read only `README.md`, `docs/PROJECT_STRUCTURE.md`, `docs/next/prompts/00_SHARED_INTERFACES.md` and the three track prompts. Do not read large source files yourself; the track agents do that.

## Step 0: publish the contracts (you, not a subagent)

1. Copy `docs/next/prompts/00_SHARED_INTERFACES.md` to `docs/NEXT_INTERFACES.md` unchanged and commit it ("Publish shared interfaces for tracks 1A, 1B, 1C").
2. Write `docs/NEXT_PLAN.md`: the three tracks, their ownership tables (copied verbatim from the interfaces file), the merge order below, the acceptance gates below, and a progress log that you append to as things happen. Commit.
3. Create the task list: one task per track deliverable (1A-1 library, 1A-2 physics validation, 1A-3 binding statistics, 1B-1 mean field, 1B-2 survival training, 1B-3 structural ablations, 1B-4 baselines, 1B-5 pre-registration, 1C-1 members, 1C-2 SIPP, 1C-3 synthetic truth), plus "Integration checks", "Combined evidence README", "Pull requests opened".

## Step 1: launch the three tracks in parallel

Launch three `Agent` calls in a single message, each with `isolation: "worktree"`, `run_in_background: true`, `subagent_type: "general-purpose"`, and a prompt that says exactly: "Read `docs/NEXT_INTERFACES.md`, then read and execute `docs/next/prompts/<file>` in full. Work only inside the files that prompt's ownership section allows. When you finish a deliverable, append a line to `docs/NEXT_PLAN.md` under Progress log with the headline number and commit. Do not merge. When done, reply with: branch name, list of changed files, headline numbers, open problems." Use the model your organization allows for long tasks; if a choice exists, prefer the strongest model for 1A and 1C (they contain proofs and differential tests) and a fast model is acceptable for 1B's baseline work only if the agent is told to escalate hard parts.

While they run, do not idle-poll. When an agent reports, record its summary in `docs/NEXT_PLAN.md`. If an agent asks a question only the human can answer (data roots, the forecast rasters, the NIROPS archive location, FARSITE availability), relay it to the human with `AskUserQuestion` once, batching questions.

## Step 2: ownership enforcement (after each agent reports, before any merge)

For each track branch run `git diff --name-only Main...<branch>` and compare against the ownership table in `docs/NEXT_INTERFACES.md`. Any file outside the track's allowance is a violation: send the agent a `SendMessage` instructing it to revert that file (or move the change into its own folder) and re-run its tests. Do not merge a branch with a violation. The one deliberately shared touch point is `forecast/wildfire/rollout.py` (only track 1C, only the `trajectory_callback` kwarg); verify the diff there is exactly that and that the byte-identical-default test exists.

## Step 3: acceptance gates (per track, all must pass)

- Tests: each track's test suite passes in a fresh virtual environment built from the repository's pinned requirements (`python3.12 -m venv`, `pip install -c constraints-routing.txt './integration[packets]'` for routing-side tracks; the forecast environment for 1B). Record the commands and exit codes in the progress log.
- Evidence: the track's `research/<track>/README.md` opens with its headline numbers, every number has a producing script and recorded seeds, hashes and host, and a "Scope and limits" section exists.
- Honesty: no README claims field validation, physical accuracy, or a universal speedup. Grep for the words "validated", "proves", "guarantees", "safe" in the READMEs and check each use.
- Style: no em dashes anywhere in new prose, comments, figure labels or commit messages (grep for the character). Figures exist as PNG and SVG with captions.

## Step 4: integration checks (one additional subagent, after 1A and 1C-1 and 1C-3 have passed their gates)

Launch an integration agent in a worktree on a branch `next/integration` that merges the three passed branches (ownership guarantees no conflicts; if git reports one, stop and report) and then:

1. Runs track 1C's synthetic-truth harness with track 1A's radiation law v2 enabled (`radiation_law="v2"`) on campaign C1 and C4 and reports how the false-safe and false-refusal rates change versus law v1.
2. Runs track 1A's binding statistics on track 1C's trajectory members (K = 4 and 16) and reports whether peak and dose bind more or less often with coherent members.
3. Runs track 1C's SIPP equivalence tests on packets built by `bridge_v2.py` (trajectory members), confirming identical arrival seconds to the sweep on those packets as well.
4. Writes `research/next-combined/README.md`: one table with the three tracks' headline numbers, one table of the cross-track results above, the full list of commands, and a one-page "What changed in the scientific claims" section that a judge could read: what is now supported, what is still open, what is explicitly model-relative.

## Step 5: pull requests and human handoff

Open one PR per track branch and one for `next/integration` (titles given in the track prompts; the integration PR is "Next: combined evidence for radiation law v2, trajectory members, SIPP and synthetic-truth validation"). Do not merge any of them. End with a message to the human containing: the four PR links, the headline numbers, the acceptance-gate results, the ownership-check results, the open questions, and the recommended merge order (1C-1 export and members, 1A library, 1B, 1C-2 SIPP, 1C-3 harness, integration).

## Rules you enforce on yourself

- Never edit a track's files yourself; steer the agent instead.
- Never let a result be reported without its seeds, hashes and host.
- Never let "unresolved" be collapsed into "no route" or into "route" anywhere.
- Keep `docs/NEXT_PLAN.md` current; it is the record the human reads first.
- No em dashes.
