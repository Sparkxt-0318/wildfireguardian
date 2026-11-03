/**
 * URLs of files the app serves itself, under the Vite `base` (VITE_BASE_PATH; GitHub Pages:
 * "/wildfireguardian/"; a relative "./" makes a build that works under any path).
 *
 * Everything the planner reads from its own origin — planner/public/** (`data/…`, `basemap/…`) and
 * the precompute cache (`cache/…`) — is addressed through these helpers, never as a root-absolute
 * "/data/…" string, so the same code works at "/" (vite dev / preview / booth), under a sub-path
 * and with a relative base.
 *
 *   appPath('data/regions/index.json')            // "/wildfireguardian/data/regions/index.json"
 *   appUrl('basemap/fonts/{fontstack}/{range}.pbf') // "https://host/wildfireguardian/basemap/fonts/{fontstack}/{range}.pbf"
 *
 * Any file placed under planner/public/data/** (e.g. a generated `data/explanations/<file>.json`)
 * is served at `appPath('data/<file>')` without further configuration; `fetchAppJson` reads one.
 */

/** Vite's base as the build saw it: "/", "/wildfireguardian/" or "./" (always ends with "/"). */
export const BASE_URL: string = normalizeBase(import.meta.env.BASE_URL);

/**
 * Normalises a base setting: "" or "/" → "/"; "." or "./" → "./"; "wildfireguardian" or
 * "/wildfireguardian" → "/wildfireguardian/". Full URLs ("https://…") are returned with a trailing
 * slash (Vite accepts them; the static demo refuses them in vite.config.ts).
 */
export function normalizeBase(raw: string | null | undefined): string {
  const b = String(raw ?? '').trim();
  if (b === '' || b === '/') return '/';
  if (b === '.' || b === './') return './';
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(b)) return b.endsWith('/') ? b : `${b}/`;
  if (b.startsWith('./')) return b.endsWith('/') ? b : `${b}/`;
  const trimmed = b.replace(/^\/+/, '').replace(/\/+$/, '');
  return trimmed ? `/${trimmed}/` : '/';
}

function stripLeadingSlashes(path: string): string {
  return path.replace(/^\/+/, '');
}

function currentHref(): string | null {
  return typeof window !== 'undefined' && window.location && typeof window.location.href === 'string' ? window.location.href : null;
}

/** Path of an app file for fetch(): base + path (leading slashes of `path` are ignored). */
export function appPath(path: string, base: string = BASE_URL): string {
  const b = normalizeBase(base);
  return b + stripLeadingSlashes(path);
}

/**
 * Directory of the app on its origin as an absolute URL ("https://host/wildfireguardian/"). A
 * relative base is resolved against the page URL (`href`).
 */
export function appDirUrl(base: string = BASE_URL, href: string | null = currentHref()): string | null {
  if (!href) return null;
  try {
    return new URL(normalizeBase(base), href).href;
  } catch {
    return null;
  }
}

/** Path of the app directory on its origin ("/" or "/wildfireguardian/"). */
export function appDirPath(base: string = BASE_URL, href: string | null = currentHref()): string {
  const dir = appDirUrl(base, href);
  if (dir) return new URL(dir).pathname;
  const b = normalizeBase(base);
  return b.startsWith('/') ? b : '/';
}

/**
 * Absolute URL of an app file. MapLibre style URLs must be absolute; template tokens such as
 * "{fontstack}" are appended as text and stay unescaped.
 */
export function appUrl(path: string, base: string = BASE_URL, href: string | null = currentHref()): string {
  const dir = appDirUrl(base, href);
  return dir ? dir + stripLeadingSlashes(path) : appPath(path, base);
}

/**
 * Reads a JSON file the app serves itself (`path` relative to the app, e.g.
 * "data/explanations/<file>.json"). Resolves null when the file does not exist (404, or an HTML
 * fallback page), so optional files need no special handling; other failures throw.
 */
export async function fetchAppJson<T = unknown>(path: string, signal?: AbortSignal): Promise<T | null> {
  const r = await fetch(appPath(path), { signal, headers: { Accept: 'application/json' } });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  if ((r.headers.get('content-type') ?? '').includes('text/html')) return null;
  return (await r.json()) as T;
}
