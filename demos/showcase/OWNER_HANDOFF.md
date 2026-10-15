/Users/jp/Documents/Codex/2026-10-11/run-x20/outputs/WildfireGuardian_Showcase/

# WildfireGuardian exhibition handoff

Open **Launch.command** in that folder. The portable archive is alongside it as **WildfireGuardian_Showcase.zip**. The original authored source is `/Users/jp/Documents/Codex/2026-09-24/fu/outputs/kcf_standalone_product_website_20261011_v1/`.

The website is a Korean-first, genuine Three.js 3D exhibition: sculpted terrain and forest, evolving stylized fire and smoke, road-aligned cyan journey, moving trail, smooth chapter cameras, route-following view, north-up overview, and a product reveal using the supplied housing CAD. Start demonstration plays a 108-second narrative. English, manual exploration, local track import, low effects and a Canvas2D failure fallback are included.

## Run and present

- Double-click `Launch.command`, or run `./Launch.command` from its directory. Node.js 20+ or Python 3 is required; both assets and JavaScript dependencies are bundled. No account, CDN, map token, or internet is required for local launch.
- Keep the terminal open while presenting. Ctrl+C stops the server. The default address is `http://127.0.0.1:4173`; the launcher selects a later port if occupied.
- Use `DEMO_SCRIPT.md` for the presentation and reset/replay instructions. The default first frame is deliberately paused.
- `qa/screenshots/final-hero.png` is the final hero. The 16-second actual WebGL canvas recording is `qa/actual-scene-capture-final.webm`; it excludes the surrounding HTML interface. Full screen video was not captured.

## Evidence and scope

**Mode: fixture / illustrative demonstration. No final scientific forecast-routing artifacts were imported.** The final integration directory had no public final-ready manifest at the bounded availability check; intermediate results were not read. No real recorded track was supplied. The import workflow was exercised with explicitly synthetic QA input and accepts user-supplied recordings without authenticating them. Imported coordinates are normalized onto illustrative terrain; playback timing and elevation are not measured.

The device uses exact owner CAD housing geometry with exhibition materials and an explicitly DEMO display graphic. Owner-reported hardware completion remains distinct from this CAD view. No internals, sensor accuracy, indoor tracking, live GPS or rescue result is demonstrated. Terrain and roads are authored; fire is artistic animation; compared paths establish no safety or routing superiority.

## Verification and remaining limits

Read `qa/BROWSER_QA_REPORT.md` for final browser, motion, fallback, import and packaging evidence. Three substantive before/after visual passes and the independent review are preserved. `docs/ASSET_PROVENANCE.md` lists asset sources and hashes; `schema.json` and `docs/ARTIFACT_SCHEMA.md` document the strict local input interface.

The result is a deliberately stylized terrain diorama, not photorealism or measured Korean geography. Secondary mobile labels and the device display are small. Native phone touch, other browser engines, venue equipment and physical-device behavior were not validated. Ego kept its page visible during background tests; the visibility handler passed a synthetic-event check, but actual hidden-tab suspension remains a venue-browser check. Actual forecast raster/elevation binding is a documented future extension, not an implemented scientific adapter in this release.

No research solver/forecast source, frozen experiment, default selection, merge, deployment or publication was changed. The canonical project context receives an appended delivery record under its existing inode lock.
