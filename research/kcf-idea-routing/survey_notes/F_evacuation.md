LITERATURE SURVEY: evacuation planning, wildfire emphasis, hazard-dependent road availability

`date -u` at start: Wed Nov 18 22:53:06 UTC 2026. At end: Wed Nov 18 23:02:25 UTC 2026. (About 9 minutes of wall time, well under the 25-minute budget; the survey is broad but not exhaustive. No project files were written; PDFs were only text-extracted into the session scratchpad.)

Headline: I found no published method that returns per-place leave-by time as an exact function of a spread-rate margin over a road graph with closing/reopening segments, no exact incremental update of evacuation deadlines after a single closure report, and no single-pass "benefit of delaying fire at every location" for evacuation time. These are "not found in this search", not proofs of absence.

## A. Sources opened and read in full text (PDF text extracted and searched)

1. **Cova, Dennison, Kim, Moritz (2005).** "Setting Wildfire Evacuation Trigger Points Using Fire Spread Modeling and GIS." Transactions in GIS 9(4):603-617.
   - URL: https://content.csbs.utah.edu/~pdennison/reprints/denn/2005_Cova_etal_TGIS.pdf
   - Method: three steps. (1) FlamMap rate of spread per raster cell in 8 directions; (2) a fire travel-time network between adjacent cells; (3) reverse all arcs and run Dijkstra from the community cell with a modified stop: "the algorithm terminates at the first cell that exceeds the original evacuation time estimate."
   - The buffer is the set of cells from which fire "could" reach the community in less than the evacuation time T (shortest, not most likely, path). Nested 15/30/45-minute buffers are shown.
   - Stated limit: "The trigger buffer is also only valid for the given wind speed and direction, so it would have to be recomputed as wind conditions change."
   - Relation: an exact backward shortest-path deadline field, but on the fire raster, not the road graph. Evacuation time T is a scalar input; there are no road closures, no parametric spread rate, no incremental update.

2. **Dennison, Cova, Moritz (2007).** "WUIVAC: a wildland-urban interface evacuation trigger model applied in strategic wildfire scenarios." Natural Hazards 41:181-199.
   - URL: https://content.csbs.utah.edu/~pdennison/reprints/denn/2007_Dennison_etal_NatHaz.pdf
   - Method: runs WUIVAC for Julian, CA under worst-case wind speed in each of 16 directions (8 years of weather-station data), with 1/2/3-hour buffers.
   - It also computes trigger buffers for the evacuation routes themselves: "the time before an evacuation route may be blocked by a wildfire", and overlays them into one-, two- and three-route impact areas.
   - Relation: the closest trigger-literature treatment of hazard-dependent road availability, but routes are whole objects, not a graph with travel times. Spread uncertainty is a discrete set of worst-case wind scenarios. No incremental update.

3. **Larsen, Dennison, Cova, Jones (2011).** "Evaluating dynamic wildfire evacuation trigger buffers using the 2003 Cedar Fire." Applied Geography 31:12-19.
   - URL: https://content.csbs.utah.edu/~pdennison/reprints/denn/2011_Larsen_etal_AG.pdf (abstract and method passages read)
   - Method: WUIVAC buffers recomputed hourly with forecast winds and compared with actual Cedar Fire perimeters. Modeled buffers exceeded the actual front by up to 126 m (1-hour) and 1400 m (3-hour).
   - Relation: "dynamic" means full recomputation per hour, not an incremental algorithm.

4. **Fryer, Dennison, Cova (2013).** "Wildland firefighter entrapment avoidance: modelling evacuation triggers." Int. J. Wildland Fire, doi 10.1071/WF12160.
   - URL: https://content.csbs.utah.edu/~pdennison/reprints/denn/2013_Fryer_etal_IJWF.pdf (abstract read)
   - Method: WUIVAC buffers for escape routes on foot, by engine and by bulldozer under combinations of weather and fuel inputs (2007 Zaca fire). Evacuation travel time was the most important factor for buffer size.
   - Relation: sensitivity by re-running scenarios, not a parametric solution.

5. **Li, Cova, Dennison (2015).** "A household-level approach to staging wildfire evacuation warnings using trigger modeling." Computers, Environment and Urban Systems 54:56-67.
   - URL: https://content.csbs.utah.edu/~pdennison/reprints/denn/2015_Li_etal_CEUS.pdf
   - Method: (1) a reverse-Dijkstra trigger buffer per household, using that household's evacuation time; (2) forward fire-spread simulation; when the fire crosses household i's buffer, that gives a "recommended evacuation departure time (REDT)"; (3) households are grouped into staged warning zones by REDT.
   - Relation: the closest published "departure deadline per place". It is exact given one fire simulation, one wind setting and a scalar per-household evacuation time. No time-varying road closures; spread rate is not a parameter; no incremental update.

6. **Li, Cova, Dennison (2019).** "Setting wildfire evacuation triggers by coupling fire and traffic simulation models: a spatiotemporal GIS approach." Fire Technology 55(2):617-642.
   - URL: https://content.csbs.utah.edu/~pdennison/reprints/denn/2019_Li_etal_FT.pdf
   - Method: evacuation time estimates come from traffic simulation (shortest-path route choice, no user equilibrium) instead of expert judgment. The distribution of those estimates over departure-time and demand scenarios gives "probability-based trigger buffers" (the outermost 53-minute buffer is 100%, the 45-minute buffer 1%).
   - Relation: the probability is over evacuation-time uncertainty, not fire-spread uncertainty. No road closures by fire in the routing; simulation plus Dijkstra on the raster.

7. **Ronchi et al. (2024).** "WUI-NITY 4: An Industry-Ready WUI Fire Evacuation Model." Fire Protection Research Foundation.
   - URL: https://lup.lub.lu.se/search/files/224899975/WUI-NITY4.pdf (Section 5 on k-PERIL read in full)
   - k-PERIL inputs: community required evacuation time from an evacuation model, plus rate and direction of spread rasters from a fire model.
   - Stochastic trigger boundaries "define a range of perimeters around a community that, once a fire breaches a specific line, will provide sufficient time to evacuate in a specific proportion of wildfire spread scenarios simulated."
   - Roxborough Park case: 1000 FARSITE simulations with stochastic wind, humidity and temperature, at required evacuation times of 120 and 360 minutes. Convergence is declared when 20 consecutive simulations change the boundary by less than 0.3%.
   - WUI-NITY's traffic side does dynamic re-routing when a road is blocked by fire, by simulation.
   - Relation: this is the "members" analogue: a per-cell fraction of scenarios in which evacuation succeeds. It is Monte Carlo over full fire simulations with a scalar community evacuation time, not parametric in a margin, and not a road-graph closure algorithm.

8. **Borgwardt, Crawford, Horton, Morrison, Speakman (2024/2025).** "Evacuation Planning on Time-Expanded Networks with Integrated Wildfire Information." arXiv:2410.14500v2.
   - URL: https://arxiv.org/pdf/2410.14500
   - Method: a wildfire time-expanded network. Nodes inside the fire set F(t) and their incident arcs are removed; arcs near the fire lose capacity. Max flow is solved with Dinic's algorithm, with the minimal horizon found by extension.
   - Update: with revised fire data, flows before the re-optimisation time are fixed, a new smaller network is built from that time on, and it is re-solved. Future work explicitly lists "warm starting a combinatorial algorithm for the reoptimization".
   - Fire in the experiments is a union of circles with linearly growing radii.
   - Relation: the closest published "time-expanded road graph with fire-driven closures". It is an exact max-flow plan, not per-place leave-by windows. Closures are monotone (F(t) ⊂ F(t+1), so no reopening). No spread-rate parameterisation. The update is a re-solve on a truncated network, not an incremental algorithm.

9. **Harris, Forbes, Taimre (2022; published Computers & Operations Research 2023, doi 10.1016/j.cor.2023.106392).** "Logic-Based Benders Decomposition for Wildfire Suppression." arXiv:2209.01371.
   - URL: https://arxiv.org/pdf/2209.01371
   - Model: landscape graph; fire arrival time is the shortest-path distance from the ignition nodes (minimum travel time principle). A resource at a node adds delay Δ. The objective is to minimise the nodes reached within an arrival-time target ψ, which "may represent the time taken for people to evacuate".
   - Framed as shortest-path interdiction. Each master solution is evaluated by a fresh Dijkstra run; solved exactly by logic-based Benders. It builds on the Alvelos (2018) MIP and the Mendes and Alvelos iterated local search.
   - Relation: the formal "delay fire by Δ at a location" literature. It optimises a resource set combinatorially by repeated Dijkstra re-solves. It gives no single-pass marginal value of delay at every node and has no road graph or leave-by times.

10. **Hamacher and Tjandra (2001).** "Mathematical Modelling of Evacuation Problems: A State of Art." ITWM Report 24 (published 2002 in Pedestrian and Evacuation Dynamics, pp. 227-266).
    - URL: https://kluedo.ub.rptu.de/files/1477/bericht24.pdf (relevant sections read)
    - Content: survey of macroscopic dynamic network flow models (max dynamic flow, earliest arrival/universal max flow, quickest path and flow, time-dependent capacities). It introduces a dynamic severity matrix r_it for hazard level by area and time.
    - It explicitly discusses arcs made impassable by fire or smoke at time t0, by modifying the time-dependent arc cost for t ≥ t0. It says "More work is certainly needed in this area" and points to Tjandra's algorithm for universal max flow with time-dependent capacity.
    - Relation: the canonical statement of closure-at-time-t0 arcs in evacuation flows. Flow-oriented (clearance time), with no per-origin latest-departure sets, no hazard parameterisation, no incremental update.

11. **Skutella.** "An Introduction to Network Flows Over Time."
    - URL: https://www3.math.tu-berlin.de/Vorlesungen/SS08/NetOpt/flows_over_time.pdf
    - Caveat: I read the lecture-note version dated April 25, 2008, not the 2009 Springer chapter (Research Trends in Combinatorial Optimization, pp. 451-482). The Matheon-hosted copy refused the connection.
    - Content: flows over time with constant capacities and transit times; Ford-Fulkerson temporally repeated flows; time-expanded networks; earliest arrival flows via successive shortest paths (motivated by evacuation); quickest flow; quickest transshipment (Hoppe-Tardos). It notes the earliest-arrival pattern can have exponentially many breakpoints.
    - Relation: background. The scope is explicitly constant capacities, so there are no closing or reopening arcs.

12. **Shekhar, Yang, Gunturi, Manikonda, Oliver, Zhou, George, Kim, Wolff, Lu (2012).** "Experiences with evacuation route planning algorithms." IJGIS 26(12):2253-2265.
    - URL: https://www-users.cse.umn.edu/~shekhar/talk/evac/ijgis.12.2012.pdf (abstract and method overview read)
    - Content: the Capacity Constrained Route Planner (CCRP) generalises shortest paths with capacity time series on time-aggregated graphs instead of time-expanded graphs. It is a near-optimal heuristic, positioned against exact LP/time-expanded approaches that do not scale.
    - Relation: a time-series-per-edge representation (close in spirit to interval sets), but heuristic, capacity-driven, with no hazard closures and no deadlines.

13. **Darvishan and Lim (2021).** "Dynamic Network Flow Optimization for Real-time Evacuation Reroute Planning under Multiple Road Disruptions." Reliability Engineering and System Safety (accepted manuscript).
    - URL: https://www.ie.uh.edu/sites/ie/files/faculty/glim/RealTimeRouting.pdf
    - Method: each arc has a disruption time; a path-based dynamic network flow MIP over pre-enumerated origin-destination paths; two preprocessing algorithms compute per-path parameters telling whether flow departing at t passes each arc before its disruption time; rerouting is optimised after an "updating time".
    - Relation: the closest OR treatment of "arc closes at a given time, re-plan after a report". It is a re-optimisation over enumerated paths, not an exact incremental update of a deadline field. No reopening, no hazard parameter.

14. **Patel, Min, Lim (2016).** "Accurate Evacuation Route Planning Using Forward-Backward Shortest Paths." IEEE SysCon.
    - URL: https://www.myweb.ttu.edu/slim/lab/papers/min_syscon_16.pdf
    - Content: a CCRP-family heuristic combining forward and backward shortest paths to shorten clearance time. No hazard dynamics. Marginal relevance.

15. **Louis, Turkan, Al-Hamadani.** "Predicting Wildfire Impacts on Mobility Using GIS and Fire Simulation." PacTrans final report, Oregon State University.
    - URL: https://rosap.ntl.bts.gov/view/dot/66305/dot_66305_DS1.pdf (abstract and method passages read; I did not capture the report year)
    - Method: a fire-simulation arrival-time grid is overlaid on roads to mark blocked segments per time snapshot; ArcGIS Network Analyst (Dijkstra) then finds alternative shortest routes per snapshot.
    - Relation: typical practice: snapshot-by-snapshot re-solve, no time-expanded exact deadline.

## B. Sources opened at abstract or record level only

16. **Kalogeropoulos, Mitchell, Ronchi, Gwynne, Rein (2023).** "Design of stochastic trigger boundaries for rural communities evacuating from a wildfire." Fire Safety Journal 140:103854.
    - URL: https://lup.lub.lu.se/record/d98cd001-0d8c-4bd8-a21a-e90f8a94061c (abstract). ScienceDirect returned 403.
    - Method details come from item 7 (primary, same authors) and a secondary source: the authors' interview at https://www.firescienceshow.com/156-trigger-boundaries-with-harry-mitchell-and-nick-kalogeropoulos/ (many single-scenario PERIL runs bundled until convergence; the band gives the percent of simulated fires for which evacuation succeeds; the safety factor is applied by scaling evacuation time).

17. **Mitchell, Gwynne, Ronchi, Kalogeropoulos, Rein (2023).** "Integrating wildfire spread and evacuation times to design safe triggers: Application to two rural communities using PERIL model." Safety Science 157:105914.
    - URL: https://portal.research.lu.se/en/publications/integrating-wildfire-spread-and-evacuation-times-to-design-safe-t/ (abstract), plus the Zenodo code record https://zenodo.org/records/4106654 ("based on the work of Cova et al 2005").
    - Content: PERIL generates trigger perimeters from FARSITE output with a safety factor; applied to Swinley Forest (UK) and Roxborough Park (USA). Full text not read.

18. **Shahparvari, Chhetri, Abbasi, Abareshi (2016).** "Enhancing emergency evacuation response of late evacuees: Revisiting the case of Australian Black Saturday bushfire." Transportation Research Part E 93:148-176.
    - URL: https://econpapers.repec.org/RePEc:eee:transe:v:93:y:2016:i:c:p:148-176 (abstract)
    - Content: multi-objective integer program solved by the ε-constraint method; sensitivity to short time windows, resource availability and road disruptions. How the time windows are derived from fire is not in the abstract.

19. **Shahparvari and Abbasi (2017).** "Robust stochastic vehicle routing and scheduling for bushfire emergency evacuation: An Australian case study." Transportation Research Part A 104:32-49.
    - URL: https://econpapers.repec.org/RePEc:eee:transa:v:104:y:2017:i:c:p:32-49 (abstract)
    - Content: stochastic vehicle routing with uncertain population, time windows and fire propagation, with road availability and disruptions; greedy heuristic versus genetic algorithm.
    - Relation: time windows per location are inputs (the nearest OR analogue of leave-by windows), solved heuristically. Not derived by an exact graph pass.

20. **Intini, Ronchi, Gwynne, Pel (2019).** "Traffic modeling for wildland-urban interface fire evacuation." J. Transportation Engineering Part A 145(3):04019002.
    - URL: https://research.tudelft.nl/en/publications/traffic-modeling-for-wildland-urban-interface-fire-evacuation (abstract)
    - Content: review of 22 traffic models against WUI needs. Simulation-oriented.

21. **Tammali, Khanda, Satpathy, Shovan, Das (2026).** "RESCUE: Routing under Evolving Stochastic Congestion and Uncertain Spread in Wildfire Emergencies." ICDCN 2026, pp. 168-172, doi 10.1145/3772290.3772301.
    - URL: https://scholarsmine.mst.edu/comsci_facwork/2138/ (abstract)
    - Content: time-varying weighted road graph; a stochastic edge fire-risk function derived from rate of spread; multi-objective shortest path; compared against A* and D*.
    - Relation: risk-weighted routing heuristic, not exact deadline sets.

22. **Moradi, Sauré, Patrick (2026).** "A Relaxation-Based Decomposition Approach for Solving a Supported-Evacuation Problem in Wildfires." arXiv:2608.05413.
    - URL: https://arxiv.org/abs/2608.05413 (abstract)
    - Content: two-stage stochastic location, fleet and routing model with strict time windows, solved by logic-based Benders; Roxborough Park data.

23. **Delazeri and Ritt (2026).** "Wildfire Suppression: Complexity, Models, and Instances." arXiv:2603.29865.
    - URL: https://arxiv.org/abs/2603.29865 (abstract)
    - Content: the suppression-resource (delay) problem is strongly NP-complete on planar graphs and weighted directed grids; new MIP.
    - Relation: selecting a set of delay locations is hard, which is context for why a per-location single-delay ranking is the tractable piece.

24. **Maheshwari, Nouri, Sack (2018).** "Time-Dependent Shortest Path Queries Among Growing Discs." arXiv:1808.01984.
    - URL: https://arxiv.org/abs/1808.01984 (abstract)
    - Content: a (1+ε)-approximate earliest-arrival function A(t) over all departure times among discs growing at given rates.
    - Relation: computational geometry, not evacuation, but the nearest thing I saw to "departure-time profile against obstacles that grow at a rate". Approximate, single source-destination pair.

## C. Could not open; relied on search-result summaries only (treat as unverified)

- **Lu, George, Shekhar (2005)**, CCRP, UMN TR 05-023: conservancy.umn.edu returned 403. Relied on item 12 and the search snippet (heuristic; time-series node/edge capacities; no time-expanded graph).
- **Kim, George, Shekhar (2007)** "Evacuation route planning: scalable heuristics": seen only as a citation in item 12.
- **Hoppe and Tardos (2000)** "The Quickest Transshipment Problem", Math. Oper. Res. 25(1):36-62: search summary only (first polynomial algorithm; integral optimum).
- **Baumann and Skutella (2009)** "Earliest arrival flows with multiple sources", Math. Oper. Res. 34(2):499-512: search summary only (exact; strongly polynomial in input plus output size).
- **Bayram (2016)** survey, Surveys in OR and Management Science 21(2):63-84: search summary only.
- **Beloglazov, Almashor, Abebe, Richter, Steer (2016)**, doi 10.1016/j.simpat.2015.10.002: search summary only (composed fire, behaviour and microscopic traffic simulators; Victoria case).
- **Wolshon and Marchive (2007)**, J. Urban Planning and Development 133(1):73-81: search summary only (subdivision-level simulation).
- **Mendes and Alvelos (2023)**, EJOR 304(3):887-900: search summary plus the description in item 9.
- **Ramirez, Monedero, Silva, Cardil (2019)** "Stochastic decision trigger modelling to assess the probability of wildland fire impact", Science of the Total Environment, doi 10.1016/j.scitotenv.2019.07.311: search summary only (many trigger-buffer runs with perturbed inputs give a probability map; Tubbs fire). Record page returned 403.
- **Priest, Stimely, Wood, Madin, Watzig (2016)** "Beat-the-wave evacuation mapping for tsunami hazards in Seaside, Oregon, USA", Natural Hazards 80(2):1031-1056: search summary only; USGS page returned 403. Reported method: least-cost distance to safety per grid cell; minimum required speed = distance / tsunami arrival time; bridge-failure scenarios re-run as cases.
- **Pais, Carrasco, Elimbi Moudio, Shen (2021)** "Downstream protection value", Computers & Operations Research 131: search summary only; HKU page returned 403.
- **Zhou and Erdogan (2019)**: the search surfaced an abstract-only ScienceDirect page titled "A spatial optimization model for resource allocation for wildfire suppression and resident evacuation" (403 on fetch), described as a two-stage stochastic goal program over fire scenarios. I could not confirm the authors or the "robust evacuation planning" title you gave.
- **Wei, Rideout, Kirsch (2008)**: not opened. One secondary description calls it a MIP minimising expected fire loss, not an arrival-time model.
- **Not searched or not found:** Yuan and Wang 2009; flood time-dependent closure papers (Liu, Lai et al.); Zhao and Wong 2021 (appeared only as a search hit and as a citation in item 8); Grajdura et al.; Alexandridis et al.; lahar deadline maps; the Shekhar-group contraflow paper; NIST ESCAPE TN 2262 (search hit only); the CASPER paper (USC PDF download failed).

## D. Answers to the three specific questions

**(1) Closest published thing to "leave-by time per place as an exact function of assumed spread rate / reach margin".**

The trigger-buffer family is closest, in three variants:
- **WUIVAC reverse-Dijkstra field (items 1, 2).** One backward pass gives, for every cell, the minimum fire travel time to the community; buffers at T = 15/30/45 minutes are level sets of that one field. My inference, not a claim in the papers: because arc times are distance/rate, a uniform spread-rate multiplier m simply rescales the field by 1/m, so this field is already an exact function of a uniform multiplier for a single protected target. The papers do not frame it that way; they treat wind and spread as fixed scenario inputs that require recomputation.
- **Household REDT (item 5).** An explicit recommended departure time per household, but for one simulated fire and one scalar evacuation time.
- **k-PERIL and probability-based buffers (items 7, 16, 6; Ramirez 2019 unverified).** These handle spread uncertainty, but by Monte Carlo over hundreds to 1000 full fire simulations, producing a fraction-of-scenarios band. That is an empirical distribution, not a closed-form function of a margin.
- **Dual-parameter analogue.** The tsunami "beat the wave" maps (unverified, search summary only) give a per-cell minimum evacuee speed that survives. That is the mirror image of "fastest hazard speed a departure survives", but for a single wave arrival time with static bridge-out scenarios.

How all of these differ from an exact graph algorithm over road closures:
- The shortest path is computed on the fire raster, not the road graph. The evacuation side is collapsed to a scalar T (or a simulated distribution of T).
- There is one protected target and one deadline. No per-segment closure times interact with en-route position; "the route gets cut behind or ahead of you" is not modelled. Dennison 2007's route buffers are the only nod, and they are overlays.
- No reopening after burn-out, hence no multi-interval departure sets. No heat-dose budget.
- Uncertainty is handled by scenario re-runs.
- Item 8 does have the time-expanded road graph with fire-removed arcs, but it computes a max-flow plan for one fire forecast, with monotone closures and no parameterisation.

**(2) Exact incremental recomputation of evacuation deadlines after a single road closure/reopening report.**

None found. What exists:
- Item 8: re-solves max flow on a truncated time-expanded network and names warm-started re-optimisation as future work.
- Item 13: MIP re-optimisation over pre-enumerated paths with per-arc disruption times.
- Item 3: hourly full recomputation of trigger buffers.
- WUI-NITY (item 7) and RESCUE (item 21): simulation or heuristic re-routing.
- Item 15: per-snapshot Dijkstra re-solve.

None maintains a per-place deadline field incrementally, and none handles reopening. Generic dynamic shortest-path algorithms were outside this topic; one extended search for them in an evacuation context returned nothing.

**(3) Single-pass computation of the benefit of delaying fire arrival at every location for evacuation time.**

None found. The nearest work:
- The suppression/interdiction line (item 9; Alvelos 2018 and Mendes and Alvelos 2023 via item 9; item 23). It models a fixed delay Δ at a node and an arrival-time target ψ interpreted as evacuation time. But it optimises a resource set by MIP, local search or Benders with repeated Dijkstra evaluations, and the problem is strongly NP-complete. It does not output a marginal-value-of-delay map, and the objective is nodes burned by ψ, not safe departure time on a road network.
- Downstream Protection Value (Pais et al. 2021, unverified): reportedly ranks every cell's treatment impact from fire-propagation trees. That is a per-location ranking, but of burned-area value, not evacuation time.
- Dennison 2007's route impact areas show where a fire cuts 1, 2 or 3 routes within T, which is a static overlay.

A per-location "minutes of safe departure gained per 30/60/120 minutes of hold" from one pass appears unpublished in what I searched; the published practice is re-solving per candidate, as your companion study does.

## E. Caveats

- All fetched-page summaries were produced by a fetch tool's summariser. Where I quote, the quotes come from text I extracted myself from PDFs (items 1-15) or from the tool's rendering of an abstract (items 16-24).
- For item 11 I read the 2008 lecture-note version, not the 2009 chapter.