# 부스 운영 안내 · Booth runbook

한국어가 먼저, 영어가 뒤에 있습니다. English follows the Korean.

## 한국어

### 하루 시작: 10분 설치 점검표

1. 전원: 멀티탭에 MacBook 충전기, iPad 충전기를 꽂습니다. iPhone은 Lightning to USB-C 케이블로 Mac에 연결합니다 (충전도 됩니다).
2. 외부 모니터를 MacBook에 연결하고 켭니다. MacBook 뚜껑은 열어 둡니다.
3. iPad를 거치대에 세우고 설정합니다: 자동 밝기, True Tone, Night Shift 끔; 밝기 약 80%; 자동 잠금 안 함.
4. iPad에서 부스 영상을 전체 화면으로 반복 재생합니다. 시팅 2에서 고른 파일입니다 (`configs/booth_local.yaml`의 `booth.hold_factor`가 2면 `_hold2.mp4`, 3이면 `_hold3.mp4`). 재생 버튼 등 조작 화면은 숨기고, 네 모서리의 흑백 무늬가 모두 보여야 합니다. 그다음 사용법 유도(Guided Access)를 켭니다.
5. iPhone: 케이스를 벗기고 삼각대에 가로로 고정합니다. iPad 화면이 사진의 약 3분의 2를 차지하고 살짝 비스듬하게 보이도록 합니다. 햇빛이 닿지 않는 곳에 두고, 잠근 상태로 둡니다.
6. 검은 천 후드를 iPad와 iPhone 위에 씌워 반사를 막습니다.
7. Mac 메뉴 막대의 비디오 메뉴(초록색 카메라 아이콘)에서 반응, 센터 스테이지, 인물 사진, 스튜디오 조명을 모두 끕니다.
8. iPhone과 Mac에서 집중 모드를 켭니다.
9. 터미널에서 명령 하나로 시작합니다:

```
bash wfglink/booth/booth.sh
```

   또는 Finder에서 `wfglink/booth/booth.command`를 더블 클릭합니다.
10. 확인: 외부 모니터에 영상과 주황색 불티 궤적이 보이고, 아래 상태 줄에 "실시간"이 나오며, 화면에 띠가 없습니다. L을 한 번 눌러 언어가 바뀌는지 봅니다.

### 미리 한 번 맞춰 두는 설정

- 연속성 카메라는 케이블로 연결해서 씁니다. iPhone과 Mac 모두 Wi-Fi와 Bluetooth는 켜 두되, 어떤 네트워크에도 접속하지 않습니다.
- iPhone과 Mac은 같은 Apple 계정입니다. iPhone에서 "이 컴퓨터를 신뢰"를 승인합니다.
- iPhone의 개인용 핫스팟은 끕니다.
- iPhone과 Mac 모두 집중 모드를 켭니다.
- iPhone, iPad, Mac의 자동 업데이트를 끕니다.
- iPad: 자동 밝기, True Tone, Night Shift 끔; 자동 잠금 안 함; 사용법 유도로 반복 재생 화면을 고정합니다.
- Mac 비디오 메뉴의 효과는 모두 끕니다.
- iPhone 케이스는 벗기고, 햇빛을 피합니다.
- 검은 천 후드를 씌웁니다.

### 키

| 키 | 하는 일 |
|---|---|
| L | 한국어와 영어 전환 |
| I | 측정의 한계 카드 열기와 닫기 |
| T | 불티 궤적 보이기와 숨기기 |
| F | 바람 추정(불티 기반) 화살표 보이기와 숨기기 |
| G | 게이트 선 보이기와 숨기기 |
| Esc 두 번 | 종료 (2초 안에 두 번) |

### 화면에 나오는 띠와 표시

| 표시 | 뜻 | 할 일 |
|---|---|---|
| 녹화 재생 · 실시간 아님 (REPLAY · not live) | 카메라가 없어 준비된 영상을 직접 재생하고 있습니다. 숫자는 따로 셉니다. | 카메라가 돌아오면 5초 동안 정상인지 확인한 뒤 자동으로 실시간으로 돌아갑니다. 아래 "카메라가 끊겼을 때"를 봅니다. |
| 합성 영상 · 실측 아님 (SYNTHETIC · not measured) | 카메라도 녹화 영상도 없어 합성 데모를 보여 줍니다. 측정값이 아닙니다. | 카메라 케이블과 iPad를 확인합니다. |
| 카메라 재연결 중 (Reconnecting camera) | 카메라가 잠깐 끊겨 다시 연결하는 중입니다. | 몇 초 기다립니다. |
| iPad 정지 (iPad paused) | iPad 재생이 멈췄습니다. | iPad에서 재생을 다시 누릅니다. 띠가 없어도 그림이 멈추고 숫자가 바뀌지 않으면 같은 조치를 합니다. |
| 0.5× 재생 또는 0.33× 재생 | 부스 영상은 느리게 재생됩니다. 정상입니다. | 없음. 속도는 원본 영상의 시간으로 계산합니다. |

### 문제가 생겼을 때

- 카메라가 끊겼을 때 (케이블이 빠짐, iPhone이 꺼짐): 앱이 자동으로 USB 웹캠으로, 없으면 녹화 재생으로 넘어갑니다. 케이블을 다시 꽂으면 카메라가 5초 동안 정상인지 확인한 뒤 iPhone으로 자동 복귀합니다 (보통 15초 이내). 30초가 지나도 돌아오지 않으면: 케이블 양쪽 확인, iPhone이 잠긴 채 가로로 고정되어 있는지 확인, 그래도 안 되면 다시 시작합니다.
- 앱이 꺼지거나 멈췄을 때: 감시 스크립트(booth.sh)가 자동으로 다시 시작합니다. 빨리 연달아 꺼지면 2초에서 60초까지 간격을 늘려 가며 다시 시작합니다. 화면이 멈춘 채 30초 넘게 기록이 없으면 멈춤으로 보고 다시 시작합니다.
- 직접 다시 시작하는 법: Esc를 두 번 눌러 끈 뒤, 터미널에서 `bash wfglink/booth/booth.sh`를 다시 실행합니다. 터미널 창을 닫았다면 `booth/booth.command`를 더블 클릭합니다.
- 화면이 노트북 화면에 뜰 때: Esc 두 번, 모니터 연결을 확인하고 다시 실행합니다. 계속 그러면 `bash wfglink/booth/booth.sh --screen external`로 실행합니다.
- 기록 파일: `wfglink/logs/booth.log` (감시 스크립트와 앱의 기록), `wfglink/logs/heartbeat.json` (2초마다 다시 씀: 초당 프레임, 소스, 메모리). 문제를 알릴 때 이 두 파일을 보내 주세요.
- 하루 끝: Esc를 두 번 누릅니다. 깨끗하게 끝나면 감시 스크립트도 함께 끝납니다.

## English

### Start of the day: 10 minute setup checklist

1. Power: MacBook charger and iPad charger into the power strip. The iPhone connects to the Mac with the Lightning to USB-C cable (which also charges it).
2. Connect the external monitor to the MacBook and turn it on. Keep the MacBook lid open.
3. iPad on its stand: Auto-Brightness, True Tone and Night Shift off; brightness about 80 percent; Auto-Lock Never.
4. On the iPad, play the booth clip full screen on repeat. It is the file chosen in sitting 2 (`_hold2.mp4` when `booth.hold_factor` in `configs/booth_local.yaml` is 2, `_hold3.mp4` when it is 3). Hide the player controls; all four black and white corner patterns must be visible. Then turn on Guided Access.
5. iPhone: case off, on the tripod in landscape, the iPad filling about two thirds of the picture at a slight angle. Out of the sun, and locked.
6. Put the black cloth hood over the iPad and the iPhone against reflections.
7. Mac menu bar, Video menu (the green camera icon): Reactions, Center Stage, Portrait and Studio Light all off.
8. Turn on Focus on the iPhone and the Mac.
9. Start with the one command in Terminal:

```
bash wfglink/booth/booth.sh
```

   or double-click `wfglink/booth/booth.command` in Finder.
10. Check: the external monitor shows the video with orange ember tracks, the status line says "Live", and there is no band across the picture. Press L once and see the language change.

### Settings to make once, before the day

- Continuity Camera over the cable. Wi-Fi and Bluetooth on for the iPhone and the Mac, but joined to no network.
- The iPhone and the Mac on the same Apple Account; Trust This Computer accepted on the iPhone.
- Personal Hotspot off on the iPhone.
- Focus on for the iPhone and the Mac.
- Automatic updates off on the iPhone, the iPad and the Mac.
- iPad: Auto-Brightness, True Tone and Night Shift off; Auto-Lock Never; Guided Access holding the looping player.
- Every effect in the Mac's Video menu off.
- iPhone case off, out of the sun.
- The black cloth hood.

### Keys

| Key | What it does |
|---|---|
| L | Korean or English |
| I | Limits card on or off |
| T | Ember tracks on or off |
| F | Ember-derived wind arrows on or off |
| G | Gate line on or off |
| Esc twice | Quit (twice within 2 s) |

### Bands and labels on the screen

| On screen | Meaning | What to do |
|---|---|---|
| REPLAY · not live (녹화 재생 · 실시간 아님) | No camera works, so the prepared clip plays directly. Its counts are kept separately. | When a camera is back and stays healthy for 5 s, the booth returns to live by itself. See "Camera lost" below. |
| SYNTHETIC · not measured (합성 영상 · 실측 아님) | No camera and no clip: a synthetic demo, not a measurement. | Check the camera cable and the iPad. |
| Reconnecting camera (카메라 재연결 중) | The camera dropped out for a moment and is being reopened. | Wait a few seconds. |
| iPad paused (iPad 정지) | The iPad stopped playing. | Press play on the iPad. Do the same if the picture stands still and the numbers stop changing without this band. |
| 0.5× playback or 0.33× playback | The booth clip plays slowed down. This is normal. | Nothing. Speeds are computed in the original clip's time. |

### When something goes wrong

- Camera lost (cable out, iPhone off): the app falls back by itself to the USB webcam, or to the replay with its band when there is no webcam. When the cable is back, the camera must stay healthy for 5 s and then the booth switches back to the iPhone by itself (usually within 15 s). If it is not back after 30 s: check the cable at both ends, check that the iPhone is locked and in landscape on the tripod, then restart.
- The app closes or freezes: the supervisor (booth.sh) restarts it by itself, waiting 2 s, then longer up to 60 s if it keeps failing quickly. A picture frozen with no heartbeat for 30 s counts as a hang and is restarted.
- How to restart by hand: press Esc twice, then run `bash wfglink/booth/booth.sh` again in Terminal. If the Terminal window was closed, double-click `booth/booth.command`.
- The picture opens on the laptop screen: Esc twice, check the monitor cable, start again. If it keeps happening, start with `bash wfglink/booth/booth.sh --screen external`.
- Logs: `wfglink/logs/booth.log` (supervisor and app output) and `wfglink/logs/heartbeat.json` (rewritten every 2 s: frames per second, source, memory). Send both when you report a problem.
- End of the day: press Esc twice. A clean exit stops the supervisor too.
