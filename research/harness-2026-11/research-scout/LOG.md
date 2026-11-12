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

### Mission A, accessed 2026-11-12

See `MISSION_A.md`: 15 Korean and 18 international findings, plus a village-level timeline for 25-26 March 2025. All are SNIPPET-ONLY.

### Queue item 3: F-3.2 certificates (Thomas), accessed 2026-11-12. Abstract/metadata level

| Source | ID | Finding |
|---|---|---|
| McConnell, Mehlhorn, Näher & Schweitzer 2011, CS Review 5(2):119 | doi:10.1016/j.cosrev.2010.09.009 | Certifying-algorithms framework; static shortest-path certificates via potentials |
| Alkassar, Böhme, Mehlhorn & Rizkallah, CAV 2011 / JAR 52(3) 2014 | doi:10.1007/978-3-642-22110-1_7 ; arXiv:1301.7462 | Verified checkers (VCC plus Isabelle); static graphs |
| Rizkallah PhD 2015, Saarland | https://publikationen.sulb.uni-saarland.de/handle/20.500.11880/26674 | Shortest-path checker chapter |
| Shokry et al. 2024 | arXiv:2412.06121 | Linear-time static SSSP verifier |
| Eriksson, Röger & Helmert, ICAPS 2017 / 2018 | doi:10.1609/icaps.v27i1.13818 ; doi:10.1609/icaps.v28i1.13899 | Unsolvability certificates checked by an independent validator; untimed |
| Wimmer & von Mutius, TACAS 2020 | doi:10.1007/978-3-030-45190-5_24 | Verified certificate checker for timed-automata unreachability. **Novelty risk** |
| Wang & Abdulaziz 2025 | arXiv:2510.10189 | Verified unsolvability certificates for temporal planning. **Novelty risk** |
| Cheung, Gleixner & Steffy, IPCO 2017 (VIPR) | doi:10.1007/978-3-319-59250-3_13 | Exact MIP certificates |
| Phillips & Likhachev, ICRA 2011 (SIPP) | n/a | Safe-interval search; no certificate output |
| Orda & Rom 1990, JACM 37(3) | doi:10.1145/79147.214078 | Waiting policies (unrestricted, forbidden, source) |
| Zeitz 2023, IPL 179:106287 | n/a | Earliest arrival is NP-hard for non-FIFO networks with waiting disallowed. This implies a single-label certificate cannot work in general (inference) |
| Basch et al. ICRA 2001; Varava et al. arXiv:2002.02715; Marcucci et al. T-RO 2024 | n/a | Motion-planning disconnection and infeasibility proofs; static |

**Verdict: incremental new combination (~65%).** No source claims that a single earliest-arrival label is a sound dual under forbidden waiting. Certificates should use (node, safe-interval) states.

### Queue item 4: F-4.2 margin routing (Priya), accessed 2026-11-12. Snippet level

| Source | ID | Finding |
|---|---|---|
| US Patent 9,530,304 "Distributed sensor network" | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9530304 | Ranks routes by "safe time remaining" (minimum fire arrival over waypoints); shelter if none is safe. **Must cite** |
| WiSE, PSAM16 MH163 | https://www.iapsam.org/PSAM16/papers/MH163-PSAM16.pdf | ASET/RSET margin from 500 FlamMap runs; evaluation only |
| Sheng et al. 2024, IJWF 33(3) WF23166; Wang, Sheng et al. 2024, Fire 7(12):459 | https://www.publish.csiro.au/WF/WF23166 ; https://mdpi.com/2571-6255/7/12/459 | Firefighter escape routes with safety windows; weighted-sum objectives |
| Yu & Yang 1998; Bertsimas & Sim 2003; Montemanni & Gambardella 2004; Nikolova et al. ESA 2006 | n/a | Robust and reliable shortest paths; uncertainty in travel time |
| Lindemann et al. 2023 (arXiv:2210.10254); Dixit et al. 2023 (arXiv:2212.00278) | n/a | Conformal prediction in MPC planning |
| Liang et al. CP-SIPP, L4DC 2026 | arXiv:2511.18170 | Conformal safe intervals on space-time graphs. **Closest for (b)** |
| Dayan 2026 | arXiv:2603.22331 | Conformal risk control on wildfire spread maps; no routing |
| Fan, Kalaba & Moore 2005 | n/a | **Not located**; do not cite its details |

**Verdicts:** (a) margin-maximizing routing is incremental (~65%); (b) conformal margins are novel in this application (~60%).

### Queue item 5: F-C1 viewshed and see-before-leave (Leo), accessed 2026-11-12. Abstract/snippet level

| Source | ID | Finding |
|---|---|---|
| Li, Cova & Dennison 2017, Appl. Geog. 87:14 | doi:10.1016/j.apgeog.2017.05.008 | Viewshed used to rank trigger landmarks. **Closest prior work** |
| Larsen, Dennison, Cova & Jones 2011, Appl. Geog. 31:12 | n/a | "Evaluating dynamic wildfire evacuation trigger buffers using the 2003 Cedar Fire" |
| Cova et al. 2017, Risk Analysis 37(4):601 | doi:10.1111/risa.12651 | Observed cues used as triggers |
| Mistick et al. 2022, Fire 5(5):151 | n/a | Coarse DEMs overestimate visibility by up to 223%; use a DSM |
| IJWF 15(2):197 (2006) | doi:10.1071/WF04016 | Lookout effective detection radius 13.4-20.6 km |
| Kuligowski et al., NIST TN 2103 (2020); IJWF doi:10.1071/WF20038 | https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2103.pdf | 81.4% of Gatlinburg evacuees decided after fire cues |
| McCaffrey, Wilson & Konar 2018, Risk Analysis 38(7):1390 | doi:10.1111/risa.12944 | Reliance on cues raised the odds of wait-and-see by 158% |
| Lindell & Perry 2012 PADM; Strahan & Gilbert 2021, Fire 4(1):4; Strahan, Whittaker & Handmer 2018 | n/a | Decision-model and wait-and-see literature |
| Marshall Fire 2021, Travel Behaviour & Society | n/a | Cues not significant: a counterexample |

- Night-glow visibility distance: none found.
- Korean study of cue-driven delay: none found.

**Verdict: novel, moderate (~65-70%).**

### Queue item 6: S-D9 benchmark (Victor), accessed 2026-11-12

Labels: VERIFIED means the Zenodo record metadata was read through its API (zenodo.org is reachable). Everything else is SNIPPET.

| Source | ID | Finding |
|---|---|---|
| WildfireSpreadTS, Gerard et al., NeurIPS 2023 D&B | zenodo 8006177 (VERIFIED) | 607 US fires 2018-21, next-day binary target, AP; leave-one-year-out; one horizon |
| WSTS+ | arXiv 2502.12003 | Adds years; UTAE about 0.452 AP |
| "Unobserved but Burning" WSTS annotations, WACV 2027 | zenodo 23876108 (VERIFIED) | 1,732 unreliable-negative fire-days plus an observation-aware protocol |
| AFSeq "From Next Day Wildfire to Next Days Wildfire" | arXiv 2610.38086 | Multi-day seq2seq, 1,194 events, leave-one-region-out. **Closest competitor**; could not be re-found |
| Gopakumar & Pannozzo 2026, "WildfireSpreadBench: The Metric Decides the Model…" | arXiv 2609.22191 | **Found.** Top-AP model over-predicts area 4-5×. No proper scores; one horizon |
| Huot et al. 2022, TGRS (NDWS) | doi:10.1109/TGRS.2022.3192974 | Weekly split; fires can leak across splits |
| GOFER, ESSD 16:1395 (2024) | zenodo 14642378 (VERIFIED) | Hourly GOES perimeters, 28 California fires |
| ELMFIRE validation set | zenodo 23574586 (VERIFIED) | Arrival-time rasters for 31 fires |
| NIROPS perimeters, W. US 2020-24 | Mendeley 10.17632/95rj5d379g | 737 incidents, 12,705 perimeters |
| Allaire, Filippi & Mallet 2020, IJWF 29(2):160 | doi:10.1071/WF19073; HAL hal-02447187 | Monte Carlo fire ensembles scored probabilistically (Brier) on 7 Corsican fires. **Brier on spread maps is not new** |
| arXiv 2609.17763; 2605.03148 | n/a | Brier/ECE on next-day ML spread maps |
| arXiv 2603.26975 | zenodo 19599116 (VERIFIED) | Flow-matching arrival-time surrogate; scores unread |
| WeatherBench 2, Rasp et al., JAMES 2024 | n/a | Fixed lead-time-stratified protocol with CRPS |
| Bracher et al. 2021, PLOS CB | n/a | WIS ≈ CRPS; FluSight's truncated log score is improper |
| Filippi et al. 2014, IJWF 23:46; NHESS 14:3077 | n/a | Spread-score review; metric choice changes rankings |
| FireGraphNet arXiv 2610.19191; DailyWildfireCAN arXiv 2611.14207 | n/a | **Could not be re-found / contradicted.** Do not rely on them |

- CRPS on fire arrival time: no precedent found.
- Formal pre-registration of FluSight: unverified.

**Verdict: incremental but a real gap (~0.65).**

## Sources that most need a full read

These are the sources on which a verdict or quoted number depends, ordered by priority. All are currently SNIPPET or abstract-level only.

1. Ganguly et al. 2026, arXiv:2609.14951: the interval-censoring passage that the S-D2 novelty rests on.
2. Hajian, Melachrinoudis & Kubat 2016, doi:10.1016/j.envsoft.2016.03.012: whether edge-time distributions are fitted to data (S-D1).
3. Li, Cova & Dennison 2015 CEUS and 2017 Appl. Geog. (doi:10.1016/j.apgeog.2017.05.008): household triggers and the viewshed (F-3.1, F-C1).
4. Dibbelt et al. CSA profile section, arXiv:1703.05997, and Chabini 1998: backward all-origins precedent (F-3.1).
5. WiSE 2.0, PSAM18 WA333, and arXiv:2608.05413 (F-3.1, F-4.2).
6. Wimmer & von Mutius, TACAS 2020; Wang & Abdulaziz, arXiv:2510.10189; Zeitz 2023, IPL 179 (F-3.2).
7. US Patent 9,530,304: whether its margin subtracts vehicle arrival (F-4.2).
8. CP-SIPP, arXiv:2511.18170; Dayan 2026, arXiv:2603.22331 (F-4.2 b).
9. AFSeq, arXiv 2610.38086; Gopakumar & Pannozzo, arXiv 2609.22191; arXiv 2603.26975 evaluation section (S-D9).
10. Kuligowski et al., NIST TN 2103: the 81.4% cue figure (F-C1).
11. Mission A numbers: LA County AAR PDF; FSRI Lahaina reports; Greenpeace Korea survey PDF (percentages); BAI audit (1 h 39 min, 41.8%); 행안부 2025-04-16 release (5 h / 8 h zones); Nocut KFS data (2 of 8 h forecast).

## Batch 2 (2026-11-12, network open): sources read in full

### F-3.2 certificates (Thomas): revised after reading the sources

**Read:**

- Zeitz, IPL 2023: https://publikationen.bibliothek.kit.edu/1000147976/148924256
- Wimmer & von Mutius, TACAS 2020: https://home.cit.tum.de/~wimmers/papers/TA_Reachability_Certification.pdf
- Wang & Abdulaziz: https://arxiv.org/pdf/2510.10189v2
- SIPP-IP (Ali & Yakovlev, AAAI 2023): https://arxiv.org/pdf/2302.00776v1
- Orda & Rom 1990: https://sites.cs.ucsb.edu/~suri/cs231/Rlist/ordaRom.pdf

**What the sources show:**

- **SIPP-IP Statement 1** already gives the counterexample: SIPP is incomplete when some states are non-waitable. Its fix is (vertex, waiting interval) labels with interval projection, proven complete and optimal under integer durations. Credit it.
- **Zeitz:** SubsetSum chain whose final edge is passable only at τ = B, a window that cannot be waited out. Weakly or strongly NP-hard; pseudo-polynomial in integer ticks. The reduction transfers to mixed waitability.
- **Orda & Rom:** under forbidden waiting, optimal paths may contain loops, or may need to be infinite. They cite Halpern 1977, where waiting is allowed only in set intervals; this is the closest model to ours.
- **Wimmer:** the certificate is an admissible set (invariant, closed under monotone subsumption, covers the initial state, no state in F, with F a predicate on discrete states). It certifies unreachability only.
- **Wang & Abdulaziz:** only the unsolvability direction is proved, about 18k lines of Isabelle, no experiments; optimality certificates are called "much harder".

**Ideas:**

1. Integer ticks, rounded conservatively.
2. SIPP-IP labels, with subsumption by interval inclusion.
3. A no-route certificate in Wimmer's admissible form.
4. An optimality certificate: a witness plus unreachability of a discrete "goal-early" flag. This is the apparent contribution.
5. Pareto subsumption on dose.
6. An optional timed-automaton export for cross-checking with Muntac.

**Downloaded material:** PDFs and extracted text are in the scout session's scratchpad `dl/` folder.

### Batch 2: ideas from sources read in full (2026-11-12)

Each bullet gives the source, then the idea and the stream it serves. Every source listed here was opened and read. Sources that could not be opened are listed at the end of this batch.

**Korea**

- Greenpeace Korea survey (n=297): only 62% received the disaster text; broadcast and neighbours outranked the text (237 vs 112); 16.5% left in a neighbour's car; 92% of shelter users were moved at least once.
  - Coupled driver/passenger deadlines (F-3.1).
  - Certify the shelter for the whole stay plus the onward leg (F-4.2, F-3.2).
- 행안부 2025-04-16 plan (newsseoul 1065591618401273): 5h/8h zones; 27.6 m/s worst case when the fire line is unknown; facilities must be out before sunset; elderly walking speed 72% of normal.
  - Use as the official baseline on KFS_01 (S-D9).
  - Sunset as a deadline constraint (F-3.1).
- Nocut 6409424: KFS provided 2 h of an 8 h forecast and did not re-run after spot fires.
  - Horizon-value experiment (S-D9).
  - Re-run on spot-fire detection (F-3.1).
- BAI audit (newsis NISX20251023_0003373693): texts averaged 1h39m from situation room; 41.8% never sent.
  - Issue-order-by field (F-3.1, F-C1).
- Hankook Ilbo A2025032714350000238: a son assumed his parents were safe because their 읍 was not named in the text; both died.
  - Explicit "not ordered yet — leave by" message for every village.
- Kyunghyang 202503261311001: 104 people trapped on breakwaters.
  - Refuge nodes (F-4.2).
- Nocut 6318424 (임하 신덕1리): about 10 minutes from first sight to arrival (F-C1).

**Abroad**

- LA County AAR, Eaton synopsis (file.lacounty.gov 1192777): aircraft grounded 27 minutes after ignition; rumour that the fire was "moving east".
  - Intel-blind benchmark mode (S-D9).
  - Publish uncertainty in fire direction (F-C1).
- Citygate Eaton alert investigation (file.lacounty.gov 1208708): command learned of the westward spread at 2:18; orders at 3:25; front crossed at about 5:13; probable ember cast 1 mile; warning adjacent zones was not policy.
  - Ember-keyed deadlines.
  - Auto-flag adjacent zones (F-3.1).
- Spokesman-Review on MonteCedro: night staff absent; 2 residents missed.
  - Facility timing chain to the last resident out (F-3.1, F-3.2).
- NIST TN 2252 (Camp NETTRA): Concow order 07:37, burnovers from 07:50; spotting 6 km ahead; at least 2 of 4 arteries closed 68% of the time; 31 refuge areas; Table 12 gives order and burnover times.
  - Margins that survive k closures (F-4.2).
  - Name a refuge in every no-route certificate (F-3.2).
  - Ground truth (S-D9).
- NIST TN 2103 (Chimney Tops 2): 74.6% acted on cues; among cues, smoke 92.5%, embers 46.5%, flames 43.2%.
  - Cue-ladder viewshed (F-C1).
- FSRI Lahaina Phase 1 and 2: about 75 minutes from reignition to Front St; locked gates; unmaintained dirt egress roads.
  - Conditional edges listed in certificates (F-3.2, F-4.2).
- NSW Bushfire Inquiry, Rec 73: compliant plans for aged-care facilities.
  - A "stay" certificate (F-3.2).
- PBS Frontline (Camp): 7,000 of 52,000 evacuees received an alert.
  - Model alert reach per origin (F-C1).

**Spread models**

- Ganguly 2026 (arxiv html 2609.14951): approximates event times by the first observation and assigns ignition cause by rule; the authors call this biased; precision@k evaluation.
  - S-D2 baseline and evaluation protocol.
- Kenah & Robins 2007 (q-bio/0610057): epidemic percolation networks with a shared recovery time per node.
  - S-D1 construction.
  - Per-edge exponential clocks for time-varying weather.
- Bu et al. 2022 (arXiv 1910.04221): DARCI data augmentation.
  - DA-MCMC over ignition times (S-D2).
- Zhenirovskyy 2026 (arxiv html 2606.11676): wind and slope cosine factors; no held-out fire.
  - Edge-rate form and baseline (S-D1).
- Veraverbeke 2014 (jin.ucdavis.edu): kriging standard errors of 0.8-3.6 days.
  - Label noise (S-D2).
- CFSDS (nature s41597-024-03436-4): no per-pixel uncertainty released; detections shifted to 19:00.
  - Fit to raw detections instead (S-D2).
- FPP survey (arxiv html 1511.03262): shape theorem; eikonal limit; t^{1/3} fluctuations.
  - Diagnostics (S-D1).
- FlamMap MTT help page: multi-cell segment edges.
  - Stencil choice and zero-variance baseline (S-D1).

**Routing**

- CSA (arXiv 1703.05997): decreasing-time profile scan with front insert.
  - Deadline-field algorithm (F-3.1).
- Dean TDSP: waiting closure applied only at waitable nodes; O(mT) exact reference; post-burnout pitfall (F-3.1).
- Li, Cova & Dennison 2015 and 2017 (csbs.utah.edu reprints): REDT and SKATER zoning; cumulative-viewshed prominence.
  - Baseline and output layer (F-3.1).
  - Inverted trigger landmarks (F-C1).
- PERIL slides and lup.lub.lu.se records: safety factor ASET/RSET; uncertainty rosettes.
  - λ* and δ* rosettes (F-4.2).
- WiSE 2.0 (PSAM18 WA333): vehicle is safe if RSET ≤ SSET on every segment.
  - Metric suite (F-4.2).
- CP-SIPP (2511.18170) and Lindemann (2210.10254): a max-score over a fixed region gives a route guarantee without a union bound (F-4.2).
- Moradi et al. (2608.05413) and Borgwardt et al. (2410.14500): soft/hard time windows; time-expanded max-flow.
  - Capacity-aware deadline (F-3.1).

**KFS_01 / NIROPS fact check (pages read)**

- The box matches the FIRMS S-NPP detection envelope (36.336-36.590°N); there is no northern clip.
- A second ignition, Angye at 14:36 KST, lies inside the box.
- Grid area is 1,540 km² against KFS's 993 km²: inflated.
- NIROPS public files: PolygonDateTime is empty; flight time appears only in Comments; no "Area Covered by IR Flight" layer was found in 32 zips.

**Could not open:** patents.google.com and mdpi.com (DNS failed for the agents), NUREG/CR-7002 (403), ScienceDirect (Hajian 2016, 403), the original mois.go.kr press release, the full BAI report, the NARS PDF.

Downloaded PDFs and extracted text are in the scout session's scratchpad (`dl/`, `dl2/`).

### Follow-up requests (2026-11-12)

**Marcus, P(T_x ≤ t) estimators.** All sources read except Juneja et al. (abstract only).

- L'Ecuyer, Puchhammer & Ben Abdellah, arXiv 1906.04607: cut-set conditional Monte Carlo (CMC).
  - Idea: use the in-edges of x as the cut, which gives a closed-form exponential race with the burn-window cap.
- Botev, L'Ecuyer, Simard & Tuffin, GERAD G-2015-12: permutation Monte Carlo (PMC) and turnip; applicable when the spread is a CTMC.
- Botev, L'Ecuyer & Tuffin, arXiv 1805.03326: generalized splitting for large networks.
- Wan & Fu, WSC 2020: smoothed IPA for unbiased gradients.
- Juneja, Karandikar & Shahabuddin, TOMACS 2007: path-mixture importance sampling for the tails (abstract only).
- Berthet et al., arXiv 2002.08676: a relaxation is not needed here, because the exponential clocks already smooth the objective.
- Lokhov, Mézard & Zdeborová, PRE 2015: dynamic message passing as a surrogate.
- FSPro/FSim: scenario Monte Carlo of MTT runs only.
- Conclusion: no fire-spread work using CMC, IS or splitting estimators was found.

**Richard, latest-departure sets.**

- Closest precedent: Brunelli & Viennot, arXiv 2211.12136 (read). It does a backward edge scan per destination and builds unions of start-time intervals under per-node waiting bounds.
- Himmel et al., arXiv 1909.01152: per-node α/β waiting bounds; β = 0 models a no-wait node.
- Casteigts et al., arXiv 1909.06437: hardness holds for paths only, not for walks.
- Halpern 1977 and Sancho 1992: original model with absolute waiting windows (read through secondary summaries).
- Delling, Pajor & Werneck (rRAPTOR, ALENEX 2012) and Witt (Trip-Based, ESA 2015): profile queries; both assume free waiting.
- Thomas et al., any-start-time SIPP, arXiv 2610.03312: forward arrival-time functions with free waiting.
- Kerimov et al., SI-RRT, arXiv 2412.19567: backward goal tree.
- Li, Cova & Dennison 2019: no exact backward computation.
- No precedent found for:
  - a finite hazard-free dwell on arrival;
  - a per-origin certificate;
  - an exact backward-set algorithm with absolute waiting windows.

**Thomas, W-KIT message rules (2026-11-12).** Sources were opened unless marked snippet.

Governing rule: 「재난문자방송 기준 및 운영규정」 (행안부예규 제361호, 2026-02-04; law.go.kr admRulSeq=2100000274384, plus annexes 별표1 and 별표2).

- 제10조② requires the issuing agency's name in every message.
- Length limits appear only as annex labels "90자" and "157자", which count characters, not bytes.
- 별표1 sends a pre-evacuation advisory (사전대피 권고) as an 안전안내문자, which uses the normal notification sound. An evacuation order goes as a 긴급재난문자 at 40 dB or more.
- 별표2 wildfire templates #153, #154 and #155 (advisory, order, order lifted) are each 90 characters and put [기관명] (agency name) last.

Related releases:

- 2025-08-27: messages must say 언제·어디로·어떻게 (when, where to, how); capacity to go from 90 to 157 characters in stages.
- 2026-02-26: evacuation messages must go out as 위급재난문자 or 긴급재난문자.
- 매일신문 2026-10-12: 157 characters applies to 안전안내문자 only; 위급 and 긴급 stay at 90.

Research on message content:

- NIST TN 1982 and TN 2008: five message elements; put the source first; for 90-character messages, order them source, guidance, hazard, location, time.
- Mileti & Sorensen 1990: could not open.

Not found:

- Official guidance on village-broadcast (마을방송) length or repetition.
- A real evacuation ARS script with key-press replies. The closest is the 진천 welfare ARS, which is not for evacuation.
- Guidance on announcing or limiting shelter changes.
