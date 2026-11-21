## What this shows and what it does not

* **Firefighter and witness reports, not resident trips.** The road-state rows, the burnovers and the two movements are
  what firefighters, police and some civilians reported. The two movements are fire-engine and escorted-convoy trips.
  Nothing here measures whether a resident's evacuation would have been feasible. Engines drove through conditions
  (and were damaged) that the product's closure rule treats as closed; that is the gap the passable rows measure.
* **One fire, one day, one place.** The Camp Fire on 8–9 November 2018 in Paradise, Concow and Magalia: a wind-driven
  fire that crossed the town in a few hours. The rates do not transfer to other fires, terrain or weather.
* **Observations are densest where people were.** The workbook records fire where someone saw it: along roads, at
  the hospital, at refuge areas. Cells nobody reported never close under the no-margin variant. A "miss" can be
  a cell where fire arrived but no one wrote it down; a "hit" can follow from a report made on the same road by the
  same crew. The 500 m / 60 min hold-out removes the most direct leaks; the leaky run shows how much they matter.
* **The input is not the product's real input.** The product is fed a satellite- or forecast-based arrival raster.
  Here it is fed ground reports (point locations, 15–30 min resolution, some "Inferred" times). The tests check the
  closure rule and the frozen margin on that input, not the satellite pipeline.
* **Present-day roads.** OpenStreetMap as fetched on 21 November 2026 stands in for the 2018 network. Free-flow speeds,
  no congestion; the record describes hours of gridlock, so feasible times here are optimistic for civilians.
* **Locations.** Burnover stretches are built from the report's named roads, cross streets, refuge-area coordinates and
  Table 30 lengths; the report's own map (Fig. 24) is an image and was not digitised. Two burnover places rest on
  sources outside TN 2252 (BO 12, BO 14), marked in the burnover table.
* **Not public.** The CAL FIRE AVL CSV that NIST TN 2128 §3.2.1 describes (281 apparatus, 5–12 November) and the NETTRA
  database are not public. With them, Test 3 could be run on hundreds of real apparatus trips instead of two
  narrative movements. That is the single most useful next record (see the evidence folder's `records_requests.txt`).
