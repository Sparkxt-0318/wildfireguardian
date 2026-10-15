# Data provenance and distribution scope

The repository publishes project source, the selected forecast checkpoint, reviewed result tables, figures and version manifests. Release assets provide the original bounded routing evidence, independent evidence, evaluated routing packets/requests/graphs and the separate forecast-ablation evidence. Every asset has a SHA-256 checksum.

OpenStreetMap-derived road data are attributed to OpenStreetMap contributors under the Open Database License: https://www.openstreetmap.org/copyright . Grid CRS, scenarios, units, source versions and declared probability-zero policy remain in the evaluated packet metadata.

External environmental rasters, upstream prepared training arrays and observed-survey inputs are not silently bundled into a clean-machine installation. Obtain them through the source-specific instructions and retain the original access, attribution and redistribution conditions in `forecast/`. The owner-local runtime companion is retained locally and is not automatically a publicly licensed dataset.

Vendored Three.js and IBM Plex fonts retain their included licenses. Owner-supplied housing meshes remain a separate design study. No new blanket license is granted over upstream assets by this packaging update.

Real device recordings, browser profiles, privacy secrets and device logs are excluded. The included map sessions are explicitly simulated fixtures; benchmark roads and scenario maps are research inputs.
