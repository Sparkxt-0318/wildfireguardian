# Demo builds

Each row is a commit that passed the demo gate (`scripts/tag_demo.sh`: the booth UI runs headless on the synthetic source and on an approved clip with no errors; from the booth change of 2026-10-15 on, also in ember mode on generated phones; from the fixes after the booth verification on, also through the keys A, M and Space, with the ember count checked against the scene's phones). Any of them is a working demo even if later work breaks something.

To run one: `git fetch origin && git worktree add ~/wfglink-demo <commit>`, then:

```
cd ~/wfglink-demo/wfglink
ln -s ~/wfglink-run/wfglink/data/raw data/raw     # the clips you already have
./scripts/setup_mac.sh                            # may end with a FAIL line (offline, no camera); the booth runs all the same
./booth/booth.sh
```

Builds before the setup change of 2026-10-15 (commits before the playback booth) install with `scripts/sitting1.sh` instead and expect a camera. Builds before the booth change of 2026-10-15 have no ember mode and no keys A and M.

To make a real tag (this project's cloud session cannot push tags): `git tag <tag> <commit> && git push origin <tag>`.

| Date (Asia/Shanghai) | Tag | Commit | Gate | Tag pushed |
|---|---|---|---|---|
| 20261015 | wfglink-demo-20261015 | d1bcff08f4fd | 60 s each: synthetic 563 frames, 557 paints, 0 errors; clip 459 frames, 459 paints, 0 errors | no |
| 20261015 | wfglink-demo-20261015-2 | 1c5783393797 | 60 s each: synthetic 660 frames, 635 paints, 0 errors; clip 261 frames, 262 paints, 0 errors | no |
| 20261015 | wfglink-demo-20261015-3 | 161612e99f41 | 60 s each: synthetic 652 frames, 647 paints, 0 errors; playlist 678 frames, 650 paints, 0 errors; ember 821 frames, 823 paints, 0 errors | no |
