"""KMA ASOS hourly (apihub kma_sfctm2.php), every KST hour 2025-03-22 00:00 .. 2025-03-26 23:00, stn=0 (all), keep 4 stations.
Key from $KMA_API_KEY_FILE or $KMA_API_KEY; never printed, logged or written."""
import json, os, sys, time, datetime as dt, urllib.request
K = open(os.environ["KMA_API_KEY_FILE"]).read().strip() if os.environ.get("KMA_API_KEY_FILE") else os.environ["KMA_API_KEY"]
STN = {278: "Uiseong", 136: "Andong", 276: "Cheongsong", 277: "Yeongdeok"}
URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php?tm={tm}&stn=0&help=0&authKey=" + K
t0 = dt.datetime(2025, 3, 22, 0); rows = []; log = []; fails = []
for i in range(120):
    tm = (t0 + dt.timedelta(hours=i)).strftime("%Y%m%d%H00")
    for a in range(5):
        try:
            ft = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            txt = urllib.request.urlopen(URL.format(tm=tm), timeout=60).read().decode("euc-kr", "replace")
            if txt.lstrip().startswith("{"):
                raise RuntimeError(txt.replace(K, "<key>")[:160])
            break
        except Exception as e:
            err = str(e).replace(K, "<key>"); time.sleep(2 ** a)
    else:
        fails.append((tm, err)); continue
    n = 0
    for ln in txt.splitlines():
        if ln.startswith("#") or not ln.strip(): continue
        f = ln.split()
        if len(f) > 7 and int(f[1]) in STN:
            rows.append(dict(tm=f[0], stn=int(f[1]), point=STN[int(f[1])], wd=f[2], ws=f[3], gst_wd=f[4], gst_ws=f[5], gst_tm=f[6])); n += 1
    log.append(dict(tm=tm, fetched_utc=ft, stations_found=n))
json.dump(rows, open("work/kma_asos_hourly.json", "w"), indent=0)
json.dump(dict(service="apihub.kma.go.kr kma_sfctm2.php (ASOS hourly), stn=0, 4 stations kept", key="not stored", calls=len(log), failures=fails, first_fetch=log[0]["fetched_utc"] if log else None, last_fetch=log[-1]["fetched_utc"] if log else None, per_hour=log), open("work/fetch_log_kma_hourly.json", "w"), indent=0)
print("rows", len(rows), "calls ok", len(log), "failures", fails[:3])
