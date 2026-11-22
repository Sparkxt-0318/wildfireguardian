"""Build data/eupmyeondong_202502.csv: MOIS 2025-02 households, population, 65+ for every 읍·면·동 of 안동시, 의성군,
청송군, 영양군, 영덕군, plus the number of live 법정리 under it (법정동코드 table of PublicDataReader 1.1.1.post2)."""
import csv, io, json, re, zipfile
from collections import defaultdict
SG = ["안동시", "의성군", "청송군", "영양군", "영덕군"]
def rd(fn, enc):
    return list(csv.reader(io.StringIO(open(fn, "rb").read().decode(enc))))
def num(s): return int(s.replace(",", "") or 0)
hh = rd("data/mois_202502_households.csv", "cp949")
age = rd("data/mois_202502_age5.csv", "cp949")
ah = age[0]
i65 = [k for k, h in enumerate(ah) if k > 0 and h.split("_", 1)[1].startswith("계_") and re.match(r"계_(65|70|75|80|85|90|95)~|계_100세", h.split("_", 1)[1])]
assert len(i65) == 8, [ah[k] for k in i65]
agemap = {r[0]: r for r in age[1:]}
z = zipfile.ZipFile("raw/PublicDataReader.whl"); d = json.load(z.open("PublicDataReader/raw/code_bdong.json"))
n = len(d["법정동코드"]); rows = [{k: d[k][str(i)] for k in d} for i in range(n)]
ri = defaultdict(set)
for r in rows:
    isn = lambda v: isinstance(v, str) and v
    if r["시도명"] == "경상북도" and not isn(r["말소일자"]) and r["시군구명"] in SG and isn(r["읍면동명"]):
        ri[(r["시군구명"], r["읍면동명"])].add(r["동리명"]) if isn(r["동리명"]) else ri[(r["시군구명"], r["읍면동명"])].add("")
out = []
for r in hh[1:]:
    m = re.match(r"경상북도 (\S+) (\S+?)\s*\((\d+)\)$", r[0].strip())
    if not m or m.group(1) not in SG: continue
    sg, nm, code = m.groups(); a = agemap[r[0]]
    mm = re.match(r"^(.+?[읍면])\S*출장소$", nm)
    sub = nm if mm else ""
    if mm: nm = mm.group(1)
    P, H = num(r[1]), num(r[2]); A65 = sum(num(a[k]) for k in i65)
    prev = [o for o in out if o[0] == sg and o[1] == nm]
    if prev:
        o = prev[0]; o[3] += H; o[4] += P; o[5] += A65; o[6] = round(o[4] / o[3], 3); o[8] += "+" + sub; continue
    out.append([sg, nm, code, H, P, A65, round(P / H, 3) if H else "", len(ri.get((sg, nm), set()) - {""}) or (1 if (sg, nm) in ri else 0), sub])
with open("data/eupmyeondong_202502.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["sigungu", "eupmyeondong", "mois_code", "households", "population", "age65plus", "persons_per_hh", "n_legal_ri", "merged_sub_office"]); w.writerows(out)
print(len(out)); print(sum(1 for o in out if o[7] == 0), "without 법정리 match:", [o[:2] for o in out if o[7] == 0][:40])
for o in out:
    if o[0] in ("영덕군",): print(o)
