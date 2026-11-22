"""Overpass client with backoff. Historical snapshot via [date:...] (attic). UA identifies the project only."""
import json, sys, time, hashlib, requests
URLS = ["https://overpass-api.de/api/interpreter"]
UA = {"User-Agent": "wildfireguardian-research/1.0"}
DATE = "2025-03-21T23:59:59Z"
def query(body, timeout=180, tries=12):
    q = f'[out:json][timeout:{timeout}][date:"{DATE}"];\n{body}'
    wait = 10
    for i in range(tries):
        for u in URLS:
            try:
                r = requests.post(u, data={"data": q}, headers=UA, timeout=timeout + 60)
                if r.status_code == 200 and r.text.startswith("{"):
                    return r.json()
                sys.stderr.write(f"try {i} {u} -> {r.status_code} {r.text[:60]!r}\n")
            except Exception as e:
                sys.stderr.write(f"try {i} {u} -> {type(e).__name__}\n")
        time.sleep(wait); wait = min(wait * 2, 240)
    raise RuntimeError("overpass failed")
if __name__ == "__main__":
    d = query('way["building"](36.40,129.35,36.405,129.355);\nout tags center 3;', 60)
    print(json.dumps(d.get("osm3s"), ensure_ascii=False), len(d["elements"]))
