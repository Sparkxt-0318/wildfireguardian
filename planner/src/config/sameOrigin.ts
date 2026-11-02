/**
 * fetch() guard for the static demo and root-path compatibility under a sub-path base.
 *
 * - Rewrite (any mode, only when the app is not served at "/"): a root-absolute path of an app
 *   folder — "/data/…", "/cache/…", "/basemap/…" — that is not already under the app directory is
 *   moved under it ("/wildfireguardian/data/…"). Code that addresses planner/public/** with a
 *   leading slash therefore keeps working on GitHub Pages without changes.
 * - Block (static demo only, VITE_WFG_API_MODE=static): a request that would leave the page's
 *   origin (another host, or another port such as http://127.0.0.1:8765 or localhost) or that
 *   addresses the Route-Check API (".../api/…") is refused before anything is sent: the promise
 *   rejects with a TypeError, exactly like a network failure. Static builds also carry a
 *   Content-Security-Policy (`connect-src 'self'`, see vite.config.ts) that the browser enforces
 *   for every request type.
 *
 * `guardUrl` is pure (unit-tested); `installFetchGuard` wraps globalThis.fetch once.
 */

/** App folders that may be addressed root-absolute ("/data/…") by code written for base "/". */
export const APP_FOLDERS = ['data', 'cache', 'basemap'] as const;

export interface GuardContext {
  /** page URL (location.href); relative request URLs resolve against it */
  pageHref: string;
  /** app directory path on the origin, e.g. "/" or "/wildfireguardian/" (with trailing slash) */
  appDir: string;
  /** static demo: refuse cross-origin and API requests */
  block: boolean;
}

export type GuardDecision =
  | { action: 'pass'; url: string }
  | { action: 'rewrite'; url: string }
  | { action: 'block'; reason: string };

const LOCAL_SCHEME = /^(data|blob):/i;

/** Decides what happens to one request URL (pure). */
export function guardUrl(raw: string, ctx: GuardContext): GuardDecision {
  if (LOCAL_SCHEME.test(raw)) return { action: 'pass', url: raw }; // never leaves the browser
  let page: URL;
  let u: URL;
  try {
    page = new URL(ctx.pageHref);
    u = new URL(raw, page);
  } catch {
    return ctx.block ? { action: 'block', reason: `unparseable URL ${raw}` } : { action: 'pass', url: raw };
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') {
    return ctx.block ? { action: 'block', reason: `${u.protocol} request ${u.href}` } : { action: 'pass', url: raw };
  }
  if (u.origin !== page.origin) {
    return ctx.block ? { action: 'block', reason: `cross-origin request ${u.origin} (page ${page.origin})` } : { action: 'pass', url: raw };
  }
  const appDir = ctx.appDir.endsWith('/') ? ctx.appDir : `${ctx.appDir}/`;
  const inApp = u.pathname.startsWith(appDir);
  const rel = inApp ? u.pathname.slice(appDir.length) : u.pathname.replace(/^\/+/, '');
  if (ctx.block && /^api(\/|$)/.test(rel)) {
    return { action: 'block', reason: `Route-Check API request ${u.pathname} (static demo: no API)` };
  }
  if (!inApp && appDir !== '/' && APP_FOLDERS.some((f) => rel.startsWith(`${f}/`))) {
    return { action: 'rewrite', url: `${appDir}${rel}${u.search}${u.hash}` };
  }
  return { action: 'pass', url: raw };
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

type FetchFn = typeof fetch;

/** Blocked requests seen in this page (for diagnostics and the smoke test). */
export const blockedRequests: string[] = [];

/**
 * Wraps `target.fetch` (default globalThis) with `guardUrl`. Does nothing when there is nothing to
 * guard (not static and served at "/") or when fetch/location are missing. Returns the uninstall
 * function (tests).
 */
export function installFetchGuard(opts: { block: boolean; appDir: string; target?: { fetch?: FetchFn; location?: { href: string } } }): () => void {
  const target = opts.target ?? (globalThis as unknown as { fetch?: FetchFn; location?: { href: string } });
  const original = target.fetch;
  if (typeof original !== 'function' || !target.location) return () => {};
  if (!opts.block && (opts.appDir === '/' || opts.appDir === '')) return () => {};
  const loc = target.location;
  const guarded: FetchFn = (input, init) => {
    const raw = requestUrl(input);
    const d = guardUrl(raw, { pageHref: loc.href, appDir: opts.appDir, block: opts.block });
    if (d.action === 'block') {
      blockedRequests.push(raw);
      if (typeof console !== 'undefined') console.error(`[static demo] blocked: ${d.reason}`);
      return Promise.reject(new TypeError(`blocked by the static demo: ${d.reason}`));
    }
    if (d.action === 'rewrite') {
      const next = typeof input === 'string' || input instanceof URL ? d.url : new Request(d.url, input);
      return original.call(target, next, init);
    }
    return original.call(target, input, init);
  };
  target.fetch = guarded;
  return () => {
    if (target.fetch === guarded) target.fetch = original;
  };
}
