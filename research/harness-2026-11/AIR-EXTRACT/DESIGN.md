# AIR-EXTRACT: open-ground candidates near places with no road escape (design note; SKELETON, plan only)

**Status.**
- This is a skeleton. Leo and Richard write it together. Richard has not yet agreed the split.
- **No code and no build** until Iris has assessed the finished note.
- Person-facing wording waits until Clara's pause lifts.
- Every threshold below is a **named parameter with no value** until a source is attached:
  - Sofia gives the landing-zone numbers;
  - Priya gives the radiant stand-off;
  - Daniel gives the layers.

**Owner direction (via the orchestrator, 2026-11-12 22:25 UTC).** Produce "air-extraction candidates" for places
with no road escape. It comes after current work and must not displace `no_reentry/2`.

**What this is not.**
- A candidate is "open-ground candidate", never "safe to land" and never "landing zone".
- Every table carries this line: "Whether a flight is feasible is the pilot's and the agency's decision; this table
  lists open ground only."

## A. Which places have "no road escape" (Richard; Leo supplies the packets)

**Draft definition.** A place is in the labelled set **NO_CHECKED_ROUTE** when it has no checked route under every
named timing variant: kriged_mean, firms_early, envelope and envelope_burnset.
- Packets: `no_reentry/2` (MANIFEST_v3_7, once Nora passes it).
- Router: Richard's full checker.
- It is never reported as a bare "no route".

**Split by cause.** Each place in the set gets exactly one label. The precedence is still to be fixed by Richard:
1. **at-issue.** The origin cell is already burning, or burned, at the departure.
2. **road-limited.** The only exits leave the loaded graph. The graph is clipped: the c651 window, or the export grid
   + 5 km under Daniel's rebuild. So the result says nothing about roads outside it.
3. **fire-limited.** Inside the loaded graph, every exit is blocked by fire under every variant.

**Sensitivity to waiting.**
- Waiting is allowed only at graph dead-end nodes, as supplied in graph.json; the rule is undocumented and the owner
  has been asked.
- The set is also reported under "waiting nowhere" and under "waiting anywhere". Membership that changes between them
  is flagged.

**Departure grid.** As in Richard's headline: the 30-min grid, per region, start and horizon.

**Open (Richard).**
- Is "every variant" the right quantifier? The alternative is to report per variant and the intersection.
- How is a place mapped to its origin node(s)?

## B. Candidate-site rule (Leo; layers from Daniel; thresholds from Sofia)

**Layers.** These are asked of Daniel; nothing is fetched yet.
- **OSM polygons** (Korea extracts: the export grid + 5 km): school grounds (amenity=school), sports pitches and
  centres (leisure=pitch/sports_centre/stadium), car parks (amenity=parking), farmland, meadow and grass
  (landuse=farmland/meadow/grass), and existing helipads and heliports (aeroway=helipad/heliport).
  - OSM completeness in rural Gyeongbuk is unknown and is reported per region.
  - A missing polygon means **no candidate**, never "no open ground".
- **Tree cover.** Product to be decided (Daniel). Candidates: ESA WorldCover 10 m, Hansen GFC, Korean national land
  cover. One product is chosen and its date stated.
- **Slope.** A DEM to be decided (Daniel). Candidates: Copernicus GLO-30, SRTM, Korean NGII.

**Rule.** All parameters are named; their values are TBD from sources.
- **Open ground.** An OSM open-ground polygon, or a raster patch whose tree cover is at most `TREE_MAX` over a clear
  area of at least `CLEAR_MIN_M` diameter.
- **Slope.** The site's slope is at most `SLOPE_MAX_DEG` over that area.
- **Not modelled.** Obstacles (wires, masts, buildings) are not modelled beyond OSM building footprints, if those are
  used. This is listed in C.

**Output of B.** A static candidate set per region, with the source layer and its vintage for each site. Nothing in B
depends on fire.

## C. Time condition (Leo: arrival margins from packets; Priya: stand-off)

At departure time t, under a timing variant v, a candidate site is **open at t under v** when all three hold:
1. no cell within `BUFFER_M` of the site is burning, or has burned, at t;
2. the forecast arrival in that buffer is later than t + `MARGIN_MIN` under v;
3. no cell burning at t is within the radiant stand-off `STANDOFF_M` (Priya's table, cited as is).

**Burned buffer cells.** Under `no_reentry/2`, "has burned" uses C0 ∪ born cells. That is the same closure as the
routing packets, so a burned-out buffer cell counts as not open.

**Ranges.** Results are reported per variant: the window over t is a **range across variants, not a point**.
envelope_burnset is static, so it gives the most restrictive reading.

**NOT modelled, listed in every table:**
- smoke and visibility;
- wind at the site;
- wires and obstacles (beyond the stated layers);
- night;
- aircraft availability, range and turnaround;
- crew procedures;
- ground conditions (soft field);
- people's ability to reach the site.

## D. Output: a planning table for staff and agencies (Leo)

One row per place in the A set:
- the cause label;
- the **nearest k open-ground candidates**, k to be fixed;
- for each candidate:
  - the distance from the place on foot (straight line and along roads/paths if the graph has them, both labelled);
  - the source layer;
  - the **time window per variant** in which C holds.

Header line: "Open-ground candidates only. Whether a flight is feasible is the pilot's and the agency's decision."

## E. What the March 2025 replay could check (Richard and Leo)

- Whether places in the A set match places where evacuation by air or rescue was reported.
  - This needs a sourced incident list (NFA/KFS reports or press, to be named).
  - Without one, nothing is validated, and the note says so.
- Whether the OSM candidates near those places include any site that was actually used (sourced).
- Whether the time windows in C were open at the reported times.

These are checks against reported events, not proof that a site is usable.

## Inputs pending

| Who | What | Status |
|---|---|---|
| Richard | Agree the split; A definition, cause precedence, waiting sensitivity; E | asked |
| Daniel | Korea tree-cover/DEM products, OSM open-ground polygons in the extracts | asked |
| Sofia (via orchestrator) | Sourced LZ size, slope, obstacle values | asked |
| Priya (via orchestrator) | Radiant stand-off table and its assumptions | asked |
| Iris | Assessment of the finished note before any build | after the draft |
