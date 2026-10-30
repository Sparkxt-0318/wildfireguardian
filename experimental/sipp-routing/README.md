# sipp-routing experimental overlay

Opt-in research code. Evidence and producing commands: research/sipp-routing/README.md. Overall track status is HOLD_PARTIAL; see research/scenario-members/TRACK_STATUS.json for exact completed and open requirements.

Use Python 3.12 with NumPy 1.26.4 and the routing constraints. Forecast export requires the separate pinned forecast environment. Add this overlay's src plus the scenario-members, sipp-routing and synthetic-truth sibling src directories to PYTHONPATH for tests. No frozen kit or checkpoint is changed. The opt-in experimental/scenario-members/export_v3.py wrapper preserves the frozen integration exporter and its publication identity.

This code concerns represented models and source support, not physical safety. Unknown source fields remain unsupported; capped computation remains unresolved. No new checkpoint default or application policy is promoted.

The separate opt-in `wfg_sipp.known_footprint` entry point can check cell-local
contact on a known journey footprint while retaining unknown off-road values.
See docs/KNOWN_FOOTPRINT_CONTACT.md for the exact finite-clock, source-binding,
history-omission and restricted-failure contract. This does not change the
strict bridge default or supply peak, dose, full-policy or risk evidence.

The independent fd8bf2e7 review found source-consistency and clock-boundary
defects beyond the original fixtures. See docs/KNOWN_FOOTPRINT_CONTACT_REPAIR.md
for repaired admission rules and the separate repair receipt. The original
fixture and receipt are preserved; native execution still requires recheck.
