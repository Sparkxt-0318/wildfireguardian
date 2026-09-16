# WildfireGuardian research program

Three research directions that test rules Korea already uses for wildfire
planning against what real Korean fires actually did. Everything here is
separate from the Korea Code Fair finals build, which is frozen until the
October 2026 finals in Gwangju.

## The three questions

| # | direction | question | deliverable layer |
|---|---|---|---|
| 1 | `roads/` | When a real Korean fire front reached a forest road, river or ridge, did it hold, and what made it fail? | road barrier and access ratings |
| 2 | `landslides/` | How long does a burned Korean slope stay more landslide-prone, and does the window differ between pine and oak? | post-fire landslide warning adjustment |
| 3 | `suppression/` | Recorded fire sizes are cut short by firefighting. Which fires would have grown large, and can that be flagged in the first hours? | early escape-risk score |

Program priority order is roads first, then landslides, then suppression.
Phases 1 to 4 run for roads before the same phases start for landslides.

## Scope rules

These are non-negotiable and every agent works under them.

1. **Korea only.** Every dataset used for fitting, validation or results must
   cover South Korea. Foreign studies may be cited as prior art or as the
   source of a method or an equation. Foreign fire, road or landslide data is
   never pooled into a Korean model.
2. **Computation and public or low-cost data only.** No human-subject research,
   no field work, no paid data above USD 100 total without the author's
   approval.
3. **Do not touch the finals build.** No edits to `src/wildfireguardian/`, the
   demo, the posters or existing tests. The one allowed exception is the FIRMS
   feed fix, which lives on its own branch and is not merged.
4. **Compute.** Everything runs on one Apple M4 Pro laptop. No HPC, no WRF, no
   GPU training. Bayesian models use PyMC or Stan; comparison models use
   scikit-learn.
5. **Writing style.** No em dashes anywhere, including code comments, docs,
   commit messages and reports.
6. **Provenance.** Every number that could appear in a poster, paper or README
   is registered in `docs/NUMBERS.json` with its source file, script and commit.
   The repository's existing automated gates keep passing.
7. **Claims discipline.** The three questions are hypotheses. They are listed in
   the forbidden-claims registry in hypothesis wording. No agent writes a result
   as fact until the validation agent signs it off.

## Where things live

```
research/
  README.md                 this file
  TASKBOARD.md              single source of truth for task status
  DECISIONS.md              dated log of design decisions and why
  data/
    REGISTRY.yaml           one entry per dataset
    raw/                    immutable downloads, never edited
    interim/                cleaned and harmonized
    processed/              model-ready tables
    checks/                 re-runnable verification scripts, one per dataset
  shared/                   loaders, geocoding, solar times, CV splits, plot style
  roads/                    direction 1 in priority, road and barrier breach
  landslides/               direction 2 in priority, post-fire landslide clock
  suppression/              direction 3 in priority, suppression as censoring
  scenarios/                optional climate step, phase 5
  eval/                     shared evaluation harness and reports
  lit/                      prior-art notes and verified bibliography
  reports/                  per-agent run reports
```

Large raw files are git-ignored. Their `REGISTRY.yaml` entries carry the URL,
checksum and access date, so anyone can re-download them exactly.

## Status

See `TASKBOARD.md`. Items needing the author sit under "Waiting on John" there,
each with a one-line action, so they can be cleared in a single sitting.
