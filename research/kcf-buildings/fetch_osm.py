"""Fetch OSM objects as of 2025-03-21T23:59:59Z (Overpass attic) for the two regions: admin boundaries (level 8-10),
place nodes, buildings (tags + centre), amenities (schools, care, health). Raw JSON -> raw/ (not committed);
compact CSVs are made by add_osm.py (committed). Usage: python3 fetch_osm.py [admin place building amenity]"""
import json
import sys
import time

import overpass

BOXES = {"yeongdeok": (36.10, 128.95, 36.80, 129.55), "uiseong": (36.05, 128.25, 36.75, 129.00), "andong": (36.30, 128.25, 37.00, 129.25)}
PL = "^(village|hamlet|neighbourhood|isolated_dwelling|suburb|quarter|town|locality)$"
Q = {
    "admin": 'relation["boundary"="administrative"]["admin_level"~"^(8|9|10)$"]({b});\nout geom tags;',
    "place": 'node["place"~"' + PL + '"]({b});\nout;',
    "building": 'nwr["building"]({b});\nout tags center;',
    "amenity": ('nwr["amenity"~"^(school|kindergarten|college|social_facility|nursing_home|hospital|clinic|doctors|childcare|community_centre)$"]({b});\n'
                'nwr["healthcare"]({b});\nnwr["building"~"^(school|kindergarten|hospital|nursing_home)$"]({b});\nout tags center;'),
}


def main(kinds):
    for kind, q in Q.items():
        if kinds and kind not in kinds:
            continue
        allel = {}
        for name, (s, w, n, e) in BOXES.items():
            d = overpass.query(q.format(b=f"{s},{w},{n},{e}"), 400)
            for el in d["elements"]:
                allel[(el["type"], el["id"])] = el
            print(kind, name, len(d["elements"]), flush=True)
        fn = f"raw/osm_{kind}_20250321.json"
        json.dump({"date": overpass.DATE, "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elements": list(allel.values())},
                  open(fn, "w"), ensure_ascii=False)
        print(kind, "total", len(allel), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
