/**
 * Loads public/data/provenance/<region>__<input>.json (same-origin, under Vite's BASE_URL) and accepts it only for the
 * exact cache entry on screen (path + sha256). Missing or foreign → null: the label is then "not established".
 */
import { useEffect, useState } from 'react';
import { compactUtc } from '../../domain/clock';
import type { CacheEntry } from '../../domain/types';
import { parseProvenanceFile, type ProvenanceFile } from './model';

function baseUrl(): string {
  const b = import.meta.env.BASE_URL || '/';
  return b.endsWith('/') ? b : `${b}/`;
}

export function provenanceUrl(regionId: string, inputTimeIso: string): string {
  return `${baseUrl()}data/provenance/${encodeURIComponent(`${regionId}__${compactUtc(inputTimeIso)}.json`)}`;
}

const pending = new Map<string, Promise<ProvenanceFile | null>>();

export function loadProvenanceFile(entry: CacheEntry): Promise<ProvenanceFile | null> {
  const url = provenanceUrl(entry.regionId, entry.inputTime);
  const key = `${url}#${entry.sha256}`;
  const hit = pending.get(key);
  if (hit) return hit;
  const p = (async () => {
    try {
      const r = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!r.ok || (r.headers.get('content-type') ?? '').includes('text/html')) return null;
      return parseProvenanceFile(await r.json(), { path: entry.path, sha256: entry.sha256 });
    } catch {
      return null;
    }
  })();
  pending.set(key, p);
  return p;
}

/** undefined while loading; null when absent or foreign. */
export function useProvenanceFile(entry: CacheEntry | null): ProvenanceFile | null | undefined {
  const [f, setF] = useState<ProvenanceFile | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setF(undefined);
    if (!entry) {
      setF(null);
      return;
    }
    void loadProvenanceFile(entry).then((x) => live && setF(x));
    return () => {
      live = false;
    };
  }, [entry]);
  return f;
}
