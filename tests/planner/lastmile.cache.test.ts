/**
 * Property tests of the last-mile kit over EVERY origin of the six booth caches
 * (2 regions × 3 recorded input times), loaded the way the app loads them
 * (tests/planner/lastmile.cachedata.ts). For every origin and every output, in Korean and English:
 * length limits, mandatory lines, data time, replay note, no forbidden word, and no departure
 * instruction or clock time unless the planner has a checked departure window.
 *
 * The limits are checked twice: by the module's own checks (checkFieldMessages) and by independent
 * oracles written here — Python's strict `euc_kr` codec for the Korean byte counts (skipped only if
 * python3 is missing), a separate GSM-7 character class, and separate word / instruction patterns.
 *
 * Real outputs are snapshotted WITHOUT a deadline explanation (none exists in this branch). The
 * "contract-shaped explanation" block below builds a synthetic `wfg.explanation/1` file from the
 * planner's own deadlines with a made-up road name; it only exercises the reader and the length
 * budgets and never leaves the test.
 */
import { execFileSync } from 'node:child_process';
import { beforeAll, describe, expect, it } from 'vitest';
import { enDateSpoken, hm, koDateSpoken } from '../../planner/src/features/lastmile/compose';
import { maskData } from '../../planner/src/features/lastmile/checks';
import { BROADCAST_MAX_S, LMS_MAX_BYTES, SMS_EN_MAX_GSM7, SMS_KO_MAX_BYTES } from '../../planner/src/features/lastmile/encoding';
import { allTexts, buildFieldMessages, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import { MODEL_NOT_LIVE, OFFICIAL_FIRST } from '../../planner/src/features/lastmile/strings';
import type { LastMileInput } from '../../planner/src/features/lastmile/types';
import { loadBoothCaches, syntheticExplanationFor, type BoothCache } from './lastmile.cachedata';

let caches: BoothCache[] = [];
let all: { cache: BoothCache; input: LastMileInput; fm: FieldMessages }[] = [];

beforeAll(() => {
  caches = loadBoothCaches();
  all = caches.flatMap((cache) => cache.inputs.map((input) => ({ cache, input, fm: buildFieldMessages(input, null) })));
}, 180_000);

// independent oracles -----------------------------------------------------------------------

const GSM7 = /^[@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&'()*+,\-./0-9:;<=>?¡A-ZÄÖÑÜ§¿a-zäöñüà]*$/;
const NEVER = /안전|구조|구출|데리러|모시러|픽업|태워|실내 대피|옥내 대피|보장|안심|걱정|\bsafe|safety|rescue|pick[ -]?up|shelter[ -]in[ -]place|stay (indoors|inside|home|put)|guarantee|don'?t worry|no danger/i;
const DEPART = /까지\s*(차로\s*)?출발|출발하(십시오|세요)|출발 마감|leave by|depart by|leave now|leave before/i;

function pythonEucKr(texts: string[]): (number | string)[] | null {
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

describe('all six booth caches, every origin', () => {
  it('loads 2 regions × 3 recorded input times and one input per origin of each scenario', () => {
    expect(caches.map((c) => c.entry.path).sort()).toEqual([
      'uiseong_andong_2025/20250323T010000Z.json',
      'uiseong_andong_2025/20250324T090000Z.json',
      'uiseong_andong_2025/20250325T170000Z.json',
      'yeongdeok_2025/20250325T190000Z.json',
      'yeongdeok_2025/20250325T230000Z.json',
      'yeongdeok_2025/20250326T080000Z.json',
    ]);
    for (const c of caches) {
      expect(c.inputs.length).toBeGreaterThanOrEqual(c.cachedOrigins);
      expect(new Set(c.inputs.map((i) => i.origin.id)).size).toBe(c.inputs.length);
      expect(c.inputs.every((i) => !i.mock && !i.testData && i.replay)).toBe(true);
    }
    const kinds: Record<string, number> = {};
    for (const x of all) kinds[x.fm.kind] = (kinds[x.fm.kind] ?? 0) + 1;
    // the message kind follows the planner's verdict
    for (const x of all) {
      const v = x.input.plan?.bestVerdict ?? 'unresolved';
      if (x.fm.kind === 'leave_by' || x.fm.kind === 'partial') expect(v).toBe('checked_route');
      if (x.fm.kind === 'no_route') expect(v).toBe('model_no_route');
      if (x.fm.kind === 'unresolved') expect(v).toBe('unresolved');
    }
    expect(Object.keys(kinds).sort()).toEqual(['leave_by', 'no_route', 'unresolved']);
    expect(all.length).toBeGreaterThan(500);
  });

  it('every output passes the module rule checks (limits, mandatory lines, data time, replay note, words, instructions)', () => {
    const bad = all.filter((x) => x.fm.violations.length).map((x) => `${x.cache.entry.path} ${x.input.origin.id}: ${x.fm.violations.join(' | ')}`);
    expect(bad).toEqual([]);
  });

  it('Korean SMS ≤ 90 bytes and long texts ≤ 2,000 bytes in strict EUC-KR (independent: Python euc_kr codec)', () => {
    const sms = all.map((x) => x.fm.text.ko.sms);
    const lms = all.flatMap((x) => [x.fm.text.ko.lms, x.fm.text.en.lms]);
    for (const x of all) expect(x.fm.metrics.ko.smsUnits).toBeLessThanOrEqual(SMS_KO_MAX_BYTES);
    const py = pythonEucKr([...sms, ...lms]);
    if (!py) {
      console.warn('python3 not found: independent EUC-KR cross-check skipped (module counts still enforced)');
      return;
    }
    py.slice(0, sms.length).forEach((n, i) => {
      expect(n, sms[i]).toBe(all[i]!.fm.metrics.ko.smsUnits);
      expect(n as number).toBeLessThanOrEqual(SMS_KO_MAX_BYTES);
    });
    py.slice(sms.length).forEach((n, i) => {
      expect(typeof n, lms[i]).toBe('number');
      expect(n as number).toBeLessThanOrEqual(LMS_MAX_BYTES);
    });
  });

  it('English SMS ≤ 160 GSM-7 characters, all inside the GSM 03.38 alphabet (independent character class)', () => {
    for (const x of all) {
      const s = x.fm.text.en.sms;
      expect(GSM7.test(s), s).toBe(true);
      expect(s.length).toBeLessThanOrEqual(SMS_EN_MAX_GSM7);
      expect(x.fm.metrics.en.smsUnits).toBe(s.length);
    }
  });

  it('village broadcast scripts read in ≤ 60 s at the assumed rate, Korean and English', () => {
    for (const x of all) {
      expect(x.fm.metrics.ko.broadcastS).toBeLessThanOrEqual(BROADCAST_MAX_S);
      expect(x.fm.metrics.en.broadcastS).toBeLessThanOrEqual(BROADCAST_MAX_S);
    }
  });

  it('every output carries the data time and "official orders come first"; written ones also the model line verbatim', () => {
    for (const x of all) {
      const it0 = x.input.scenario.inputTimeIso;
      for (const lang of ['ko', 'en'] as const) {
        const t = allTexts(x.fm, lang);
        expect(t.sms).toContain(lang === 'ko' ? '공식명령 우선' : 'Official orders come first.');
        for (const k of ['lms', 'broadcast', 'call', 'card'] as const) expect(t[k]).toContain(OFFICIAL_FIRST[lang]);
        for (const k of ['lms', 'card'] as const) expect(t[k]).toContain(MODEL_NOT_LIVE[lang]);
        expect(t.sms).toContain(hm(it0));
        expect(t.lms).toContain(hm(it0));
        expect(t.card).toContain(hm(it0));
      }
    }
  });

  it('no forbidden word anywhere (independent pattern, place names masked)', () => {
    for (const x of all) for (const lang of ['ko', 'en'] as const) for (const t of Object.values(allTexts(x.fm, lang))) expect(maskData(t, x.fm.inserted)).not.toMatch(NEVER);
  });

  it('model_no_route and unresolved never yield a departure instruction or a clock time; leave_by always names its time', () => {
    for (const x of all) {
      const texts = [...Object.values(allTexts(x.fm, 'ko')), ...Object.values(allTexts(x.fm, 'en'))].map((t) => maskData(t, x.fm.inserted));
      if (x.fm.kind === 'leave_by') {
        expect(x.fm.leaveByS).not.toBeNull();
        expect(x.fm.text.ko.sms).toContain(`${hm(x.input.scenario.inputTimeIso, x.fm.leaveByS!)}까지 출발`);
        // the leave-by time is a checked departure and every earlier requested time is checked too
        const cells = x.input.plan!.sweep.filter((c) => c.verdict !== 'window_closed' && c.offsetS <= x.fm.leaveByS!);
        expect(cells.length).toBeGreaterThan(0);
        expect(cells.every((c) => c.verdict === 'checked_route')).toBe(true);
      } else {
        const spokenData = [koDateSpoken(x.input.scenario.inputTimeIso), enDateSpoken(x.input.scenario.inputTimeIso)];
        for (const t0 of texts) {
          const t = spokenData.reduce((acc, d) => acc.split(d).join(' '), t0);
          expect(t).not.toMatch(DEPART);
          const data = hm(x.input.scenario.inputTimeIso);
          const times = [...t.replace(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}|\d{2}\.\d{1,2}\.\d{1,2} \d{2}:\d{2}|\d{4}년 \d{1,2}월 \d{1,2}일 \d{2}:\d{2}/g, '').matchAll(/(?<![\w:.])(\d{2}):(\d{2})(?![\d:])/g)].map((m) => `${m[1]}:${m[2]}`);
          expect(times.every((c) => c === data), t).toBe(true);
          expect(t).not.toMatch(/(새벽|오전|낮|오후|밤) \d{1,2}시 \d{1,2}분|\d{1,2}:\d{2} [ap]\.m\./);
        }
      }
    }
  });
});

describe('with a contract-shaped explanation file built from the planner deadlines (synthetic road name)', () => {
  const explanationFor = syntheticExplanationFor;

  it('reasons appear exactly where the entry agrees with the planner, and every limit still holds', () => {
    let used = 0;
    let eligible = 0;
    for (const cache of caches) {
      const file = explanationFor(cache);
      for (const input of cache.inputs) {
        const fm = buildFieldMessages(input, file);
        expect(fm.violations, `${cache.entry.path} ${input.origin.id}`).toEqual([]);
        const p = messagePlan(input, null);
        const want = (p.kind === 'leave_by' && p.nextVerdict === 'model_no_route') || p.kind === 'no_route';
        if (want) eligible += 1;
        if (fm.reason) used += 1;
        expect(Boolean(fm.reason), `${cache.entry.path} ${input.origin.id}`).toBe(want);
        if (fm.kind === 'unresolved') expect(fm.reason).toBeNull();
      }
    }
    expect(eligible).toBeGreaterThan(0);
    expect(used).toBe(eligible);
  });

  it('a file whose deadlines are off by one departure step gives no reason at all (fail closed)', () => {
    for (const cache of caches) {
      const file = explanationFor(cache, 600);
      for (const input of cache.inputs) {
        const fm = buildFieldMessages(input, file);
        if (fm.kind === 'leave_by') expect(fm.reason).toBeNull();
      }
    }
  });
});

describe('real outputs (booth cache, no explanation file) — snapshots in both languages', () => {
  const pick = (path: string, id: string) => {
    const x = all.find((y) => y.cache.entry.path === path && y.input.origin.id === id);
    if (!x) throw new Error(`${path} ${id} not found`);
    return x.fm;
  };
  const view = (fm: FieldMessages) => ({ kind: fm.kind, ko: allTexts(fm, 'ko'), en: allTexts(fm, 'en') });

  it('checked_route → leave_by (삼춘리, 의성·안동, 2025-03-26 02:00 KST)', () => {
    expect(view(pick('uiseong_andong_2025/20250325T170000Z.json', 'osm:node/415160437'))).toMatchInlineSnapshot(`
      {
        "en": {
          "broadcast": "Attention, residents of Samchun-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time. It is not live information.
      Leave by car by 2:20 a.m. The model checked a route to Uiseong Bukbu Elementary School for departures up to then.
      Later departures have no checked route.
      Follow official guidance on where to go.
      If you have no car, tell the village head or the eup/myeon office now.
      Again: leave by 2:20 a.m.
      Official evacuation orders come first.",
          "call": "[Before the call] Official evacuation orders come first. What follows is model-based planning information, not live information. Fill in the [brackets] yourself.
      Hello, this is [your name and role]. I am calling the family of [resident name], who lives in Samchun-ri, about the wildfire evacuation plan.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time. It is not live information.
      In the model, leaving by car from the road near the village by 2:20 a.m. gives a checked route to Uiseong Bukbu Elementary School.
      Later departures have no checked route.
      Official evacuation orders come first. The actual place and time of any move may change with official guidance.
      If you have questions, please call [phone number]. Thank you.",
          "card": "Evacuation plan card · Uiseong–Andong · Recorded 2025 wildfire · scenario replay
      Samchun-ri (Village)
      Checked vehicle route in the model
      Leave by 02:20 (2:20 a.m. KST)
      Do not wait for the deadline: leave by car early.
      Model-checked destination: Uiseong Bukbu Elementary School; leave 02:20, arrive around 02:50 (about 30 min by car; traffic not included)
      No checked route for departures after 02:20.
      Follow official guidance on where to go. No car, or cannot move alone? Tell the village head or eup/myeon office now.
      Official evacuation orders come first.
      Data time: 2025-03-26 02:00 KST · Replay of recorded 2025 wildfire scenarios
      Model-based planning information · not live
      Times at the road entry point 195 m away; boarding time not included · Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
      Planning aid only — not for live evacuation operations.
      Prepared 2026-11-02 14:00 KST · Scenario ffb1:20250325T170000Z:53e6da7897bf9b5b · Precomputed 2026-10-18 08:10 KST",
          "lms": "[Wildfire evacuation plan information - 2025 recorded replay]
      Samchun-ri (Village)
      Data time: 2025-03-26 02:00 KST

      - Leave by car no later than 02:20 KST (2:20 a.m.). Do not wait until the last minute.
      - Destination the model checked: Uiseong Bukbu Elementary School. Leaving at 02:20, arrival around 02:50 KST (about 30 min by car; traffic not included).
      - Departures after 02:20 have no checked route in the model.
      - Follow official guidance on where to go and which roads to use.
      - If you have no car or cannot move on your own, tell the village head or the eup/myeon office now.
      - Times refer to the nearest road point (entry point), 195 m from the village. Time to get ready and board is not included.

      Official evacuation orders come first.
      Model-based planning information · not live
      Replay of recorded 2025 wildfire scenarios.
      Planning aid only - not for live evacuation operations.",
          "sms": "Model: checked route found.
      Leave by 02:20 KST.
      Official orders come first.
      Model-based info, not live.
      Replay of 2025-03-26 02:00 KST data",
        },
        "kind": "leave_by",
        "ko": {
          "broadcast": "삼춘리 주민 여러분께 알려 드립니다.
      이 안내는 2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보이며, 실시간 정보가 아닙니다.
      새벽 2시 20분까지 차로 출발하십시오. 의성북부초등학교까지 가는 길이 모델로 확인되었습니다.
      그보다 늦게 출발하는 길은 확인되지 않았습니다.
      실제 대피 장소는 공식 안내를 따르십시오.
      다시 알려 드립니다. 새벽 2시 20분까지 출발하십시오.
      공식 대피 명령이 우선합니다.",
          "call": "[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
      안녕하세요. [소속·이름]입니다. 삼춘리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
      지금 드리는 내용은 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보이며, 실시간 정보가 아닙니다.
      모델 계산으로는 마을 근처 도로에서 새벽 2시 20분까지 차로 출발하면 의성북부초등학교까지 가는 경로가 확인되었습니다.
      그보다 늦게 출발하는 경로는 확인되지 않았습니다.
      공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
      궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.",
          "card": "산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현
      삼춘리 (마을)
      모델로 확인된 차량 경로 있음
      출발 마감 02:20 (새벽 2시 20분 · 한국 시각)
      마감 시각까지 기다리지 말고 미리 차로 출발하십시오.
      모델이 점검한 도착지: 의성북부초등학교 · 02:20 출발 시 02:50쯤 도착(차로 약 30분, 교통 정체 미반영)
      02:20 이후 출발은 모델로 확인된 경로가 없습니다.
      실제 대피 장소와 길은 공식 안내를 따르십시오. 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
      공식 대피 명령이 우선합니다.
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
      모델 기반 계획 정보 · 실시간 아님
      시각은 마을에서 195 m 떨어진 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외 · 차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
      작성 2026-11-02 14:00 KST · 시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 사전 계산 2026-10-18 08:10 KST",
          "lms": "[산불 대피 계획 정보 · 2025년 기록 재현]
      삼춘리(마을)
      자료 기준: 2025년 3월 26일 02:00 (한국 시각)

      ■ 02:20(새벽 2시 20분)까지 차로 출발하십시오. 마감 시각까지 기다리지 마십시오.
      ■ 모델이 점검한 도착지: 의성북부초등학교. 02:20에 출발하면 02:50쯤 도착합니다(차로 약 30분, 교통 정체 미반영).
      ■ 02:20보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.
      ■ 실제 대피 장소와 길은 공식 안내를 따르십시오.
      ■ 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
      ■ 시각은 마을에서 195 m 떨어진 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
          "sms": "모델로 확인된 경로 있음
      02:20까지 출발
      공식명령 우선·실시간 아님
      25.3.26 02:00 재현",
        },
      }
    `);
  });

  it('model_no_route (구계리, 의성·안동, 2025-03-26 02:00 KST)', () => {
    expect(view(pick('uiseong_andong_2025/20250325T170000Z.json', 'osm:node/415160471'))).toMatchInlineSnapshot(`
      {
        "en": {
          "broadcast": "Attention, residents of Gugye-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time. It is not live information.
      In the model, there is no checked vehicle route from here. Call 119 or the eup/myeon office now, and follow official instructions.
      Again: call 119 or the eup/myeon office now.
      Official evacuation orders come first.",
          "call": "[Before the call] Official evacuation orders come first. What follows is model-based planning information, not live information. Fill in the [brackets] yourself.
      [Before the call] Check that 119 and the eup/myeon office have been contacted first.
      Hello, this is [your name and role]. I am calling the family of [resident name], who lives in Gugye-ri, about the wildfire evacuation plan.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time. It is not live information.
      In the model, there was no checked vehicle route from the village. So 119 and the eup/myeon office must be contacted now, and official instructions followed.
      Official evacuation orders come first. The actual place and time of any move may change with official guidance.
      If you have questions, please call [phone number]. Thank you.",
          "card": "Evacuation plan card · Uiseong–Andong · Recorded 2025 wildfire · scenario replay
      Gugye-ri (Village)
      No checked vehicle route in the model
      Call 119 or the eup/myeon office now and follow official instructions.
      "No route in the model" means no checked route for any departure time or destination that was checked.
      Official evacuation orders come first.
      Data time: 2025-03-26 02:00 KST · Replay of recorded 2025 wildfire scenarios
      Model-based planning information · not live
      Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
      Planning aid only — not for live evacuation operations.
      Prepared 2026-11-02 14:00 KST · Scenario ffb1:20250325T170000Z:53e6da7897bf9b5b · Precomputed 2026-10-18 08:10 KST",
          "lms": "[Wildfire evacuation plan information - 2025 recorded replay]
      Gugye-ri (Village)
      Data time: 2025-03-26 02:00 KST

      - No checked vehicle route in the model.
      - Call 119 or the eup/myeon office now and follow official instructions.

      Official evacuation orders come first.
      Model-based planning information · not live
      Replay of recorded 2025 wildfire scenarios.
      Planning aid only - not for live evacuation operations.",
          "sms": "No route in the model.
      Call 119 or the eup/myeon office now.
      Official orders come first.
      Model-based info, not live.
      Replay of 2025-03-26 02:00 KST data",
        },
        "kind": "no_route",
        "ko": {
          "broadcast": "구계리 주민 여러분께 알려 드립니다.
      이 안내는 2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보이며, 실시간 정보가 아닙니다.
      모델로 계산한 결과, 이곳에서 차로 나가는 확인된 길이 없습니다. 지금 바로 119나 읍·면사무소에 연락하고, 공식 지시를 따르십시오.
      다시 알려 드립니다. 지금 바로 119나 읍·면사무소에 연락하십시오.
      공식 대피 명령이 우선합니다.",
          "call": "[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
      [통화 전 확인] 119와 읍·면사무소에 먼저 연락했는지 확인하십시오.
      안녕하세요. [소속·이름]입니다. 구계리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
      지금 드리는 내용은 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보이며, 실시간 정보가 아닙니다.
      모델 계산으로는 마을에서 차로 나가는 확인된 경로가 없었습니다. 그래서 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따라야 합니다.
      공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
      궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.",
          "card": "산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현
      구계리 (마을)
      모델상 확인된 차량 경로 없음
      지금 바로 119 또는 읍·면사무소에 연락하고 공식 지시를 따르십시오.
      모델상 경로 없음: 점검한 모든 출발 시각과 도착지에서 확인된 경로가 없었다는 뜻입니다.
      공식 대피 명령이 우선합니다.
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
      모델 기반 계획 정보 · 실시간 아님
      차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
      작성 2026-11-02 14:00 KST · 시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 사전 계산 2026-10-18 08:10 KST",
          "lms": "[산불 대피 계획 정보 · 2025년 기록 재현]
      구계리(마을)
      자료 기준: 2025년 3월 26일 02:00 (한국 시각)

      ■ 모델상 확인된 차량 경로가 없습니다.
      ■ 지금 바로 119 또는 읍·면사무소에 연락하고 공식 지시를 따르십시오.

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
          "sms": "모델상 경로 없음
      즉시 119·읍면사무소 연락
      공식명령 우선·실시간 아님
      25.3.26 02:00 재현",
        },
      }
    `);
  });

  it('unresolved (광연리, 의성·안동, 2025-03-26 02:00 KST)', () => {
    expect(view(pick('uiseong_andong_2025/20250325T170000Z.json', 'osm:node/415160467'))).toMatchInlineSnapshot(`
      {
        "en": {
          "broadcast": "Attention, residents of Gwang-yeon-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time. It is not live information.
      The model could not check a vehicle route from here. This means neither that a route exists nor that it does not. Follow official evacuation guidance.
      Again: follow official evacuation guidance.
      Official evacuation orders come first.",
          "call": "[Before the call] Official evacuation orders come first. What follows is model-based planning information, not live information. Fill in the [brackets] yourself.
      Hello, this is [your name and role]. I am calling the family of [resident name], who lives in Gwang-yeon-ri, about the wildfire evacuation plan.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time. It is not live information.
      The model could not check a vehicle route from the village (unresolved). This means neither that a route exists nor that it does not. Official evacuation guidance must be followed.
      Official evacuation orders come first. The actual place and time of any move may change with official guidance.
      If you have questions, please call [phone number]. Thank you.",
          "card": "Evacuation plan card · Uiseong–Andong · Recorded 2025 wildfire · scenario replay
      Gwang-yeon-ri (Village)
      Unresolved: the model could not check a route
      Unresolved means neither that a route exists nor that it does not.
      Follow official evacuation guidance.
      Official evacuation orders come first.
      Data time: 2025-03-26 02:00 KST · Replay of recorded 2025 wildfire scenarios
      Model-based planning information · not live
      Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
      Planning aid only — not for live evacuation operations.
      Prepared 2026-11-02 14:00 KST · Scenario ffb1:20250325T170000Z:53e6da7897bf9b5b · Precomputed 2026-10-18 08:10 KST",
          "lms": "[Wildfire evacuation plan information - 2025 recorded replay]
      Gwang-yeon-ri (Village)
      Data time: 2025-03-26 02:00 KST

      - The model could not check a vehicle route (unresolved).
      - Unresolved means neither that a route exists nor that it does not.
      - Follow official evacuation guidance.

      Official evacuation orders come first.
      Model-based planning information · not live
      Replay of recorded 2025 wildfire scenarios.
      Planning aid only - not for live evacuation operations.",
          "sms": "Unresolved: route not checked.
      Follow official evacuation guidance.
      Official orders come first.
      Model-based info, not live.
      Replay of 2025-03-26 02:00 KST data",
        },
        "kind": "unresolved",
        "ko": {
          "broadcast": "광연리 주민 여러분께 알려 드립니다.
      이 안내는 2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보이며, 실시간 정보가 아닙니다.
      모델로는 이곳의 차량 대피 길을 확인하지 못했습니다. 길이 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따르십시오.
      다시 알려 드립니다. 공식 대피 안내를 따르십시오.
      공식 대피 명령이 우선합니다.",
          "call": "[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
      안녕하세요. [소속·이름]입니다. 광연리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
      지금 드리는 내용은 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보이며, 실시간 정보가 아닙니다.
      모델 계산으로는 마을의 차량 대피 경로를 확인하지 못했습니다(미확인). 경로가 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따라야 합니다.
      공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
      궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.",
          "card": "산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현
      광연리 (마을)
      미확인: 모델로 확인하지 못함
      미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.
      공식 대피 안내를 따르십시오.
      공식 대피 명령이 우선합니다.
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
      모델 기반 계획 정보 · 실시간 아님
      차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
      작성 2026-11-02 14:00 KST · 시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 사전 계산 2026-10-18 08:10 KST",
          "lms": "[산불 대피 계획 정보 · 2025년 기록 재현]
      광연리(마을)
      자료 기준: 2025년 3월 26일 02:00 (한국 시각)

      ■ 모델로 차량 경로를 확인하지 못했습니다(미확인).
      ■ 미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.
      ■ 공식 대피 안내를 따르십시오.

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
          "sms": "경로 미확인(모델)
      공식 대피 안내를 따르세요
      공식명령 우선·실시간 아님
      25.3.26 02:00 재현",
        },
      }
    `);
  });
});
