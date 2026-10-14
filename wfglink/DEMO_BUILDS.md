# Demo builds

Each row is a commit that passed the demo gate (`scripts/tag_demo.sh`: the booth UI runs headless on the synthetic source and on an approved clip with no errors). Any of them is a working demo even if later work breaks something.

To run one: `git fetch origin && git worktree add ~/wfglink-demo <commit>`, then `bash ~/wfglink-demo/wfglink/booth/booth.sh` (after `scripts/sitting1.sh` has installed the environment there).

To make a real tag (this project's cloud session cannot push tags): `git tag <tag> <commit> && git push origin <tag>`.

| Date (Asia/Shanghai) | Tag | Commit | Gate | Tag pushed |
|---|---|---|---|---|
| 20261015 | wfglink-demo-20261015 | d1bcff08f4fd | 60 s each: synthetic 563 frames, 557 paints, 0 errors; clip 459 frames, 459 paints, 0 errors | no |
