# S-D2 E3 (pinned) checkpoints: part-a CV and the three-arm state family

Data-only branch for verifying `results/cv_state_family_pinned.json` (claude/s-d2-next 40596d56) and
`results/cv_part_a_pinned.json` (4278da2d). There is no code here; the code is on claude/s-d2-next under research/harness-2026-11/S-D2/.

- `cv_ckpt_pinned/fold{0..4}.json`: the per-fold CV checkpoints (cv_part_a.py 54f22b47…, E3).
- `family_ckpt_pinned/{mcem,plugin}_fold{k}.fire{i}.npz`: 50 stage-1 state-family checkpoints (cv_state_family.py c51a1d79…, E3).
  Each holds p_grid [8 multipliers x cells], y, dist, n, seconds and env.
- `SHA256SUMS`: check with `sha256sum -c SHA256SUMS`.

Aggregate (from S-D2/, with this branch checked out at $D):
`python cv_state_family.py --brackets <brackets_v2> --cv results/cv_part_a_pinned.json --cv-ckpt $D/cv_ckpt_pinned --ckpt $D/family_ckpt_pinned --out <out.json>`

Scope: part-a fires only (allow-list sha 7db3cc0e). Covariate-free, homogeneous, 25 fires incl. 4 H-dev, not the neural refit.
