"""KMA ASOS via data.go.kr (AsosDalyInfoService, AsosHourlyInfoService), 22-26 March 2025. Key is read from the file named by
$DATA_GO_KR_KEY_FILE, else from $DATA_GO_KR_KEY. It is never printed, logged or written to the output."""
import json, os, sys, time, datetime as dt, urllib.request, urllib.error
K = (open(os.environ["DATA_GO_KR_KEY_FILE"]).read().strip() if os.environ.get("DATA_GO_KR_KEY_FILE") else os.environ["DATA_GO_KR_KEY"])
STN = {"Uiseong": 278, "Andong": 136, "Cheongsong": 276, "Yeongdeok": 277, "Yeongyang": None}
BASE = "https://apis.data.go.kr/1360000/"
def call(path, **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    url = BASE + path + "?serviceKey=" + K + "&" + qs
    for i in range(4):
        try:
            t = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            r = urllib.request.urlopen(url, timeout=60); b = r.read().decode("utf-8", "replace"); st = r.status
        except urllib.error.HTTPError as e:
            st, b, t = e.code, e.read().decode("utf-8", "replace"), t
        except Exception as e:
            st, b = None, str(e).replace(K, "<key>")
        if st == 200:
            try: return t, json.loads(b)
            except Exception: return t, {"raw_head": b[:300].replace(K, "<key>")}
        time.sleep(2 ** (i + 1))
    return t, {"error": st, "body": (b or "")[:300].replace(K, "<key>")}
out, log = {}, []
for name, sid in STN.items():
    if sid is None:
        out[name] = {"stn": None, "note": "no ASOS id assumed (protocol amendment 1)"}; continue
    t1, d = call("AsosDalyInfoService/getWthrDataList", pageNo=1, numOfRows=10, dataType="JSON", dataCd="ASOS", dateCd="DAY",
                 startDt="20250322", endDt="20250326", stnIds=sid)
    t2, h = call("AsosHourlyInfoService/getWthrDataList", pageNo=1, numOfRows=100, dataType="JSON", dataCd="ASOS", dateCd="HR",
                 startDt="20250325", startHh="00", endDt="20250325", endHh="23", stnIds=sid)
    def items(j):
        try: return j["response"]["body"]["items"]["item"]
        except Exception: return None
    hdr = lambda j: j.get("response", {}).get("header", j)
    out[name] = {"stn": sid, "daily_header": hdr(d), "hourly_header": hdr(h), "daily": items(d), "hourly": items(h)}
    log.append(dict(point=name, stn=sid, daily_fetched_utc=t1, hourly_fetched_utc=t2, daily_header=hdr(d), hourly_header=hdr(h)))
json.dump(out, open("work/kma_datagokr.json", "w"), ensure_ascii=False)
json.dump(dict(service="data.go.kr 1360000 AsosDalyInfoService / AsosHourlyInfoService (KMA ASOS)", key="not stored", fetches=log), open("work/fetch_log_kma_datagokr.json", "w"), indent=1, ensure_ascii=False)
for name, v in out.items():
    print(name, v.get("stn"), v.get("daily_header"), v.get("hourly_header"), "daily rows", len(v.get("daily") or []), "hourly rows", len(v.get("hourly") or []))
