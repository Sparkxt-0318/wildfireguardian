/**
 * Independent oracles for the last-mile property tests (lastmile.cache.test.ts, lastmile.property.test.ts,
 * lastmile.docs.test.ts): written here from the rules in planner/docs/LASTMILE.md, not from the
 * module's own code paths.
 */
import { execFileSync } from 'node:child_process';
import { maskData } from '../../planner/src/features/lastmile/checks';
import { arrivalShown, enDate, enDateSpoken, enSpokenTime, hm, koDate, koDateSpoken, koSmsDate, koSpokenTime, ymd } from '../../planner/src/features/lastmile/compose';
import { BROADCAST_MAX_S, spokenSeconds } from '../../planner/src/features/lastmile/encoding';
import { allTexts, TEMPLATES, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import { MODEL_NOT_LIVE, MODEL_NOT_LIVE_SMS, MODEL_NOT_LIVE_SPOKEN, MODEL_PLAN_SPOKEN, MODEL_SMS, OFFICIAL_FIRST, OFFICIAL_FIRST_SMS } from '../../planner/src/features/lastmile/strings';
import type { LmLang } from '../../planner/src/features/lastmile/types';

/** The GSM 03.38 basic alphabet (the English SMS uses no extension characters). */
export const GSM7 = /^[@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&'()*+,\-./0-9:;<=>?¡A-ZÄÖÑÜ§¿a-zäöñüà]*$/;
/** Words no output may contain (a summary of FORBIDDEN, written independently). */
export const NEVER = /안전|구조|구출|데리러|모시러|픽업|태워|실내 대피|옥내 대피|보장|안심|걱정|\bsafe|safety|rescue|pick[ -]?up|shelter[ -]in[ -]place|stay (indoors|inside|home|put)|guarantee|don'?t worry|no danger/i;
/** A departure instruction, in either language. */
export const DEPART = /까지\s*(차로\s*)?출발|출발하(십시오|세요)|출발 마감|leave by|depart by|leave now|leave before/i;
/** Hangul (jamo, compatibility jamo, syllables). */
export const HANGUL = /[ᄀ-ᇿ㄰-㆏가-힣]/;

/** Byte lengths in Python's strict `euc_kr` codec (or "unencodable: …"); null when no Python is found. */
export function pythonEucKr(texts: string[]): (number | string)[] | null {
  const script =
    'import json,sys\n' +
    'out=[]\n' +
    'for t in json.load(sys.stdin):\n' +
    '    try: out.append(len(t.encode("euc_kr")))\n' +
    '    except UnicodeEncodeError as e: out.append("unencodable: "+t[e.start:e.end])\n' +
    'print(json.dumps(out))\n';
  for (const py of ['python3', 'python']) {
    try {
      return JSON.parse(execFileSync(py, ['-I', '-c', script], { input: JSON.stringify(texts), maxBuffer: 64 * 1024 * 1024 }).toString('utf8'));
    } catch {
      /* try the next interpreter */
    }
  }
  return null;
}

type Entry = Record<string, unknown> & { binding?: Record<string, unknown>[]; exits?: Record<string, unknown>[] };

/**
 * The reason kind one origin's messages must carry, read from the explanation entry's own fields
 * and the planner's sweep — deliberately WITHOUT the module's detail-code whitelist, so a new or
 * renamed code in the files fails the test instead of silently dropping the reason line:
 * - leave_by: only when the message's time T is the planner's deadline D (the latest checked
 *   departure), the entry's deadline is D, and the entry's next departure is the sweep's next one,
 *   recorded as model_no_route; flame / dwell reasons when binding[0] covers the message's
 *   destination; "explained" window + time_window and no_flame_avoiding_route + flames;
 * - no_route: "explained" entries: window + time_window, no_flame_avoiding_route + flames,
 *   all_exits_blocked (entry_point_in_flame → the entry point in flames);
 * - never for unresolved or partial messages, or a not_explainable entry.
 */
export function expectedReasonKind(entryRaw: unknown, fm: FieldMessages): string | null {
  if (!entryRaw || typeof entryRaw !== 'object') return null;
  const e = entryRaw as Entry;
  if (e.status === 'not_explainable') return null;
  const plan = fm.plan.input.plan;
  if (fm.kind === 'leave_by' && plan) {
    const D = plan.latestSafeDepartureS;
    if (e.verdict_summary !== 'checked_route' || D === null || fm.leaveByS !== D || e.deadline_offset_s !== D) return null;
    const next = [...plan.sweep].sort((a, b) => a.offsetS - b.offsetS).find((c) => c.offsetS > D);
    if (!next || next.verdict !== 'model_no_route' || e.next_verdict !== 'model_no_route' || e.next_offset_s !== next.offsetS) return null;
    if (e.reason_code === 'flame_on_route' || e.reason_code === 'dwell_at_destination') {
      const ids = (e.binding?.[0]?.destination_ids ?? []) as string[];
      return fm.plan.destination && ids.includes(fm.plan.destination.id) ? (e.reason_code as string) : null;
    }
    if (e.status !== 'explained') return null;
    if (e.reason_code === 'window' && e.deadline_cause === 'time_window') return 'time_window';
    if (e.reason_code === 'no_flame_avoiding_route' && e.deadline_cause === 'flames') return 'no_flame_avoiding_route';
    return null;
  }
  if (fm.kind === 'no_route') {
    if (e.verdict_summary !== 'model_no_route' || e.status !== 'explained') return null;
    if (e.reason_code === 'window' && e.deadline_cause === 'time_window') return 'no_route_time_window';
    if (e.reason_code === 'no_flame_avoiding_route' && e.deadline_cause === 'flames') return 'no_route_flames';
    if (e.reason_code === 'all_exits_blocked') return e.detail_code === 'entry_point_in_flame' ? 'entry_in_flame' : 'all_exits_blocked';
    return null;
  }
  return null;
}

// ---------------------------------------------------------------- what each output of a leave-by message gives

/** The sentence that says what limits T, in any of its written forms (long text, card). */
const LIMIT_WRITTEN: Record<LmLang, RegExp> = {
  ko: /이유: |다음 점검 시각인 \d{2}:\d{2}에 출발하면|마지막 출발 시각이 \d{2}:\d{2}입니다|그 뒤 출발은 점검하지 않았습니다|\d{2}:\d{2} 이후에는 모델로 확인된 경로가 없는 출발 시각이 있어|\d{2}:\d{2}보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다/,
  en: /Why: |[Nn]ext checked time,? \d{2}:\d{2}|is the last departure time the model checked|Later departures were not checked|Some departure times after \d{2}:\d{2} have no checked route|Departures after \d{2}:\d{2} have no checked route|No checked route for departures after \d{2}:\d{2}/,
};
/** The same, spoken (broadcast, call script). */
const LIMIT_SPOKEN: Record<LmLang, RegExp> = {
  ko: /불길이 닿습니다|불길을 피하는 길로|그보다 늦게 출발하면 컴퓨터 예측 계산으로 확인된 길이 없습니다|그 뒤 출발은 점검하지 않았습니다|확인된 길이 없는 출발 시각이 있습니다/,
  en: /flames reach|avoids the flames|Later departures have no checked route|Later departures were not checked|Some later departure times have no checked route/,
};
const DONT_WAIT: Record<LmLang, { lms: string; card: string; any: RegExp }> = {
  ko: { lms: '이 시각까지 기다리지 마십시오', card: '이 시각까지 기다리지 말고', any: /기다리지/ },
  en: { lms: 'Do not wait until that time', card: 'Do not wait until this time', any: /\bwait\b/i },
};
// the arrival sentence (not "(arrival and stay)" of the English card's 1-hour-range line)
const ARRIVAL_ANY: Record<LmLang, RegExp> = { ko: /쯤 도착|차로 약 \d+분/, en: /arriv(e|al) around|min by car/i };
const DEST_ANY: Record<LmLang, RegExp> = { ko: /도착|대피소/, en: /destination|arriv|shelter/i };
const VARIES: Record<LmLang, string> = { ko: '도착지는 출발 시각에 따라 다릅니다', en: 'depends on the departure time' };
/** What the English call script says for a destination without a Latin-script name (the caller fills it in from the card). */
export const EN_CALL_CARD_DESTINATION = '[destination name from the card]';

export interface LeaveByFacts {
  /** statements of LASTMILE.md §2 ("What each output gives") that do not hold for this origin */
  violations: string[];
  /** the broadcast carries what limits T (an optional block: only when the 60 s budget leaves room) */
  broadcastReason: Record<LmLang, boolean>;
  /** the broadcast's leave-by sentence leaves out a destination it could name (the 60 s budget) */
  destinationLeftOut60s: Record<LmLang, boolean>;
  /** the destination has an OSM name without a Latin-script form: English spoken outputs cannot say it */
  noLatinName: boolean;
}

/**
 * LASTMILE.md §2 "What each output gives", checked on the outputs of one leave-by origin, in both
 * languages: the long text and the card give T with "do not wait", the destination (or "depends on
 * the departure time"), the arrival time and minutes (one rounding) for a destination that does not
 * vary, what limits T, the data time and the mandatory lines verbatim; the SMS gives T, the data
 * time and the short forms only; the broadcast and the call script give T and the destination
 * (except when it varies or, in English, has no Latin-script name; the broadcast also leaves it out
 * only when its required blocks in their full wording exceed 60 s), what limits T (the call script
 * always, the broadcast exactly when it fits in 60 s), the data time and the mandatory lines as
 * sentences — and none of them the arrival time or "do not wait". The broadcast's blocks
 * (TEMPLATES[lang].broadcastBlocks) are used only to name its optional lines and to time the full
 * wording of its required blocks.
 */
export function leaveByOutputFacts(fm: FieldMessages): LeaveByFacts {
  const v: string[] = [];
  const out: LeaveByFacts = { violations: v, broadcastReason: { ko: false, en: false }, destinationLeftOut60s: { ko: false, en: false }, noLatinName: false };
  const p = fm.plan;
  const iso = p.input.scenario.inputTimeIso;
  const d = p.destination;
  if (fm.kind !== 'leave_by' || p.leaveByS === null || !d) {
    v.push(`not a leave-by message with a time and a destination (${fm.kind})`);
    return out;
  }
  const L = p.leaveByS;
  const T = hm(iso, L);
  out.noLatinName = d.name !== null && HANGUL.test(d.name.en);
  for (const lang of ['ko', 'en'] as const) {
    const t = allTexts(fm, lang);
    const masked = (s: string) => maskData(s, fm.inserted);
    const S = lang === 'ko' ? koSpokenTime(iso, L) : enSpokenTime(iso, L);
    const say = (ok: boolean, what: string) => {
      if (!ok) v.push(`${lang}: ${what}`);
    };
    // the destination as written and as said (an unnamed one by its category; English says no Hangul)
    const written = d.name ? d.name[lang] : lang === 'ko' ? `지도 자료에 이름이 없는 ${d.category.ko}` : 'with no name in the map data';
    const spoken = d.name ? (lang === 'en' && HANGUL.test(d.name.en) ? null : d.name[lang]) : lang === 'ko' ? `이름 없는 ${d.category.ko}` : `an unnamed ${d.category.en.toLowerCase()}`;
    const arrival = !p.destinationVaries && d.arrivalS !== null && d.arrivalS > L ? arrivalShown(iso, L, d.arrivalS) : null;

    // ---- long text and card
    say(t.lms.includes(lang === 'ko' ? `${T}(${S})까지 차로 출발하십시오` : `Leave by car no later than ${T} KST (${S})`), 'long text: leave by T');
    say(fm.text[lang].card.big?.time === T && t.card.includes(T), 'card: leave by T');
    say(t.lms.includes(DONT_WAIT[lang].lms), 'long text: "do not wait until this time"');
    say(t.card.includes(DONT_WAIT[lang].card), 'card: "do not wait until this time"');
    for (const [k, x] of [['long text', t.lms], ['card', t.card]] as const) {
      say(x.includes(written), `${k}: the destination ${written}`);
      if (p.destinationVaries) say(x.includes(VARIES[lang]), `${k}: "the destination depends on the departure time"`);
      if (arrival) say(x.includes(arrival.hm) && x.includes(lang === 'ko' ? `약 ${arrival.min}분` : `about ${arrival.min} min`), `${k}: arrival ${arrival.hm}, ${arrival.min} min`);
      else say(!ARRIVAL_ANY[lang].test(masked(x)), `${k}: an arrival time without a destination that does not vary`);
      say(LIMIT_WRITTEN[lang].test(x), `${k}: what limits T`);
      say(x.includes(OFFICIAL_FIRST[lang]) && x.includes(MODEL_NOT_LIVE[lang]), `${k}: the mandatory lines verbatim`);
    }
    say(t.lms.includes(lang === 'ko' ? koDate(iso) : enDate(iso)) && t.card.includes(lang === 'ko' ? koDate(iso) : enDate(iso)), 'long text / card: the data time');

    // ---- SMS: T, the data time and the short forms only
    say(t.sms.includes(lang === 'ko' ? `${T}까지 차로 출발` : `no later than ${T} KST`), 'SMS: leave by T');
    say(t.sms.includes(lang === 'ko' ? koSmsDate(iso) : `${ymd(iso)} ${hm(iso)} KST`), 'SMS: the data time');
    say([OFFICIAL_FIRST_SMS[lang], MODEL_NOT_LIVE_SMS[lang], MODEL_SMS[lang]].every((s) => t.sms.includes(s)), 'SMS: the short forms');
    say(!t.sms.includes(OFFICIAL_FIRST[lang]) && !t.sms.includes(MODEL_NOT_LIVE[lang]), 'SMS: a verbatim mandatory line');
    say(!masked(t.sms).includes('⟨data⟩') && !DEST_ANY[lang].test(t.sms), 'SMS: a destination');
    say(!ARRIVAL_ANY[lang].test(t.sms) && !DONT_WAIT[lang].any.test(t.sms), 'SMS: an arrival time or "do not wait"');
    say(!LIMIT_WRITTEN[lang].test(t.sms) && !LIMIT_SPOKEN[lang].test(t.sms), 'SMS: what limits T');

    // ---- broadcast and call script
    const blocks = TEMPLATES[lang].broadcastBlocks(p);
    const reason = blocks.find((b) => b.optional === 'reason')?.text ?? null;
    const repeat = blocks.find((b) => b.optional === 'repeat')?.text ?? null;
    say(reason !== null && LIMIT_SPOKEN[lang].test(reason), 'broadcast: no optional block that says what limits T');
    for (const [k, x] of [['broadcast', t.broadcast], ['call script', t.call]] as const) {
      say(x.includes(lang === 'ko' ? koDateSpoken(iso) : enDateSpoken(iso)), `${k}: the data time`);
      const sentence = k === 'broadcast' ? MODEL_PLAN_SPOKEN[lang] : MODEL_NOT_LIVE_SPOKEN[lang];
      say(x.includes(OFFICIAL_FIRST[lang]) && x.includes(sentence) && !x.includes(MODEL_NOT_LIVE[lang]), `${k}: the mandatory lines as sentences`);
      say(!ARRIVAL_ANY[lang].test(masked(x)) && !DONT_WAIT[lang].any.test(masked(x)), `${k}: an arrival time or "do not wait"`);
    }
    const bLines = t.broadcast.split('\n');
    const bLeave = bLines.find((l) => l.includes(lang === 'ko' ? `${S}까지 차로 출발하십시오` : `Leave by car no later than ${S}`));
    say(bLeave !== undefined, 'broadcast: leave by T');
    const cLines = t.call.split('\n');
    const cLeave = cLines.find((l) => l.includes(lang === 'ko' ? `${S}까지 차로 출발` : `no later than ${S} gives a checked route`));
    say(cLeave !== undefined, 'call script: leave by T');
    if (bLeave !== undefined && cLeave !== undefined) {
      if (!p.destinationVaries && spoken !== null) {
        say(cLeave.includes(spoken), `call script: the destination ${spoken}`);
        if (!bLeave.includes(spoken)) {
          // left out only when the required blocks in their full wording exceed the budget
          const full = blocks.filter((b) => !b.optional).map((b) => b.text).join('\n');
          say(spokenSeconds(full, lang) > BROADCAST_MAX_S, `broadcast: the destination ${spoken} left out although the required blocks fit in 60 s`);
          out.destinationLeftOut60s[lang] = true;
        }
      } else {
        // not given: it varies, or (English) it has no Latin-script name — never Hangul read in English
        if (spoken !== null) say(!bLeave.includes(spoken) && !cLeave.includes(spoken), `broadcast / call script: the destination ${spoken} although it varies`);
        if (lang === 'en') say(!HANGUL.test(bLeave) && !HANGUL.test(cLeave), 'broadcast / call script: Hangul read in English');
        if (p.destinationVaries) say(t.call.includes(VARIES[lang]), 'call script: "the destination depends on the departure time"');
        else say(cLeave.includes(EN_CALL_CARD_DESTINATION), `call script: "${EN_CALL_CARD_DESTINATION}"`);
      }
    }
    // what limits T: the call script always; the broadcast exactly when it fits in the 60 s budget
    say(reason !== null && cLines.includes(reason) && LIMIT_SPOKEN[lang].test(t.call), 'call script: what limits T');
    const has = reason !== null && bLines.includes(reason);
    out.broadcastReason[lang] = has;
    say(LIMIT_SPOKEN[lang].test(t.broadcast) === has, 'broadcast: a line that says what limits T outside its optional block');
    if (reason !== null) {
      const required = bLines.filter((l) => l !== reason && l !== repeat);
      const fits = spokenSeconds([...required, reason].join('\n'), lang) <= BROADCAST_MAX_S;
      say(has === fits, has ? 'broadcast: what limits T although it does not fit in 60 s' : 'broadcast: what limits T left out although it fits in 60 s');
    }
  }
  return out;
}
