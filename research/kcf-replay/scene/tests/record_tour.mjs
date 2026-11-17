// Records the 90-second fallback video of the three levels, frame by frame, from the scene's own deterministic tour
// (?tour=1, window.KCF_APP.tour.seek(t)). Frame-by-frame capture makes the video smooth even where the browser renders
// slowly (headless Chromium draws WebGL in software here).
//
//   node research/kcf-replay/scene/tests/record_tour.mjs [--out planner/public/kcf-scene/kcf_scene_tour_90s.mp4] [--fps 24] [--size 1920x1080] [--query full]
// Long captures can run in segments: --frames DIR --from N --to M --no-encode, then a last run with --encode-only.
// Smoothing in the drive camera depends on the previous frame, so each segment first replays the 2 s before --from.
import { createServer } from 'node:http';
import { readFileSync, existsSync, mkdirSync, statSync, rmSync } from 'node:fs';
import { join, resolve, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../../..');
const pub = join(root, 'planner/public');
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const OUT = resolve(opt('--out', join(root, 'planner/public/kcf-scene/kcf_scene_tour_90s.mp4'))); // ships with the scene folder
const FPS = Number(opt('--fps', '24'));
const [W, H] = opt('--size', '1920x1080').split('x').map(Number);
const FRAMES = resolve(opt('--frames', join(process.env.TMPDIR || tmpdir(), 'kcf_tour_frames')));
const EXTRA = opt('--query', '');
const FROM = Number(opt('--from', '0')), TO = opt('--to', null);
const NO_ENCODE = args.includes('--no-encode'), ENCODE_ONLY = args.includes('--encode-only');
function encode() {
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', join(FRAMES, 'f%05d.jpg'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', OUT]);
  console.log('wrote', OUT, statSync(OUT).size, 'bytes at', FPS, 'fps');
}
if (ENCODE_ONLY) { encode(); process.exit(0); }
if (!FROM) rmSync(FRAMES, { recursive: true, force: true });
mkdirSync(FRAMES, { recursive: true }); mkdirSync(dirname(OUT), { recursive: true });

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css' };
const srv = await new Promise((res) => {
  const s = createServer((req, rsp) => {
    let u = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/wildfireguardian\//, '/');
    let p = join(pub, u);
    if (existsSync(p) && statSync(p).isDirectory()) p = join(p, 'index.html');
    if (!p.startsWith(pub) || !existsSync(p)) { rsp.writeHead(404); return rsp.end(); }
    rsp.writeHead(200, { 'content-type': TYPES[extname(p)] || 'application/octet-stream' }); rsp.end(readFileSync(p));
  });
  s.listen(0, '127.0.0.1', () => res(s));
});
const browser = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('pageerror', e.message));
await page.goto(`http://127.0.0.1:${srv.address().port}/wildfireguardian/kcf-scene/?tour=1${EXTRA ? '&' + EXTRA : ''}`, { timeout: 300000 });
await page.evaluate(() => window.KCF_APP.ready);
const dur = await page.evaluate(() => window.KCF_APP.tour.duration);
const n = Math.round(dur * FPS);
const last = TO == null ? n : Math.min(n, Number(TO));
const t0 = Date.now();
for (let i = Math.max(0, FROM - 2 * FPS); i < FROM; i++) await page.evaluate((t) => window.KCF_APP.tour.seek(t), i / FPS); // warm-up
for (let i = FROM; i < last; i++) {
  await page.evaluate((t) => window.KCF_APP.tour.seek(t), i / FPS);
  await page.screenshot({ path: join(FRAMES, `f${String(i).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 92 });
  if (i % (FPS * 5) === 0) console.log(`frame ${i}/${n} (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
}
await browser.close(); srv.close();
console.log('frames', FROM, '..', last - 1, 'of', n, 'in', ((Date.now() - t0) / 1000).toFixed(0), 's');
if (!NO_ENCODE && last >= n) encode();
