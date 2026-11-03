/**
 * Loads public/data/explanations/<region>__<input>.json with a same-origin relative fetch under Vite's BASE_URL
 * (works in dev, preview, a sub-path deployment and a static demo). A missing, unreadable or foreign file resolves to
 * null — the UI then shows its fallback; nothing is ever invented in its place.
 */
import { compactUtc } from '../../domain/clock';
import { EXPLANATION_SCHEMA, type ExplFile } from './types';

function baseUrl(): string {
  // the literal import.meta.env.BASE_URL is what Vite replaces at build time ('/' or e.g. '/wildfireguardian/')
  const b = import.meta.env.BASE_URL || '/';
  return b.endsWith('/') ? b : `${b}/`;
}

export function explanationFileName(regionId: string, inputTimeIso: string): string {
  return `${regionId}__${compactUtc(inputTimeIso)}.json`;
}

export function explanationUrl(regionId: string, inputTimeIso: string): string {
  return `${baseUrl()}data/explanations/${encodeURIComponent(explanationFileName(regionId, inputTimeIso))}`;
}

/** Accepts only a wfg.explanation/1 document for exactly this region and input time. */
export function parseExplanationFile(raw: unknown, regionId: string, inputTimeIso: string): ExplFile | null {
  if (!raw || typeof raw !== 'object') return null;
  const d = raw as Partial<ExplFile>;
  if (d.schema !== EXPLANATION_SCHEMA || d.region_id !== regionId) return null;
  if (typeof d.input_time !== 'string' || compactUtc(d.input_time) !== compactUtc(inputTimeIso)) return null;
  if (!d.origins || typeof d.origins !== 'object' || Array.isArray(d.origins)) return null;
  return d as ExplFile;
}

const pending = new Map<string, Promise<ExplFile | null>>();
const settled = new Map<string, ExplFile | null>();

/** Already settled result (undefined while unknown) — lets components render synchronously from the cache. */
export function settledExplanation(regionId: string, inputTimeIso: string): ExplFile | null | undefined {
  return settled.get(explanationUrl(regionId, inputTimeIso));
}

export function loadExplanationFile(regionId: string, inputTimeIso: string): Promise<ExplFile | null> {
  const url = explanationUrl(regionId, inputTimeIso);
  const hit = pending.get(url);
  if (hit) return hit;
  const p = (async () => {
    try {
      const r = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!r.ok) return null;
      if ((r.headers.get('content-type') ?? '').includes('text/html')) return null; // an SPA fallback page, not our file
      return parseExplanationFile(await r.json(), regionId, inputTimeIso);
    } catch {
      return null;
    }
  })().then((f) => {
    settled.set(url, f);
    return f;
  });
  pending.set(url, p);
  return p;
}

/** Test hook: forget every loaded file. */
export function clearExplanationCache(): void {
  pending.clear();
  settled.clear();
}
