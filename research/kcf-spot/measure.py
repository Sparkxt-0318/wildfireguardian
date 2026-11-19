"""Step 2 tables (PROTOCOL section 3): every candidate spot with wind, direction, terrain and time; counts, rates,
distances, direction against the wind, and the satellite-miss estimate.

    python measure.py --work WORK --wind derived/era5_wind.csv.gz --terrain derived/spot_terrain.csv \
        --airir derived/airir_dixie.csv --out derived
"""
import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spotlib as S  # noqa: E402

ABSTAIN = HERE.parent / "kcf-abstain/derived/hours.csv.gz"
PRODUCT = {"CA": "GOFER", "CAV": "GOFER", "KR": "CHOI", "DET": "DET"}
RNG = np.random.default_rng(20261119)
NB = 1000


def boot(df, stat, by="fire"):
    fires = df[by].unique()
    g = {f: d for f, d in df.groupby(by)}
    vals = []
    for _ in range(NB):
        pick = RNG.choice(fires, len(fires), replace=True)
        vals.append(stat(pd.concat([g[f] for f in pick], ignore_index=True)))
    v = np.array([x for x in vals if np.isfinite(x)])
    return (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))) if len(v) else (np.nan, np.nan)


def load(work, wind, terrain):
    sp = pd.concat([pd.read_csv(p) for p in glob.glob(f"{work}/spots_*.csv") if Path(p).stat().st_size > 1],
                   ignore_index=True)
    sp["t_utc"] = pd.to_datetime(sp.t_utc, format="mixed").dt.round("min")
    sp["hour"] = sp.t_utc.dt.floor("h")
    w = pd.read_csv(wind)
    w["t_utc"] = pd.to_datetime(w.t_utc)
    sp = sp.merge(w[["fire", "t_utc", "era5_dir_deg", "era5_ws_ms", "era5_gust_ms"]].rename(columns={"t_utc": "hour"}),
                  on=["fire", "hour"], how="left")
    h = pd.read_csv(ABSTAIN, low_memory=False, usecols=["fire", "product", "t_utc", "gust_ms"])
    h["t_utc"] = pd.to_datetime(h.t_utc)
    fc = []
    for _, s in sp.iterrows():
        hh = h[(h.fire == s.fire) & (h["product"] == PRODUCT[s.region])]
        d = (hh.t_utc - s.hour).abs()
        fc.append(float(hh.gust_ms.values[d.values.argmin()]) if len(hh) and d.min() <= pd.Timedelta(hours=3) else np.nan)
    sp["fc_gust_ms"] = fc
    sp["angle_dw"] = S.angle_to_downwind(sp.bearing_deg.values, sp.era5_dir_deg.values)
    sp["sector"] = S.sector(sp.angle_dw.values)
    sp["local_hour"] = ((sp.t_utc.dt.hour + sp.t_utc.dt.minute / 60 + sp.lon / 15) % 24).round(1)
    if terrain and Path(terrain).exists():
        sp = sp.merge(pd.read_csv(terrain), on=["fire", "region", "spot"], how="left")
    return sp, h


def summarise(sp, h, region, conf_only):
    d = sp[sp.region == region]
    if conf_only:
        d = d[d.confirmed.astype(bool)]
    hours = h[h["product"] == PRODUCT[region]]
    fires_all = sorted(sp[sp.region == region].fire.unique().tolist() + [])
    fh = hours[hours.fire.isin(fires_all) | True].groupby("fire").size()
    n = len(d)
    out = dict(region=region, confirmed_only=conf_only, n=n, fires_with=int(d.fire.nunique()))
    if region in ("KR", "DET"):
        fh = fh[fh.index.str.startswith("KFS")]
    out["fire_hours"] = int(fh.sum())
    out["per_100_fire_hours"] = 100 * n / max(fh.sum(), 1)
    if not n:
        return out
    out["dist_km_q50"], out["dist_km_q90"], out["dist_km_max"] = (float(d.dist_km.median()),
                                                                  float(d.dist_km.quantile(0.9)), float(d.dist_km.max()))
    out["dist_now_km_q50"] = float(d.dist_now_km.median())
    out["beyond_5km"] = int((d.dist_km > 5).sum())
    for s in ("down", "cross", "up"):
        out[s] = int((d.sector == s).sum())
    out["down_minus_up"] = out["down"] - out["up"]
    out["share_down"] = out["down"] / n
    if d.fire.nunique() > 1:
        out["share_down_95"] = boot(d, lambda x: (x.sector == "down").mean())
        out["down_minus_up_95"] = boot(d, lambda x: float((x.sector == "down").sum() - (x.sector == "up").sum()))
    out["fc_gust_q50"] = float(d.fc_gust_ms.median())
    out["era5_ws_q50"] = float(d.era5_ws_ms.median())
    out["n_cells_q50"] = float(d.n_cells.median())
    out["single_pixel_share"] = float((d.n_cells == 1).mean())
    out["night_share"] = float(((d.local_hour < 6) | (d.local_hour >= 18)).mean())
    if "ridge_crossing" in d:
        out["ridge_crossing_share"] = float(d.ridge_crossing.mean())
        out["elev_change_m_q50"] = float(d.elev_change_m.median())
        out["spot_lower_share"] = float((d.elev_change_m < 0).mean())
    # downwind share by forecast gust band
    bands = pd.cut(d.fc_gust_ms, [0, 10, 15, 20, 99], labels=["<10", "10-15", "15-20", ">=20"], right=False)
    out["by_gust"] = {str(k): dict(n=int(len(g)), down=int((g.sector == "down").sum()), up=int((g.sector == "up").sum()),
                                   dist_q50=float(g.dist_km.median()) if len(g) else None)
                      for k, g in d.groupby(bands, observed=False)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--wind", required=True)
    ap.add_argument("--terrain"); ap.add_argument("--airir"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sp, h = load(a.work, a.wind, a.terrain)
    sp.to_csv(Path(a.out) / "spots_all.csv", index=False)
    res = [summarise(sp, h, r, c) for r in ("CA", "CAV", "KR", "DET") for c in (True, False)]
    if a.airir:
        d = pd.read_csv(a.airir)
        cls = pd.cut(d.area_ha, [0, 1, 10, 100, 1e9], labels=["<1 ha", "1-10 ha", "10-100 ha", ">100 ha"])
        res.append(dict(region="AIRIR_Dixie", n=len(d), nights=int(d.date.nunique()),
                        by_area={str(k): dict(n=int(len(g)), viirs=float(g.seen_viirs.mean()) if len(g) else None,
                                              gofer=float(g.seen_gofer.mean()) if len(g) else None)
                                 for k, g in d.groupby(cls, observed=False)},
                        viirs_all=float(d.seen_viirs.mean()), gofer_all=float(d.seen_gofer.mean())))
    json.dump(res, open(Path(a.out) / "measure.json", "w"), indent=1, default=float)
    for r in res:
        print(json.dumps({k: v for k, v in r.items() if k not in ("by_gust", "by_area")}, default=float))
        if "by_gust" in r:
            print("   by gust", r["by_gust"])


if __name__ == "__main__":
    main()
