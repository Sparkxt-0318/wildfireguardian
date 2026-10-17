"""High-precision mode (opt-in): a causal verifier of confirmed tracks.

Loaded only when the config has a `verify` section (configs/high_precision.yaml, via
`--high-precision METHOD`); the legacy pipeline never imports this package. Per confirmed
track the verifier keeps a decision (candidate, method_accepted, rejected,
insufficient_evidence) made from past and current frames only, and the high-precision
screen, counts and tables use the accepted tracks alone. "Accepted" always means accepted by
the chosen method, never proven to be an ember.

Modules: config (the overlay section), ring (recent frames), motion (camera motion and the
hotspot map), features (per-hit and per-window features, patches), models (logistic
regression and a small MLP with save/load), scorers (accept_all, rules, patch, temporal),
ledger (decisions), observer (the pipeline hooks and the high-precision LiveState). The
offline tools (`python -m wfglink verify ...`) live in cli_tools and the modules it imports.
"""
