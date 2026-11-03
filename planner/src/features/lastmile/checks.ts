/**
 * Rule checks of the field messages (fail closed: the panel does not offer a text that fails).
 * The same function is the oracle of the property tests over every origin of the six booth caches.
 *
 * For every language and output:
 * - length: Korean SMS ≤ 90 bytes (strict EUC-KR), long text ≤ 2,000 bytes, English SMS ≤ 160
 *   GSM-7 characters, no character outside the SMS encoding, broadcast ≤ 60 s at the assumed rate;
 * - mandatory phrases (requiredPhrases), the data time, and — for a recorded scenario — the
 *   replay note with its year, the replay marker on the FIRST line of the SMS and long text, and
 *   "이 방송은 실제 상황이 아닙니다 / This is not a real emergency" as the broadcast's first line;
 * - resident- and family-facing outputs (SMS, broadcast, call script) never say "call 119 now";
 * - no forbidden word (FORBIDDEN, both languages; names from data are masked first);
 * - a message that is not `leave_by` gives no departure instruction and names no clock time other
 *   than the data time; a `leave_by` message names its leave-by time in every output.
 */
import { BROADCAST_MAX_S, LMS_MAX_BYTES, spokenSeconds } from './encoding';
import { cardText, enDate, enDateSpoken, enSpokenTime, hm, kstParts, koDate, koDateSpoken, koSmsDate, koSpokenTime, ymd } from './compose';
import type { FieldMessages } from './messages';
import { DEPARTURE_INSTRUCTION, FORBIDDEN, NOT_REAL, requiredPhrases, RESIDENT_119_NOW, SHIPPED_LANGS, type OutputKind } from './strings';
import type { LmLang } from './types';

export const OUTPUT_KINDS: readonly OutputKind[] = ['sms', 'lms', 'broadcast', 'call', 'card'];

/** The data-time text each output must contain. */
export function dataTimeToken(kind: OutputKind, lang: LmLang, inputIso: string): string {
  if (lang === 'ko') {
    if (kind === 'sms') return koSmsDate(inputIso);
    if (kind === 'broadcast' || kind === 'call') return koDateSpoken(inputIso);
    return koDate(inputIso);
  }
  if (kind === 'sms') return `${ymd(inputIso)} ${hm(inputIso)}`;
  if (kind === 'broadcast' || kind === 'call') return enDateSpoken(inputIso);
  return enDate(inputIso);
}

/** Replaces every data string (place / road names) with a neutral token. */
export function maskData(text: string, inserted: string[]): string {
  let s = text;
  for (const name of inserted) if (name) s = s.split(name).join('⟨data⟩');
  return s;
}

const p2 = (n: number) => String(n).padStart(2, '0');

/**
 * Clock times named in a text as "HH:MM" (24 h), written or spoken, after removing date-time
 * stamps ("2025-03-24 18:00", "2025년 3월 24일 18:00", "25.3.24 18:00", "March 24, 2025, 6 p.m.").
 */
export function clockTimes(text: string): string[] {
  let s = text
    .replace(/\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}/g, ' ')
    .replace(/\d{4}년 \d{1,2}월 \d{1,2}일 (\d{1,2}:\d{2}|(새벽|오전|낮|오후|밤) \d{1,2}시( \d{1,2}분)?)/g, ' ')
    .replace(/\d{2}\.\d{1,2}\.\d{1,2} \d{1,2}:\d{2}/g, ' ')
    .replace(/[A-Z][a-z]+ \d{1,2}, \d{4}, \d{1,2}(:\d{2})? [ap]\.m\./g, ' ');
  const out: string[] = [];
  s = s.replace(/(새벽|오전|낮|오후|밤)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?/g, (_m, per: string, hs: string, ms?: string) => {
    let h = Number(hs);
    if (per === '오후' && h < 12) h += 12;
    else if (per === '밤') h = h === 12 ? 0 : h + 12;
    out.push(`${p2(h)}:${p2(ms ? Number(ms) : 0)}`);
    return ' ';
  });
  s = s.replace(/\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.m\./g, (_m, hs: string, ms: string | undefined, ap: string) => {
    let h = Number(hs) % 12;
    if (ap === 'p') h += 12;
    out.push(`${p2(h)}:${ms ?? '00'}`);
    return ' ';
  });
  for (const m of s.matchAll(/(?<![\w:.])(\d{1,2}):(\d{2})(?![\d:])/g)) out.push(`${p2(Number(m[1]))}:${m[2]}`);
  return out;
}

export function checkFieldMessages(fm: FieldMessages): string[] {
  const v: string[] = [];
  const input = fm.plan.input;
  const iso = input.scenario.inputTimeIso;
  const dataHM = hm(iso);
  const year = String(input.region.fireYear ?? kstParts(iso).y);
  for (const lang of SHIPPED_LANGS) {
    const t = fm.text[lang];
    const m = fm.metrics[lang];
    const texts: Record<OutputKind, string> = { sms: t.sms, lms: t.lms, broadcast: t.broadcast, call: t.call, card: cardText(t.card) };
    if (m.smsUnits > m.smsLimit) v.push(`${lang}.sms: ${m.smsUnits} ${m.smsUnit} > ${m.smsLimit}`);
    if (m.smsBad.length) v.push(`${lang}.sms: characters outside the SMS encoding: ${m.smsBad.join(' ')}`);
    if (m.lmsBytes > LMS_MAX_BYTES) v.push(`${lang}.lms: ${m.lmsBytes} bytes > ${LMS_MAX_BYTES}`);
    if (m.lmsBad.length) v.push(`${lang}.lms: characters outside EUC-KR: ${m.lmsBad.join(' ')}`);
    // unrounded: the metric shown in the panel is rounded to 0.1 s
    const broadcastS = spokenSeconds(t.broadcast, lang);
    if (broadcastS > BROADCAST_MAX_S) v.push(`${lang}.broadcast: ${broadcastS.toFixed(2)} s > ${BROADCAST_MAX_S} s`);
    for (const kind of OUTPUT_KINDS) {
      const text = texts[kind];
      for (const phrase of requiredPhrases(kind, lang, input.replay)) if (!text.includes(phrase)) v.push(`${lang}.${kind}: missing "${phrase}"`);
      const dt = dataTimeToken(kind, lang, iso);
      if (!text.includes(dt)) v.push(`${lang}.${kind}: missing the data time "${dt}"`);
      if (input.replay) {
        const words = lang === 'ko' ? (kind === 'sms' ? ['재현', 'MOCK', '시험'] : ['재현']) : ['replay'];
        if (!words.some((w) => text.toLowerCase().includes(w.toLowerCase()))) v.push(`${lang}.${kind}: missing the replay note`);
        // the replay marker comes first: a replay must never read as a live alert
        const first = (text.split('\n')[0] ?? '').toLowerCase();
        if ((kind === 'sms' || kind === 'lms') && !words.some((w) => first.includes(w.toLowerCase()))) v.push(`${lang}.${kind}: the first line does not say it is a replay`);
        if (kind === 'lms' && !first.includes(lang === 'ko' ? '실제 상황 아님' : 'not a real emergency')) v.push(`${lang}.lms: the first line does not say it is not a real situation`);
        if (kind === 'broadcast' && first !== NOT_REAL[lang].toLowerCase()) v.push(`${lang}.broadcast: does not open with "${NOT_REAL[lang]}"`);
        // the year: written in full except in the Korean SMS, whose date is "25.3.24"
        if (!(lang === 'ko' && kind === 'sms') && !text.includes(year)) v.push(`${lang}.${kind}: replay note without the year ${year}`);
      }
      const masked = maskData(text, fm.inserted);
      const low = masked.toLowerCase();
      if ((kind === 'sms' || kind === 'broadcast' || kind === 'call') && RESIDENT_119_NOW[lang].test(masked)) v.push(`${lang}.${kind}: tells residents or families to call 119 now`);
      for (const w of [...FORBIDDEN.ko, ...FORBIDDEN.en]) if (low.includes(w.toLowerCase())) v.push(`${lang}.${kind}: forbidden word "${w}"`);
      if (fm.kind === 'leave_by') {
        if (fm.leaveByS === null) v.push(`${lang}.${kind}: leave_by without a time`);
        else {
          const want = kind === 'broadcast' || kind === 'call' ? (lang === 'ko' ? koSpokenTime(iso, fm.leaveByS) : enSpokenTime(iso, fm.leaveByS)) : hm(iso, fm.leaveByS);
          if (!masked.includes(want)) v.push(`${lang}.${kind}: leave-by time "${want}" missing`);
        }
      } else {
        if (DEPARTURE_INSTRUCTION.ko.test(masked) || DEPARTURE_INSTRUCTION.en.test(masked)) v.push(`${lang}.${kind}: departure instruction in a ${fm.kind} message`);
        // the card's preparation stamps ("작성 2026-… KST") are date-time stamps and are removed first
        for (const c of clockTimes(masked)) if (c !== dataHM) v.push(`${lang}.${kind}: clock time ${c} in a ${fm.kind} message`);
      }
    }
  }
  return v;
}
