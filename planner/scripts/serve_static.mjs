#!/usr/bin/env node
/**
 * Serves a static-demo build (planner/dist) the way GitHub Pages does, and nothing else:
 *
 *   - only the files in dist/, under the base path (default /wildfireguardian/); no proxy, no
 *     middleware, no planner/cache — the copy in dist/cache is what is served;
 *   - a missing file is a 404 (no single-page-app fallback to index.html); a folder without its
 *     trailing slash is redirected to it, and a folder is served through its index.html;
 *   - HTTP Range requests answer 206 with Content-Range (the PMTiles basemaps read byte ranges);
 *   - GET and HEAD only; hidden files (a path part starting with ".") are never served.
 *
 *   node scripts/serve_static.mjs [--dir dist] [--base /wildfireguardian/] [--port 4180]
 *
 * scripts/static_smoke.mjs uses it by default (startStaticServer).
 */
import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.geojson': 'application/geo+json',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf',
  '.pbf': 'application/x-protobuf',
  '.pmtiles': 'application/octet-stream',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.csv': 'text/csv; charset=utf-8',
  '.pdf': 'application/pdf',
};

export function normalizeBase(raw) {
  const b = String(raw ?? '/').replace(/^\/+|\/+$/g, '');
  return b ? `/${b}/` : '/';
}

/** "bytes=a-b" / "bytes=a-" / "bytes=-n" → {start, end} (inclusive), "invalid", or null (no usable single range). */
export function parseRange(header, size) {
  const m = /^bytes=(\d*)-(\d*)$/.exec(String(header ?? '').trim());
  if (!m || (m[1] === '' && m[2] === '')) return null;
  let start;
  let end;
  if (m[1] === '') {
    const n = Number(m[2]);
    if (n === 0) return 'invalid';
    start = Math.max(0, size - n);
    end = size - 1;
  } else {
    start = Number(m[1]);
    end = m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1);
  }
  if (start >= size || start > end) return 'invalid';
  return { start, end };
}

/** Resolves a request path to a file in `root` ({file} | {redirect} | null for 404). */
export function resolvePath(urlPath, root, base) {
  if (!urlPath.startsWith(base) && `${urlPath}/` !== base) return null;
  if (`${urlPath}/` === base) return { redirect: base };
  let rel;
  try {
    rel = decodeURIComponent(urlPath.slice(base.length));
  } catch {
    return null;
  }
  if (rel.split('/').some((part) => part.startsWith('.') || part.includes('\0'))) return null;
  const file = normalize(join(root, rel));
  if (file !== root && !file.startsWith(root + sep)) return null;
  if (!existsSync(file)) return null;
  const st = statSync(file);
  if (st.isDirectory()) {
    if (rel !== '' && !rel.endsWith('/')) return { redirect: `${urlPath}/` };
    const index = join(file, 'index.html');
    return existsSync(index) ? { file: index } : null;
  }
  return st.isFile() ? { file } : null;
}

export function startStaticServer({ dir, base = '/wildfireguardian/', port = 4180, host = '127.0.0.1', log = null } = {}) {
  const root = resolve(dir);
  const b = normalizeBase(base);
  const server = createServer((req, res) => {
    const method = req.method ?? 'GET';
    const urlPath = (req.url ?? '/').split('?')[0].split('#')[0];
    const done = (status, extra = '') => log?.(`${status} ${method} ${urlPath}${extra}`);
    if (method !== 'GET' && method !== 'HEAD') {
      res.writeHead(405, { Allow: 'GET, HEAD', 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('method not allowed');
      return done(405);
    }
    const hit = resolvePath(urlPath, root, b);
    if (!hit) {
      res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(method === 'HEAD' ? undefined : '<!doctype html><title>404</title><h1>404 — File not found</h1>');
      return done(404);
    }
    if (hit.redirect) {
      res.writeHead(301, { Location: hit.redirect });
      res.end();
      return done(301);
    }
    const size = statSync(hit.file).size;
    const headers = {
      'Content-Type': TYPES[extname(hit.file).toLowerCase()] ?? 'application/octet-stream',
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'max-age=600',
    };
    const range = req.headers.range ? parseRange(req.headers.range, size) : null;
    if (range === 'invalid') {
      res.writeHead(416, { ...headers, 'Content-Range': `bytes */${size}` });
      res.end();
      return done(416);
    }
    if (range) {
      res.writeHead(206, { ...headers, 'Content-Range': `bytes ${range.start}-${range.end}/${size}`, 'Content-Length': range.end - range.start + 1 });
      if (method === 'HEAD') res.end();
      else createReadStream(hit.file, { start: range.start, end: range.end }).pipe(res);
      return done(206, ` ${range.start}-${range.end}`);
    }
    res.writeHead(200, { ...headers, 'Content-Length': size });
    if (method === 'HEAD') res.end();
    else createReadStream(hit.file).pipe(res);
    return done(200);
  });
  return new Promise((ok, fail) => {
    server.once('error', fail);
    server.listen(port, host, () => ok({ server, url: `http://${host}:${server.address().port}${b}`, close: () => new Promise((r) => server.close(() => r())) }));
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const opt = (name, fallback) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : fallback;
  };
  const here = resolve(fileURLToPath(new URL('..', import.meta.url)));
  const dir = resolve(opt('--dir', join(here, 'dist')));
  if (!existsSync(join(dir, 'index.html'))) {
    console.error(`[serve] ${dir}/index.html not found — run: VITE_BASE_PATH=/wildfireguardian/ npm run build:static`);
    process.exit(1);
  }
  const { url } = await startStaticServer({ dir, base: opt('--base', process.env.VITE_BASE_PATH || '/wildfireguardian/'), port: Number(opt('--port', '4180')), log: args.includes('--quiet') ? null : (l) => console.log(`[serve] ${l}`) });
  console.log(`[serve] ${dir} (dist only, like GitHub Pages) at ${url}`);
}
