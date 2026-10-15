# Vendored front-end files

Everything the page loads comes from this folder and from `web/`; the app fetches nothing from the network.

| File | What it is | Licence |
|---|---|---|
| `maplibre-gl/maplibre-gl.js`, `maplibre-gl.css` | MapLibre GL JS 4.7.1, the `dist/` files | BSD 3-Clause, `maplibre-gl/LICENSE.txt` |
| `fonts/PretendardVariable.woff2` | Pretendard, variable weight | SIL OFL 1.1, `fonts/Pretendard-LICENSE.txt` |
| `fonts/WFGMonoHangul-subset.woff2` | a renamed subset of D2Coding 1.3.2 (Latin, symbols, 2,574 Hangul syllables) | SIL OFL 1.1, `fonts/WFGMonoHangul-LICENSE.txt` |

## One change in maplibre-gl.js

The folder follows the package rule of no en or em dashes in any file. `maplibre-gl.js` had one of each (U+2013 and
U+2014), as two keys of its table of vertical punctuation, where they map to their vertical forms U+FE32 and U+FE31.
The two keys are now written as JavaScript escapes, `"\u2013"` and `"\u2014"`, which are the same strings when the
script runs, so MapLibre behaves exactly as before. Nothing else was changed.

- SHA-256 of `maplibre-gl.js` as released (4.7.1): `be9633c4d870e26fb37f1cfe5c5a77181667114003ea16207ac7850d8da8add1`
- SHA-256 of `maplibre-gl.js` here: `741d5bd002b1687f6504d19fe29e6992e2871a9ac4e6e8b8b6ba430e6d516564`

`tests/test_static.py` checks the second hash, and checks that no dash is left anywhere in `web/`, this folder included.
