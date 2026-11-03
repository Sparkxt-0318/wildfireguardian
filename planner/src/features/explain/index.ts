/**
 * Deadline explanations (wfg.explanation/1, written by tools/explain_deadlines): the "왜 이 시각인가요? /
 * Why this time?" block of the origin detail panel and the plan-sheet section. Data: public/data/explanations/.
 */
export { ExplainBlock, ExplainSheetSection, MemberDots, useExplanationFile, useExplanationFiles, type ExplainBlockProps, type ExplanationState } from './ExplainBlock';
export { computedOnText, explainView, hostText, matchesShown, onEvaluatedHost, sheetNoteText, slackText, whereText, type ExplainView } from './text';
export { clearExplanationCache, explanationFileName, explanationUrl, loadExplanationFile, parseExplanationFile } from './load';
export { COMPUTED_MARK, EXPLAIN } from './strings';
export type { ExplComputedOn, ExplFile, ExplItem, ExplOrigin, ExplReason, ExplStatus, ShownPlan } from './types';
