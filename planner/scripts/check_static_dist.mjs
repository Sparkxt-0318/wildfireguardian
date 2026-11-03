#!/usr/bin/env node
/**
 * Checks a static-demo build (`npm run build:static` → planner/dist) before it is published:
 *
 *   - every file < 100 MiB and the whole folder < 1 GiB (GitHub Pages limits; prints the totals and
 *     the largest files, in MiB = 1024² bytes);
 *   - index.html carries the static-demo Content-Security-Policy (connect-src 'self') and loads
 *     its scripts from the configured base path;
 *   - dist/cache/INDEX.json lists every cache file, and each shipped file has exactly the bytes
 *     and SHA-256 that INDEX.json records (the demo replays the committed results unchanged);
 *   - the forecast cells (dist/data/forecast, saved by scripts/save_forecasts.py): every file has
 *     the bytes and SHA-256 its INDEX.json records, matched the cached route checks when it was
 *     saved, and every cached scenario has one;
 *   - basemaps: dist/basemap/<region>.pmtiles for every region the demo lists (regions with cached
 *     results) and none for the regions it does not list;
 *   - no hidden working folders (cache/.state) or .env files are shipped.
 *
 * Usage: node scripts/check_static_dist.mjs [dist] [--base /wildfireguardian/] [--json report.json]
 * Exit code 1 on any failure.
 */
import { createHash } from 'node:crypto';
import { createReadStream, existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';

const MB = 1024 * 1024;
const FILE_LIMIT = 100 * MB;
const TOTAL_LIMIT = 1024 * MB;

const args = process.argv.slice(2);
const opt = (name) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
};
const dist = resolve(args.find((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--'))) ?? 'dist');
const wantBase = opt('--base') ?? process.env.VITE_BASE_PATH ?? null;
const jsonOut = opt('--json');

const failures = [];
const fail = (m) => failures.push(m);

if (!existsSync(join(dist, 'index.html'))) {
  console.error(`[check] ${dist}/index.html not found — run npm run build:static first`);
  process.exit(1);
}

function walk(dir, out = []) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (e.isFile()) out.push({ path: relative(dist, p).split(sep).join('/'), bytes: statSync(p).size });
  }
  return out;
}

const files = walk(dist);
const total = files.reduce((n, f) => n + f.bytes, 0);
const largest = [...files].sort((a, b) => b.bytes - a.bytes).slice(0, 12);
for (const f of files) {
  if (f.bytes >= FILE_LIMIT) fail(`${f.path} is ${(f.bytes / MB).toFixed(1)} MiB (limit 100 MiB)`);
  if (f.path.split('/').some((part) => part.startsWith('.'))) fail(`hidden file shipped: ${f.path}`);
  if (/(^|\/)\.?env(\.|$)/.test(f.path)) fail(`env file shipped: ${f.path}`);
}
if (total >= TOTAL_LIMIT) fail(`dist is ${(total / MB).toFixed(1)} MiB (limit 1 GiB)`);

const byTop = {};
for (const f of files) {
  const top = f.path.includes('/') ? f.path.split('/')[0] : '(root)';
  byTop[top] = (byTop[top] ?? 0) + f.bytes;
}

// index.html: CSP + base path
const html = readFileSync(join(dist, 'index.html'), 'utf8');
const decode = (s) => s.replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const rawCsp = /<meta[^>]+http-equiv="Content-Security-Policy"[^>]+content="([^"]+)"/i.exec(html)?.[1] ?? null;
const csp = rawCsp === null ? null : decode(rawCsp);
if (!csp) fail('index.html has no Content-Security-Policy meta tag (not a static-demo build? use npm run build:static)');
else {
  if (!/connect-src 'self'/.test(csp)) fail(`CSP lacks connect-src 'self': ${csp}`);
  if (/https?:\/\/|\*/.test(csp)) fail(`CSP allows another origin: ${csp}`);
}
const scriptSrcs = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map((m) => m[1]);
if (!scriptSrcs.length) fail('index.html loads no script');
for (const s of scriptSrcs) {
  if (/^(https?:)?\/\//.test(s)) fail(`index.html loads a script from another origin: ${s}`);
  if (wantBase && !s.startsWith(wantBase)) fail(`script ${s} is not under the base ${wantBase}`);
}

// cache integrity
async function sha256(p) {
  const h = createHash('sha256');
  await new Promise((res, rej) => createReadStream(p).on('data', (d) => h.update(d)).on('end', res).on('error', rej));
  return h.digest('hex');
}
const cacheReport = [];
const indexPath = join(dist, 'cache', 'INDEX.json');
if (!existsSync(indexPath)) fail('dist/cache/INDEX.json missing: the demo would have no recorded results');
else {
  const index = JSON.parse(readFileSync(indexPath, 'utf8'));
  const entries = Array.isArray(index) ? index : [];
  if (!entries.length) fail('dist/cache/INDEX.json lists no cache file');
  for (const e of entries) {
    const p = join(dist, 'cache', ...String(e.path).split('/'));
    if (!existsSync(p)) {
      fail(`cache file listed but missing: ${e.path}`);
      continue;
    }
    const bytes = statSync(p).size;
    const digest = await sha256(p);
    if (e.bytes !== undefined && bytes !== e.bytes) fail(`${e.path}: ${bytes} bytes, INDEX.json says ${e.bytes}`);
    if (e.sha256 && digest !== e.sha256) fail(`${e.path}: sha256 ${digest} ≠ INDEX.json ${e.sha256}`);
    cacheReport.push({ path: e.path, bytes, sha256: digest, checks: e.checks ?? null, region: e.region_id, input_time: e.input_time, host: e.host?.platform ?? null });
  }
}

// forecast cells of the cached scenarios (the static demo's forecast layer)
const cacheEntries = existsSync(indexPath) ? (JSON.parse(readFileSync(indexPath, 'utf8')) ?? []) : [];
const compact = (iso) => String(iso).replace(/[-:]/g, '').replace(/\.\d+/, '');
const forecastReport = [];
const fcIndexPath = join(dist, 'data', 'forecast', 'INDEX.json');
if (!existsSync(fcIndexPath)) console.log('[check] no dist/data/forecast/INDEX.json: the forecast layer stays off in the static demo');
else {
  const fcIndex = JSON.parse(readFileSync(fcIndexPath, 'utf8'));
  const fcFiles = Array.isArray(fcIndex.files) ? fcIndex.files : [];
  for (const f of fcFiles) {
    const p = join(dist, 'data', 'forecast', ...String(f.path).split('/'));
    if (!existsSync(p)) {
      fail(`forecast file listed but missing: ${f.path}`);
      continue;
    }
    const bytes = statSync(p).size;
    const digest = await sha256(p);
    if (bytes !== f.bytes) fail(`forecast ${f.path}: ${bytes} bytes, INDEX.json says ${f.bytes}`);
    if (digest !== f.sha256) fail(`forecast ${f.path}: sha256 ${digest} ≠ INDEX.json ${f.sha256}`);
    const matched = f.matches_cached_checks ?? {};
    const flags = ['region', 'input_time', 'scenario_set_id', 'checkpoint', 'graph_id', 'packet_hashes', 'not_mock'];
    if (!flags.every((k) => matched[k] === true)) fail(`forecast ${f.path}: did not match the cached route checks when saved ${JSON.stringify(matched)}`);
    if (f.path !== `${f.region_id}__${compact(f.input_time)}.json`) fail(`forecast ${f.path}: name does not match ${f.region_id} ${f.input_time}`);
    forecastReport.push({ path: f.path, bytes, sha256: digest, cells: f.cells });
  }
  for (const e of cacheEntries) {
    const f = fcFiles.find((x) => x.region_id === e.region_id && x.input_time === e.input_time);
    if (!f) fail(`no forecast file for the cached scenario ${e.region_id} ${e.input_time}`);
    else if (f.scenario_set_id !== e.scenario_set_id) fail(`forecast ${f.path}: scenario set ${f.scenario_set_id} ≠ cache ${e.scenario_set_id}`);
  }
}

// basemaps: the listed regions (cached results) only
const regionsPath = join(dist, 'data', 'regions', 'index.json');
const regionIds = existsSync(regionsPath) ? JSON.parse(readFileSync(regionsPath, 'utf8')).map((r) => r.region_id) : [];
const cachedRegions = new Set(cacheEntries.map((e) => e.region_id).filter((id) => regionIds.includes(id)));
const basemaps = { listed: [], removed: [] };
for (const id of regionIds) {
  const shipped = existsSync(join(dist, 'basemap', `${id}.pmtiles`));
  if (!cachedRegions.size || cachedRegions.has(id)) {
    if (!shipped) fail(`basemap/${id}.pmtiles missing for a listed region`);
    basemaps.listed.push(id);
  } else {
    if (shipped) fail(`basemap/${id}.pmtiles shipped although the demo does not list ${id}`);
    basemaps.removed.push(id);
  }
}

const report = {
  dist,
  files: files.length,
  total_bytes: total,
  total_mb: Number((total / MB).toFixed(2)),
  largest: largest.map((f) => ({ path: f.path, mb: Number((f.bytes / MB).toFixed(2)) })),
  by_folder_mb: Object.fromEntries(Object.entries(byTop).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k, Number((v / MB).toFixed(2))])),
  csp,
  scripts: scriptSrcs,
  cache: cacheReport,
  cache_checks_total: cacheReport.reduce((n, c) => n + (c.checks ?? 0), 0),
  forecast: forecastReport,
  basemaps,
  failures,
};

console.log(`[check] ${files.length} files, ${report.total_mb} MiB (${total} bytes) in ${dist}`);
console.log(`[check] by folder (MiB): ${JSON.stringify(report.by_folder_mb)}`);
console.log(`[check] largest: ${report.largest.slice(0, 6).map((f) => `${f.path} ${f.mb} MiB`).join(' · ')}`);
console.log(`[check] cache: ${cacheReport.length} files verified against INDEX.json sha256, ${report.cache_checks_total} recorded checks`);
console.log(`[check] forecast: ${forecastReport.length} files verified against data/forecast/INDEX.json sha256 (${forecastReport.reduce((n, f) => n + (f.cells ?? 0), 0)} cells)`);
console.log(`[check] basemaps: ${basemaps.listed.join(', ') || '—'} shipped; not listed, not shipped: ${basemaps.removed.join(', ') || '—'}`);
console.log(`[check] CSP: ${csp ?? '—'}`);
if (jsonOut) writeFileSync(jsonOut, JSON.stringify(report, null, 2));
if (failures.length) {
  for (const f of failures) console.error(`[check] FAIL ${f}`);
  process.exit(1);
}
console.log('[check] OK — every file < 100 MiB, total < 1 GiB, CSP present, cache and forecast files identical to their INDEX.json, basemaps of the listed regions only');
