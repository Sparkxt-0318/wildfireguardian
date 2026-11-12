#!/usr/bin/env python3
"""Write FEASIBILITY.md from the outputs of s0_feasibility.py and s0_restore_plan.py.
Run: python3 -I src/s0_write_feasibility_md.py
Credits: HPWREN (hpwren.ucsd.edu), UC San Diego; GOFER v0.2 Liu et al. doi:10.5281/zenodo.14642378;
DEM AWS Terrain Tiles skadi 1-arcsec (SRTM/NED derived).
"""
import json, pathlib
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
O = ROOT / "outputs"


def pct(x):
    return "n/a" if pd.isna(x) else f"{100 * x:.1f}%"


def main():
    F = pd.read_csv(O / "gofer_fires.csv", comment="#")
    C = pd.read_csv(O / "feasibility_table.csv", comment="#")
    P = pd.read_csv(O / "feasibility_pairs.csv", comment="#")
    S = pd.read_csv(O / "feasibility_spotcheck.csv", comment="#")
    R = pd.read_csv(O / "restore_plan_bobcat_wilson.csv", comment="#")
    summ = json.loads((O / "feasibility_summary.json").read_text())
    rec = json.loads((ROOT / "cache/gofer/record.json").read_text())
    doi, cdoi = rec.get("doi"), rec.get("conceptdoi")
    fx = C[C.camera_kind.str.startswith("fixed")]
    best = fx.sort_values("in_fov_vis_frac_ground", ascending=False).iloc[0]
    L = []
    w = L.append
    w("# Step 0 - Feasibility gate: GOFER fires x HPWREN cameras\n")
    w("**Credits.** Camera sites, view directions and archive: HPWREN (hpwren.ucsd.edu), UC San Diego "
      "(archived data CC BY-NC 4.0). *HPWREN data are not intended to be used as a decision-making tool, or as a "
      "replacement for such tools.* Fire perimeters: GOFER v0.2, Liu, T. et al., "
      f"*{rec['metadata']['title']}*, Zenodo, doi:{doi} (version DOI, verified from the Zenodo record; concept DOI "
      f"{cdoi}); method paper Liu et al. 2024, ESSD 16, 1395. DEM: AWS Terrain Tiles 'skadi' 1-arc-second (~30 m) "
      "elevation tiles (SRTM / USGS NED derived), https://s3.amazonaws.com/elevation-tiles-prod/skadi/.\n")
    gp, gt = summ["geometric_pass"], summ["gate_pass"]
    w("## Verdict\n")
    w(f"**GATE: FAIL.** geometric_pass = {str(gp).lower()}, gate_pass = {str(gt).lower()}.\n")
    w(f"1. **Geometry fails, narrowly.** No fixed HPWREN camera sees at least 10% of any GOFER fire's final burned "
      f"area at ground level, inside its own horizontal field of view. The best are `{best.camera}` and "
      f"`wilson-e-mobo-c` on **Bobcat 2020**, at "
      f"{pct(C.loc[C.camera=='chino-n-mobo-c','in_fov_vis_frac_ground'].iloc[0])} and "
      f"{pct(C.loc[C.camera=='wilson-e-mobo-c','in_fov_vis_frac_ground'].iloc[0])}. With the secondary +20 m "
      f"target (flames or plume above the ground) these become "
      f"{pct(C.loc[C.camera=='chino-n-mobo-c','in_fov_vis_frac_20m'].iloc[0])} and "
      f"{pct(C.loc[C.camera=='wilson-e-mobo-c','in_fov_vis_frac_20m'].iloc[0])}. The union of the two best "
      f"Mount Wilson colour cameras (n+e) reaches "
      f"{pct(P.loc[P.site=='wilson','best_two_colour_cams_vis_frac_ground'].iloc[0])} at ground level. Neither "
      "of these is the gate criterion, which is a single camera at ground level.")
    w("2. **The archive is not retrievable, for any candidate.** No 1-minute JPEGs exist for 2019-2021, and "
      "the image lists return HTTP 403. For Mount Wilson, 69Bravo and Green Peak, 3-hour MP4s exist for the "
      "Bobcat dates, with HEAD returning 200, but they are in S3 **DEEP_ARCHIVE**. A GET returns 403 until HPWREN "
      "restores them. Chino Hills and Iron Horse Vineyards return 403 for lists and videos on the dates probed, "
      "so we found no archive, and the camera may not have existed then.")
    w("3. Per the instructions, the work **stops at Step 0**. No non-GOFER fire was substituted.\n")
    w("## Method\n")
    w("* Fires: the 28 GOFER v0.2 fires, using the final (last hourly) GOFER-Combined cumulative perimeter "
      "(`cache/gofer/final_perimeters.gpkg`).")
    w("* Cameras: 82 HPWREN sites and 503 cameras from `sites.js` (`outputs/hpwren_cameras.csv`). A site is a "
      f"candidate if it lies within {summ['max_km']:.0f} km of the nearest point of the final perimeter. "
      "Distances are computed in EPSG:3310.")
    w("* Burned cells: each perimeter is rasterised on a 30 m grid in a camera-centred azimuthal-equidistant "
      "projection. A cell counts as burned if its centre lies inside the perimeter. The raster areas match the "
      "GOFER `farea` to within 0.1% (e.g. Bobcat 583.7 vs 583.9 km2, LNU 1540.0 vs 1538.8 km2).")
    w("* DEM: skadi 1-arcsec tiles, cached in `cache/dem/`, bilinearly interpolated.")
    w("* Line of sight: a polar sweep from the camera (`src/viewshed.py`), with rays every <=20 m of arc at "
      "maximum range and samples every 30 m along each ray. The apparent tangent is "
      "(z - d^2(1-k)/2R - z_cam)/d, with earth curvature R = 6371 km and refraction k = 0.13. A target is visible "
      "if its tangent is >= the running maximum of all ray samples up to range d - 30 m. Targets use their own DEM "
      "height, either at ground level (the gate) or at +20 m (secondary).")
    w("* Camera height z_cam is the DEM elevation at the listed site coordinate plus the mast height above "
      "ground (AGL) from HPWREN metadata. Sites with no AGL use an **assumed 10 m** (cynbk, latem, mlee, svct). "
      "Two sensitivity variants are reported: (a) the highest DEM point within 150 m of the listed position, "
      "since HPWREN says many coordinates are rounded, plus AGL; (b) the `sites.js` elevation plus AGL.")
    w("* Field of view: each fixed camera uses its own azimuth and horizontal FOV from `sites.js`. These are "
      "90 deg for every n/e/s/w mobo camera here, and 75 deg for the Delphire cameras, so the 90 deg default "
      "was never needed. The FOV test is horizontal only; the vertical FOV was not modelled. A camera pointing "
      "away from the fire scores 0. PTZ (`*-axis`) cameras have no fixed view, so they are listed with the "
      "site-level any-direction fraction but **excluded from the gate**.")
    w("* **Visible burned fraction** = visible burned cells / all burned cells of the final perimeter. "
      "*In-FOV visible fraction* = (visible and inside the camera's horizontal FOV) / all burned cells. "
      "The gate uses the in-FOV ground fraction of a single fixed camera, with a threshold of 10%.")
    w("* Archive: `src/hpwren_archive.archive_exists` probes each camera with an in-FOV visible fraction > 0, "
      "and each PTZ camera at a site with visibility > 0. It uses the Pacific date of the fire's peak GOFER daily "
      "growth, block Q7 (18-21 PT, dusk/night). For each probe it GETs the image list and HEADs the video, and "
      "HEADs the first image only if a list exists. The two best fixed colour cameras were also probed on all 8 "
      "blocks of the peak date, and on Q7 of the first GOFER date. Requests were sequential and >=1.2 s apart, "
      "with User-Agent `research-poc-camera-arrival/0.1`. Every response is cached in `cache/http/` and was "
      "never refetched.")
    w("* Checks: `src/test_viewshed.py` has three synthetic tests, all passing. They cover the analytic shadow "
      "of a flat-topped ridge at 5050-10100 m, 100% agreement with a dense brute-force ray check on 400 random "
      "targets, and the curvature horizon at 12.10 km for a 10 m camera. Real-terrain spot checks compare the "
      "polar viewshed with brute-force line of sight (10-15 m steps) on 300 random burned cells for each of the "
      "top pairs:\n")
    w("| fire | site | n | agreement | polar visible | brute-force visible |\n|---|---|---|---|---|---|")
    for _, s in S.iterrows():
        w(f"| {s.fire} | {s.site} | {s.n} | {s.agreement:.3f} | {pct(s.polar_vis)} | {pct(s.brute_vis)} |")
    w("\nQuick-look maps (gitignored): `cache/feasibility_quicklooks/<fire>__<site>.png`.\n")
    w("## Limitations of this gate\n")
    w("* Ground-surface line of sight is **conservative** for flames and glow, which rise above terrain, and "
      "for smoke plumes. It is also **optimistic** in other ways: it ignores vegetation and buildings, the "
      "vertical FOV, haze, image resolution, and the fact that a cell must be visible *while it burns*, not "
      "just on the final map.")
    w("* A 30 m DEM smooths summits and ridges. The camera position comes from rounded `sites.js` "
      "coordinates; see the sensitivity columns. Some `sites.js` elevations disagree strongly with the DEM: "
      "cynbk is listed at 1630, and 1630 ft is about 497 m, which matches the DEM's 494.5 m, so the value is "
      "probably in feet. d_lhlg is listed at 969 m against 578 m in the DEM. latem is listed at 0.")
    w("* GOFER perimeters are GOES-derived at about 2 km pixels. Their final areas differ from the official "
      "acres for some fires (Bobcat: GOFER 584 km2 vs official 469 km2), so the denominator is the GOFER "
      "burned area, not the true one.")
    w("* A 403 from HPWREN's S3/CDN does not distinguish 'missing' from 'forbidden'. Only one 3 h block per "
      "camera was probed, except for the two deep-checked cameras.\n")
    w("## GOFER fires (28)\n")
    w("Times are GOFER end-of-hour UTC, and the hourly labels are nominal. The bbox is the extent of the "
      "final perimeter (lon_min, lat_min, lon_max, lat_max).\n")
    w("| # | fire | year | first perimeter (UTC) | last perimeter (UTC) | final GOFER km2 | bbox | nearest HPWREN site within 60 km |")
    w("|---|---|---|---|---|---|---|---|")
    near = P.groupby("fire").apply(lambda d: ", ".join(f"{r.site} ({r.dist_site_to_perimeter_km:.1f} km)"
                                                      for _, r in d.sort_values("dist_site_to_perimeter_km").iterrows()))
    for i, f in F.iterrows():
        w(f"| {i+1} | {f['name']} | {f.year} | {f.first_utc} | {f.last_utc} | {f.final_area_km2:.1f} | "
          f"{f.lon_min:.4f}, {f.lat_min:.4f}, {f.lon_max:.4f}, {f.lat_max:.4f} | {near.get(f['name'], 'none')} |")
    w(f"\n{len(P)} fire x site pairs lie within 60 km, covering {P.fire.nunique()} fires. The other "
      f"{28 - P.fire.nunique()} fires (mostly northern California) have no HPWREN site within 60 km.\n")
    w("## Fire x site summary (all cameras at the site, any direction)\n")
    w("| fire | site | site to perimeter km | median km to burned cells | z_cam m (DEM + AGL) | visible ground | visible +20 m | sens: local max 150 m | sens: listed elev | best 2 colour cams (union, ground) |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for _, p in P.iterrows():
        w(f"| {p.fire} | {p.site} | {p.dist_site_to_perimeter_km:.2f} | {p.dist_median_km:.1f} | "
          f"{p.z_cam_m:.0f} ({p.site_elev_dem_m:.0f} + {p.mast_agl_m:g}{' assumed' if 'ASSUMED' in p.mast_agl_source else ''}) | "
          f"{pct(p.vis_frac_ground_any_dir)} | {pct(p.vis_frac_20m_any_dir)} | "
          f"{pct(p.sens_localmax150m_vis_frac_ground_any_dir)} | {pct(p.sens_listed_elev_vis_frac_ground_any_dir)} | "
          f"{p.best_two_colour_cams_vis_frac_ground*100:.1f}% {p.best_two_colour_cams if isinstance(p.best_two_colour_cams, str) else ''} |")
    w("\n## Full fire x camera table\n")
    w("`dist` = distance from the site to the nearest burned cell (km). `in-FOV` = burned cells that are inside "
      "this camera's horizontal FOV and visible, divided by all burned cells. The archive column gives the result "
      "of the probe; the exact HTTP statuses are in `outputs/feasibility_table.csv` (`archive_tried`) and "
      "`outputs/feasibility_archive.json`.\n")
    w("| fire | camera | kind | az / HFOV | dist km | site visible ground / +20 m | in-FOV burn share | in-FOV visible ground | in-FOV visible +20 m | sens local-max / listed | archive images for fire dates |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, c in C.iterrows():
        azs = "PTZ" if c.camera_kind == "ptz" else f"{c.azimuth_deg:g} / {c.hfov_deg:g}"
        w(f"| {c.fire} | {c.camera} | {c.camera_kind} | {azs} | {c.dist_min_km:.1f} | "
          f"{pct(c.vis_frac_ground_any_dir)} / {pct(c.vis_frac_20m_any_dir)} | {pct(c.in_fov_burn_frac)} | "
          f"**{pct(c.in_fov_vis_frac_ground)}** | {pct(c.in_fov_vis_frac_20m)} | "
          f"{pct(c.sens_localmax150m_in_fov_vis_frac_ground)} / {pct(c.sens_listed_elev_in_fov_vis_frac_ground)} | "
          f"{c.archive_status} |")
    w("\n## What a human would need to request from HPWREN (if the project wants to continue with GOFER)\n")
    w("Even after a restore, the best single-camera geometry is below the 10% gate at ground level. Going ahead "
      "would therefore need an explicit decision to relax the gate, for example to the +20 m flame target or to "
      "the Mount Wilson n+e pair. If that decision is made, the best data case is **Bobcat 2020 seen from Mount "
      "Wilson** (`wilson-e-mobo-c`, plus `wilson-n-mobo-c`; the `-m` monochrome twins exist as well). The "
      "cameras are 0.3 km from the perimeter, and the median distance to burned cells visible in the e-camera "
      "FOV is "
      f"{C.loc[C.camera=='wilson-e-mobo-c','in_fov_dist_median_km'].iloc[0]:.1f} km. 3 h MP4s exist (HEAD 200, "
      "DEEP_ARCHIVE) for all 8 blocks of 2020-09-18 and for Q7 of 2020-09-06. Note that the videos give "
      "1 frame per minute only if they hold one frame per archived image; this is unverified until a restored "
      "file is inspected.\n")
    w("Request a Glacier restore of `https://cdn.hpwren.ucsd.edu/hpwren-cameras/wilson-e-mobo-c/2020/<YYYYMMDD>/Q<q>.mp4` "
      "(and the same paths for `wilson-n-mobo-c`). Make the request through HPWREN's contact page "
      "(https://www.hpwren.ucsd.edu/cameras/help.html). HPWREN says retrieval takes about 1 day. The blocks "
      "below are ranked by the GOFER new burned area that is terrain-visible inside the wilson-e FOV "
      "(`outputs/restore_plan_bobcat_wilson.csv`, from `src/s0_restore_plan.py`). Summed over the whole fire, "
      f"this is {R['wilson-e-mobo-c_new_visible_km2'].sum():.1f} km2 for wilson-e and "
      f"{R['wilson-n-mobo-c_new_visible_km2'].sum():.1f} km2 for wilson-n, out of "
      f"{R['new_burned_km2'].sum():.1f} km2.\n")
    w("| Pacific date | block | GOFER new burned km2 | wilson-e new visible km2 | wilson-n new visible km2 |")
    w("|---|---|---|---|---|")
    for _, r in R.head(15).iterrows():
        w(f"| {r.pacific_date} | {r.hpwren_block} | {r.new_burned_km2:.2f} | {r['wilson-e-mobo-c_new_visible_km2']:.2f} | "
          f"{r['wilson-n-mobo-c_new_visible_km2']:.2f} |")
    w("\nThe peak GOFER growth day for Bobcat (2020-09-18, 165 km2) was mostly the northward run into the "
      "Antelope Valley side, and almost none of it is visible from Mount Wilson.\n")
    w("## Files\n")
    w("* Scripts: `src/s0_feasibility.py` (main), `src/viewshed.py`, `src/test_viewshed.py`, "
      "`src/s0_restore_plan.py`, `src/s0_write_feasibility_md.py`, `src/hpwren_archive.py`, `src/hpwren_common.py`.")
    w("* Outputs: `outputs/feasibility_table.csv` (fire x camera), `outputs/feasibility_pairs.csv` (fire x site), "
      "`outputs/feasibility_spotcheck.csv`, `outputs/feasibility_archive.json`, `outputs/feasibility_summary.json`, "
      "`outputs/feasibility_daily_growth.csv`, `outputs/restore_plan_bobcat_wilson.csv`.")
    w("* Gitignored: `cache/dem/` (skadi tiles), `cache/feasibility/*.npz` (cell-level visibility), "
      "`cache/feasibility_quicklooks/*.png`, `cache/http/` (HPWREN responses).\n")
    w("Reproduce: `python3 -I src/test_viewshed.py && python3 -I src/s0_feasibility.py && "
      "python3 -I src/s0_restore_plan.py && python3 -I src/s0_write_feasibility_md.py`.\n")
    (ROOT / "FEASIBILITY.md").write_text("\n".join(L))
    print("wrote FEASIBILITY.md", len(L), "lines")


if __name__ == "__main__":
    main()
