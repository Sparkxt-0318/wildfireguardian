# 산악기상관측망 for the 2025 영덕 fire — acquired, verified, and what it is for

**Acquired 2026-09-14 on the author's laptop.** The 산림청 국립산림과학원 mountain weather
network (data.go.kr 15084696) serves 10 m wind at minute resolution, and — the question the
2026-09-13 verification report left open and this page settles — **it serves history**: a
call with `tm=202503251400` returns real observations from the day the fire reached 영덕.

Acquisition script: `scripts/fetch_mountain_weather.py`. Raw pulls live under
`data/raw/mountain_weather/` (git-ignored) with a sidecar manifest each. Nothing here is
registered in `docs/NUMBERS.json` and nothing is on a judge-facing surface.

## 1. Why this network and not ERA5

`docs/MODEL_CARD.md` records that the committed spread model runs on ERA5 weather at about
0.25°, roughly 25 km, hourly means. The national system's own post-mortem of the same fire
(원명수, 국립산림과학원, YTN 2025-04-09) said the thing that beat it was gusts:
「초속 27m 정도의 순간 최대 풍속이 실제로는 예상이 안 됐습니다」, and the government's
response was to re-specify the evacuation zone on 최대순간풍속 (행안부, 주민대피 3단계 체계).

A 25 km hourly mean cannot carry that. This network can: **94 stations in 경상북도 alone**,
of which **8 carry 영덕 in their name** (대봉산, 독경산, 등운산, 명동산, 바데산, 삿갓봉,
칠보산, 서항목재), against **one** ASOS station for the whole county (지점 277).

## 2. What is held

| pull | window (KST) | step | calls | rows | gaps |
|---|---|---|---:|---:|---|
| hourly, fire period | 2025-03-22 00:00 – 03-28 23:00 | 60 min | 168 | 15,792 | 0 empty timestamps; 14.2 % of rows carry no wind value (station reported `-`, kept not dropped) |
| minute, the 영덕 night | 2025-03-25 16:00 – 03-26 03:59 | 1 min | 720 | 67,680 | 0 empty timestamps; 16.9 % of rows carry no wind value |

Fields per station per timestamp: `ws10m`/`wd10m` (10 m wind speed and direction, plus a
16-point string), `ws2m`/`wd2m`, `tm10m`/`tm2m` (temperature), `hm10m`/`hm2m` (humidity),
`pa` (pressure), `ts` (ground temperature), `rn`/`cprn` (rain).

## 3. What the data says about the fire window [M]

Strongest hourly 10 m winds in 경상북도, 2025-03-22 to 03-28, from the pull above:

| time (KST) | 10 m wind | dir | station | RH |
|---|---:|---|---|---:|
| 2025-03-22 02:00 | 22.7 m/s | WNW | 포항 내연산 | 33.4 % |
| 2025-03-22 03:00 | 19.4 m/s | WNW | 포항 내연산 | 32.6 % |
| 2025-03-25 21:00 | 18.8 m/s | W | 울진 아구산 | 32.8 % |
| 2025-03-26 01:00 | 18.7 m/s | WNW | 포항 내연산 | 38.2 % |
| 2025-03-25 21:00 | 18.5 m/s | W | 울진 가재미재 | 35.6 % |

The 03-25 21:00 readings sit in the hours the fire ran from 청송 to the 영덕 coast, and the
direction is westerly, i.e. offshore, down the slope toward the coastal villages. The
strongest 영덕-named station reading in the window is 13.6 m/s (명동산, 03-22 21:00).

### At minute resolution, the event the national system missed is in the data

The 720-call, 1-minute pull over the night the fire reached the coast:

| time (KST) | 10 m wind | dir | station |
|---|---:|---|---|
| 2025-03-25 21:11 | **25.1 m/s** | W | 울진 가재미재 |
| 2025-03-25 20:46 | 24.1 m/s | WSW | 울진 아구산 |
| 2025-03-25 21:17 | 23.9 m/s | W | 울진 아구산 |
| 2025-03-25 22:08 | **19.4 m/s** | W | 영덕 독경산 |

The agency's own account of why its spread prediction fell behind is that a gust of about
27 m/s was not anticipated. This network **observed 25.1 m/s at 21:11 that night**, and
19.4 m/s at a station inside 영덕 an hour later, both westerly. The hourly aggregate of the
same network tops out at 18.8 m/s for the same night, and a 25 km hourly reanalysis mean
cannot resolve either. That gap — between what was observed at minute resolution on a public
free network and what the model was fed — is the specific, checkable opening this project has
on the environmental-input side.

⚠ **These are 10 m mean winds at the reporting minute, not 최대순간풍속.** This network does
not publish a separate gust field, so the 27 m/s the agency quoted is not reproduced here and
is not claimed. What is established is that the network resolves a westerly 18–22 m/s event
that a 25 km hourly mean cannot, at stations inside and beside the burned area.

## 4. What this does NOT show

- Not a gust product. No 최대순간풍속, no gust timestamp; see above.
- Not validated against the fire. No spread model has been re-run on this wind yet; that is
  the K-SPREAD stage-1 work (`docs/benchmark/K_SPREAD_2025.md`), not this page.
- Station coordinates are not in the API response (`obsid`, `obsname`, `localarea` only).
  The coordinate table is in the dataset's 기술문서 and has not been joined yet, so
  「8 영덕 stations」 is a name match, not a verified in-box location.
- 14.2 % of hourly rows carry no wind value. Those minutes are held as reported, and any
  downstream interpolation is a choice that must be declared where it is made.
- 경상북도 only. 강원 and other regions are one flag away but were not pulled.

## 5. Reproduce

    python scripts/fetch_mountain_weather.py --start 202503220000 --end 202503282300 --step 60
    python scripts/fetch_mountain_weather.py --start 202503251600 --end 202503260359 --step 1

Needs `~/.config/wildfireguardian/datago.key` (data.go.kr 일반 인증키, 개발계정 quota
10,000 calls/day). One call covers every station in a region for one timestamp.
