# `.wfgc` certificate bundle format, version 1

ASCII text. Tokens are separated by any whitespace (space, tab, newline). Every non-keyword token is a decimal integer,
optionally with a leading `-`, fitting in signed 64-bit. Keywords are exactly as written below, in exactly this order.
Semantics are in `CERTIFICATE_SPEC.md`. An interval list `<m> lo_1 hi_1 ... lo_m hi_m` is valid only if
`lo_k <= hi_k` and `hi_k + 1 < lo_{k+1}` (sorted, disjoint, non-adjacent).

```
WFGC 1
INSTANCE
V <nV> E <nE>
DEP <dep> HOR <H> ORIGIN <origin> START <s0>
EDGES
  <tail_0> <head_0> <D_0>
  ...                                   (exactly nE triples, edge j = j-th triple; 0 <= tail,head < nV; D >= 1)
WAITABLE <k> <node_1> ... <node_k>      (strictly increasing node ids; all other nodes are not waitable)
FORBID <k> <s_1> <j_1> ... <s_k> <j_k>  (pairs, 0 <= s <= nE, 0 <= j < nE; sorted by (s, j), no duplicates)
EB <k>  then k records: <j> <interval list>   (strictly increasing j; edge blocked departure seconds)
WB <k>  then k records: <n> <interval list>   (strictly increasing n; node blocked wait-start seconds)
AC <k>  then k records: <n> <interval list>   (strictly increasing n; node acceptance seconds; listed n are destinations)
END_INSTANCE
CLAIM ROUTE <T>        or        CLAIM NO_ROUTE
WITNESS <k> then k legs, each either  E <j> <start> <end>  or  W <n> <start> <end>
CERT <T> <k> then k records: <s> <R interval list> <A interval list>   (strictly increasing s, 0 <= s <= nE)
END
```

Rules a checker must enforce (in addition to the C0–C4 conditions of the spec):

- `0 <= dep <= H`, `0 <= origin < nV`, `0 <= s0 <= nE`; if `s0 < nE` then `head[s0] = origin`.
- State `s` has head node `hd(s) = head[s]` for `s < nE` and `hd(nE) = origin`.
- `CLAIM NO_ROUTE` requires `WITNESS 0` and `CERT` threshold `T = H + 1`.
- `CLAIM ROUTE <T>` requires `dep <= T <= H`, certificate threshold equal to `T`, and a witness that is a legal lattice
  path: leg 1 starts at `dep` in state `s0`; legs are contiguous in time (`start_k = end_{k-1}`); `E j a b` needs
  `tail[j] = hd(current state)`, `(current state, j)` not forbidden, `a` not in `EB_j`, `b = a + D_j <= H`, then the
  current state becomes `j` and is admitted; `W n a b` needs `n = hd(current state)`, `n` waitable, `a` not in `WB_n`,
  `b = a + 1 <= H`, state unchanged, not admitted. After the last leg the state must be admitted (or `k = 0`, which
  is admitted at `dep`), and the final time must equal `T` and lie in `AC_hd(state)`.
- The certificate's instance identity is the SHA-256 of the exact bytes from the `I` of `INSTANCE` through the newline
  after `END_INSTANCE`. It is recorded beside the file (`.sha256` sidecar, and the run manifest) and compared with the
  instance independently re-derived from the frozen inputs. Checkers need not compute it.
- Anything else (unknown token, wrong count, trailing tokens after `END`, out-of-range ids) => reject.

Checker output: exactly one line `ACCEPT <claim> <T>` with exit status 0, or `REJECT <reason>` with exit status 1
(2 for unreadable input).
