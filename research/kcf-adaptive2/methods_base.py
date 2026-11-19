"""FIXED, PERSIST and the reference model M_ref (PROTOCOL 3, 5.2 item 3)."""
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from lib import ALL, FC, OWN


class Fixed:
    name = "FIXED"
    configs = [{}]

    def fit(self, cfg, D, tr):
        return None

    def predict(self, model, D, idx):
        return np.ones(len(idx))


class Persist:
    name = "PERSIST"
    configs = [{"w": w} for w in (0.5, 1.0, 2.0, 4.0)]

    def fit(self, cfg, D, tr):
        return cfg["w"]

    def predict(self, model, D, idx):
        G = D.X["g3"][idx] * 5 / 3 if D.h == 5 else D.X["g6"][idx] * 8 / 6
        return 0.375 + model * G


class GBM:
    """HistGradientBoosting quantile regression (item 3)."""

    def __init__(self, name, cols, configs):
        self.name, self.cols, self.configs = name, cols, configs

    def fit(self, cfg, D, tr):
        m = HistGradientBoostingRegressor(loss="quantile", quantile=cfg["tau"], max_depth=cfg["depth"],
                                          learning_rate=cfg.get("lr", 0.05), max_iter=cfg["iters"],
                                          min_samples_leaf=cfg.get("leaf", 200), random_state=20261119,
                                          early_stopping=False)
        m.fit(D.mat(self.cols, tr), D.S[tr])
        return m

    def predict(self, model, D, idx):
        return model.predict(D.mat(self.cols, idx))


def mref():
    return GBM("M_ref", ALL, [dict(tau=0.9, depth=3, iters=300)])
