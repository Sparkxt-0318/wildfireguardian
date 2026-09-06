# 부스 인쇄물 (printables) — 어떻게 만들고, 무엇을 믿을 수 있는가

**Row:** WFG-007 (P0, KCF) · **Built by:** `scripts/build_printables.py` ·
**Gate:** `tests/test_printables.py` · **Command:** `make printables`
**Proposed by:** the loop (2026-09-06 dev lap), on the row the author's backlog carries.

---

## 1. 무엇인가

부스에서 손에 들고 있을 종이 네 가지를 A4 PDF 한 권으로 묶습니다.

| 순서 | 원본 문서 | 인쇄물 제목 |
|---|---|---|
| 1 | `docs/auto/finals/BOOTH_SETUP.md` | 부스 설치 체크리스트 |
| 2 | `docs/auto/DEMO_SCRIPT_5MIN.md` | 5분 시연 대본 |
| 3 | `docs/auto/JUDGE_QA.md` | 심사위원 질의응답 카드 |
| 4 | `docs/auto/finals/DETECTION_FLOOR_CARD.md` | 탐지 하한 근거 카드 |

산출물은 `docs/auto/finals/printables/WFG_printables_<stamp>.pdf` 와 그 옆의
`manifest_<stamp>.json` 입니다. 스탬프는 재사용하지 않습니다 — CHARTER §3.2 가 「새 결과에는 새
파일 이름」을 요구하므로, 다음 랩이 다시 만들면 이 파일을 덮어쓰지 않고 옆에 놓입니다.

## 2. 방법 — 그리고 왜 이렇게 생겼는가

**이 저장소의 샌드박스에는 PDF 도구가 없습니다.** `reportlab`, `weasyprint`, `wkhtmltopdf`,
`pandoc`, 헤드리스 크로미움 모두 없습니다. 새로 하나를 넣으면 `make check-declared-deps` 와
`scripts/env_check.py` 가 그 핀을 부스 노트북까지 들고 가야 합니다.

이미 있는 것으로 만들었습니다: **matplotlib** (이 저장소의 모든 그림이 이것으로 그려집니다) 이
PDF 를 쓰고, **fontTools + brotli** 가 `web/assets/fonts/` 의 한글 웹폰트를 풀어 줍니다.
`matplotlib` 과 `fontTools` 는 `requirements.txt` 에 있습니다. `brotli` 는 fontTools 가 woff2 를
읽을 때 필요한데, `scripts/auto/bootstrap.sh` 가 설치하고 기존 `tests/test_screen_checks.py` 의
woff2 읽기가 이미 요구합니다 — 다만 **`requirements.txt` 나 `pyproject.toml` 에 이름이 적혀
있지는 않습니다.** 이 스크립트가 만든 상황이 아니고, 이 스크립트가 바꾸지도 않습니다.

그래서 인쇄물은 화면과 **같은 서체**, 그림과 **같은 스택**으로, **새 의존성 없이** 나옵니다.
인터넷도, 키도, 유료 서비스도 쓰지 않습니다.

## 3. 결과 (2026-09-06T0620Z 빌드)

- **29 페이지** — 체크리스트 6, 대본 7, 질의응답 17, 탐지 카드 3.
- 빌드 시간 약 9 초, 파일 약 400 KB, 폰트는 PDF 안에 임베드(Type 42)됩니다.
- 같은 스탬프로 두 번 빌드하면 **바이트가 동일**합니다 (`CreationDate` 고정).
  `tests/test_printables.py` 가 그것을 다시 빌드해서 확인합니다.

## 4. 이 빌드가 실제로 막는 것 — 글꼴 부분집합

`IBMPlexSansKR-Regular.woff2` 는 화면용으로 **잘라낸(subset)** 글꼴이고 **2,460 코드포인트**만
있습니다. 이 문서들이 쓰는 한글 음절은 전부 들어 있지만, 기호 **19 개**가 **없습니다**:
`§ – — Ⅱ Ⅲ Ⅴ ← → ≥ ② ⚠ ✅ ❌ ⭕ 「 」 〔 〕 🛑`.

⚠ **이 19 라는 숫자는 손으로 적은 것이 아닙니다.** manifest 의
`n_chars_needing_substitution` 이 빌드할 때 계산해서 적고, `tests/test_printables.py` 가 이
문서의 숫자를 그것과 대조합니다. 첫 초안은 여기에 「17」이라고 적었는데, 그것은 네 문서 중
`JUDGE_QA.md` **한 개**의 개수였고 네 문서의 합집합이 아니었습니다. 이 랩의 독립 검토자가
잡았습니다 — 그 숫자를 만들어 낸 산출물이 **없었기 때문에** 아무것도 반박하지 못했던 것입니다.
저장소 규칙(CHARTER §3.3) 그대로입니다: 등록된 산출물이 없는 숫자는 쓰지 않습니다.

matplotlib 은 없는 글자를 만나도 **예외를 던지지 않습니다.** 조용히 빈칸을 그립니다. 그리고 그
실패는 심사위원이 들고 있는 종이 위에서 처음 보입니다. CHARTER §8 이 이 위험을 이미 좁은 형태로
알고 있습니다(「shipped screens 에 em-dash 금지 — 폰트 부분집합」). 이 스크립트는 그것을 게이트로
일반화합니다. 세 겹입니다:

1. **사전 검사** — 원본 네 문서의 모든 글자가 글꼴에 있거나 `SUBSTITUTIONS` 표에 있어야 합니다.
   아니면 빌드가 **거부**됩니다(exit 2).
2. **레이아웃 후 검사** — 실제로 페이지에 그려진 글자를 그것이 **배정된 서체**에 대해 다시
   확인합니다.
3. **경고의 예외 승격** — matplotlib 자신의 「missing from font」 경고를 빌드 동안 예외로
   바꿉니다.

**2번과 3번이 필요한 이유는 1번이 실제로 두 번 뚫렸기 때문입니다.** 이 랩의 첫 초안에서:

- 렌더러가 목록 기호로 쓰던 `•` (U+2022) 는 **원본 문서 어디에도 없는 글자**여서 사전 검사가
  볼 수 없었고, 글꼴에도 없었습니다. (지금은 `·` U+00B7 을 씁니다.)
- 표와 코드 줄은 `IBMPlexMono-Regular` 로 그려지는데 이 글꼴에는 코드포인트가 **229 개**뿐이고
  **한글이 하나도 없습니다.** 한국어 표가 통째로 빈칸이 될 뻔했습니다. 지금은 모노가 그릴 수 없는
  줄이면 본문 서체로 물러나고, 그렇게 물러난 줄 수를 manifest 의 `mono_fallback_lines` 에
  적습니다. 그 줄은 칸 맞춤을 잃습니다 — 두 손해 중 작은 쪽을 고른 것입니다.

즉 **원본을 검사하는 게이트는 렌더러가 스스로 덧붙이는 글자를 보지 못합니다.** 페이지를 검사하는
게이트만 그것을 봅니다.

## 5. 이 파일이 보여주지 않는 것 (what this does NOT show)

- **새로운 숫자도, 새로운 주장도, 새로운 출처도 없습니다.** 인쇄물은 커밋된 네 문서의 인쇄
  렌더링일 뿐이고, 그 문서들이 그때 말하던 것을 그대로 말합니다. 원본이 바뀌면 이 PDF 는 낡은
  것이 되고, 새 스탬프로 하나 더 만들어야 합니다. manifest 에 원본 네 개의 sha256 이 적혀 있어서
  낡았는지 기계로 확인할 수 있습니다.
- **지도도, 경로도, 그림도 들어 있지 않습니다.** 화면(`web/finals.html`)의 대체물이 아닙니다.
- **아직 없는 인쇄물이 있습니다:** A4 근거 시트(WFG-018)와 관련연구 표(WFG-026)는 아직 문서
  자체가 없어서 여기에 없습니다. `outputs/dispatch*` 의 29 장 마을 A4 시트와 마을방송 대본은
  **이미 커밋된 PDF** 라서 그대로 인쇄하면 되고, 이 파일에 다시 넣지 않았습니다(사본 두 벌 금지,
  CHARTER §3.2).
- **markdown 렌더러가 아닙니다.** 제목, 목록, 인용, 코드/표(그대로), 가로줄, 인라인 강조 제거만
  처리합니다. 강조(굵게/기울임)는 **복원하지 않고 버립니다** — 본문 굵기는 한 가지입니다.
  이미지는 `[그림: …]` 로 대체됩니다.
- **인쇄기에서 실제로 뽑아 본 사람은 아직 없습니다.** 샌드박스에는 PDF 래스터라이저가 없어서
  이 랩은 같은 figure 객체를 PNG 로도 저장해서 눈으로 확인했습니다(`--preview`). 그것은 **배치와
  글자 존재**를 증명하지, 인쇄기의 색·여백·양면을 증명하지 않습니다. **학생이 한 번 뽑아 보는
  단계가 이 행의 남은 절반입니다** (WFG-007 done-when).

## 6. 쓰는 법

```
make printables                                  # 새 UTC 스탬프로 빌드
python scripts/build_printables.py --check-only   # 글꼴 커버리지만 확인
python scripts/build_printables.py --stamp 20260906T0620Z --preview /tmp/pv
```

인쇄물에 문서를 하나 더 넣으려면 `scripts/build_printables.py` 의 `SOURCES` 에 한 줄
추가하면 됩니다. 그 문서에 글꼴이 못 그리는 글자가 있으면 빌드가 거부하면서 그 글자를
`U+XXXX` 로 알려 줍니다. `SUBSTITUTIONS` 에 넣거나 원본에서 빼십시오.
