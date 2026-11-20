"""Fetch OSM objects as of 2025-03-21T23:59:59Z (Overpass attic) for the two regions: admin boundaries (level 8-10),
place nodes, buildings (tags + centre), amenities (schools, care, health). Raw JSON -> raw/ (not committed);
compact CSVs -> data/ (committed). Usage: python3 fetch_osm.py"""
import json, csv, hashlib, time, overpass
BOXES = {"yeongdeok": (36.10, 128.95, 36.80, 129.55), "uiseong": (36.05, 128.25, 36.75, 129.00), "andong": (36.30, 128.25, 37.00, 129.25)}
Q = {
 "admin": 'relation["boundary"="administrative"]["admin_level"~"^(8|9|10)$"]({b});\nout geom tags;',
 "place": 'node["place"~"^(village|hamlet|neighbourhood|isolated_dwelling|suburb|quarter|town|locality)$"]({b});\nout tags;',
 "building": 'nwr["building"]({b});\nout tags center;',
 "amenity": 'nwr["amenity"~"^(school|kindergarten|college|social_facility|nursing_home|hospital|clinic|doctors|childcare|community_centre)$"]({b});\nnwr["healthcare"]({b});\nnwr["building"~"^(school|kindergarten|hospital|nursing_home)$"]({b});\nout tags center;',
}
for kind, q in Q.items():
    allel = {}
    for name, (s, w, n, e) in BOXES.items():
        d = overpass.query(q.format(b=f"{s},{w},{n},{e}"), 400)
        for el in d["elements"]:
            allel[(el["type"], el["id"])] = el
        print(kind, name, len(d["elements"]), flush=True)
    fn = f"raw/osm_{kind}_20250321.json"
    json.dump({"date": overpass.DATE, "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elements": list(allel.values())}, open(fn, "w"), ensure_ascii=False)
    print(kind, "total", len(allel), flush=True)
