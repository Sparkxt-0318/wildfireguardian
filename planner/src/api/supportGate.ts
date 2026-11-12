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
/** Keys whose presence with any value other than null / undefined / false marks a support-masked packet. */
const MASK_KEYS = ['support', 'support_writer', 'support_semantics', 'support_channel'] as const;
const MAX_DEPTH = 6;

function obj(v: unknown): Record<string, unknown> | null {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

const present = (v: unknown) => v !== undefined && v !== null && v !== false;
const isMarker = (v: unknown) => typeof v === 'string' && v.trim().toUpperCase() === SUPPORT_WRITE_FAILED;

interface Scan { masked: boolean; writer: string | null; marker: boolean }

/**
 * Walks every nested object (not array elements, except marker lists) of a wire object. Leo's packets put the identity
 * at provenance.identity = { packet_writer_sha256, base_packet_writer_sha256, support_writer: {…} } (packets_f93.py
 * stamp()), so the writer hash is read as a SIBLING of support_writer as well as inside a support block.
 */
function scan(o: Record<string, unknown>, acc: Scan, depth: number): void {
  if (depth > MAX_DEPTH) return;
  if (o.support_write_failed === true) acc.marker = true;
  for (const k of ['status', 'raw_status', 'marker']) if (isMarker(o[k])) acc.marker = true;
  for (const k of ['notes', 'markers']) {
    const a = o[k];
    if (Array.isArray(a) && a.some(isMarker)) acc.marker = true;
  }
  const usi = o.unknown_support_involved;
  const holdsMask = MASK_KEYS.some((k) => present(o[k])) || (present(usi) && usi !== 'none');
  if (holdsMask) {
    acc.masked = true;
    const sib = o.packet_writer_sha256;
    if (!acc.writer && typeof sib === 'string' && SHA256.test(sib)) acc.writer = sib;
  }
  for (const [k, v] of Object.entries(o)) {
    const c = obj(v);
    if (!c) continue;
    // a writer hash inside a support block counts too
    if ((k === 'support' || k === 'support_writer') && !acc.writer && typeof c.packet_writer_sha256 === 'string' && SHA256.test(c.packet_writer_sha256)) acc.writer = c.packet_writer_sha256;
    scan(c, acc, depth + 1);
  }
}

/**
 * The unresolved reason code for a masked result, or null for an unmasked one. `sources` are the wire objects that may
 * carry support information: the attempt, the result, and the result's and job's provenance (null entries are ignored).
 * Any value of a mask key other than null / undefined / false counts as masked (fail closed).
 */
export function supportGate(...sources: unknown[]): string | null {
  const acc: Scan = { masked: false, writer: null, marker: false };
  for (const o of sources.map(obj)) if (o) scan(o, acc, 0);
  if (acc.marker) return SUPPORT_WRITE_FAILED;
  if (!acc.masked) return null;
  if (!acc.writer) return WRITER_IDENTITY_MISSING;
  return `${UNKNOWN_SUPPORT_NOT_EVALUATED}@${acc.writer.slice(0, 8)}`;
}

/** Split "<CODE>@<sha8>" into the code and the writer's sha8 (null when the code carries none). */
export function splitReasonCode(code: string): { code: string; writer: string | null } {
  const m = /^([A-Z_]+)@([0-9a-f]{8})$/.exec(code);
  return m ? { code: m[1]!, writer: m[2]! } : { code, writer: null };
}
