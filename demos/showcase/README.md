# WildfireGuardian · A way through the fire

An offline, Korean-first 3D exhibition of wildfire understanding, an escape journey, and a field device. This is an **illustrative fixture showcase**, independent of the operational routing application.

## Launch on a Mac

Double-click **Launch.command**, or run this one command in Terminal:

```sh
./Launch.command
```

The launcher opens a local browser. It uses installed Node.js 20+ or Python 3; dependencies and assets are already included, so no network or npm installation is required. Keep Terminal open during the exhibition; press Ctrl+C to stop. The server binds only to `127.0.0.1` and tries ports 4173–4183 if necessary.

For a terminal-only launch: `node server.mjs`. The initial page is Korean. Choose EN for English. The page does not make cloud calls or require a map token. Direct `file://` opening cannot load JavaScript modules and is unsupported; use the launcher.

## Explore

Start demonstration plays a 108-second guided sequence. Chapter navigation, pause, restart and the timeline let you control it. Drag the terrain to orbit and scroll/pinch to zoom; manual interaction pauses the guided camera. Choose the route-following or overview view, or reset to the opening frame. Low effects reduces rendering cost. Browser reduced-motion preference starts with low effects and requires deliberate playback.

The 2D overview is available even without WebGL. Open `http://127.0.0.1:4173/?fallback=1` to force the Canvas fallback. When the tab is hidden, the animation loop stops and presentation time does not advance.

The information panel explains provenance and accepts a local JSON artifact or recorded track. Loading a track does not upload it anywhere. Source assertions are not independently authenticated. A imported track is normalized onto illustrative terrain; its elevation and playback timing are not measurements. No live telemetry is implied.

## Contents

- `index.html`, `src/`: editable source; ES modules with vendored Three.js.
- `vendor/`: Three.js 0.180.0 and license.
- `public/assets/`: owner CAD study and locally bundled fonts/licenses.
- `docs/ASSET_PROVENANCE.md`: source paths, source distinctions and asset custody.
- `docs/ARTIFACT_SCHEMA.md`, `schema.json`: bounded import interface and limitations.
- `DEMO_SCRIPT.md`: exact presentation/replay instructions.
- `qa/`: actual browser observations and refinement evidence.
- `OWNER_HANDOFF.md`: final delivery status and scientific-artifact import status.

## Reproduce development

No build is required. Vendored runtime is the reproducible exhibition payload. To restore the package-manager copy of the pinned dependency, run `npm ci --ignore-scripts --no-audit --no-fund` with a network connection; this does not change vendored files. For bounded logic checks, run `npm run check` using Node.js. These are interface/control tests, not forecast or routing validation.

No forecasting, routing solver, model checkpoint, research benchmark, account, SMS, dispatch, deployment or physical device validation is included. The comparison is two authored paths in a fixture, not evidence of superior rescue outcomes.
