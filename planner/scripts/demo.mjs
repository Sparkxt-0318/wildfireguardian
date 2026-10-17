#!/usr/bin/env node
/**
 * Booth launcher for the WildfireGuardian 사전 대피계획 도구.
 *
 *   npm run demo                      # mock mode: starts the MOCK server if needed + the app
 *   npm run demo -- --mode real       # real Route-Check API at VITE_WFG_API_TARGET (default :8765)
 *   npm run demo -- --preview         # production build + `vite preview` (same proxy and /cache)
 *   npm run demo -- --open            # also open the browser
 *
 * It never starts or stops the real API (run `make api` in the repository root for that) and
 * never computes anything itself. With no API at all, the app still shows the precomputed cache.
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const PLANNER = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
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
const children = [];

async function health(base) {
  try {
    const r = await fetch(`${base}/v1/health`, { signal: AbortSignal.timeout(3000) });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

function run(cmd, cmdArgs, env = {}) {
  const child = spawn(cmd, cmdArgs, { cwd: PLANNER, stdio: 'inherit', env: { ...process.env, ...env } });
  children.push(child);
  return child;
}

function stopAll() {
  for (const c of children) if (!c.killed) c.kill('SIGTERM');
}
process.on('SIGINT', () => {
  stopAll();
  process.exit(130);
});
process.on('SIGTERM', () => {
  stopAll();
  process.exit(143);
});

const log = (m) => console.log(`[demo] ${m}`);

let h = await health(target);
if (mode === 'mock') {
  if (h && !(h.mode === 'mock' || h.mock === true)) {
    log(`port 8765 answers but it is NOT the mock (api ${h.api_version}); stop it or use --mode real.`);
    process.exit(1);
  }
  if (!h) {
    log('starting the MOCK server (recorded results only): python3 mock_api/server.py --quiet');
    run('python3', ['mock_api/server.py', '--quiet']);
    for (let i = 0; i < 30 && !h; i++) {
      await new Promise((r) => setTimeout(r, 300));
      h = await health(target);
    }
    if (!h) log('the MOCK server did not answer; the app will fall back to the precomputed cache.');
  }
} else if (!h) {
  log(`no Route-Check API at ${target}; the app will use the precomputed cache (offline). Start it with \`make api\`.`);
} else if (h.mode === 'mock' || h.mock === true) {
  log(`WARNING ${target} is the MOCK server, although --mode real was asked; the app will show the MOCK badge.`);
}
if (h) log(`API ${target}/v1 · ${h.mode === 'mock' || h.mock === true ? 'MOCK' : 'real'} · api_version ${h.api_version} · workers ${h.workers}`);
if (!existsSync(join(PLANNER, 'cache', 'INDEX.json'))) log('no planner/cache/INDEX.json: results are computed through the API when a scenario is opened.');

const env = { VITE_WFG_API_MODE: mode, VITE_WFG_API_TARGET: target };
const vite = join(PLANNER, 'node_modules', '.bin', 'vite');
if (flag('preview')) {
  const build = run(vite, ['build'], env);
  await new Promise((r) => build.on('exit', (code) => (code === 0 ? r() : (log('build failed'), stopAll(), process.exit(code ?? 1)))));
  run(vite, ['preview', '--port', port, '--strictPort'], env);
} else {
  run(vite, ['--port', port, '--strictPort'], env);
}
const url = `http://127.0.0.1:${port}/`;
log(`open ${url}`);
if (flag('open')) {
  setTimeout(() => {
    const opener = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
    spawn(opener, [url], { stdio: 'ignore', detached: true }).unref();
  }, 1500);
}
