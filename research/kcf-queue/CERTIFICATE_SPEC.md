# Certificate format `kcf-queue.cert/1` and the rules a checker enforces

A certificate says: "these vehicles, on these timed routes, all reach an accepted shelter, and no capacity or closure
rule is broken." It proves **feasibility of the listed schedule only**. All times are integers (seconds after the issue
time `T`). Everything is plain JSON. A checker needs nothing but this file.

```json
{
  "schema": "kcf-queue.cert/1",
  "H": 28800, "dwell": 120, "bin_s": 60,
  "rho": 0.85,
  "data": {
    "cell_close": {"<cell>": <closure second, int>},
    "nodes":  {"<node>": {"cell": <cell>}},
    "edges":  {"<edge>": {"tail": <node>, "head": <node>, "D": <int>=1.., "cap_vph": <int>,
                          "segs": [[<cell>, "<num>/<den>"], ...]}},
    "forbidden": [[<edge i>, <edge j>], ...],
    "shelters": [<node>, ...]
  },
  "input_sha256": "<hex>",
  "owners": [ {"id": "<village id>", "origin": <node>, "N": <int>, "start": <int>, "spread": <int>, "role": "subject"|"neighbour"} ],
  "vehicles": [ {"owner": "<id>", "k": <0..N-1>, "path": [[<edge>, <entry second>], ...]} ],
  "claim": {"subject": "<id>", "all_cleared": true,
            "binding": {"kind": "edge"|"node"|"shelter", "id": <edge or node>, "vehicle": [<owner>, <k>], "slack": <int>}}
}
```

`input_sha256` = SHA-256 of the UTF-8 bytes of `json.dumps(data, sort_keys=True, separators=(",", ":"))`.
Keys of `cell_close`, `nodes`, `edges` are strings of integers. Exactly one owner has role `subject` and it equals
`claim.subject`.

## Rules (each failure is reported with the code in brackets)

**R0 [HASH]** `input_sha256` matches `data`. **[SCHEMA]** all fields present, integers where stated, `D >= 1`,
`0 <= entry <= H`, exactly one subject.

**R1 [RELEASE_CURVE / COUNT]** For every owner, the vehicles of that owner are exactly `k = 0..N-1`, each once, and the
release second of vehicle `k` is `r_k = start + floor(spread * (2k+1) / (2N))` (integer arithmetic). `N >= 1`.

**R2 [ROUTE]** Each path is non-empty. The tail of the first edge is the owner's `origin`. For consecutive entries
`(e_i, t_i), (e_{i+1}, t_{i+1})`: `head(e_i) = tail(e_{i+1})`, `[e_i, e_{i+1}]` is not in `forbidden`, and
`t_{i+1} >= t_i + D(e_i)`. The first entry satisfies `t_0 >= r_k`.

**R3 [EDGE_CLOSED]** The edge cutoff `lo_e` is derived from the data: for each `[cell, z]` in `segs` of `e` with the
cell in `cell_close` (closure second `b`), `s_c = max(ceil(b - D*z), 0)` with `z` the exact fraction (`ceil` of an
exact rational); `lo_e` = minimum of those `s_c`, or "none" if no segment cell is closed. Entry at `t` is allowed iff
`lo_e` is none or `t < lo_e`.

**R4 [WAIT]** Let a vehicle be at a node `u` from time `a` (`a = r_k` at the origin, `a = t_i + D(e_i)` after edge
`e_i`) and enter the next edge at `t >= a`. Let `b_u` = `cell_close[nodes[u].cell]` if present. If `t > a` (it
waited) then `t < b_u` is required when `b_u` exists. At the **origin** the condition `t < b_o` is required even when
`t = a`, if `b_o` exists. Nothing else is required of a node the vehicle passes through without waiting.

**R5 [CAPACITY]** `n_e = max(1, floor(rho * cap_vph / 60))` (use exact rational arithmetic for `rho` given as a decimal
string if needed; `rho` here is a JSON number with at most 2 decimals, so compute `floor(round(rho*100) * cap_vph /
6000)`). For every edge `e` and every bin `m` the number of entries `(e, t)` over **all vehicles of all owners** with
`t // bin_s = m` is at most `n_e`.

**R6 [SHELTER]** The last edge's head is in `shelters`. With arrival `a = t_last + D(last)` the accepted set is
`[0, H - dwell]` minus `[max(b - dwell, 0), H]` when the shelter node's cell has a closure second `b`, so the condition
is `0 <= a <= H - dwell` and, if `b` exists, `a < max(b - dwell, 0)`. A shelter node may appear as an intermediate head
of a path; only the end of the path is tested.

**R7 [CLAIM]** `all_cleared` is true only if rules R1–R6 hold for every vehicle of every owner. The checker also
recomputes the **binding element of the subject** and compares it with `claim.binding`: over the subject's vehicles,
slacks are: for each entry `(e, t)` with a finite `lo_e`: kind `edge`, id `e`, slack `lo_e - 1 - t`; for each wait
(`t > a`) at node `u` with `b_u`: kind `node`, id `u`, slack `b_u - 1 - t`; for each vehicle's arrival: kind
`shelter`, id the shelter node, slack `min(H - dwell, max(b - dwell, 0) - 1) - a` (just `H - dwell - a` when the shelter cell has no closure). The binding element is the minimum by
`(slack, kind order edge < node < shelter, id, owner, k)`. **[BINDING_MISMATCH]** if the claim differs.

A certificate is **VALID** iff there is no failure. The checker returns the list of failures (code, owner, k, detail)
and, when valid, the slack of the binding element.

Notes. The vehicles are interchangeable, so the order of entries within a bin is not checked (FIFO is realisable by
relabelling, PROTOCOL §3.5). Capacity counts include neighbour vehicles. The checker does not decide whether the
neighbours themselves clear: it checks them with the same rules because their reservations are part of the schedule.
