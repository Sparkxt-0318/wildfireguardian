/**
 * Pure label helpers of the static demo (no React): the recorded period shown in the DEMO chip and
 * on printed plan sheets is derived from the input times of cache/INDEX.json, never hard-coded.
 */
import { CONFIG } from '../../config/env';
import { kstDate } from '../../domain/clock';
import type { Lang, TFunction } from '../../i18n';
import { monthParts } from './strings';

/** README section with the local Route-Check API instructions (documentation link, never fetched). */
export function localRunUrl(repoUrl: string = CONFIG.repoUrl): string {
  return `${repoUrl}/blob/HEAD/planner/README.md#real-route-check-api`;
}

/** KST months ("2025-03") of the recorded input times, sorted, unique. */
export function recordedMonths(inputTimes: string[]): string[] {
  const out = new Set<string>();
  for (const t of inputTimes) {
    const d = kstDate(t);
    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) out.add(d.slice(0, 7));
  }
  return [...out].sort();
}

/**
 * "March 2025" / "2025년 3월" (or a range "March 2022–March 2025"); null without recorded times.
 * `short`: "Mar 2025" / "2025년 3월" for narrow screens.
 */
export function periodLabel(inputTimes: string[], t: TFunction, short = false): string | null {
  const months = recordedMonths(inputTimes);
  const fmt = (ym: string) => {
    const p = monthParts(ym);
    return p ? t(short ? 'demo.periodShort' : 'demo.period', { year: p.year, month: p.month, monthName: p.monthName, monthShort: p.monthShort }) : ym;
  };
  if (!months.length) return null;
  if (months.length === 1) return fmt(months[0]!);
  return t('demo.periodRange', { from: fmt(months[0]!), to: fmt(months[months.length - 1]!) });
}

/** "의성·안동, 영덕" / "Uiseong–Andong and Yeongdeok". */
export function joinNames(names: string[], lang: Lang): string {
  if (names.length <= 1) return names[0] ?? '';
  if (lang === 'ko') return names.join(', ');
  return names.length === 2 ? `${names[0]} and ${names[1]}` : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}
