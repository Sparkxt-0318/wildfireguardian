# 부스 운영 안내 · Booth runbook

한국어가 먼저, 영어가 뒤에 있습니다. English follows the Korean.

명령과 경로는 모두 두 번째 점검(sitting 2) 때 쓴 폴더 `~/wfglink-run/wfglink` 기준입니다. All commands and paths refer to the folder used in sitting 2, `~/wfglink-run/wfglink`.

## 한국어

### 하루 시작: 10분 설치 점검표

1. 전원: MacBook 충전기와 iPad 충전기를 멀티탭에 꽂습니다. iPhone은 USB-C-Lightning 케이블로 Mac에 연결합니다(충전도 됩니다).
2. 외부 모니터를 MacBook에 연결하고 켭니다. MacBook 뚜껑은 열어 둡니다.
3. iPad를 거치대에 세우고 설정합니다. 자동 밝기, True Tone, Night Shift는 끄고, 밝기는 80% 정도로, 자동 잠금은 '안 함'으로 둡니다.
4. iPad의 VLC에서 부스 영상을 전체 화면으로 틀고, 반복 버튼을 눌러 이 영상 하나만 계속 반복되게 합니다. 두 번째 점검에서 고른 파일입니다. `configs/booth_local.yaml`의 `booth.hold_factor`가 2이면 `_hold2.mp4`, 3이면 `_hold3.mp4`입니다. 재생 버튼 같은 조작 화면은 숨기고, 네 모서리의 흑백 무늬가 모두 보여야 합니다. 그다음 사용법 유도(Guided Access)를 켭니다.
5. iPhone: 케이스를 벗기고 삼각대에 가로로 고정합니다. iPhone 카메라 화면에서 iPad 화면이 3분의 2쯤을 차지하고, 정면에서 살짝 비껴 보이게 둡니다. 햇빛이 닿지 않게 하고, iPhone은 잠근 상태로 둡니다.
6. 검은 천을 iPad와 iPhone 위에 덮어 반사를 막습니다.
7. iPhone과 Mac에서 집중 모드를 켭니다.
8. 터미널에서 명령 하나로 부스를 시작합니다.

```
bash ~/wfglink-run/wfglink/booth/booth.sh
```

   또는 Finder에서 홈 폴더의 `wfglink-run/wfglink/booth` 폴더를 열고 `booth.command`를 더블 클릭합니다.
9. 부스가 켜지면 Mac 메뉴 막대의 초록색 카메라 아이콘(비디오 효과)을 눌러 반응, 센터 스테이지, 인물 사진, 스튜디오 조명이 모두 꺼져 있는지 확인합니다. 이 메뉴는 앱이 카메라를 쓰는 동안에만 나타납니다.
10. 확인: 외부 모니터에 영상과 주황색 불티 궤적이 보이고, 아래 상태 줄에 '실시간'이 나오며, 화면을 가로지르는 띠가 없어야 합니다. L을 한 번 눌러 언어가 바뀌는지 봅니다.

### 미리 한 번 해 두는 설정

- 연속성 카메라는 케이블로 연결해서 씁니다. iPhone과 Mac 모두 Wi-Fi와 Bluetooth는 켜 두되, 어떤 네트워크에도 접속하지 않습니다.
- iPhone과 Mac은 같은 Apple 계정으로 로그인합니다. iPhone에 '이 컴퓨터를 신뢰하겠습니까?'가 뜨면 '신뢰'를 누릅니다.
- iPhone의 개인용 핫스팟은 끕니다.
- iPhone과 Mac 모두 집중 모드를 켭니다.
- iPhone, iPad, Mac의 자동 업데이트를 끕니다.
- Mac: 시스템 설정의 잠금 화면에서 화면 보호기 시작과 디스플레이 끄기를 모두 '안 함'으로 둡니다.
- iPad: 자동 밝기, True Tone, Night Shift는 끄고, 자동 잠금은 '안 함'으로 둡니다. 사용법 유도로 VLC 반복 재생 화면을 고정합니다.
- Mac의 비디오 효과(메뉴 막대의 초록색 카메라 아이콘)는 모두 끕니다.
- iPhone 케이스는 벗기고, 햇빛을 피합니다.
- 검은 천을 덮습니다.

### 키

| 키 | 하는 일 |
|---|---|
| L | 한국어와 영어 바꾸기 |
| I | 측정의 한계 카드 켜기/끄기 |
| T | 불티 궤적 켜기/끄기 |
| F | 바람 추정(불티 기반) 화살표 켜기/끄기 |
| G | 게이트 선 켜기/끄기 |
| Esc 두 번 | 종료(2초 안에 두 번) |

### 화면에 나오는 띠와 표시

| 표시 | 뜻 | 할 일 |
|---|---|---|
| 녹화 재생 · 실시간 아님 (REPLAY · not live) | 카메라가 없어서 준비된 영상을 직접 틀고 있습니다. 숫자는 따로 셉니다. | 카메라가 다시 5초 동안 정상이면 저절로 실시간으로 돌아갑니다. 아래 '카메라가 끊겼을 때'를 봅니다. |
| 합성 영상 · 실측 아님 (SYNTHETIC · not measured) | 카메라도 녹화 영상도 없어서 합성 데모를 보여 줍니다. 측정값이 아닙니다. | 카메라 케이블과 iPad를 확인합니다. |
| 카메라 재연결 중 (Reconnecting camera) | 카메라가 잠깐 끊겨 다시 연결하는 중입니다. | 몇 초 기다립니다. |
| iPad 정지 (iPad paused) | iPad 재생이 멈췄습니다. | iPad에서 다시 재생합니다. 띠가 없어도 그림이 멈추고 숫자가 바뀌지 않으면 똑같이 합니다. |
| 0.5× 재생, 0.33× 재생 | 부스 영상은 느리게 재생됩니다. 정상입니다. | 할 일 없음. 속도는 원래 영상의 시간으로 계산합니다. |

### 문제가 생겼을 때

- 카메라가 끊겼을 때(케이블이 빠졌거나 iPhone이 꺼졌을 때): 앱이 알아서 USB 웹캠으로, 웹캠이 없으면 녹화 재생으로 넘어갑니다. 케이블을 다시 꽂으면 카메라가 5초 동안 정상인지 확인한 뒤 iPhone으로 저절로 돌아옵니다(보통 20초 안에). 30초가 지나도 돌아오지 않으면 케이블 양쪽을 확인하고, iPhone이 잠긴 채 가로로 고정되어 있는지 봅니다. 그래도 안 되면 부스를 다시 시작합니다.
- 앱이 꺼지거나 멈췄을 때: 감시 스크립트(booth.sh)가 앱을 저절로 다시 시작합니다. 짧은 시간에 계속 꺼지면 다시 시작하기 전에 기다리는 시간을 2초에서 60초까지 늘립니다. 앱의 상태 기록(heartbeat)이 30초 넘게 멈추거나, 앱이 90초 넘게 새 프레임을 처리하지 못하면 멈춘 것으로 보고 다시 시작합니다.
- 직접 다시 시작하려면: Esc를 두 번 눌러 끈 뒤, 터미널에서 `bash ~/wfglink-run/wfglink/booth/booth.sh`를 다시 실행합니다. 터미널 창을 닫았다면 Finder에서 `booth.command`를 더블 클릭합니다.
- 그림이 노트북 화면에 뜰 때: Esc를 두 번 누르고, 모니터 케이블을 확인한 뒤 다시 시작합니다. 계속 그러면 `bash ~/wfglink-run/wfglink/booth/booth.sh --screen external`로 시작합니다.
- 기록 파일: `~/wfglink-run/wfglink/logs/booth.log`(감시 스크립트와 앱의 기록), `~/wfglink-run/wfglink/logs/heartbeat.json`(2초마다 새로 씀: 초당 프레임 수, 소스, 메모리). 문제를 알릴 때 이 두 파일을 보내 주세요.
- 하루 끝: Esc를 두 번 누릅니다. 정상적으로 끝나면 감시 스크립트도 함께 끝납니다.

## English

### Start of the day: 10 minute setup checklist

1. Power: MacBook charger and iPad charger into the power strip. The iPhone connects to the Mac with the Lightning to USB-C cable (which also charges it).
2. Connect the external monitor to the MacBook and turn it on. Keep the MacBook lid open.
3. iPad on its stand: Auto-Brightness, True Tone and Night Shift off; brightness about 80 percent; Auto-Lock Never.
4. In VLC on the iPad, play the booth clip full screen and set the repeat button so this one video repeats. It is the file chosen in sitting 2 (`_hold2.mp4` when `booth.hold_factor` in `configs/booth_local.yaml` is 2, `_hold3.mp4` when it is 3). Hide the player controls; all four black and white corner patterns must be visible. Then turn on Guided Access.
5. iPhone: case off, on the tripod in landscape, the iPad filling about two thirds of the iPhone's picture at a slight angle. Out of the sun, and locked.
6. Put the black cloth hood over the iPad and the iPhone against reflections.
7. Turn on Focus on the iPhone and the Mac.
8. Start the booth with the one command in Terminal:

```
bash ~/wfglink-run/wfglink/booth/booth.sh
```

   or open the `wfglink-run/wfglink/booth` folder in your home folder in Finder and double-click `booth.command`.
9. Once the booth is running, click the green camera icon in the Mac menu bar (Video) and check that Reactions, Center Stage, Portrait and Studio Light are all off. That menu only appears while an app uses the camera.
10. Check: the external monitor shows the video with orange ember tracks, the status line says "Live", and there is no band across the picture. Press L once and see the language change.

### Settings to make once, before the day

- Continuity Camera over the cable. Wi-Fi and Bluetooth on for the iPhone and the Mac, but joined to no network.
- The iPhone and the Mac signed in to the same Apple Account; when the iPhone asks "Trust This Computer?", tap Trust.
- Personal Hotspot off on the iPhone.
- Focus on for the iPhone and the Mac.
- Automatic updates off on the iPhone, the iPad and the Mac.
- Mac: System Settings, Lock Screen: start Screen Saver and turn display off both set to Never.
- iPad: Auto-Brightness, True Tone and Night Shift off; Auto-Lock Never; Guided Access holding the looping VLC player.
- Every effect in the Mac's Video menu (the green camera icon in the menu bar) off.
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

- Camera lost (cable out, iPhone off): the app falls back by itself to the USB webcam, or to the replay with its band when there is no webcam. When the cable is back, the camera must stay healthy for 5 s and then the booth switches back to the iPhone by itself (usually within 20 s). If it is not back after 30 s: check the cable at both ends, check that the iPhone is locked and in landscape on the tripod, then restart.
- The app closes or freezes: the supervisor (booth.sh) restarts it by itself, waiting 2 s, then longer up to 60 s if it keeps failing quickly. A heartbeat older than 30 s, or no new frame processed for 90 s, counts as a hang and the app is restarted.
- How to restart by hand: press Esc twice, then run `bash ~/wfglink-run/wfglink/booth/booth.sh` again in Terminal. If the Terminal window was closed, double-click `booth.command` in Finder.
- The picture opens on the laptop screen: Esc twice, check the monitor cable, start again. If it keeps happening, start with `bash ~/wfglink-run/wfglink/booth/booth.sh --screen external`.
- Logs: `~/wfglink-run/wfglink/logs/booth.log` (supervisor and app output) and `~/wfglink-run/wfglink/logs/heartbeat.json` (rewritten every 2 s: frames per second, source, memory). Send both when you report a problem.
- End of the day: press Esc twice. A clean exit stops the supervisor too.
