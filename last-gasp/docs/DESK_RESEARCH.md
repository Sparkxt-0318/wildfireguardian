# Real-world check: outage data in Korea (desk research)

Compiled on 2026-10-14 from web sources by a research assistant agent in this session (web search and page fetches only; no data was requested from anyone). Full citations are in `data/SOURCES.md` under "Desk research". Confidence markers:

- [F]: the page or PDF was fetched and read.
- [S]: only a search-engine summary was seen; treat as lower confidence.
- "General": not specific to Korea.

Nothing here has been confirmed with KEPCO, an internet provider or a mobile carrier.

## 1. Smart meter (AMI) deployment in Korea

- Targets slipped badly. The 2009 to 2010 plan aimed for 22.5 million households by 2020. Only 8.48 million (about 38%) were installed by December 2019. KEPCO blamed a PLC chip interoperability audit finding, a PLC patent dispute and delayed cryptographic module certification. [F] (Newspim 2020-01-27)
- Quality problems: about 644,000 meters were recalled [F] (AI Times 2019-10-15). An article published in September 2022 gave national penetration as 48% and Gyeongbuk as the lowest region at 39% (no explicit reference year; it sits alongside 2020 to 2021 data). The same article says meter failures rose from about 135,000 in 2020 to about 216,000 in 2021, and Gyeongbuk failures rose 2.2 times. [F, re-checked by the main session] (Electimes 2022-09-19)
- Rollout reported complete: KEPCO declared its own program complete at about 20.05 million low-voltage customers in November 2024 [F] (Energy Industry News 2024-11-19). In May 2024, coverage was about 90% for KEPCO-metered customers but only about 16% in the subsidised apartment program [F] (Electimes 2024-05-23). A next-generation "AMIGO" meter tender (about 2.17 million units) followed in February 2026 [F] (Electimes 2026-02-27).
- Communications:
  - Meters talk to pole-mounted data concentrator units (DCUs), mainly over power line communication (PLC). Wi-SUN or ZigBee is used where PLC is poor. DCUs backhaul over a carrier network. Reads are at 15-minute resolution. [F] (Kim et al. 2016, KEPCO Journal; abstract of Kim et al. 2020, Energies)
  - One KEPCO patent says a DCU serves up to 200 households, but typically 20 to 50, matching the households under one transformer. [F] (US11486729B2)
- Apartments versus houses: bulk-supplied apartment complexes own their transformers and meters, so KEPCO AMI coverage there is lower [F] (Money Today 2016-08-23; Lee et al. 2024). Rural detached houses, which dominate the fire-hit areas, are KEPCO-metered. They are therefore more likely to have KEPCO AMI, but Gyeongbuk lagged in figures reported in 2022.

## 2. Are last-gasp or outage events logged?

- Korea-specific:
  - No public evidence was found that KEPCO's AMI produces timestamped meter-level last-gasp messages.
  - A 2016 KEPCO network management paper lists "outage notification" only as a generic AMI function. What the system actually described does [F] (Kim et al. 2016):
    - pings DCUs every 15 minutes;
    - flags a DCU fault after 30 minutes (minor), 1 hour (major) or 3 hours (critical);
    - raises SNMP traps for DCU cold start and lost PLC modems.
  - That is a coarse after-the-fact outage indicator, not minute-resolution last gasp. Later intervals were not found.
- Distribution automation:
  - KEPCO announced nationwide completion of its ADMS ("Grid-K") on 2025-03-06 [F] (YTN 2025-03-07).
  - Distribution automation has run since 1998, and isolates faults in about 3 minutes in Seoul [F] (T&D World 2012).
  - These systems log feeder-level faults and switch operations (SCADA/FRTU). That is probably the most useful utility-side timing data, even though it is at feeder scale.
- General:
  - Last gasp is a capacitor-powered message sent on supply loss. In large outages, collisions can block up to 80% of messages [F] (Ketchledge 2008).
  - Over PLC, a last gasp has to pass through the DCU and can take more than an hour, and fails if the line between meter and DCU is cut [F] (Clou Global 2019, updated 2026).
  - Fibre ONUs send a "dying gasp" to the provider's OLT on power loss [S] (GPON patents).

## 3. Distribution system facts used in the simulation

- 22.9 kV-Y, three-phase four-wire, multi-grounded neutral [F] (secondary reproduction of a Korea Electrical Engineers Association article; CIGRE Electra 2022).
- Concrete pole spans of 30 to 50 m appear in KEPCO-affiliated studies [F, abstract] (Kim et al. 2008). No official span standard was found.
- Reclosers and sectionalizers on mains, cutout fuses on single-phase laterals [S] (secondary source); reclosers and FRTUs confirmed by CIGRE 2022 [F].

## 4. What happened to power and telecom in March 2025

- Spread:
  - The fire line moved about 51 km from Uiseong to the Yeongdeok coast in about 12 hours, on 2025-03-25 and 26 [F] (Newsis 2025-03-27).
  - The Korea Forest Service cited a spread rate of 8.2 km/h [F] (Money Today 2025-03-27).
  - Gusts were reported near 27 m/s from the west [F] (Newsis).
  - No quantified spotting distance was found.
- Power:
  - Yeongdeok was put in a preventive power cut zone from 21:00 on 3/25, and the Yeongdeok substation cut supply pre-emptively [F] (Hankyung 2025-03-26).
  - The blackout covered about 95% of Yeongdeok county after fire-caused transmission trips [F] (Electimes 2025-04-09).
  - KEPCO data cited by a lawmaker: 18 transmission lines faulted, 2 substations lost power entirely, and about 93,000 households in Yeongdeok and Cheongsong were without power for about 9 hours [F, re-checked by the main session] (Newsis 2025-04-28).
- Telecom:
  - At 00:00 on 3/26, 1,192 base stations of the three carriers were down in the five Gyeongbuk counties [F] (Kyunghyang 2025-03-26).
  - Nationwide (including Gyeongnam), about 2,900 base stations and about 20,000 wired lines were damaged [F] (Etoday 2025-03-30; EBN 2025-03-31).
  - The ministry (MSIT) said outages in northern Gyeongbuk were "mainly caused by KEPCO's power cut-off" [F].

Implication for this project: in the real event, the dominant outage signal was upstream (transmission trips, a substation-level shutoff, and telecom sites losing grid power). That is exactly the confounder that the synthetic results show to be fatal for grid-powered nodes (`substation_trip` sweep, `RESULTS.md`).

## 5. Who holds which data, and legal constraints

| Holder | Data likely held | Notes |
|---|---|---|
| KEPCO | AMI 15-min reads, DCU/NMS alarms, ADMS/DAS/SCADA feeder fault and switch events, NDIS asset GIS | Meter-level events tied to customers are personal information under the Smart Grid Act (consent needed, Art. 22 and 23) [F, secondary mirror]. Route: pseudonymised data for research under the Personal Information Protection Act Art. 28-2, or KEPCO's Data Safe Zone (designated 2023) [F]. |
| Internet providers (KT, SK Broadband, LG U+) | OLT/BRAS session and alarm logs; possibly ONU dying-gasp alarms | Not documented publicly [S]. Korea is about 90% fibre [S]. Communications confidentiality applies (Telecommunications Business Act Art. 83). |
| Mobile carriers | Base station alarms (reported to MSIT in aggregate), connection data | Location and connection data can be compelled only for disaster response under the Framework Act on Disaster and Safety Management Art. 74-3, not for research [F, secondary mirror]. |

Statute texts were read on a secondary mirror (nepla.ai) because law.go.kr did not render; verify against the official text before relying on them.

## 6. Public outage data

- data.go.kr dataset 3068741 (KEPCO distribution outage statistics): annual, by region, counts only [F]. Useless for minute-level work.
- KEPCO's Power Data Open Portal has no visible outage dataset [F, menu only].
- No public base station or internet provider outage datasets were found.

## Precedents elsewhere (general)

- Lahaina, 2023: plug-in grid sensors (Whisker Labs) timed overnight faults, but reporters had no access to utility smart meter data [F].
- Dixie Fire, 2021: PG&E's outage system logged power loss at the ignition site hours before the fire was found [S].
- Internet outage observatories: ThunderPing [S] and IODA [F] measure residential connectivity at about 11-minute or state-level resolution.
- A 2026 review mentions AMI or SCADA outage data as a wildfire impact indicator, but no published validation of AMI last gasp as a fire-front tracker was found [F, abstract].

## Not verified

- Any KEPCO last-gasp or AMI-to-outage-management integration.
- NMS polling intervals after 2016.
- An official KEPCO span standard.
- Time series of customers out by county.
- Base stations out by carrier and time.
- Spotting distances.
- Whether 8.2 km/h is a peak or an average.
- Any audit report on AMI after 2020.
