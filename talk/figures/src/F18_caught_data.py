"""Inputs of F18 (caught: fires no standard satellite label covered) from the wildfireguardiandata release caught-v0.1.

Reads the release files (downloaded, read only, to $CAUGHT_REL; checked against the release's SHA256SUMS) and the
code at the tag, and writes talk/figures/build/caught/ (committed), which F18_caught.py draws from:
  fires.json        the chosen fires: their label rows (released fields only) and their scar-pair metadata
  <rid>/pre.png, post.png, mask.png, meta.json   copied unchanged from scar_pairs.zip
  standard.json     the standard-label products and the scar test, read from the code and config at the tag

Eligible fires: the 40 scar pairs the release ships (export.scar_pairs: verified Sentinel-2 scars, seed 0) whose label
row has tier "verified", std_label false (no standard product in the record's window), scar_status "scar" from
Sentinel-2, and whose scar-pair looks are the label's own looks (meta pre_date/post_date = scar_pre/scar_post).
Main fire: the eligible fire with the largest released scar area (scar_area_ha), so the scar is visible at slide size.
Grid: six more, drawn from the remaining eligible fires (sorted by rid) with numpy default_rng(SEED).
"""
import ast
import hashlib
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

import style as S

REL = Path(os.environ.get("CAUGHT_REL", "/private/tmp/claude-501/caught/rel"))
CODE = Path(os.environ.get("CAUGHT_CODE", str(REL.parent / "src")))
OUT = S.BUILD / "caught"
REPO = "Sparkxt-0318/wildfireguardiandata"
TAG = "caught-v0.1"
TAG_COMMIT = "407614ea30eefc789fc44f8ac37a8b12241e9f16"     # git ls-remote: refs/tags/caught-v0.1 (lightweight tag)
SEED = 0
N_GRID = 6
YEARS = (2018, 2019, 2020)
COLS = ["rid", "FOD_ID", "STATE", "FIRE_YEAR", "FIRE_SIZE", "FIRE_SIZE_CLASS", "LATITUDE", "LONGITUDE", "r_m", "t0",
        "t1", "t1_source", "tier", "std_label", "std_witnesses", "pairs", "kinds", "scar_status", "scar_sensor",
        "scar_pre", "scar_post", "scar_threshold", "scar_area_ha", "fire_m2_disc", "label_t0", "label_t1"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def checked(name):
    sums = {}
    for fn in ("SHA256SUMS", "SHA256SUMS.txt"):        # the release lists scar_pairs.zip in SHA256SUMS.txt
        for line in (REL / fn).read_text().splitlines():
            if line.strip():
                h, n = line.split(maxsplit=1)
                assert sums.setdefault(n.strip(), h) == h, n

    got = sha(REL / name)
    assert sums[name] == got, (name, got, sums[name])
    return got


def plain(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, np.ndarray):
        return [plain(x) for x in v]
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def standard_from_code():
    """Standard products and the scar test, parsed from the tag's config and scar.py (not typed by hand)."""
    cfg = json.loads((CODE / "firewitness/caught/config/us.json").read_text())
    std_py = (CODE / "firewitness/caught/standard.py").read_text()
    scar_py = (CODE / "firewitness/caught/scar.py").read_text()
    doc = std_py.split('"""')[1].strip().splitlines()[0]
    m = re.search(r"^PARAMS = (\{.*?^\})", scar_py, re.S | re.M)
    params = ast.literal_eval(re.sub(r"#[^\n]*", "", m.group(1)).replace("None", "None"))
    bands = re.search(r'return \{"nir": r20\("(\w+)"\), "swir1": r20\("(\w+)"\), "swir2": r20\("(\w+)"\),\s*'
                      r'"vis": \(r10\("(\w+)"\) \+ r10\("(\w+)"\) \+ r10\("(\w+)"\)\) / 3\.0\}', scar_py)
    nbr = re.search(r'return \(b\["nir"\] - b\["swir2"\]\) / \(b\["nir"\] \+ b\["swir2"\]\)', scar_py)
    thr = re.search(r'thr = max\(p\["t_abs"\], med \+ p\["k_sigma"\] \* mad\)', scar_py)
    cand = re.search(r'cand = valid & \(dnbr >= thr\) & \(\(bpost\["nir"\] - bpre\["nir"\]\) < p\["dnir"\]\) & '
                     r'\(\(bpost\["vis"\] - bpre\["vis"\]\) < p\["dvis"\]\)', scar_py)
    sw1 = re.search(r'cand &= \(bpost\["swir1"\] - bpre\["swir1"\]\) < p\["dswir1_max"\]', scar_py)
    conn = re.search(r"ndimage\.label\(cand, structure=np\.ones\(\(3, 3\), bool\)\)", scar_py)
    nmin = re.search(r'sizes\[k\] >= p\["n_min"\] and in_disc\[k\]', scar_py)
    win = re.search(r'search\(S\.collection, lon, lat, start - timedelta\(days=p\["pre_days"\]\), '
                    r'end \+ timedelta\(days=p\["post_days"\]\)', scar_py)
    res = re.search(r'class S2:.*?res = ([0-9.]+)', scar_py, re.S)
    for k, v in dict(bands=bands, nbr=nbr, thr=thr, cand=cand, sw1=sw1, conn=conn, nmin=nmin, win=win, res=res).items():
        assert v, f"scar.py at {TAG} no longer matches the parsed form: {k}"
    return {
        "standard_doc": doc,
        "firms_products": cfg["firms"]["products"],
        "burned_area": f"MCD64A1 ({cfg['mcd64a1']['collection']})",
        "perimeters": "MTBS",
        "record_window": cfg["window"],
        "s2": {"collection": cfg["imagery"]["s2"], "res_m": float(res.group(1)), "nir": bands.group(1),
               "swir1": bands.group(2), "swir2": bands.group(3), "vis": list(bands.group(4, 5, 6))},
        "params": {k: params[k] for k in ("t_abs", "k_sigma", "dnir", "dvis", "dswir1_max", "n_min", "pre_days",
                                          "post_days", "min_clear")},
        "connectivity": "8-connected (3x3)",
        # the data card's own limit on "no standard label", quoted from the release file
        "firececci_note": "FireCCI51 was not checked." if "FireCCI51 was not checked" in
                          (REL / "DATA_CARD.md").read_text() else "",
        "files": {"config": "firewitness/caught/config/us.json", "standard": "firewitness/caught/standard.py",
                  "scar": "firewitness/caught/scar.py"},
    }


def main():
    sums = {n: checked(n) for n in [f"caught_labels_v0.1_{y}.parquet" for y in YEARS] + ["scar_pairs.zip"]}
    zf = zipfile.ZipFile(REL / "scar_pairs.zip")
    index = json.loads(zf.read("scar_pairs/INDEX.json"))
    lab = pd.concat([pd.read_parquet(REL / f"caught_labels_v0.1_{y}.parquet", columns=COLS,
                                     filters=[("rid", "in", index)]) for y in YEARS], ignore_index=True)
    assert set(lab.rid) == set(index), set(index) - set(lab.rid)
    rows = []
    for r in lab.itertuples(index=False):
        meta = json.loads(zf.read(f"scar_pairs/{r.rid}/meta.json"))
        mask = np.array(Image.open(zf.open(f"scar_pairs/{r.rid}/mask.png"))) > 0
        same_look = meta["pre_date"] == str(r.scar_pre)[:10] and meta["post_date"] == str(r.scar_post)[:10]
        ok = (r.tier == "verified" and not bool(r.std_label) and r.scar_status == "scar" and r.scar_sensor == "s2"
              and same_look and mask.any())
        rows.append({"rid": r.rid, "eligible": bool(ok), "tier": r.tier, "std_label": bool(r.std_label),
                     "same_look": same_look, "mask_px": int(mask.sum()), "scar_area_ha": float(r.scar_area_ha)})
    tab = pd.DataFrame(rows).sort_values("rid")
    elig = tab[tab.eligible]
    main_rid = elig.sort_values(["scar_area_ha", "rid"], ascending=[False, True]).rid.iloc[0]
    rest = sorted(elig.rid[elig.rid != main_rid])
    rng = np.random.default_rng(SEED)
    grid = [rest[i] for i in sorted(rng.choice(len(rest), size=N_GRID, replace=False))]
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    fires = {}
    for rid in [main_rid] + grid:
        d = OUT / rid
        d.mkdir()
        for f in ("pre.png", "post.png", "mask.png", "meta.json"):
            (d / f).write_bytes(zf.read(f"scar_pairs/{rid}/{f}"))
        row = lab[lab.rid == rid].iloc[0]
        fires[rid] = {k: plain(row[k]) for k in COLS}
        fires[rid]["mask_px"] = int(tab[tab.rid == rid].mask_px.iloc[0])
    out = {"release": {"repo": REPO, "tag": TAG, "commit": TAG_COMMIT, "sha256": sums},
           "selection": {"pairs_in_release": len(index), "eligible": int(len(elig)),
                         "eligible_rids": sorted(elig.rid), "not_eligible": tab[~tab.eligible].to_dict("records"),
                         "main_rule": "largest scar_area_ha among eligible", "seed": SEED,
                         "grid_rule": f"numpy default_rng({SEED}).choice(len(rest), {N_GRID}, replace=False) over "
                                      "the other eligible rids sorted"},
           "main": main_rid, "grid": grid, "fires": fires, "standard": standard_from_code()}
    (OUT / "fires.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"eligible {len(elig)} of {len(index)}; main {main_rid}; grid {grid}")


if __name__ == "__main__":
    main()
