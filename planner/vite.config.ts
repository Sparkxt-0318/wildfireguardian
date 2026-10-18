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
 * Serves planner/cache/** (written by planner/scripts/precompute.py) at /cache/** in dev and
 * preview, and copies it into dist/cache on build. A missing folder is fine: the app then
 * reports "no precomputed cache" and computes through the API instead.
 */
/**
 * Precompute cache folder served at /cache/**. Default planner/cache (the booth cache).
 * WFG_CACHE_DIR (relative to planner/ or absolute; environment or .env) points elsewhere, e.g.
 * planner/.test-cache for results computed on a non-evaluation host (ARCHITECTURE.md §6).
 */
function plannerCache(CACHE_DIR: string): Plugin {
  let outDir = resolve(here, 'dist');
  let isBuild = false;
  const middleware = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const url = (req.url ?? '').split('?')[0] ?? '';
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
  // where the real API runs on the booth machine).
  const apiMode = (env.VITE_WFG_API_MODE || 'mock').trim().toLowerCase() === 'real' ? 'real' : 'mock';
  const target = (apiMode === 'mock' ? 'http://127.0.0.1:8765' : env.VITE_WFG_API_TARGET || 'http://127.0.0.1:8765').replace(/\/+$/, '');
  const proxy: Record<string, ProxyOptions> = {
    '/api/v1': {
      target,
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/api\/v1/, '/v1'),
    },
  };
  return {
    root: here,
    envPrefix: ['VITE_', 'VWORLD_'],
    plugins: [react(), plannerCache(cacheDir)],
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
