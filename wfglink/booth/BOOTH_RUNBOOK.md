# 부스 운영 안내 · Booth runbook

한국어가 먼저, 영어가 뒤에 있습니다. English follows the Korean.

부스는 승인된 영상 파일을 실시간으로 재생하면서 그 자리에서 분석합니다. 카메라는 쓰지 않습니다. The booth plays approved clip files in real time and analyses them as they play. No camera is used.

명령과 경로는 모두 `~/wfglink-run/wfglink` 폴더 기준입니다. All commands and paths refer to the folder `~/wfglink-run/wfglink`.

## 한국어

### 하루 시작: 10분 설치 점검표

1. 전원: MacBook 충전기를 멀티탭에 꽂고 MacBook에 연결합니다. 뚜껑은 열어 둡니다.
2. 외부 모니터가 있으면 MacBook에 연결하고 켭니다. 없으면 부스 화면은 MacBook 화면에 나옵니다.
3. 블랙박스를 거치대에 올려 화면 옆에 두고, 'This is the sensor' A5 안내판을 그 앞에 세웁니다. 측정의 한계 A5 안내판은 화면 옆에 둡니다. 안내판 파일은 `booth/placards/`에 있습니다.
4. Mac에서 집중 모드를 켭니다.
5. 터미널에서 명령 하나로 부스를 시작합니다.

```
cd ~/wfglink-run/wfglink
./booth/booth.sh
```

   또는 Finder에서 홈 폴더의 `wfglink-run/wfglink/booth` 폴더를 열고 `booth.command`를 더블 클릭합니다.
6. 확인: 몇 초 안에 외부 모니터(없으면 MacBook 화면)에 전체 화면이 뜨고, 영상 위에 주황색 불티 궤적이 보이며, 아래 상태 줄에 영상 이름과 출처가 나옵니다. 숫자는 영상마다 몇 초 뒤에 나타납니다. L을 한 번 눌러 언어가 바뀌는지 보고, 한 번 더 눌러 되돌립니다.

### 미리 한 번 해 두는 설정

- 시스템 설정 > 잠금 화면: '비활성 상태일 때 화면 보호기 시작'과 '전원 어댑터 사용 시 비활성 상태일 때 디스플레이 끄기'를 모두 '안 함'으로 둡니다. (부스가 켜져 있는 동안에는 `booth.sh`가 Mac을 깨어 있게 합니다.)
- 시스템 설정 > 디스플레이: 외부 모니터는 '미러링'이 아니라 '확장'으로 둡니다. 부스가 외부 모니터를 스스로 고릅니다.
- 집중 모드를 켜고, 자동 업데이트를 끕니다.
- 승인된 영상이 `data/raw`에 있는지 확인합니다(`ls data/raw`). 없는 영상은 건너뜁니다.
- 안내판 두 장을 A5로 인쇄합니다(실제 크기, 100%).

### 키

| 키 | 하는 일 |
|---|---|
| L | 한국어와 영어 바꾸기 |
| T | 불티 궤적 켜기/끄기 |
| F | 바람 추정(불티 기반) 화살표 켜기/끄기 |
| G | 게이트 선 켜기/끄기 |
| Space | 일시정지(재생과 분석이 함께 멈춤), 다시 누르면 계속 |
| I | 측정의 한계 카드 켜기/끄기 |
| Esc, 다시 Esc | 종료. 첫 Esc 뒤에 확인 문구가 나오고, 몇 초 안에 한 번 더 누르면 끝납니다 |

### 모니터 연결

- 부스는 외부 모니터가 연결되어 있으면 그 화면에, 없으면 MacBook 화면에 전체 화면으로 뜹니다.
- 부스가 켜져 있을 때 모니터 케이블을 빼면 부스가 MacBook 화면으로 옮겨 가고, 다시 꽂으면 외부 모니터로 돌아갑니다. 다시 시작할 필요가 없습니다.
- 특정 화면에 고정하려면: Esc 두 번으로 끈 뒤 `./booth/booth.sh --screen external`, 또는 `python -m wfglink doctor`의 screens 줄에 나온 화면 이름으로 `--screen 이름`을 붙여 시작합니다.

### 화면에 나오는 표시

| 표시 | 뜻 | 할 일 |
|---|---|---|
| 녹화 영상을 실시간 분석 중 · Recorded clip, analysed live | 정상입니다. 승인된 영상을 재생하며 분석하고 있습니다. | 없음 |
| 측정 준비 중 · Starting measurement | 영상이 막 시작되었습니다. 배경을 익히는 몇 초 동안 숫자가 나오지 않습니다. | 없음 |
| 합성 영상 · 실측 아님 · Synthetic video · not measured | 재생할 수 있는 영상이 없어 합성 영상을 보여 줍니다. 측정값이 아닙니다. | 아래 '합성 영상만 나올 때'를 봅니다. |
| 일시정지 · Paused | Space가 눌려 멈췄습니다. | Space를 누릅니다. |
| Esc를 한 번 더 누르면 종료합니다 · Press Esc again to quit | Esc가 한 번 눌렸습니다. | 끄려면 Esc를 한 번 더, 아니면 그냥 둡니다. |
| 추정치 · Estimate, 보정 안 됨 (px) · Uncalibrated (px) | 항상 붙는 작은 표시입니다. 값의 성격을 알려 줍니다. | 없음 |

### 문제가 생겼을 때

- 화면이 멈췄을 때(그림이 서 있고 숫자가 바뀌지 않을 때): '일시정지'가 보이면 Space를 누릅니다. 그렇지 않으면 기다립니다. 감시 스크립트(`booth.sh`)는 앱의 상태 기록(heartbeat)이 30초 넘게 멈추거나, 90초 넘게 새 프레임을 분석하지 못하면 멈춘 것으로 보고 앱을 다시 시작합니다(대개 2분 안). 그래도 그대로면 Esc 두 번으로 끄고 다시 시작합니다.
- 앱이 다시 시작되었을 때(화면이 잠깐 사라졌다가 다시 전체 화면으로 뜰 때): 정상적인 복구입니다. 숫자는 처음부터 다시 셉니다. 짧은 시간에 계속 꺼지면 다시 시작하기 전에 기다리는 시간을 2초에서 60초까지 늘립니다. 자주 반복되면 `logs/booth.log`를 Claude에게 보냅니다.
- 합성 영상만 나올 때: 영상 파일이 `data/raw`에 없습니다. Esc 두 번으로 끄고 다음을 실행한 뒤 다시 시작합니다.

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
python scripts/fetch_clips.py
```

- 그림이 노트북 화면에 뜰 때: 모니터 케이블을 확인합니다. 꽂으면 부스가 저절로 옮겨 갑니다. 그래도 안 되면 위의 '모니터 연결'처럼 `--screen external`로 시작합니다.
- 터미널 창을 닫았을 때: 부스도 함께 꺼집니다. Finder에서 `booth.command`를 더블 클릭해 다시 시작합니다.
- 기록 파일: `logs/booth.log`(감시 스크립트와 앱의 기록, 다시 시작한 기록 포함)와 `logs/heartbeat.json`(2초마다 새로 씀: 상태, 초당 프레임 수, 재생 중인 영상, 메모리). 문제를 알릴 때 이 두 파일을 보내 주세요.
- 하루 끝: Esc를 누르고 한 번 더 Esc를 누릅니다. 정상적으로 끝나면 감시 스크립트도 함께 끝납니다.

### 안내판

- 'This is the sensor': 거치대 위 블랙박스 앞에 둡니다. 이 블랙박스의 원본 SD 카드 영상으로 속도를 아는 LED 회전판을 측정해 검증했다는 내용입니다.
- 측정의 한계: 화면 옆에 둡니다. 화면의 I 키 카드와 같은 다섯 가지 한계입니다.
- 두 장 모두 한국어와 영어가 있고, `booth/placards/`에서 A5로 인쇄합니다.

## English

### Start of the day: 10 minute setup checklist

1. Power: the MacBook charger into the power strip and into the MacBook. Keep the lid open.
2. If you use the external monitor, connect it to the MacBook and turn it on. Without it, the booth runs on the MacBook's screen.
3. Put the dashcam on its stand next to the screen, with the A5 "This is the sensor" placard in front of it. Put the A5 limits card next to the screen. The placard files are in `booth/placards/`.
4. Turn on Focus on the Mac.
5. Start the booth with the one command in Terminal:

```
cd ~/wfglink-run/wfglink
./booth/booth.sh
```

   or open the `wfglink-run/wfglink/booth` folder in your home folder in Finder and double-click `booth.command`.
6. Check: within a few seconds the booth is fullscreen on the external monitor (or on the MacBook without one), the video shows orange ember tracks, and the status line names the clip and its credit line. The numbers appear a few seconds into each clip. Press L once and see the language change; press it again to change back.

### Settings to make once, before the day

- System Settings > Lock Screen: "Start Screen Saver when inactive" and "Turn display off on power adapter when inactive" both Never. (While the booth runs, `booth.sh` keeps the Mac awake.)
- System Settings > Displays: the external monitor extends the desktop; it does not mirror it. The booth picks the external monitor by itself.
- Focus on, automatic updates off.
- Check that the approved clips are in `data/raw` (`ls data/raw`). A missing clip is skipped.
- Print both placards on A5, at actual size (100 percent).

### Keys

| Key | What it does |
|---|---|
| L | Korean or English |
| T | Ember tracks on or off |
| F | Ember-derived wind arrows on or off |
| G | Gate line on or off |
| Space | Pause (playback and analysis hold); Space again resumes |
| I | Limits card on or off |
| Esc, then Esc again | Quit. After the first Esc a prompt shows; a second Esc within a few seconds quits |

### Plugging the monitor

- The booth goes fullscreen on the external monitor when one is connected, else on the MacBook's screen.
- Unplug the monitor's cable while the booth runs and the booth moves to the MacBook's screen; plug it back in and the booth moves back. No restart is needed.
- To keep the booth on one screen: quit with Esc twice, then start `./booth/booth.sh --screen external`, or `--screen NAME` with a screen name from the screens line of `python -m wfglink doctor`.

### Labels on the screen

| On screen | Meaning | What to do |
|---|---|---|
| Recorded clip, analysed live (녹화 영상을 실시간 분석 중) | Normal: an approved clip plays and is analysed as it plays. | Nothing |
| Starting measurement (측정 준비 중) | A clip has just started. For a few seconds, while the background is learned, no numbers show. | Nothing |
| Synthetic video · not measured (합성 영상 · 실측 아님) | No clip can play, so synthetic video shows. It is not a measurement. | See "Only synthetic video" below. |
| Paused (일시정지) | Space was pressed. | Press Space. |
| Press Esc again to quit (Esc를 한 번 더 누르면 종료합니다) | Esc was pressed once. | Esc again to quit; otherwise leave it. |
| Estimate (추정치), Uncalibrated (px) (보정 안 됨 (px)) | Small tags that are always there; they say what kind of value it is. | Nothing |

### When something goes wrong

- The screen freezes (the picture stands still and the numbers stop): if "Paused" shows, press Space. Otherwise wait. The supervisor (`booth.sh`) treats a heartbeat older than 30 s, or no newly analysed frame for 90 s, as a hang and restarts the app (usually within 2 minutes). If it is still frozen, quit with Esc twice and start again.
- The app restarted (the screen disappeared for a moment and came back fullscreen): this is the automatic recovery. The counts start again from zero. If it keeps failing quickly, the supervisor waits longer before each restart, from 2 s up to 60 s. If it happens often, send `logs/booth.log` to Claude.
- Only synthetic video: the clip files are not in `data/raw`. Quit with Esc twice, run the commands below, then start again.

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
python scripts/fetch_clips.py
```

- The picture opens on the laptop screen: check the monitor cable; once it is plugged in, the booth moves by itself. If not, start with `--screen external` as in "Plugging the monitor".
- The Terminal window was closed: the booth closes with it. Double-click `booth.command` in Finder to start again.
- Logs: `logs/booth.log` (supervisor and app output, restarts included) and `logs/heartbeat.json` (rewritten every 2 s: status, frames per second, the clip playing, memory). Send both when you report a problem.
- End of the day: press Esc, then Esc again. A clean exit stops the supervisor too.

### Placards

- "This is the sensor": in front of the dashcam on its stand. It says that this dashcam's own SD-card files were checked against an LED turntable of known speed.
- The limits card: next to the screen. It shows the same five limits as the screen's card on key I.
- Both have Korean and English, and print on A5 from `booth/placards/`.
