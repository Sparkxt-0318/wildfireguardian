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
`WFG_UNITS=minutes`, `WFG_NOT_REACHED`, `WFG_SOURCE`. 도구는 불이 닿은 셀을 예측 범위 끝까지 계속 막힌 것으로 봅니다 (연소 후 재개통 없음).
The tool keeps a cell closed from arrival to the end of the horizon (no reopening after burn-out). Example:
`examples/fire_arrival_20250325T0900Z_MEASURED_8h.tif`. 저장소 자체 패킷 (`--packet`, 1시간 범위)도 받습니다; the repository's packet is also accepted.

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
