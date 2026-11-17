#!/usr/bin/env node
/**
 * Writes the six-place timeline of a replay pack for the planner's replay panel:
 *
 *   planner/public/data/replay/<pack>.named_places.json
 *
 * from the committed replay output research/kcf-replay/per_place.csv (rows of the six named places of
 * RESULTS.md section 4, one stand-in and horizon, every issue hour) and the reported times in
 * scripts/kcf_reported_times.json (copied from research/kcf-replay/SOURCES.md). The latest safe
 * departure is the F-3.1 field's value to the minute, exactly as in the CSV; nothing is recomputed.
 * The input CSV's SHA-256 is recorded, and tests/planner/replay.test.ts re-derives the file.
 *
 * Usage (from planner/):
 *   node scripts/build_replay_named_places.mjs [--standin RUNNING] [--horizon 8h] [--check]
 * --check: exit 1 when the committed file differs from what this script would write.
 */
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const planner = resolve(here, '..');
const repo = resolve(planner, '..');

export const NAMED = ['화매리', '지품리', '옥류리', '매정리', '노물리', '강구리'];
export const REGION = 'yeongdeok_2025';

/** Minimal RFC 4180 reader (quoted fields, doubled quotes). */
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let f = '';
  let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') {
        f += '"';
        i++;
      } else if (c === '"') q = false;
      else f += c;
    } else if (c === '"') q = true;
    else if (c === ',') {
      row.push(f);
      f = '';
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(f);
      rows.push(row);
      row = [];
      f = '';
    } else f += c;
  }
  if (f !== '' || row.length) {
    row.push(f);
    rows.push(row);
  }
  const [head, ...body] = rows.filter((r) => r.length > 1 || r[0] !== '');
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ''])));
}

/** "03-25 18:47" (KST, 2025) → "2025-03-25T09:47:00Z"; "" → null. */
export function kstToUtc(s) {
  const m = /^(\d\d)-(\d\d) (\d\d):(\d\d)$/.exec(String(s ?? '').trim());
  if (!m) return null;
  const t = Date.UTC(2025, Number(m[1]) - 1, Number(m[2]), Number(m[3]) - 9, Number(m[4]));
  return new Date(t).toISOString().replace('.000Z', 'Z');
}

export function buildNamedPlaces({ csvText, csvSha256, reported, standin, horizon, pack }) {
  const rows = parseCsv(csvText).filter((r) => r.region === REGION && NAMED.includes(r.name) && r.standin === standin && r.horizon === horizon);
  const issues = [...new Set(rows.map((r) => kstToUtc(r.issue_kst)))].sort();
  const places = NAMED.map((name) => {
    const mine = rows.filter((r) => r.name === name);
    if (!mine.length) throw new Error(`${name}: no rows for ${standin} ${horizon}`);
    const ids = [...new Set(mine.map((r) => r.place_id))];
    if (ids.length !== 1) throw new Error(`${name}: ${ids.length} place ids`);
    const rep = reported.places[name] ?? { items: [] };
    return {
      place_id: ids[0],
      name,
      sigungu: mine[0].sigungu || null,
      hours: issues.map((iu) => {
        const r = mine.find((x) => kstToUtc(x.issue_kst) === iu);
        if (!r) return { issue_utc: iu, state: 'MISSING', step: null, latest_safe_departure_utc: null, shelter_name: null, route_cut_before_departure: null };
        const ld = r.departure_state === 'LATEST_SAFE_DEPARTURE' ? kstToUtc(r.latest_safe_departure_kst) : null;
        return {
          issue_utc: iu,
          // LATEST_SAFE_DEPARTURE | INSIDE_KNOWN_FIRE_AREA | NOT_CUT_WITHIN_H | NO_DEPARTURE ...
          state: r.departure_state,
          step: r.government_step || null,
          latest_safe_departure_utc: ld,
          shelter_name: r.shelter_name || null,
          route_cut_before_departure: r.route_cut_before_departure === 'yes' ? true : r.route_cut_before_departure === 'no' ? false : null,
        };
      }),
      reported: rep.items.map((it) => ({ ...it, utc: kstToUtc(it.kst), source: { id: it.source, ...reported.sources[it.source] } })),
      reported_note_ko: rep.note_ko ?? null,
      reported_note_en: rep.note_en ?? null,
    };
  });
  return {
    schema: 'wfg.replay.named_places/1',
    pack,
    standin,
    horizon,
    region_id: REGION,
    issue_hours_utc: issues,
    source: { csv: 'research/kcf-replay/per_place.csv', csv_sha256: csvSha256, reported: 'planner/scripts/kcf_reported_times.json (from research/kcf-replay/SOURCES.md)', results: 'research/kcf-replay/RESULTS.md §4' },
    note: 'latest_safe_departure_utc: the F-3.1 deadline field to the minute (per_place.csv), not the 30-minute departure grid the map uses. Reported times are documented times from single outlets, never outcomes of the replay.',
    places,
  };
}

function main() {
  const args = process.argv.slice(2);
  const opt = (k, d) => {
    const i = args.indexOf(k);
    return i >= 0 ? args[i + 1] : d;
  };
  const standin = opt('--standin', 'RUNNING');
  const horizon = opt('--horizon', '8h');
  const pack = opt('--pack', `kcf-replay-${standin}_${horizon}`);
  const csvPath = join(repo, 'research/kcf-replay/per_place.csv');
  const buf = readFileSync(csvPath);
  const doc = buildNamedPlaces({
    csvText: buf.toString('utf8'),
    csvSha256: createHash('sha256').update(buf).digest('hex'),
    reported: JSON.parse(readFileSync(join(here, 'kcf_reported_times.json'), 'utf8')),
    standin,
    horizon,
    pack,
  });
  const out = join(planner, 'public/data/replay', `${pack}.named_places.json`);
  const text = `${JSON.stringify(doc, null, 1)}\n`;
  if (args.includes('--check')) {
    const same = existsSync(out) && readFileSync(out, 'utf8') === text;
    console.log(same ? `[replay] ${out} is up to date` : `[replay] ${out} differs from ${csvPath}`);
    process.exit(same ? 0 : 1);
  }
  writeFileSync(out, text);
  console.log(`[replay] wrote ${out}: ${doc.places.length} places × ${doc.issue_hours_utc.length} issue hours`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
