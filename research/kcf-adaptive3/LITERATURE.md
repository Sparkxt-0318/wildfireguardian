# LITERATURE: what exists, what would be new (kcf-adaptive3, step 1)

Search done 2026-11-19, about 25 web searches, well under the 2 h limit. **Limits, stated first:** titles and links come
from search-result snippets; no full text was read. No citation chasing, and conference abstracts, theses and operational
systems (FSPro, FireSTARR, NGFS) were barely covered. Items marked (memory) were not returned by a search and are
unverified. Several 2025-26 arXiv items could not be checked for peer review. "New" below therefore means "not found in
this search", not "proven absent".

## 1. Regime-switching, hidden Markov and state-space models of fire growth

| Work | What it does | How it differs from the tracker here |
|---|---|---|
| Podur & Wotton 2011, *Int. J. Wildland Fire* 20:497, "Defining fire spread event days for fire-growth modelling" | Labels days as spread or non-spread from weather; improves a growth model | The label is observed and daily; no hidden state, no update from detections |
| Wang et al. 2014, *Global Change Biology* 20:2518; Wang et al. 2017, *Environ. Res. Lett.* 12:025005 (doi 10.1088/1748-9326/aa5835) | Potential and realised spread days across Canada; climate projection of their number | Zone-level climatology, not a per-fire sequential probability |
| Podschwit et al. 2018, *Environ. Ecol. Stat.* (doi 10.1007/s10651-018-0407-5) | Bayesian state-space growth curve with "pauses and pulses" from daily incident reports | Continuous latent growth rate, retrospective, no weather in the transition, no margin |
| Chavalithumrong, Yoon & Voulgaris 2021, arXiv 2111.14038 | HMM with a hidden fire state for weekly burned area | Weekly, regional; not hourly per fire |
| arXiv 2510.12916, coupled HMMs in continuous time | Per-cell hidden burn status behind smoke and cloud | The hidden state is a cell's burn status, not a fire-level behaviour regime |
| arXiv 1808.03318 | Likelihood of active-fire detections for assimilation into a spread model | Physics-model data assimilation |
| arXiv 2609.14951 (2026) | Covariates enter spread, ignition and cessation rates of a cell network | Cell level; a latent state is only proposed there |
| *PLoS ONE* 2013 (doi 10.1371/journal.pone.0063297) | Markov chain of daily incident complexity | Observed management states |
| Ameijeiras-Alonso et al. 2019 | Non-homogeneous hidden Markov random field for fire-occurrence seasonality | Spatial segmentation of occurrence |

## 2. Fire runs, blow-up days, extreme single-day growth

| Work | What it does | How it differs |
|---|---|---|
| Coop et al. 2022, *Global Ecol. Biogeogr.* 31:1949 (doi 10.1111/geb.13496) | Single-day extreme spread events (>1,100 ha) are 70% of area burned in the western USA | Retrospective statistics |
| Balch et al. 2024, *Science* (fast fires); Balch et al. 2022, *Nature* 602:442 (doi 10.1038/s41586-021-04325-1) | Fast fires dominate losses; the night-time barrier weakens | Descriptive |
| Srock et al. 2018, *Atmosphere* 9:279 (doi 10.3390/atmos9070279), Hot-Dry-Windy index; Haines 1988; Potter 2012, *IJWF* 21:779; Werth et al. 2016, PNW-GTR-891; Byram 1954/1959 (memory) | Weather indices and theory of blow-ups | Weather only; not conditioned on what the fire is doing |
| Liu et al. 2024, *ESSD* 16:1395 (GOFER); Chen et al. 2022 (FEDS); McClure et al. 2023, *IJWF* WF22048 | Hourly, 12-hourly and daily perimeter products | Data, no forecast |
| Holden et al. 2025 (RMRS) | Boosted trees on VIIRS daily growth, 196 fires; R2 0.36 to 0.56 when yesterday's activity is added | Daily point regression with a persistence input; no latent state, no calibrated margin |
| Shmuel & Heifetz 2023, *Fire* 6:319 (doi 10.3390/fire6080319) | Classifies next-day growth up or down | One-shot classifier |
| arXiv 2609.01675 | Quantile boosting (50 to 95th percentile) of next-day spread distance | Daily, one regime, not updated in sequence |

## 3. Online changepoint detection, calibrated margins, and the transition structure

| Work | What it does | How it differs |
|---|---|---|
| Adams & MacKay 2007, arXiv 0710.3742 (memory) | Bayesian online changepoint detection (BOCPD) | Generic method |
| Bottani et al. 2025, *Remote Sensing* 17:2822; Wendelberger et al., arXiv 2112.12899 | BOCPD for fire-induced forest loss and deforestation in satellite series | Burn mapping, not growth of an active fire |
| Xu et al. 2022, arXiv 2207.13250; Dayan, arXiv 2603.22331; Chakravarty, arXiv 2510.09666 | Conformal prediction for fire occurrence, for pixel spread maps, for buffers around firelines | One regime; daily; no state |
| Leite et al., arXiv 2512.03298; RareCP, arXiv 2605.08857 | Switching state-space model plus adaptive conformal inference, generic time series | Not fire; conditioning the margin on the inferred regime is listed as future work |
| Hughes & Guttorp 1994; Hughes, Guttorp & Charles 1999, *JRSS-C* 48:15 (doi 10.1111/1467-9876.00136) | Non-homogeneous HMM: transitions depend on atmospheric covariates (rainfall) | The methodological precedent for forecast-dependent transitions |
| Bengio & Frasconi 1994/1996, *IEEE Trans. Neural Networks* 7:1231 | Input-output HMM | Same |

## What exists

- The two-regime idea (spread day or not) is old and weather-driven: Podur & Wotton 2011, Wang et al. 2014.
- Growth "pulses" as a latent quantity exist in a retrospective, daily state-space model: Podschwit et al. 2018.
- Yesterday's growth plus weather predicts today's growth better than weather alone: Holden et al. 2025. This matches
  kcf-adaptive2 (own-past inputs carry the gain).
- Quantile and conformal margins on fire spread exist at daily resolution with a single regime.
- Covariate-dependent HMM transitions are a 30-year-old tool in hydrology.

## What would be new (not found in this search)

1. A per-fire hidden quiet/run state filtered **hourly** from satellite growth. Four differently worded searches
   returned only cell-level or weekly HMMs. Confidence that it is unpublished: moderate to high.
2. A transition into "run" driven by the **issued forecast**, so the state probability can rise before any spread is seen.
   Nothing found for fire. Moderate to high.
3. **State-specific quantile margins mixed by the state probability**, at a stated miss rate. No fire hits; the generic
   literature lists it as future work. The econometrics literature on Markov-switching quantile regression was not
   searched. Moderate.
4. Online changepoint detection on an active fire's growth series: two searches came back empty. Moderate.
5. An hourly, 5 h reach-distance margin checked at a stated miss rate on held-out fires. The nearest published work is
   daily. Moderate.

None of this says the tracker works. Novelty of the combination is not evidence of skill; the test is in `RESULTS.md`.
