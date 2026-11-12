"""Finite unions of closed integer intervals [lo, hi] (lo <= hi), kept sorted, disjoint and non-adjacent."""
from __future__ import annotations

import bisect


def normalize(ivs):
    """Sorted, merged (overlapping or adjacent pieces joined) list of (lo, hi) with lo <= hi."""
    out = []
    for lo, hi in sorted((int(a), int(b)) for a, b in ivs if a <= b):
        if out and lo <= out[-1][1] + 1:
            if hi > out[-1][1]:
                out[-1] = (out[-1][0], hi)
        else:
            out.append((lo, hi))
    return out


def contains(ivs, t: int) -> bool:
    i = bisect.bisect_right(ivs, (t, float("inf"))) - 1
    return i >= 0 and ivs[i][0] <= t <= ivs[i][1]


def subtract(piece, ivs):
    """[lo, hi] minus a normalized interval list -> list of pieces (sorted)."""
    lo, hi = piece
    out = []
    i = max(0, bisect.bisect_right(ivs, (lo, float("inf"))) - 1)
    cur = lo
    while i < len(ivs) and ivs[i][0] <= hi:
        a, b = ivs[i]
        if b >= cur:
            if a > cur:
                out.append((cur, min(a - 1, hi)))
            cur = max(cur, b + 1)
            if cur > hi:
                return out
        i += 1
    if cur <= hi:
        out.append((cur, hi))
    return out


def subtract_all(pieces, ivs):
    out = []
    for p in pieces:
        out.extend(subtract(p, ivs))
    return out


def add(ivs, piece):
    """Insert a piece into a normalized list in place (merging)."""
    lo, hi = piece
    i = bisect.bisect_left(ivs, (lo, lo))
    # merge with left neighbour if overlapping/adjacent
    if i > 0 and ivs[i - 1][1] >= lo - 1:
        i -= 1
        lo = min(lo, ivs[i][0])
        hi = max(hi, ivs[i][1])
    j = i
    while j < len(ivs) and ivs[j][0] <= hi + 1:
        hi = max(hi, ivs[j][1])
        j += 1
    ivs[i:j] = [(lo, hi)]


def max_below(ivs, t: int):
    """Largest element of the set that is < t, or None."""
    j = bisect.bisect_right(ivs, (t - 1, float("inf"))) - 1
    if j < 0:
        return None
    lo, hi = ivs[j]
    return min(hi, t - 1)


def to_set(ivs):
    s = set()
    for lo, hi in ivs:
        s.update(range(lo, hi + 1))
    return s


def from_set(s):
    return normalize((t, t) for t in s)


def measure(ivs) -> int:
    return sum(hi - lo + 1 for lo, hi in ivs)
