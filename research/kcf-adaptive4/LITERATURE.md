# LITERATURE: what exists, what would be new (kcf-adaptive4, step 1)

Search done 2026-11-19: 11 web searches and one page read, about 40 minutes, under the 2 h limit.
**Limits, stated first.** Almost everything below comes from search-result summaries. One page was read in full (the
IAWF magazine article by Cruz and Alexander). The 2019 paper itself (Springer) and the 2020 evaluation (Environmental
Modelling & Software) could not be opened from this environment, so their error statistics are quoted only as far as
the summaries give them. No citation chasing. "New" means "not found in this search", not "proven absent".
`kcf-adaptive3/LITERATURE.md` covers regime models, blow-up days and conformal margins and is not repeated.

## (a) The 10% wind speed rule of thumb

| Item | What the sources say | Source |
|---|---|---|
| Rule | Forward rate of spread is roughly 10% of the 10 m open wind speed, in any unit system (25 km/h wind gives about 2.5 km/h) | Cruz & Alexander 2019, *Annals of Forest Science* 76:44, doi 10.1007/s13595-019-0829-8 (summary); IAWF article (read) |
| Purpose | A first approximation when there is little or no time for a fuller prediction | IAWF article (read) |
| Data behind it | 118 wildfire runs from three datasets in conifer forest, dry eucalypt forest and temperate shrubland | IAWF article (read) |
| Where it works | Dry fuel and strong wind; mean relative errors under 50% and reduced bias there | 2019 paper (summary) |
| Where it fails | Large over-prediction at low to moderate wind (under 20 km/h) and fine dead fuel moisture above 7%; over-prediction for fires spreading slower than 2 km/h; not for grassland | IAWF article (read); 2019 paper (summary) |
| Independent test | 350 runs from two databases (Monash/CFA eucalypt forest, Australia; BONFIRE, Portugal), filtered to wind above 30 km/h and fuel moisture below 7%: 88 runs; most within a +/-35% error band; no significant difference between the three fuel types; "at least as good as" operational spread models | Cruz, Alexander, Fernandes, Kilinc & Sil 2020, *Environ. Model. Softw.* 133:104818 (via IAWF article, read) |
| Not found | The averaging period of the wind; any statement about slope, fire build-up after ignition, or use over multi-hour horizons; MAE and bias values | - |

What this means for this folder. The rule is a statement about a **run** (a fire already spreading freely, in dry fuel,
in strong wind), with the **mean** open wind. Here it is applied (as RULE) to every issue hour, including the many
hours when the fire is not running, and to the forecast **gust**, because the issued 10 m mean wind is not among the
committed inputs. Both make RULE larger than the published rule. Korea in March is not one of the tested fuel
complexes (pine forest on steep ground is nearest to "conifer forest", untested for slope).

## (b) Data assimilation and parameter estimation for wildfire spread

| Work | What it does | How it differs from this folder |
|---|---|---|
| Mandel, Beezley, Coen & Kim 2007, arXiv 0712.3965; Beezley et al. 2008 (ICCS), arXiv 0801.3875; Mandel, Beezley & Kondratenko, arXiv 1001.1588 | Ensemble Kalman filter for a fire model coupled with WRF (later WRF-SFIRE); the "morphing" filter corrects position and amplitude together because a plain EnKF fails on a sharp fireline | Corrects the model **state** (the front). No statement of which input caused the error; no calibrated miss rate |
| Rochoux et al. 2014, *NHESS* 14:2951 (Part I) | EnKF that estimates **parameters** of a Rothermel-type spread rate (fuel and wind) from observed front positions | The filter moves every parameter in its control vector at once, weighted by ensemble covariances |
| Rochoux et al. 2015, *NHESS* 15:1721 (Part II) | EnKF on the front position; says the ensemble must vary both the initial fire location and the spread parameters; forecast skill at later lead times depends on the assimilation window | Joint state and parameter update; lead-time skill discussed, not tabulated as a growth rate |
| Zhang et al. 2019, *Frontiers Mech. Eng.* 5:8 (RxCADRE) | Ensemble transform Kalman filter that infers the wind from the front; "parameter estimation ... reduces model bias" | One experimental burn; wind is the only estimated input |
| Srivas et al. 2016, 2017 (ICCS; WIFIRE) | FARSITE with EnKF perimeter updates, hourly, 2014 Cocos fire; the 2017 version adds fuel adjustment factors to the updated state | State plus adjustment factors together |
| Zhou et al. 2019, *Fire Safety J.*; Yoo & Song 2023, *Environ. Model. Softw.* | Ensemble transform filter on FARSITE; EnKF with simplified perimeters for speed | Method variants of the same idea |
| arXiv 2510.15954 (Fire-EnSF, 2025) | Ensemble score filter on FARSITE; says EnKF and particle filters are the most used assimilation methods for fire | Preprint |
| arXiv 1909.05949; Yoo, Kwon & Cha 2025, *Remote Sensing* 17:2824; NHESS 14:1491 (2014) | Rate-of-spread **adjustment factors** per fuel model fitted to observed perimeters; says FARSITE, BEHAVE and Wildfire Analyst use such factors; parameters estimated in a window and held through the forecast | The nearest thing to "update k from the fire": one coefficient family tuned to the fire, by hand or by optimisation |
| Benali et al. 2016, *Sci. Total Environ.* ("Deciphering the impact of uncertainty ...") | Propagates uncertainty in wind, fuel, ignition location and timing through a spread model for eight large Portuguese fires, scored against satellite active fires; all of them matter | The closest to step 3: the same four kinds of term, but as **sensitivity to assumed input uncertainty**, not as an attribution of each observed miss |
| Hydrology: Wood & Lettenmaier 2008, *GRL* (reverse-ESP); Yang et al. 2014, *HESS* 18:775. NWP: Magnusson (ECMWF) "swap initial conditions" diagnostics | Swapping in perfect initial conditions or perfect forcing to split forecast error by source, and how the split changes with lead time | The methodological precedent for the swap design of step 3; not fire |

**Error growth with lead time.** The searches found statements that assimilation improves forecasts "at future lead
times" and that the assimilation window matters (Rochoux 2015; Zhang 2019), but **no table of perimeter or reach error
against lead time in hours for an operational fire-spread forecast**, and no reported growth rate. One model survey
quoted in the summaries gives mean rate-of-spread errors of 20% to 310% across 47 models (2013), which is an error at
one time, not a growth.

**Handing the error to a router.** Found: a 2026 preprint with conformal risk control on spread maps and
SAFE / MONITOR / EVACUATE zones (arXiv 2603.22331); evacuation routing on fire-forecast-weighted graphs (RESCUE,
ICDCN 2026); robust evacuation planning under demand uncertainty (Yang 2017 slides). None passes a per-hour,
per-lead forecast-error quantile from the spread forecast into the routing problem.

## What exists

- A wind-proportional spread law with a published coefficient (10%), valid for runs in dry, windy conditions.
- Filters that correct a fire forecast from observations, including filters that estimate wind and fuel parameters.
  They update **everything in the control vector together**, by covariance.
- Per-fire tuning of a spread coefficient (adjustment factors) as operational practice.
- Studies of how input uncertainty (wind, fuel, ignition place and time) spreads through a fire model.
- Swap-in-the-truth error splitting, in hydrology and weather forecasting.

## What would be new (not found in this search)

1. **Attributing each individual miss of a fire-reach forecast to one of its own terms** (wind input, coefficient,
   starting area, timing) by swapping in the truth, with shares for two regions. Benali et al. is the nearest, and it
   is a sensitivity study. Confidence that this is unpublished for fire: moderate (full texts were not read).
2. **Correcting only the blamed term** each hour, compared against updating all terms. The assimilation literature
   updates jointly; no comparison of "blamed term only" against "all at once" was found. Moderate.
3. **Error growth of a fire-reach forecast with lead time in hours, as a rate, on held-out fires**, and its change
   under online correction. Not found. Moderate.
4. **A calibrated, per-hour expected error at each lead handed to an evacuation router.** Not found. Moderate; the
   routing literature was searched with one query only.
5. Not new: the base model. It is the published rule with a learned coefficient.

Novelty of the combination is not evidence that it works. The test is in `RESULTS.md`.

## Sources

- https://link.springer.com/content/pdf/10.1007/s13595-019-0829-8.pdf
- https://www.iawfonline.org/article/evaluating-the-10-wind-speed-rule-of-thumb-for-estimating-a-wildfires-forward-spread-rate/
- https://research.csiro.au/pyropage/wp-content/uploads/sites/17/delightful-downloads/2021/05/CSIRO-PyroPage-Issue-30-ROSRuleofThumb-evaluation.pdf
- https://arxiv.org/pdf/0712.3965v1.pdf ; https://ar5iv.arxiv.org/html/0801.3875 ; https://ar5iv.arxiv.org/html/1001.1588
- https://nhess.copernicus.org/articles/14/2951/2014/ ; https://nhess.copernicus.org/articles/15/1721/2015/
- https://frontiersin.org/article/10.3389/fmech.2019.00008/full
- https://wifire.ucsd.edu/node/62 ; https://wifire.ucsd.edu/node/69
- https://arxiv.org/pdf/2510.15954 ; https://arxiv.org/pdf/1909.05949v1.pdf ; https://mdpi.com/2571-6255/5/3/58
- https://idlcc.fc.ul.pt/publications.php?id=334 (Benali et al. 2016)
- https://hess.copernicus.org/articles/18/775/2014/hess-18-775-2014.pdf ; https://zendy.io/title/10.1029/2008gl034648
- https://arxiv.org/abs/2603.22331v1 ; https://scholarsmine.mst.edu/comsci_facwork/2138
