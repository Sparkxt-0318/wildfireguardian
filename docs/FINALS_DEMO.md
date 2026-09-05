# 본선 시연 화면 (Finals Demo)

`web/finals.html` · 단일 정적 파일 · 완전 오프라인 · 운영자 콘솔과 별개로 공존.

## 시작

**시연만 하려면 빌드가 필요 없습니다.** `web/finals.html` 은 이미 빌드된
상태로 저장소에 있습니다. 파일을 열기만 하면 됩니다:

```
open web/finals.html   # 브라우저로 직접 열기 (file:// 로 동작, 서버 불필요)
```

자료가 바뀌어 **다시 빌드**할 때만 아래를 실행합니다. 반드시 기준 환경
`wfg311` 에서 실행하십시오(`docs/ENVIRONMENT.md`). 기본 `python` 은 지리
공간 스택이 없어 실패하며, 이 경우 `make finals` 가 그 사실을 한 줄로
알려 줍니다.

```
conda activate wfg311
make finals            # 빌드 + 빠른 게이트 실행·기록 + 화면 자산 게이트
```

환경을 활성화하지 않고 실행하려면 인터프리터를 직접 지정합니다:

```
make finals PYTHON=$(conda run -n wfg311 which python)
```

`python scripts/run_api.py` 실행 중이라면
`http://127.0.0.1:8000/finals.html` 로도 열립니다(같은 파일).

- `make finals` 는 `build_finals.py --verify` 를 실행합니다. `--verify` 는
  verify-numbers · check-forbidden · check-region-literals 를 실제로 돌리고
  그 결과(성공/실패·소요 시간)를 신뢰성 탭의 SYSTEM INTEGRITY 패널에
  기록합니다. `--verify` 없이 빌드하면 패널은 「게이트를 실행하지 않았다」고
  정직하게 표시합니다.
- 빌더는 `data/processed/` 에 아무것도 쓰지 않습니다.

## 시연 흐름 (60~120초)

1. 페이지를 열면 인트로(6~10초). **Enter** 또는 「시연 시작」 → 안내 시연.
   「건너뛰기」(Esc)로 언제든 즉시 탈출.
2. 안내 시연 4막: 발견 → 시간과 도로망(자동 재생) → 경로 비교(STATIC VIEW →
   TIME-AWARE VIEW 2단계) → 판단. **다음** 버튼 또는 →. 각 막은 1~4 키로
   즉시 점프.
3. 4막의 「자유 탐색」으로 탐색 모드. 출발지 클릭 → 판정 카드, 도로
   호버 → 상태·폐쇄 시각, 타임라인 드래그/재생.

## 재시작

- **R** : 시나리오 리셋(현재 지역 초기화).
- **G** : 안내 시연 처음부터.
- 우하단 ⋯ 버튼(프리젠터 컨트롤): 인트로 재생, 막 점프, 기본 지역 복귀,
  전체 화면 등. 부스에서 다음 심사위원이 오면 **G** 하나면 됩니다.

## 키보드

| 키 | 동작 |
|---|---|
| G | 안내 시연 시작/재시작 |
| Space | 타임라인 재생/정지 |
| R | 시나리오 리셋 |
| F | 전체 화면 |
| M | 소리 토글(기본 꺼짐) |
| Esc | 시연 종료 · 선택 해제 · 인트로 건너뛰기 |
| ← → | 시연 중 막 이동 / 타임라인 포커스 시 ±10분 |
| 1~4 | 막 점프 |
| EN/KO | 우상단 버튼으로 언어 전환 |

## 표시 사양

- 목표 해상도 1366×768 · 1440×900 · 1920×1080. 핵심 시연 중 세로 스크롤 없음.
- 기본 언어 한국어, EN 토글 제공. 산출물 유래 문자열(지명·주의 문구)은
  한국어 원문 그대로 둡니다.
- `prefers-reduced-motion` 존중: 전환·펄스·자동 팬 비활성.

## 데이터 계보

화면의 모든 수치·기하는 빌드 시점에 정본 산출물에서 읽어 옵니다. 계보 표는
`docs/finals_demo_plan.md` §2, 값별 출처는 화면의 「근거」 버튼과 신뢰성 탭
SYSTEM INTEGRITY 패널(런 ID·npz sha·스냅숏 이름)에서 확인합니다.
도로 구간의 시간별 상태는 커밋 산출물이 아니라 **빌드 시점 파생값**입니다:
정본 위험면을 라우팅과 동일한 규칙(공간 쌍선형·시간 선형 보간, 10분 격자,
p_cut 0.5 / 위험 대역 0.30)으로 도로 기하 위에서 표집한 것입니다.

## Artlist 미디어 설치

`web/demo-media/` 에 파일을 넣으면 자동 사용, 없으면 자동 대체.
슬롯 이름과 검색어는 `docs/ARTLIST_ASSET_GUIDE.md`.

## 오프라인 확인

```
python scripts/check_screen_assets.py web/finals.html   # 외부 참조·대시 게이트
```

와이파이를 끄고 `web/finals.html` 을 파일로 직접 열어 인트로 → 4막 → 탐색 →
근거 → 신뢰성이 모두 동작하는지 확인하십시오. 폰트·미디어·데이터 전부
저장소 내 로컬 파일입니다. 미디어 파일이 없을 때 콘솔의 404 기록은 슬롯
탐지 흔적이며 정상입니다(그 외 네트워크 요청은 없어야 합니다).

## 대체 동작 (fallback)

- 인트로 영상 없음 → 지형 음영 정지 화면 + 느린 팬.
- 오디오 없음/꺼짐 → 무음(기본값이 무음).
- DEM 스냅숏 없음 → 평면 배경(데이터 레이어는 그대로).
- 게이트 미실행 빌드 → SYSTEM INTEGRITY 에 NOT RUN 표기.

## 검증

모두 `conda activate wfg311` 상태에서 실행합니다.

```
make finals        # 빌드 + 게이트
make test          # tests/test_finals_screen.py 포함 전체 스위트
make all-checks    # verify + baseline + snapshot + env + test
```

2026-08-15 실측: `make finals` 게이트 3종 통과·화면 자산 PASS,
전체 스위트 1,050 passed / 3 skipped.
