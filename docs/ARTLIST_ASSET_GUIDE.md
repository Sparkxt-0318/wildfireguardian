# Artlist 미디어 슬롯 안내

본선 화면(`web/finals.html`)은 `web/demo-media/` 아래의 로컬 파일 슬롯을
사용합니다. **모든 슬롯은 선택 사항입니다.** 파일이 없으면 화면은 지형 기반
정적 인트로와 무음으로 자동 대체되며, 기능 저하는 없습니다. 화면은 어떤
경우에도 네트워크에 접근하지 않습니다(오프라인 게이트로 강제).

파일을 바꾸려면 같은 이름으로 덮어쓰고 브라우저를 새로고침하면 됩니다.
빌드를 다시 할 필요는 없습니다.

## 슬롯 목록

| 파일 | 용도 | 없을 때 |
|---|---|---|
| `intro-forest-loop.mp4` | 인트로 배경 루프 (6~15초, 음소거 재생) | 지형 음영 정지 화면 + 느린 팬 |
| `intro-poster.webp` | 영상 로딩 전 포스터 | 없음(배경 유지) |
| `ambient-documentary.mp3` | 소리 켬 상태의 극저음량 앰비언트 (루프) | 무음 |
| `ui-soft-click.wav` | 탭·지역 전환 클릭 | 무음 |
| `ui-map-ping.wav` | 1막 화점 표시 | 무음 |
| `ui-route-confirm.wav` | 경로 표시·선택 확인 | 무음 |
| `ui-closure-soft.wav` | 도로 구간 통행 불가 전환 (재생 중에만) | 무음 |
| `ui-transition.wav` | 안내 시연 막 전환 | 무음 |

현재 `intro-forest-loop.mp4` 와 `intro-poster.webp` 는 Artlist AI 생성
(Artlist Original Cinematic + Kling 1.6) 산출물이 들어 있습니다. 라이선스
푸티지로 교체해도 되고 그대로 두어도 됩니다.

## Artlist 검색어 제안

인트로 푸티지 (분위기 전용 · 실제 화재 영상이 아니어야 함):

- "cinematic aerial mountain forest haze"
- "forest aerial smoke atmosphere"
- "documentary mountain forest drone"
- "forest morning haze aerial"
- "satellite landscape cinematic"

피해자·불길이 식별되는 재난 장면은 쓰지 않습니다. 푸티지는 분위기이며,
실제 한국 산불 기록 영상으로 오인될 표현을 피합니다.

음악 (거의 들리지 않을 만큼 절제):

- "minimal cinematic technology"
- "documentary ambient tension"
- "scientific documentary"
- "subtle pulse ambient"
- "restrained cinematic suspense"

피할 것: 트레일러 음악, 웅장한 드럼, 영웅적 오케스트라, 호러, 감상적 피아노,
공격적 일렉트로닉.

UI 사운드 (각 0.2~0.8초, 아주 작게):

- "soft digital interface" · "minimal UI click"
- "subtle notification" · "soft map ping"
- "data scan" · "radio click"
- "minimal transition whoosh" · "low soft impact"

아케이드풍 효과음·사이렌·게임화 사운드는 피합니다. 전시장 소음 속에서
소리가 들리지 않아도 시연이 성립해야 하며, 실제로 그렇게 설계되어 있습니다
(기본값은 소리 꺼짐).

## 기술 요건

- 영상: H.264 mp4, 1080p 이하 권장, 15초 이하, 음성 트랙 불필요(음소거 재생).
- 포스터: webp 또는 png·jpg 를 `intro-poster.webp` 이름으로.
- 오디오: wav 또는 mp3. 슬롯 이름은 위 표 그대로.
- 원격 URL·CDN 참조는 어떤 형태로도 추가하지 마십시오. `make finals` 의
  오프라인 게이트가 빌드를 거부합니다.
