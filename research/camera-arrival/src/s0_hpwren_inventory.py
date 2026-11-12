"""Step 0: HPWREN site/camera inventory from the cameras page's own sites.js.
Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego.
Source: https://www.hpwren.ucsd.edu/cameras/sites.js  (loaded by /cameras/ page).
NOTE: HPWREN rounds most site coordinates to 2 decimals (~1 km); see help.html changelog 9/16/2024.
"""
import json, re, sys, pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hpwren_common import fetch, ROOT

URL = "https://www.hpwren.ucsd.edu/cameras/sites.js"
OUT = ROOT / "outputs"


def main():
    r = fetch(URL)
    assert r["status"] == 200, r["status"]
    txt = r["body"].decode()
    sites = json.loads(re.search(r"var sites\s*=\s*(\{.*\})\s*;", txt, re.S).group(1))
    rows = []
    for sid, s in sites.items():
        for cid, c in s.get("cams", {}).items():
            parts = cid.split("-")
            suffix = parts[-1]
            dirletter = parts[1] if len(parts) > 2 and parts[1] in ("n", "e", "s", "w", "ne", "nw", "se", "sw") else ""
            rows.append(dict(
                site=sid, site_name=s["name"], lat=s["lat"], lon=s["long"], elev_m=s["elev"],
                cam=cid, cam_name=c.get("name"), imager=c.get("imager"),
                colour_or_mono=("color" if suffix == "c" else "monochrome" if suffix == "m" else c.get("imager")),
                is_mobo="mobo" in cid, is_ptz=(c.get("imager") == "ptz"),
                azimuth_deg=c.get("azimuth"), horizontal_fov_deg=c.get("horizontalView"),
                owner=c.get("owner"), active=c.get("active"), experimental=c.get("experimental"),
                roll=c.get("roll"), pitch=c.get("pitch"), yaw=c.get("yaw"), agl_m=c.get("agl"),
                id_direction_token=dirletter,
                lat_decimals=len(str(s["lat"]).split(".")[-1]) if "." in str(s["lat"]) else 0,
                install_date=None))  # not provided by sites.js
    df = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    df.to_csv(OUT / "hpwren_cameras.csv", index=False)
    summ = dict(source=URL, credit="Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego",
                n_sites=len(sites), n_cameras=len(df),
                n_sites_with_coords=sum(1 for s in sites.values() if s.get("lat") and s.get("long")),
                n_sites_with_cameras=int(df.site.nunique()),
                n_sites_elev_nonzero=int((df.groupby("site").elev_m.first() > 0).sum()),
                n_active=int((df.active == "y").sum()),
                n_fixed_color=int(((df.imager == "color")).sum()), n_fixed_mono=int((df.imager == "monochrome").sum()),
                n_ptz=int(df.is_ptz.sum()),
                note="sites.js has no install/first-data dates; coordinates are rounded to ~2 decimals for most sites")
    sites_out = {sid: dict(name=s["name"], lat=s["lat"], lon=s["long"], elev=s["elev"], cams=s["cams"]) for sid, s in sites.items()}
    (OUT / "hpwren_cameras.json").write_text(json.dumps(dict(summary=summ, sites=sites_out), indent=1))
    print(json.dumps(summ, indent=1))
    print(df.imager.value_counts().to_string())
    print(df.lat_decimals.value_counts().to_string())


if __name__ == "__main__":
    main()
