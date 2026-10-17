#!/usr/bin/env node
/**
 * Booth launcher for the WildfireGuardian 사전 대피계획 도구.
 *
 *   npm run demo                      # mock mode: starts the MOCK server if needed + the app
 *   npm run demo -- --mode real       # real Route-Check API at VITE_WFG_API_TARGET (default :8765)
 *   npm run demo -- --preview         # production build + `vite preview` (same proxy and /cache)
 *   npm run demo -- --open            # also open the browser (only once the app answers)
 *   npm run demo -- --port 5180       # app port (default 5173, preview 4173)
 *   npm run demo -- --no-batch        # never offer "점검 시작" for scenarios without a cache (real API)
 *   npm run demo -- --help
 *
 * It never starts or stops the real API (see planner/README.md, "Real Route-Check API") and never
 * computes anything itself. With no API at all, the app still shows the precomputed cache.
 * It exits (non-zero) when the app server stops by itself, e.g. when the port is busy.
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const PLANNER = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const USAGE = `Usage: npm run demo -- [options]

  --mode mock|real   which Route-Check API (default VITE_WFG_API_MODE or mock)
                     mock: starts the MOCK server on :8765 if needed (recorded results only)
                     real: VITE_WFG_API_TARGET (default http://127.0.0.1:8765); never started here
  --preview          production build + vite preview (same proxy and /cache)
  --open             open the browser once the app answers
  --port <n>         app port (default 5173, preview 4173)
  --no-batch         never offer "점검 시작" for scenarios without a precomputed cache (real API)
  -h, --help         this text

The cache folder served at /cache/** is planner/cache (the booth cache) unless WFG_CACHE_DIR says
otherwise (e.g. WFG_CACHE_DIR=.test-cache for test data). Real API: planner/README.md "Real Route-Check API".`;

const args = process.argv.slice(2);
const KNOWN_FLAGS = new Set(['--preview', '--open', '--no-batch', '--help', '-h']);
const KNOWN_OPTS = new Set(['--mode', '--port']);
if (args.includes('--help') || args.includes('-h')) {
  console.log(USAGE);
  process.exit(0);
}
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (KNOWN_OPTS.has(a)) {
    if (!args[i + 1] || args[i + 1].startsWith('--')) {
      console.error(`[demo] ${a} needs a value\n\n${USAGE}`);
      process.exit(2);
    }
    i++;
  } else if (!KNOWN_FLAGS.has(a)) {
    console.error(`[demo] unknown option ${a}\n\n${USAGE}`);
    process.exit(2);
  }
}
const flag = (name) => args.includes(`--${name}`);
const opt = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : dflt;
};

function readDotEnv() {
  const out = {};
  const p = join(PLANNER, '.env');
  if (!existsSync(p)) return out;
  for (const line of readFileSync(p, 'utf8').split(/\r?\n/)) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m && !line.trim().startsWith('#')) out[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
  }
  return out;
}

const dotenv = readDotEnv();
const mode = (opt('mode', process.env.VITE_WFG_API_MODE ?? dotenv.VITE_WFG_API_MODE ?? 'mock') === 'real' ? 'real' : 'mock');
const target = (mode === 'mock' ? 'http://127.0.0.1:8765' : process.env.VITE_WFG_API_TARGET ?? dotenv.VITE_WFG_API_TARGET ?? 'http://127.0.0.1:8765').replace(/\/+$/, '');
const port = opt('port', flag('preview') ? '4173' : '5173');
const cacheSetting = process.env.WFG_CACHE_DIR ?? dotenv.WFG_CACHE_DIR ?? 'cache';
const cacheDir = isAbsolute(cacheSetting) ? cacheSetting : resolve(PLANNER, cacheSetting);
const boothCache = resolve(PLANNER, 'cache');
const children = [];
const started = new Map(); // child → name
let shuttingDown = false;
let openTimer = null;

const log = (m) => console.log(`[demo] ${m}`);

async function health(base) {
  try {
    const r = await fetch(`${base}/v1/health`, { signal: AbortSignal.timeout(3000) });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

function stopAll() {
  shuttingDown = true;
  if (openTimer) clearTimeout(openTimer);
  for (const c of children) if (c.exitCode === null && !c.killed) c.kill('SIGTERM');
}

/** Spawns a child; a server child that exits by itself ends the launcher (and the others). */
function run(name, cmd, cmdArgs, env = {}, { server = true } = {}) {
  const child = spawn(cmd, cmdArgs, { cwd: PLANNER, stdio: 'inherit', env: { ...process.env, ...env } });
  children.push(child);
  started.set(child, name);
  if (server) {
    child.on('exit', (code, signal) => {
      if (shuttingDown) return;
      log(`${name} exited (${signal ? `signal ${signal}` : `code ${code}`}); stopping.`);
      stopAll();
      process.exit(code || 1);
    });
  }
  return child;
}

process.on('SIGINT', () => {
  stopAll();
  process.exit(130);
});
process.on('SIGTERM', () => {
  stopAll();
  process.exit(143);
});

let h = await health(target);
if (mode === 'mock') {
  if (h && !(h.mode === 'mock' || h.mock === true)) {
    log(`port 8765 answers but it is NOT the mock (api ${h.api_version}); stop it or use --mode real.`);
    process.exit(1);
  }
  if (!h) {
    log('starting the MOCK server (recorded results only): python3 mock_api/server.py --quiet');
    run('MOCK server', 'python3', ['mock_api/server.py', '--quiet']);
    for (let i = 0; i < 30 && !h; i++) {
      await new Promise((r) => setTimeout(r, 300));
      h = await health(target);
    }
    if (!h) log('the MOCK server did not answer; the app will fall back to the precomputed cache.');
  }
} else if (!h) {
  log(`no Route-Check API at ${target}; the app will use the precomputed cache (offline). Start the real Route-Check API: planner/README.md, "Real Route-Check API".`);
} else if (h.mode === 'mock' || h.mock === true) {
  log(`WARNING ${target} is the MOCK server, although --mode real was asked; the app will show the MOCK badge.`);
}
if (h) log(`API ${target}/v1 · ${h.mode === 'mock' || h.mock === true ? 'MOCK' : 'real'} · api_version ${h.api_version} · workers ${h.workers}`);

// the cache folder that /cache/** will serve (and a build would copy)
const rel = relative(PLANNER, cacheDir) || '.';
if (resolve(cacheDir) !== boothCache) log(`TEST CACHE served at /cache: planner/${rel} (WFG_CACHE_DIR) — test data, not the booth cache.`);
else log('cache served at /cache: planner/cache (booth cache)');
if (!existsSync(join(cacheDir, 'INDEX.json'))) log(`no ${rel === '.' ? '' : `planner/${rel}/`}INDEX.json: results are computed through the API when a scenario is opened.`);
if (flag('no-batch')) log('--no-batch: scenarios without a precomputed cache never offer "점검 시작" against the real API.');

const env = { VITE_WFG_API_MODE: mode, VITE_WFG_API_TARGET: target, ...(flag('no-batch') ? { VITE_WFG_ALLOW_BATCH: '0' } : {}) };
const vite = join(PLANNER, 'node_modules', '.bin', 'vite');
if (flag('preview')) {
  const build = run('vite build', vite, ['build'], env, { server: false });
  await new Promise((r) =>
    build.on('exit', (code) => {
      if (code === 0) return r();
      log('build failed');
      stopAll();
      process.exit(code ?? 1);
    }),
  );
  run('vite preview', vite, ['preview', '--port', port, '--strictPort'], env);
} else {
  run('vite', vite, ['--port', port, '--strictPort'], env);
}
const url = `http://127.0.0.1:${port}/`;
log(`app ${url} (starting…)`);
if (flag('open')) {
  // open only once the app itself answers (never a stale server on that port after vite exited)
  const tryOpen = async (n) => {
    openTimer = null;
    if (shuttingDown) return;
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (r.ok && !shuttingDown) {
        const opener = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
        spawn(opener, [url], { stdio: 'ignore', detached: true }).unref();
        log(`opened ${url}`);
        return;
      }
    } catch {
      /* not up yet */
    }
    if (n > 0 && !shuttingDown) openTimer = setTimeout(() => void tryOpen(n - 1), 1000);
  };
  openTimer = setTimeout(() => void tryOpen(30), 1500);
}
