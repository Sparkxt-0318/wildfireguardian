# live-log — prospective log of the live service

This branch holds only machine-written records of `live/` (see `live/PROTOCOL.md` §10 and `live/RUNBOOK.md` on `Main`).
Do not edit or force-push. Each 30-minute run of `.github/workflows/live.yml` appends:

- `live/log/records/YYYY/MM/DD/<issue>.json` — the record, written and pushed in the run that made it, before any outcome
- `live/log/records/YYYY/MM/DD/<issue>.sigstore.json` — Sigstore bundle (keyless, GitHub OIDC identity of the workflow;
  Rekor transparency-log entry). A `.UNSIGNED` file instead means signing failed in that run.
- `live/log/inputs/<issue>/` — the raw inputs of that run (GFS once per cycle in `live/log/inputs/gfs/`)
- `live/log/scores/<issue>.json` — the later score of a record (`live/score.py`), never earlier than issue + 32 h
- `live/log/state.json` — alert and bulletin state
- `live/site/` — the last published `/live/` site (so it can be restored)

Model output, advisory, not an official order; follow instructions from authorities.
