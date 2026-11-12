"""Independent archive spot-check for the Step 0 audit (own fetch code, not hpwren_common.fetch).
Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego.
Etiquette: sequential, >= 1.5 s between requests, generic User-Agent, every response cached under
cache/audit_http/ and never refetched. Only small objects are downloaded (one list .txt, one JPEG);
videos are HEAD only.
Checks:
  1. GOFER-era: list GET + video HEAD for wilson-e-mobo-c 2020-09-09 Q2 (top-ranked restore block, not
     probed by the original gate) -> expect list 403, video 200 DEEP_ARCHIVE if the claim holds.
  2. Positive control for the same camera and URL templates today: list GET for a recent block, then one
     JPEG GET; confirm magic bytes, resolution and that the epoch in the filename matches the EXIF/
     Last-Modified time.
Writes outputs/audit_s0_archive_probe.json.
"""
import hashlib, json, pathlib, re, time, urllib.request, urllib.error, datetime as dt, io
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
C = ROOT / "cache" / "audit_http"; C.mkdir(parents=True, exist_ok=True)
UA = "research-poc-camera-arrival/0.1 (audit)"
_last = [0.0]

def get(url, method="GET"):
    k = hashlib.sha256(f"{method} {url}".encode()).hexdigest()
    mp, bp = C / f"{k}.json", C / f"{k}.bin"
    if mp.exists():
        m = json.loads(mp.read_text()); m["body"] = bp.read_bytes() if bp.exists() else b""; m["cached"] = True
        return m
    w = 1.5 - (time.time() - _last[0])
    if w > 0: time.sleep(w)
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            st, hd, body = r.status, dict(r.headers), (r.read() if method == "GET" else b"")
    except urllib.error.HTTPError as e:
        st, hd, body = e.code, dict(e.headers), e.read(2000)
    _last[0] = time.time()
    mp.write_text(json.dumps({"url": url, "method": method, "status": st, "headers": hd,
                              "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat()}))
    bp.write_bytes(body)
    return {"url": url, "method": method, "status": st, "headers": hd, "body": body, "cached": False}

CDN = "https://cdn.hpwren.ucsd.edu/hpwren-cameras/"
MTA = "https://cdn.hpwren.ucsd.edu/MTA/"
cam = "wilson-e-mobo-c"
out = {"credits": "HPWREN (hpwren.ucsd.edu), UC San Diego", "camera": cam, "checks": []}

d, q = "20200909", 2
r = get(f"{CDN}{cam}/2020/{d}/{d}_{cam}_Q{q}.txt")
out["checks"].append({"what": "GOFER-era list", "url": r["url"], "status": r["status"]})
r = get(f"{CDN}{cam}/2020/{d}/Q{q}.mp4", "HEAD")
out["checks"].append({"what": "GOFER-era video HEAD", "url": r["url"], "status": r["status"],
                      "storage_class": r["headers"].get("x-amz-storage-class"),
                      "bytes": r["headers"].get("Content-Length")})

# positive control: yesterday (Pacific) block Q5 (12-15 PT)
now_pt = dt.datetime.now(ZoneInfo("America/Los_Angeles"))
y = (now_pt - dt.timedelta(days=1)).strftime("%Y%m%d")
r = get(f"{CDN}{cam}/{y[:4]}/{y}/{y}_{cam}_Q5.txt")
eps = [int(e) for e in re.findall(r"(?<!\d)(\d{10})\.jpg", r["body"].decode(errors="ignore"))] if r["status"] == 200 else []
chk = {"what": "recent list (positive control)", "url": r["url"], "status": r["status"], "n_listed": len(eps)}
if eps:
    gaps = [b - a for a, b in zip(eps, eps[1:])]
    chk.update(first=dt.datetime.fromtimestamp(eps[0], ZoneInfo("America/Los_Angeles")).isoformat(),
               last=dt.datetime.fromtimestamp(eps[-1], ZoneInfo("America/Los_Angeles")).isoformat(),
               median_gap_s=sorted(gaps)[len(gaps) // 2] if gaps else None)
out["checks"].append(chk)
if eps:
    e = eps[len(eps) // 2]
    r = get(f"{MTA}{cam}/large/{y}/Q5/{e}.jpg")
    info = {"what": "one recent JPEG (positive control)", "url": r["url"], "status": r["status"],
            "bytes": len(r["body"]), "is_jpeg": r["body"][:3] == b"\xff\xd8\xff",
            "filename_epoch_pacific": dt.datetime.fromtimestamp(e, ZoneInfo("America/Los_Angeles")).isoformat(),
            "last_modified": r["headers"].get("Last-Modified")}
    if info["is_jpeg"]:
        import numpy as np, cv2
        im = cv2.imdecode(np.frombuffer(r["body"], np.uint8), cv2.IMREAD_COLOR)
        info["resolution_wxh"] = [int(im.shape[1]), int(im.shape[0])]
        m = re.search(rb"(\d{4}:\d\d:\d\d \d\d:\d\d:\d\d)", r["body"][:4000])
        info["exif_datetime"] = m.group(1).decode() if m else None
    out["checks"].append(info)

(ROOT / "outputs" / "audit_s0_archive_probe.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
