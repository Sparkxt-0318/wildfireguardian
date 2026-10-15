# Demo builds

Each row is a commit that passed the demo gate (`scripts/tag_demo.sh`: the booth UI runs headless on the synthetic source and on an approved clip with no errors). Any of them is a working demo even if later work breaks something.

To run one: `git fetch origin && git worktree add ~/wfglink-demo <commit>`, then `cd ~/wfglink-demo/wfglink && ./scripts/setup_mac.sh && ./booth/booth.sh`. Builds before the setup change of 2026-10-15 (commits before the playback booth) install with `scripts/sitting1.sh` instead and expect a camera.

To make a real tag (this project's cloud session cannot push tags): `git tag <tag> <commit> && git push origin <tag>`.

| Date (Asia/Shanghai) | Tag | Commit | Gate | Tag pushed |
|---|---|---|---|---|
| 20261015 | wfglink-demo-20261015 | d1bcff08f4fd | 60 s each: synthetic 563 frames, 557 paints, 0 errors; clip 459 frames, 459 paints, 0 errors | no |
| 20261015 | wfglink-demo-20261015-2 | 1c5783393797 | 60 s each: synthetic 660 frames, 635 paints, 0 errors; clip 261 frames, 262 paints, 0 errors | no |
