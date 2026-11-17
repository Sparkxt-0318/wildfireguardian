"""Terrain for the KCF scene: Terrarium elevation tiles as planner/public/kcf-scene/data/terrain.js (window.KCF.terrain).

Source: AWS Open Data "Terrain Tiles" (Mapzen), Terrarium encoding, h = R*256 + G + B/256 - 32768 (metres).
Every tile intersecting lon 128.28..129.50, lat 36.20..36.62 is taken at every zoom 5..12. Raw downloads are cached under
research/kcf-replay/scene/.cache/terrarium/ (git-ignored) with a fetch log (time, ETag, Last-Modified, imagery sources),
so a re-run with a warm cache is byte-identical and makes no request.

Repair (default on; --no-repair turns it off), recorded with per-zoom counts in built.repair:
1. Despike. The source has resampling artifacts at the edges of flat water surfaces (reservoirs, dams): 1-3 px
   needles and pits such as -3546 m next to +930 m where the surroundings are ~160 m (12/3513/1600, Andong dam) or a
   +2393 m needle among ~30 m (11/1754/802). A pixel is replaced by the median of its 5x5 neighbourhood of
   max(h, 0) when it differs from that median by more than 250 m (z >= 9) or 1000 m (z <= 8); two passes.
2. Sea level. Elevations below 0 m are set to 0 m. There is no land below sea level in the bbox; this flattens the sea
   (the source mixes ETOPO1 bathymetry, about -300 m off the coast at z10, with about -4 m at z12, which pops when
   MapLibre changes zoom level) and removes what is left of the land pits.
Clip (default on; --no-clip turns it off), recorded with per-zoom counts in built.clip: pixels whose centre lies
outside the bbox are set to 0 m at every zoom. A tile reaches further beyond the bbox the lower its zoom (z9 to about
37.16 N, z12 to about 36.67 N), so without the clip the edge of the terrain moves, and notches open in it, when
MapLibre mixes zoom levels across the view. With it, the terrain ends at the bbox at every zoom, as the basemap does.
Every other pixel keeps its source R and G exactly.

Each tile is then re-encoded losslessly as PNG (Pillow optimize=True, then oxipng when pyoxipng is installed) with
the blue channel set to 0, i.e. elevation floored to whole metres (error B/256 < 1 m). The builder checks, for every
tile, that the PNG decodes to exactly the intended pixels, that pixels neither repaired nor clipped keep their source R
and G (built.check.all_tiles.unrepaired_rg_unchanged), and that the elevation differs from the repaired and clipped
source by less than 1 m.
`flat` is a 256x256 tile of 0 m (rgb 128,0,0) for the scene's tile handler to return outside the bounds.

Usage (from anywhere): python3 research/kcf-replay/scene/build_terrain.py [--offline] [--no-repair] [--no-clip]
"""
from __future__ import annotations

import argparse, base64, hashlib, io, json, math, subprocess, sys, time, urllib.request, zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
import PIL
from PIL import Image

try:  # lossless PNG optimizer (pip install pyoxipng); optional, the pixels are verified either way
    import oxipng
except ImportError:  # pragma: no cover
    oxipng = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "planner/public/kcf-scene/data/terrain.js"
CACHE = HERE / ".cache/terrarium"
LOG = CACHE / "fetch_log.json"
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
BBOX = (128.28, 36.20, 129.50, 36.62)  # W, S, E, N
ZMIN, ZMAX = 5, 12
OXI_LEVEL = 4
SPIKE_M = {"z>=9": 250.0, "z<=8": 1000.0}
CHECK_LONLAT = (129.30, 36.48)  # 옥류리 area
ATTRIBUTION = "Terrain Tiles: Mapzen / AWS Open Data (SRTM, GMTED, ETOPO1 and others)"
SCRIPT = "research/kcf-replay/scene/build_terrain.py"


def lon2x(lon, z):
    return (lon + 180.0) / 360.0 * (1 << z)


def lat2y(lat, z):
    r = math.radians(lat)
    return (1.0 - math.asinh(math.tan(r)) / math.pi) / 2.0 * (1 << z)


def tiles_for(z):
    """All tiles whose square overlaps the bbox with positive area."""
    W, S, E, N = BBOX
    x0, x1 = math.floor(lon2x(W, z)), math.ceil(lon2x(E, z)) - 1
    y0, y1 = math.floor(lat2y(N, z)), math.ceil(lat2y(S, z)) - 1
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def git_commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def ensure_cache():
    CACHE.mkdir(parents=True, exist_ok=True)
    gi = HERE / ".cache/.gitignore"
    if not gi.exists():
        gi.write_text("# raw downloads of the scene builders; never committed\n*\n")


def load_log():
    return json.loads(LOG.read_text()) if LOG.exists() else {}


def save_log(log):
    tmp = LOG.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, sort_keys=True, indent=1) + "\n")
    tmp.replace(LOG)


def fetch(z, x, y, log, offline):
    key = f"{z}/{x}/{y}"
    p = CACHE / f"{z}/{x}/{y}.png"
    if p.exists() and key in log:
        b = p.read_bytes()
        if hashlib.sha256(b).hexdigest() == log[key]["sha256"]:
            return b
        print(f"  cache mismatch for {key}, refetching", file=sys.stderr)
    if offline:
        raise SystemExit(f"--offline and {key} is not in the cache")
    url = URL.format(z=z, x=x, y=y)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                b = r.read()
                hd = r.headers
            break
        except Exception as e:  # noqa: BLE001 - retry any network error
            if attempt == 4:
                raise
            print(f"  retry {key}: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    if int(hd.get("Content-Length", len(b))) != len(b):
        raise SystemExit(f"short read for {url}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b)
    log[key] = {"url": url, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "etag": hd.get("ETag", "").strip('"'), "last_modified": hd.get("Last-Modified", ""),
                "imagery_sources": hd.get("x-amz-meta-x-imagery-sources", "")}
    save_log(log)
    return b


def decode_rgb(b):
    im = Image.open(io.BytesIO(b))
    im.load()
    if im.size != (256, 256):
        raise SystemExit(f"unexpected tile size {im.size}")
    return np.asarray(im.convert("RGB"), dtype=np.uint8)


def elev(a):
    a = a.astype(np.float64)
    return a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0


def median5(h):
    return np.median(sliding_window_view(np.pad(h, 2, mode="edge"), (5, 5)), axis=(2, 3))


def repair(h0, z):
    """Despike against the 5x5 median of max(h, 0), two passes, then clamp below 0 m to 0 m (see module doc)."""
    t = SPIKE_M["z>=9"] if z >= 9 else SPIKE_M["z<=8"]
    h = h0.copy()
    spiked = np.zeros(h.shape, dtype=bool)
    for _ in range(2):
        m = median5(np.maximum(h, 0.0))
        mask = np.abs(h - m) > t
        h[mask] = m[mask]
        spiked |= mask
    h[h < 0] = 0.0
    changed = spiked | (h0 < 0)
    sea = (h0 < 0) & (h == 0.0)  # below sea level in the source, 0 m now (clamped, or despiked to a 0 m median)
    return h, changed & ~sea, sea


def outside_bbox(z, x, y):
    """Mask of the tile's pixels whose centre lies outside the bbox."""
    W, S, E, N = BBOX
    n = float(1 << z)
    lon = (x + (np.arange(256) + 0.5) / 256.0) / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1.0 - 2.0 * (y + (np.arange(256) + 0.5) / 256.0) / n))))
    return ((lon < W) | (lon > E))[None, :] | ((lat < S) | (lat > N))[:, None]


def encode_rgb(h):
    v = np.floor(h).astype(np.int64) + 32768
    if v.min() < 0 or v.max() > 65535:
        raise SystemExit("elevation out of Terrarium range")
    q = np.zeros(h.shape + (3,), dtype=np.uint8)
    q[..., 0] = v // 256
    q[..., 1] = v % 256
    return q


def encode_png(a):
    """Lossless: Pillow optimize=True, then oxipng (lossless only, all ancillary chunks stripped) when installed."""
    buf = io.BytesIO()
    Image.fromarray(a, "RGB").save(buf, format="PNG", optimize=True)
    b = buf.getvalue()
    if oxipng is not None:
        o = oxipng.optimize_from_memory(b, level=OXI_LEVEL, strip=oxipng.StripChunks.all())
        if len(o) < len(b):
            b = o
    return b


def encoder_info():
    info = {"pillow": PIL.__version__, "zlib": zlib.ZLIB_VERSION, "png": "Pillow optimize=True"}
    if oxipng is not None:
        from importlib.metadata import version
        info.update(oxipng=f"pyoxipng {version('pyoxipng')}", png=f"Pillow optimize=True, then oxipng level {OXI_LEVEL} "
                    "strip all ancillary chunks (lossless; kept only when smaller)")
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true", help="use the cache only; fail if a tile is missing")
    ap.add_argument("--no-repair", action="store_true", help="skip the despike and sea-level repair")
    ap.add_argument("--no-clip", action="store_true", help="keep the pixels outside the bbox")
    a = ap.parse_args()
    ensure_cache()
    log = load_log()
    do_repair, do_clip = not a.no_repair, not a.no_clip

    tiles, inputs, per_zoom = {}, [], {}
    check_all = {"tiles": 0, "max_abs_quantization_m": 0.0, "unrepaired_rg_unchanged": True, "decode_exact": True,
                 "min_m": None, "max_m": None}
    rep = {"enabled": do_repair, "spike_threshold_m": SPIKE_M, "window": "5x5 median of max(h, 0), edge-padded, 2 passes",
           "per_zoom": {}, "largest": []}
    clip = {"enabled": do_clip, "rule": "pixel centre outside the bbox -> 0 m, at every zoom", "bbox": list(BBOX),
            "per_zoom": {}}
    for z in range(ZMIN, ZMAX + 1):
        zt = tiles_for(z)
        per_zoom[str(z)] = {"tiles": len(zt), "png_bytes": 0, "b64_bytes": 0, "original_bytes": 0}
        rz = rep["per_zoom"][str(z)] = {"despiked_px": 0, "below_sea_level_px": 0, "tiles_touched": 0}
        cz = clip["per_zoom"][str(z)] = {"clipped_px": 0, "clipped_nonzero_px": 0, "tiles_touched": 0}
        for (z_, x, y) in zt:
            raw = fetch(z_, x, y, log, a.offline)
            key = f"{z}/{x}/{y}"
            src = decode_rgb(raw)
            h0 = elev(src)
            if do_repair:
                h, spikes, sea = repair(h0, z)
            else:
                h, spikes, sea = h0, np.zeros(h0.shape, bool), np.zeros(h0.shape, bool)
            out = outside_bbox(z, x, y) if do_clip else np.zeros(h0.shape, bool)
            if out.any():
                cz["clipped_px"] += int(out.sum()); cz["clipped_nonzero_px"] += int((h[out] != 0.0).sum())
                cz["tiles_touched"] += 1
            hr = h  # repaired, before the clip (the repair statistics below describe the repair alone)
            if out.any():
                h = h.copy(); h[out] = 0.0
            changed = spikes | sea | out
            q = encode_rgb(h)
            png = encode_png(q)
            back = decode_rgb(png)
            if not np.array_equal(back, q):
                check_all["decode_exact"] = False
            keep = ~changed
            if not (np.array_equal(back[..., 0][keep], src[..., 0][keep]) and
                    np.array_equal(back[..., 1][keep], src[..., 1][keep])):
                check_all["unrepaired_rg_unchanged"] = False
            e1 = elev(back)
            check_all["tiles"] += 1
            check_all["max_abs_quantization_m"] = max(check_all["max_abs_quantization_m"], float(np.max(np.abs(e1 - h))))
            lo, hi = float(e1.min()), float(e1.max())
            check_all["min_m"] = lo if check_all["min_m"] is None else min(check_all["min_m"], lo)
            check_all["max_m"] = hi if check_all["max_m"] is None else max(check_all["max_m"], hi)
            rz["despiked_px"] += int(spikes.sum()); rz["below_sea_level_px"] += int(sea.sum())
            rz["tiles_touched"] += int((spikes | sea).any())
            if spikes.any():
                d = np.where(spikes, np.abs(hr - h0), 0.0)
                py, px = np.unravel_index(int(np.argmax(d)), d.shape)
                rep["largest"].append({"tile": key, "pixel": [int(px), int(py)], "px": int(spikes.sum()),
                                       "from_m": round(float(h0[py, px]), 1), "to_m": round(float(hr[py, px]), 1)})
            b64 = base64.b64encode(png).decode("ascii")
            tiles[key] = b64
            pz = per_zoom[str(z)]
            pz["png_bytes"] += len(png); pz["b64_bytes"] += len(b64); pz["original_bytes"] += len(raw)
            ent = log[key]
            inputs.append({"url": ent["url"], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                           "etag": ent["etag"], "last_modified": ent["last_modified"],
                           "imagery_sources": ent["imagery_sources"]})
    if not (check_all["decode_exact"] and check_all["unrepaired_rg_unchanged"]) or check_all["max_abs_quantization_m"] >= 1.0:
        raise SystemExit(f"terrain check failed: {check_all}")
    check_all["max_abs_quantization_m"] = round(check_all["max_abs_quantization_m"], 6)
    rep["largest"] = sorted(rep["largest"], key=lambda r: -abs(r["to_m"] - r["from_m"]))[:12]
    rep["despiked_px"] = sum(r["despiked_px"] for r in rep["per_zoom"].values())
    rep["below_sea_level_px"] = sum(r["below_sea_level_px"] for r in rep["per_zoom"].values())

    # spot check: the z12 tile containing 옥류리 (129.30, 36.48): source vs shipped elevation
    lon, lat = CHECK_LONLAT
    fx, fy = lon2x(lon, ZMAX), lat2y(lat, ZMAX)
    tx, ty = int(fx), int(fy)
    px, py = int((fx - tx) * 256), int((fy - ty) * 256)
    ck = f"{ZMAX}/{tx}/{ty}"
    e0 = elev(decode_rgb((CACHE / f"{ck}.png").read_bytes()))
    e1 = elev(decode_rgb(base64.b64decode(tiles[ck])))
    spot = {"lonlat": [lon, lat], "tile": ck, "pixel": [px, py],
            "elev_source_m": round(float(e0[py, px]), 4), "elev_shipped_m": round(float(e1[py, px]), 4),
            "tile_max_abs_diff_m": round(float(np.max(np.abs(e1 - e0))), 6),
            "tile_mean_abs_diff_m": round(float(np.mean(np.abs(e1 - e0))), 6),
            "tile_repaired_px": int(np.sum(np.abs(e1 - e0) >= 1.0)),
            "tile_elev_range_m": [round(float(e1.min()), 1), round(float(e1.max()), 1)]}
    if spot["tile_max_abs_diff_m"] >= 1.0:
        raise SystemExit(f"spot check failed: {spot}")

    flat = encode_png(np.tile(np.array([128, 0, 0], dtype=np.uint8), (256, 256, 1)))
    assert float(elev(decode_rgb(flat)).max()) == 0.0
    fetched = sorted(log[k]["fetched_utc"] for k in tiles)
    obj = {
        "encoding": "terrarium", "tileSize": 256, "minzoom": ZMIN, "maxzoom": ZMAX, "bounds": list(BBOX),
        "quantized": "blue channel zeroed: 1 m steps",
        "repaired": ("water-edge spikes and pits replaced by the 5x5 median (|h - median| > 250 m at z >= 9, "
                     "> 1000 m at z <= 8); elevations below 0 m set to 0 m (flat sea); counts in built.repair")
        if do_repair else "none",
        "clipped": "pixels outside the bbox set to 0 m at every zoom, so the terrain ends at the bbox at every zoom; "
                   "counts in built.clip" if do_clip else "none",
        "tiles": tiles, "flat": base64.b64encode(flat).decode("ascii"),
        "attribution": ATTRIBUTION,
        "source": {"url_template": URL, "fetched_utc": fetched[-1], "fetched_utc_first": fetched[0],
                   "dataset": "AWS Open Data Terrain Tiles (s3://elevation-tiles-prod), Terrarium format",
                   "decode": "h = R*256 + G + B/256 - 32768 (m)"},
        "built": {"script": SCRIPT, "commit": git_commit(),
                  "encoder": encoder_info(),
                  "check": {"all_tiles": check_all, "spot": spot},
                  "repair": rep,
                  "clip": clip,
                  "per_zoom": per_zoom,
                  "inputs": inputs},
    }
    js = f"// built by {SCRIPT} (do not edit)\n(window.KCF=window.KCF||{{}}).terrain=" + \
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + ";\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(js, encoding="ascii")
    total = OUT.stat().st_size
    print(f"wrote {OUT.relative_to(ROOT)}: {total} bytes ({total / 1e6:.2f} MB), {len(tiles)} tiles")
    for z, pz in per_zoom.items():
        print(f"  z{z}: {pz['tiles']} tiles, original {pz['original_bytes']} B, png {pz['png_bytes']} B, base64 {pz['b64_bytes']} B")
    print(f"  all tiles: {json.dumps(check_all, sort_keys=True)}")
    print(f"  repair: despiked {rep['despiked_px']} px, below sea level -> 0 m {rep['below_sea_level_px']} px; "
          + ", ".join(f"z{z}: {r['despiked_px']}/{r['below_sea_level_px']}" for z, r in rep["per_zoom"].items()))
    print("  clip: " + ", ".join(f"z{z}: {c['clipped_px']} px ({c['clipped_nonzero_px']} non-zero) in {c['tiles_touched']} tiles"
                                 for z, c in clip["per_zoom"].items()))
    for r in rep["largest"][:6]:
        print(f"    {r['tile']} px {r['pixel']}: {r['from_m']} -> {r['to_m']} m ({r['px']} px in tile)")
    print(f"  spot check: {json.dumps(spot, sort_keys=True, ensure_ascii=False)}")
    if total > 12e6:
        print("  NOTE: terrain.js exceeds 12 MB (kept every tile; see per-zoom sizes above)")


if __name__ == "__main__":
    main()
