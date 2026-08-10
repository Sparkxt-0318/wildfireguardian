// Generates public/icons/icon-512.png — a flame+shield placeholder glyph —
// with zero dependencies (no canvas): rasterizes simple shapes into RGBA and
// encodes a PNG by hand (zlib from node:zlib).
//
// Usage: node scripts/make-icons.mjs
import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SIZE = 512;
const here = dirname(fileURLToPath(import.meta.url));
const outPath = join(here, "..", "public", "icons", "icon-512.png");

// ---- tiny geometry helpers -------------------------------------------------
function inRoundedRect(x, y, w, h, r) {
  if (x < 0 || y < 0 || x >= w || y >= h) return false;
  const cx = Math.min(Math.max(x, r), w - r);
  const cy = Math.min(Math.max(y, r), h - r);
  const dx = x - cx;
  const dy = y - cy;
  return dx * dx + dy * dy <= r * r || (x >= r && x <= w - r) || (y >= r && y <= h - r);
}

// point-in-polygon (ray casting)
function inPoly(x, y, pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i];
    const [xj, yj] = pts[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

// shield outline as a polygon (matches public/icons/icon.svg proportions)
function shieldPoly(cx, top, halfW, bodyBottom, tipY) {
  const pts = [];
  pts.push([cx, top]);
  pts.push([cx + halfW, top + (bodyBottom - top) * 0.18]);
  pts.push([cx + halfW, bodyBottom]);
  // right curve toward the tip
  for (let t = 0; t <= 1; t += 0.05) {
    const x = cx + halfW * Math.cos((t * Math.PI) / 2);
    const y = bodyBottom + (tipY - bodyBottom) * Math.sin((t * Math.PI) / 2);
    pts.push([x, y]);
  }
  for (let t = 1; t >= 0; t -= 0.05) {
    const x = cx - halfW * Math.cos((t * Math.PI) / 2);
    const y = bodyBottom + (tipY - bodyBottom) * Math.sin((t * Math.PI) / 2);
    pts.push([x, y]);
  }
  pts.push([cx - halfW, bodyBottom]);
  pts.push([cx - halfW, top + (bodyBottom - top) * 0.18]);
  return pts;
}

// teardrop flame: circle bottom + curved point top
function inFlame(x, y, cx, cy, r, tipY) {
  const dx = x - cx;
  const dy = y - cy;
  if (dx * dx + dy * dy <= r * r && y >= cy - r * 0.2) return true;
  // upper teardrop: width shrinks toward the tip
  if (y < cy - r * 0.2 && y >= tipY) {
    const t = (cy - r * 0.2 - y) / (cy - r * 0.2 - tipY); // 0 at widest, 1 at tip
    const w = r * (1 - t) * (1 - t * 0.3);
    // lean the tip slightly right, like the SVG glyph
    const lean = r * 0.25 * t;
    return Math.abs(dx - lean) <= w;
  }
  return false;
}

// ---- palette (matches theme/tokens.css + icon.svg) -------------------------
const GREEN = [0x1b, 0x7f, 0x4b, 255];
const WHITE = [255, 255, 255, 255];
const ORANGE = [0xff, 0x8a, 0x3d, 255];
const YELLOW = [0xff, 0xd1, 0x66, 255];
const CLEAR = [0, 0, 0, 0];

// ---- rasterize (2x supersampling for smooth edges) -------------------------
const SS = 2;
const N = SIZE * SS;
const outer = shieldPoly(N / 2, 84 * SS, 156 * SS, 268 * SS, 444 * SS);
const inner = shieldPoly(N / 2, 116 * SS, 128 * SS, 266 * SS, 412 * SS);

function samplePixel(x, y) {
  if (!inRoundedRect(x, y, N, N, 112 * SS)) return CLEAR;
  let c = GREEN;
  if (inPoly(x, y, outer)) c = WHITE;
  if (inPoly(x, y, inner)) c = GREEN;
  if (inFlame(x, y, N / 2, 292 * SS, 62 * SS, 168 * SS)) c = ORANGE;
  if (inFlame(x, y, N / 2, 300 * SS, 32 * SS, 236 * SS)) c = YELLOW;
  return c;
}

const rgba = Buffer.alloc(SIZE * SIZE * 4);
for (let py = 0; py < SIZE; py++) {
  for (let px = 0; px < SIZE; px++) {
    let r = 0,
      g = 0,
      b = 0,
      a = 0;
    for (let sy = 0; sy < SS; sy++) {
      for (let sx = 0; sx < SS; sx++) {
        const c = samplePixel(px * SS + sx, py * SS + sy);
        r += c[0];
        g += c[1];
        b += c[2];
        a += c[3];
      }
    }
    const n = SS * SS;
    const i = (py * SIZE + px) * 4;
    rgba[i] = Math.round(r / n);
    rgba[i + 1] = Math.round(g / n);
    rgba[i + 2] = Math.round(b / n);
    rgba[i + 3] = Math.round(a / n);
  }
}

// ---- PNG encoding ----------------------------------------------------------
const CRC_TABLE = new Int32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(SIZE, 0);
ihdr.writeUInt32BE(SIZE, 4);
ihdr[8] = 8; // bit depth
ihdr[9] = 6; // color type RGBA
// compression 0, filter 0, interlace 0

// raw scanlines, filter byte 0 per row
const raw = Buffer.alloc(SIZE * (SIZE * 4 + 1));
for (let y = 0; y < SIZE; y++) {
  raw[y * (SIZE * 4 + 1)] = 0;
  rgba.copy(raw, y * (SIZE * 4 + 1) + 1, y * SIZE * 4, (y + 1) * SIZE * 4);
}

const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk("IHDR", ihdr),
  chunk("IDAT", deflateSync(raw, { level: 9 })),
  chunk("IEND", Buffer.alloc(0)),
]);

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, png);
console.log(`wrote ${outPath} (${png.length} bytes)`);
