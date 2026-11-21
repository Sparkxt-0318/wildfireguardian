# INTERFACE — 화재 도달 입력 / fire-arrival input

모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order. 산림청 예측 시스템 출력을 이 형식으로 내보내면 그대로
꽂아 쓸 수 있습니다. If the Forest Service prediction system can export this, it plugs in unchanged.

## 필요한 것 / What is needed

| 항목 / item | 요구 / requirement |
|---|---|
| 파일 / file | GeoTIFF 1밴드 (float32/64 또는 정수; 무압축·LZW·Deflate·PackBits; 줄·타일). One band, float or integer; none/LZW/Deflate/PackBits; strips or tiles. |
| 값 / value | **발표 시각부터 그 픽셀에 불이 처음 닿을 때까지의 분**. **Minutes from the issue time to first fire arrival in the pixel.** |
| 이미 탐 / already burning | 값 ≤ 0 (발표 시각에 이미 불이 있거나 탄 곳). Value ≤ 0 (burning or burnt at the issue time). |
| 도달 안 함 / not reached | 예측 범위보다 큰 값, +Inf, 또는 `WFG_NOT_REACHED` 로 선언한 값. A value above the horizon, +Inf, or the value declared in `WFG_NOT_REACHED`. |
| 자료 없음 / no data | GeoTIFF NoData 또는 NaN = **계산 안 함**. 도로가 지나는 셀에 있으면 실행을 거부합니다. NoData or NaN = **not computed**; on any road cell the run is refused. |
| 좌표계 / CRS | GeoKey 의 EPSG 코드 필수. EPSG:5179 (도로 격자와 같음) 권장; 5186·4326 등은 pyproj 로 변환. An EPSG code in the GeoKeys is required; EPSG:5179 preferred, others via pyproj. |
| 범위 / extent | 지역 도로가 지나는 모든 375 m 셀을 덮어야 함 (의성·안동 x 1,093,875–1,121,250 · y 1,815,750–1,840,125; 영덕 x 1,147,500–1,174,125 · y 1,815,750–1,840,875, EPSG:5179). Must cover every road cell of the region. |
| 해상도 / resolution | 제한 없음. 375 m 도로 셀마다 겹치는 픽셀 중 **가장 이른 도달**을 씁니다. Any; each 375 m road cell takes the **earliest** arrival among the pixels it overlaps. |
| 발표 시각 / issue time | 명령줄 `--issue-time` (시간대 포함, 예 `2025-03-25T18:00+09:00`). 메타데이터 `WFG_ISSUE_TIME` 이 있으면 같아야 함. Command line, with zone; must equal `WFG_ISSUE_TIME` if present. |
| 예측 범위 / horizon | 메타데이터 `WFG_HORIZON_MIN` 또는 `--horizon-min`. 8시간 이상이어야 도달 없는 마을의 단계를 판단. Metadata or command line; 8 h or more to stage villages the fire does not reach. |
| 시나리오 / scenarios | 하나의 도달 시각만. 앙상블이면 내보내는 쪽이 줄여야 함 (예: 구성원 중 가장 이른 값). One arrival time per pixel; an ensemble must be reduced by the exporter (e.g. earliest member). |

메타데이터는 GDAL_METADATA 항목 (`gdal_edit.py -mo WFG_HORIZON_MIN=480 file.tif`): `WFG_ISSUE_TIME`, `WFG_HORIZON_MIN`,
`WFG_UNITS=minutes`, `WFG_NOT_REACHED`, `WFG_SOURCE`. 기본값으로 도구는 불이 닿은 셀을 예측 범위 끝까지 계속 막힌 것으로 봅니다
(연소 후 재개통 없음; 주민용 기본값). By default the tool keeps a cell closed from arrival to the end of the horizon (no reopening
after burn-out; the residents' default). 선택 사항: 아래 "연소 후 재개통". Optional: "Reopening after burn-out" below. Example:
`examples/fire_arrival_20250325T0900Z_MEASURED_8h.tif`. 저장소 자체 패킷 (`--packet`, 1시간 범위)도 받습니다; the repository's packet is also accepted.

## 연소 후 재개통 (선택) / Reopening after burn-out (optional)

research/kcf-reopen. 기본은 꺼짐 (`settings.toml [reopen] mode = 0`). Off by default. 켜면 셀은 [닫힘 b, 재개통 r) 동안만 막히고,
r = max(b, 도달 A + 연소 시간). 연소 시간 기본 240분 (Camp Fire 2018 도로 차단 보고에서 추정; 낮게 105, 높게 465). When on, a cell is
closed on [b, r) with r = max(b, A + burn-out), burn-out 240 min by default (estimated from Camp Fire 2018 road-blocked
reports; low 105, high 465). A cell with no arrival stays closed to the horizon.

| 방식 / mode | 누구 / for whom | 무엇이 다시 열리나 / what reopens |
|---|---|---|
| `--reopen off` (기본 / default) | 주민 / residents | 없음 / nothing |
| `--reopen confirmed --reopen-confirmed FILE` | 주민 / residents | 보고 또는 차량 장치 `REOPENED` 로 확인되고, 확인 시각 u 가 A + 연소 시간 ≤ u ≤ 발표 시각인 셀만. Only cells confirmed by a report or a vehicle-unit `REOPENED` event at u with A + burn-out ≤ u ≤ the issue time |
| `--reopen responders` | 대응 인력 / responders | 도달 시각이 있는 모든 셀 / every cell with an arrival |

* **도달 A / arrival A.** `--raster` 값 그대로. 그 래스터가 이미 여유(margin)만큼 앞당겨져 있으면 재개통도 그만큼 이르므로
  `--reopen-arrival 중심도달.tif` 로 중심 도달을 따로 주십시오 (같은 형식; **음수 = 발표 전 그만큼 앞서 도달**). `--raster` 에서 값 ≤ 0 인 셀은
  나이를 모르므로 A = 0 (발표 + 연소 시간에 재개통; 실제보다 늦음). The `--raster` values, unless `--reopen-arrival` gives a
  central arrival raster (same format; **negative minutes = arrived that long before the issue time**). In `--raster` a
  value ≤ 0 has no age, so A = 0 (reopens at issue + burn-out, later than the truth). Only a negative central arrival can
  make a cell burned over at the issue time, so only then can a residents' confirmation count.
* **확인 파일 / confirmations file** (JSON, api/live.py 의 REOPENED 필드): `{"events": [{"event": "REOPENED", "lat": 36.4,
  "lon": 128.7, "utc": "2025-03-25T02:59:00Z", "source": "unit-3"}]}`; `"PASSABLE"` (도로 통행 가능 보고 / a passable report) 도 받음.
* **모르는 것 / not modelled.** 쓰러진 나무, 전선, 연기, 뒤쪽에서 타는 건물, 재발화. Fallen trees, power lines, smoke, burning
  buildings behind the front, re-ignition. 연소 시간은 한 화재(Camp Fire)의 75개 셀에서 나온 값이며, 그 화재에서도 보수적이지 않았습니다
  (차단 보고 195건 중 16건이 이미 재개통된 셀에 있음). The burn-out time comes from 75 cells of one fire, and even there 16 of
  195 road-blocked reports fell in a cell the rule had already reopened (research/kcf-reopen RESULTS.md).
* 인증서는 계속 검증됩니다: 재개통 시 출발 가능 시간대가 여러 구간일 수 있어 verifier 가 식 (E) 의 최소 고정점으로 전체 집합을 다시 계산합니다.
  Certificates still verify: with reopening a departure set can have several windows, and the verifier recomputes the
  whole set as the least fixed point of equation (E) (research/kcf-theorem THEOREM.md §2).
* `--heat`, `--fragility`, `cards` 와 함께 쓸 수 없음 (거부). Not combined with `--heat`, `--fragility` or `cards` (refused).

## 산림청 출력에 대해 모르는 것 / What is unknown about the Forest Service output

1. **형식 / form.** 픽셀별 도달 시각 래스터를 내는지, 시간별 확산 범위 폴리곤(SHP·KML)이나 그림만 내는지 모릅니다. 폴리곤이면 픽셀마다 처음
   포함되는 시간 구간의 **시작** 시각을 도달로 주면 됩니다 (변환기는 아직 없음). Unknown whether it is a per-pixel arrival raster, hourly
   perimeters, or images. Perimeters convert by giving each pixel the **start** of the first interval that contains it (no converter yet).
2. **시간 기준 / time base.** 발표 시각 기준인지 관측·자료 마감 시각 기준인지, 시간대, 갱신 주기와 지연을 모릅니다. Relative to the issue
   time or to the data cut-off; time zone; update cycle and latency.
3. **좌표계·해상도·범위 / CRS, resolution, extent** (EPSG:5186? 30 m?), and whether the whole county is computed or only around the fire.
4. **예측 범위 / horizon.** 몇 시간까지 내는지. 8시간보다 짧으면 단계(8 h / 5 h)를 끝까지 판단할 수 없습니다. How many hours; below 8 h the
   stages cannot always be told.
5. **안 탄 곳의 뜻 / meaning of unburnt pixels.** "도달 안 함"과 "계산 안 함"을 구분하는지 (구분 안 하면 이 도구는 거부합니다). Whether "not
   reached" and "not computed" are distinguished; if not, the tool refuses.
6. **현재 화선 / current fire.** 발표 시각에 이미 탄 곳이 포함되는지. Whether burnt and burning area at the issue time is included.
7. **불확실성 / uncertainty.** 단일 결정론적 실행인지 앙상블·확률인지, 그리고 정부 단계(5 h·8 h)를 같은 출력에서 정하는지. Deterministic or
   ensemble/probability, and whether the government stages are set from the same output.
8. **전달·이용 조건 / delivery and terms.** 오프라인 반출 가능 여부, 파일 이름·전달 경로, 이용 허락. Offline export, naming, channel, licence.
