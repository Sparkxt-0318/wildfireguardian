# 어느 커밋된 출동 지시서가 옛 사유를 들고 있는가

*WFG-267. 방법을 제안한 쪽은 루프이고, 행을 세운 쪽은 크리틱 #72입니다(CHARTER §9).
측정 스크립트 `scripts/measure_dispatch_sheet_staleness.py`, 산출물
`data/processed/dispatch_sheet_staleness/staleness_20260912T101941Z.json`,
게이트 `tests/test_dispatch_sheet_staleness.py`, 등록 키 `dss_*`.*

## 1. 왜 이 문서가 있는가

`WFG-264` <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. No figure is asserted on this line. -->가 2026-09-12에 `no_surviving_vehicle_ingress` 등급의 **사유 한 줄**을
고쳤습니다. 옛 문장은 불을 원인으로, 그리고 예산이 소진되었다고 단정했는데, 그 등급을
정하는 조건은 둘 중 어느 것도 세우지 않습니다. 고친 곳은 문장을 **찍는** 파일
(`scripts/generate_dispatch_outputs.py`)이고, 무엇이 대체되었는지는
`docs/live_pipeline.md` §「Responder-side」가, 왜인지는 `docs/routing_limitations.md`
§7이 적어 두었습니다.

**그런데 어느 문서도 「지금 손에 든 이 장이 옛 것인가」에 답하지 않았습니다.** 부스에서
심사위원이 한 묶음 안의 서로 다른 두 문장을 가리키면, 학생이 펼 수 있는 파일이
없었습니다. 이 문서와 `outputs/dispatch/README.md`의 해당 절이 그 답입니다.

## 2. 방법

전체 범위는 **`outputs/` 아래 추적되는 모든 파일**입니다(`git ls-files -z outputs`).
한 run 디렉터리가 아닙니다 — 그 점이 §5의 첫 항목입니다.

1. 두 사유 상수(`UNREACHABLE_REASON_KO`, `SUPERSEDED_UNREACHABLE_REASON_KO`)를
   `ast`로 emitter 소스에서 **파싱**합니다. import 하지 않는 이유는 두 상수가 이
   측정의 **대상**이기 때문입니다: 이름이 바뀌거나 사라지면 스크립트는 0을 보고하는
   대신 **거부하고 멈춥니다**.
2. 추적되는 모든 `.html` 시트를 열어 두 문장 각각의 유무를 셉니다.
3. 커밋된 `dispatch_a4*.pdf` 는 **같은 이름의 형제 HTML**로 등급을 매깁니다.
   `scripts/generate_dispatch_outputs.py` 가 그 HTML에서 그 PDF를 렌더링하기 때문이고,
   산출물은 이 방법을 `method: "sibling_html_via_render_path"` 로 기록합니다.

시계·네트워크·저장소 밖 파일을 하나도 쓰지 않고, 아무것도 다시 만들지 않으며, 커밋된
시트를 **한 장도 고치지 않습니다**(CHARTER §3 rule 2·rule 7).

## 3. 결과

| 등록 키 | 값 | 뜻 |
|---|---|---|
| `dss_committed_dispatch_pdfs` | 38 | `outputs/` 아래 커밋된 출동 지시서 PDF 전체 |
| `dss_run_dirs_with_a_committed_pdf` | 12 | 그 PDF들이 흩어져 있는 run 디렉터리 수 |
| `dss_stale_committed_pdfs` | 3 | 그중 옛 사유를 들고 있는 장 |
| `dss_tracked_dispatch_html` | 650 | 추적되는 `.html` 시트 전체 |
| `dss_html_carrying_superseded` | 44 | 옛 사유를 찍는 HTML — `docs/live_pipeline.md`의 「44 files」를 트리에서 다시 센 값 |
| `dss_html_carrying_current` | 0 | 오늘의 사유를 찍는 커밋된 HTML |

옛 사유를 들고 있는 세 장:

- `outputs/dispatch/20260801T163042Z/02-천전공원-일대/dispatch_a4.pdf`
- `outputs/dispatch_full/20260801T183522Z/03-영덕해맞이공원-일대/dispatch_a4.pdf`
- `outputs/dispatch_full/20260801T183522Z/03-영덕해맞이공원-일대/dispatch_a4_unreachable.pdf`

**`dss_html_carrying_current` 이 0인 것은 결함이 아니라 기록의 성질입니다.** 커밋된
시트는 전부 WFG-264 <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. No figure is asserted on this line. --> 수리보다 앞서 만들어졌으므로, 오늘 emitter가 찍는 문장을 가진
커밋 시트는 있을 수 없습니다. 0이 아니었다면 커밋된 트리가 기록 하나와 수리 하나가
아니라 **살아 있는 문장 둘**을 들고 있다는 뜻이 됩니다. ⚠ **다만 이것을 「대조군」이라고
부르지는 않습니다.** 이 0은 위의 44와 **같은 한 번의 훑기에서, 같은 코드로** 나온
값입니다. 그러니 이것이 배제하는 것은 **트리가 두 문장을 동시에 들고 있는 경우**
하나뿐이고, 훑기 자체가 틀렸을 가능성 — 예를 들어 상수를 잘못 읽었거나 파일 목록이
잘렸을 가능성 — 은 **전혀 배제하지 못합니다**. 바깥에서 들어온 참값이 없기 때문입니다.
그 두 번째 종류의 오류를 잡는 것은 이 숫자가 아니라
`scripts/measure_dispatch_sheet_staleness.py` 가 상수를 못 찾으면 **0을 보고하는 대신
멈추는** 동작(§2.1)과, 아래 게이트입니다. 나중에 새 run을 커밋하는 랩은 이 칸을 움직이게 되고,
`tests/test_dispatch_sheet_staleness.py::test_no_committed_sheet_carries_the_current_sentence`
가 그 랩에게 이 절을 같이 고치라고 말합니다.

## 4. 한계 — 등급은 **추론**이고, 독립된 두 번째 경로가 그것을 뒷받침합니다

⚠⚠ **이 절의 첫 판은 틀린 논증이었고, 독립 검토자가 그것으로 이 랩을 막았습니다.**
첫 판은 「이 샌드박스에 `pypdf`·`pdfminer`·`pdftotext` 가 없다, **그러므로** 형제 HTML로
등급을 매긴다」고 적었습니다. 앞 절반은 참입니다(`pypdf`, `PyPDF2`, `pdfminer`, `fitz`,
`pikepdf`, `pdftotext`, `pdftk`, `qpdf`, `mutool`, `gs` 모두 없음을 확인했습니다).
**「그러므로」가 거짓입니다** — 라이브러리가 없다는 것은 방법이 없다는 뜻이 아닙니다.

### 4.1 실제로 PDF 바이트를 읽었습니다

`scripts/probe_dispatch_pdf_fonts.py`, **표준 라이브러리만** 씁니다. 이 시트들은 Chrome이
한글 폰트를 **서브셋**으로 심어 렌더링한 것이고, 서브셋에는 그 쪽이 **실제로 찍은 글자**만
들어갑니다. 각 PDF의 `/ToUnicode` CMap은 `FlateDecode` 스트림이므로 `zlib` 하나로 풀려서,
그 파일이 **철자할 수 있는 문자 집합**이 그대로 나옵니다. 두 사유에만 각각 고유한 음절로
가르면:

- 커밋된 PDF `dss_committed_dispatch_pdfs` 장 가운데, **옛 사유에만 있는 음절을 하나도
  빠짐없이** 심고 있는 것은 `dss_stale_committed_pdfs` 장입니다.
- **오늘 사유에만 있는 음절을 모두** 심고 있는 것은 `dss_html_carrying_current` 와 같은
  값, 즉 **없습니다**.

⚠ 두 「고유 음절」 집합의 크기는 이 문서에 적지 않습니다. 그것은 두 상수에서 그때그때
유도되는 값이고 등록된 키가 아니므로, 적어 두면 상수가 바뀌는 순간 낡습니다(§3.3, 그리고
이 랩이 바로 그것으로 막혔습니다). 스크립트와 게이트가 실행 시점에 다시 셉니다.

그 결과로 나온 장들은 §3의 세 장과 **정확히 같습니다.** HTML을 한 번도 보지 않은 경로가
같은 답에 도착했습니다.

### 4.2 그래도 「읽었다」가 아니라 「뒷받침한다」입니다

폰트 서브셋은 **쪽 전체**의 성질이므로, 어떤 음절이 그 쪽의 **다른 글**에서 왔을
가능성을 원리적으로 배제하지 못합니다. 그래서 이 탐침은 §2의 등급을 **대체하지 않고
교차 검증**합니다 — 공유하는 것이라고는 저장소뿐인 두 경로가 일치한다는 것이 요점입니다.
따라서:

- `dss_stale_committed_pdfs` 는 여전히 「**옛 문장을 가진 HTML에서 렌더링되었다**」는
  뜻이고, 이제 「그리고 그 PDF는 옛 문장을 철자할 수 있고 새 문장은 철자할 수 없다」가
  따라붙습니다.
- 렌더링 경로만 있었다면 깨질 수 있던 경우 — HTML이 쓰인 뒤 PDF가 다른 입력으로 다시
  만들어졌거나 손으로 갈아 끼워진 경우 — 는 4.1이 **좁혀 줍니다**. 그런 PDF라면 옛
  사유를 철자할 수 없었을 것이기 때문입니다.
- 남는 부채: 글자 **순서**와 **문장**을 읽은 것은 아직 아닙니다. 추출기가 있는 기계는
  그것까지 확인할 수 있고, 그것은 페이지 수를 렌더러 있는 기계가 재야 하는 `WFG-116`과
  같은 모양의 부채입니다.

**이 절이 남기는 교훈은 숫자보다 큽니다:** 「도구가 없어서 못 한다」는 문장은 거의 언제나
**측정이 아니라 가정**입니다. 반증이 20줄이면 그것은 한계가 아니라 미룬 일입니다.

## 5. 이 측정이 보여 주지 **않는** 것

1. **행이 물은 범위가 아닙니다.** `WFG-267`은
   `outputs/dispatch/20260801T163042Z/` 하나를 두고 세워졌고 「커밋된 PDF 세 장 중
   어느 것인가」를 물었습니다. 그 물음은 답을 세 개짜리 세계에 미리 가둡니다. 트리는
   `dss_committed_dispatch_pdfs` 장을 `dss_run_dirs_with_a_committed_pdf` 개
   디렉터리에 걸쳐 들고 있고, **옛 사유를 든 장이 그 디렉터리 밖에도 있습니다.**
   행의 물음에 그대로 답했다면 두 장을 놓쳤을 것입니다.
2. **어느 등급이 옳은지는 말하지 않습니다.** 이것은 **문장**에 대한 측정이지 분류에
   대한 측정이 아닙니다. 어떤 집이 왜 그 등급에 들어갔는지는
   `docs/routing_limitations.md` §7과 `vus_*` 키가 다룹니다.
3. **실제 산불에 대해 아무것도 말하지 않습니다.** 세어진 파일은 전부 2026-08-01
   실행의 기록이고, 그 뒤의 위험면은 합성입니다.
4. **인쇄 이력을 말하지 않습니다.** 어떤 장이 실제로 프린터로 나갔는지 저장소는
   모릅니다(사람 몫: `WFG-007`, `NH-014`).
5. **이 목록은 손으로 관리되지 않습니다.** 열거는 **두 곳**에 있습니다 —
   `outputs/dispatch/README.md` 의 해당 절과 이 문서 §3 — 그리고
   `tests/test_dispatch_sheet_staleness.py` 가 트리에서 **다시 유도해** **두 쪽 모두**와
   대조합니다. 양방향으로 깨집니다: 트리에 있는데 쪽에 없는 장도, 쪽에 있는데 더 이상
   낡지 않은 경로도 게이트를 빨갛게 만듭니다. 오늘의 열거를 테스트에 박아 넣지 않은
   것은 일부러입니다 — 그런 게이트는 오늘의 사각지대를 그대로 물려받습니다
   (`WFG-266` done-when (d), `WFG-271`의 다시 쓰인 done-when). ⚠ **두 쪽을 다 묶은
   것은 이 랩의 `sip` 점검이 잡아 준 것입니다**: 첫 판은 README 만 묶었고, 그러면 이
   문서 §3 의 같은 목록이 조용히 낡을 수 있었습니다 — 크리틱 #73 이 F1 으로 적은 바로
   그 종류입니다.

## 6. 부스에서 할 말

「다시 뽑은 장이 지금 기준이고, 미리 만들어 둔 PDF는 2026-08-01 기록입니다. 어느
장이 옛 것인지는 `outputs/dispatch/README.md` 에 경로까지 적어 두었고, 테스트가 그
목록을 트리와 맞춰 봅니다. 가장 안전한 방법은 인쇄할 장을 전부 다시 만드는 것이고,
그러면 섞이지 않습니다.」

❌ 「커밋된 시트를 고쳤습니다」 — 고치지 않았습니다. 기록이라 그대로 둡니다.
❌ 「옛 문장이 있는 PDF는 한 장뿐입니다」 — 한 디렉터리 안에서만 참입니다.
