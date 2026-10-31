# Decisions

Dated, one line of reason each. Interface changes also bump `hazard_contract.CONTRACT_VERSION`.

- **2026-10-31** — Program started in a Claude Code cloud container, not on the Mac.
  Reason: the session was launched in the cloud; work that needs no Mac data proceeds here,
  data-dependent work is flagged as blocked rather than replaced with synthetic data.
- **2026-10-31** — `claude/ecstatic-keller-fm31to` mirrors `next/integration`.
  Reason: the cloud session must push its designated branch; Siyeong's branch layout is kept.
- **2026-10-31** — Bench lock = Python `fcntl.flock` on `<main checkout>/program/.bench.lock`
  via `program/benchlock.py`. Reason: stock macOS lacks `flock(1)`; one file shared by all
  worktrees.
- **2026-10-31** — Per-folder `.gitignore` files instead of editing the root `.gitignore`.
  Reason: the root is part of the frozen release.
- **2026-10-31** — No torch in the cloud venvs for now. Reason: the CPU wheel index is blocked
  and the PyPI Linux wheel set is over 1 GB (needs approval); c651 needs Mac data anyway.
