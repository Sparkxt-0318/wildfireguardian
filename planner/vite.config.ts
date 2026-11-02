/// <reference types="vitest/config" />
import { cpSync, createReadStream, existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { defineConfig, loadEnv, type Plugin, type ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';

const here = dirname(fileURLToPath(import.meta.url));

const MIME: Record<string, string> = {
  '.json': 'application/json; charset=utf-8',
  '.geojson': 'application/geo+json; charset=utf-8',
  '.csv': 'text/csv; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

/**
 * Vite `base` from VITE_BASE_PATH: "" or "/" → "/"; "./" stays relative (a build that works under
 * any path); "wildfireguardian" or "/wildfireguardian" → "/wildfireguardian/" (GitHub Pages).
 * Full URLs are refused: the static demo loads nothing from another origin.
 */
export function normalizeBasePath(raw: string | undefined): string {
  const b = String(raw ?? '').trim();
  if (b === '' || b === '/') return '/';
  if (b === '.' || b === './') return './';
  if (/^[a-z][a-z0-9+.-]*:/i.test(b) || b.startsWith('//')) throw new Error(`VITE_BASE_PATH must be a path ("/", "/wildfireguardian/" or "./"), not ${b}`);
  if (b.startsWith('./')) return b.endsWith('/') ? b : `${b}/`;
  const trimmed = b.replace(/^\/+/, '').replace(/\/+$/, '');
  return trimmed ? `/${trimmed}/` : '/';
}

/**
 * Content-Security-Policy of static builds (the public demo): every fetch, image, font, script,
 * worker and style must come from the page's own origin (MapLibre's worker and the plan sheet's
 * map snapshot use blob:/data: URLs, which never leave the browser). The browser refuses anything
 * else — e.g. a request to http://127.0.0.1:8765, localhost or an internet tile server.
 */
export const STATIC_CSP = [
  "default-src 'self'",
  "connect-src 'self' data: blob:",
  "script-src 'self'",
  "worker-src 'self' blob:",
  "child-src 'self' blob:",
  "img-src 'self' data: blob:",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "media-src 'self'",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'none'",
].join('; ');

/** Adds the static-demo CSP as the first element of <head> (build only: dev needs inline HMR scripts). */
function staticCsp(): Plugin {
  return {
    name: 'wfg-static-csp',
    apply: 'build',
    transformIndexHtml() {
      return [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: STATIC_CSP }, injectTo: 'head-prepend' }];
    },
  };
}

/**
 * Serves planner/cache/** (written by planner/scripts/precompute.py) at <base>cache/** in dev and
 * preview, and copies it into dist/cache on build. A missing folder is fine: the app then
 * reports "no precomputed cache" and computes through the API instead.
 */
/**
 * Precompute cache folder served at <base>cache/**. Default planner/cache (the booth cache).
 * WFG_CACHE_DIR (relative to planner/ or absolute; environment or .env) points elsewhere, e.g.
 * planner/.test-cache for results computed on a non-evaluation host (ARCHITECTURE.md §6).
 */
function plannerCache(CACHE_DIR: string, basePath: string): Plugin {
  let outDir = resolve(here, 'dist');
  let isBuild = false;
  const middleware = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    let url = (req.url ?? '').split('?')[0] ?? '';
    // the dev/preview servers may hand the URL over with or without the base path
    if (basePath.startsWith('/') && basePath !== '/' && url.startsWith(basePath)) url = `/${url.slice(basePath.length)}`;
    if (!url.startsWith('/cache/')) return next();
    let rel: string;
    try {
      rel = decodeURIComponent(url.slice('/cache/'.length));
    } catch {
      res.statusCode = 400;
      res.end('bad path');
      return;
    }
    const file = normalize(join(CACHE_DIR, rel));
    // never serve the precompute's resumable working state
    const hidden = rel.split('/').some((part) => part.startsWith('.'));
    if (hidden || !file.startsWith(CACHE_DIR + sep) || !existsSync(file) || !statSync(file).isFile()) {
      res.statusCode = 404;
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.end(JSON.stringify({ error: { code: 'NOT_FOUND', message: `no cache file ${rel}` } }));
      return;
    }
    res.statusCode = 200;
    res.setHeader('Content-Type', MIME[extname(file)] ?? 'application/octet-stream');
    res.setHeader('Cache-Control', 'no-cache');
    createReadStream(file).pipe(res);
  };
  return {
    name: 'wfg-planner-cache',
    configResolved(cfg) {
      outDir = resolve(cfg.root, cfg.build.outDir);
      isBuild = cfg.command === 'build' && !process.env.VITEST;
    },
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
    closeBundle() {
      if (!isBuild) return;
      if (!existsSync(CACHE_DIR)) {
        this.warn('planner/cache not found: the build has no precomputed cache (the app computes via the API).');
        return;
      }
      // never ship test data silently as the booth cache (the app also marks it in the UI)
      const booth = resolve(here, 'cache');
      if (CACHE_DIR !== booth) this.warn(`TEST CACHE: copying ${CACHE_DIR} (WFG_CACHE_DIR) into dist/cache — this is NOT the booth cache planner/cache.`);
      try {
        const index = JSON.parse(readFileSync(join(CACHE_DIR, 'INDEX.json'), 'utf8')) as { api_mode?: string; purpose?: string; host?: { platform?: string; machine?: string } | null; path?: string }[];
        for (const e of Array.isArray(index) ? index : []) {
          const plat = String(e.host?.platform ?? '');
          const evalHost = (plat.startsWith('macOS') || plat.includes('Darwin')) && e.host?.machine === 'arm64';
          if (e.api_mode === 'mock' || e.purpose === 'test' || !evalHost) {
            this.warn(`cache ${e.path ?? '?'} is ${e.api_mode === 'mock' ? 'MOCK' : 'test data (not the evaluation host)'} — it ships in dist/cache labelled as such, not as the booth cache.`);
          }
        }
      } catch {
        /* no or unreadable INDEX.json: nothing to check */
      }
      cpSync(CACHE_DIR, join(outDir, 'cache'), {
        recursive: true,
        filter: (src) => !src.slice(CACHE_DIR.length).split(sep).some((part) => part.startsWith('.')),
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, here, ['VITE_', 'VWORLD_', 'WFG_']);
  const cacheDir = resolve(here, env.WFG_CACHE_DIR || 'cache');
  // The one switch: mock → the mock server on 8765; real → VITE_WFG_API_TARGET (default 8765,
  // where the real API runs on the booth machine); static (`--mode static`) → no API at all.
  const rawMode = (env.VITE_WFG_API_MODE || 'mock').trim().toLowerCase();
  const apiMode = mode === 'static' || rawMode === 'static' ? 'static' : rawMode === 'real' ? 'real' : 'mock';
  const base = normalizeBasePath(env.VITE_BASE_PATH);
  const target = (apiMode === 'mock' ? 'http://127.0.0.1:8765' : env.VITE_WFG_API_TARGET || 'http://127.0.0.1:8765').replace(/\/+$/, '');
  // static: no proxy, so even the dev/preview server never forwards anything to an API
  const proxy: Record<string, ProxyOptions> =
    apiMode === 'static'
      ? {}
      : {
          '/api/v1': {
            target,
            changeOrigin: true,
            rewrite: (p) => p.replace(/^\/api\/v1/, '/v1'),
          },
        };
  return {
    root: here,
    base,
    // the static demo's public bundle never carries the optional VWorld key
    envPrefix: apiMode === 'static' ? ['VITE_'] : ['VITE_', 'VWORLD_'],
    plugins: [react(), plannerCache(cacheDir, base), ...(apiMode === 'static' ? [staticCsp()] : [])],
    server: { host: '127.0.0.1', port: 5173, strictPort: false, proxy },
    preview: { host: '127.0.0.1', port: 4173, strictPort: false, proxy },
    build: { outDir: 'dist', emptyOutDir: true, chunkSizeWarningLimit: 1700, sourcemap: false },
    test: {
      dir: resolve(here, '../tests/planner'),
      include: ['**/*.test.ts'],
      environment: 'node',
      server: { deps: { inline: [] } },
    },
  };
});
