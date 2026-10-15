# Local artifact contract · version 1

The website runs from a self-contained deterministic fixture. Its 108 seconds are presentation time, not fire simulation time. Scene coordinates use x east, z south in arbitrary visual units. Terrain is always the procedural `heightAt(x,z)` function. Fire is always an illustrative radial visual. Import does not run a forecast, compute escape routes, or verify safety.

A local file is read in the browser using `File.text()` and `JSON.parse()`. No upload, remote fetch, account, analytics, or cloud processing is involved in the import path. A successful import means format validation passed; it does not authenticate the source, its labels, or any result. Source text must be rendered as text, never HTML.

## Scene JSON

The exact supported shape is `schema.json`, definition `scene`. `public/assets/illustrative-scene.json` is the full valid built-in example. Required fields:

| Field | Contract |
|---|---|
| version | Exactly 1 |
| mode | fixture, artifact, or recorded; never live |
| title | ko and en strings, 1–120 characters |
| duration | Exactly 108 presentation seconds |
| roads | 1–128 objects, each unique id and 2–4,000 points; 30,000 road points total |
| routes | selected and comparator paths; both connect the declared start to destination |
| fire | center [x,z] and radius 0–30; radius 0 hides fire |
| start / destination | [x,z] |
| deviceTrace | 2–4,000 [x,z] points |
| provenance | terrain, roads, fire, routes, track, device, source |

Every position must be finite, with x in [-64,64], z in [-46,46]. Every adjacent pair in both route paths must reuse an exact adjacent road pair (either direction); including only the same endpoints is insufficient. Repeated coordinates are permitted and interpolation handles zero-length segments. Unknown fields are rejected. The runtime validator also enforces endpoint equality, unique road ids, the aggregate limit, and provenance-mode consistency; JSON Schema alone does not express all these cross-field rules.

`provenance.terrain` and `.fire` must be `illustrative`. This renderer does not consume DEMs, elevation rasters, fuel maps, forecast rasters, probabilities, uncertainty ensembles, hazard units, support masks, or scientific timing. `.roads` may be `illustrative` or `imported-artifact`; `.routes` may be `scripted` or `imported-artifact`. These imported values identify supplied coordinates only. `.track` is `scripted` or `recorded-user-supplied`. `.device` is always `owner-cad-study` because this version displays the bundled owner housing exterior. `.source` is a required 1–2,000-character attribution and context string.

`fixture` requires illustrative terrain/roads/fire and scripted routes/track. `recorded` additionally requires recorded-user-supplied track, scripted routes, and illustrative roads. `artifact` permits supplied route/road coordinate geometry, but its terrain and fire remain illustrative. Imported sources do not acquire verified, live, measured, final-ready, or safe status from successful parsing.

## Recorded track JSON

A second small format is accepted by `loadArtifact` and adapted into the scene contract:

```json
{
  "version": 1,
  "kind": "recorded-track",
  "title": "Your recording title",
  "coordinates": [[129.0, 36.0], [129.001, 36.001]],
  "source": "Describe the actual recorder, export, and permission to use this track",
  "recordedAt": "2026-10-11T09:00:00+08:00"
}
```

The coordinates above are a schema illustration, not a supplied or claimed real recording. Replace them with an authorized local recording. `coordinates` contains 2–4,000 WGS84 [longitude,latitude] pairs; longitude is within ±180°, latitude strictly inside ±85°. A source string is mandatory. `recordedAt` requires an ISO timestamp with timezone. Extents greater than two degrees, date-line crossings, and tracks with negligible extent are rejected. Unknown fields are rejected.

The adapter applies a local equirectangular projection about the bounding-box center, scales the track uniformly into the scene, and does not preserve measured distance, elevation, speed, or timing. It creates identical selected/comparator paths from the supplied track, hides fire, and sets the mode to `recorded`. The playback is illustrative and does not represent a solved evacuation route. The source's assertion that a track was recorded remains unverified. No demo track is portrayed as a real recording.

## Limits and reserved extensions

Files must be between 2 bytes and 5 MiB. Only JSON is accepted; CSV/GPX/GeoJSON adapters are not included. The presentation retains the 108-second timeline for imported data. Future scientifically grounded artifacts need explicit georeferencing, elevation binding, raster values and units, support, time semantics, provenance, and a real renderer implementation before those fields can be accepted. There is no final forecast artifact bundled into this release.
