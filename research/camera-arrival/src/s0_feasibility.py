#!/usr/bin/env python3
"""Step 0 feasibility gate: GOFER fires x HPWREN cameras.

Run:  python3 -I src/s0_feasibility.py
Inputs (made by s0_gofer_inventory.py / s0_hpwren_inventory.py):
  cache/gofer/final_perimeters.gpkg, cache/gofer/x/GOFER/GOFER_Combined/GOFERC_fireProg.shp,
  outputs/gofer_fires.csv, outputs/hpwren_cameras.csv
Outputs:
  outputs/feasibility_table.csv, outputs/feasibility_pairs.csv, outputs/feasibility_archive.json,
  outputs/feasibility_spotcheck.csv, outputs/feasibility_summary.json,
  cache/feasibility/<fire>__<site>.npz (cell-level visibility, gitignored),
  cache/feasibility_quicklooks/*.png
FEASIBILITY.md is written by s0_write_feasibility_md.py from these outputs.

Credits: camera metadata/archive = HPWREN (hpwren.ucsd.edu), UC San Diego.
GOFER v0.2 = Liu et al., Zenodo doi:10.5281/zenodo.14642378 (concept doi:10.5281/zenodo.8327264).
DEM = AWS Terrain Tiles 'skadi' 1-arcsec (SRTM / USGS NED derived), s3.amazonaws.com/elevation-tiles-prod.
"""
import json, sys, pathlib, time
import numpy as np, pandas as pd, geopandas as gpd
import rasterio.features
from rasterio.transform import from_origin

SRC = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
from viewshed import DEM, aeqd, polar_visibility, brute_los, K_REFR  # noqa: E402
from hpwren_archive import archive_exists, video_url, list_url  # noqa: E402

ROOT = SRC.parent
OUT = ROOT / "outputs"
CF = ROOT / "cache" / "feasibility"
QL = ROOT / "cache" / "feasibility_quicklooks"
CF.mkdir(parents=True, exist_ok=True)
QL.mkdir(parents=True, exist_ok=True)
MAXKM = 60.0
CELL = 30.0
H2 = 20.0  # secondary target height above ground (flame / plume proxy)
DEFAULT_AGL = 10.0
DEFAULT_HFOV_CARDINAL = 90.0
CREDIT = ("Camera data: HPWREN (hpwren.ucsd.edu), UC San Diego. Perimeters: GOFER v0.2, Liu et al., "
          "doi:10.5281/zenodo.14642378. DEM: AWS Terrain Tiles skadi 1-arcsec (SRTM/NED derived).")


def load():
    fires = gpd.read_file(ROOT / "cache/gofer/final_perimeters.gpkg")
    meta = pd.read_csv(OUT / "gofer_fires.csv", comment="#")
    cams = pd.read_csv(OUT / "hpwren_cameras.csv")
    return fires, meta, cams


def daily_growth():
    """GOFER-Combined hourly cumulative areas -> growth per Pacific date of the hour interval (T-1h, T]."""
    p = gpd.read_file(ROOT / "cache/gofer/x/GOFER/GOFER_Combined/GOFERC_fireProg.shp", ignore_geometry=True)
    p["t"] = pd.to_datetime(p["tUTC"]).dt.tz_localize("UTC")
    p = p.sort_values(["fname", "t"])
    p["dA"] = p.groupby("fname")["farea"].diff().fillna(p["farea"])
    p["pdate"] = (p["t"] - pd.Timedelta(minutes=30)).dt.tz_convert("America/Los_Angeles").dt.date
    return p


def cam_kind(r):
    if bool(r.is_ptz):
        return "ptz"
    if str(r.imager) in ("color", "monochrome"):
        return "fixed-" + str(r.imager)
    return "fixed-" + str(r.imager)  # delphire experimental etc. (fixed azimuth in metadata)


def ang_in_fov(az_deg, center, hfov):
    d = (az_deg - center + 180.0) % 360.0 - 180.0
    return np.abs(d) <= hfov / 2.0


def analyse_pair(fire_row, site_row, site_cams):
    fname = fire_row.fname
    lon_c, lat_c = float(site_row.lon), float(site_row.lat)
    crs, inv, fwd = aeqd(lon_c, lat_c)
    g = gpd.GeoSeries([fire_row.geometry], crs=4326).to_crs(crs).iloc[0]
    xmin, ymin, xmax, ymax = g.bounds
    xmin, ymin = np.floor(xmin / CELL) * CELL, np.floor(ymin / CELL) * CELL
    xmax, ymax = np.ceil(xmax / CELL) * CELL, np.ceil(ymax / CELL) * CELL
    W, H = int((xmax - xmin) / CELL), int((ymax - ymin) / CELL)
    tr = from_origin(xmin, ymax, CELL, CELL)
    burned = rasterio.features.rasterize([(g, 1)], out_shape=(H, W), transform=tr, dtype="uint8").astype(bool)
    rows, cols = np.nonzero(burned)
    tx = xmin + (cols + 0.5) * CELL
    ty = ymax - (rows + 0.5) * CELL
    flon, flat = inv.transform(tx, ty)
    b = fire_row.geometry.bounds
    dem = DEM(min(b[0], lon_c) - 0.03, min(b[1], lat_c) - 0.03, max(b[2], lon_c) + 0.03, max(b[3], lat_c) + 0.03)
    tz = dem.sample(np.asarray(flon), np.asarray(flat))
    z_ground = float(dem.sample(np.array([lon_c]), np.array([lat_c]))[0])
    agl_vals = pd.to_numeric(site_cams.agl_m, errors="coerce")
    agl_vals = agl_vals[(agl_vals > 0)]
    agl_known = len(agl_vals) > 0
    agl = float(agl_vals.median()) if agl_known else DEFAULT_AGL
    z_cam = z_ground + agl

    def hfn(x, y):
        lo, la = inv.transform(x, y)
        return dem.sample(np.asarray(lo), np.asarray(la))

    t0 = time.time()
    vis, d = polar_visibility(hfn, z_cam, tx, ty, tz, dr=CELL, arc_m=20.0, h_targets=(0.0, H2))
    taz = np.degrees(np.mod(np.arctan2(tx, ty), 2 * np.pi))
    # sensitivity of camera height: (a) highest DEM point within 150 m of the listed position
    # (HPWREN says many coordinates are rounded), (b) listed site elevation from sites.js (if > 0)
    gx, gy = np.meshgrid(np.arange(-150, 151, 15.0), np.arange(-150, 151, 15.0))
    inr = np.hypot(gx, gy) <= 150
    z_localmax = float(hfn(gx[inr], gy[inr]).max())
    sens = {}
    for lab, zc in (("localmax150m", z_localmax + agl),
                    ("listed_elev", float(site_row.elev_m) + agl if float(site_row.elev_m) > 0 else np.nan)):
        sens[lab] = (zc, polar_visibility(hfn, zc, tx, ty, tz, dr=CELL, arc_m=20.0)[0][0.0] if np.isfinite(zc) else None)
    np.savez_compressed(CF / f"{fname.replace(' ', '_')}__{site_row.site}.npz",
                        burned=burned, transform=np.array(tr)[:6], crs=crs.to_proj4(),
                        rows=rows, cols=cols, vis0=vis[0.0], vis20=vis[H2], dist=d, az=taz, tz=tz,
                        z_cam=z_cam)
    n = len(d)
    res = dict(fire=fname, site=site_row.site, site_name=site_row.site_name, site_lat=lat_c, site_lon=lon_c,
               site_elev_listed_m=site_row.elev_m, site_elev_dem_m=round(z_ground, 1),
               mast_agl_m=agl, mast_agl_source="hpwren metadata (median of site cameras)" if agl_known
               else f"ASSUMED {DEFAULT_AGL} m (unknown)", z_cam_m=round(z_cam, 1),
               n_burned_cells=n, burned_area_raster_km2=round(n * CELL * CELL / 1e6, 1),
               dist_min_km=round(d.min() / 1000, 2), dist_median_km=round(np.median(d) / 1000, 2),
               dist_max_km=round(d.max() / 1000, 2),
               vis_frac_ground_any_dir=round(vis[0.0].mean(), 4), vis_frac_20m_any_dir=round(vis[H2].mean(), 4),
               dem_tiles=" ".join(u.rsplit("/", 1)[-1] for u in dem.urls), dem_void_frac=dem.void_fraction,
               runtime_s=round(time.time() - t0, 1))
    for lab, (zc, vv) in sens.items():
        res[f"sens_{lab}_z_cam_m"] = round(zc, 1) if np.isfinite(zc) else np.nan
        res[f"sens_{lab}_vis_frac_ground_any_dir"] = round(vv.mean(), 4) if vv is not None else np.nan
    camrows = []
    masks = {}
    for _, c in site_cams.iterrows():
        kind = cam_kind(c)
        row = dict(res)
        hf = pd.to_numeric(c.horizontal_fov_deg, errors="coerce")
        azc = pd.to_numeric(c.azimuth_deg, errors="coerce")
        row.update(camera=c.cam, camera_kind=kind, owner=c.owner if isinstance(c.owner, str) else "",
                   azimuth_deg=azc, hfov_deg=hf)
        if kind == "ptz":
            row.update(hfov_source="PTZ: view direction variable; no fixed FOV", in_fov_burn_frac=np.nan,
                       in_fov_vis_frac_ground=np.nan, in_fov_vis_frac_20m=np.nan,
                       in_fov_dist_median_km=np.nan)
            for lab in sens:
                row[f"sens_{lab}_in_fov_vis_frac_ground"] = np.nan
        else:
            src = "hpwren metadata"
            if not np.isfinite(hf):
                hf, src = DEFAULT_HFOV_CARDINAL, f"ASSUMED {DEFAULT_HFOV_CARDINAL} deg"
            m = ang_in_fov(taz, azc, hf)
            if kind == "fixed-color":
                masks[c.cam] = m
            row.update(hfov_deg=hf, hfov_source=src, in_fov_burn_frac=round(m.mean(), 4),
                       in_fov_vis_frac_ground=round((m & vis[0.0]).mean(), 4),
                       in_fov_vis_frac_20m=round((m & vis[H2]).mean(), 4),
                       in_fov_dist_median_km=round(np.median(d[m & vis[0.0]]) / 1000, 2) if (m & vis[0.0]).any() else np.nan)
            for lab, (zc, vv) in sens.items():
                row[f"sens_{lab}_in_fov_vis_frac_ground"] = round((m & vv).mean(), 4) if vv is not None else np.nan
        camrows.append(row)
    # best union of two fixed colour cameras at this site (secondary; the gate is per single camera)
    best2 = (0.0, "")
    names = sorted(masks)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            f2 = float(((masks[names[i]] | masks[names[j]]) & vis[0.0]).mean())
            if f2 > best2[0]:
                best2 = (f2, names[i] + "+" + names[j])
    for r_ in [res] + camrows:
        r_["best_two_colour_cams"] = best2[1]
        r_["best_two_colour_cams_vis_frac_ground"] = round(best2[0], 4)
    pack = dict(tx=tx, ty=ty, tz=tz, vis=vis, d=d, taz=taz, hfn=hfn, z_cam=z_cam, dem=dem, inv=inv,
                bounds=(xmin, ymin, xmax, ymax))
    return res, camrows, pack


def spot_check(pack, n=300, seed=1):
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(pack["d"]), size=min(n, len(pack["d"])), replace=False)
    ref = np.array([brute_los(pack["hfn"], pack["z_cam"], pack["tx"][i], pack["ty"][i], pack["tz"][i], step=15.0)
                    for i in idx])
    pol = pack["vis"][0.0][idx]
    return dict(n=len(idx), agreement=float((ref == pol).mean()), polar_vis=float(pol.mean()),
                brute_vis=float(ref.mean()))


def quicklook(pair, cams_rows, pack, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Wedge, Circle
    xmin, ymin, xmax, ymax = pack["bounds"]
    xmin, xmax = min(xmin, 0) - 2000, max(xmax, 0) + 2000
    ymin, ymax = min(ymin, 0) - 2000, max(ymax, 0) + 2000
    step = max((xmax - xmin) / 600, 60)
    gx = np.arange(xmin, xmax, step)
    gy = np.arange(ymax, ymin, -step)
    GX, GY = np.meshgrid(gx, gy)
    Z = pack["hfn"](GX, GY)
    dzdx = np.gradient(Z, axis=1) / step
    dzdy = np.gradient(Z, axis=0) / -step
    hs = (np.cos(np.radians(45)) * 1 / np.sqrt(1 + dzdx ** 2 + dzdy ** 2)
          + np.sin(np.radians(45)) * (-dzdx * np.sin(np.radians(315)) - dzdy * np.cos(np.radians(315)))
          / np.sqrt(1 + dzdx ** 2 + dzdy ** 2))
    fig, ax = plt.subplots(figsize=(9, 8.5))
    ax.imshow(hs, extent=(xmin / 1e3, xmax / 1e3, ymin / 1e3, ymax / 1e3), cmap="gray", vmin=-0.2, vmax=1.2)
    v = pack["vis"][0.0]
    k = max(1, len(v) // 150000)
    ax.scatter(pack["tx"][::k][~v[::k]] / 1e3, pack["ty"][::k][~v[::k]] / 1e3, s=0.3, c="#E69F00", lw=0)
    ax.scatter(pack["tx"][::k][v[::k]] / 1e3, pack["ty"][::k][v[::k]] / 1e3, s=0.3, c="#0072B2", lw=0)
    R = max(abs(xmin), abs(xmax), abs(ymin), abs(ymax)) / 1e3
    for c in cams_rows:
        if c["camera_kind"].startswith("fixed") and np.isfinite(c["azimuth_deg"]):
            if c["camera"].endswith("-m"):
                continue
            a0 = 90 - (c["azimuth_deg"] + c["hfov_deg"] / 2)
            ax.add_patch(Wedge((0, 0), R, a0, a0 + c["hfov_deg"], fill=False, ec="#CC79A7", lw=1, ls="--"))
            th = np.radians(c["azimuth_deg"])
            ax.text(0.55 * R * np.sin(th), 0.55 * R * np.cos(th), c["camera"], color="#CC79A7", fontsize=7,
                    ha="center", clip_on=True)
    for rk in (5, 10, 20, 40, 60):
        ax.add_patch(Circle((0, 0), rk, fill=False, ec="w", lw=0.5, ls=":"))
    ax.plot(0, 0, "k^", ms=9, mec="w")
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], ls="", marker="s", color="#0072B2", label="burned, visible from camera (ground)"),
               Line2D([], [], ls="", marker="s", color="#E69F00", label="burned, hidden from camera (ground)"),
               Line2D([], [], ls="--", color="#CC79A7", label="fixed colour camera horizontal FOV"),
               Line2D([], [], ls="", marker="^", color="k", label=f"camera site {pair['site']}")]
    ax.set_xlim(xmin / 1e3, xmax / 1e3)
    ax.set_ylim(ymin / 1e3, ymax / 1e3)
    ax.set_xlabel("km east of camera")
    ax.set_ylabel("km north of camera")
    ax.set_title(f"{pair['fire']} (GOFER final perimeter) seen from {pair['site']}\n"
                 f"visible burned fraction (ground) {pair['vis_frac_ground_any_dir']:.1%}, +20 m "
                 f"{pair['vis_frac_20m_any_dir']:.1%}; rings 5/10/20/40/60 km; dashed = fixed colour camera FOV",
                 fontsize=9)
    ax.legend(handles=handles, loc="lower left", fontsize=7)
    fig.text(0.01, 0.005, CREDIT + " Feasibility quick-look, terrain line of sight only.", fontsize=6)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def main():
    fires, meta, cams = load()
    sites = cams.groupby("site").first().reset_index()
    sg = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs=4326).to_crs(3310)
    fg = fires.to_crs(3310)
    prog = daily_growth()
    pairs, camrows, packs = [], [], {}
    for i, f in fires.iterrows():
        dist = sg.distance(fg.geometry.iloc[i]) / 1000.0
        near = sites[dist.values <= MAXKM]
        for _, s in near.iterrows():
            print(f"[pair] {f.fname} x {s.site} ({dist[s.name]:.1f} km)", flush=True)
            res, crow, pack = analyse_pair(f, s, cams[cams.site == s.site])
            res["dist_site_to_perimeter_km"] = round(float(dist[s.name]), 2)
            for c in crow:
                c["dist_site_to_perimeter_km"] = res["dist_site_to_perimeter_km"]
            pairs.append(res)
            camrows.extend(crow)
            packs[(f.fname, s.site)] = (res, crow, pack)
    P = pd.DataFrame(pairs)
    C = pd.DataFrame(camrows)

    # ---- fire timing context: GOFER period and peak growth Pacific date
    g = prog.groupby(["fname", "pdate"])["dA"].sum().reset_index()
    peak = g.loc[g.groupby("fname")["dA"].idxmax()].set_index("fname")
    first = prog.groupby("fname")["pdate"].min()

    # ---- archive checks (throttled + cached via hpwren_common.fetch)
    arch = {}
    probe = C[(C.in_fov_vis_frac_ground.fillna(0) > 0) |
              ((C.camera_kind == "ptz") & (C.vis_frac_ground_any_dir > 0))]
    for _, c in probe.iterrows():
        dates = [str(peak.loc[c.fire, "pdate"])]  # one block (Q7 = 18-21 PT, dusk/night) on peak-growth date
        for dt in dates:
            key = f"{c.camera}|{dt}"
            if key in arch:
                continue
            print(f"[archive] {c.camera} {dt} Q7", flush=True)
            arch[key] = {"camera": c.camera, "date": dt, "fire": c.fire,
                         "result": archive_exists(c.camera, dt.replace("-", ""), quarters=(7,))}
    # deeper check on the best fixed camera: all 8 blocks of peak date + Q7 of first GOFER date
    fixed = C[C.camera_kind == "fixed-color"].sort_values("in_fov_vis_frac_ground", ascending=False)
    for _, best in fixed.head(2).iterrows():  # deeper check on the two best fixed colour cameras
        for dt, qs in ((str(peak.loc[best.fire, "pdate"]), tuple(range(1, 9))),
                       (str(first.loc[best.fire]), (7,))):
            print(f"[archive-deep] {best.camera} {dt} {qs}", flush=True)
            arch[f"{best.camera}|{dt}|deep"] = {"camera": best.camera, "date": dt, "fire": best.fire,
                                                "result": archive_exists(best.camera, dt.replace("-", ""), quarters=qs)}

    def summarise(cam, fire):
        hits = [v for k, v in arch.items() if v["camera"] == cam and v["fire"] == fire]
        if not hits:
            return "not checked (no visible burned cells in view)", None, None, ""
        lists, imgs, vids, tried = [], [], [], []
        seen = set()
        for h in hits:
            for q, r in h["result"].items():
                if (h["date"], q) in seen:
                    continue
                seen.add((h["date"], q))
                lists.append(r["list"]); imgs.append(bool(r["images"])); vids.append((r["video_status"], r["video_storage_class"]))
                tried.append(f"{h['date']} Q{q}: list {r['list_status']}, image {r['image_status']}, "
                             f"video {r['video_status']} {r['video_storage_class'] or ''}".strip())
        img_ok = any(imgs)
        vid_exist = any(s == 200 for s, _ in vids)
        vid_readable = any(s == 200 and sc not in ("DEEP_ARCHIVE", "GLACIER") for s, sc in vids)
        if img_ok:
            txt = "yes (1-min JPEGs retrievable)"
        elif vid_exist and not vid_readable:
            txt = "no - JPEGs/lists 403; 3 h MP4 exists but DEEP_ARCHIVE (needs HPWREN restore)"
        elif vid_readable:
            txt = "partly - 3 h MP4 readable, JPEGs not"
        else:
            txt = "no - list 403 and video 403 (no archive found / camera may not have existed)"
        return txt, img_ok, vid_exist, "; ".join(tried)

    out = []
    for _, c in C.iterrows():
        txt, img_ok, vid_exist, tried = summarise(c.camera, c.fire)
        out.append(dict(archive_status=txt, archive_images_retrievable=img_ok,
                        camera_existed_on_date=("yes (archive video object exists)" if vid_exist else
                                                ("unknown (403 is ambiguous)" if vid_exist is False else "not checked")),
                        archive_tried=tried))
    C = pd.concat([C.reset_index(drop=True), pd.DataFrame(out)], axis=1)
    C["fire_peak_growth_pacific_date"] = C.fire.map(lambda f: str(peak.loc[f, "pdate"]))
    C["fire_peak_growth_km2"] = C.fire.map(lambda f: round(float(peak.loc[f, "dA"]), 1))
    C = C.sort_values(["in_fov_vis_frac_ground", "vis_frac_ground_any_dir"], ascending=False, na_position="last")

    # ---- spot checks + quicklooks for top pairs
    P = P.sort_values("vis_frac_ground_any_dir", ascending=False)
    spots = []
    top_pairs = P[P.vis_frac_ground_any_dir > 0].head(8)
    for _, p in top_pairs.iterrows():
        res, crow, pack = packs[(p.fire, p.site)]
        sc = spot_check(pack)
        sc.update(fire=p.fire, site=p.site)
        spots.append(sc)
        print("[spot]", sc, flush=True)
        quicklook(res, crow, pack, QL / f"{p.fire.replace(' ', '_')}__{p.site}.png")
    S = pd.DataFrame(spots)

    # ---- gate
    fx = C[C.camera_kind.str.startswith("fixed")]
    geo = fx[fx.in_fov_vis_frac_ground >= 0.10]
    geometric_pass = len(geo) > 0
    gate_pass = bool(geometric_pass and geo.archive_images_retrievable.fillna(False).astype(bool).any())
    summary = dict(geometric_pass=bool(geometric_pass), gate_pass=gate_pass,
                   n_pairs_within_60km=len(P), n_camera_rows=len(C),
                   fires_with_site_within_60km=sorted(P.fire.unique().tolist()),
                   geometric_passing_cameras=geo[["fire", "camera", "in_fov_vis_frac_ground", "dist_min_km",
                                                  "in_fov_dist_median_km", "archive_status"]].to_dict("records"),
                   k_refraction=K_REFR, cell_m=CELL, max_km=MAXKM, run_utc=pd.Timestamp.now('UTC').isoformat(),
                   credit=CREDIT)
    hdr = "# " + CREDIT + " Terrain line of sight only (not flame visibility); see FEASIBILITY.md.\n"
    for df, name in ((C, "feasibility_table.csv"), (P, "feasibility_pairs.csv"), (S, "feasibility_spotcheck.csv")):
        with open(OUT / name, "w") as fh:
            fh.write(hdr)
            df.to_csv(fh, index=False)
    (OUT / "feasibility_archive.json").write_text(json.dumps({"credit": CREDIT, "checks": arch}, indent=1, default=str))
    gd = g.copy()
    gd["pdate"] = gd["pdate"].astype(str)
    gd.to_csv(OUT / "feasibility_daily_growth.csv", index=False)
    (OUT / "feasibility_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
