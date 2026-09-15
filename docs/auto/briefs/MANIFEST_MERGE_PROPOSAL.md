# Proposal — stop the artifact manifest conflicting on every pull request

Written 2026-09-15 by HQ after `docs/artifact_manifest.json` conflicted on **four consecutive
pull requests** (#36, #43 → #44, #45 → #47, #46 → #48). Needs an author decision before any
of it is applied; nothing here is implemented yet.

## 1. The measurement, before the argument

Every one of those conflicts was resolved the same way — throw both sides away and re-run
`scripts/build_artifact_manifest.py` — which is a strong hint that the file never actually
disagreed with itself. It did not. Re-played here with `git merge-file` on the real divergent
pair (base `45b4cce`, ours `1b84ccb` = K-SPREAD Stage 2, theirs `7fd0393` = refuge provenance),
both of which add artifacts:

```
conflict hunks: 1
  "generated_at_git_commit": ...   ours 6d7959f   theirs c1b29b5
  "n_artifacts":  144              ours 144       theirs 144
  "total_bytes":  26312833         ours 26312833  theirs 26460508
  "total_mib":    25.09            ours 25.09     theirs 25.23
```

**The `artifacts` body merged cleanly. The single conflict hunk is entirely the derived
header.** Two branches that each add a different artifact touch different regions of the
entry map, so git handles them; what they cannot both be right about is the summary block
that counts them.

Five top-level fields differ between any two such heads: `generated_at_git_commit`,
`n_artifacts`, `total_bytes`, `total_mib`, `n_git_tracked`. All five are **derived** — every
one is recomputable from `artifacts` by the builder that wrote them.

## 2. What follows

A union merge driver would not have helped and would have produced invalid JSON: these are
scalar fields with two genuinely different values, not two additions sitting side by side.
Splitting the manifest into one file per artifact would work but is a real refactor that
touches `scripts/verify_numbers.py`, and the measurement says it is not needed.

**Recommendation: delete the five derived fields from the tracked file.** The builder keeps
computing them and keeps printing them on the console line it already prints
(`wrote docs/artifact_manifest.json: N artifacts, X MiB, ...`), so nothing stops being
visible to a human running it; they simply stop being *stored* in a file two branches both
rewrite. `_README` stays — it is prose, it does not change per run, and it is the thing a
reader needs. On the measured pair this takes the conflict count from one to zero.

Expected cost: whatever reads those five fields must read them from `artifacts` instead.
`grep -rn 'n_artifacts\|total_mib\|total_bytes\|generated_at_git_commit\|n_git_tracked'`
over `scripts/`, `tests/` and `docs/` is the whole blast radius and must be surveyed before
this is applied — this proposal has NOT surveyed it, and that survey is the first step of
implementing, not of deciding.

## 3. What this does not change

The manifest's meaning, the `check-artifact-manifest` gate, the rule that a registry entry
must resolve to a tracked file or a manifest entry with a digest and a regeneration command,
and `scripts/verify_numbers.py`'s enforcement of it. Digests and regeneration commands are
per-artifact and are not touched. No number moves.

## 4. Why it is worth doing at all

It is not the minutes. It is that **the resolution is destructive by nature**: every time,
someone takes one side's file, discards it, and regenerates. That is safe only because the
file is derived — but it is the same motion as discarding a real change, performed routinely,
by whoever happens to be rebasing. Four repetitions in two days is enough to remove the
motion rather than keep performing it correctly.

## 5. The decision

Apply the recommendation in §2 (survey first, then delete the five fields), do the
per-artifact split instead, or leave it alone and keep regenerating. Author's call.
