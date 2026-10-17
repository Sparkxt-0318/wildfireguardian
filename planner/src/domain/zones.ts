/**
 * User-drawn spread zones (사용자 입력 확산 구역, 가정) — pure geometry and request helpers.
 * Unit-tested in tests/planner/zones.test.ts.
 *
 * Model: two zones, 5 h and 8 h (산림청식 화선 도달 범위). Each zone is a list of polygons; a polygon
 * is [outer ring, ...holes]; a ring is an OPEN list of [lon, lat] vertices (the first vertex is not
 * repeated at the end). Zones go to the Route-Check API as fire_input {type: "spread_zones"} with a
 * ZoneCollection (contract v1.5: Polygon | MultiPolygon, properties.arrival_h_max).
 *
 * Honesty: nothing here invents, buffers or scales a polygon. Presets copy a RECORDED burned
 * footprint and only reduce its vertex count (Douglas–Peucker); the user edits from there.
 * Ready-Set-Go tagging is planner-side point-in-polygon only (ARCHITECTURE.md §6).
 */
import type { Feature, FeatureCollection, MultiPolygon, Polygon, Position } from 'geojson';
import { parseUtc } from './clock';
import { compareUrgency, type UrgencyItem } from './plan';

export type LonLat = [number, number];
/** Open ring: first vertex not repeated at the end. */
export type Ring = LonLat[];
/** [outer, ...holes] */
export type ZonePolygon = Ring[];
export type ZoneKey = 'h5' | 'h8';

export const ZONE_KEYS: readonly ZoneKey[] = ['h5', 'h8'];
/** arrival_h_max of each zone (contract ZoneFeature.properties.arrival_h_max) */
export const ZONE_HOURS: Record<ZoneKey, number> = { h5: 5, h8: 8 };
/** Douglas–Peucker tolerance for footprint presets (m). */
export const PRESET_TOLERANCE_M = 50;
/** "구역 안·주변 마을": origins inside a zone or within this distance of one (m). */
export const NEAR_ZONE_M = 2000;
export const DEFAULT_MARGIN_MIN = 60;
export const MAX_ISSUE_OFFSET_H = 8;
export const MAX_MARGIN_MIN = 120;

/** Where a zone's geometry came from. A preset is a copy of a recorded burned footprint (real data). */
export interface ZonePreset {
  kind: 'footprint';
  /** recorded input time of the copied footprint (UTC ISO) */
  inputTime: string;
  verticesBefore: number;
  verticesAfter: number;
  toleranceM: number;
}

export interface DrawnZone {
  key: ZoneKey;
  arrivalHMax: number;
  polygons: ZonePolygon[];
  preset: ZonePreset | null;
  /** edited by the user after the preset was copied */
  edited: boolean;
}

export type DrawnZones = Record<ZoneKey, DrawnZone>;

export interface VertexRef {
  zone: ZoneKey;
  poly: number;
  ring: number;
  index: number;
}

export function emptyZone(key: ZoneKey): DrawnZone {
  return { key, arrivalHMax: ZONE_HOURS[key], polygons: [], preset: null, edited: false };
}

export function emptyZones(): DrawnZones {
  return { h5: emptyZone('h5'), h8: emptyZone('h8') };
}

export function hasAnyZone(z: DrawnZones): boolean {
  return ZONE_KEYS.some((k) => z[k].polygons.length > 0);
}

// ---------------------------------------------------------------- local metric projection

const EARTH_R = 6371008.8;
const DEG = Math.PI / 180;

export interface LocalProjection {
  toXY: (p: LonLat) => [number, number];
  toLonLat: (xy: [number, number]) => LonLat;
}

/** Equirectangular projection around (lon0, lat0) in metres — accurate to < 0.5 % within ~50 km. */
export function localProjection(lon0: number, lat0: number): LocalProjection {
  const kx = EARTH_R * Math.cos(lat0 * DEG) * DEG;
  const ky = EARTH_R * DEG;
  return {
    toXY: (p) => [(p[0] - lon0) * kx, (p[1] - lat0) * ky],
    toLonLat: (xy) => [xy[0] / kx + lon0, xy[1] / ky + lat0],
  };
}

function projectionFor(points: LonLat[]): LocalProjection {
  if (points.length === 0) return localProjection(0, 0);
  let sx = 0;
  let sy = 0;
  for (const p of points) {
    sx += p[0];
    sy += p[1];
  }
  return localProjection(sx / points.length, sy / points.length);
}

// ---------------------------------------------------------------- rings

const EPS = 1e-12;

function samePoint(a: LonLat, b: LonLat): boolean {
  return Math.abs(a[0] - b[0]) < 1e-10 && Math.abs(a[1] - b[1]) < 1e-10;
}

/** Drops the closing vertex and consecutive duplicates; keeps only finite [lon, lat]. */
export function openRing(coords: Position[] | LonLat[]): Ring {
  const out: Ring = [];
  for (const c of coords) {
    const lon = Number(c[0]);
    const lat = Number(c[1]);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    const p: LonLat = [lon, lat];
    if (out.length && samePoint(out[out.length - 1]!, p)) continue;
    out.push(p);
  }
  while (out.length > 1 && samePoint(out[0]!, out[out.length - 1]!)) out.pop();
  return out;
}

export function closeRing(ring: Ring): Position[] {
  if (ring.length === 0) return [];
  return [...ring.map((p) => [p[0], p[1]]), [ring[0]![0], ring[0]![1]]];
}

/** Polygon / MultiPolygon geometry → zone polygons (open rings). Empty rings are dropped. */
export function geometryToPolygons(g: Polygon | MultiPolygon | null | undefined): ZonePolygon[] {
  if (!g) return [];
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
  const out: ZonePolygon[] = [];
  for (const poly of polys) {
    const rings = poly.map((r) => openRing(r)).filter((r) => r.length > 0);
    if (rings.length) out.push(rings);
  }
  return out;
}

export function ringCount(zone: DrawnZone): number {
  return zone.polygons.reduce((n, p) => n + p.length, 0);
}

export function zoneVertexCount(zone: DrawnZone): number {
  return zone.polygons.reduce((n, p) => n + p.reduce((m, r) => m + r.length, 0), 0);
}

export function polygonsVertexCount(polys: ZonePolygon[]): number {
  return polys.reduce((n, p) => n + p.reduce((m, r) => m + r.length, 0), 0);
}

/** Signed area in the projection plane (m²); > 0 counter-clockwise. */
function signedAreaXY(xy: [number, number][]): number {
  let a = 0;
  for (let i = 0, n = xy.length; i < n; i += 1) {
    const p = xy[i]!;
    const q = xy[(i + 1) % n]!;
    a += p[0] * q[1] - q[0] * p[1];
  }
  return a / 2;
}

export function ringAreaM2(ring: Ring, proj: LocalProjection = projectionFor(ring)): number {
  if (ring.length < 3) return 0;
  return Math.abs(signedAreaXY(ring.map(proj.toXY)));
}

/** Counter-clockwise in lon/lat (x east, y north). */
export function ringIsCcw(ring: Ring): boolean {
  if (ring.length < 3) return true;
  let a = 0;
  for (let i = 0, n = ring.length; i < n; i += 1) {
    const p = ring[i]!;
    const q = ring[(i + 1) % n]!;
    a += p[0] * q[1] - q[0] * p[1];
  }
  return a > 0;
}

export function polygonAreaM2(poly: ZonePolygon): number {
  if (!poly.length) return 0;
  const proj = projectionFor(poly[0]!);
  const outer = ringAreaM2(poly[0]!, proj);
  const holes = poly.slice(1).reduce((n, r) => n + ringAreaM2(r, proj), 0);
  return Math.max(0, outer - holes);
}

export function zoneAreaKm2(zone: DrawnZone): number {
  return zone.polygons.reduce((n, p) => n + polygonAreaM2(p), 0) / 1e6;
}

// ---------------------------------------------------------------- segment intersection

function orient(a: LonLat, b: LonLat, c: LonLat): number {
  const v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  return Math.abs(v) < EPS ? 0 : v > 0 ? 1 : -1;
}

function onSegment(a: LonLat, b: LonLat, p: LonLat): boolean {
  return Math.min(a[0], b[0]) - EPS <= p[0] && p[0] <= Math.max(a[0], b[0]) + EPS && Math.min(a[1], b[1]) - EPS <= p[1] && p[1] <= Math.max(a[1], b[1]) + EPS;
}

/** True when the closed segments ab and cd share at least one point (proper crossing, touching or collinear overlap). */
export function segmentsIntersect(a: LonLat, b: LonLat, c: LonLat, d: LonLat): boolean {
  const o1 = orient(a, b, c);
  const o2 = orient(a, b, d);
  const o3 = orient(c, d, a);
  const o4 = orient(c, d, b);
  if (o1 !== o2 && o3 !== o4) return true;
  if (o1 === 0 && onSegment(a, b, c)) return true;
  if (o2 === 0 && onSegment(a, b, d)) return true;
  if (o3 === 0 && onSegment(c, d, a)) return true;
  if (o4 === 0 && onSegment(c, d, b)) return true;
  return false;
}

/**
 * How two closed segments meet: 'cross' = proper crossing of their interiors, 'overlap' = collinear
 * with a shared stretch of positive length, 'touch' = they share exactly one point (an endpoint
 * on the other segment), 'none'. A polygon is invalid when rings cross or overlap; rings that only
 * touch at a point (e.g. a hole touching its shell, as in dissolved cell footprints) are valid
 * (OGC simple features) and the API rasterises them.
 */
export function segmentRelation(a: LonLat, b: LonLat, c: LonLat, d: LonLat): 'none' | 'touch' | 'cross' | 'overlap' {
  const o1 = orient(a, b, c);
  const o2 = orient(a, b, d);
  const o3 = orient(c, d, a);
  const o4 = orient(c, d, b);
  if (o1 * o2 < 0 && o3 * o4 < 0) return 'cross';
  if (o1 === 0 && o2 === 0) {
    // collinear: overlap length along the dominant axis
    const ax = Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]) ? 0 : 1;
    const lo = Math.max(Math.min(a[ax], b[ax]), Math.min(c[ax], d[ax]));
    const hi = Math.min(Math.max(a[ax], b[ax]), Math.max(c[ax], d[ax]));
    if (hi - lo > 1e-12) return 'overlap';
    return hi - lo >= -1e-12 ? 'touch' : 'none';
  }
  if ((o1 === 0 && onSegment(a, b, c)) || (o2 === 0 && onSegment(a, b, d)) || (o3 === 0 && onSegment(c, d, a)) || (o4 === 0 && onSegment(c, d, b))) return 'touch';
  return 'none';
}

function crosses(a: LonLat, b: LonLat, c: LonLat, d: LonLat): boolean {
  const r = segmentRelation(a, b, c, d);
  return r === 'cross' || r === 'overlap';
}

/** Intersection point of two segments (approximate for collinear overlaps: a shared endpoint or midpoint). */
function intersectionPoint(a: LonLat, b: LonLat, c: LonLat, d: LonLat): LonLat {
  const den = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0]);
  if (Math.abs(den) < EPS) {
    for (const p of [c, d, a, b]) if (onSegment(a, b, p) && onSegment(c, d, p)) return p;
    return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  }
  const t = ((a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])) / den;
  return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])];
}

/**
 * Points where a ring crosses itself (non-adjacent edges crossing or overlapping; adjacent edges
 * folding back onto each other). Touching at a single point is not reported. Empty for a simple ring.
 */
export function ringSelfIntersections(ring: Ring, limit = 50): LonLat[] {
  const n = ring.length;
  const out: LonLat[] = [];
  if (n < 3) return out;
  for (let i = 0; i < n; i += 1) {
    const a = ring[i]!;
    const b = ring[(i + 1) % n]!;
    for (let j = i + 1; j < n; j += 1) {
      const c = ring[j]!;
      const d = ring[(j + 1) % n]!;
      const adjacent = j === i + 1 || (i === 0 && j === n - 1);
      if (adjacent) {
        // shared vertex: only a fold-back (collinear, pointing back) is a self-intersection
        const shared = j === i + 1 ? b : a;
        const p = j === i + 1 ? a : b;
        const q = j === i + 1 ? d : c;
        if (n > 3 && orient(p, shared, q) === 0) {
          const dot = (p[0] - shared[0]) * (q[0] - shared[0]) + (p[1] - shared[1]) * (q[1] - shared[1]);
          if (dot > 0) out.push(shared);
        }
        continue;
      }
      if (crosses(a, b, c, d)) {
        out.push(intersectionPoint(a, b, c, d));
        if (out.length >= limit) return out;
      }
    }
  }
  return out;
}

export function ringIsSimple(ring: Ring): boolean {
  return ring.length >= 3 && ringSelfIntersections(ring, 1).length === 0;
}

/** Points where two rings cross or overlap (touching at a single point is allowed). */
export function ringsIntersections(r1: Ring, r2: Ring, limit = 50): LonLat[] {
  const out: LonLat[] = [];
  for (let i = 0; i < r1.length; i += 1) {
    const a = r1[i]!;
    const b = r1[(i + 1) % r1.length]!;
    for (let j = 0; j < r2.length; j += 1) {
      const c = r2[j]!;
      const d = r2[(j + 1) % r2.length]!;
      if (crosses(a, b, c, d)) {
        out.push(intersectionPoint(a, b, c, d));
        if (out.length >= limit) return out;
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------- point in polygon (holes, multipolygons)

/** Even–odd ray casting; points exactly on an edge count as inside. */
export function pointInRing(p: LonLat, ring: Ring): boolean {
  const n = ring.length;
  if (n < 3) return false;
  let inside = false;
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const a = ring[i]!;
    const b = ring[j]!;
    if (orient(a, b, p) === 0 && onSegment(a, b, p)) return true;
    if (a[1] > p[1] !== b[1] > p[1]) {
      const x = ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0];
      if (p[0] < x) inside = !inside;
    }
  }
  return inside;
}

/** Inside the outer ring and not strictly inside any hole. */
export function pointInPolygon(p: LonLat, poly: ZonePolygon): boolean {
  if (!poly.length || !pointInRing(p, poly[0]!)) return false;
  for (const hole of poly.slice(1)) {
    if (pointInRing(p, hole) && !pointOnRing(p, hole)) return false;
  }
  return true;
}

function pointOnRing(p: LonLat, ring: Ring): boolean {
  for (let i = 0, n = ring.length; i < n; i += 1) {
    const a = ring[i]!;
    const b = ring[(i + 1) % n]!;
    if (orient(a, b, p) === 0 && onSegment(a, b, p)) return true;
  }
  return false;
}

export function pointInZone(p: LonLat, zone: DrawnZone): boolean {
  return zone.polygons.some((poly) => pointInPolygon(p, poly));
}

/** Shortest distance (m) from a point to the zone: 0 inside, else to the nearest edge. Infinity when empty. */
export function distanceToZoneM(p: LonLat, zone: DrawnZone): number {
  if (!zone.polygons.length) return Number.POSITIVE_INFINITY;
  if (pointInZone(p, zone)) return 0;
  const proj = localProjection(p[0], p[1]);
  let best = Number.POSITIVE_INFINITY;
  for (const poly of zone.polygons) {
    for (const ring of poly) {
      for (let i = 0, n = ring.length; i < n; i += 1) {
        const a = proj.toXY(ring[i]!);
        const b = proj.toXY(ring[(i + 1) % n]!);
        best = Math.min(best, pointSegmentDistance([0, 0], a, b));
      }
    }
  }
  return best;
}

function pointSegmentDistance(p: [number, number], a: [number, number], b: [number, number]): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2));
  return Math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1]);
}

// ---------------------------------------------------------------- Ready-Set-Go (산림청)

/** 'go' = inside the 5 h zone (실행: 전원 대피), 'set' = inside the 8 h zone only (준비: 노약자·취약시설 우선 대피). */
export type RsgTag = 'go' | 'set';

export function rsgTag(p: LonLat, zones: DrawnZones): RsgTag | null {
  if (pointInZone(p, zones.h5)) return 'go';
  if (pointInZone(p, zones.h8)) return 'set';
  return null;
}

export function rsgTags(points: { id: string; lon: number; lat: number }[], zones: DrawnZones): Map<string, RsgTag> {
  const out = new Map<string, RsgTag>();
  if (!hasAnyZone(zones)) return out;
  for (const p of points) {
    const tag = rsgTag([p.lon, p.lat], zones);
    if (tag) out.set(p.id, tag);
  }
  return out;
}

const RSG_RANK: Record<RsgTag | 'none', number> = { go: 0, set: 1, none: 2 };

export interface DrawnUrgencyItem extends UrgencyItem {
  rsg: RsgTag | null;
}

/** Drawn-zone list order: inside zones first (Go before Set), then the planner urgency order. */
export function compareDrawn(a: DrawnUrgencyItem, b: DrawnUrgencyItem): number {
  const ra = RSG_RANK[a.rsg ?? 'none'];
  const rb = RSG_RANK[b.rsg ?? 'none'];
  if (ra !== rb) return ra - rb;
  return compareUrgency(a, b);
}

export function sortDrawn<T extends DrawnUrgencyItem>(items: T[]): T[] {
  return [...items].sort(compareDrawn);
}

/** Origins inside any zone or within `nearM` of one ("구역 안·주변 마을"). */
export function originsNearZones<T extends { lon: number; lat: number }>(origins: T[], zones: DrawnZones, nearM = NEAR_ZONE_M): { inside: T[]; near: T[] } {
  const inside: T[] = [];
  const near: T[] = [];
  const active = ZONE_KEYS.map((k) => zones[k]).filter((z) => z.polygons.length > 0);
  if (!active.length) return { inside, near };
  for (const o of origins) {
    const p: LonLat = [o.lon, o.lat];
    const d = Math.min(...active.map((z) => distanceToZoneM(p, z)));
    if (d === 0) inside.push(o);
    else if (d <= nearM) near.push(o);
  }
  return { inside, near };
}

// ---------------------------------------------------------------- Douglas–Peucker

/**
 * Douglas–Peucker simplification of an OPEN polyline in metres (local projection). The first and
 * last points are always kept and every removed point lies within `tolM` of the kept polyline.
 */
export function douglasPeucker(points: LonLat[], tolM: number, proj: LocalProjection = projectionFor(points)): LonLat[] {
  if (points.length <= 2 || !(tolM > 0)) return points.slice();
  const xy = points.map(proj.toXY);
  const keep = new Uint8Array(points.length);
  keep[0] = 1;
  keep[points.length - 1] = 1;
  const stack: [number, number][] = [[0, points.length - 1]];
  while (stack.length) {
    const [lo, hi] = stack.pop()!;
    let best = -1;
    let bestD = -1;
    for (let i = lo + 1; i < hi; i += 1) {
      const d = pointSegmentDistance(xy[i]!, xy[lo]!, xy[hi]!);
      if (d > bestD) {
        bestD = d;
        best = i;
      }
    }
    if (best > 0 && bestD > tolM) {
      keep[best] = 1;
      stack.push([lo, best], [best, hi]);
    }
  }
  return points.filter((_, i) => keep[i] === 1);
}

/**
 * Closed-ring simplification: split at vertex 0 and the vertex farthest from it, simplify both halves.
 * Never returns fewer than 3 vertices (returns the input then).
 */
export function simplifyRing(ring: Ring, tolM: number): Ring {
  if (ring.length <= 4 || !(tolM > 0)) return ring.slice();
  const proj = projectionFor(ring);
  const xy = ring.map(proj.toXY);
  let far = 1;
  let farD = -1;
  for (let i = 1; i < ring.length; i += 1) {
    const d = Math.hypot(xy[i]![0] - xy[0]![0], xy[i]![1] - xy[0]![1]);
    if (d > farD) {
      farD = d;
      far = i;
    }
  }
  const first = douglasPeucker(ring.slice(0, far + 1), tolM, proj);
  const second = douglasPeucker([...ring.slice(far), ring[0]!], tolM, proj);
  const out = [...first, ...second.slice(1, -1)];
  return out.length >= 3 ? out : ring.slice();
}

/** Every ring of a polygon is simple and no two rings cross. */
export function polygonIsSimple(poly: ZonePolygon): boolean {
  if (!poly.every(ringIsSimple)) return false;
  for (let i = 0; i < poly.length; i += 1) {
    for (let j = i + 1; j < poly.length; j += 1) if (ringsIntersections(poly[i]!, poly[j]!, 1).length) return false;
  }
  return true;
}

/**
 * Simplifies every ring of every polygon. If simplification would break a simple polygon (self-
 * intersection or crossing rings), the tolerance is halved (up to 3 times), else the original
 * polygon is kept. Rings are never buffered, moved or scaled.
 */
export function simplifyPolygons(polys: ZonePolygon[], tolM: number): ZonePolygon[] {
  return polys.map((poly) => {
    const wasSimple = polygonIsSimple(poly);
    let tol = tolM;
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const next = poly.map((r) => simplifyRing(r, tol));
      if (!wasSimple || polygonIsSimple(next)) return next;
      tol /= 2;
    }
    return poly.map((r) => r.slice());
  });
}

// ---------------------------------------------------------------- validation

export type ZoneIssueCode =
  | 'too_few_vertices'
  | 'self_intersection'
  | 'rings_cross'
  | 'hole_outside'
  | 'zero_area'
  | 'outside_region'
  | 'partly_outside_region';

export interface ZoneIssue {
  code: ZoneIssueCode;
  severity: 'error' | 'warning';
  zone: ZoneKey;
  poly?: number;
  ring?: number;
  /** where to mark the problem on the map */
  points?: LonLat[];
}

/** [west, south, east, north] */
export type BBox = [number, number, number, number];

export function zoneBounds(zone: DrawnZone): BBox | null {
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  for (const poly of zone.polygons) {
    for (const ring of poly) {
      for (const p of ring) {
        w = Math.min(w, p[0]);
        e = Math.max(e, p[0]);
        s = Math.min(s, p[1]);
        n = Math.max(n, p[1]);
      }
    }
  }
  return Number.isFinite(w) ? [w, s, e, n] : null;
}

/**
 * Validity of one zone: ≥ 3 vertices per ring, simple rings (segment-intersection test), holes
 * inside their outer ring without crossing it, non-zero area; bbox checks against the region
 * (entirely outside → error, the API answers 422 ZONES_OUTSIDE_REGION; partly outside → warning).
 */
export function validateZone(zone: DrawnZone, regionBBox: BBox | null): ZoneIssue[] {
  const issues: ZoneIssue[] = [];
  zone.polygons.forEach((poly, pi) => {
    poly.forEach((ring, ri) => {
      if (ring.length < 3) issues.push({ code: 'too_few_vertices', severity: 'error', zone: zone.key, poly: pi, ring: ri, points: ring.slice(0, 1) });
      else {
        const x = ringSelfIntersections(ring, 20);
        if (x.length) issues.push({ code: 'self_intersection', severity: 'error', zone: zone.key, poly: pi, ring: ri, points: x });
      }
    });
    for (let i = 0; i < poly.length; i += 1) {
      for (let j = i + 1; j < poly.length; j += 1) {
        const x = ringsIntersections(poly[i]!, poly[j]!, 20);
        if (x.length) issues.push({ code: 'rings_cross', severity: 'error', zone: zone.key, poly: pi, ring: j, points: x });
      }
    }
    for (let h = 1; h < poly.length; h += 1) {
      const hole = poly[h]!;
      if (hole.length && poly[0]!.length >= 3 && !pointInRing(hole[0]!, poly[0]!)) {
        issues.push({ code: 'hole_outside', severity: 'error', zone: zone.key, poly: pi, ring: h, points: hole.slice(0, 1) });
      }
    }
    if (poly[0] && poly[0].length >= 3 && polygonAreaM2(poly) < 1) issues.push({ code: 'zero_area', severity: 'error', zone: zone.key, poly: pi, points: poly[0].slice(0, 1) });
  });
  const b = zoneBounds(zone);
  if (b && regionBBox) {
    const [w, s, e, n] = regionBBox;
    if (b[2] < w || b[0] > e || b[3] < s || b[1] > n) issues.push({ code: 'outside_region', severity: 'error', zone: zone.key });
    else if (b[0] < w || b[2] > e || b[1] < s || b[3] > n) issues.push({ code: 'partly_outside_region', severity: 'warning', zone: zone.key });
  }
  return issues;
}

export function validateZones(zones: DrawnZones, regionBBox: BBox | null): ZoneIssue[] {
  return ZONE_KEYS.flatMap((k) => validateZone(zones[k], regionBBox));
}

/** True when the 5 h zone lies inside the 8 h zone (the normal nested case; not required). */
export function isNested(inner: DrawnZone, outer: DrawnZone): boolean {
  if (!inner.polygons.length || !outer.polygons.length) return false;
  return inner.polygons.every((poly) => poly[0]!.every((p) => pointInZone(p, outer)));
}

// ---------------------------------------------------------------- editing (pure; returns new objects)

function cloneZones(z: DrawnZones): DrawnZones {
  const c = (zone: DrawnZone): DrawnZone => ({ ...zone, polygons: zone.polygons.map((p) => p.map((r) => r.map((v) => [v[0], v[1]] as LonLat))) });
  return { h5: c(z.h5), h8: c(z.h8) };
}

function touched(zone: DrawnZone): DrawnZone {
  return zone.preset ? { ...zone, edited: true } : zone;
}

export function addPolygon(z: DrawnZones, key: ZoneKey, ring: Ring): DrawnZones {
  const next = cloneZones(z);
  next[key] = touched({ ...next[key], polygons: [...next[key].polygons, [ring.map((v) => [v[0], v[1]] as LonLat)]] });
  return next;
}

export function moveVertex(z: DrawnZones, ref: VertexRef, p: LonLat): DrawnZones {
  const ring = z[ref.zone].polygons[ref.poly]?.[ref.ring];
  if (!ring || !ring[ref.index]) return z;
  const next = cloneZones(z);
  next[ref.zone].polygons[ref.poly]![ref.ring]![ref.index] = [p[0], p[1]];
  next[ref.zone] = touched(next[ref.zone]);
  return next;
}

/** Inserts a vertex after `ref.index` (i.e. on the edge ref.index → ref.index + 1); returns the new vertex ref. */
export function insertVertex(z: DrawnZones, ref: VertexRef, p: LonLat): { zones: DrawnZones; ref: VertexRef } {
  const ring = z[ref.zone].polygons[ref.poly]?.[ref.ring];
  if (!ring) return { zones: z, ref };
  const next = cloneZones(z);
  next[ref.zone].polygons[ref.poly]![ref.ring]!.splice(ref.index + 1, 0, [p[0], p[1]]);
  next[ref.zone] = touched(next[ref.zone]);
  return { zones: next, ref: { ...ref, index: ref.index + 1 } };
}

/**
 * Removes a vertex. A ring keeps at least 3 vertices: deleting from a triangle removes the whole
 * ring (a hole) or the whole polygon (an outer ring, with its holes). `removed` says which.
 */
export function deleteVertex(z: DrawnZones, ref: VertexRef): { zones: DrawnZones; removed: 'vertex' | 'ring' | 'polygon' } {
  const poly = z[ref.zone].polygons[ref.poly];
  const ring = poly?.[ref.ring];
  if (!poly || !ring || !ring[ref.index]) return { zones: z, removed: 'vertex' };
  const next = cloneZones(z);
  const zone = next[ref.zone];
  if (ring.length > 3) {
    zone.polygons[ref.poly]![ref.ring]!.splice(ref.index, 1);
    next[ref.zone] = touched(zone);
    return { zones: next, removed: 'vertex' };
  }
  if (ref.ring > 0) {
    zone.polygons[ref.poly]!.splice(ref.ring, 1);
    next[ref.zone] = touched(zone);
    return { zones: next, removed: 'ring' };
  }
  zone.polygons.splice(ref.poly, 1);
  next[ref.zone] = zone.polygons.length ? touched(zone) : emptyZone(ref.zone);
  return { zones: next, removed: 'polygon' };
}

export function clearZone(z: DrawnZones, key: ZoneKey): DrawnZones {
  const next = cloneZones(z);
  next[key] = emptyZone(key);
  return next;
}

/** All vertex refs of a zone in order (for keyboard cycling). */
export function vertexRefs(zone: DrawnZone): VertexRef[] {
  const out: VertexRef[] = [];
  zone.polygons.forEach((poly, pi) => poly.forEach((ring, ri) => ring.forEach((_, i) => out.push({ zone: zone.key, poly: pi, ring: ri, index: i }))));
  return out;
}

export function sameRef(a: VertexRef | null | undefined, b: VertexRef | null | undefined): boolean {
  return Boolean(a && b && a.zone === b.zone && a.poly === b.poly && a.ring === b.ring && a.index === b.index);
}

export function vertexAt(z: DrawnZones, ref: VertexRef | null | undefined): LonLat | null {
  if (!ref) return null;
  return z[ref.zone].polygons[ref.poly]?.[ref.ring]?.[ref.index] ?? null;
}

// ---------------------------------------------------------------- presets from recorded footprints

export interface FootprintLike {
  inputTime: string;
  geometry: Polygon | MultiPolygon;
}

/** Copies a recorded footprint into a zone, reducing vertices with Douglas–Peucker (tolerance ≈ 50 m). */
export function presetZone(key: ZoneKey, fp: FootprintLike, tolM = PRESET_TOLERANCE_M): DrawnZone {
  const raw = geometryToPolygons(fp.geometry);
  const simplified = simplifyPolygons(raw, tolM);
  return {
    key,
    arrivalHMax: ZONE_HOURS[key],
    polygons: simplified,
    preset: { kind: 'footprint', inputTime: fp.inputTime, verticesBefore: polygonsVertexCount(raw), verticesAfter: polygonsVertexCount(simplified), toleranceM: tolM },
    edited: false,
  };
}

/**
 * Default preset times: 5 h = the footprint recorded at the base input time, 8 h = the next later
 * recorded footprint (null when none exists). Never invents a footprint.
 */
export function defaultPresetTimes(footprintTimes: string[], baseInputTime: string | null): { h5: string | null; h8: string | null } {
  const times = [...new Set(footprintTimes)].sort((a, b) => parseUtc(a) - parseUtc(b));
  if (!baseInputTime) return { h5: null, h8: null };
  const base = parseUtc(baseInputTime);
  const h5 = times.find((t) => parseUtc(t) === base) ?? null;
  const h8 = times.find((t) => parseUtc(t) > base) ?? null;
  return { h5, h8 };
}

// ---------------------------------------------------------------- request building

export interface ZoneFeatureProps {
  arrival_h_max: number;
}

function roundCoord(v: number): number {
  return Math.round(v * 1e6) / 1e6;
}

/**
 * Contract ZoneCollection: one Feature per non-empty zone, Polygon (one part) or MultiPolygon,
 * rings closed, outer rings counter-clockwise and holes clockwise (RFC 7946), coordinates rounded
 * to 1e-6°, properties exactly {arrival_h_max}.
 */
export function zonesFeatureCollection(zones: DrawnZones): FeatureCollection<Polygon | MultiPolygon, ZoneFeatureProps> {
  const features: Feature<Polygon | MultiPolygon, ZoneFeatureProps>[] = [];
  for (const key of ZONE_KEYS) {
    const zone = zones[key];
    const polys = zone.polygons
      .map((poly) =>
        poly
          .filter((r) => r.length >= 3)
          .map((ring, i) => {
            const r = ring.map((p) => [roundCoord(p[0]), roundCoord(p[1])] as LonLat);
            const ccw = ringIsCcw(r);
            const oriented = (i === 0) === ccw ? r : [...r].reverse();
            return closeRing(oriented);
          }),
      )
      .filter((poly) => poly.length > 0);
    if (!polys.length) continue;
    const geometry: Polygon | MultiPolygon = polys.length === 1 ? { type: 'Polygon', coordinates: polys[0]! } : { type: 'MultiPolygon', coordinates: polys };
    features.push({ type: 'Feature', geometry, properties: { arrival_h_max: zone.arrivalHMax } });
  }
  return { type: 'FeatureCollection', features };
}

/** "2025-03-24T09:00:00Z" minus offset hours → ISO UTC without milliseconds. */
export function issuedAtFor(inputTime: string, offsetH: number): string {
  const t = parseUtc(inputTime) - Math.round(offsetH * 3600) * 1000;
  return new Date(t).toISOString().replace(/\.\d{3}Z$/, 'Z');
}

/** Seconds from the zone forecast's issue time to input time + offsetS (relative clock "T+h:mm"). */
export function secondsSinceIssue(inputTime: string, issuedAt: string, offsetS: number): number {
  return (parseUtc(inputTime) - parseUtc(issuedAt)) / 1000 + offsetS;
}

export function clampIssueOffsetH(v: unknown): number {
  const n = Math.round(Number(v));
  return Number.isFinite(n) ? Math.max(0, Math.min(MAX_ISSUE_OFFSET_H, n)) : 0;
}

export function clampMarginMin(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(0, Math.min(MAX_MARGIN_MIN, Math.round(n))) : DEFAULT_MARGIN_MIN;
}

/** Stable short fingerprint (FNV-1a 32 bit, hex) of a JSON-able value — tags results with their fire input. */
export function fingerprint(v: unknown): string {
  const s = JSON.stringify(v);
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

export interface ZoneSummary {
  key: ZoneKey;
  arrivalHMax: number;
  polygons: number;
  holes: number;
  vertices: number;
  areaKm2: number;
}

export function zoneSummary(zone: DrawnZone): ZoneSummary {
  return {
    key: zone.key,
    arrivalHMax: zone.arrivalHMax,
    polygons: zone.polygons.length,
    holes: zone.polygons.reduce((n, p) => n + Math.max(0, p.length - 1), 0),
    vertices: zoneVertexCount(zone),
    areaKm2: zoneAreaKm2(zone),
  };
}

/** Label anchor: the northern-, southern-, western- or easternmost vertex of the zone's outer rings. */
export function labelAnchor(zone: DrawnZone, side: 'north' | 'south' | 'west' | 'east'): LonLat | null {
  let best: LonLat | null = null;
  const better = (p: LonLat, b: LonLat) =>
    side === 'north' ? p[1] > b[1] : side === 'south' ? p[1] < b[1] : side === 'west' ? p[0] < b[0] : p[0] > b[0];
  for (const poly of zone.polygons) {
    for (const p of poly[0] ?? []) {
      if (!best || better(p, best)) best = p;
    }
  }
  return best;
}

// ---------------------------------------------------------------- persistence (shape only; storage I/O lives in state/)

export interface StoredZones {
  version: 1;
  zones: DrawnZones;
  settings: { inputTime: string | null; issueOffsetH: number; marginMin: number };
  savedAt: string;
}

function validRing(r: unknown): r is LonLat[] {
  return Array.isArray(r) && r.every((p) => Array.isArray(p) && p.length >= 2 && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1])));
}

/** Parses what the app stored in localStorage; anything malformed → null (start empty). */
export function parseStoredZones(raw: unknown): StoredZones | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  if (r.version !== 1 || !r.zones || typeof r.zones !== 'object') return null;
  const zr = r.zones as Record<string, unknown>;
  const zones = emptyZones();
  for (const key of ZONE_KEYS) {
    const z = zr[key] as Record<string, unknown> | undefined;
    if (!z || !Array.isArray(z.polygons)) continue;
    const polys: ZonePolygon[] = [];
    for (const poly of z.polygons as unknown[]) {
      if (!Array.isArray(poly) || !poly.every(validRing)) continue;
      const rings = (poly as LonLat[][]).map((ring) => openRing(ring)).filter((ring) => ring.length > 0);
      if (rings.length) polys.push(rings);
    }
    const pr = z.preset as Record<string, unknown> | null | undefined;
    zones[key] = {
      key,
      arrivalHMax: ZONE_HOURS[key],
      polygons: polys,
      preset:
        pr && pr.kind === 'footprint' && typeof pr.inputTime === 'string'
          ? { kind: 'footprint', inputTime: pr.inputTime, verticesBefore: Number(pr.verticesBefore) || 0, verticesAfter: Number(pr.verticesAfter) || 0, toleranceM: Number(pr.toleranceM) || PRESET_TOLERANCE_M }
          : null,
      edited: z.edited === true,
    };
  }
  const st = (r.settings ?? {}) as Record<string, unknown>;
  return {
    version: 1,
    zones,
    settings: {
      inputTime: typeof st.inputTime === 'string' ? st.inputTime : null,
      issueOffsetH: clampIssueOffsetH(st.issueOffsetH),
      marginMin: clampMarginMin(st.marginMin ?? DEFAULT_MARGIN_MIN),
    },
    savedAt: typeof r.savedAt === 'string' ? r.savedAt : '',
  };
}
