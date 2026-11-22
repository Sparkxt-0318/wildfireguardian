# Allowlist-safe NIROPS reads (fix requested by the orchestrator, 12 Nov 2026)

The fix was triggered by Daniel's disclosure. The v1 pricing script `parta_price_v1_AS_RUN.py` (run once, about 13:05 UTC) read the attribute columns `Incident_C` and `UTC` for **all** NIROPS records with `read_dataframe(..., columns=['Incident_C','UTC'], read_geometry=False)` at L8, then dropped non-allowlisted rows in memory at L9. Those part b/c/d values were never printed, logged, written, counted or summarised; its output `parta_price.csv` holds only the 490 allowlisted rows. The disclosure goes in an ACCESS_CONTROL amendment, drafted by Victor and verified by Hannah.

The builder (`data-fetch/build_nirops_event.py`, L62) and `arrival_vs_union.py` (L36) used an OGR attribute filter, `where="Incident_C = '<id>'"`. Only matching features reached Python, but the driver evaluates the filter by reading every record. It is replaced here as well.

## New rule, implemented in `nirops_access.py`

1. `id_index(shp)`: reads the `Incident_C` column **alone** for all records. It reads no geometry and no other field.
2. `allowlisted_fids(...)`: computes the fids whose `Incident_C` is on the allowlist.
3. `read_by_fid` / `read_incident`: read geometry and every other column **by fid**, for allowlisted fids only. They raise `PermissionError` *before any read* if a non-allowlisted incident or fid is requested.

There is no `where=` filter anywhere.

- `test_nirops_access.py` builds a 3-record shapefile with one non-allowlisted record. It checks that the index read returns IDs only, that only the allowlisted fids are read, and that requests for the non-allowlisted incident or fid (alone or mixed) are refused. The result is in `TEST_OUTPUT.txt` (PASS).
- `build_nirops_event_v2.py` is `build_nirops_event.py` with the read replaced by `nirops_access.read_incident`. The v1 file on Main is pinned by sha in PERIMETER_MANIFEST and is not edited. For 3 hash-selected part-a incidents (the lowest sha256 of the ID: AZ-SCA-002036_Valley, CO-RTF-000363_MiddleFork, OR-781S-000115_7k), v2 output is **byte-identical** to the v1 build: arrival_time_hours.tif, grid.json, labels/cumulative_masks.npz, labels/intervals.csv, perimeters.geojson and states.npz.
- `parta_price_v2.py` is the pricing script on the same reader. `parta_price.csv` is the v1 output: 490 allowlisted rows giving incident, grid h×w, O1280 nodes, start and end, days, and slim weighted calls.

All further reads of the NIROPS shapefile use `nirops_access.py`.
