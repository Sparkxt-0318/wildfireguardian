/**
 * Fail-closed reader for results computed on a support-MASKED packet (F-9.3 support_mask, #152; design:
 * research/harness-2026-11/SUPPORT-OUTCOME/DESIGN.md; orchestrator decision (c), 2026-11-12).
 *
 * Until kit v2 emits the decision schema "wfg.journey-decision/2" with `unknown_support_involved` (PLAN Step 1b), the
 * planner cannot tell whether a masked result depended on cells of unknown fire state. So EVERY masked result is read
 * as "not evaluated", i.e. unresolved: never a route, never "no route", never safe. A masked result without its packet
 * writer's identity, or one whose support write failed, is unresolved with its own code. Unmasked results are
 * untouched (byte-identical).
 *
 * The writer identity travels inside the reason code as "<CODE>@<sha8>", so every staff surface that already shows
 * unresolved reasons (panel, timeline, CSV, A4 sheet) shows it too (Hannah's consumer rule 1: the writer identity
 * goes into every key, so results of different writers are never pooled under one code).
 */

export const UNKNOWN_SUPPORT_NOT_EVALUATED = 'UNKNOWN_SUPPORT_NOT_EVALUATED';
export const WRITER_IDENTITY_MISSING = 'WRITER_IDENTITY_MISSING';
export const SUPPORT_WRITE_FAILED = 'SUPPORT_WRITE_FAILED';

const SHA256 = /^[0-9a-f]{64}$/;

function obj(v: unknown): Record<string, unknown> | null {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function hasMarker(o: Record<string, unknown>): boolean {
  if (o.support_write_failed === true) return true;
  for (const k of ['status', 'raw_status', 'marker']) if (o[k] === SUPPORT_WRITE_FAILED) return true;
  for (const k of ['notes', 'markers']) {
    const a = o[k];
    if (Array.isArray(a) && a.some((x) => String(x) === SUPPORT_WRITE_FAILED)) return true;
  }
  return false;
}

/**
 * The unresolved reason code for a masked result, or null for an unmasked one. `sources` are the wire objects that may
 * carry support information: the attempt, the result, and the result's and job's provenance (null entries are ignored).
 */
export function supportGate(...sources: unknown[]): string | null {
  const objs = sources.map(obj).filter((o): o is Record<string, unknown> => o !== null);
  if (objs.some(hasMarker)) return SUPPORT_WRITE_FAILED;
  let masked = false;
  let writer: string | null = null;
  for (const o of objs) {
    const support = obj(o.support);
    const sw = obj(o.support_writer);
    // kit v2 emits support: null and unknown_support_involved: "none" for an UNMASKED packet (Priya, PLAN Step 1b)
    const usi = o.unknown_support_involved;
    if (support || sw || (usi !== undefined && usi !== null && usi !== 'none')) masked = true;
    for (const cand of [support?.packet_writer_sha256, sw?.packet_writer_sha256]) {
      if (!writer && typeof cand === 'string' && SHA256.test(cand)) writer = cand;
    }
  }
  if (!masked) return null;
  if (!writer) return WRITER_IDENTITY_MISSING;
  return `${UNKNOWN_SUPPORT_NOT_EVALUATED}@${writer.slice(0, 8)}`;
}

/** Split "<CODE>@<sha8>" into the code and the writer's sha8 (null when the code carries none). */
export function splitReasonCode(code: string): { code: string; writer: string | null } {
  const m = /^([A-Z_]+)@([0-9a-f]{8})$/.exec(code);
  return m ? { code: m[1]!, writer: m[2]! } : { code, writer: null };
}
