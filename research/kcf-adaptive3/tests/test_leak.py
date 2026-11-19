"""Leakage tests (PROTOCOL section 2). L1: nothing after hour t changes p_t or the margin at t.
L2: scrambling the labels and outcomes of the forecast fire leaves its output unchanged."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib3 import Tracker, load

NOARCH = {"trans": ["gust_ms", "w850_ms", "rhmin_pct", "sin_h", "cos_h"]}


def _setup():
    D = load()
    m = Tracker("T", NOARCH)
    tr = D.rows_of(D.dev[:8])
    te = D.rows_of([D.dev[9]])
    return D, m, m.fit(m.configs[0], D, tr), te


def test_L1_future_does_not_change_past():
    D, m, mdl, te = _setup()
    base = m.predict(mdl, D, te).copy(); p0 = m.last["p"].copy()
    cut = len(te) // 2
    rng = np.random.default_rng(0)
    keep = {c: D.X[c].copy() for c in D.X}
    S = D.S.copy()
    for c in D.X:
        D.X[c][te[cut:]] = rng.permutation(D.X[c][te[cut:]])
    D.S[te[cut:]] = 99.0
    alt = m.predict(mdl, D, te); p1 = m.last["p"]
    for c in keep:
        D.X[c][:] = keep[c]
    D.S[:] = S
    assert np.array_equal(base[:cut], alt[:cut]) and np.array_equal(p0[:cut], p1[:cut])
    assert not np.array_equal(base[cut:], alt[cut:])


def test_L2_own_labels_unused_online():
    D, m, mdl, te = _setup()
    base = m.predict(mdl, D, te).copy()
    S, z = D.S.copy(), D.z.copy()
    D.S[te] = np.random.default_rng(1).permutation(D.S[te]); D.z[te] = 1 - D.z[te]
    alt = m.predict(mdl, D, te)
    D.S[:], D.z[:] = S, z
    assert np.array_equal(base, alt)
