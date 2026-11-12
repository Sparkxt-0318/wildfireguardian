"""Throttled, disk-cached HTTP helper for HPWREN hosts.
Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego.
Sequential only; >= 1.2 s between any two requests to hpwren hosts; every
response (including 403/404) is cached on disk and never refetched."""
import hashlib, json, time, urllib.request, urllib.error, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "http"
UA = "research-poc-camera-arrival/0.1"
MIN_INTERVAL = 1.2
_last = [0.0]
REQUEST_LOG = ROOT / "cache" / "request_log.jsonl"


def _key(method, url):
    return hashlib.sha256((method + " " + url).encode()).hexdigest()


def fetch(url, method="GET", max_bytes=None, range_header=None):
    """Return dict(status, body(bytes), headers, from_cache). Never refetches.
    HEAD/ranged GET are cached separately. Network errors are cached as status 0
    only for DNS/proxy refusals (HTTPError statuses are always cached)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    k = _key(method + (range_header or ""), url)
    meta, body = CACHE / (k + ".json"), CACHE / (k + ".bin")
    if meta.exists():
        m = json.loads(meta.read_text())
        m["body"] = body.read_bytes() if body.exists() else b""
        m["from_cache"] = True
        return m
    wait = MIN_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    if range_header:
        req.add_header("Range", range_header)
    status, data, headers, err = None, b"", {}, None
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            status, headers = r.status, dict(r.headers)
            data = r.read(max_bytes) if max_bytes else r.read()
    except urllib.error.HTTPError as e:
        status, headers = e.code, dict(e.headers)
        data = e.read(4000)
    except Exception as e:  # network-level error: record, do not cache
        err = repr(e)
    _last[0] = time.time()
    with open(REQUEST_LOG, "a") as f:
        f.write(json.dumps({"t": time.time(), "method": method, "url": url, "status": status, "err": err}) + "\n")
    if err:
        return {"status": None, "body": b"", "headers": {}, "error": err, "from_cache": False}
    meta.write_text(json.dumps({"url": url, "method": method, "status": status, "headers": headers}))
    body.write_bytes(data)
    return {"status": status, "body": data, "headers": headers, "from_cache": False}
