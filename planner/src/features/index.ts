/**
 * Feature modules mounted by the app shell (planner/src/features/README.md):
 * About panel, plan sheet (기관용 사전 대피계획서, A4 print) and client-side exports.
 */
export { AboutPanel, type AboutPanelProps } from './about/AboutPanel';
export { PlanSheetDialog, type PlanSheetDialogProps } from './plansheet/PlanSheetDialog';
export type { PlanSheetData, PlanSheetScenario, PlanSheetShelter, PlanSheetExposure, PlanSheetSweepCell, SweepVerdict } from './plansheet/types';
export { alternativePlanItems, deadlineCell, exposureSummary } from './plansheet/sheetLogic';
export { ExportDialog, type ExportDialogProps } from './exports/ExportDialog';
export type { ExportInput, ExportOrigin, ExportOriginPlan, ExportPlace, ExportProvenance, ExportRoute, RouteRole } from './exports/types';
export {
  routeToGeoJSON,
  routeToKML,
  dispatchListCSV,
  assertExportable,
  isExportable,
  exportFileName,
  ExportRefusedError,
  MIME as EXPORT_MIME,
} from './exports/exports';
export { VerdictIcon, VerdictBadge, SweepCellGlyph } from './shared/VerdictIcon';
export { VERDICT_LABEL, VERDICT_DEFINITION, ALT_PLAN_TEXT, LIMITATIONS, FOOTER_APP } from './shared/strings';
