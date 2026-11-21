"""Per-place real household, resident, 65+ and vehicle numbers (PROTOCOL §3 as amended) -> per_place_real.csv (+ inputs for
research/kcf-queue: research/kcf-queue/inputs_real/<region>.csv). OSM-derived columns are added by add_osm.py."""
import csv, io, json, re
from pathlib import Path
R = Path(__file__).resolve().parents[2]
PROD = R / "product/wfg-roadlayer/data"
emd = {(r["sigungu"], r["eupmyeondong"]): r for r in csv.DictReader(open("data/eupmyeondong_202502.csv", encoding="utf-8"))}
# province ratio: MOLIT vehicles 2024-12 (CITED in traffic_sources.json) / MOIS households 2025-02 (Gyeongbuk row)
t = io.StringIO(open("data/mois_202502_households.csv", "rb").read().decode("cp949"))
prov = [r for r in csv.reader(t) if re.match(r"^경상북도\s+\(4700000000\)", r[0].strip())][0]
H_GB = int(prov[2].replace(",", ""))
VEH_GB = json.load(open(PROD / "traffic_sources.json"))["vehicles"]["gyeongbuk_vehicles_2024_12"]["value"]
VPH = VEH_GB / H_GB
print("Gyeongbuk households 2025-02", H_GB, "vehicles 2024-12", VEH_GB, "veh/hh", round(VPH, 4))
per = {}
for r in csv.DictReader(open(R / "research/kcf-replay/per_place.csv", encoding="utf-8")):
    per.setdefault(r["place_id"], r)
rows, unmatched = [], []
for rid in ["uiseong_andong_2025", "yeongdeok_2025"]:
    towns = {r["place_id"]: r for r in csv.DictReader(open(PROD / f"towns/{rid}.csv", encoding="utf-8"))}
    old = list(csv.DictReader(open(PROD / f"households/{rid}.csv", encoding="utf-8")))
    out = []
    for o in old:
        pid = o["place_id"]; tw = towns[pid]
        row = dict(place_id=pid, name=o["name"], region=rid, kind=o["kind"], sigungu=o["sigungu"], eupmyeon=o["eupmyeon"],
                   eupmyeon_method=tw["method"], in_174=int(pid in per), households_old=o["households"], persons_per_household_old=o["persons_per_household"])
        e = emd.get((o["sigungu"], o["eupmyeon"]))
        if o["kind"] != "village":
            row.update(households=0, residents=o["facility_residents"], residents65="", vehicles=0, households_status="ASSUMED", residents_status="ASSUMED (care facility, 30 residents, old rule)", vehicles_status="ASSUMED (none with a car, old rule)", residents65_status="not available")
        elif e is None or e["n_legal_ri"] in ("0", 0):
            unmatched.append((pid, o["name"], o["sigungu"], o["eupmyeon"]))
            row.update(households=o["households"], residents=round(float(o["households"]) * float(o["persons_per_household"] or 1.7), 1), residents65="", vehicles=round(float(o["households"]) * VPH, 1),
                       households_status="ASSUMED (old equal split kept: 읍면동 not matched)", residents_status="ASSUMED (old)", vehicles_status="ESTIMATED (province ratio)", residents65_status="not available")
        else:
            n = int(e["n_legal_ri"]); H, P, A = int(e["households"]), int(e["population"]), int(e["age65plus"])
            row.update(households=round(H / n, 2), residents=round(P / n, 2), residents65=round(A / n, 2), vehicles=round(H / n * VPH, 2),
                       households_status="ESTIMATED (MEASURED 읍면동 2025-02 / %d 법정리)" % n, residents_status="ESTIMATED (MEASURED 읍면동 2025-02 / %d 법정리)" % n,
                       residents65_status="ESTIMATED (MEASURED 읍면동 2025-02 / %d 법정리)" % n, vehicles_status="ESTIMATED (province ratio %.3f)" % VPH,
                       hh_eupmyeondong=H, pop_eupmyeondong=P, age65_eupmyeondong=A, n_legal_ri=n)
        rows.append(row); out.append(row)
    qdir = R / "research/kcf-queue/inputs_real"; qdir.mkdir(exist_ok=True)
    with open(qdir / f"{rid}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["place_id", "name", "sigungu", "eupmyeon", "kind", "households", "persons_per_household", "facility_residents", "status", "basis", "vehicles"])
        for r in out:
            w.writerow([r["place_id"], r["name"], r["sigungu"], r["eupmyeon"], r["kind"], r["households"], r.get("persons_per_household_old", ""), "", r["households_status"], "kcf-buildings", r["vehicles"]])
keys = []
for r in rows:
    for k in r:
        if k not in keys: keys.append(k)
with open("per_place_real.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
print(len(rows), "rows;", sum(r["in_174"] for r in rows), "in the 174; unmatched:", unmatched)
json.dump(dict(H_GB_2025_02=H_GB, vehicles_gb_2024_12=VEH_GB, veh_per_hh=VPH), open("data/vehicle_ratio.json", "w"))
