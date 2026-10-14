# Novelty check (phase 2, item 4)

This is desk research compiled on 2026-10-15 by a research agent in this session, using web, patent and paper search; no one was contacted. Markers:

- [read]: the page or paper was fetched and read.
- [abstract] or [snippet]: only part of it was seen.
- [verified]: the main session re-fetched the source and confirmed the quoted text.

Full URLs are in `data/SOURCES.md` under "Phase 2: novelty".

## Bottom line

The core mechanism of Last Gasp is not new:
- a periodic heartbeat;
- silence read as fire reaching the node;
- the last heartbeat taken as the fire arrival time;
- fire progress charted from destroyed sensors.

It is described in patents from 2005 and 2014, and fitting a fire front to smart-meter outage times was publicly disclosed in July 2026.

Nothing found does the following, so these are the defensible contributions:
- a spatial arrival-time map reconstructed from many node death times (with censoring from the heartbeat interval);
- spot fire detection from deaths that break the expected order (a node dies while nodes between it and the front survive), with the jump distance;
- the quantitative finding that grid-powered devices (meters, routers, grid-powered gateways) are censored by upstream outages.

An examiner could still argue that these are obvious extensions of the prior art plus standard interpolation.

## Closest prior art

| Source | What it already does | What it lacks |
|---|---|---|
| IBM (Clarke), US9530304 / US9721458, "Distributed sensor network", priority 2014-10-30 [verified] | Mesh of nodes with heartbeat signals. A node "determines a fire arrival time for the adjacent node that application 104 determined to be destroyed", using "the time at which application 104 received the last heartbeat signal from the node". It forecasts arrival at other locations and the speed of the fire edge. | No spatial arrival-time map, no spot fire detection (fire jumping roads and rivers is mentioned only as background). Listed as "Expired - Fee Related" on Google Patents. |
| Smith, US9619996, "Distributed wild fire alert system", priority 2014-08-14 [verified] | Fixed (including air-dropped) sensors; "information could also be derived from the loss of signals from the sensors", "providing information about where fixed sensors have been destroyed by the fire"; data used "to chart the location, intensity, progress and direction of the wildfire". | No method for arrival-time maps, no spotting. Lapsed 2025-04-11 per Google Patents. |
| Smart Packaging Solutions, EP1952368 / WO2007054630, priority 2005-11-10 [read] | Tags send a periodic ID; loss of the signal from two or more neighbours means a probable fire; the antenna degrades above a set temperature (sacrificial tag). | Alarm only; no reconstruction or spotting. Lapsed. |
| Live in the Future, defensive disclosure LITF-PA-2026-122, 2026-07-27 [read] | Smart-meter anomaly and outage flags; "fits a propagating front model to the timestamps of anomaly onset across meters"; perimeter polygons every 1 to 5 min. | Grid-dependent meters (the censoring problem shown in phase 1); no spotting; it rejects isolated clusters as equipment faults. |
| Blank and Simard (USDA), US4521120, 1985 [read] | Cheap point devices (buried timers started by melting solder) give arrival times, from which rate and direction of spread are computed. | Manual retrieval, not live; no network. |

## Commercial systems

None of these uses node loss as a signal or publishes arrival-time maps from ground nodes.

| System | Sensing | Notes |
|---|---|---|
| Dryad Networks Silvanet | Gas sensors (CO, H2, VOC), solar, LoRaWAN mesh | Early detection; typically about 1 sensor per hectare in dense areas, sparser elsewhere [snippet] |
| N5 Sensors | Particulates, gas, heat | A 2026 DHS Inspector General audit found the sensors "did not consistently detect fires" [read] |
| Pano AI, IQ FireWatch, Insight Robotics | Cameras on towers or peaks | Detection and situational awareness |
| OroraTech | Thermal satellites | Marketing claims spread mapping [snippet] |
| Korea | Gangwon province reported 519 IoT fire detectors and 70 smart CCTVs (2023) | No Korean use of node loss found [snippet] |

## Academic work

- **Sensors in the fire front.**
  - FireWxNet (Hartung et al., MobiSys 2006) and FireBug (Doolin and Sitar, 2005) measured conditions as fronts passed.
  - Antoine-Santoni et al. (Sensors, 2009) tracked the front with thermally protected motes and called node destruction "one of the great challenges".
  - Imran and Ko (Sensors, 2017) treat node failure as noise.
  - In this literature, node destruction is a problem to engineer around, not a measurement.
- **Arrival-time maps and data assimilation.**
  - Mandel et al. (2008), Rochoux et al. (2014), Farguell et al. (2018, 2021) and Parks (2014).
  - These use satellite or infrared perimeters and temperatures, not node death times.
- **Spot fires.** Measured from airborne line scans (Storey et al., Fire, 2020). No sensor-network spot detection was found.
- **Outage data and disasters.**
  - ThunderPing, Trinocular and IODA measure residential internet outages for weather events.
  - "Five Alarms" (IMC 2020) assesses wildfire risk to cell sites.
  - None of them reconstructs fire progression from outage times.
  - NIST's Camp Fire timeline (TN 2135, 2021) did not use device offline times, but recommends collecting utility, communication and alarm-company data in future [read].

## What Last Gasp can claim

1. A dense field of cheap tags whose only measurement is their own death, with arrival-time maps and spot fire flags computed from death order. No published example of the reconstruction and spotting steps was found.
2. A design rule from the simulations: grid-powered devices and gateways censor the signal, so a fire-mapping network must be independently powered, including its gateways (`RESULTS.md`, `RESULTS_PHASE2.md`).
3. Not claimable: heartbeat loss as a fire indicator, last heartbeat as arrival time, charting progress from destroyed sensors, or fitting a front to meter outage times.

## Gaps

- Non-English patents (Chinese, Korean, Japanese) were not searched systematically. This is the largest gap.
- The full claims of US9530304, US10255780 ("detecting and mapping progression of a fire event"; page unavailable) and US11620891 were not read.
- Whether the Lahaina timeline used device offline times is not verified.
- Patent status is as shown on Google Patents and is not a legal opinion.
