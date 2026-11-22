"""Write the household tables and the building points that product/wfg-roadlayer reads, from per_place_real.csv.
The old tables (assumed arm) are kept in data/households_assumed/ (git mv done once by hand)."""
import csv, gzip
from pathlib import Path
from pyproj import Transformer
R = Path(__file__).resolve().parents[2]
PROD = R / "product/wfg-roadlayer/data"
T = Transformer.from_crs(4326, 5179, always_xy=True)
rows = list(csv.DictReader(open("per_place_real.csv", encoding="utf-8")))
cols = ["place_id", "name", "sigungu", "eupmyeon", "kind", "households", "persons_per_household", "facility_residents", "status", "basis",
        "residents", "residents65", "vehicles", "households_status", "residents_status", "residents65_status", "vehicles_status",
        "bldg_house", "bldg_apartment", "bldg_care", "bldg_school", "bldg_other", "bldg_unknown", "bldg_mapped_total", "schools", "care_facilities", "bldg_status", "data_dates"]
DATES = "MOIS 2025-02 (households, residents, 65+); OSM 2025-03-21 (buildings); vehicles: MOLIT 2024-12 province / MOIS 2025-02 province households"
for rid in ("uiseong_andong_2025", "yeongdeok_2025"):
    out = []
    for r in rows:
        if r["region"] != rid: continue
        o = dict(r)
        if r["kind"] == "village" and r.get("n_legal_ri"):
            hh, res = float(r["households"]), float(r["residents"])
            o["persons_per_household"] = round(res / hh, 3) if hh else r["persons_per_household_old"]
            o["status"] = r["households_status"]
            o["basis"] = ("%s %s: 세대 %s, 주민 %s, 65세 이상 %s (MOIS 2025-02, MEASURED 읍·면·동) / 법정리 %s (균등 분할, ESTIMATED)" %
                          (r["sigungu"], r["eupmyeon"], r["hh_eupmyeondong"], r["pop_eupmyeondong"], r["age65_eupmyeondong"], r["n_legal_ri"]))
        elif r["kind"] == "village":
            o["persons_per_household"] = r["persons_per_household_old"]; o["status"] = r["households_status"]; o["basis"] = "old equal split kept (읍·면·동 not matched)"
        else:
            o["persons_per_household"] = ""; o["status"] = "ASSUMED"; o["basis"] = "care facility: 30 residents, none with a car (ASSUMED, old rule)"
            o["facility_residents"] = "30"
        o["data_dates"] = DATES
        out.append({k: o.get(k, "") for k in cols})
    with open(PROD / "households" / f"{rid}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(out)
# building points for 'buildings at risk' (EPSG:5179 metres)
pl = {r["place_id"]: r["region"] for r in rows}
for rid in ("uiseong_andong_2025", "yeongdeok_2025"):
    (PROD / "buildings").mkdir(exist_ok=True)
    n = 0
    with gzip.open(PROD / "buildings" / f"{rid}.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["osm_id", "place_id", "use", "x", "y"])
        for b in csv.DictReader(open("data/osm_buildings_20250321.csv", encoding="utf-8")):
            if b["place_id"] and pl.get(b["place_id"]) == rid:
                x, y = T.transform(float(b["lon"]), float(b["lat"]))
                w.writerow([b["osm_id"], b["place_id"], b["use"], round(x, 1), round(y, 1)]); n += 1
    print(rid, "building points", n)
