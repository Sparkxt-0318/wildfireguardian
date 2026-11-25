# NEEDS (checked 25 Nov 2026)

| item | status | what unblocks it |
|---|---|---|
| `/Users/jp/wildfireguardian-keys/keys.env` | The folder does not exist on this machine. No key was needed (OpenStreetMap through Overpass and PyPI need none). | Nothing. |
| Exposure pipeline and saved example | **Resolved 24 Nov 2026**: supplied by the user as `/Users/jp/Desktop/wildfire4.zip` (PROTOCOL.md Amendment 1). Unpacked read-only into a scratch folder; the saved example reruns bit for bit. | Done. |
| The workspace's own Python environment (`.venv` inside the zip) | Cannot be loaded on this machine: macOS refuses its unsigned libraries after download. The pinned versions from `pyproject.toml` were installed fresh from PyPI instead. | Nothing; for the user's information. |
| `/Users/jp/Desktop/wildfire` (local copy) | Older than the zip (last local commit 11 Oct 2026; no exposure code). Only its Fish Creek `grid.json` is read. | Nothing. |
| Road layer on Fish Creek | A script in this folder (`route.py`) runs the road layer's own engine unchanged; `product/` is not changed. | Done. |
| Export from the pipeline | `export_fishcreek.py`; binwise radiant and CO read from the pipeline's own weighted bins (Amendment 1 item 3). | Done; output in `export_6h/`. |
| Per-path heat and CO for all 1,024 paths (Amendment 2) | **Not needed**: about 1 s per 32 paths per hour, the full run took 5.6 min, so no 128-path subset was used. | Nothing. |
| v3 Part A routing (1,024 paths x up to 8 road-layer runs) | Run in full in 12 processes (about 2.5 h); no subset. | Nothing. |
