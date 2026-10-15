# WildfireGuardian · A way through the fire

Premium exhibition scene, Korean default with English switch. One continuous cinematic charcoal/navy terrain composition, warm fires, cyan road journey, restrained mint destination. Huge genuine 3D landscape, no stock dashboard/cards. Hero copy: 불길을 읽고, / 돌아갈 길을 잇다. Small eyebrow WILDFIRE INTELLIGENCE / KOREA CODE FAIR 2026. Three chapters understand fire / find escape / connect field. Guided journey 108 seconds (36s each). All deterministic fixture; compact badge “일러스트 데모” and an info drawer explains evidence. Never infer live or safety superiority. Conceptual device if no usable owner model.

## Ownership
- Scene worker: src/scene.mjs only; geometry/lighting/camera/particles/route rendering.
- UI worker: src/ui.mjs + src/style.css + index.html only.
- Asset worker: src/data.mjs + src/device.mjs + public/assets/* + docs/ASSET_PROVENANCE.md + docs/ARTIFACT_SCHEMA.md + schema.json only.
- Coordinator: src/main.mjs, server.mjs, launchers, tests, integration fixes after coordination, QA, packaging, handoff.
Not alone: never revert another worker; coordinate interfaces and report changes.

## Shared API / coordinate / time contract
Use ES modules; import * as THREE from 'three'; import OrbitControls from 'three/addons/controls/OrbitControls.js'; import map points to local vendor. No build mandatory.
Scene world: x east, y elevation up, z south. Terrain x=-70..70, z=-52..52. Scene units illustrative, not measured meters. heightAt(x,z) returns elevation. Terrain visual presentation is procedural and deterministic. Roads and route follow SAME heightAt function. Scene camera should compose within #scene-host (viewport's right ~75%, expanding on mobile). Viewer handles resize from host bounds. Canvas must be visible at first frame, avoid heavy postprocessing.

src/data.mjs exports:
- heightAt(x,z): deterministic terrain height (roughly 0..24).
- demoData = {version:1, mode:'fixture', title:{ko,en}, duration:108, roads:[{id,points:[[x,z],...]}], routes:{selected:[[x,z],...], comparator:[[x,z],...]}, fire:{center:[x,z],radius:12}, destination:[x,z], start:[x,z], deviceTrace:[[x,z],...], provenance:{terrain:'illustrative',track:'scripted',...}}. Paths smoothly interpolate to follow roads; route points exist in roads.
- pointAlong(points,t): returns [x,z] for t clamped 0..1 with distance-weighted interpolation.
- validateArtifact(value) -> {ok:boolean,errors:string[]} (bounded strict schema, finite coords, source labels). Genuine track adapter may be separate; no live claim.
- loadArtifact(file): parse and validate local JSON; returns data or throws; browser only local upload, no cloud.
src/device.mjs exports createDevice(THREE) -> {group, update(seconds), dispose?}, a lit exterior at origin approx size 10x18x5; no undocumented internals. May use owner model if available with license/provenance.

src/scene.mjs exports async createScene(host, data, onInteraction) -> viewer object:
- update(state,deltaSeconds) renders. state={time:0..108,chapter:0|1|2,playing:boolean,compare:boolean,view:'cinematic'|'follow'|'overview',layers:{forest:true,fire:true},lowEffects:boolean,lang:'ko'|'en',data}. time defines fixture evolution, not wall-clock scientific duration. Ambient time may accumulate only when page visible. onInteraction pauses guided playback.
- setView(view), reset(), resize(), dispose(), getDiagnostics() returning drawCalls/triangles/renderer etc.
- optional projectLabels() -> [{id,x,y,visible}] if DOM labels useful.
Graceful WebGL failure: throw for coordinator fallback. Query ?fallback=1 forces 2D fallback.

src/ui.mjs exports mountUI(root,initialState,onAction) -> {update(state),setStatus(text),destroy()}. It creates #scene-host. onAction({type,...}) uses types play,pause,restart,chapter(index),scrub(time),compare(value),view(value),reset,lowEffects(value),language(value),layer(key,value),info,import(file). UI internal drawer interactions may be contained. State includes mode, error, reducedMotion, importStatus, elapsed animation time. Stable data-action attributes for QA.

Main orchestrates requestAnimationFrame, delta cap, hidden-tab pause, reduced-motion default, canvas fallback, local artifact import, errors. Preserve WebGL before repaint, no stats claims. Pause and scrub deterministic geometry, scene interaction pauses guided camera. Intro time 0 should already show fire and luminous path; narrative reveals emphasis without hiding hero geometry.

## Visual criteria
Beautiful wide first load with luminous topographic island, high ridges/valleys, forest canopy variation, fine contours, winding roads, glowing cyan route, clustered warm fire/smoke, compass/grid and precise annotations. Not neon spaghetti. Three chapters alter camera gently and narrative; chapter3 shows a handsome device in-scene or turntable. Left typography stays readable with negative space. Bottom compact transport timeline; chapter progress makes location obvious. Mobile retains large usable scene and touch targets; no overlapping panels. No synthetic scores or comparative wins.
