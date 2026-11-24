# SOURCES: blocking thresholds (checked 24 Nov 2026)

No number was changed by this check. Where a primary source could not be opened, that is said.

## Carbon monoxide, AEGL-2 (final): 420 ppm (10 min), 150 ppm (30 min), 83 ppm (60 min)

* **Confirmed in the primary source.** Status "Final" on the US EPA AEGL page; the ppm values are in Table 2-1 / 2-17 of
  the NRC document. Full row, ppm (10 min / 30 min / 1 h / 4 h / 8 h): AEGL-2 420 / 150 / 83 / 33 / 27; AEGL-3
  1700 / 600 / 330 / 150 / 130; AEGL-1 not recommended. mg/m³ for AEGL-2: 480 / 170 / 95 / 38 / 31; the document's
  conversion is 1 ppm = 1.145 mg/m³ (used in PROTOCOL.md §3b).
* Meaning: AEGL-2 end point is cardiac effects in people with coronary artery disease (estimated COHb about 4 % in
  adults). It is set for the general public, including susceptible people.
* National Research Council (2010). *Acute Exposure Guideline Levels for Selected Airborne Chemicals: Volume 8.*
  Committee on Acute Exposure Guideline Levels; Committee on Toxicology. Washington, DC: National Academies Press.
  Appendix 2, "Carbon Monoxide", pp. 49–143. ISBN 0-309-14516-3. doi:10.17226/12770.
  Read: https://www.epa.gov/sites/default/files/2014-11/documents/carbon_monoxide_final_volume8_2010.pdf
* US EPA, "Carbon Monoxide Results – AEGL Program", CAS 630-08-0. Read:
  https://www.epa.gov/aegl/carbon-monoxide-results-aegl-program
* Not opened: the NCBI Bookshelf copy (returned a CAPTCHA page).

## Radiant heat 2.5 kW/m² (residents)

* **Primary source not opened** (Springer login wall). The number is confirmed by two openly readable documents that
  reproduce Purser's limit.
* Primary: Purser, D.A. & McAllister, J.L. (2016). "Assessment of Hazards to Occupants from Smoke, Toxic Gases, and
  Heat." In Hurley, M.J. et al. (eds.), *SFPE Handbook of Fire Protection Engineering*, 5th ed., Springer, New York,
  ch. 63, pp. 2308–2428. doi:10.1007/978-1-4939-2565-0_63. (4th ed.: Purser, D.A., in DiNenno, P.J. (ed.), NFPA,
  Quincy MA, 2008, section 2, ch. 6. A 6th ed. exists: Springer Cham 2026, ch. 70, doi:10.1007/978-3-031-59212-6_70.)
* Meaning, as the open documents give it: the asymptote of the radiant-flux versus time-to-severe-skin-pain curve for
  bare skin; below it, exposure "can be tolerated for 30 minutes or longer"; above it, severe pain within seconds to
  tens of seconds. A building-occupant tenability limit.
* Read: Engineers Australia, Society of Fire Safety NSW Chapter (2014). *Practice Note for Tenability Criteria in
  Building Fires*, v2.0, 3 April 2014.
  https://www.engineersaustralia.org.au/sites/default/files/2024-01/tenability-criteria-practice-note_0.pdf
* Read: SCDF Singapore (2022). *Code of Practice for Fire Precautions in Rapid Transit Systems*, Annex 7A "Tenable
  Environment", A.2.1.
* Not opened: ISO 13571:2012 (paywalled).

## Radiant heat 7.0 kW/m² (responders)

* **Primary source not opened** (CSIRO page 404 / timed out; ResearchGate 403; not in Treesearch).
* Primary: Butler, B.W. & Cohen, J.D. (1998). "Firefighter safety zones: a theoretical model based on radiative
  heating." *International Journal of Wildland Fire* 8(2): 73–77. doi:10.1071/WF9980073. The abstract (Crossref) does
  not state the value.
* Value confirmed in Butler's own later papers: Butler, B.W. (2014). "Wildland firefighter safety zones: a review of
  past science and summary of future needs." *IJWF* 23: 295–308, doi:10.1071/WF13021 (read via
  https://research.fs.usda.gov/download/treesearch/46999.pdf): the limit used by Butler and Cohen (1998) was
  7 kW/m². Butler & Forthofer (2010), *Proc. VI Int. Conf. Forest Fire Research*, Coimbra (read via
  https://research.fs.usda.gov/download/treesearch/39347.pdf).
* **Meaning corrected:** Butler describes 7.0 kW/m² as the level at which **exposed** skin develops a second-degree
  burn in under 90 s, not a limit for a firefighter in protective clothing. (The 2014 review mentions 7 kW/m² for
  clothed skin, but credits that to Rossi et al. 2011, not to Butler and Cohen.) It is used here, as instructed, as
  the responders' limit, with this meaning.

## Visibility 10 m (ASSUMPTION)

* The 10 m figure is a **building-egress** criterion: 10 m (optical density 0.08 /m) for large enclosures and long
  travel distances, 5 m for small enclosures, from Purser & McAllister (2016), SFPE Handbook ch. 63 (above; **not
  opened**).
* Read in two open sources that quote it: Gager, A.H. III & Dominguez, G. (2016). "Tenability Criteria in Unique
  Situations and Atypical Buildings." FEMTC 2016, Table 2.
  https://files.thunderheadeng.com/femtc/2016_d1-14-gager-paper.html ; and Engineers Australia (2014), above ("suitable
  for large enclosures to assist occupant way finding").
* **Origin corrected:** Jin, T. (1978), "Visibility through fire smoke", *J. Fire & Flammability* 9: 135–157, is the
  source of the visibility–smoke-density relation, not of the 10 m criterion. Jin's own escape thresholds are 13 m
  (unfamiliar occupants) and 4 m (familiar); Jin, T. (1997), "Studies on Human Behavior and Tenability in Fire
  Smoke", *Fire Safety Science – Proc. 5th Int. Symp.*, IAFSS, pp. 3–21, Table 1 (read).
* The **0.5 probability level is our choice**, not a published value (sensitivity: 0.1 and 0.9).
* Not opened: BS 7974 / PD 7974-6, ISO 13571, NFPA 130.

## PM2.5

Reported only; no threshold is applied.
