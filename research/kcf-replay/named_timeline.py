"""Named-place timeline table (4-6 places): per issue hour, step and latest safe departure under each stand-in (8 h and
5 h), the shelter, and the documented times (SOURCES.md). Usage: python3 named_timeline.py per_place.csv OUT.csv"""
import csv, sys
NAMES = ["화매리", "지품리", "옥류리", "매정리", "노물리", "강구리"]
DOC = {
    "화매리": "~18:00 이장 음성 안내·마을 가장자리 화염 (매일신문, SINGLE); 영양군 공식 경보 시각 미확인",
    "지품리": "18:00 지품면 대피명령·CBS; 18:25 황장재 통행제한 CBS; 18:58 국도34호선(구미~황장) 통제; 19:04 도계→영양 도로통제; 19:30 9개 읍·면 명령; 20:25 단전; 21:00 군 CBS (뉴스로, SINGLE); 화재 도달 시각 문서 없음",
    "옥류리": "18:00 지품면 명령; 18:52 옥류리 CBS; 18:58 국도34호선 통제; 19:30; 21:00 (뉴스로, SINGLE); 화재 도달 시각 문서 없음",
    "매정리": "19:30 9개 읍·면 명령; 21:00 군 CBS (뉴스로, SINGLE); ~20:00 이장 방문, ~20:30 주민 출발, ~20:40 마을에 불 (한국일보, 주민 1인, SINGLE)",
    "노물리": "19:30; 21:00 (뉴스로, SINGLE); ~24:00 주민 인지 (대구신문, SINGLE); 화재 도달 시각 문서 없음",
    "강구리": "19:30; 21:00 (뉴스로); 21:58 국도7호선 송라 지경삼거리 통제 (뉴스로); 00:07 문자, ~00:37 불 도달, 00:41 재문자 (경향신문, 강구면·남정면 단위, SINGLE)",
}
rows = [r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")) if r["name"] in NAMES and r["region"] == "yeongdeok_2025"]
out = []
for n in NAMES:
    for hz in ("8h", "5h"):
        issues = sorted({r["issue_kst"] for r in rows if r["name"] == n})
        for t in issues:
            o = {"place": n, "horizon": hz, "issue_kst": t}
            for st in ("ORDINARY", "RUNNING", "WORST", "MEASURED", "MEASURED_GUST"):
                r = next(x for x in rows if x["name"] == n and x["issue_kst"] == t and x["standin"] == st and x["horizon"] == hz)
                lsd = r["latest_safe_departure_kst"][6:]
                if not lsd:
                    lsd = {"NOT_CUT_WITHIN_H": "not cut in " + hz, "INSIDE_KNOWN_FIRE_AREA": "inside known fire",
                           "NO_SAFE_DEPARTURE": "none"}[r["departure_state"]]
                o[f"{st}_step"] = r["government_step"]
                o[f"{st}_latest_safe_departure"] = lsd
                o[f"{st}_shelter"] = r["shelter_name"] or r["shelter_id"]
                o[f"{st}_route_cut_earlier"] = r["route_cut_before_departure"]
            o["dist_known_fire_km"] = r["dist_known_fire_km"]
            o["documented"] = DOC[n]
            out.append(o)
with open(sys.argv[2], "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out))
