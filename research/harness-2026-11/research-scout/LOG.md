# Research scout log (Sofia)

Running log of web research for the November 2026 harness. Each entry: source, date accessed, finding, and verification label.

- **VERIFIED**: the page or paper itself was read.
- **ABSTRACT/SNIPPET**: seen only in an abstract, a search-result snippet or a secondary summary.

Citations that could not be found are recorded as such; none are inferred.

## Access notes

- 2026-11-12: Direct `curl` from the scout container to `arxiv.org:443` and `www.yna.co.kr:443` is refused by the egress proxy (`CONNECT tunnel failed, response 403`). The WebSearch tool works. Pages are read through the session's search and fetch tools instead.

## Batch 1 (2026-11-12): mission A plus queue items 1-2

Pending.

### Queue item 2: S-D1 (Marcus) and S-D2 (Elena), accessed 2026-11-12

Labels: arxiv.org could not be reached in this session, so **nothing here is VERIFIED** (no full text read). "Abstract-level" means several independent search results agreed on the title, authors, venue and method. "Snippet" is weaker.

| Source | URL / ID | Finding | Label |
|---|---|---|---|
| Finney 2002, Can. J. For. Res. 32(8):1420 | https://research.fs.usda.gov/treesearch/25940 | Minimum travel time (MTT) fire growth: deterministic Rothermel edge times; no distribution and no data fit | abstract-level |
| Stepanov & Smith 2012, EJOR 218(3):775 | https://ideas.repec.org/a/eee/ejores/v218y2012i3p775-788.html | Delaunay triangulation plus shortest-path arrival times; deterministic | abstract-level |
| (no such title) "Spatial fire spread as first-passage percolation" | none | Not found; appears not to exist | n/a |
| Hajian, Melachrinoudis & Kubat 2016, Environ. Model. Softw. 82:73 | doi:10.1016/j.envsoft.2016.03.012 | Stochastic shortest-path fire spread; Monte Carlo over wind variability gives travel-time distributions. **Closest prior work for S-D1.** Not learned from progression data | abstract-level |
| Ganguly, Ali, Sanyal, Aneja & Sengupta 2026, arXiv:2609.14951 | https://arxiv.org/abs/2609.14951 | **Exists.** Continuous-time Markov lattice with covariate-dependent competing ignition hazards, fitted to 2018 California and 2019-20 Australia fires. Reportedly approximates interval-censored times by the first observation time and names full integration over censored paths as more complete. **Closest prior work for S-D2.** Markovian only | abstract-level plus quoted excerpt (excerpt not read directly) |
| Kenah & Robins 2007, Phys. Rev. E 76:036113 | arXiv q-bio/0610057 | Epidemic percolation networks: SIR spread as a random graph with passage times | abstract-level |
| Kenah 2015, JASA 110(509):313 | PMC4489164 | Pairwise survival models of transmission with covariates | abstract-level |
| Sharker, Diallo, KhudaBukhsh & Kenah 2024, Stat. Med. | doi:10.1002/sim.10226 | Pairwise accelerated-failure-time model with internal and external infection sources | abstract-level |
| Bu, Aiello, Xu & Volfovsky 2022, JASA 117(537):510 | n/a | Continuous-time network epidemic with data augmentation for unobserved event times | abstract-level |
| Zhenirovskyy et al. 2026, arXiv:2606.11676 | github.com/mzhen77/neural-ca-wildfire | **Exists.** CNN-parameterised probabilistic cellular automaton (discrete time); close to our current kernel model, not to S-D1/S-D2 | abstract-level |
| Grieshop & Wikle 2023, Spatial Statistics | doi:10.1016/j.spasta.2023.100794 | Bayesian stochastic cellular automaton with a latent spatio-temporal process; discrete time | abstract-level |
| Heracleum invasion lattice model (Cook et al.?) | https://core.ac.uk/download/30317897.pdf | Continuous-time lattice invasion with latent colonization times in a Bayesian likelihood; the machinery S-D2 needs, in ecology. Authors, year and venue not confirmed | snippet |
| Storey et al. 2021, Environ. Model. Softw. 144:105127 | n/a | Bayesian rate-of-spread model fitted to line scans; not spatial propagation | abstract-level |
| Veraverbeke et al. 2014, IJWF 23(5):655 | doi:10.1071/WF13015 | Kriged MODIS burn-timing maps; standard errors about 0.8-3.6 days | abstract-level |
| Parks 2014, IJWF 23(2):215 | doi:10.1071/WF13138 | Compares 10 day-of-burning interpolation methods | abstract-level |
| Canadian Fire Spread Dataset 2024, Sci. Data | https://www.nature.com/articles/s41597-024-03436-4 | Kriged day-of-burning plus about 50 covariates, offered for training | abstract-level |
| arXiv 2309.02615 (AIES 2024) | n/a | Conditional-GAN ensemble of arrival times with pixelwise standard deviation | abstract-level |

**Verdicts**

- **S-D1: incremental (high confidence).** Safe claim: first-passage spread whose *non-exponential, covariate-dependent* edge passage-time distributions are *learned from multi-fire daily progressions*, giving arrival-time distributions directly. Avoid claiming to be the first shortest-path, first stochastic MTT, or first continuous-time covariate spread model.
- **S-D2: incremental to partly novel in wildfire (moderate confidence).** Safe claim: an *exact* interval-censored likelihood for cell ignition times between consecutive satellite or perimeter observations, under neighbour-driven competing hazards with covariates. Optionally it could propagate kriging or interpolation variance into the likelihood; no prior work found does this. Avoid claiming to be the first survival or censored formulation of spread (Kenah, Bu et al., ecology invasion models). Do not say Ganguly et al. ignore censoring: they approximate it.
- **Open check:** read the Ganguly interval-censoring passage on arXiv when the host is reachable. Daniel could fetch the code repo `github.com/mzhen77/neural-ca-wildfire` and the Canadian Fire Spread Dataset if wanted.

### Queue item 1: F-3.1 deadline field (Richard), accessed 2026-11-12

Labels: WebFetch returned ENOTFOUND for arxiv.org, link.springer.com, content.csbs.utah.edu, digitalcommons.odu.edu and doaj.org, so **nothing here is VERIFIED**. SNIPPET means a search result quoted the abstract or record. MEMORY means the agent's own recall, not re-checked.

| Source | URL / ID | Finding | Label |
|---|---|---|---|
| Chabini 1998, TRR 1645:170 | doi:10.3141/1645-21 (DOI from MEMORY) | All-to-one, all-departure-times problem; the DOT algorithm sweeps departure times in decreasing order. Latest feasible departure per node is trivial from it. Discrete time, no hazard | SNIPPET |
| Dean 2004, MIT tech report | https://people.csail.mit.edu/bdean/tdsp.pdf | Latest-departure function LD_sd(t); FIFO all-to-one by reverse-chronological scans | SNIPPET |
| Orda & Rom 1990, JACM 37(3) | n/a | Waiting policies in time-dependent networks | MEMORY |
| Foschini, Hershberger & Suri, SODA 2011 / Algorithmica 2014 | doi:10.1007/s00453-012-9714-7 | Arrival functions can have n^Θ(log n) breakpoints: complexity caveat for exact fields | SNIPPET |
| Dibbelt, Pajor, Strasser & Wagner, CSA, JEA 2018 | arXiv:1703.05997 | Profile CSA: decreasing-time scan, Pareto (departure, arrival) profile for every stop to a target. **Closest algorithmic precedent** | existence SNIPPET; profile details MEMORY |
| Delling, Pajor & Werneck, RAPTOR/rRAPTOR | Transp. Sci. 2015 | Range and profile queries in timetables | MEMORY |
| Bakhtyar, Nguyen, Cetin & Nguyen 2016, J. Appl. Math. Phys. | https://digitalcommons.odu.edu/cee_fac_pubs/24 | Backward Dijkstra giving departure times at all source nodes for a required arrival; FIFO and non-FIFO; no hazard | SNIPPET |
| Chen, Mao, Bai, Li & Tang 2020, Transport 35(1) | doi:10.3846/transport.2020.12106 | Latest departure per O-D pair with last-service closure (analogue of edges becoming unusable) | SNIPPET |
| Cova, Dennison, Kim & Moritz 2005, Trans. GIS 9(4) | doi:10.1111/j.1467-9671.2005.00237.x | Reverse shortest path over the *fire* travel-time raster from an asset to set trigger buffers; evacuation time T is an input | SNIPPET |
| Li, Cova & Dennison 2015, CEUS 54:56 | doi:10.1016/j.compenvurbsys.2015.05.008 | "A household-level approach to staging wildfire evacuation warnings using trigger modeling": per-household trigger buffers ranked by lead time. **Closest wildfire precedent**; no road-edge hazard; T given. (No 2015 "reverse geocoding" title exists; a 2017 Applied Geography reverse-geocoding paper's title is unconfirmed) | SNIPPET |
| Li, Cova & Dennison 2019, Fire Technol. 55(2) | doi:10.1007/s10694-018-0771-6 | Triggers from coupled fire plus agent-based traffic simulation; probabilistic; community level | SNIPPET |
| Mitchell, Gwynne, Ronchi, Kalogeropoulos & Rein 2023, Safety Sci. 157:105914 | doi:10.1016/j.ssci.2022.105914 | PERIL: trigger perimeters from FARSITE plus evacuation time with a safety factor. k-PERIL stochastic follow-up in Fire Safety J. 140 (DOI uncertain). A paper titled "Using wildfire spread simulation to set evacuation zone timing" was **not found** | SNIPPET |
| WiSE (Wildfire Safe Egress), UCLA Garrick | https://www.risksciences.ucla.edu/girs-reports/2022/03 ; https://www.iapsam.org/PSAM18/papers/WA333-PSAM18.pdf | ASET vs RSET in a Bayesian network; WiSE 2.0 reportedly checks per vehicle whether fire reaches each segment first. Forward check, probabilistic | SNIPPET |
| Wahlqvist et al. 2021, Safety Sci. 136:105145 | n/a | WUI-NITY: FARSITE + pedestrian + traffic, forward simulation. "e-Sanctuary" not found | SNIPPET |
| Borgwardt et al., arXiv:2410.14500 | https://arxiv.org/abs/2410.14500 | Max-flow on time-expanded networks with fire-driven arc removal | SNIPPET |
| arXiv:2608.05413 | n/a | Supported-evacuation optimisation with soft and hard fire time windows on routes; metadata unverified | SNIPPET |
| Regnier 2008, Mgmt Sci 54(1):16 | doi:10.1287/mnsc.1070.0764 | Hurricane evacuation decision time vs track uncertainty; no network | SNIPPET |

**Verdict: incremental (confidence about 0.7).**

- The backward all-origins latest-departure sweep is classical (Chabini DOT, Dean, profile CSA, rRAPTOR, Bakhtyar 2016). Edge closures fit as deadline-capped FIFO arrival functions.
- The wildfire trigger literature reverses the *fire* spread with evacuation time as a scalar input; it does not search the road network backward against per-edge hazard.
- No work found combines: per-edge multi-criterion hazard (contact, flux, cumulative exposure), destination windows with required stays, complete-journey checks, and one backward pass for all nodes.
- Cumulative exposure is path-dependent (not FIFO-decomposable) and needs resource labels; exact handling would be the real technical contribution.

**Safe claim:** "To our knowledge, the first network-wide field of latest safe departure times under forecast wildfire road hazards from a single backward time-dependent search, adapting all-to-one latest-departure / profile techniques (Chabini; Dean; Dibbelt et al.) to edge hazard deadlines, destination windows with stays and complete-journey safety, and generalising household trigger buffers (Cova et al. 2005; Li et al. 2015), which take evacuation time as a fixed input."

**Avoid:** a new latest-departure or backward-search algorithm; the first per-household evacuation deadline; the first fire plus routing coupling; the first probabilistic timing; any complexity better than Foschini et al.; exactness under cumulative exposure without a proof.

**Read in full before publishing:** the CSA profile section, Li et al. 2015, WiSE 2.0 PSAM18, arXiv:2608.05413.
