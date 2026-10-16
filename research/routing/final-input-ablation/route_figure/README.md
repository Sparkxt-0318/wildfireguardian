# Recorded route comparison

This figure uses recorded Uiseong–Andong 2025 OSM-derived road geometry and recorded A0/A4 journeys from the final-input routing constraint ablation. No routing experiment was added.

- `route_overlay.svg`: editable vector.
- `route_overlay.pdf`: vector, one page.
- `route_overlay.png`: 3060 × 2306 RGB pixels.
- `CAPTION.md`: publication caption including checker and proof scope.
- `A0_route_geometry.csv`, `A4_route_geometry.csv`: exact edge-leg endpoint geometry drawn.
- `background_road_geometry.csv`: local road segments drawn.
- `contact_witness.json`: exact independent flame-contact witness and its position interpolation.
- `SOURCE_MANIFEST.json`: frozen input hashes and plotted quantities.
- `QA.json`: numeric checks, visual inspection and asset hashes.

Geometry is EPSG:5179 (metres). Original road source: © OpenStreetMap contributors, https://www.openstreetmap.org/copyright . The graph contains provisional direction assumptions documented in its original provenance. No external map tiles were used.

The orange dashed route is A0 (travel only); the blue route is A4 (full hazard policy). Shared roads display both styles. The red marker is predicted contact in scenario member 2, not an observed fire location. Arrival and contact times are seconds after mission departure; 09:00 UTC is the input cutoff.

To regenerate vectors and exact geometry in the original study workspace, run `build_route_figure.py` with the bundled Python (ReportLab). Export SVG to PNG at 3060 pixel width with Sharp; no asset download or dependency installation is required. No claim of physical safety or independent continuous-road radiation proof is made.
