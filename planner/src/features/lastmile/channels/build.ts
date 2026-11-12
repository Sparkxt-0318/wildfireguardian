/**
 * W-KIT — channel-ready message outputs built on the last-mile kit (research/harness-2026-11/W-KIT/DESIGN.md).
 *
 * Deterministic templates over the kit's own MessagePlan (../plan.ts); no model, no network. Planning aid only:
 * every output says it is model-based and not live, a recorded replay says it is not a real situation, and
 * `unresolved` never carries a departure time, a destination or reassurance. Each output fails closed on its own
 * (checkChannels): a violating output is withheld, the others stay usable.
 *
 * Outputs per origin (Korean source, English translation pending native review):
 *  - head: village-head script — a ≤ 20 s CORE carrying the five warning elements (source, hazard, location, time,
 *    guidance) between a fixed framing OPENER (not-real / data time / markers) and CLOSER (official orders first),
 *    counted separately (the framing alone is ≈ 12–13 s, so a 20 s script with framing is infeasible).
 *  - voice: automatic voice call (ARS) with key-press replies; key 2 = "needs help to leave", passed to the 이장 and
 *    읍·면사무소 — never a promise of transport (the kit's FORBIDDEN list bans pickup / rescue words).
 *  - familyText (≤ 90 bytes EUC-KR / ≤ 160 GSM-7) and familyScript (exactly three lines).
 *  - noOrder: only when the order status supplied by officials is `not_issued`: "no order yet — …", so silence is never
 *    read as safety.
 *  - staff: data-age line and the issue-order-by field (officials only; never a time unless one was computed).
 */
import { FORBIDDEN, MODEL_NOT_LIVE, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS, MODEL_NOT_LIVE_SMS, NOT_REAL, DEPARTURE_INSTRUCTION, RESIDENT_119_NOW } from '../strings';
import { clockTimes, maskData } from '../checks';
import { eucKrBytes, gsm7Length, spokenSeconds, KO_SYLLABLES_PER_S, SMS_KO_MAX_BYTES, SMS_EN_MAX_GSM7 } from '../encoding';
import { enSpokenTime, hm, koDate, koSpokenTime, enDate, kstParts, ymd } from '../compose';
import type { MessagePlan } from '../plan';
import type { LmLang } from '../types';

export const HEAD_CORE_MAX_S = 20;
export const HEAD_FULL_MAX_S = 35;
/**
 * 안전안내문자 limit of the 2025 reform (157 CHARACTERS; 행정안전부예규 제361호 별표 labels "90자"/"157자"). Orders stay
 * at 90 characters. Kept for reference: the no-order message is a STAFF output (Iris/orchestrator scope decision), so
 * it is not sent as a 재난문자 and no 157 limit is enforced on it.
 */
export const STANDARD_MAX_CHARS = 157;
/**
 * 재난문자 limits per message class, in CHARACTERS (행정안전부예규 제361호, 2026-02-04, annex labels; Sofia): 위급·긴급
 * (incl. evacuation orders) 90, 안전안내 (incl. advance-evacuation advice) 157. The kit's older assumption was 90 BYTES of
 * EUC-KR, which is stricter (every character is ≥ 1 byte, so ≤ 90 bytes ⇒ ≤ 90 characters; 45 Hangul fit in 90 bytes,
 * 90 in 90 characters). Kit outputs keep the stricter byte rule. None of these outputs is a 재난문자: if one were ever
 * sent as one, the issuing agency name is mandatory (제10조②) and goes last.
 */
export type CbsClass = 'emergency' | 'urgent' | 'safety_guidance';
export const CBS_CHAR_LIMIT: Record<CbsClass, number> = { emergency: 90, urgent: 90, safety_guidance: 157 };
/** Characters as the regulation counts them (Unicode code points; a line break counts as one). */
export function cbsChars(text: string): number {
  return [...text].length;
}
/** The class a message of this kind would take: an order-like no-route warning is urgent; a leave-by is advance advice. */
export function cbsClassFor(kind: MessagePlan['kind']): CbsClass {
  return kind === 'leave_by' ? 'safety_guidance' : 'urgent';
}

/** Slower reading rate also reported for older listeners (Iris): seconds scale by 3.0 / 2.5. */
export const SLOW_SYLLABLES_PER_S = 2.5;

/**
 * Official order status, supplied explicitly by a named person, with an expiry. Absent, malformed, not yet valid or
 * expired (relative to nowIso) => the no-order output is NOT produced; status is never inferred from silence.
 */
export interface OrderStatusInput {
  status: 'issued' | 'not_issued';
  suppliedBy: string;
  suppliedAtIso: string;
  expiresAtIso: string;
}

/**
 * F-3.1 deadline-field record for this origin (Richard, research/harness-2026-11/F-3.1/deadline_field/postprocess.py):
 * offsets in s after the input time. leaveByS null = model no-route at every departure. issueByS = leaveByS minus
 * ASSUMED alert and door-to-door latencies (sensitivity settings, not measurements); negative = already late.
 * Origin absent from the file => undefined/null here => "not computed". The field has no unresolved state.
 */
export interface IssueOrderBy {
  leaveByS: number | null;
  issueByS?: { low: number; median: number; high: number };
}

/** How a leave-by time is worded (kept variable for a later comprehension test). */
export type TimeStyle = 'clock' | 'clock_and_minutes';

export interface ChannelOptions {
  /** when the outputs are produced (ISO); the data age is measured against it */
  nowIso: string;
  orderStatus?: OrderStatusInput | null;
  issueOrderBy?: IssueOrderBy | null;
  timeStyle?: TimeStyle;
  /**
   * Issuing agency and its contact number: SUPPLIED by officials, never invented or defaulted. Validated by
   * `validIssuer`; anything that fails validation counts as not supplied. English outputs use only `agency.en` (a supplied
   * English or romanised name); a Korean name is never put into an English output.
   */
  issuer?: IssuerInput | null;
  /**
   * Report, per resident-facing output, which of the four fields of the DRAFT decree it carries (draft requirement, as
   * of the notice date 2026-11-04: 재난 및 안전관리 기본법 시행령 일부개정령안 안 제49조②, 행정안전부공고 제2026-1391호,
   * https://opinion.lawmaking.go.kr/gcom/ogLmPp/89332). A report only: a missing field never withholds a message.
   */
  draftDecreeCheck?: boolean;
}

// ------------------------------------------------------------------------------------------------ issuer + draft decree

export interface IssuerInput {
  agency: { ko: string; en?: string | null };
  contact: string;
  /**
   * Explicitly marked by whoever supplied it as usable in drills and replays. A replay, mock or test-data message
   * renders the contact line ONLY with this mark: a real agency number in a replay of a 2025 event invites real calls.
   */
  forDrillOrReplay?: boolean;
}

/** A supplied issuer that passed validation; `en` null = no usable English name (the English field is withheld). */
export interface Issuer {
  agency: { ko: string; en: string | null };
  contact: string;
  forDrillOrReplay: boolean;
}

/** Longest agency name accepted (characters): Korean 40; English 60 (romanised names run longer). */
export const AGENCY_MAX_CHARS = 40;
export const AGENCY_EN_MAX_CHARS = 60;
/**
 * Spoken budget of the contact line in the village-head script, separate from the 35 s budget of opener + core + closer
 * (which the Korean script already uses up to 32.7 s over the 531 real places, so no contact line fits inside it).
 * Over budget => the contact line is left out of the head (the field is withheld there, not the message).
 */
export const HEAD_CONTACT_MAX_S = 10;

const ONE_LINE = /^[^\r\n\t\u0000-\u001f\u007f]+$/;
const EN_NAME = /^[A-Za-z0-9 .,'()&/-]+$/;

/** Agency-name endings accepted (Mira N2): an agency name is a name, not a sentence. */
const AGENCY_SUFFIX: Record<LmLang, RegExp> = {
  ko: /(과|실|청|본부|센터|단|군|시|구|읍|면|동|소|국|대|팀|처|원|부|도|서|사무소|상황실)$/,
  en: /\b(Division|Office|Center|Centre|Department|County|City|Headquarters|Team|Bureau|Unit|Agency|Service|Station|Section)$/i,
};
/** Standard agency-name compounds that contain a kit-forbidden word; removed before the word check of a name. */
const AGENCY_COMPOUNDS: Record<LmLang, string[]> = {
  ko: ['재난안전', '안전재난', '행정안전', '안전관리', '안전총괄', '안전정책', '시민안전', '안전건설', '안전도시', '안전센터', '구조구급', '119구조', '구조대'],
  en: ['safety', 'rescue'],
};

/**
 * A supplied agency name must look like a name (Mira N2): whole contact lines are masked before the kit's scans, so the
 * name itself is checked here. Refused: a clock time, a departure instruction, a sentence ending, a kit-forbidden word
 * outside a standard agency compound, or a name that does not end in an agency suffix.
 */
export function agencyLike(name: string, lang: LmLang): boolean {
  const n = name.trim();
  // main rule: a name that ends in an agency suffix, short, with no sentence punctuation (Iris)
  if (!AGENCY_SUFFIX[lang].test(n)) return false;
  if (n.length > AGENCY_NAME_MAX[lang] || n.split(/\s+/).length > AGENCY_WORDS_MAX) return false;
  if (/[.!?;:。·…"'“”‘’]/.test(lang === 'en' ? n.replace(/\b(Dept|St|No)\./g, '$1') : n)) return false;
  // secondary rejections: clock-time patterns (not digits: 119안전센터 is a real name), departure instructions,
  // sentence endings at the end of any word, kit-forbidden words outside standard agency compounds
  if (clockTimes(n).length || /\d{1,2}\s*:\s*\d{2}/.test(n) || /\d{1,2}\s*시(\s|$|까지|에|\d)/.test(n) || /\b\d{1,2}\s*(a\.?m|p\.?m)\b/i.test(n)) return false;
  if (DEPARTURE_INSTRUCTION.ko.test(n) || DEPARTURE_INSTRUCTION.en.test(n)) return false;
  if (n.split(/\s+/).some((w) => /(니다|시오|세요|하라|바람|바랍니다|해요|어요|아요)$/.test(w))) return false;
  let rest = n.toLowerCase();
  for (const c of AGENCY_COMPOUNDS[lang]) rest = rest.split(c.toLowerCase()).join(' ');
  if (FORBIDDEN[lang].some((w) => rest.includes(w.toLowerCase()))) return false;
  return true;
}

/** Form limits of an agency name (Iris): characters and words. */
const AGENCY_NAME_MAX: Record<LmLang, number> = { ko: 25, en: 60 };
const AGENCY_WORDS_MAX = 8;

/** The supplied issuer if usable, else null. Never fills in, guesses or transliterates anything. */
export function validIssuer(raw: IssuerInput | null | undefined): Issuer | null {
  if (!raw || typeof raw !== 'object' || !raw.agency || typeof raw.agency.ko !== 'string' || typeof raw.contact !== 'string') return null;
  const ko = raw.agency.ko.trim();
  const contact = raw.contact.trim();
  if (!ko || ko.length > AGENCY_MAX_CHARS || !ONE_LINE.test(ko) || !agencyLike(ko, 'ko')) return null;
  // a contact number is digits with optional hyphens; emergency numbers are not an agency's contact line
  if (!/^[0-9]+(-[0-9]+)*$/.test(contact) || contact.replace(/-/g, '').length < 3 || contact.replace(/-/g, '').length > 12) return null;
  if (['112', '119', '110'].includes(contact.replace(/-/g, ''))) return null;
  const enRaw = typeof raw.agency.en === 'string' ? raw.agency.en.trim() : '';
  const en = enRaw && enRaw.length <= AGENCY_EN_MAX_CHARS && EN_NAME.test(enRaw) && gsm7Length(enRaw).nonGsm.length === 0 && agencyLike(enRaw, 'en') ? enRaw : null;
  return { agency: { ko, en }, contact, forDrillOrReplay: raw.forDrillOrReplay === true };
}

/** The four fields of the draft decree (안 제49조② 1–4). */
export type DecreeField = 'area_people' | 'reason_timing' | 'shelter' | 'agency_contact';
export const DECREE_FIELDS: readonly DecreeField[] = ['area_people', 'reason_timing', 'shelter', 'agency_contact'];
export type ResidentOutput = 'head' | 'voice' | 'familyText' | 'familyScript';
export const RESIDENT_OUTPUTS: readonly ResidentOutput[] = ['head', 'voice', 'familyText', 'familyScript'];
/** Why an output has no agency/contact field. */
export type ContactStatus = 'included' | 'not_supplied' | 'no_english_name' | 'replay_not_marked' | 'over_length';
/**
 * Why a decree field is missing (Iris): not_applicable = no checked departure time, so no timing can be given;
 * not_supplied = the input lacks it (no issuer, no English name, no drill/replay mark, no nameable place or shelter);
 * does_not_fit = it exists but the output's length budget left it out.
 */
export type MissingReason = 'not_applicable' | 'not_supplied' | 'does_not_fit';

export interface DecreeReport {
  present: DecreeField[];
  missing: DecreeField[];
  /** one reason per missing field */
  reasons: Partial<Record<DecreeField, MissingReason>>;
  contact: ContactStatus;
}

const ASCII = /^[\x20-\x7E]+$/;

/** Why `field` is missing from an output (the field is known to be missing). */
function missingReason(p: MessagePlan, field: DecreeField, lang: LmLang, contact: ContactStatus, output: ResidentOutput): MissingReason {
  if (field === 'reason_timing') return p.kind === 'leave_by' && p.leaveByS !== null ? 'does_not_fit' : 'not_applicable';
  if (field === 'agency_contact') return contact === 'over_length' ? 'does_not_fit' : 'not_supplied';
  if (field === 'shelter') {
    // a shelter with only a Korean name is shown in Hangul in English text (owner decision), so it is supplied — except
    // in the English automated voice call, which never reads Hangul (interim, orchestrator): not supplied there
    const d = namedDestination(p);
    if (!d) return 'not_supplied';
    if (lang === 'en' && output === 'voice' && !d.en && !EN_VOICE_KOREAN_SHELTER) return 'not_supplied';
    return 'does_not_fit';
  }
  const name = p.input.origin.name?.[lang];
  // English outputs never carry a non-ASCII place name: such a name counts as not supplied in English
  return name && (lang === 'ko' || ASCII.test(name)) ? 'does_not_fit' : 'not_supplied';
}

const FIELD_LABEL: Record<LmLang, Record<DecreeField, string>> = {
  ko: { area_people: '대피 대상 지역·대상자', reason_timing: '대피 사유·시기', shelter: '대피장소 명칭·위치', agency_contact: '안내 기관 명칭·문의 연락처' },
  en: { area_people: 'area and people', reason_timing: 'reason and timing', shelter: 'shelter name and location', agency_contact: 'issuing agency and contact number' },
};
const REASON_LABEL: Record<LmLang, Record<MissingReason, string>> = {
  ko: { not_applicable: '해당 없음(확인된 출발 시각 없음)', not_supplied: '입력 없음', does_not_fit: '길이 제한으로 빠짐' },
  en: { not_applicable: 'not applicable (no checked departure time)', not_supplied: 'not supplied', does_not_fit: 'does not fit (length)' },
};
const OUTPUT_LABEL: Record<LmLang, Record<ResidentOutput, string>> = {
  ko: { head: '이장 방송', voice: '자동 음성전화', familyText: '가족 문자', familyScript: '가족 전화 대본' },
  en: { head: 'village head', voice: 'voice call', familyText: 'family text', familyScript: 'family call script' },
};

/** Staff-only text of the decree report: always shown when the check is on, never silent. */
export function decreeReportText(r: Record<ResidentOutput, DecreeReport>, lang: LmLang, extra: string[] = []): string {
  const head =
    lang === 'ko'
      ? '[직원용] 입법예고안(2026-11-04 공고) 제49조② 네 항목 점검 — 초안 기준이며, 항목이 빠진 안내를 보낼지는 담당 기관이 정합니다.'
      : '[Staff] Four items of draft Article 49(2) of the disaster management enforcement decree (notice of 2026-11-04) — a draft requirement as of that date; whether a notice missing an item may be sent is for officials to decide.';
  const lines = RESIDENT_OUTPUTS.map((o) => {
    const x = r[o];
    const body = x.missing.length === 0 ? (lang === 'ko' ? '네 항목 모두 있음' : 'all four present') : x.missing.map((f) => `${FIELD_LABEL[lang][f]}: ${REASON_LABEL[lang][x.reasons[f]!]}`).join('; ');
    return `${OUTPUT_LABEL[lang][o]} — ${body}`;
  });
  return [head, ...lines, ...extra].join('\n');
}

/** Which of the four fields a resident-facing text carries (by content, not by template). */
export function decreeFields(p: MessagePlan, text: string, lang: LmLang, issuer: Issuer | null): DecreeField[] {
  const out: DecreeField[] = [];
  const v = p.input.origin.name?.[lang];
  if (v && text.includes(v)) out.push('area_people');
  const hazard = lang === 'ko' ? text.includes('산불') : /wildfire/i.test(text);
  if (hazard && p.kind === 'leave_by' && p.leaveByS !== null && DEPARTURE_INSTRUCTION[lang].test(text)) out.push('reason_timing');
  const nd = namedDestination(p);
  const d = nd ? (lang === 'ko' ? nd.ko : nd.en || nd.ko) : null;
  if (d && text.includes(d)) out.push('shelter');
  const a = issuer?.agency[lang];
  if (issuer && a && text.includes(a) && text.includes(issuer.contact)) out.push('agency_contact');
  return out;
}

/** The contact line, or null when this language has no usable agency name. */
export function contactLine(iss: Issuer, lang: LmLang): string | null {
  if (lang === 'ko') return `문의: ${iss.agency.ko} ${iss.contact}`;
  return iss.agency.en ? `Contact: ${iss.agency.en} ${iss.contact}` : null;
}

/** The compact contact line of the family text (SMS), or null when this language has no usable agency name. */
export function contactSmsLine(iss: Issuer, lang: LmLang): string | null {
  if (lang === 'ko') return `문의 ${iss.agency.ko} ${iss.contact}`;
  return iss.agency.en ? `Contact ${iss.agency.en} ${iss.contact}` : null;
}

/**
 * The exact lines the builder inserts for a supplied issuer. Only these whole lines are masked before the word checks,
 * never the agency name on its own: the same word anywhere else in generated text is still caught, even when the
 * agency name is that word.
 */
export function issuerLines(iss: Issuer | null): string[] {
  if (!iss) return [];
  return (['ko', 'en'] as LmLang[]).flatMap((l) => [contactLine(iss, l), contactSmsLine(iss, l)]).filter((x): x is string => !!x);
}

/** Spoken length of a contact line; the number is read digit by digit (one syllable / one word per digit). */
export function contactSeconds(line: string, iss: Issuer, lang: LmLang): number {
  if (lang === 'en') return spokenSeconds(line, 'en');
  const digits = iss.contact.replace(/[^0-9]/g, '').length;
  return spokenSeconds(line.split(iss.contact).join(' '), 'ko') + digits / KO_SYLLABLES_PER_S;
}

export type Element = 'source' | 'hazard' | 'location' | 'time' | 'guidance';
export const ELEMENTS: readonly Element[] = ['source', 'hazard', 'location', 'time', 'guidance'];

export interface TaggedBlock {
  text: string;
  elements: Element[];
  /** dropped (last first) only while the core exceeds its budget */
  optional?: boolean;
  /** same elements in fewer words (e.g. without a long place name), used only while still over budget */
  short?: string;
}

export interface HeadScript {
  opener: string;
  core: string;
  closer: string;
  /** elements present in the core as assembled */
  elements: Element[];
  coreS: number;
  fullS: number;
  /** the same at the slower 2.5 syllables/s (Korean; English is unchanged) */
  coreSlowS: number;
  fullSlowS: number;
  /** the only exportable form: opener + core + closer (+ the supplied contact line), inseparable */
  script: string;
  /** the supplied agency/contact line after the closer (own budget HEAD_CONTACT_MAX_S), or null */
  contact?: string | null;
  contactS?: number;
}

export interface ChannelTexts {
  head: HeadScript;
  voice: string;
  familyText: string;
  familyScript: [string, string, string];
  /** staff / village-head only (never resident-facing) */
  staff: { dataAge: string; issueOrderBy: string; noOrder: string | null; decree?: string | null; readerNote?: string | null };
}

export interface ChannelSet {
  originId: string;
  kind: MessagePlan['kind'];
  /** the single destination any output may name (null: none may) */
  destinationName: Record<LmLang, string> | null;
  text: Record<LmLang, ChannelTexts>;
  violations: string[];
  /** the validated supplied issuer (its names and number are data: masked before the word checks), or null */
  issuer?: Issuer | null;
  /** draft-decree field report per resident output (only with draftDecreeCheck) */
  decree?: Record<LmLang, Record<ResidentOutput, DecreeReport>>;
}

const iso = (p: MessagePlan) => p.input.scenario.inputTimeIso;
const year = (p: MessagePlan) => kstParts(iso(p)).y;

function villageName(p: MessagePlan, lang: LmLang): string | null {
  const n = p.input.origin.name;
  return n ? n[lang] ?? null : null;
}

/** The one destination outputs may name: leave_by with a destination that does not vary, and a real name. */
export function namedDestination(p: MessagePlan): Record<LmLang, string> | null {
  if (p.kind !== 'leave_by' || !p.destination || p.destinationVaries || !p.destination.name) return null;
  const ko = p.destination.name.ko;
  const en = p.destination.name.en;
  return ko ? { ko, en: en && /^[\x20-\x7E]+$/.test(en) ? en : '' } : null;
}

// ------------------------------------------------------------------------------------------------ time wording

let STYLE: TimeStyle = 'clock';
/** live data age, spoken (set per build from nowIso; empty for replays) */
let AGE_KO = '';
let AGE_EN = '';

/** Spoken leave-by time, in the selected style (the only place a spoken leave-by time is worded). */
/** Days between the data date and the date of input + offset (KST). */
function dayShift(p: MessagePlan, offsetS: number): number {
  const a = kstParts(iso(p)), b = kstParts(iso(p), offsetS);
  return Math.round((Date.UTC(b.y, b.mo - 1, b.d) - Date.UTC(a.y, a.mo - 1, a.d)) / 86400000);
}

/** A clock time that names the day when it is not the data date (Mira N2: midnight crossing). */
function dayMarked(p: MessagePlan, offsetS: number, lang: LmLang, t: string): string {
  const d = dayShift(p, offsetS);
  if (d === 0) return t;
  if (lang === 'ko') return d === 1 ? `다음날 ${t}` : `${ymd(iso(p), offsetS)} ${t}`;
  return d === 1 ? `${t} (next day)` : `${t} (${ymd(iso(p), offsetS)})`;
}

/** Written HH:MM with the day marked when it crosses midnight. */
function hmDay(p: MessagePlan, offsetS: number, lang: LmLang): string {
  return dayMarked(p, offsetS, lang, hm(iso(p), offsetS));
}

function spokenLeaveBy(p: MessagePlan, lang: LmLang): string {
  const t = dayMarked(p, p.leaveByS!, lang, lang === 'ko' ? koSpokenTime(iso(p), p.leaveByS!) : enSpokenTime(iso(p), p.leaveByS!));
  if (STYLE === 'clock') return t;
  const m = Math.floor(p.leaveByS! / 60);
  return lang === 'ko' ? `자료 시각부터 ${m}분 뒤인 ${t}` : `${t}, ${m} minutes after the data time`;
}

// ------------------------------------------------------------------------------------------------ head script

function assemble(blocks: TaggedBlock[], lang: LmLang, maxS: number): TaggedBlock[] {
  const keep = blocks.map((b) => ({ ...b }));
  const len = () => spokenSeconds(keep.map((b) => b.text).join('\n'), lang);
  for (let i = keep.length - 1; i >= 0 && len() > maxS; i--) if (keep[i]!.optional) keep.splice(i, 1);
  // shorten from the end backwards, so the place name in the first block is the last thing dropped
  for (const b of [...keep].reverse()) {
    if (len() <= maxS) break;
    if (b.short) b.text = b.short;
  }
  return keep;
}

function framing(p: MessagePlan, lang: LmLang): { opener: string; closer: string } {
  const o: string[] = [];
  if (lang === 'ko') {
    if (p.input.replay) o.push(NOT_REAL.ko);
    const via = p.input.mock ? '모의 서버로 ' : '';
    const test = p.input.testData ? '시험용 ' : '';
    o.push(p.input.replay ? (via || test ? `${year(p)}년 기록을 ${via}재현한 ${test}자료입니다.` : `${year(p)}년 기록 재현입니다.`) : `${koSpokenTime(iso(p))} ${via ? '모의 서버 ' : ''}${test}자료이며 실시간이 아닙니다.${AGE_KO}`);
    return { opener: o.join('\n'), closer: OFFICIAL_FIRST.ko };
  }
  if (p.input.replay) o.push(NOT_REAL.en);
  o.push(p.input.replay ? `This is a replay of ${year(p)} records, not live.` : `Data from ${enSpokenTime(iso(p))}, not live.${AGE_EN}`);
  if (p.input.mock) o.push('Mock server data.');
  if (p.input.testData) o.push('Test computation data.');
  return { opener: o.join('\n'), closer: OFFICIAL_FIRST.en };
}

function headCoreBlocks(p: MessagePlan, lang: LmLang, koShelterInEn = true): TaggedBlock[] {
  const v = villageName(p, lang);
  const dest = namedDestination(p);
  const facility = p.input.origin.kind === 'facility';
  if (lang === 'ko') {
    const who = facility ? `${v ?? '이 시설'} 안내입니다.` : `${v ?? '이 마을'} 이장입니다.`;
    const b: TaggedBlock[] = [{ text: `${who} 산불 대피 안내입니다.`, short: `${facility ? '시설' : '이장'} 안내입니다. 이곳 산불 대피 안내입니다.`, elements: ['source', 'location', 'hazard'] }];
    if (p.kind === 'leave_by' && p.leaveByS !== null) {
      b.push({ text: `${spokenLeaveBy(p, 'ko')}까지 차로 출발하십시오.`, short: `${spokenLeaveBy(p, 'ko')}까지 출발하십시오.`, elements: ['time', 'guidance'] });
      if (dest) b.push({ text: `${dest.ko} 쪽입니다.`, elements: ['location'], optional: true });
      b.push({ text: facility ? '차가 부족하면 읍·면사무소에 알리십시오.' : '차가 없으면 이장에게 알리십시오.', short: facility ? '차가 부족하면 면사무소에 알리십시오.' : '차가 없으면 이장에게.', elements: ['guidance'] });
    } else if (p.kind === 'no_route') {
      b.push({ text: `${koSpokenTime(iso(p))} 자료로는 차로 나가는 확인된 길이 없습니다.`, short: `${koSpokenTime(iso(p))} 자료로는 확인된 길이 없습니다.`, elements: ['time'] });
      b.push({ text: '공식 지시를 따르고, 위급하면 119에 신고하십시오.', short: '공식 지시를 따르십시오. 위급하면 119입니다.', elements: ['guidance'] });
    } else {
      b.push({ text: `${koSpokenTime(iso(p))} 자료로는 대피 길을 확인하지 못했습니다.`, short: `${koSpokenTime(iso(p))} 자료로는 확인하지 못했습니다.`, elements: ['time'] });
      b.push({ text: '공식 대피 안내를 따르십시오.', elements: ['guidance'] });
    }
    return b;
  }
  const who = facility ? 'This is your facility.' : 'This is your village head.';
  const b: TaggedBlock[] = [{ text: `${who} Wildfire evacuation notice${v && /^[\x20-\x7E]+$/.test(v) ? ` for ${v}` : ' for this village'}.`, short: `${who} Wildfire evacuation notice for this place.`, elements: ['source', 'location', 'hazard'] }];
  if (p.kind === 'leave_by' && p.leaveByS !== null) {
    b.push({ text: `Leave by car by ${spokenLeaveBy(p, 'en')}.`, elements: ['time', 'guidance'] });
    // OWNER DECISION: no English name => the Korean (Hangul) shelter name, never a romanisation
    const en = dest ? dest.en || (koShelterInEn ? dest.ko : '') : '';
    if (en) b.push({ text: `Go toward ${en}.`, elements: ['location'], optional: true });
    b.push({ text: facility ? 'Short of cars? Tell the town office.' : 'No car? Tell the village head.', elements: ['guidance'] });
  } else if (p.kind === 'no_route') {
    b.push({ text: `Data from ${enSpokenTime(iso(p))} shows no checked road out.`, elements: ['time'] });
    b.push({ text: 'Follow official instructions. In an emergency, report to 119.', elements: ['guidance'] });
  } else {
    b.push({ text: `Data from ${enSpokenTime(iso(p))} could not check a road out.`, elements: ['time'] });
    b.push({ text: 'Follow official evacuation guidance.', elements: ['guidance'] });
  }
  return b;
}

export function headScript(p: MessagePlan, lang: LmLang, koShelterInEn = true): HeadScript {
  const { opener, closer } = framing(p, lang);
  const blocks = assemble(headCoreBlocks(p, lang, koShelterInEn), lang, HEAD_CORE_MAX_S);
  const core = blocks.map((b) => b.text).join('\n');
  const elements = ELEMENTS.filter((e) => blocks.some((b) => b.elements.includes(e)));
  const script = [opener, core, closer].join('\n');
  const coreS = spokenSeconds(core, lang);
  const fullS = spokenSeconds(script, lang);
  const slow = lang === 'ko' ? 3.0 / SLOW_SYLLABLES_PER_S : 1;
  return { opener, core, closer, elements, coreS, fullS, coreSlowS: coreS * slow, fullSlowS: fullS * slow, script };
}

// ------------------------------------------------------------------------------------------------ voice call (ARS)

export type ReplyCode = 'leaving' | 'acknowledged' | 'needs_help' | 'repeat' | 'unknown';

/** What a key press means for this origin's message kind. */
export function replyCode(kind: MessagePlan['kind'], key: string): ReplyCode {
  if (key === '1') return kind === 'leave_by' ? 'leaving' : 'acknowledged';
  if (key === '2') return 'needs_help';
  if (key === '3') return 'repeat';
  return 'unknown';
}

/**
 * English automated voice call: a Korean shelter name is NOT read (a TTS voice cannot be relied on to pronounce
 * Hangul); how it should be handled is open with Iris, so the call keeps its earlier behaviour and the shelter field
 * is reported as missing.
 */
export const EN_VOICE_KOREAN_SHELTER = false;
export const VOICE_EN_SHELTER_POINTER = 'The shelter has no English name; it is named in the Korean message.';
/** Staff note for a human reader of the English village-head script (orchestrator: interim). */
export function headReaderNote(p: MessagePlan): string | null {
  const d = namedDestination(p);
  return d && !d.en ? `Reader: say the shelter name in Korean: ${d.ko}` : null;
}

function voice(p: MessagePlan, lang: LmLang): string {
  const h = headScript(p, lang, EN_VOICE_KOREAN_SHELTER);
  const leave = p.kind === 'leave_by';
  if (lang === 'ko') {
    return [
      h.opener,
      '산불 대피 안내 자동 전화입니다.',
      h.core,
      `${leave ? '지금 출발하시면' : '안내를 들으셨으면'} 1번, 차가 없거나 혼자 이동이 어려우면 2번, 다시 들으시려면 3번을 누르십시오.`,
      '2번을 누르시면 이장과 읍·면사무소에 전달됩니다.',
      h.closer,
    ].join('\n');
  }
  const d = namedDestination(p);
  return [
    h.opener,
    'This is an automated wildfire evacuation call.',
    h.core,
    // interim (orchestrator, reported to the owner): the English call never reads a Korean shelter name; it points to
    // the Korean message instead. GAP: an English-only listener who gets only this call has no destination.
    ...(d && !d.en && !EN_VOICE_KOREAN_SHELTER ? [VOICE_EN_SHELTER_POINTER] : []),
    `Press 1 ${leave ? 'if you are leaving now' : 'if you heard this notice'}, 2 if you have no car or cannot leave on your own, 3 to hear this again.`,
    'If you press 2, your answer is passed to the village head and the town office.',
    h.closer,
  ].join('\n');
}

// ------------------------------------------------------------------------------------------------ family relay

function tag(p: MessagePlan, lang: LmLang): string {
  const m = p.input.mock, t = p.input.testData;
  if (lang === 'ko') return m && t ? '[MOCK시험]' : m ? '[MOCK]' : t ? '[시험자료]' : p.input.replay ? '[기록재현]' : '';
  return [p.input.replay ? 'REPLAY' : '', m ? 'MOCK' : '', t ? 'TEST' : ''].filter(Boolean).join(' ');
}

function familyText(p: MessagePlan, lang: LmLang): string {
  const full = familyTextWith(p, lang, villageName(p, lang));
  const fits = lang === 'ko' ? eucKrBytes(full).bytes <= SMS_KO_MAX_BYTES : gsm7Length(full).chars <= SMS_EN_MAX_GSM7;
  return fits ? full : familyTextWith(p, lang, null);
}

function familyTextWith(p: MessagePlan, lang: LmLang, v: string | null): string {
  if (lang === 'ko') {
    const head = `${tag(p, 'ko')}${v ?? '마을'} 산불`;
    const body = p.kind === 'leave_by' && p.leaveByS !== null ? `모델상 ${hmDay(p, p.leaveByS, 'ko')}까지 차로 출발` : p.kind === 'no_route' ? '모델상 경로 없음, 위급 시 119' : '모델 미확인, 공식안내 따름';
    return `${head}\n${body}\n${OFFICIAL_FIRST_SMS.ko}·${MODEL_NOT_LIVE_SMS.ko}`;
  }
  const head = `${tag(p, 'en')} ${v && /^[\x20-\x7E]+$/.test(v) ? v : 'Village'} wildfire`.trim();
  const body = p.kind === 'leave_by' && p.leaveByS !== null ? `Model: leave by car by ${hmDay(p, p.leaveByS, 'en')}` : p.kind === 'no_route' ? 'Model: no route. Emergency: 119' : 'Model: not checked. Follow official guidance';
  return `${head}\n${body}\n${OFFICIAL_FIRST_SMS.en} ${MODEL_NOT_LIVE_SMS.en}`;
}

function familyScript(p: MessagePlan, lang: LmLang): [string, string, string] {
  const v = villageName(p, lang);
  const dest = namedDestination(p);
  const replay = p.input.replay;
  if (lang === 'ko') {
    const l1 = `[이름]님, ${v ?? '마을'} 산불 대피 안내입니다. ${replay ? '실제 상황이 아니라 기록 재현이며, ' : ''}컴퓨터 예측 계산 자료입니다.`;
    const l2 =
      p.kind === 'leave_by' && p.leaveByS !== null
        ? `${spokenLeaveBy(p, 'ko')}까지 차로 출발하셔야 합니다${dest ? `. ${dest.ko} 쪽입니다` : ''}.`
        : p.kind === 'no_route'
          ? `${koSpokenTime(iso(p))} 자료로는 차로 나가는 확인된 길이 없습니다.`
          : `${koSpokenTime(iso(p))} 자료로는 대피 길을 확인하지 못했습니다.`;
    const l3 = `차가 없으면 이장에게 알리시고, 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오. ${OFFICIAL_FIRST.ko}`;
    return [l1, l2, l3];
  }
  const l1 = `[Name], this is a wildfire evacuation notice for ${v && /^[\x20-\x7E]+$/.test(v) ? v : 'your village'}. ${replay ? 'It is a replay of records, not a real emergency, ' : ''}from a computer forecast, not live.`;
  const l2 =
    p.kind === 'leave_by' && p.leaveByS !== null
      ? `Leave by car by ${spokenLeaveBy(p, 'en')}${dest ? `, toward ${dest.en || dest.ko}` : ''}.`
      : p.kind === 'no_route'
        ? `Data from ${enSpokenTime(iso(p))} shows no checked road out by car.`
        : `Data from ${enSpokenTime(iso(p))} could not check a road out.`;
  const l3 = `No car? Tell the village head, and follow official instructions. In an emergency, report to 119. ${OFFICIAL_FIRST.en}`;
  return [l1, l2, l3];
}

// ------------------------------------------------------------------------------------------------ no order yet

/** True only for an explicit, attributed, currently valid `not_issued` status. */
export function orderNotIssued(o: OrderStatusInput | null | undefined, nowIso: string): boolean {
  if (!o || o.status !== 'not_issued' || !o.suppliedBy || !o.suppliedBy.trim()) return false;
  const now = Date.parse(nowIso), from = Date.parse(o.suppliedAtIso), to = Date.parse(o.expiresAtIso);
  return Number.isFinite(now) && Number.isFinite(from) && Number.isFinite(to) && from <= now && now < to;
}

/** Staff / village-head output (never resident-facing): "no order yet" with the planning frame and data age. */
function noOrder(p: MessagePlan, lang: LmLang, opt: ChannelOptions): string | null {
  const o = opt.orderStatus;
  if (!orderNotIssued(o, opt.nowIso)) return null;
  const v = villageName(p, lang);
  const age = dataAge(p, opt.nowIso, lang);
  if (lang === 'ko') {
    const body =
      p.kind === 'leave_by' && p.leaveByS !== null
        ? `모델 계산으로는 ${hmDay(p, p.leaveByS, 'ko')}까지 출발해야 하는 곳입니다.`
        : p.kind === 'no_route'
          ? '모델 계산으로는 확인된 대피 길이 없는 곳입니다.'
          : '모델 계산으로 확인하지 못한 곳입니다.';
    return [
      `[이장·담당자용 · ${longTag(p, 'ko')}${MODEL_NOT_LIVE.ko}]`,
      `${v ?? '이 마을'}: 아직 공식 대피 명령은 없습니다(명령 상태 입력: ${o!.suppliedBy}, ${koDate(o!.suppliedAtIso)}).`,
      body,
      '명령이 없다고 위험이 없는 것은 아닙니다.',
      age,
      OFFICIAL_FIRST.ko,
    ].join('\n');
  }
  const body =
    p.kind === 'leave_by' && p.leaveByS !== null
      ? `Model: this place must leave by ${hmDay(p, p.leaveByS, 'en')}.`
      : p.kind === 'no_route'
        ? 'Model: no checked road out.'
        : 'Model: not checked.';
  return [
    `[For village head / staff · ${longTag(p, 'en')}${MODEL_NOT_LIVE.en}]`,
    `${v && /^[\x20-\x7E]+$/.test(v) ? v : 'This village'}: no official order yet (order status from ${o!.suppliedBy}, ${enDate(o!.suppliedAtIso)}).`,
    body,
    'No order yet is not an all-clear.',
    age,
    OFFICIAL_FIRST.en,
  ].join('\n');
}

/** Tag naming the replay and every marker. */
function longTag(p: MessagePlan, lang: LmLang): string {
  const parts = lang === 'ko'
    ? [p.input.replay ? '기록재현' : '', p.input.mock ? 'MOCK' : '', p.input.testData ? '시험자료' : '']
    : [p.input.replay ? 'REPLAY' : '', p.input.mock ? 'MOCK' : '', p.input.testData ? 'TEST' : ''];
  const t = parts.filter(Boolean).join(lang === 'ko' ? '·' : ' ');
  return t ? `${t} · ` : '';
}

// ------------------------------------------------------------------------------------------------ staff fields

export function dataAge(p: MessagePlan, nowIso: string, lang: LmLang): string {
  const t0 = iso(p);
  if (p.input.replay) return lang === 'ko' ? `자료 시각 ${koDate(t0)} · ${year(p)}년 기록 재현 자료` : `Data time ${enDate(t0)} · replay of ${year(p)} records`;
  const ageMin = Math.floor((Date.parse(nowIso) - Date.parse(t0)) / 60000);
  if (!Number.isFinite(ageMin) || ageMin < 0) return lang === 'ko' ? `자료 시각 ${koDate(t0)} · 자료 나이 확인 불가` : `Data time ${enDate(t0)} · data age unknown`;
  return lang === 'ko' ? `자료 시각 ${koDate(t0)} · ${ageMin}분 전 자료` : `Data time ${enDate(t0)} · ${ageMin} min old`;
}

export function issueOrderByText(p: MessagePlan, v: IssueOrderBy | null | undefined, lang: LmLang): string {
  const head = lang === 'ko' ? '공식 명령 발령 시한(모델 계산, 전달 지연은 가정값)' : 'Issue order by (model; delivery latencies are assumptions)';
  const none = lang === 'ko' ? `${head}: 산출되지 않음` : `${head}: not computed`;
  if (!v) return none;
  if (v.leaveByS === null) {
    // the field's model no-route; shown only when the planner agrees (never a time)
    if (p.kind !== 'no_route') return lang === 'ko' ? `${head}: 플래너 결과와 불일치 — 산출되지 않음` : `${head}: disagrees with the planner — not computed`;
    return lang === 'ko' ? `${head}: 모델상 확인된 경로 없음 — 시한 없음, 명령을 미루지 마십시오` : `${head}: no checked route in the model — no deadline; do not delay the order`;
  }
  if (p.kind !== 'leave_by' || !v.issueByS) return lang === 'ko' ? `${head}: 플래너 결과와 불일치 — 산출되지 않음` : `${head}: disagrees with the planner — not computed`;
  const { low, median, high } = v.issueByS;
  const H = p.input.scenario.horizonS;
  // Mira N6: the field's leave-by is exact and the planner's is a sweep value, so the field may be later but never
  // earlier; every issue-by must be no later than the leave-by the RESIDENTS are given (the planner's).
  // Mira N7: issue-by = leave-by − latency, so a shorter latency gives a later time: low ≥ median ≥ high.
  const valid = (x: number) => Number.isInteger(x) && x <= v.leaveByS! && x <= p.leaveByS!;
  if (!Number.isInteger(v.leaveByS) || v.leaveByS < 0 || v.leaveByS > H || ![low, median, high].every(valid)) {
    return lang === 'ko' ? `${head}: 입력값 범위 오류 — 산출되지 않음` : `${head}: input out of range — not computed`;
  }
  if (p.leaveByS === null || v.leaveByS < p.leaveByS) {
    return lang === 'ko' ? `${head}: 플래너 결과와 불일치 — 산출되지 않음` : `${head}: disagrees with the planner — not computed`;
  }
  if (!(low >= median && median >= high)) {
    return lang === 'ko' ? `${head}: 지연 가정 순서 오류 — 산출되지 않음` : `${head}: latency settings out of order — not computed`;
  }
  const show = (x: number) => (x < 0 ? (lang === 'ko' ? '이미 지남' : 'already past') : hmDay(p, x, lang));
  return lang === 'ko'
    ? `${head}: 지연 짧음 ${show(low)} · 중간 ${show(median)} · 김 ${show(high)}`
    : `${head}: short latency ${show(low)} · median ${show(median)} · long ${show(high)}`;
}

// ------------------------------------------------------------------------------------------------ assembly + checks

export function buildChannels(p: MessagePlan, opt: ChannelOptions): ChannelSet {
  const text = {} as Record<LmLang, ChannelTexts>;
  STYLE = opt.timeStyle ?? 'clock';
  const ageMin = Math.floor((Date.parse(opt.nowIso) - Date.parse(iso(p))) / 60000);
  const liveAge = !p.input.replay && Number.isFinite(ageMin) && ageMin >= 0;
  AGE_KO = liveAge ? ` ${ageMin}분 전 자료입니다.` : '';
  AGE_EN = liveAge ? ` The data is ${ageMin} minutes old.` : '';
  for (const lang of ['ko', 'en'] as LmLang[]) {
    text[lang] = {
      head: headScript(p, lang),
      voice: voice(p, lang),
      familyText: familyText(p, lang),
      familyScript: familyScript(p, lang),
      staff: { dataAge: dataAge(p, opt.nowIso, lang), issueOrderBy: issueOrderByText(p, opt.issueOrderBy, lang), noOrder: noOrder(p, lang, opt) },
    };
  }
  const iss = validIssuer(opt.issuer);
  const contact = {} as Record<LmLang, Record<ResidentOutput, ContactStatus>>;
  for (const lang of ['ko', 'en'] as LmLang[]) {
    const t = text[lang];
    const line = iss ? contactLine(iss, lang) : null;
    const nonLive = p.input.replay || p.input.mock || p.input.testData;
    const base: ContactStatus = !iss ? 'not_supplied' : nonLive && !iss.forDrillOrReplay ? 'replay_not_marked' : line === null ? 'no_english_name' : 'included';
    const c: Record<ResidentOutput, ContactStatus> = { head: base, voice: base, familyText: base, familyScript: base };
    if (iss && line !== null && base === 'included') {
      const h = t.head;
      const sec = contactSeconds(line, iss, lang);
      if (sec <= HEAD_CONTACT_MAX_S) {
        h.contact = line;
        h.contactS = sec;
        h.script = [h.opener, h.core, h.closer, line].join('\n');
      } else c.head = 'over_length';
      t.voice = `${t.voice}\n${line}`;
      t.familyScript = [t.familyScript[0], t.familyScript[1], `${t.familyScript[2]} ${line}`];
      const withLine = `${t.familyText}\n${contactSmsLine(iss, lang)}`;
      const fits = lang === 'ko' ? eucKrBytes(withLine).bytes <= SMS_KO_MAX_BYTES && eucKrBytes(withLine).unencodable.length === 0 : gsm7Length(withLine).chars <= SMS_EN_MAX_GSM7 && gsm7Length(withLine).nonGsm.length === 0;
      if (fits) t.familyText = withLine;
      else c.familyText = 'over_length';
    }
    contact[lang] = c;
  }
  text.en.staff.readerNote = text.en.head.script.includes(namedDestination(p)?.ko ?? '\u0000') ? headReaderNote(p) : null;
  const set: ChannelSet = { originId: p.input.origin.id, kind: p.kind, destinationName: namedDestination(p), text, violations: [], issuer: iss };
  set.violations = checkChannels(p, set);
  if (opt.draftDecreeCheck) {
    const decree = {} as Record<LmLang, Record<ResidentOutput, DecreeReport>>;
    for (const lang of ['ko', 'en'] as LmLang[]) {
      const t = text[lang];
      const texts: Record<ResidentOutput, string> = { head: t.head.script, voice: t.voice, familyText: t.familyText, familyScript: t.familyScript.join('\n') };
      const r = {} as Record<ResidentOutput, DecreeReport>;
      for (const o of RESIDENT_OUTPUTS) {
        const present = decreeFields(p, texts[o], lang, iss);
        const missing = DECREE_FIELDS.filter((f) => !present.includes(f));
        const reasons: Partial<Record<DecreeField, MissingReason>> = {};
        for (const f of missing) reasons[f] = missingReason(p, f, lang, contact[lang][o], o);
        r[o] = { present, missing, reasons, contact: contact[lang][o] };
      }
      decree[lang] = r;
      const h = t.head;
      const extra = [
        lang === 'ko'
          ? `이장 방송 길이: 기본 ${h.fullS.toFixed(1)}초(한도 ${HEAD_FULL_MAX_S}초) + 문의 ${(h.contactS ?? 0).toFixed(1)}초(한도 ${HEAD_CONTACT_MAX_S}초) = ${(h.fullS + (h.contactS ?? 0)).toFixed(1)}초`
          : `Village-head script length: ${h.fullS.toFixed(1)} s (limit ${HEAD_FULL_MAX_S} s) + contact ${(h.contactS ?? 0).toFixed(1)} s (limit ${HEAD_CONTACT_MAX_S} s) = ${(h.fullS + (h.contactS ?? 0)).toFixed(1)} s`,
      ];
      const nd = namedDestination(p);
      if (nd && !nd.en && !EN_VOICE_KOREAN_SHELTER)
        extra.push(
          lang === 'ko'
            ? '공백: 영어 자동 음성전화는 한글 대피장소 이름을 읽지 않습니다. 그 전화만 받는 영어 사용자는 대피장소를 알 수 없습니다.'
            : 'Gap: the English automated voice call does not read the Korean shelter name; an English-only listener who gets only that call has no destination.',
        );
      t.staff.decree = decreeReportText(r, lang, extra);
    }
    set.decree = decree;
    set.violations = checkChannels(p, set);
  }
  return set;
}

/** True when no violation names this output (an output with a violation is withheld). */
export function outputWithheld(set: ChannelSet, lang: LmLang, output: ResidentOutput): boolean {
  return set.violations.some((v) => v.startsWith(`${lang}.${output}:`) || v.startsWith(`${lang}.${output}.`));
}

/**
 * Names from data, masked before the word checks (a village called 안전마을 must not trip "안전"; an agency called
 * 재난안전과 must not either). Supplied proper nouns only: place names, and the exact contact lines built from the
 * supplied issuer (issuerLines).
 */
function inserted(p: MessagePlan, iss: Issuer | null = null): string[] {
  const out: string[] = [];
  for (const t of [p.input.origin.name, p.destination?.name]) if (t) for (const s of [t.ko, t.en]) if (s) out.push(s);
  out.push(...issuerLines(iss));
  return out.sort((a, b) => b.length - a.length);
}

/** Every rule violation of every output, each prefixed with its output (e.g. "ko.head.core: …"). */
export function checkChannels(p: MessagePlan, set: ChannelSet): string[] {
  const v: string[] = [];
  const iss = set.issuer ?? null;
  const names = inserted(p, iss);
  const dataHm = hm(iso(p));
  for (const lang of ['ko', 'en'] as LmLang[]) {
    const t = set.text[lang];
    const outs: [string, string][] = [
      ['head', t.head.script],
      ['voice', t.voice],
      ['familyText', t.familyText],
      ['familyScript', t.familyScript.join('\n')],
      ['staff', `${t.staff.dataAge}\n${t.staff.issueOrderBy}`],
      ...(t.staff.noOrder !== null ? ([['staff.noOrder', t.staff.noOrder]] as [string, string][]) : []),
      ...(t.staff.decree ? ([['staff.decree', t.staff.decree]] as [string, string][]) : []),
      ...(t.staff.readerNote ? ([['staff.readerNote', t.staff.readerNote]] as [string, string][]) : []),
    ];
    for (const [name, s] of outs) {
      const id = `${lang}.${name}`;
      const masked = maskData(s, names).toLowerCase();
      for (const w of FORBIDDEN[lang]) if (masked.includes(w.toLowerCase())) v.push(`${id}: forbidden word "${w}"`);
      if (!name.startsWith('staff') && RESIDENT_119_NOW[lang].test(s)) v.push(`${id}: tells residents to call 119 now`);
      if (p.kind !== 'leave_by' && DEPARTURE_INSTRUCTION[lang].test(maskData(s, names))) v.push(`${id}: departure instruction without a checked window`);
      if (p.kind !== 'leave_by') {
        const extra = clockTimes(maskData(s, names)).filter((c) => c !== dataHm);
        if (extra.length) v.push(`${id}: clock time ${extra.join(',')} without a checked window`);
      }
      if (!['staff', 'staff.decree', 'staff.readerNote'].includes(name) && !s.includes(OFFICIAL_FIRST[lang]) && !s.includes(OFFICIAL_FIRST_SMS[lang])) v.push(`${id}: missing official-orders-first`);
      const markerInstead = lang === 'ko' && name === 'familyText' && (p.input.mock || p.input.testData) && /MOCK|시험자료/.test(s);
      if (p.input.replay && !['staff', 'staff.decree', 'staff.readerNote'].includes(name) && !markerInstead && !(lang === 'ko' ? /재현/.test(s) : /replay/i.test(s))) v.push(`${id}: missing replay note`);
      // destination consistency: only the plan's own destination, and only when it may be named. The allowed name
      // and the origin's name are masked first (a destination name may be a substring of the allowed one).
      const allowed = [set.destinationName?.[lang], ...(lang === 'en' ? [set.destinationName?.ko] : []), p.input.origin.name?.[lang], ...issuerLines(iss)].filter((n): n is string => !!n).sort((a, b) => b.length - a.length);
      const rest = maskData(s, allowed);
      const dests = Object.values(p.input.destinations)
        .flatMap((d) => (d.name ? (lang === 'en' ? [d.name.en, d.name.ko] : [d.name[lang]]) : []))
        .filter((n): n is string => !!n && n.length > 1);
      for (const d of new Set(dests)) if (rest.includes(d)) v.push(`${id}: names destination "${d}" the plan does not allow`);
      // English resident outputs carry Hangul only as the plan's own shelter name (owner decision), nowhere else
      if (lang === 'en' && !name.startsWith('staff')) {
        const ko = set.destinationName?.ko;
        const left = ko ? s.split(ko).join('') : s;
        if (/[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]/.test(left)) v.push(`${id}: Hangul outside the shelter name`);
      }
    }
    if (t.head.coreS > HEAD_CORE_MAX_S) v.push(`${lang}.head.core: ${t.head.coreS.toFixed(1)} s > ${HEAD_CORE_MAX_S} s`);
    if (t.head.fullS > HEAD_FULL_MAX_S) v.push(`${lang}.head: ${t.head.fullS.toFixed(1)} s > ${HEAD_FULL_MAX_S} s`);
    if ((t.head.contactS ?? 0) > HEAD_CONTACT_MAX_S) v.push(`${lang}.head: contact line ${t.head.contactS!.toFixed(1)} s > ${HEAD_CONTACT_MAX_S} s`);
    const missing = ELEMENTS.filter((e) => !t.head.elements.includes(e));
    if (missing.length) v.push(`${lang}.head.core: missing elements ${missing.join(',')}`);
    if (lang === 'ko') {
      const b = eucKrBytes(t.familyText);
      if (b.unencodable.length) v.push(`ko.familyText: unencodable ${b.unencodable.join('')}`);
      if (b.bytes > SMS_KO_MAX_BYTES) v.push(`ko.familyText: ${b.bytes} bytes > ${SMS_KO_MAX_BYTES}`);
    } else {
      const g = gsm7Length(t.familyText);
      if (g.nonGsm.length) v.push(`en.familyText: not GSM-7 ${g.nonGsm.join('')}`);
      if (g.chars > SMS_EN_MAX_GSM7) v.push(`en.familyText: ${g.chars} > ${SMS_EN_MAX_GSM7}`);
    }
    if (t.staff.noOrder !== null && !t.staff.noOrder.includes(MODEL_NOT_LIVE[lang])) v.push(`${lang}.staff.noOrder: missing planning-only frame`);
    if (t.familyScript.length !== 3) v.push(`${lang}.familyScript: not three lines`);
  }
  return v;
}

// ------------------------------------------------------------------------------------------------ transport-need list

export interface Reply {
  originId: string;
  /** opaque household / contact label from the call system (never shown to residents) */
  contact: string;
  key: string;
  receivedAtIso: string;
}

export interface NeedRow {
  originId: string;
  contact: string;
  code: ReplyCode;
  kind: MessagePlan['kind'];
  /** leave-by offset (s) — only for kind leave_by */
  leaveByS: number | null;
  /** "no checked leave-by — check first" for no_route / unresolved / partial / unknown origin */
  checkFirst: boolean;
  urgencyRank: number | null;
  receivedAtIso: string;
}

/**
 * Staff list of replies that need follow-up (key 2, and unknown keys — flagged). SYNTHETIC households only in this
 * repository; in practice the list would be held by the 읍·면사무소 staff and the 이장 who run the call system.
 * Two sections, in the planner's own order so the kit and the planner never disagree:
 *  - topSection: places that need a human decision, not a time — model no-route, then unresolved (including origins
 *    with no plan), then partial; within each, planner urgency rank, then reply time, then contact;
 *  - byDeadline: leave_by places, ascending by T; ties by urgency rank, reply time, contact.
 */
export function transportNeedList(replies: Reply[], plans: Record<string, MessagePlan>): { topSection: NeedRow[]; byDeadline: NeedRow[] } {
  const rows: NeedRow[] = [];
  for (const r of replies) {
    const p = plans[r.originId];
    const kind = p?.kind ?? 'unresolved';
    const code = replyCode(kind, r.key.trim());
    if (code !== 'needs_help' && code !== 'unknown') continue;
    const leaveByS = p && p.kind === 'leave_by' ? p.leaveByS : null;
    rows.push({ originId: r.originId, contact: r.contact, code, kind, leaveByS, checkFirst: leaveByS === null, urgencyRank: p?.input.urgencyRank ?? null, receivedAtIso: r.receivedAtIso });
  }
  const inf = Number.POSITIVE_INFINITY;
  const KIND_ORDER: Record<string, number> = { no_route: 0, unresolved: 1, partial: 2, leave_by: 3 };
  const tie = (a: NeedRow, b: NeedRow) =>
    (a.urgencyRank ?? inf) - (b.urgencyRank ?? inf) || a.receivedAtIso.localeCompare(b.receivedAtIso) || a.contact.localeCompare(b.contact);
  const top = rows.filter((r) => r.checkFirst).sort((a, b) => KIND_ORDER[a.kind]! - KIND_ORDER[b.kind]! || tie(a, b));
  const dated = rows.filter((r) => !r.checkFirst).sort((a, b) => a.leaveByS! - b.leaveByS! || tie(a, b));
  return { topSection: top, byDeadline: dated };
}
