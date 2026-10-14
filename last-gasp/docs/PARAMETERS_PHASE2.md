# Phase 2 parameters and defaults

All parameters are in `configs/phase2.json`. Phase 1 parameters are in `configs/default.json`, documented in `docs/PARAMETERS.md`. Results are synthetic.

Source markers:
- [R]: read by the research agent.
- [verified]: re-checked by the main session.
- [S]: snippet only.
- "derived": computed here from cited values.
- "assumption": no source was found.

Full URLs are in `data/SOURCES.md`.

## Tag layouts (`layout`)

| Key | Default | Reason |
|---|---|---|
| `kind` | `roads` | Tags along drivable OSM roads. `edge` uses a forest-edge proxy (the line 100 m from the nearest building), because no land-cover data are used. |
| `spacing_m` | 100 (item 1 uses 200) | Minimum 2D separation after greedy thinning of 5 m samples. Dense road networks give fewer tags per km of road than 1000/spacing, so the tags actually achieved per km are reported. |

## Tags (`tag`)

| Key | Default | Reason or source |
|---|---|---|
| `death_delay_min` | 0.17 to 2.0 min (10 to 120 s) after flame arrival | Unprotected motes in fire last "on the scale of seconds" (Antoine-Santoni et al. 2009 [R]). Flame radiant flux of 24 to 166 kW/m² [S]. Electronics rated to 85 to 120 °C, solder melts at 217 °C, lithium at 180.5 °C [S]. The 10 to 120 s range is the agent's reasoned estimate, not a measurement. |
| `p_die_given_fire` | 0.95 | Assumption. A few tags survive (for example on bare ground). |
| `random_failure_rate_per_h` | 0.0005 | Assumption. |

## Radio (`radios`)

Path loss PL(d) = alpha + 10 n log10(d / 1 m) + X, where X ~ N(0, sigma) is drawn once per link. A link is up if EIRP - PL >= sensitivity + fade margin. The fits include antenna and vegetation effects, so the extra antenna gain is 0 dBi.

| Profile | EIRP | Sensitivity | Tag to tag (alpha, n, sigma) | Tag to gateway (alpha, n, sigma) | Median range tag-tag / tag-gw (derived) |
|---|---|---|---|---|---|
| `lora` (default, SF7, 125 kHz) | 14 dBm | -124 dBm | 46.04, 3.63, 8.85 | 30.62, 3.22, 8.0 | 282 m / 1.74 km |
| `lora_sf9` | 14 dBm | -129 dBm | same | same | 388 m / 2.49 km |
| `lora_pessimistic` | 14 dBm | -124 dBm | 23.18, 4.68, 11.38 | 46.04, 3.63, 8.85 | 245 m / 282 m |
| `ble` (1 Mbps, +8 dBm) | 8 dBm | -95 dBm | 40.07, 3.70, 5.38 | same | 42 m / 42 m |

Sources for the radio values:
- **EIRP.** KR920-923: end devices default to 14 dBm EIRP on 922.1 to 923.3 MHz and gateways to 23 dBm; channel access is listen-before-talk (LoRa Alliance RP002-1.0.3, section 2.11.2 [verified]). Korean rules (MSIT Notice 2019-105 [R]): band 917 to 923.5 MHz, listen-before-talk with at most 4 s per transmission and 50 ms idle. Beacons every 10 to 60 s are allowed under listen-before-talk.
- **Sensitivity.** SX1262 datasheet: -124 dBm at SF7 and 125 kHz [R]; SF9 is about -129 dBm (derived from the datasheet SNR limits). nRF52840: -95 dBm at 1 Mbps, TX up to +8 dBm [R].
- **Tag to tag, LoRa.** Callebaut and Van der Perre (2020), 868 MHz near-ground point-to-point in forest, 40 to 900 m, all data. Values as re-fitted by Azevedo and Mendonca (2024, Sensors 24:3877, Table 12 [R]).
- **Tag to gateway, LoRa.** Boonlom et al. (2026, Sensors 26:3192 [verified]): 923.2 MHz, about 14 dBm, transmitter at 1.7 m, gateway at 8 m, forest, up to 1.2 km. RSSI = -16.62 - 32.24 log10(d), so PL = 30.62 + 32.24 log10(d). The paper gives no sigma, so 8 dB is assumed, in line with forest LoRa fits of 6 to 9 dB (Bianco and Marrocco 2023, sigma 8.05 dB [R]; Lima et al. 2024, RMSE 6.2 to 6.7 dB [R]).
- **Pessimistic LoRa.** Tag to tag uses the Callebaut fit "below the transitional region" (n = 4.68, RMSE 11.4 dB). Tag to gateway uses the near-ground fit, so the gateway gets no height advantage. This stands in for ridges blocking line of sight in Korean hills: Myagmardulam et al. (2021) lost the 920 MHz link completely behind a ridge [S]. No Korean forest measurement was found.
- **BLE.** Gay-Fernandez et al. (2010), 2.45 GHz in forest, 1 to 150 m (fit as tabulated in Azevedo and Mendonca 2024 [R]).
- **Fade margin.** 3 dB, an assumption covering small-scale fading and flames near the path. Fire adds mostly 0 to 6 dB, occasionally 10 to 16 dB (Hong et al. 2021, ETRI compartment fire [R]), so a flame does not normally break a neighbour's link.

## Reception (`reception`)

| Key | Default | Reason |
|---|---|---|
| `mode` | `mesh_sf` | `star` = direct to gateway (LoRaWAN-like); `mesh` = relaying up to `max_hops`; `mesh_sf` adds tag-side store-and-forward, which turns out identical to `mesh` because fire only removes links. |
| `max_hops` | 8 | Assumption. |
| `heartbeat_s` | 30 | A battery life of 3.3 years at SF7 (below); swept from 10 to 120 s. |
| `timeout_beats` | 3 | A death is declared after 3 missed heartbeats. |
| `step_min` | 1 min | Simulation step. |

## Gateways (`gateways`)

| Key | Default | Reason |
|---|---|---|
| `count` | 4 (swept 1 to 12) | Greedy placement on utility pole positions, maximising expected tags reached (directly, or within `max_hops` for mesh). |
| `hardened` | false | Exposed gateways burn. Hardened ones (for example on a concrete roof or outside the fire area) survive. |
| `p_destroyed_given_fire` | 0.9 | Assumption. |
| `death_delay_min` | 0 to 5 min | Assumption. |
| `power` | battery | A solar-plus-battery gateway kit is sold for more than 5 days without sun (RAK, [R]). `grid` makes the gateway die with its local feeder (phase 1 model). |
| `backhaul_fail_min`, `backhaul_restore_min`, `buffer` | none, none, true | Cellular backhaul outage scenario. In 2025, 1,192 base stations were down in the five counties (phase 1 desk research). With `buffer`, a live gateway stores records and sends them at restore. |

## Trip logs (`trips`)

| Key | Default | Reason or source |
|---|---|---|
| `logged_kinds` | breaker, recloser | Only SCADA/FRTU-monitored devices are logged. Fuses and transformer cutouts are not monitored (KEPCO DAS uses FRTUs at automated switches [R]). |
| `p_type_logged` | 1.0 (swept to 0) | Whether a log distinguishes a protection trip from a remote or manual open. Not verified for KEPCO. |
| `clock_sd_s` | 1 s | Assumption. Time synchronisation for KEPCO FRTUs was not verified. |
| `precaution` | none; blanket at 60 min; proximity at 500 m or 0 m with a 10 min decision delay | Yeongdeok emergency de-energisation zone from 21:00 on 2025-03-25 [R]. Reactive cut of lines already reached by fire on 2025-03-22 [verified]. |
| `logging_stops_min` | none (scenario: 40 min) | "Automation equipment all stopped" in Yeongdeok [verified]. |
| `coordination_window_min`, `coordination_min_others` | 2 min, 1 | Untyped breaker opens within 2 min of another breaker are treated as a coordinated (precautionary) action. |
| `tag_check_margin_min`, `tag_check_radius_m` | 10 min, 500 m | An entry is not counted as fire if tags say the fire reached the zone more than 10 min after the trip. The check is applied only where an observed tag death lies within 500 m of the zone. |
| `assumed_fault_delay_min` | 5 min | Mean of the phase 1 fault delay (0 to 10 min). |
| `tag_spacing_m` | 400 (swept 200 to 1600) | Sparse tags to combine with trips. |

## Economics (`economics`)

All prices are in USD as seen on 2026-10-15 for quantities of about 100 to 1,000; they are estimates, not quotes.

| Key | Default | Source |
|---|---|---|
| LoRa module | 6.49 | RAK3172 (STM32WL + SX1262, KR920 variant, TCXO), RAK store [R] |
| Battery | 5.60 | Saft LS14500 LiSOCl2 AA, 2.6 Ah, Digi-Key 480+ [R]. EVE ER14505 is about €1.95 [S]. |
| Enclosure | 10.00 | Hammond 1554 IP68 polycarbonate, about A$15 at 50+ [S]. Cheaper IP67 ABS boxes exist but were not researched. |
| PCB, assembly, passives | 3.00 | Assumption informed by JLCPCB assembly pricing [R]. |
| Antenna | 1.00 | Assumption. |
| Tag total | 26.09 | Derived. The agent's range was 12 to 30. |
| Tag install | 5.00 per tag | Assumption (about 10 min of field labour). |
| Battery replacement service | 5.00 per tag per replacement | Assumption. |
| Gateway | 1,249 | RAK WisGate Edge Pro Solar bundle, KR920 with LTE, 8 channels, $1,199 [R], plus an antenna (about $50, assumption). |
| Gateway install | 500 | Assumption (pole mount, permits). |
| Gateway backhaul | 60 per year | Assumption. Korean IoT data plan prices were not verified. |
| SX1262 TX at +14 dBm | 45 mA | Datasheet [R] |
| MCU and listen-before-talk awake time | 5 mA for 10 ms per beacon | Derived from SX1262 RX current of 4.6 mA plus about 6 ms of listen-before-talk [R]; assumption for wake overhead. |
| Sleep | 3 µA | SX1262 sleep 0.6 to 1.2 µA plus MCU; agent estimate [R] |
| Time on air | 41.2 ms for 12 bytes at SF7 | Semtech formula (derived; matches the agent's value) |
| Battery usable fraction | 0.8 | Assumption |
| Self-discharge | 2% per year | Saft states below 1% per year at 20 °C [R]; doubled for hot summers (assumption) |
| BLE advertising event | 20 µC | Nordic estimate for nRF51 [S] |
