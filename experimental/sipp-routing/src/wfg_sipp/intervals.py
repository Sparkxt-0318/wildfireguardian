"""Closed integer interval sets: sorted, disjoint, non-adjacent lists of (lo, hi) with lo <= hi."""
from __future__ import annotations

import bisect


def normalise(ivs):
    out = []
    for lo, hi in sorted((int(a), int(b)) for a, b in ivs if int(a) <= int(b)):
        if out and lo <= out[-1][1] + 1:
            if hi > out[-1][1]:
                out[-1] = (out[-1][0], hi)
        else:
            out.append((lo, hi))
    return out


def clip(ivs, lo, hi):
    return [(max(a, lo), min(b, hi)) for a, b in ivs if b >= lo and a <= hi]


def complement(blocked, lo, hi):
    """Free sub-intervals of [lo, hi] given a normalised blocked set."""
    out, cur = [], lo
    if lo > hi:
        return out
    i = bisect.bisect_left(blocked, (lo, lo)) - 1
    i = max(i, 0)
    for a, b in blocked[i:]:
        if b < cur:
            continue
        if a > hi:
            break
        if a > cur:
            out.append((cur, min(a - 1, hi)))
        cur = max(cur, b + 1)
        if cur > hi:
            break
    if cur <= hi:
        out.append((cur, hi))
    return out


def contains(ivs, t):
    i = bisect.bisect_right(ivs, (t, float("inf"))) - 1
    return i >= 0 and ivs[i][0] <= t <= ivs[i][1]


def next_member(ivs, t):
    """Smallest x >= t in the set, or None."""
    i = bisect.bisect_right(ivs, (t, float("inf"))) - 1
    if i >= 0 and ivs[i][0] <= t <= ivs[i][1]:
        return t
    j = i + 1
    return ivs[j][0] if j < len(ivs) else None


def first_in(ivs, lo, hi):
    """Smallest x in [lo, hi] belonging to the set, or None."""
    x = next_member(ivs, lo)
    return x if x is not None and x <= hi else None


class Covered:
    """Union of covered integer intervals with subtraction of new pieces (dominance by set inclusion)."""

    __slots__ = ("ivs",)

    def __init__(self):
        self.ivs = []

    def subtract(self, lo, hi):
        return complement(self.ivs, lo, hi)

    def add(self, lo, hi):
        ivs = self.ivs
        i = bisect.bisect_left(ivs, (lo, lo))
        if i > 0 and ivs[i - 1][1] >= lo - 1:
            i -= 1
        j = i
        nlo, nhi = lo, hi
        while j < len(ivs) and ivs[j][0] <= hi + 1:
            nlo, nhi = min(nlo, ivs[j][0]), max(nhi, ivs[j][1])
            j += 1
        ivs[i:j] = [(nlo, nhi)]
