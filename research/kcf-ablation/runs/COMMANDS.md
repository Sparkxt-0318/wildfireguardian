# Commands and hosts for the NEW RUN cells

Host: this container, Linux x86_64 (6.18), 4 cores, 15 GiB, Python 3.13.18, numpy 2.5.3. Inputs: the SHA-256-verified release
asset `WFG-evaluated-routing-inputs-20261015.zip` (`d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202`),
unpacked with `tools/fetch_routing_inputs.py --archive`. The asset was downloaded through the repository's release-asset
REST endpoint because the `github.com/.../releases/download/` URL answered 401 from this session; the digest check is the
same one `tools/fetch_routing_inputs.py` applies.

```
python3 tools/fetch_routing_inputs.py --archive inputs.zip --out $DATA
python3 research/kcf-ablation/run_v1.py --data-root $DATA --out research/kcf-ablation/runs/v1.json
for ARM in full persistence heat_off; do
  python3 research/kcf-ablation/run_v2.py --data-root $DATA --out-dir research/kcf-ablation/runs/v2 --arm $ARM \
    planner/cache/uiseong_andong_2025/*.json planner/cache/yeongdeok_2025/*.json
done
python3 research/kcf-ablation/build_cells.py
```

Wall clock (`wallclock.txt`): V1 2026-11-17 15:43:45–15:46:13Z (2 min 28 s); V2 arms started together at 15:46:31Z and ended
16:36:48Z (full, 50 min), 16:14:39Z (persistence, 28 min), 16:18:52Z (heat_off, 32 min). Each run is under the 2 h limit.
