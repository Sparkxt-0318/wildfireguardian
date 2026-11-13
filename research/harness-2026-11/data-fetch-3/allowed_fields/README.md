# Column-trimmed copies of two pinned per-incident tables (orchestrator decision, 12 Nov 2026)

The originals below are pinned and already on Main. They are **not edited and not deleted**. Use these copies instead: they carry only the fields that S-D9 A1 §1.2 allows the split to use.

| Copy | Columns | Rows | sha256 | Original (unchanged) |
|---|---|---|---|---|
| `nirops_incidents_allowed.csv` | Incident_C, surveys, project_status, shares_irwin_with_project_fire, year | 737 | `bc9dd62f31018554a8a5d41744c13e3b1fef2ea14b86f577ad9052e226996cf1` | `data-fetch/nirops_incidents_v2.csv` (`9cd9c260…`) |
| `incident_metadata_allowed.csv` | Incident_C, irwinid, group | 733 | `d4e8e239393305ed5874ca0c6f41433e839169972c70b2a0724c648db2ec7789` | `data-fetch/incident_metadata.csv` (`5246ce8f…`) |

The originals hold more fields for **every** incident, parts b, c and d included:
- `nirops_incidents_v2.csv` adds **first_utc, last_utc, days** and irwinid.
- `incident_metadata.csv` adds **first_utc, last_utc, discovery_utc**, origin and initial lat/lon, state, WFIGS and ICS-209 names, and their dates and positions.

The earlier v1 table (`nirops_incidents.csv`, in git history at 0cf39959) also carried max_acres; that is already recorded in ACCESS_CONTROL. Anyone who has looked at those columns for a b, c or d incident should record it in S-D9 `ledger/ACCESS_CONTROL.md`. For `incident_metadata_allowed.csv`, `group` is the S-D9 part label (cohort_a/b/c/d, forecast_v2_fit or forecast_v2_heldout) and `irwinid` is the IRWIN ID that COHORT_SPLIT itself carries.
