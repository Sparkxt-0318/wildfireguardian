# sipp-routing experimental overlay

Opt-in research code. Evidence and producing commands: research/sipp-routing/README.md. Overall track status is HOLD_PARTIAL; see research/scenario-members/TRACK_STATUS.json for exact completed and open requirements.

Use Python 3.12 with NumPy 1.26.4 and the routing constraints. Forecast export requires the separate pinned forecast environment. Add this overlay's src plus the scenario-members, sipp-routing and synthetic-truth sibling src directories to PYTHONPATH for tests. No frozen kit or checkpoint is changed. The opt-in experimental/scenario-members/export_v3.py wrapper preserves the frozen integration exporter and its publication identity.

This code concerns represented models and source support, not physical safety. Unknown source fields remain unsupported; capped computation remains unresolved. No new checkpoint default or application policy is promoted.
