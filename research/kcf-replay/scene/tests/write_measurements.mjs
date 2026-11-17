// Writes research/kcf-replay/scene/MEASUREMENTS.md from a smoke.mjs results.json plus the shipped file sizes.
//   node research/kcf-replay/scene/tests/write_measurements.mjs <results.json>
import { readFileSync, writeFileSync, statSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { execFileSync } from 'node:child_process';
import os from 'node:os';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../../..');
const scene = join(root, 'planner/public/kcf-scene');
const res = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const files = ['index.html', 'app.js', 'style.css', 'vendor/maplibre-gl.js', 'vendor/maplibre-gl.css', 'data/scene.js', 'data/terrain.js', 'data/basemap.js', 'data/fonts.js'];
const MB = (b) => (b / 1e6).toFixed(2);
let raw = 0, gz = 0;
const rows = files.map((f) => { const b = readFileSync(join(scene, f)); const g = gzipSync(b, { level: 9 }).length; raw += b.length; gz += g; return `| \`${f}\` | ${MB(b.length)} | ${MB(g)} |`; });
const s = (ms) => (ms / 1000).toFixed(1);
const commit = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: root }).toString().trim();
const cpu = os.cpus()[0]?.model || 'unknown CPU';
const runs = res.runs.map((r) => {
  const t = r.timings || {};
  const inter = r.interaction ? ` · next issue hour → idle ${s(r.interaction.issue_step_to_idle_ms)} s, select place ${r.interaction.select_place_sync_ms} ms` : '';
  return `| ${r.label} | ${t.lite ? 'lite (auto)' : 'full'} | ${s(t.scripts_parsed_ms)} | ${s(t.map_load_ms)} | ${s(t.ready_ms)} |${inter ? ' ' + inter.slice(3) : ''} |`;
});
const rw = res.checks.rewalk_all || {};
const md = `# KCF 3D scene: load time and checks (measured)

Measured ${res.started_utc.slice(0, 16).replace('T', ' ')} UTC at commit \`${commit}\` by \`research/kcf-replay/scene/tests/smoke.mjs\`
(headless Chromium, Playwright, viewport 1600 × 900, device pixel ratio 1) on a cloud container with ${os.cpus().length} vCPU
(${cpu}) and **no GPU**. WebGL there runs in software (${(res.runs[0]?.timings?.renderer || '').replace(/\|/g, '/')}).
The scene detects a software renderer and switches to lite mode on its own; \`?full\` forces full quality.

**Read these numbers as an upper bound.** Here the GPU's work (drawing terrain, hillshade and the draped layers) runs on the
CPU in software; scripts parse in well under a second and selecting a place takes milliseconds of JavaScript (table), so the
rest of the time is drawing. A 2020 laptop with any integrated GPU does that drawing in hardware. No such laptop was available
to measure here, so no laptop figure is claimed: time a cold load once on the presentation laptop before the talk.

## Cold load (ready = first fully drawn frame with data, fonts and labels)

| run | mode | scripts parsed (s) | map load (s) | ready (s) | interaction |
|---|---|---|---|---|---|
${runs.join('\n')}

"http" = served like GitHub Pages (\`/wildfireguardian/kcf-scene/\`) by a local server; "file://" = the folder opened from disk.
CPU ×${res.runs.find((r) => r.throttle)?.throttle || 4} = Chrome DevTools CPU throttling; 20 Mbit/s = DevTools network emulation (40 ms latency).

## Payload

| file | raw MB | gzip MB |
|---|---|---|
${rows.join('\n')}
| **total** | **${MB(raw)}** | **${MB(gz)}** |

GitHub Pages serves gzip, so a first visit transfers about ${MB(gz)} MB (about ${Math.round(gz * 8 / 20e6)} s at 20 Mbit/s,
${Math.round(gz * 8 / 5e6)} s at 5 Mbit/s); a second visit comes from the browser cache. Offline (file://) nothing is downloaded.
Terrain dominates: base64 PNG tiles barely compress.

## Checks in the same run

* Labels: the test-data badge and "reconstruction from the 2025 record" visible in ${(res.checks.views || []).filter((v) => v.labels.test && v.labels.recon).length} of ${(res.checks.views || []).length} views checked (region, place, check it, one minute later, drive, horizon-capped rows).
* Numbers without a source tag in the panels: ${(res.checks.views || []).reduce((n, v) => n + v.unsourced.length, 0)}.
* Witness re-walk by the page's own code against every committed arrival second: ${Object.entries(rw).map(([k, v]) => `${k} ${v.same_arrival}/${v.routes}`).join(', ')} identical; departing 60 s later fails on the same road in ${Object.values(rw).reduce((n, v) => n + v.later_fail, 0)} of ${Object.values(rw).reduce((n, v) => n + v.routes, 0)}.
* Sources panel paths that are not files in the repository: ${(res.checks.source_paths || []).filter((p) => !p.exists).length} (of ${(res.checks.source_paths || []).length} checked).
* Page errors and requests leaving the page: ${(res.checks.http_errors || []).length + (res.checks.file_url?.errors || []).length}.
`;
writeFileSync(join(root, 'research/kcf-replay/scene/MEASUREMENTS.md'), md);
console.log(md);
