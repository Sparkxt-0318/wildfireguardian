"""cv_part_a.fit_mcem resumed from a mid-chain checkpoint equals an uninterrupted run, bit for bit."""
import numpy as np

import cv_part_a as C
import synthetic as S


def test_mcem_resume_bit_identical(tmp_path):
    fires = []
    for sd in (1, 2):
        p = S.make_problem(sd, n=20, radius=1, T=24.0, n_seeds=2, scale=0.08)
        fires.append((p, S.observe_perimeter(p, every=8.0)))
    a = C.fit_mcem(fires, np.random.default_rng(7), iterations=4, average_last=2)
    ck = tmp_path / "st.pkl"
    C.fit_mcem(fires, np.random.default_rng(7), iterations=2, average_last=2, ckpt=ck)     # "crash" after 2
    b = C.fit_mcem(fires, np.random.default_rng(999), iterations=4, average_last=2, ckpt=ck)  # resume (seed ignored)
    assert np.array_equal(a, b)
