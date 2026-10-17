# Feature modules (About · plan sheet · exports)

Owned by the feature builder. The app shell mounts these components; they never read the store or
wire formats — the core builds their inputs (`src/state/featureData.ts`). Every string has Korean and
English variants in the module's own `strings.ts`; nothing here edits `src/i18n`.

| Module | Entry | Input |
|---|---|---|
| About panel | `about/AboutPanel.tsx` → `AboutPanel({ open, onClose, lang, apiVersion?, fireInputLabel?, mock? })` | contract version from `/health` |
| Plan sheet | `plansheet/PlanSheetDialog.tsx` → `PlanSheetDialog({ open, onClose, sheets, lang, initialOriginId?, prepareAll?, forceSvgMaps? })` | `PlanSheetData[]` (`plansheet/types.ts`), one per origin |
| Exports | `exports/ExportDialog.tsx` → `ExportDialog({ open, onClose, input, lang })`; pure `exports/exports.ts` | `ExportInput` (`exports/types.ts`) |

## Honesty rules enforced here

- Status is always colour + icon + text (`shared/VerdictIcon.tsx`): green check = 확인된 경로, black slashed
  circle = 모델상 경로 없음, grey hatch + question mark = 미확인. Unresolved never gets a deadline, never green.
- Only `checked_route` geometry is drawn or exported (`drawableRoute`, `assertExportable` →
  `ExportRefusedError`). A travel-time-only route appears only as role `travel_only_comparison`, dashed,
  labelled "비교용 — 대피 경로 아님", with its own verdict and full-policy grade.
- 대체 계획 필요 시나리오 lists exactly the scenarios whose best verdict is not `checked_route`:
  `model_no_route` → "차량 대피 경로를 확인하지 못함: 조기 대피 또는 실내 대피(대피 장소 사전 지정) 등 대안 필요";
  `unresolved` → "판단 불가 — 안전으로 간주하지 말 것".
- Every sheet / dialog / export carries the fire-input label, the MOCK badge when mock, provenance and the
  planning-aid footer. Names are never invented: unnamed places read "{구분} · 이름 없음".

## Plan sheet printing

- One `<article class="wfgf-sheet">` per origin, 210 × 297 mm with 16 mm side margins. While the dialog is
  open, `html.wfgf-printing-sheets` makes print media show only the sheets (one per page, no app chrome).
  "PDF로 저장" prints the current sheet, "전체 마을 PDF" renders every map first and prints all.
- Maps: a non-interactive MapLibre render of `basemapStyle(region, { flavor: 'grayscale' })` is converted to
  an `<img>` on `idle` (serial queue, one WebGL context at a time, cached); without WebGL an inline SVG of
  the route geometry with a scale bar is drawn instead. The map fills the page's remaining height.
- Automation hooks on `.wfgf-plansheet-root`: `data-wfg-sheets-ready="true"` (all maps final + fonts
  loaded), `data-wfg-current-ready`, `data-wfg-sheet-count`, `data-print-scope`. Each sheet carries
  `data-sheet-origin`, `data-region`, `data-input-time`, `data-mock`. `?print=all` in the page URL (or
  `prepareAll`) renders every map up front.

## Scripts

- `planner/scripts/export_plan_pdfs.mjs` — opens `<url>/?print=all&region=<id>[&scenario=<input_compact|set id|zones>]&lang=<ko|en>`
  (the app opens the plan sheet by itself once its data is ready), opens the
  dialog (button "계획서"), waits for `data-wfg-sheets-ready`, writes one A4 PDF per region to `planner/exports/`.
- `planner/scripts/screenshots.mjs` — the documented list of states at 1440×900 and 1920×1080 into
  `planner/docs/screenshots/` with `manifest.json`; missing states are logged and skipped.

Both take `--url` and `--out`, and find Playwright through `PLAYWRIGHT_MODULE` (never `playwright install`).
If the app sets `document.documentElement.dataset.wfgDataReady = 'true'` once the selected scenario's results
are loaded, the scripts wait for it; otherwise they wait for network idle.
