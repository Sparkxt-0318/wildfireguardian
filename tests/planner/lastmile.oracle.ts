/**
 * Independent oracles for the last-mile property tests (lastmile.cache.test.ts, lastmile.property.test.ts):
 * written here from the rules in planner/docs/LASTMILE.md, not from the module's own code paths.
 */
import { execFileSync } from 'node:child_process';
import type { FieldMessages } from '../../planner/src/features/lastmile/messages';

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
