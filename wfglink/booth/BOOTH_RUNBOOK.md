# 부스 운영 안내 · Booth runbook

한국어가 먼저, 영어가 뒤에 있습니다. English follows the Korean.

부스에는 두 가지 모드가 있습니다. 화재 영상 모드는 승인된 영상 파일을 실시간으로 재생하면서 그 자리에서 분석합니다. 불티 모드("당신이 불티입니다 / You are an ember")는 카메라로 방문객의 휴대폰을 추적합니다. 휴대폰 화면에는 빛나는 불티 페이지가 떠 있습니다. 부스는 화재 영상 모드로 시작하고, M 키로 두 모드를 오갑니다.

The booth has two modes. Fire mode plays approved clip files in real time and analyses them as they play. Ember mode ("당신이 불티입니다 / You are an ember") tracks visitors' phones through a camera; each phone shows a glowing ember page. The booth starts in fire mode, and key M switches between the two.

명령과 경로는 모두 `~/wfglink-run/wfglink` 폴더 기준입니다. All commands and paths refer to the folder `~/wfglink-run/wfglink`.

## 한국어

### 하루 시작: 15분 설치 점검표

1. 전원: MacBook 충전기를 멀티탭에 꽂고 MacBook에 연결합니다. 뚜껑은 열어 둡니다.
2. 외부 모니터가 있으면 MacBook에 연결하고 켭니다. 없으면 부스 화면은 MacBook 화면에 나옵니다.
3. 카메라: USB 웹캠을 쓰면 MacBook에 꽂고, 서는 자리를 정면으로 향하게 모니터 위나 책상 위에 둡니다. 쓰지 않으면 MacBook의 카메라가 서는 자리를 향하도록 MacBook을 놓습니다. 창문이나 밝은 조명이 카메라 화면에 들어오지 않게 합니다.
4. 서는 자리: 카메라 렌즈에서 정면으로 2.0 m 떨어진 바닥에 테이프로 표시합니다. 줄자로 바닥을 따라 잽니다. 이 표시는 휴대폰을 드는 자리입니다. 방문객은 표시 바로 뒤에 서서 휴대폰을 표시 위로 내밀어 듭니다. 카메라나 표시가 어제와 다른 곳에 있으면 아래 '다시 보정하기'를 합니다.
5. 서는 자리 옆에 불티 페이지 QR 카드(`booth/placards/ember_page_ko.pdf`와 `ember_page_en.pdf`, 아래 '불티 페이지 QR 카드 만들기')를 둡니다. 불티 모드 화면의 오른쪽 아래에도 같은 QR 코드와 주소가 나옵니다.
6. 블랙박스를 거치대에 올려 화면 옆에 두고, '이것이 센서입니다' A5 안내판을 그 앞에 세웁니다. 측정의 한계 A5 안내판은 화면 옆에 둡니다. 안내판 파일은 `booth/placards/`에 있습니다.
7. Mac에서 집중 모드를 켭니다.
8. 터미널에서 명령 하나로 부스를 시작합니다.

```
cd ~/wfglink-run/wfglink
./booth/booth.sh
```

   또는 Finder에서 홈 폴더의 `wfglink-run/wfglink/booth` 폴더를 열고 `booth.command`를 더블 클릭합니다.
9. 화재 영상 모드 확인: 몇 초 안에 외부 모니터(없으면 MacBook 화면)에 전체 화면이 뜨고, 영상 위에 주황색 불티 궤적이 보이며, 아래 상태 줄에 영상 이름과 출처가 나옵니다. 숫자는 영상마다 몇 초 뒤에 나타납니다. L을 눌러 언어가 바뀌는지 보고 한 번 더 눌러 되돌립니다. A를 눌러 원본 영상으로 바뀌는지 보고 한 번 더 눌러 분석 화면으로 되돌립니다.
10. 불티 모드 확인: M을 누릅니다. 카메라 화면(거울처럼 좌우가 바뀌어, 휴대폰을 오른쪽으로 움직이면 화면에서도 오른쪽으로 갑니다)과 '당신이 불티입니다 / You are an ember' 제목이 두 언어로 나옵니다(L로 고른 언어가 위에 크게). 휴대폰으로 불티 페이지를 열고 바닥 표시 바로 뒤에 서서 휴대폰을 표시 위로 내밀고 움직입니다. 불티 하나가 궤적, 번호, 속도와 함께 따라와야 합니다. M을 다시 눌러 화재 영상 모드로 돌아갑니다.

### 미리 한 번 해 두는 설정

- 시스템 설정 > 잠금 화면: '비활성 상태일 때 화면 보호기 시작'과 '전원 어댑터 사용 시 비활성 상태일 때 디스플레이 끄기'를 모두 '안 함'으로 둡니다. (부스가 켜져 있는 동안에는 `booth.sh`가 Mac을 깨어 있게 합니다.)
- 시스템 설정 > 디스플레이: 외부 모니터는 '미러링'이 아니라 '확장'으로 둡니다. 부스가 외부 모니터를 스스로 고릅니다.
- 집중 모드를 켜고, 자동 업데이트를 끕니다.
- 카메라 권한: 첫 번째 작업(sitting 1, docs/SITTING1.md)에서 설치 스크립트(`./scripts/setup_mac.sh`)가 묻고 `python -m wfglink cameras --request`로 확인해 터미널의 카메라 사용을 허용해 두었습니다. 부스는 터미널에서 돌아가므로 이 허용이 그대로 쓰입니다.
- 비디오 효과 끄기: 불티 모드에서 카메라가 켜져 있을 때 메뉴 막대의 초록색 카메라 아이콘(비디오 메뉴)을 눌러 센터 스테이지, 인물 사진, 스튜디오 조명, 배경, 반응을 모두 끕니다. 센터 스테이지는 화면을 잘라 내고 움직여서 속도의 크기를 바꾸고, 반응은 화면 위에 그림을 그립니다.
- 불티 페이지(`booth/ember/index.html`)를 GitHub Pages에 올리고, 아래 '불티 페이지 QR 카드 만들기'대로 주소를 설정에 적고 QR 카드를 만듭니다.
- A4 보정판(`booth/ember/calibration_target_A4.pdf`)을 실제 크기(100%)로 인쇄하고, 판 위의 100 mm 선을 자로 확인한 뒤 두꺼운 판지에 평평하게 붙여 둡니다.
- 승인된 영상이 `data/raw`에 있는지 확인합니다(`ls data/raw`). 없는 영상은 건너뜁니다.
- 안내판 세 장(이것이 센서입니다, 측정의 한계, 불티 페이지 QR)을 한국어와 영어로 A5에 인쇄합니다(실제 크기, 100%).

### 두 가지 모드

- 화재 영상 모드(부스가 이 모드로 시작합니다): 승인된 영상을 실시간으로 재생하며 분석합니다. A를 누르면 약 0.5초에 걸쳐 원본 영상과 분석 화면(불티 궤적, 바람 화살표, 숫자)이 서서히 바뀝니다. 시작은 분석 화면입니다. A는 화재 영상에만 작동합니다. 불티 모드는 언제나 분석 화면이고, 화재 영상으로 돌아오면 A로 골라 둔 상태 그대로입니다. 빛나는 점은 확인된 궤적의 점만 그립니다(숫자와 분석은 같습니다).
- 불티 모드 '당신이 불티입니다 / You are an ember': 카메라 화면 위에 휴대폰마다 궤적, 번호, 속도(m/s, 2.0 m에서 잰 값)가 나오고, 지금 잡힌 불티 수와 모든 휴대폰의 움직임으로 계산한 바람 화살표가 나옵니다. 한 번에 최대 3대까지 추적합니다. 더 많은 휴대폰은 무시되고, 숫자 아래에 작게 '최대 3개 · max 3'이 나옵니다. 천장 조명처럼 움직이지 않는 밝은 물체는 불티로 잡지 않도록 되어 있습니다(`validate --suite ember`가 확인하는 목표). 휴대폰이 조명 바로 앞을 지나가면 그 조명에 1초 남짓 번호가 붙었다가 사라질 수 있습니다.
- M을 누르면 두 모드를 오갑니다. 앱이 다시 시작되면 언제나 화재 영상 모드, 분석 화면으로 시작합니다.

### 방문객 안내 (불티 모드)

1. 카드의 주소나 QR 코드로 휴대폰에서 불티 페이지를 엽니다. 검은 화면에 주황색 불티가 빛나고, 짧은 안내가 3초 뒤에 사라집니다.
2. 화면 밝기를 최대로 올립니다. 저전력 모드는 끕니다. 페이지는 브라우저가 허락하면 화면이 꺼지지 않게 합니다.
3. 바닥 표시 바로 뒤에 서서 휴대폰을 표시 위로 내밀고, 화면을 카메라 쪽으로 향하게 들고 움직입니다.
4. 큰 화면에서 자기 불티의 궤적, 번호, 속도를 봅니다. 여러 명이 함께 하면 바람 화살표가 모두의 움직임에서 나옵니다.
5. 속도는 2.0 m에서 잰 값입니다. 휴대폰이 표시보다 카메라에 가까우면 실제보다 빠르게, 멀면 느리게 나옵니다.
6. 휴대폰을 오래(10초 넘게) 꼼짝 않고 들고 있으면 번호가 사라질 수 있습니다. 다시 움직이면 돌아옵니다.

부스에서는 카메라 화면을 보여 주기만 하고 저장하거나 보내지 않습니다. 부스 운영 중에는 `record` 명령을 실행하지 않습니다.

### 키

| 키 | 하는 일 |
|---|---|
| L | 한국어와 영어 바꾸기 |
| T | 불티 궤적 켜기/끄기(불티 모드에서는 화면 위의 번호와 속도도) |
| F | 바람 추정(불티 기반) 화살표 켜기/끄기 |
| G | 게이트 선 켜기/끄기 |
| Space | 일시정지(재생과 분석이 함께 멈춤), 다시 누르면 계속 |
| I | 측정의 한계 카드 켜기/끄기 |
| A | 화재 영상의 원본과 분석 화면 바꾸기(약 0.5초 동안 서서히). 시작은 분석 화면. 불티 모드에서는 아무 일도 하지 않습니다 |
| M | 화재 영상 모드와 불티 모드 바꾸기. 시작은 화재 영상 모드 |
| Esc, 다시 Esc | 종료. 첫 Esc 뒤에 확인 문구가 나오고, 몇 초 안에 한 번 더 누르면 끝납니다 |

### 모니터 연결

- 부스는 외부 모니터가 연결되어 있으면 그 화면에, 없으면 MacBook 화면에 전체 화면으로 뜹니다.
- 부스가 켜져 있을 때 모니터 케이블을 빼면 부스가 MacBook 화면으로 옮겨 가고, 다시 꽂으면 외부 모니터로 돌아갑니다. 다시 시작할 필요가 없습니다.
- 특정 화면에 고정하려면: Esc 두 번으로 끈 뒤 `./booth/booth.sh --screen external`, 또는 `python -m wfglink doctor`의 screens 줄에 나온 화면 이름으로 `--screen 이름`을 붙여 시작합니다.

### 다시 보정하기 (카메라를 옮겼을 때)

카메라를 옮겼거나, 다른 카메라로 바꿨거나, 불티 모드의 속도가 이상해 보이면 A4 보정판으로 다시 보정합니다. 5분이면 됩니다.

1. Esc 두 번으로 부스를 끕니다.
2. 바닥 표시가 카메라 렌즈에서 정면으로 2.0 m인지 줄자로 다시 잽니다. 아니면 표시를 옮깁니다.
3. 터미널에서:

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
python -m wfglink calibrate
```

4. 카메라 화면이 전체 화면으로 나옵니다. 바닥 표시 바로 뒤에 서서, A4 보정판을 휴대폰을 드는 자리인 표시 위로 내밀어 가슴 높이에서 카메라를 향해 평평하게 들고 가만히 있습니다. 네 모서리의 표식이 모두 화면 안에 보여야 합니다. 보정판과 방문객의 휴대폰이 같은 거리에 있어야 속도가 맞습니다.
5. 측정이 안정되면 명령이 스스로 끝나고 결과(초점 거리와 같은 값의 가로 화각)를 출력하며, `configs/booth_local.yaml`에 기록합니다. 90초 안에 안정되지 않으면 아무것도 기록하지 않고 '안정되지 않음'을 알립니다. 그때는 다시 실행합니다. 화각이 카메라의 공칭 값과 많이 다르면 경고가 나옵니다(거리나 인쇄 크기를 확인합니다). Esc를 누르면 취소합니다.
6. `./booth/booth.sh`로 부스를 다시 시작하고, 불티 모드에서 휴대폰으로 확인합니다.

보정을 하지 않으면 속도는 카메라의 공칭 화각으로 계산하므로 덜 정확합니다.

### 화면에 나오는 표시

| 표시 | 뜻 | 할 일 |
|---|---|---|
| 녹화 영상을 실시간 분석 중 · Recorded clip, analysed live | 정상입니다. 화재 영상 모드에서 승인된 영상을 재생하며 분석하고 있습니다. | 없음 |
| 측정 준비 중 · Starting measurement | 영상이 막 시작되었습니다. 배경을 익히는 몇 초 동안 숫자가 나오지 않습니다. | 없음 |
| 합성 영상 · 실측 아님 · Synthetic video · not measured | 재생할 수 있는 영상이 없어 합성 영상을 보여 줍니다. 측정값이 아닙니다. | 아래 '합성 영상만 나올 때'를 봅니다. |
| 당신이 불티입니다 · You are an ember | 불티 모드입니다. | 없음. M을 누르면 화재 영상 모드로 돌아갑니다. |
| 2.0 m 거리에서 측정 · measured at 2.0 m | 불티 모드의 속도는 서는 자리(2.0 m)에서 잰 값입니다. | 없음 |
| 보정 전 · nominal field of view | A4 보정을 아직 하지 않아, 카메라의 공칭 화각으로 속도를 계산합니다. | '다시 보정하기'를 합니다. |
| 원본 영상 · Raw footage | A로 화재 영상의 원본을 보고 있습니다. | A를 누르면 분석 화면으로 돌아갑니다. |
| 카메라를 켜는 중 · Starting the camera | 불티 모드가 카메라를 여는 중입니다. | 몇 초 기다립니다. |
| 카메라를 찾을 수 없습니다 · No camera found | 카메라가 없거나 열리지 않습니다. | 아래 '불티 모드에서 카메라 화면이 나오지 않을 때'를 봅니다. |
| 카메라 사용이 꺼져 있습니다 · Camera access is off | 터미널에 카메라 권한이 없습니다. | 시스템 설정에서 터미널의 카메라를 켭니다(아래). |
| 카메라 권한을 기다리는 중 · Waiting for camera permission | macOS가 권한을 묻는 창을 띄웠습니다. | 창에서 허용을 누릅니다. 창이 안 보이면 M을 두 번 눌러 다시 묻습니다. |
| 불티 모드를 시작하지 못했습니다 · Ember mode could not start | 불티 모드에 오류가 났습니다. 화재 영상은 그대로입니다. | M으로 화재 영상으로 돌아가고 `logs/booth.log`를 Claude에게 보냅니다. |
| 일시정지 · Paused | Space가 눌려 멈췄습니다. | Space를 누릅니다. |
| Esc를 한 번 더 누르면 종료합니다 · Press Esc again to quit | Esc가 한 번 눌렸습니다. | 끄려면 Esc를 한 번 더, 아니면 그냥 둡니다. |
| 불티 기반 바람 추정 · Ember-derived wind (estimate) | 바람 화살표(F)가 켜져 있을 때 나오는 범례입니다. 화살표는 추정치입니다. | 없음 |
| 보정 안 됨 (px) · Uncalibrated (px) | 화재 영상의 값이 픽셀 단위라는 작은 표시입니다. | 없음 |

### 문제가 생겼을 때

- 화면이 멈췄을 때(그림이 서 있고 숫자가 바뀌지 않을 때): '일시정지'가 보이면 Space를 누릅니다. 그렇지 않으면 기다립니다. 감시 스크립트(`booth.sh`)는 앱의 상태 기록(heartbeat)이 30초 넘게 멈추거나, 90초 넘게 새 프레임을 분석하지 못하면 멈춘 것으로 보고 앱을 다시 시작합니다(대개 2분 안). 그래도 그대로면 Esc 두 번으로 끄고 다시 시작합니다.
- 앱이 다시 시작되었을 때(화면이 잠깐 사라졌다가 다시 전체 화면으로 뜰 때): 정상적인 복구입니다. 화재 영상 모드, 분석 화면으로 다시 시작하고 숫자는 처음부터 다시 셉니다. 불티 모드가 필요하면 M을 누릅니다. 짧은 시간에 계속 꺼지면 감시 스크립트가 다시 시작하기 전에 기다리는 시간을 2초부터 최대 60초까지 스스로 늘립니다. 자주 반복되면 `logs/booth.log`를 Claude에게 보냅니다.
- 합성 영상만 나올 때: 영상 파일이 `data/raw`에 없습니다. Esc 두 번으로 끄고 다음을 실행한 뒤 다시 시작합니다(setup은 부스 영상 두 개, 약 50 MB만 받고 영상 목록은 git에 있는 그대로 둡니다).

```
cd ~/wfglink-run/wfglink
./scripts/setup_mac.sh
```

- 불티 모드에서 카메라 화면이 나오지 않을 때(카메라 화면 대신 '카메라를 찾을 수 없습니다', '카메라 사용이 꺼져 있습니다', '카메라 권한을 기다리는 중' 또는 '불티 모드를 시작하지 못했습니다'가 두 언어로 나올 때): 카메라가 없거나, 권한이 없거나, 열리지 않습니다. 카메라가 다시 잡히면 화면은 저절로 돌아옵니다. 그동안 M을 눌러 화재 영상 모드로 운영하면서 다음을 합니다.
  1. Esc 두 번으로 부스를 끕니다. FaceTime, Zoom, Photo Booth처럼 카메라를 쓰는 다른 앱을 모두 종료합니다.
  2. USB 웹캠이면 케이블을 다시 꽂거나 다른 포트에 꽂습니다.
  3. 터미널에서 `cd ~/wfglink-run/wfglink`, `source .venv/bin/activate`, 그리고 `python -m wfglink cameras --request`를 실행합니다. 카메라 목록, 설정이 고른 카메라, 권한 상태가 나옵니다. 이어서 `python -m wfglink cameras --open 5`로 카메라가 실제로 열리는지(백엔드, 크기, 초당 프레임 수) 봅니다.
  4. 권한이 authorized가 아니면: 시스템 설정 > 개인정보 보호 및 보안 > 카메라에서 '터미널'을 켭니다. 터미널을 완전히 종료(Command-Q)했다가 다시 열고 부스를 시작합니다. 목록에 터미널이 없으면 `tccutil reset Camera com.apple.Terminal`을 실행한 뒤 `python -m wfglink cameras --request`를 다시 실행하고, 나오는 창에서 '허용'을 누릅니다.
  5. 원하는 카메라가 아닌 다른 카메라가 골라졌으면: `open -e configs/booth_local.yaml`로 파일을 열고, `camera:` 아래에(없으면 `camera:` 줄을 새로 만들고) `  name: "카메라 이름의 일부"`를 적고 저장합니다. 이미 있는 다른 줄은 지우지 않습니다. 이름은 `cameras`가 보여 준 그대로 씁니다. 카메라를 바꿨으면 '다시 보정하기'를 합니다.
  6. `./booth/booth.sh`로 다시 시작하고 M을 누릅니다.
- 휴대폰이 잡히지 않을 때: 화면 밝기를 최대로, 저전력 모드를 끄고, 화면을 카메라 쪽으로 향하게 들고, 바닥 표시 바로 뒤에 서서 휴대폰을 표시 위로 내밉니다. 페이지가 꺼졌으면 새로 고칩니다.
- 사람이 없는데 불티가 잡힐 때(반짝이는 옷, 반사, 다른 화면): 움직이는 반짝이는 물건을 카메라 화면 밖으로 치우고, 카메라 방향을 조금 바꿉니다. 불을 보여 주는 TV나 다른 모니터, 형광 주황색 조끼처럼 밝은 주황색으로 움직이는 것은 불티로 잡힐 수 있으니 카메라 화면에 들어오지 않게 합니다. 움직이지 않는 조명은 잡지 않도록 되어 있습니다.
- 불티 모드의 속도가 이상할 때: 방문객이 바닥 표시 위에 서 있는지 봅니다. 그래도 이상하면 '다시 보정하기'를 합니다.
- 그림이 노트북 화면에 뜰 때: 모니터 케이블을 확인합니다. 꽂으면 부스가 저절로 옮겨 갑니다. 그래도 안 되면 위의 '모니터 연결'처럼 `--screen external`로 시작합니다.
- 터미널 창을 닫았을 때: 부스도 함께 꺼집니다. Finder에서 `booth.command`를 더블 클릭해 다시 시작합니다.
- 기록 파일: `logs/booth.log`(감시 스크립트와 앱의 기록, 다시 시작한 기록 포함)와 `logs/heartbeat.json`(2초마다 새로 씀: 상태, 초당 프레임 수, 재생 중인 영상, 모드, 원본 또는 분석 화면, 카메라 상태, 메모리). 문제를 알릴 때 이 두 파일을 보내 주세요.
- 하루 끝: Esc를 누르고 한 번 더 Esc를 누릅니다. 정상적으로 끝나면 감시 스크립트도 함께 끝납니다.

### 안내판

- '이것이 센서입니다' (This is the sensor): 거치대 위 블랙박스 앞에 둡니다. 이 블랙박스가 wfglink가 읽는 것과 같은 평범한 카메라이고, wfglink가 그런 영상에서 무엇을 재는지 알려 줍니다.
- 측정의 한계: 화면 옆에 둡니다. 화면의 I 키 카드와 같은 다섯 가지 한계입니다.
- 불티 페이지 QR 카드: 서는 자리 옆에 둡니다. 불티 페이지 주소의 큰 QR 코드와 주소, 할 일 두 가지가 있습니다.
- 세 장 모두 한국어와 영어가 있고, `booth/placards/`에서 A5로 인쇄합니다.

### 블랙박스를 부스 카메라로 쓰기 (USB 'PC 카메라' 모드)

USB 'PC 카메라'(UVC) 모드를 지원하는 블랙박스는 보통 웹캠처럼 쓸 수 있습니다.
1. 블랙박스를 USB로 맥북에 연결하고, 블랙박스 화면이나 메뉴에서 'PC 카메라'(PC Camera, UVC)를 고릅니다. '저장 장치'(Mass Storage)를 고르면 카메라가 아니라 SD 카드로 잡힙니다.
2. `python -m wfglink cameras`로 목록을 봅니다. 블랙박스가 `usb` 종류로 나와야 합니다(예: `USB2.0 PC CAMERA`). 목록에 없으면 케이블(충전 전용 케이블은 안 됨)과 모드를 확인합니다.
3. `camera.name`이 `auto`이면 USB 카메라가 내장 카메라보다 먼저 골라집니다. 다른 USB 카메라도 꽂혀 있으면 `configs/booth_local.yaml`의 `camera:` 아래에 `  name: "PC CAMERA"`처럼 이름의 일부를 적습니다.
4. 블랙박스 렌즈는 화각이 넓으므로 반드시 A4 보정을 다시 합니다(`python -m wfglink calibrate`). 화각이 이상하다는 경고는 광각 렌즈에서는 정상일 수 있습니다. 광각 렌즈는 화면 가장자리를 휘게 하므로, 표시 지점은 화면 가운데에 오게 합니다.
5. 화면에 시간이나 로고가 찍혀 나오면(특히 노란색, 주황색 글자), `camera:` 아래에 `  mask: [[0.0, 0.92, 0.45, 1.0]]`처럼 가릴 영역을 화면 너비와 높이의 비율(좌우 반전 전)로 적습니다. 그 부분은 검게 가려지고 분석하지 않습니다.
6. `python -m wfglink live --ember --duration 60`으로 확인합니다.

### 불티 페이지 QR 카드 만들기 (페이지를 올린 뒤 한 번)

1. 불티 페이지를 GitHub Pages에 올리고 주소를 확인합니다(docs/SITTING1.md 3부, `booth/ember/README.md`).
2. `open -e configs/booth_local.yaml`로 파일을 열고(없으면 먼저 `touch configs/booth_local.yaml`), 다음 두 줄을 적고 저장합니다. 이미 `booth:` 줄이 있으면 그 아래에 둘째 줄만 넣습니다.

```
booth:
  ember_page_url: https://YOUR-NAME.github.io/ember/
```

3. 터미널에서 `cd ~/wfglink-run/wfglink`, `source .venv/bin/activate`, `python scripts/make_placards.py --card ember_page`를 실행합니다. `booth/placards/ember_page_ko.pdf`와 `ember_page_en.pdf`가 생깁니다. A5에 실제 크기(100%)로 인쇄하고, 휴대폰 카메라로 QR 코드를 찍어 페이지가 열리는지 확인합니다.
4. 이 설정이 있으면 부스의 불티 모드 화면 오른쪽 아래에도 같은 QR 코드와 주소가 나옵니다. 주소를 비우면 화면에도 카드에도 나오지 않습니다.

## English

### Start of the day: 15 minute setup checklist

1. Power: the MacBook charger into the power strip and into the MacBook. Keep the lid open.
2. If you use the external monitor, connect it to the MacBook and turn it on. Without it, the booth runs on the MacBook's screen.
3. Camera: if you use the USB webcam, plug it into the MacBook and put it on the monitor or the table, facing the standing spot. Without it, place the MacBook so its own camera faces the standing spot. Keep windows and bright lamps out of the camera's view.
4. Standing spot: a tape mark on the floor 2.0 m straight in front of the camera lens, measured along the floor with the tape measure. The mark is where the phone is held: visitors stand just behind it and hold the phone out over it. If the camera or the mark is not where it was yesterday, do "Recalibrating" below.
5. Next to the standing spot, put the ember page's QR card (`booth/placards/ember_page_ko.pdf` and `ember_page_en.pdf`, see "Making the ember page's QR card" below). Ember mode's screen shows the same QR code and address bottom right.
6. Put the dashcam on its stand next to the screen, with the A5 "This is the sensor" placard in front of it. Put the A5 limits card next to the screen. The placard files are in `booth/placards/`.
7. Turn on Focus on the Mac.
8. Start the booth with the one command in Terminal:

```
cd ~/wfglink-run/wfglink
./booth/booth.sh
```

   or open the `wfglink-run/wfglink/booth` folder in your home folder in Finder and double-click `booth.command`.
9. Check fire mode: within a few seconds the booth is fullscreen on the external monitor (or on the MacBook without one), the video shows orange ember tracks, and the status line names the clip and its credit line. The numbers appear a few seconds into each clip. Press L and see the language change; press it again to change back. Press A and see the raw clip; press it again to return to the analysed view.
10. Check ember mode: press M. The camera picture (mirrored, so a phone moving right moves right on screen) and the header "당신이 불티입니다 / You are an ember" in both languages (the L language on top, large) appear. Open the ember page on a phone, stand just behind the floor mark, hold the phone out over it and move it: one ember with a trail, an ID and a speed must follow it. Press M again to return to fire mode.

### Settings to make once, before the day

- System Settings > Lock Screen: "Start Screen Saver when inactive" and "Turn display off on power adapter when inactive" both Never. (While the booth runs, `booth.sh` keeps the Mac awake.)
- System Settings > Displays: the external monitor extends the desktop; it does not mirror it. The booth picks the external monitor by itself.
- Focus on, automatic updates off.
- Camera permission: in sitting 1 (docs/SITTING1.md), the setup script (`./scripts/setup_mac.sh`) asked for it and `python -m wfglink cameras --request` confirmed that Terminal may use the camera. The booth runs in Terminal, so that permission holds.
- Video effects off: while ember mode shows the camera, click the green camera icon in the menu bar (the Video menu) and turn off Center Stage, Portrait, Studio Light, Background and Reactions. Center Stage crops and moves the picture, which changes the scale of the speeds; Reactions draw on the picture.
- Put the ember page (`booth/ember/index.html`) on GitHub Pages, write its address into the config and make the QR card, as in "Making the ember page's QR card" below.
- Print the A4 calibration target (`booth/ember/calibration_target_A4.pdf`) at actual size (100 percent), check its 100 mm line with a ruler, and glue it flat onto stiff card.
- Check that the approved clips are in `data/raw` (`ls data/raw`). A missing clip is skipped.
- Print the three placards ("This is the sensor", the limits card and the ember page's QR card), Korean and English, on A5 at actual size (100 percent).

### The two modes

- Fire mode (the booth starts in it): approved clips play in real time and are analysed as they play. A fades between the raw clip and the analysed view (ember trails, wind arrows, numbers) over about 0.5 s. The booth starts analysed. A acts on the fire footage only: ember mode always shows its analysed screen, and the fire footage comes back the way A left it. The glowing points are those of confirmed tracks only (the numbers and the analysis are the same).
- Ember mode, "당신이 불티입니다 / You are an ember": on the camera picture, each phone gets a trail, an ID and a speed (m/s, measured at 2.0 m), with the number of embers tracked and the wind arrows computed from all the phones' motion. Up to 3 phones are tracked at once; more phones are ignored, and a small "max 3" note shows under the count. Bright things that do not move, such as ceiling lights, are meant not to be taken for embers (a goal `validate --suite ember` checks). When a phone sweeps right in front of a lamp, the lamp may carry a number for about a second before it goes.
- M switches between the two modes. After any restart the app starts in fire mode, analysed.

### Guiding visitors (ember mode)

1. Open the ember page on the phone from the address or QR code on the card. A glowing orange ember fills the black screen; a short instruction fades after 3 s.
2. Turn the screen brightness up to maximum and low power mode off. Where the browser allows, the page keeps the screen awake.
3. Stand just behind the floor mark, hold the phone out over it with its screen to the camera, and move it.
4. Watch your own ember on the big screen: its trail, ID and speed. With several people, the wind arrows come from everyone's motion.
5. Speeds are measured at 2.0 m. A phone nearer the camera than the mark shows faster than it moves; farther away, slower.
6. A phone held perfectly still for a long time (more than about 10 s) may lose its number; it comes back when the phone moves.

The booth shows the camera picture live and never stores or sends it. Do not run the `record` command while the booth is open to visitors.

### Keys

| Key | What it does |
|---|---|
| L | Korean or English |
| T | Ember tracks on or off (in ember mode also the numbers and speeds on the picture) |
| F | Ember-derived wind arrows on or off |
| G | Gate line on or off |
| Space | Pause (playback and analysis hold); Space again resumes |
| I | Limits card on or off |
| A | Fire footage: raw clip or analysed view (a fade of about 0.5 s); the booth starts analysed. Nothing in ember mode |
| M | Fire mode or ember mode; the booth starts in fire mode |
| Esc, then Esc again | Quit. After the first Esc a prompt shows; a second Esc within a few seconds quits |

### Plugging the monitor

- The booth goes fullscreen on the external monitor when one is connected, else on the MacBook's screen.
- Unplug the monitor's cable while the booth runs and the booth moves to the MacBook's screen; plug it back in and the booth moves back. No restart is needed.
- To keep the booth on one screen: quit with Esc twice, then start `./booth/booth.sh --screen external`, or `--screen NAME` with a screen name from the screens line of `python -m wfglink doctor`.

### Recalibrating (when the camera moved)

When the camera moved, another camera is used, or ember mode speeds look wrong, calibrate again with the A4 target. It takes 5 minutes.

1. Quit the booth with Esc twice.
2. Check with the tape measure that the floor mark is 2.0 m straight in front of the camera lens; move the mark if not.
3. In Terminal:

```
cd ~/wfglink-run/wfglink
source .venv/bin/activate
python -m wfglink calibrate
```

4. The camera picture shows fullscreen. Stand just behind the floor mark and hold the A4 target out over it, where phones are held, flat at chest height, facing the camera, and keep still. All four corner markers must be inside the picture. The target and the visitors' phones must be at the same distance for the speeds to be right.
5. Once the measurement is stable, the command ends by itself, prints the result (the focal length and the equivalent horizontal field of view) and writes it into `configs/booth_local.yaml`. If it is not stable within 90 s, it writes nothing and says "not stable": run it again. A field of view far from the camera's nominal one gives a warning (check the distance and the print scale). Esc cancels.
6. Start the booth again with `./booth/booth.sh` and check ember mode with a phone.

Without a calibration, speeds are computed from the camera's nominal field of view and are less accurate.

### Labels on the screen

| On screen | Meaning | What to do |
|---|---|---|
| Recorded clip, analysed live (녹화 영상을 실시간 분석 중) | Normal: in fire mode, an approved clip plays and is analysed as it plays. | Nothing |
| Starting measurement (측정 준비 중) | A clip has just started. For a few seconds, while the background is learned, no numbers show. | Nothing |
| Synthetic video · not measured (합성 영상 · 실측 아님) | No clip can play, so synthetic video shows. It is not a measurement. | See "Only synthetic video" below. |
| You are an ember (당신이 불티입니다) | Ember mode. | Nothing; M returns to fire mode. |
| measured at 2.0 m (2.0 m 거리에서 측정) | Ember mode speeds are measured at the standing spot, 2.0 m from the camera. | Nothing |
| nominal field of view (보정 전) | No A4 calibration yet: speeds use the camera's nominal field of view. | Do "Recalibrating". |
| Raw footage (원본 영상) | A shows the fire footage's raw clip. | A returns to the analysed view. |
| Starting the camera (카메라를 켜는 중) | Ember mode is opening the camera. | Wait a few seconds. |
| No camera found (카메라를 찾을 수 없습니다) | No camera, or it does not open. | See "Ember mode shows no camera picture" below. |
| Camera access is off (카메라 사용이 꺼져 있습니다) | Terminal may not use the camera. | Turn Terminal on for the camera in System Settings (below). |
| Waiting for camera permission (카메라 권한을 기다리는 중) | macOS shows the permission dialog. | Click Allow. No dialog? Press M twice to ask again. |
| Ember mode could not start (불티 모드를 시작하지 못했습니다) | Ember mode hit an error; fire mode still works. | M back to the fire footage; send `logs/booth.log` to Claude. |
| Paused (일시정지) | Space was pressed. | Press Space. |
| Press Esc again to quit (Esc를 한 번 더 누르면 종료합니다) | Esc was pressed once. | Esc again to quit; otherwise leave it. |
| Ember-derived wind (estimate) (불티 기반 바람 추정) | The legend of the wind arrows, while F has them on. The arrows are an estimate. | Nothing |
| Uncalibrated (px) (보정 안 됨 (px)) | A small tag: fire mode's values are in pixels. | Nothing |

### When something goes wrong

- The screen freezes (the picture stands still and the numbers stop): if "Paused" shows, press Space. Otherwise wait. The supervisor (`booth.sh`) treats a heartbeat older than 30 s, or no newly analysed frame for 90 s, as a hang and restarts the app (usually within 2 minutes). If it is still frozen, quit with Esc twice and start again.
- The app restarted (the screen disappeared for a moment and came back fullscreen): this is the automatic recovery. It comes back in fire mode, analysed, and the counts start again from zero; press M if you want ember mode. If it keeps failing quickly, the supervisor waits longer before each restart, from 2 s up to 60 s. If it happens often, send `logs/booth.log` to Claude.
- Only synthetic video: the clip files are not in `data/raw`. Quit with Esc twice, run the commands below (setup downloads just the two booth clips, about 50 MB, and keeps the clip list as it is in git), then start again.

```
cd ~/wfglink-run/wfglink
./scripts/setup_mac.sh
```

- Ember mode shows no camera picture (instead, "No camera found", "Camera access is off", "Waiting for camera permission" or "Ember mode could not start", in both languages): there is no camera, no permission, or the camera does not open. The picture comes back by itself once the camera does. Keep the booth running in fire mode (M) meanwhile, and:
  1. Quit the booth with Esc twice. Quit every other app that uses the camera, such as FaceTime, Zoom or Photo Booth.
  2. For the USB webcam, plug its cable in again, or into another port.
  3. In Terminal: `cd ~/wfglink-run/wfglink`, `source .venv/bin/activate`, then `python -m wfglink cameras --request`. It lists the cameras, the one the config picks, and the permission status. Then `python -m wfglink cameras --open 5` shows whether the camera really opens (backend, size, frames per second).
  4. If the permission is not authorized: System Settings > Privacy & Security > Camera, turn Terminal on. Quit Terminal completely (Command-Q), open it again and start the booth. If Terminal is not in that list, run `tccutil reset Camera com.apple.Terminal`, then `python -m wfglink cameras --request` again, and click Allow in the dialog.
  5. If the wrong camera is picked: open the file with `open -e configs/booth_local.yaml`; under `camera:` (add a `camera:` line if there is none) write `  name: "part of the camera's name"` and save. Do not delete the other lines. Write the name as `cameras` shows it. After changing the camera, do "Recalibrating".
  6. Start again with `./booth/booth.sh` and press M.
- A phone is not picked up: brightness to maximum, low power mode off, the screen held towards the camera, standing just behind the floor mark with the phone held out over it. Reload the page if it went dark.
- Embers appear with nobody there (shiny clothing, reflections, another screen): move shiny moving things out of the camera's view and turn the camera a little. Bright orange things that move, such as a TV or a second monitor showing fire, or a hi-vis orange vest, can be taken for embers: keep them out of the camera's view. Lights that do not move are meant not to be picked up.
- Ember mode speeds look wrong: check that visitors stand on the floor mark. If they still look wrong, do "Recalibrating".
- The picture opens on the laptop screen: check the monitor cable; once it is plugged in, the booth moves by itself. If not, start with `--screen external` as in "Plugging the monitor".
- The Terminal window was closed: the booth closes with it. Double-click `booth.command` in Finder to start again.
- Logs: `logs/booth.log` (supervisor and app output, restarts included) and `logs/heartbeat.json` (rewritten every 2 s: status, frames per second, the clip playing, the mode, raw or analysed, the camera state, memory). Send both when you report a problem.
- End of the day: press Esc, then Esc again. A clean exit stops the supervisor too.

### Placards

- "This is the sensor": in front of the dashcam on its stand. It says that this dashcam is the kind of ordinary camera wfglink reads, and what wfglink measures from such video.
- The limits card: next to the screen. It shows the same five limits as the screen's card on key I.
- The ember page's QR card: next to the standing spot. A large QR code of the page's address, the address, and the two things to do.
- All three have Korean and English, and print on A5 from `booth/placards/`.

### Using a dashcam as the booth camera (USB "PC camera" mode)

A dashcam with a USB "PC camera" (UVC) mode works like a webcam.
1. Connect the dashcam to the MacBook by USB and choose "PC camera" (PC Camera, UVC) on its screen or menu. "Mass storage" makes it show up as its SD card, not as a camera.
2. Run `python -m wfglink cameras`. The dashcam should be listed with the kind `usb` (for example `USB2.0 PC CAMERA`). If it is missing, check the cable (a charge-only cable does not work) and the mode.
3. With `camera.name` set to `auto`, a USB camera is picked before the built-in one. If another USB camera is plugged in too, write part of the dashcam's name under `camera:` in `configs/booth_local.yaml`, for example `  name: "PC CAMERA"`.
4. A dashcam lens is wide, so always redo the A4 calibration (`python -m wfglink calibrate`). A warning about an unusual field of view can be normal for a wide lens. A wide lens bends the picture toward its edges, so place the floor mark where it appears near the middle of the picture.
5. If the picture carries a burned-in time or logo (yellow or orange text especially), write the area to blank under `camera:`, for example `  mask: [[0.0, 0.92, 0.45, 1.0]]`, as fractions of the picture's width and height before mirroring. That area is blacked out and not analysed.
6. Check with `python -m wfglink live --ember --duration 60`.

### Making the ember page's QR card (once, after publishing the page)

1. Publish the ember page on GitHub Pages and note its address (docs/SITTING1.md Part 3, `booth/ember/README.md`).
2. Open the file with `open -e configs/booth_local.yaml` (if it does not exist, `touch configs/booth_local.yaml` first), write these two lines and save. If there is a `booth:` line already, put only the second line under it.

```
booth:
  ember_page_url: https://YOUR-NAME.github.io/ember/
```

3. In Terminal: `cd ~/wfglink-run/wfglink`, `source .venv/bin/activate`, `python scripts/make_placards.py --card ember_page`. It writes only `booth/placards/ember_page_ko.pdf` and `ember_page_en.pdf`. Print them on A5 at actual size (100 percent), and scan the QR code with a phone's camera to check that the page opens.
4. With this setting, the booth's ember mode screen also shows the same QR code and address bottom right. With the address empty, neither the screen nor a card shows one.
