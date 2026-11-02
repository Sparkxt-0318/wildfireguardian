/**
 * Builds every field message of one origin: Korean (source) and English SMS, long text, village
 * broadcast script, family call script and the printable card. Deterministic templates only — no
 * model, no network. The result carries its length metrics and the list of rule violations found
 * by ./checks.ts (the panel refuses to offer a text that has any).
 */
import type { Verdict } from '../../domain/types';
import { checkFieldMessages } from './checks';
import { assembleSpoken, cardText, type CardContent, type TemplateSet } from './compose';
import { BROADCAST_MAX_S, eucKrBytes, gsm7Length, spokenSeconds } from './encoding';
import type { LmReason } from './explanation';
import { messagePlan, type MessageKind, type MessagePlan } from './plan';
import { LANGUAGES, SHIPPED_LANGS } from './strings';
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

export interface FieldMessages {
  originId: string;
  urgencyRank: number;
  kind: MessageKind;
  verdict: Verdict;
  leaveByS: number | null;
  reason: LmReason | null;
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
  }
  add(plan.input.scenario.scenarioSetId);
  return [...out].sort((a, b) => b.length - a.length);
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
    plan,
    text,
    metrics,
    inserted: insertedStrings(plan),
    violations: [],
  };
  fm.violations = checkFieldMessages(fm);
  return fm;
}

/** Every output of one language as plain text, in a fixed order (CSV, checks). */
export function allTexts(fm: FieldMessages, lang: LmLang): Record<'sms' | 'lms' | 'broadcast' | 'call' | 'card', string> {
  const t = fm.text[lang];
  return { sms: t.sms, lms: t.lms, broadcast: t.broadcast, call: t.call, card: cardText(t.card) };
}
