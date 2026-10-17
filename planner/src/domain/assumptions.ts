/**
 * Verbatim rendering of the API's `assumptions` object (RouteCheckResult.assumptions,
 * DispatchPlanResult.assumptions) as readable key–value rows. Nothing is paraphrased, rounded,
 * unit-converted or translated: numbers are printed with String(n) (the shortest round-trip form of
 * the value the API sent), strings as sent, booleans/null as JSON. Unit-tested in
 * tests/planner/zones.test.ts.
 */

export interface AssumptionRow {
  /** full dotted path, e.g. "clock.issued_at" or "bands_detail[0].cells" */
  path: string;
  /** last path segment */
  key: string;
  depth: number;
  /** null for a group header (object / array of objects) */
  value: string | null;
  kind: 'number' | 'string' | 'boolean' | 'null' | 'array' | 'group';
}

const MAX_DEPTH = 6;

/** A primitive exactly as sent: numbers via String(n), strings unchanged, booleans/null as JSON words. */
export function primitiveText(v: unknown): string {
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'number') return String(v);
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'string') return v;
  return JSON.stringify(v);
}

function isPrimitive(v: unknown): boolean {
  return v === null || v === undefined || typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean';
}

function kindOf(v: unknown): AssumptionRow['kind'] {
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'number') return 'number';
  if (typeof v === 'boolean') return 'boolean';
  return 'string';
}

/** Array of primitives on one line: [-1, 1.6666666666666665, null] (strings JSON-quoted). */
export function arrayText(xs: unknown[]): string {
  return `[${xs.map((x) => (typeof x === 'string' ? JSON.stringify(x) : primitiveText(x))).join(', ')}]`;
}

/** Flattens the object in key order (as sent). */
export function flattenAssumptions(obj: unknown): AssumptionRow[] {
  const rows: AssumptionRow[] = [];
  const walk = (v: unknown, path: string, key: string, depth: number) => {
    if (isPrimitive(v)) {
      rows.push({ path, key, depth, value: primitiveText(v), kind: kindOf(v) });
      return;
    }
    if (Array.isArray(v)) {
      if (v.every(isPrimitive) || depth >= MAX_DEPTH) {
        rows.push({ path, key, depth, value: v.every(isPrimitive) ? arrayText(v) : JSON.stringify(v), kind: 'array' });
        return;
      }
      rows.push({ path, key, depth, value: null, kind: 'group' });
      v.forEach((x, i) => walk(x, `${path}[${i}]`, `[${i}]`, depth + 1));
      return;
    }
    if (typeof v === 'object' && v) {
      if (depth >= MAX_DEPTH) {
        rows.push({ path, key, depth, value: JSON.stringify(v), kind: 'string' });
        return;
      }
      if (path) rows.push({ path, key, depth, value: null, kind: 'group' });
      for (const [k, x] of Object.entries(v as Record<string, unknown>)) walk(x, path ? `${path}.${k}` : k, k, path ? depth + 1 : depth);
    }
  };
  if (obj && typeof obj === 'object' && !Array.isArray(obj)) walk(obj, '', '', 0);
  else if (obj !== undefined) walk(obj, 'value', 'value', 0);
  return rows;
}

/** The mock marks its spread-zone answers {mock: true, evaluated: false, text: {ko, en}}. */
export function mockAssumptionText(a: Record<string, unknown> | null | undefined, lang: 'ko' | 'en'): string | null {
  if (!a || a.mock !== true) return null;
  const text = a.text;
  if (typeof text === 'string') return text;
  if (text && typeof text === 'object') {
    const t = text as Record<string, unknown>;
    const v = t[lang] ?? t.ko ?? t.en;
    return typeof v === 'string' ? v : null;
  }
  return null;
}
