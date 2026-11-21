"""Assign OSM-mapped buildings and facilities (snapshot 2025-03-21) to the 174 places (nearest anchor, <= 1.5 km; PROTOCOL
§3 as amended 1) and add the by-use counts and facility names to per_place_real.csv; write data/osm_buildings_20250321.csv."""
import csv, json, re
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
LIM = 1500.0
T = Transformer.from_crs(4326, 5179, always_xy=True)
def load(k): return json.load(open(f"raw/osm_{k}_20250321.json", encoding="utf-8"))["elements"]
def xy(e):
    lon, lat = (e["lon"], e["lat"]) if e["type"] == "node" else (e["center"]["lon"], e["center"]["lat"])
    return lon, lat
per = {r["place_id"]: r for r in csv.DictReader(open("../kcf-replay/per_place.csv", encoding="utf-8")) if True}
places = {}
for r in csv.DictReader(open("../kcf-replay/per_place.csv", encoding="utf-8")):
    places.setdefault(r["place_id"], (float(r["lon"]), float(r["lat"]), r["name"]))
anch = [(pid, lon, lat, nm, True) for pid, (lon, lat, nm) in places.items()]
P = np.array([T.transform(a[1], a[2]) for a in anch])
tree0 = cKDTree(P)
for e in load("place"):
    lon, lat = xy(e); x, y = T.transform(lon, lat)
    if tree0.query([x, y])[0] < 25: continue
    anch.append(("osm:node/%d" % e["id"], lon, lat, e["tags"].get("name", ""), False))
A = np.array([T.transform(a[1], a[2]) for a in anch]); tree = cKDTree(A)
print("anchors", len(anch), "of which the 174 places:", sum(a[4] for a in anch))
HOUSE = {"house", "detached", "semidetached_house", "terrace", "residential", "bungalow", "farm", "cabin", "hut", "static_caravan"}
def cls(t):
    b = t.get("building", ""); am = t.get("amenity", "")
    nm = t.get("name", "") + t.get("name:ko", "")
    if b in ("apartments", "dormitory") : return "apartment"
    if b in ("school", "kindergarten", "college", "university") or am in ("school", "kindergarten", "college", "childcare"): return "school"
    if b in ("nursing_home", "hospital") or am in ("social_facility", "nursing_home", "hospital", "clinic", "doctors") or re.search("요양|노인복지|양로|복지", nm) and "경로당" not in nm: return "care"
    if b in HOUSE: return "house"
    if b == "yes": return "unknown"
    return "other"
cnt = {pid: dict(house=0, apartment=0, care=0, school=0, other=0, unknown=0) for pid in places}
rows = []
for e in load("building"):
    lon, lat = xy(e); x, y = T.transform(lon, lat); d, i = tree.query([x, y])
    c = cls(e["tags"]); pid = anch[i][0] if anch[i][4] and d <= LIM else ""
    if pid: cnt[pid][c] += 1
    rows.append((e["type"][0] + str(e["id"]), round(lon, 6), round(lat, 6), c, pid, round(float(d))))
with open("data/osm_buildings_20250321.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["osm_id", "lon", "lat", "use", "place_id", "dist_m"]); w.writerows(rows)
fac = {pid: dict(school=[], care=[], senior=[], health=[]) for pid in places}
frows = []
for e in load("amenity"):
    t = e["tags"]; nm = t.get("name") or t.get("name:ko") or ""
    am = t.get("amenity", ""); k = None
    if am in ("school", "kindergarten", "college") or t.get("building") in ("school", "kindergarten"): k = "school"
    elif am in ("social_facility", "nursing_home") or t.get("building") == "nursing_home" or (re.search("요양|노인복지|양로", nm)): k = "care"
    elif am in ("hospital", "clinic", "doctors") or t.get("healthcare") or t.get("building") == "hospital": k = "health"
    elif re.search("경로당", nm): k = "senior"
    if not k: continue
    lon, lat = xy(e); x, y = T.transform(lon, lat); d, i = tree.query([x, y]); pid = anch[i][0] if anch[i][4] and d <= LIM else ""
    if pid and nm: fac[pid][k].append(nm)
    frows.append((e["type"][0] + str(e["id"]), nm, k, am or t.get("building", ""), round(lon, 6), round(lat, 6), pid, round(float(d))))
with open("data/osm_facilities_20250321.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["osm_id", "name", "class", "tag", "lon", "lat", "place_id", "dist_m"]); w.writerows(frows)
rows = list(csv.DictReader(open("per_place_real.csv", encoding="utf-8")))
new = ["bldg_mapped_total", "bldg_house", "bldg_apartment", "bldg_care", "bldg_school", "bldg_other", "bldg_unknown", "schools", "care_facilities", "senior_halls", "health_facilities", "bldg_status"]
for r in rows:
    c = cnt.get(r["place_id"])
    if c is None:
        for k in new: r[k] = ""
        continue
    r.update(bldg_mapped_total=sum(c.values()), bldg_house=c["house"], bldg_apartment=c["apartment"], bldg_care=c["care"], bldg_school=c["school"], bldg_other=c["other"], bldg_unknown=c["unknown"],
             schools="; ".join(sorted(set(fac[r["place_id"]]["school"]))), care_facilities="; ".join(sorted(set(fac[r["place_id"]]["care"]))),
             senior_halls="; ".join(sorted(set(fac[r["place_id"]]["senior"]))), health_facilities="; ".join(sorted(set(fac[r["place_id"]]["health"]))),
             bldg_status="MAPPED in OSM 2025-03-21 (lower bound, not a count)")
keys = list(rows[0].keys()); [keys.append(k) for r in rows for k in r if k not in keys]
with open("per_place_real.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
tot = sum(sum(c.values()) for c in cnt.values())
print("buildings read", len(rows) and sum(1 for _ in open("data/osm_buildings_20250321.csv")) - 1, "assigned to the 174:", tot, "facilities", len(frows))
