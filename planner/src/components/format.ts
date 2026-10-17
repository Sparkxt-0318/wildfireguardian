/**
 * Display helpers shared by components (names, categories, hosts, error texts).
 */
import type { TFunction, Lang } from '../i18n';
import type { HostInfo, Place } from '../domain/types';
import { kstClock, kstDateTime, parseUtc } from '../domain/clock';

export function categoryLabel(p: Pick<Place, 'category' | 'role'>, t: TFunction): string {
  if (p.role === 'research_destination') return t('category.research_destination');
  return t(`category.${p.category}`);
}

function shortCase(caseId: string): string {
  const m = /_([A-Z]+\d+)$/.exec(caseId);
  return m ? m[1]! : caseId;
}

/** Name for display; unnamed places are never given an invented name. */
export function placeName(p: Place, t: TFunction, lang: Lang): string {
  const name = lang === 'en' ? p.nameEn ?? p.name : p.name ?? p.nameEn;
  if (name) return name;
  if (p.role === 'research_origin') return t('place.research', { case: p.caseId ? shortCase(p.caseId) : '—' });
  if (p.role === 'research_destination') return t('place.researchDest', { case: p.caseId ? shortCase(p.caseId) : '—' });
  const ref = p.osm ? `${p.osm.type} ${p.osm.id}` : p.snapNode ? `node ${p.snapNode.replace(/^osm:/, '')}` : p.id;
  const cat = categoryLabel(p, t);
  return t('place.unnamed', { category: lang === 'en' ? cat.charAt(0).toLowerCase() + cat.slice(1) : cat, ref });
}

/** Small mono source tag: "OSM place=village · node 415158323" / "request <case> origin node osm:…". */
export function sourceTag(p: Place): string {
  if (p.source === 'OpenStreetMap') {
    const ref = p.osm ? ` · ${p.osm.type} ${p.osm.id}` : '';
    return `OSM ${p.sourceTag}${ref}`;
  }
  return p.sourceTag || p.source;
}

export function hostLabel(h: HostInfo | null | undefined, t: TFunction): string | null {
  if (!h) return null;
  if (h.recorded) return t('compute.recorded', { machine: h.machine ?? '—' });
  const plat = h.platform ? h.platform.split('-')[0] : h.os;
  const head = [plat, h.machine].filter(Boolean).join(' ');
  const parts = [head, h.cpuCount ? `${h.cpuCount} vCPU` : null].filter(Boolean);
  return parts.length ? parts.join(' · ') : null;
}

export function computeLabel(computeS: number | null, h: HostInfo | null | undefined, t: TFunction): string {
  if (computeS === null) return t('compute.none');
  const host = hostLabel(h, t) ?? '—';
  return t('compute.label', { s: computeS.toFixed(1), host });
}

export function errorText(e: { code: string; message?: string } | null | undefined, t: TFunction): string {
  if (!e) return t('common.unknownError');
  const known = t(`error.${e.code}`);
  if (known !== `error.${e.code}`) return e.message ? `${known} (${e.code}: ${e.message})` : `${known} (${e.code})`;
  return e.message ? `${e.code}: ${e.message}` : e.code;
}

export function reasonText(code: string | null | undefined, t: TFunction): string | null {
  if (!code) return null;
  const s = t(`reason.${code}`);
  if (s !== `reason.${code}`) return `${code} · ${s}`;
  // a request the API refused carries the API's error code (e.g. NODE_NOT_ALLOWED)
  const e = t(`error.${code}`);
  return e === `error.${code}` ? code : `${code} · ${e}`;
}

export function rawStatusText(raw: string | null | undefined, t: TFunction): string | null {
  if (!raw) return null;
  const s = t(`raw.${raw}`);
  return s === `raw.${raw}` ? raw : `${raw} · ${s}`;
}

/** True when the raw status has its own explanation (e.g. MOCK_NO_RECORDED_RESULT). */
export function hasRawStatusText(raw: string | null | undefined, t: TFunction): boolean {
  return Boolean(raw) && t(`raw.${raw}`) !== `raw.${raw}`;
}

/**
 * Reason of an unresolved attempt: when the code is OTHER (or missing) and the raw status has its
 * own explanation, that explanation ("MOCK_NO_RECORDED_RESULT · 기록된 실행 없음 …") instead of
 * "OTHER · 기타"; otherwise the reason code text, then the raw status. Codes are never changed.
 */
export function unresolvedReasonText(code: string | null | undefined, rawStatus: string | null | undefined, t: TFunction): string | null {
  if ((!code || code === 'OTHER') && hasRawStatusText(rawStatus, t)) return rawStatusText(rawStatus, t);
  return reasonText(code, t) ?? rawStatusText(rawStatus, t);
}

/** The batch counter: "{done} / {total} 점검 완료" (+ " · 거부·실패 {n}" only when there are refusals). */
export function batchCounter(b: { done: number; total: number; rejected?: number }, t: TFunction): string {
  const r = b.rejected ?? 0;
  return t('batch.progress', { done: b.done, total: b.total }) + (r > 0 ? t('batch.progressRejected', { rejected: r }) : '');
}

/** English plural forms: `key.one` when n === 1 (Korean has no plural and repeats the text). */
export function pluralKey(key: string, n: number): string {
  return n === 1 ? `${key}.one` : key;
}

export function fmtKstClock(inputTime: string | null | undefined, offsetS: number | null | undefined, seconds = false): string {
  if (!inputTime || offsetS === null || offsetS === undefined) return '—';
  return kstClock(inputTime, offsetS, { seconds });
}

/** "2026-10-17 18:30 KST" from an ISO timestamp (e.g. a cache created_at). */
export function fmtKstStamp(iso: string | null | undefined): string {
  if (!iso || !Number.isFinite(parseUtc(iso))) return '—';
  return kstDateTime(iso, 0);
}

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  if (v === 0) return '0';
  const floor = 10 ** -digits;
  if (Math.abs(v) < floor) return `< ${floor.toFixed(digits)}`;
  return v.toFixed(digits);
}

export function short(s: string | null | undefined, n = 12): string {
  if (!s) return '—';
  return s.length > n ? `${s.slice(0, n)}…` : s;
}
