# Claude Code prompt: Track 1D, Last Gasp: fire arrival observations from existing devices going offline

Run after track 1C has created `experimental/synthetic-truth/` (it consumes its truth packets) or in parallel with a fixture. Branch `track/1d-last-gasp`. Ownership: `experimental/last-gasp/**`, `research/last-gasp/**`, `docs/LAST_GASP_DATA_CONTRACT.md`. Nothing else.

---

You are working in the WildfireGuardian repository. Read `docs/NEXT_INTERFACES.md`, `integration/src/wfg_latest/contract.py`, `integration/src/wfg_latest/bridge.py` (how present-fire activity and ignition times enter a packet) and, if present, `experimental/synthetic-truth/README.md`.

## Why

The model has never been trained or validated on a measured ignition time at a point. Every powered, networked device that a fire reaches records that moment implicitly: its last heartbeat, its outage timestamp, or its protection trip. Korea has dense networks of such devices (KEPCO smart meters and distribution feeders, mobile base stations, the Korea Forest Service mountain weather stations and fire-watch cameras, road ITS detectors, village broadcast nodes). Turning those timestamps into arrival-time observations gives point-level ground truth for the March 2025 fires at zero deployment cost, and a live observation stream for assimilation. This track builds the contract, the ingestion, the conversion to the model's arrival-time field, and the first dataset from sources that need no agreement.

## Deliverable 1: the data contract (`docs/LAST_GASP_DATA_CONTRACT.md`)

Define one record type for an offline event: `device_id` (hashed), `device_type` (meter, feeder, cell_site, weather_station, cctv, its_detector, broadcast_node, other), `lat`, `lon`, `positional_uncertainty_m`, `last_seen_utc`, `first_missing_utc`, `outage_cause` (unknown, fire_suspected, power, backhaul, planned, confirmed_fire), `cause_evidence`, `source_org`, `heartbeat_interval_s`, `recovered_utc` or null. State the inference rule explicitly: an offline event is evidence that fire reached the device's location between `last_seen_utc` and `first_missing_utc` only when the cause is fire or unknown with no competing explanation (grid-wide blackout, planned outage, backhaul loss upstream), so every record carries a cause flag and a confidence, and a cluster of simultaneous outages across a wide area is treated as a grid event, not fire arrivals. Add a privacy section: hashed device ids, coordinates coarsened to 50 m for meters, aggregation before publication, no household attribution.

## Deliverable 2: ingestion and conversion (`experimental/last-gasp/`)

- `ingest.py`: CSV and JSON readers for the record type, with validators.
- `screen.py`: the cause screening above (temporal clustering of outages, comparison against known grid-event windows, upstream dependency checks for cell sites), producing per-record confidence.
- `to_arrival.py`: convert screened records into point observations with a time interval `[last_seen, first_missing]`, then into (a) a sparse arrival-time observation set for the 375 m grid in EPSG:5179 (cell, earliest interval, count, confidence), and (b) a "truth packet" of the same shape track 1C's harness consumes (`truth_source = "device_offline"`), with cells lacking observations marked unknown, never unburned.
- `assimilate.py`: the reset step from the briefing: given a forecast export and a set of arrival observations up to time t, set observed cells to burned at the interval midpoint (and record the interval), leave unobserved cells untouched, and emit a new export tagged with the observations used. No weights, no resimulation; that is for the harness to evaluate.

## Deliverable 3: the first dataset without agreements (`research/last-gasp/`)

1. Korea Forest Service mountain weather stations (산악기상관측망): the historical observations are published by NIFoS through its mountain weather information service and the public data portal. Download March 2025 for all stations in the affected counties (의성, 안동, 영덕, 산청, 울주 and neighbours), find stations whose reporting stopped during the fires, and record each as an offline event with the last observation time and the wind at that time. Document exactly which endpoint or download you used and its licence; if the data must be requested rather than downloaded, write the request text and stop with a fixture.
2. Public outage reporting: collect any published KEPCO or telecom outage timelines for the March 2025 fires (news, agency releases) into records with `cause_evidence` pointing at the source; these are coarse and are labelled as such.
3. Compare every record with the kriged arrival-time reconstruction of the same fire: report the difference between the device's offline interval and the reconstruction's arrival time at that cell, as a table and a figure (`fig01_device_vs_reconstruction`), and with the forecast members from the cutoff before each event (`fig02_device_vs_forecast_members`).
4. Write `README.md` with the counts, the comparison statistics, the commands, hashes and a "Scope and limits" section: these are proxies for arrival, cause attribution is uncertain, coverage is where devices are, not where fire is.

## Deliverable 4: the requests that need agreements (`research/last-gasp/REQUESTS.md`)

Draft, in Korean and English, data requests for KEPCO 전력연구원 (AMI last-seen timestamps and feeder protection events in the fire counties for 21 to 30 March 2025, hashed ids, 50 m coarsening), the three mobile operators (site outage logs), and 산림청 (fire-watch camera and station logs), each with the exact fields from the contract, the privacy annex, and the analysis they enable. Do not send them; the owner sends.

## Tests

Validators reject records with missing times or impossible coordinates; a simultaneous outage of 200 meters across 20 km is classified as a grid event; a lone meter outage downwind of the front is classified fire-suspected with the right confidence; `to_arrival` never marks a cell unburned; `assimilate` leaves unobserved cells byte-identical.

## Rules

No em dashes. Figures per the shared figure rules. Never present an offline timestamp as a measured ignition time; it is an interval with a cause flag. Open a pull request "Track 1D: Last Gasp arrival observations from device outages (contract, ingestion, first dataset)". Do not merge.
