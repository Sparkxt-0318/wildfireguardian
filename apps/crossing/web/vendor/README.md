# Vendored three.js (r180)

These files are copied byte for byte from `demos/showcase/vendor/` in this repository (three.js r180, MIT
licence, see `three/THREE-LICENSE.txt`). Nothing is loaded from the network: `web/index.html` maps the bare
specifier `three` to `./vendor/three/three.module.js` and `three/addons/` to `./vendor/three/addons/` with an
import map. `three.module.js` imports `./three.core.js` relatively.

Do not edit these files. To update, copy the new release over them, update the hashes below and run
`apps/crossing/tests/test_web_static.py` (it recomputes every hash and compares it with this table and with the
source copy in `demos/showcase/vendor/` when that exists).

| file (relative to `web/vendor/`) | sha256 |
|---|---|
| three/three.module.js | c8211c69345d2e9949dc7a8ac969380497aa0600a5a8ac6a459c8cd02dd9cb8a |
| three/three.core.js | eb077d2417f61d3e6d9264c317cabc4ea35769ed6b0ab533067292a550784c20 |
| three/addons/controls/OrbitControls.js | b97879c748170baadeb3fb84cea1ffdf4674e283dc06042f34e2acb95a76042c |
| three/THREE-LICENSE.txt | bfe119ea4fd413f5f7ca3fcd63adb0c4a073ed39daa2fe7d3e6b769e21272601 |
