"""Wi-Fi pull (spec section 3C, option): the device's own export mode serves 192.168.4.1 (firmware web_export.cpp).

The backend makes these requests, never the page, and to no address other than 192.168.4.1 (tests replace BASE with a
local test server; nothing else changes it). The app never sends a confirm or a delete over Wi-Fi.
  GET /api/status                       {"device","board","fw","state","used","total","last_delete"}
  GET /api/list                         [{"name","session_id","mode","size","records","closed","end_reason",
                                          "exported","ok_sha","active","start_reason"}, ...]
  GET /api/sha?name=S000001.wfg&fmt=wfg {"sha256","size"}
  GET /dl?name=S000001.wfg&fmt=wfg      the bytes, with the header X-WFG-SHA256
"""
import hashlib
import json
import urllib.parse
import urllib.request

BASE = "http://192.168.4.1"
TIMEOUT_S = 2.0
DL_TIMEOUT_S = 60.0


class WifiError(RuntimeError):
    pass


def _opener():
    # No proxy: the request must go straight to the device's access point (or the local test server in tests).
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(path, timeout=TIMEOUT_S):
    url = BASE + path
    try:
        with _opener().open(url, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except OSError as ex:
        raise WifiError(str(ex))


def _json(path):
    status, _, body = _get(path)
    if status != 200:
        raise WifiError("HTTP %d for %s" % (status, path))
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as ex:
        raise WifiError("bad JSON from %s: %s" % (path, ex))


def status():
    return _json("/api/status")


def sessions():
    """Closed sessions only: one still recording ("active": true) is not offered."""
    items = _json("/api/list")
    return [s for s in items if not s.get("active")]


def download(name):
    """Returns (bytes, header sha, api sha). Raises WifiError when the hashes disagree."""
    q = urllib.parse.urlencode({"name": name, "fmt": "wfg"})
    status_code, headers, body = _get("/dl?" + q, timeout=DL_TIMEOUT_S)
    if status_code != 200:
        raise WifiError("HTTP %d for %s" % (status_code, name))
    head_sha = {k.lower(): v for k, v in headers.items()}.get("x-wfg-sha256", "").strip().lower()
    api = _json("/api/sha?" + q)
    api_sha = str(api.get("sha256", "")).lower()
    got = hashlib.sha256(body).hexdigest()
    if not head_sha or got != head_sha or got != api_sha:
        raise WifiError("SHA-256 mismatch: received %s, header %s, /api/sha %s" % (got[:12], head_sha[:12] or "-",
                                                                                api_sha[:12] or "-"))
    return body, head_sha, api_sha
