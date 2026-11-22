"""Fetch MOIS 주민등록 인구통계 monthly CSVs (all 읍면동) for one month: households+population, and age bands.
Usage: python3 fetch_mois.py 2025 02   -> data/mois_YYYYMM_households.csv, data/mois_YYYYMM_age5.csv (+ .sha256)"""
import sys, hashlib, time, requests
y, m = sys.argv[1], sys.argv[2]
UA = {"User-Agent": "wildfireguardian-research/1.0"}
s = requests.Session(); s.headers.update(UA)
base = "https://jumin.mois.go.kr/"
def post(page, dl, extra):
    s.get(base + page, timeout=60)
    d = dict(sltOrgType="1", sltOrgLvl1="A", sltOrgLvl2="", sltUndefType="", searchYearStart=y, searchMonthStart=m,
             searchYearEnd=y, searchMonthEnd=m, sltOrderType="1", sltOrderValue="ASC", category="month", state="3")
    d.update(extra)
    r = s.post(base + dl + "?searchYearMonth=month&xlsStats=3", data=d, timeout=300)
    r.raise_for_status(); return r.content
for name, page, dl, extra in [
    ("households", "statMonth.do", "downloadCsv.do", dict(gender="gender")),
    ("age5", "ageStatMonth.do", "downloadCsvAge.do", dict(gender="gender", sum="sum", sltArgTypes="5", sltArgTypeA="0", sltArgTypeB="100"))]:
    b = post(page, dl, extra)
    fn = f"data/mois_{y}{m}_{name}.csv"; open(fn, "wb").write(b)
    open(fn + ".sha256", "w").write(hashlib.sha256(b).hexdigest() + "  " + fn.split("/")[-1] + "\n")
    print(fn, len(b), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
