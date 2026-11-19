# Prior work: placing suppression to protect evacuation (PROTOCOL §9)

**Search 2026-11-18, 15:28–15:30 UTC (web search only).** Fetches of full texts failed: arxiv.org and ar5iv.arxiv.org
are not reachable from this environment. **No full text was read.** Every entry below rests on search-result
snippets: abstract fragments, catalogue records, or citing papers. Anything not seen in a snippet is marked *not
verified*. This search was done after PROTOCOL.md was frozen (`af06676`) and did not change the method.

## Sources

| # | Source | Read | What it decides / optimises | Fire model | Evacuation or roads? |
|---|---|---|---|---|---|
| 1 | **Harris, M.G., Forbes, M.A., Taimre, T. (2023).** Logic-based Benders decomposition for wildfire suppression. *Computers & Operations Research* 160, 106392. doi:10.1016/j.cor.2023.106392; arXiv:2209.01371 | snippets | Where to place k suppression resources, framed as network interdiction against a spreading process. **Objective: minimise total area burned.** Solved exactly by logic-based Benders. | Minimum travel time: arrival = shortest path from the ignition. A resource at vertex v adds a delay Δ to v's outgoing arcs. | None seen in the snippets. Synthetic grid instances (parameters of Alvelos and of Mendes). |
| 2 | Delazeri, G., Ritt, M. (2026). Wildfire Suppression: Complexity, Models, and Instances. arXiv:2603.29865 | snippets | The same Wildfire Suppression Problem (Alvelos 2018). Shows NP-completeness; proposes models and benchmark instances. | Same delay-on-arcs model. | None seen. |
| 3 | Mendes, A.B., Alvelos, F.P. (2023). Iterated local search for the placement of wildland fire suppression resources. *EJOR* 304(3), 887–900 | abstract snippet | Resource placement. Objective: minimise burned area, then the number of resources. | Grid network, minimum travel time. | None seen. |
| 4 | Alvelos, F., Marto, M., Mendes, A.B. (2025). Dispatching, positioning and routing resources for wildfire initial attack. *Networks* 86(1), 80–102. doi:10.1002/net.22278 | snippet | MIP for dispatching, positioning and routing initial-attack crews and helicopters. Objective *not verified*. | Minimum travel time. | Resource routing appears; evacuation *not verified*. |
| 5 | Belval, E.J., Wei, Y., Bevers, M. (2015). A mixed integer program to model spatial wildfire behavior and suppression placement decisions. *Can. J. For. Res.* 45, 384–393; stochastic follow-up 46(2) (2016), 234–248 | snippet | Suppression placement inside a fire-behaviour MIP on a raster. Exact objective *not verified*. | Spread inside the MIP. | None seen. |
| 6 | Hof, J., Omi, P., Bevers, M., Laven, R. (2000). A timing-oriented approach to spatial allocation of fire management effort. *Forest Science* 46(3), 442–451 (also Donovan & Rideout 2003, cited alongside) | citing snippets only | Effort allocated so as to **delay the fire's arrival at protected target locations**. Exact objective *not verified*. | Arrival timing. | *Not verified.* |
| 7 | Wei, Y., Rideout, D., Kirsch, A. (2008). Locating fuel treatments across a landscape to reduce expected fire losses. *Can. J. For. Res.* 38(4), 868–877 | snippet | Fuel treatment placement under a budget (not suppression). | Probabilistic cell-to-cell spread. | None. |
| 8 | Wei, Y., Thompson, M.P., Scott, J.H., O'Connor, C.D., Dunn, C.J. (2019). Designing operationally relevant daily large fire containment strategies. *Forests* 10(4), 311 | snippet | Groups operational delineations (PODs) into a containment area. Objective: minimise expected loss, with firefighter-safety preferences. Case: Sliderock Fire 2017. | FSPro layers, including arrival time. | Not seen. |
| 9 | Zhou, S., Erdogan, A. (2019). A spatial optimization model for resource allocation for wildfire suppression and resident evacuation. *Computers & Industrial Engineering* 138, 106101 | abstract snippet | **Joint suppression and evacuation**: a two-stage stochastic goal program. Objectives: cost and property loss, and the number of people who must be evacuated. Case: Santa Clara County. | Fire-spread scenarios on cells (*not verified* in detail). | Evacuation, yes. Road network and departure windows *not verified*. |
| 10 | van der Merwe, M., Minas, J., Ozlen, M., Hearne, J. (2015). A MIP approach for asset protection during escaped wildfires. *Can. J. For. Res.* 45(4), 444–451 | abstract snippet | Routes protection vehicles to assets (team orienteering with time windows set by fire arrival). | Arrival time per asset. | Road network for the crews; no evacuation. |
| 11 | Li, D., Cova, T.J., Dennison, P.E. (2015, 2017, 2019) evacuation trigger buffers; Fryer, Dennison & Cova (2013) | snippets | Where to place a warning trigger so there is enough time to evacuate (reverse spread from the community). | Minimum travel time, reversed. | Evacuation, yes (2019: traffic simulation). **No suppression.** |
| 12 | Wahlqvist, J., Ronchi, E. et al. (2021). The WUI-NITY platform. *Safety Science* | snippet | Simulation coupling fire, pedestrian response and traffic. | CA/BEHAVE. | Evacuation, yes. No suppression, no optimisation. |
| 13 | Kwon, K., Kim, Y., Han, J. (2025). Integrated optimization for resilient wildfire evacuation system design: a rural county in Korea. *Systems* 13(12), 1125 | abstract snippet | Shelter and backup-link selection (MIP), motivated by the 2025 Yeongnam fires. | — | Evacuation network, yes. No suppression. |
| 14 | Moradi, S., Sauré, A., Patrick, J. (2026). Supported evacuation in wildfires. arXiv:2608.05413 | abstract snippet | Assisted evacuation (facility location, fleet, routing), solved with logic-based Benders. | — | Evacuation, yes. No suppression. |
| 15 | Louis, J., Turkan, Y., Al-Hamadani, S. (2022). Predicting wildfire impacts on mobility using GIS and fire simulation. PacTrans report | snippet | Overlays FlamMap arrival times on roads to find affected segments and detours (Archie Creek Fire 2020). | FlamMap minimum travel time. | Roads, yes. **No ranking by time bought, no suppression.** |

Peripheral, from snippets: Cell2Fire and the Downstream Protection Value line (firebreak placement); Matsypura et al.
(2018) on prescribed burning. A Korean GIS zone-ranking paper and reports on the national helicopter dispatch system
were seen, but **no Korean suppression-placement optimisation model was found**.

## How this study differs

1. **Objective.** Harris et al. and the Alvelos/Mendes/Delazeri line minimise **area burned**. Here the quantity is
   **person-minutes of safe departure window** on the road network: for each village, how much longer a departure
   still reaches one of its shelters in the F-3.1 deadline field.
2. **Same delay idea, different target.** The mechanism is the same: a resource imposes a delay Δ on fire arrival at a
   location (Harris et al.: Δ on a vertex's outgoing arcs). Here Δ postpones the closure of one road cell, or the
   spread from one 2 km section of known fire front. Its effect is read through **road closures and departure
   windows**, not through burned area.
3. **No optimisation over resources.** There is no budget, no choice of k locations, no crew routing and no
   scheduling. Each single candidate is evaluated exactly and the candidates are ranked. That is a screening list,
   not an optimal plan. Interactions between two held locations are not computed.
4. **Nearest neighbours.**
   * Hof et al. 2000 (delaying arrival at protected targets): delays arrival at places, not at the roads people leave by.
   * Zhou & Erdogan 2019 (joint suppression and evacuation): a cost/goal programme over scenarios; it is not shown to
     use departure windows on a road graph.
   * Trigger-buffer work (Li, Cova, Dennison): uses the same reverse arrival-time machinery for warnings, but has no
     suppression.
   * Louis et al. 2022: identifies road segments affected by arrival time, but does not rank them by evacuation time
     bought.
5. **Case.** This is a replay of one real day (25 March 2025, 의성·안동 and 영덕) with six fire-reach arms. The works
   above use synthetic grids or other single cases.
6. **What this study does not have that those do:** feasibility of resources (Alvelos et al. 2025; van der Merwe et
   al. 2015), firefighter safety preferences (Wei et al. 2019), and stochastic weather (Belval et al. 2016).

**Gap as found:** no source in this search places suppression to maximise evacuation departure time, or ranks road
segments or fire-front sections by the evacuation time they would buy. This rests on snippets only. A full-text check,
which needs arXiv access (above all Harris et al. 2023 and Delazeri & Ritt 2026), could change it.
