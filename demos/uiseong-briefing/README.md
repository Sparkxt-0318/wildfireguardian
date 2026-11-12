# 의성 산불 변화 지도

[데모 열기](index.html) · [13:22 화면 미리보기](preview.png)

이 폴더를 내려받아 `index.html`을 브라우저에서 여세요. 지도, 예측, 관측 자료를 함께 담아 설치나 네트워크 연결 없이 실행됩니다. GitHub의 파일 보기 화면에서는 HTML 소스가 표시됩니다.

## 1분 시연

1. **3월 24일 복귀 동선 보기**로 12:44 위성 관측을 엽니다. **현재 브리핑 검토 완료**를 누르면 이 관측이 비교 기준이 되고 검토 당시의 문안이 기록됩니다.
2. **다음**을 눌러 13:07 관측을 봅니다. 지도 전체에 새로 표시된 도로 구간은 187개입니다. 가상의 복귀 동선에서는 신감옥산로의 17개 구간이 새로 표시됩니다. 이들은 떨어진 두 곳에 모여 있습니다. **복귀 동선 확인**에서 한 곳을 선택하면 해당 구간의 양 끝이 A, B로 표시됩니다.
3. **관측 15분 뒤 보기**를 누릅니다. 훈련 기준 시각은 13:22, 최신 수록 관측은 13:07, 관측 경과는 15분입니다. 당시 현장 수신 시각은 알려져 있지 않습니다. **무전 전 브리핑**에서 문안을 고쳐 읽고, **문안에 연결된 구간 보기**로 지도에서 같은 위치를 짚으세요. **한 장으로 인쇄**하면 현재 지도, 시각, 선택 및 검토 문안이 함께 인쇄됩니다.
4. **예측이 있는 시점 보기**를 누르면 18:00 기준 시각으로 이동합니다. 같은 지도에서 다음 한 시간의 연구 예측을 확인합니다. 19:00에 이 예측의 유효기간이 끝납니다. 13:22 장면에는 유효한 예측이 없습니다.

'검토 완료'는 이 브라우저 세션의 비교 기준입니다. 담당자가 새 기준을 정할 때까지 이후 관측은 그 기준과 비교합니다. **직전 관측과 비교**를 누르면 바로 앞 관측을 기준으로 돌아갑니다. 이전 시점으로 되감으면 미래의 검토 기록은 당시 비교에서 제외됩니다. 지도에서 선택한 구간과 문안이 연결되며 텍스트 편집만으로 연결 위치가 바뀌지는 않습니다. 이 화면은 현장 관제·송신 시스템에 연결되지 않습니다.

## 무엇을 볼 수 있나요?

- **관측**은 위성 열 이상 픽셀의 중심입니다. 이전 열점이 사라졌다고 진압이나 재개통이 확인되는 것은 아닙니다. 관측 간격은 불규칙하며 자동 재생은 이 간격을 압축합니다.
- **예측**은 훈련 기준 시각에 유효한 연구 모형의 다음 한 시간 새 연소 확률입니다. 예측 기준, 유효기간, 이미 탄 셀 및 자료 부족을 구분합니다. 과거 연구 모형의 출력이 당시 지휘부에 전달됐는지는 확인할 수 없습니다.
- **도로 표시**는 지도 창 안에 있는 열점 중심과 도로 선분 사이의 거리가 375 m 이하라는 뜻입니다. 이 거리는 훈련을 위한 기준입니다. 화선, 화재 진행 방향, 도로 통제나 현장 차량의 통행 가능 여부를 관측한 값은 아닙니다.
- **복귀 동선**은 연구 도로망의 의성·안동 FL2 장거리 가상 사례입니다. 123개 구간에서 일방통행 태그가 없어 연구 도로망은 양방향 통행을 가정했습니다. 실제 소방대의 진입·철수 기록은 사용하지 않습니다. 명칭이 없는 길에는 지도 내 구간 번호를 표시합니다.

## Data and reuse

The study window is 9.75 km square in EPSG:5179. The bundled data contain 476 nominal/high-confidence thermal detections from Suomi NPP and NOAA-20 across 21 acquisition minutes, March 23–26, 2025 KST. Records were selected by time, location and product. The historical graph contains 2,453 physical road segments, using the requested March 21, 2025 23:59:59 UTC OpenStreetMap snapshot. The data come from the existing retrospective Uiseong replay. This PR changes the presentation and comparison logic.

[Suomi NPP source CSV](https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/2025/viirs-snpp_2025_Republic_of_Korea.csv) · [NOAA-20 source CSV](https://firms.modaps.eosdis.nasa.gov/data/country/viirs-jpss1/2025/viirs-jpss1_2025_Republic_of_Korea.csv) · [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/download/) · Road database © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).

The earlier source comparison reproduced all selected rows in the NASA country-year files (227 S-NPP, 249 NOAA-20). The three regional c651 forecast exports retain their own origin, end, native masks and class colours. Their 702 rendered tiles per window total 2,106 classified tiles. See [input fingerprints](sources.json). Physical field conditions and incident-time delivery are unknown. Check these sources and boundaries separately for any additional fire.

## Tests

With Node 20 or later, run inside this directory:

```sh
node --test tests/core.test.cjs tests/data.test.cjs
```

For end-to-end tests, make Playwright accessible to Node and install its Chromium in your testing environment. Run `node tests/browser.cjs`. Set `WFG_CHROME_CHANNEL=chrome` to use locally installed Google Chrome or `WFG_CHROMIUM` to use a specific executable. The test opens the checked-in files with networking disabled. It checks the March 24 timeline, reviewed versus previous comparisons, both disjoint stretches, synchronized map and draft, 15-minute age, forecast validity, mobile layout and A4 output.

The demo is contained in this directory and runs independently of the public planner or routing service.
