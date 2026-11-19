# Literature gate (Step 0), written 2026-11-18 before any code

Question: what already exists for (a) an exact village-level leave-by window under congestion with fire-closing roads, and
(b) a per-answer certificate for it, checked by independent code?

**How this was done, and its limits.** 11 web searches on 2026-11-18, standard mode, run from a US-only search tool. I
read result titles and the snippets the tool returned. **I did not read any full paper.** Every statement below about a
paper is therefore a statement about its abstract or snippet, and is marked so. No Korean-language search was run
(KOSIS, KOTI, Korea Forest Service, KHCM literature were not searched for evacuation work). Time spent: well under the
2 hours allowed. Absence of a hit below means "not found by these searches", not "does not exist".

## What already exists

| topic | what I found (snippet level) | source |
|---|---|---|
| Dynamic flows, earliest arrival, quickest transshipment | Quickest flow = minimum time to send a given amount; earliest arrival flow = maximum flow reaching the sink at every time; quickest transshipment (Hoppe and Tardos 2000; Fleischer 2001) is the multi-source, multi-sink version and is the usual model of evacuation. Baumann and Skutella treat multiple sources. | [Springer chapter](https://rd.springer.com/chapter/10.1007/978-3-030-17953-3_28), [INFORMS reference list](https://pubsonline.informs.org/doi/references/10.1287/moor.1090.0382) |
| Time-dependent capacities (closure = capacity 0) | Dynamic flows with time-dependent capacities: with a finite horizon, a single edge changing capacity once makes the maximum-flow problem weakly NP-hard in the compact encoding; with storage at vertices a pseudo-polynomial algorithm exists (time-expanded network). Flow-dependent transit time (a real congestion law) is strongly NP-hard. | [Bläsius, Feilhauer, Westenfelder, arXiv 2302.07657](https://arxiv.org/pdf/2302.07657) |
| Wildfire plus time-expanded max flow | A wildfire evacuation formulated as maximum flow on a time-expanded network, fire given as a shapefile, blocked roads and reduced capacity, plan revised as the fire forecast is revised; Camp Fire example. | [Borgwardt et al., arXiv 2410.14500](https://arxiv.org/pdf/2410.14500) |
| Capacity-constrained route planning (CCRP) | Heuristic that routes evacuees one group at a time on a time series of arc capacities, no preset time bound; faster than the linear-programming (time-expanded) optimum, sub-optimal. Evaluated in Twin Cities Homeland Security scenarios. | [Lu, George, Shekhar 2005, UMN](https://conservancy.umn.edu/items/f5fbf849-e484-426d-ab55-5a4aa5318289), [Dagstuhl summary](https://drops.dagstuhl.de/entities/document/10.4230/DagSemProc.10121.3), [IJGIS 2012 evaluation (abstract)](https://bohrium.dp.tech/paper/arxiv/1905.06783) |
| Evacuation under road disruptions | Dynamic network-flow rerouting under multiple road disruptions (Darvishan and Lim 2021) and short-notice evacuation on time-expanded networks (Lim et al.): cited in the Borgwardt list; **not opened**. | [Borgwardt et al. citation list](https://arxiv.org/pdf/2410.14500) |
| Dynamic paths with time-varying roads | Evacuation as path finding on a directed graph whose roads change with a wildfire; schools as shelters; southern California records. | [Scalable evacuation routing in a dynamic environment (USC)](https://johnwilson.usc.edu/wp-content/uploads/2018/03/Scalable-evacuation-routing-in-a-dynamic-environment.pdf) |
| WUI-NITY | Platform coupling a fire model (FARSITE-based), a pedestrian model and a traffic model (Lighthill-Whitham-Richards, later SUMO); trigger-buffer tool PERIL / k-PERIL; a 24-test verification protocol (15 traffic, 5 fire spread and trigger buffers). Egress-route interruption is listed as **future work** in the WUI-NITY 4 report. | [WUI-NITY platform](https://spiral.imperial.ac.uk/entities/publication/fdcb41b0-5d72-44c1-bc3c-237a48dd1697), [WUI-NITY 4 report](https://lup.lub.lu.se/search/files/224899975/WUI-NITY4.pdf), [verification, Nat. Hazards 2023](https://link.springer.com/content/pdf/10.1007/s11069-023-05913-2.pdf) |
| Trigger models with traffic | Li, Cova, Dennison (Fire Technology 2019): evacuation time from traffic simulation, then probability-based trigger buffers around a community (Julian, California). | [Li et al. 2019 reprint](https://content.csbs.utah.edu/~pdennison/reprints/denn/2019_Li_etal_FT.pdf) |
| Ladris | Commercial AI-driven evacuation simulator; scenarios with road closures and early orders; used by agencies (Nevada County, Pikes Peak, Spokane pilot). A 2024 PyroAnalysis/Ladris study of Tahoe's north shore reports an evacuation of up to 14 h against an earlier 4 h estimate. Method not published in what I found. | [Spokane page](https://my.spokanecity.org/emergencymanagement/evacuation/), [KNPR](https://knpr.org/2024-09-06/evacuating-mountain-west-tourist-area-wildfire-take-14-hours-ai-study), [Gazette](https://gazette.com/?p=1501227) |
| Capacity as the binding constraint | A 2026 arXiv paper on the Lahaina fire concludes road capacity, not driver behaviour, binds. Snippet only. | [arXiv 2603.29055](https://arxiv.org/pdf/2603.29055v2) |
| Certifying algorithms | A certifying algorithm returns a witness with each answer, checkable by a simpler program (McConnell, Mehlhorn, Näher, Schweitzer, *Computer Science Review* 5(2), 2011). Max-flow with its min-cut is the textbook example. | [survey record](https://vufind-test.katalog.k.utb.cz/SummonRecord/FETCH-LOGICAL-c338t-1e4a5d99c92d5f63dbb4d9158399491a3d4205a4b9d85cd1b9c0b9352ced6b583), [Mehlhorn slides](https://people.mpi-inf.mpg.de/~mehlhorn/ftp/UVMSept2014.pdf) |
| Witness output in evacuation flows | "Optimal evacuation flows on dynamic paths" says its decision algorithm can also return an explicit evacuation protocol. Not framed as certification, not checked independently. | [arXiv 1606.07208](https://arxiv.org/pdf/1606.07208) |

## What this means for the two claims

**(a) An exact village-level leave-by window under congestion with fire-closing roads.**

* **The model class exists.** Time-expanded maximum flow with arcs removed or capacity-reduced when fire reaches them
  (Borgwardt et al.), CCRP-style capacity reservation (Lu et al.), earliest-arrival and quickest-flow theory, and
  time-dependent-capacity flow theory (Bläsius et al.) already cover "capacities, queues, closures over time". **If both
  of my claims were "a congestion model with fire closures", both would already exist, and I say so.**
* **Not found:** a published output of the form "for each village, the latest time the whole village can *start*
  leaving so that its *last* vehicle still reaches a shelter before the fire cuts the road". With a time-expanded flow it
  is a search over the release time (a binary search if feasibility is monotone in it), so it is a *use* of the existing
  methods, not a new algorithm. My contribution, if any, is that output on a real road graph with per-cell fire
  closure times, reported per village, and the comparison with the one-vehicle free-flow window.
* **What I will not claim.** I will not claim exactness for route choice unless the brute-force test supports it. The
  solver planned here (sequential capacity reservation, i.e. CCRP-like) is a *guaranteed-safe lower bound*: a feasible
  schedule exists for every start time it accepts. The optimum over all routings is a flow problem and CCRP is known to
  be a heuristic. The test in PROTOCOL T1 measures how far apart they are on small networks.
* **Not tested here:** whether Ladris or WUI-NITY can output a leave-by window. WUI-NITY 4 lists route interruption as
  future work; Ladris method documentation was not found. Their absence from my results is not evidence they cannot.

**(b) A per-answer certificate checked by independent code.**

* The *concept* exists (certifying algorithms; max-flow/min-cut). A feasible schedule is a certificate by definition.
* **Not found** in the evacuation papers I could see: a shipped certificate per village plus a separate checker that
  shares no code with the solver. This repository already does that for the one-vehicle field
  (`research/kcf-theorem/checker.py`), so the idea is not new here either; the new part is only the extension to queue
  schedules. Because my search read snippets only, I cannot rule out earlier work.
* For a lower bound the certificate proves **feasibility only** (this start time works). It does not prove that a later
  start time fails. An exact answer would need a second certificate (a cut). I do not have one for route choice.

## Verdict

Neither (a) nor (b) is new as a method. As far as these searches show, the village-level leave-by output and the
shipped independent checker for queue schedules are not published, but that is a limit of the search and not a finding.
I continue with the congestion model as asked.
