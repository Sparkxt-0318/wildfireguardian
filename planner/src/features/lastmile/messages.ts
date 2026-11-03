/**
 * Builds every field message of one origin: Korean (source) and English SMS, long text, village
 * broadcast script, family call script and the printable card. Deterministic templates only — no
 * model, no network. The result carries its length metrics and the list of rule violations found
 * by ./checks.ts (the panel and the CSV withhold each output that has one: outputOk).
 */
import { compactUtc } from '../../domain/clock';
import type { Verdict } from '../../domain/types';
import { checkFieldMessages } from './checks';
import { assembleSpoken, cardText, type CardContent, type TemplateSet } from './compose';
import { BROADCAST_MAX_S, eucKrBytes, gsm7Length, spokenSeconds } from './encoding';
import type { LmReason } from './explanation';
import { messagePlan, type MessageKind, type MessagePlan } from './plan';
import { LANGUAGES, SHIPPED_LANGS, type OutputKind } from './strings';
import { EN } from './templates/en';
import { KO } from './templates/ko';
import type { ExplanationFile, LastMileInput, LmLang } from './types';

export const TEMPLATES: Record<LmLang, TemplateSet> = { ko: KO, en: EN };

/** Languages offered: shipped AND enabled in the registry (a language under review stays out). */
export function enabledLangs(): LmLang[] {
  return SHIPPED_LANGS.filter((l) => LANGUAGES[l].enabled);
}

export interface FieldTexts {
  sms: string;
  lms: string;
  broadcast: string;
  call: string;
  card: CardContent;
}

export interface FieldMetrics {
  /** Korean SMS / long text: strict EUC-KR bytes; English SMS: GSM-7 characters */
  smsUnits: number;
  smsLimit: number;
  smsUnit: 'bytes' | 'chars';
  /** characters the SMS encoding cannot carry (must be empty) */
  smsBad: string[];
  lmsBytes: number;
  lmsBad: string[];
  broadcastS: number;
  callS: number;
}

/** The deadline explanation file a reason line comes from (CSV "이유 자료 / Reason data"). */
export interface ReasonSource {
  /** file name under data/explanations/ */
  file: string;
  /** the file's provenance.code_commit / generated_at, when it states them */
  codeCommit: string | null;
  generatedAtIso: string | null;
}

export interface FieldMessages {
  originId: string;
  urgencyRank: number;
  kind: MessageKind;
  verdict: Verdict;
  leaveByS: number | null;
  reason: LmReason | null;
  /** where the reason line comes from (null without a reason line) */
  reasonSource: ReasonSource | null;
  plan: MessagePlan;
  text: Record<LmLang, FieldTexts>;
  metrics: Record<LmLang, FieldMetrics>;
  /** strings from data (place and road names) inserted into the texts; masked by the word checks */
  inserted: string[];
  /** rule violations (empty when every output passed) */
  violations: string[];
}

function insertedStrings(plan: MessagePlan): string[] {
  const out = new Set<string>();
  const add = (s: string | null | undefined) => {
    if (s && s.trim()) out.add(s.trim());
  };
  const o = plan.input.origin;
  for (const l of SHIPPED_LANGS) {
    add(o.name?.[l]);
    add(o.display[l]);
    add(plan.input.region.name[l]);
    if (plan.destination) {
      add(plan.destination.name?.[l]);
      add(plan.destination.display[l]);
    }
    const r = plan.reason;
    if (r && r.kind === 'all_exits_blocked') for (const e of r.exits) add(e.text[l]);
    else if (r && 'road' in r) add(r.road.text[l]);
    // a live result's compute host, as the API reports it
    add(plan.input.provenance.host?.[l]);
  }
  add(plan.input.scenario.scenarioSetId);
  return [...out].sort((a, b) => b.length - a.length);
}

function explanationSource(f: ExplanationFile): ReasonSource {
  const str = (v: unknown) => (typeof v === 'string' && v.length > 0 ? v : null);
  return { file: `${f.region_id}__${compactUtc(f.input_time)}.json`, codeCommit: str(f.provenance?.code_commit), generatedAtIso: str(f.provenance?.generated_at) };
}

function metricsOf(lang: LmLang, t: FieldTexts): FieldMetrics {
  const sms = LANGUAGES[lang].sms;
  let smsUnits: number;
  let smsBad: string[];
  if (sms.encoding === 'gsm7') {
    const g = gsm7Length(t.sms);
    smsUnits = g.chars;
    smsBad = g.nonGsm;
  } else {
    const b = eucKrBytes(t.sms);
    smsUnits = b.bytes;
    smsBad = b.verified ? b.unencodable : ['(EUC-KR decoder unavailable)'];
  }
  const l = eucKrBytes(t.lms);
  return {
    smsUnits,
    smsLimit: sms.limit,
    smsUnit: sms.unit,
    smsBad,
    lmsBytes: l.bytes,
    lmsBad: l.verified ? l.unencodable : ['(EUC-KR decoder unavailable)'],
    broadcastS: Math.round(spokenSeconds(t.broadcast, lang) * 10) / 10,
    callS: Math.round(spokenSeconds(t.call, lang) * 10) / 10,
  };
}

/** All messages of one origin. `explanation` is the scenario's explanation file, or null. */
export function buildFieldMessages(input: LastMileInput, explanation: ExplanationFile | null = null): FieldMessages {
  const plan = messagePlan(input, explanation);
  const text = {} as Record<LmLang, FieldTexts>;
  const metrics = {} as Record<LmLang, FieldMetrics>;
  for (const lang of SHIPPED_LANGS) {
    const T = TEMPLATES[lang];
    const t: FieldTexts = {
      sms: T.sms(plan),
      lms: T.lms(plan),
      broadcast: assembleSpoken(T.broadcastBlocks(plan), lang, BROADCAST_MAX_S),
      call: T.call(plan),
      card: T.card(plan),
    };
    text[lang] = t;
    metrics[lang] = metricsOf(lang, t);
  }
  const fm: FieldMessages = {
    originId: input.origin.id,
    urgencyRank: input.urgencyRank,
    kind: plan.kind,
    verdict: plan.verdict,
    leaveByS: plan.leaveByS,
    reason: plan.reason,
    reasonSource: plan.reason && explanation ? explanationSource(explanation) : null,
    plan,
    text,
    metrics,
    inserted: insertedStrings(plan),
    violations: [],
  };
  fm.violations = checkFieldMessages(fm);
  return fm;
}

const OUTPUT_OF = /^(ko|en)\.(sms|lms|broadcast|call|card):/;

/**
 * Fail closed per OUTPUT: true when no rule check failed for this language and output. Every rule is
 * checked for each output on its own (checks.ts prefixes each violation "<lang>.<output>:"), so a
 * passing output may be used even when another output of the origin failed; a violation that names
 * no output blocks every output of the origin.
 */
export function outputOk(fm: FieldMessages, lang: LmLang, kind: OutputKind): boolean {
  return fm.violations.every((v) => {
    const m = OUTPUT_OF.exec(v);
    return m !== null && !(m[1] === lang && m[2] === kind);
  });
}

/** Every output of one language as plain text, in a fixed order (CSV, checks). */
export function allTexts(fm: FieldMessages, lang: LmLang): Record<'sms' | 'lms' | 'broadcast' | 'call' | 'card', string> {
  const t = fm.text[lang];
  return { sms: t.sms, lms: t.lms, broadcast: t.broadcast, call: t.call, card: cardText(t.card) };
}
