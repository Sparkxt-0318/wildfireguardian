# Origin sparsity, and what it does to village-level delivery

**Artifact:** `data/processed/cluster_sparsity.json`
**Script:** `scripts/analyse_cluster_sparsity.py`
**Measured:** 2026-08-01

## ⚠ What these numbers are a property of

**These are sampled ORIGINS, not households.** Origins are taken by walking the
OSM node list at a fixed stride, so their spatial distribution reflects **road
network structure, not residential density**. A stretch of road with many mapped
nodes yields many origins whether or not anyone lives there; a dense hamlet on a
single short lane yields few. Every figure below inherits that.

So this measures the dispersion of the **sampled origin set**. Whether
Yeongdeok's actual settlements are equally dispersed is a related but separate
question, and this project holds no household data with which to answer it.
Everything below should be read as a property of the analysis, not of the county.

Values come from the 2026-07-24 snapshot re-run (441 origins), not from the
committed 439-origin figures — see [`network_drift.md`](network_drift.md).

## Why this was measured at all

Clustering the 174 origins needing rescue leaves **69.2 % of clusters holding a
single point** at eps = 500 m. Widening to 1500 m only reaches 45.2 %. A
parameter that refuses to help across a six-fold range is not mistuned; it is
reporting something about the data.

## Nearest-neighbour distance

| set | n | median | mean | p90 | max |
|---|---:|---:|---:|---:|---:|
| all origins | 441 | **196 m** | 353 m | 814 m | 4032 m |
| origins needing rescue | 174 | **418 m** | 624 m | 1450 m | 4032 m |

**The origins needing rescue are 2.13× more dispersed than origins in general**
(median nearest neighbour 418 m vs 196 m; p90 1450 m vs 814 m).

This is the more interesting half of the result, and it was not assumed — the
comparison set exists precisely so the rescue subset could be checked against the
whole. Isolation and needing rescue travel together in this sample: an origin far
from its neighbours tends to be far from a refuge and far from a depot, which is
what puts it in the rescue set in the first place. The direction is what one
would expect; the size of the gap was not known before measuring.

## The eps sweep

| eps | clusters | singletons | singleton % | max cluster | largest cluster as % of all points |
|---:|---:|---:|---:|---:|---:|
| 250 m | 143 | 120 | **83.9 %** | 8 | 4.6 % |
| 500 m | 107 | 74 | **69.2 %** | 16 | 9.2 % |
| 750 m | 82 | 48 | **58.5 %** | 16 | 9.2 % |
| 1000 m | 63 | 31 | **49.2 %** | 24 | 13.8 % |
| 1500 m | 31 | 14 | **45.2 %** | 38 | 21.8 % |
| 2000 m | 17 | 6 | 35.3 % | 91 | **52.3 %** |
| 3000 m | 5 | 2 | 40.0 % | 168 | **96.6 %** |

**The singleton fraction does fall below 40 %, but only after clustering has
stopped being clustering.** At 2000 m the largest cluster holds 91 of 174 points
— more than half the county's rescue set in one "village" — and at 3000 m it
holds 168 of 174. Neither is a village-scale audience.

Restricting to radii where no cluster exceeds 25 % of all rescue points
(250–1500 m), **the singleton fraction never goes below 49.2 %.**

An earlier draft of this document asserted the fraction never drops below 40 % at
any radius. The artifact contradicted it, and the claim was corrected rather than
the range quietly truncated.

## Operational implication

A village broadcast addresses a cluster. **Where a cluster is one point, there is
no village-level audience to address.** At the configured 500 m radius that is
true of 74 of 107 clusters; even at 1500 m it is true of 14 of 31.

The channel and the geography do not line up over a substantial part of the
region. Restated plainly: village-scale delivery — the 마을방송, and a 이장's
single sheet — is a good fit for the clustered minority and a poor fit for the
dispersed majority of this origin set.

This is recorded as an observation. **No remedy is proposed here.**

## What would sharpen it

Real household locations would separate "the road network is sparse here" from
"people are sparse here". The two are correlated in rural Korea but not
identical, and only the first is measured above.
