// WildfireGuardian 3D booth replay (web/finals3d.html).
// Draws web/assets/finals3d/data.js (built by scripts/build_finals3d.py) and nothing else:
// no network, no numbers typed by hand. Every count on screen is computed here from that
// payload with the same rule the build script records in data/processed/finals3d/.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';

const D = window.WFG3D;
const VEX = 1.6;            // vertical exaggeration of the terrain (stated on screen)
const B_H = 3.0;            // building footprint exaggeration (stated on screen)
const B_V = 2.6;            // building height exaggeration
const NEVER = 65535;
const WALK_CAP_MIN = 90;    // walks longer than this are flagged on the card, not recoloured

// ---------------------------------------------------------------- payload decoding
function b64(s, T) {
  const bin = atob(s);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return T === Uint8Array ? u8 : new T(u8.buffer);
}
const TR = D.terrain;
const H = b64(TR.h, Int16Array);
const SEA = b64(TR.sea, Uint8Array);
const W = (TR.nx - 1) * TR.step;
const L = (TR.ny - 1) * TR.step;
const PASS = D.obs_times_min;
const HORIZON = D.horizon_min;

function heightAt(x, y) {
  const fx = Math.min(Math.max(x / TR.step, 0), TR.nx - 1.001);
  const fy = Math.min(Math.max(y / TR.step, 0), TR.ny - 1.001);
  const c = Math.floor(fx), r = Math.floor(fy), tx = fx - c, ty = fy - r;
  const i = r * TR.nx + c;
  const h00 = H[i], h10 = H[i + 1], h01 = H[i + TR.nx], h11 = H[i + TR.nx + 1];
  return (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty;
}
// local metres (x east, y north, from the ROI origin) -> world
const wx = (x) => x - W / 2;
const wz = (y) => -(y - L / 2);
const wy = (x, y) => heightAt(x, y) * VEX;

// ---------------------------------------------------------------- renderer and scene
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05070d);
scene.fog = new THREE.FogExp2(0x070a12, 0.000022);

const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 30, 200000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 600;
controls.maxDistance = 90000;

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.75, 0.35, 0.9);
composer.addPass(bloom);
composer.addPass(new OutputPass());

// shared uniforms
const U = {
  uTime: { value: 0 },           // replay minute since T0
  uClock: { value: 0 },          // wall seconds, for flicker
  uScan: { value: -1 },          // satellite sweep progress 0..1, -1 off
  uForecast: { value: 0 },
  uFireOrigin: { value: new THREE.Vector2(D.fire.origin[0], D.fire.origin[1]) },
  uFireSize: { value: new THREE.Vector2(D.fire.ncols * D.fire.cell, D.fire.nrows * D.fire.cell) },
  uSize: { value: new THREE.Vector2(W, L) },
};

// fire state texture, recomputed on the CPU whenever the replay minute changes.
// R = flaming front, G = burned (seen by a satellite), B = could be burning (between the
// last clear look and the first detection), A = model forecast has reached the cell.
const firstPass = b64(D.fire.first_pass, Uint8Array);
const fc16 = b64(D.fire.forecast_min, Uint16Array);
const FNC = D.fire.ncols, FNR = D.fire.nrows;
const fireTexData = new Uint8Array(FNC * FNR * 4);
const fireTex = new THREE.DataTexture(fireTexData, FNC, FNR, THREE.RGBAFormat);
fireTex.magFilter = THREE.LinearFilter;
fireTex.minFilter = THREE.LinearFilter;
U.uFireTex = { value: fireTex };
const cellTR = new Float32Array(FNC * FNR), cellTL = new Float32Array(FNC * FNR);
for (let i = 0; i < firstPass.length; i++) {
  const k = firstPass[i];
  cellTR[i] = k ? PASS[k - 1] : 1e9;
  cellTL[i] = k >= 2 ? PASS[k - 2] : -1e9;
}
const burnedAt = (c, r, t) => c >= 0 && r >= 0 && c < FNC && r < FNR && t >= cellTR[r * FNC + c];
function updateFireTex(t) {
  for (let r = 0; r < FNR; r++) {
    for (let c = 0; c < FNC; c++) {
      const i = r * FNC + c, o = i * 4;
      const burned = t >= cellTR[i];
      const edge = burned && !(burnedAt(c - 1, r, t) && burnedAt(c + 1, r, t) && burnedAt(c, r - 1, t) && burnedAt(c, r + 1, t));
      const fresh = burned && firstPass[i] >= 2 ? 0.75 * Math.max(0, 1 - (t - cellTR[i]) / 90) : 0;
      fireTexData[o] = Math.round(255 * Math.max(edge ? 0.6 : 0, fresh));
      fireTexData[o + 1] = burned ? 255 : 0;
      fireTexData[o + 2] = !burned && t > cellTL[i] && firstPass[i] >= 2 ? 255 : 0;
      fireTexData[o + 3] = fc16[i] <= t ? 255 : 0;
    }
  }
  fireTex.needsUpdate = true;
}

const GLSL_COMMON = /* glsl */`
  uniform float uTime; uniform float uClock;
  uniform sampler2D uFireTex; uniform vec2 uFireOrigin; uniform vec2 uFireSize;
  float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f*f*(3.0-2.0*f);
    return mix(mix(hash(i), hash(i+vec2(1,0)), u.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), u.x), u.y); }
  float fbm(vec2 p){ float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++){ v += a*noise(p); p *= 2.03; a *= 0.5; } return v; }
  vec4 fireSample(vec2 local){
    vec2 warp = vec2(fbm(local*0.0018), fbm(local*0.0018 + 17.3)) - 0.5;
    vec2 uv = (local - uFireOrigin + warp * 300.0) / uFireSize;
    if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return vec4(0.0);
    return texture2D(uFireTex, uv);
  }
`;

// ---------------------------------------------------------------- terrain
function buildTerrain() {
  const nx = TR.nx, ny = TR.ny;
  const pos = new Float32Array(nx * ny * 3);
  const loc = new Float32Array(nx * ny * 2);
  const sea = new Float32Array(nx * ny);
  for (let r = 0; r < ny; r++) {
    for (let c = 0; c < nx; c++) {
      const i = r * nx + c, x = c * TR.step, y = r * TR.step;
      pos[i * 3] = wx(x); pos[i * 3 + 1] = SEA[i] ? -6 : H[i] * VEX; pos[i * 3 + 2] = wz(y);
      loc[i * 2] = x; loc[i * 2 + 1] = y; sea[i] = SEA[i];
    }
  }
  const idx = new Uint32Array((nx - 1) * (ny - 1) * 6);
  let k = 0;
  for (let r = 0; r < ny - 1; r++) {
    for (let c = 0; c < nx - 1; c++) {
      const a = r * nx + c, b = a + 1, d = a + nx, e = d + 1;
      idx[k++] = a; idx[k++] = b; idx[k++] = d; idx[k++] = b; idx[k++] = e; idx[k++] = d;
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aLocal', new THREE.BufferAttribute(loc, 2));
  g.setAttribute('aSea', new THREE.BufferAttribute(sea, 1));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  g.computeVertexNormals();
  const m = new THREE.ShaderMaterial({
    uniforms: U,
    vertexShader: /* glsl */`
      attribute vec2 aLocal; attribute float aSea;
      varying vec2 vLocal; varying float vSea; varying vec3 vN; varying float vH; varying vec3 vW;
      void main(){ vLocal = aLocal; vSea = aSea; vN = normal; vH = position.y;
        vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: GLSL_COMMON + /* glsl */`
      uniform float uScan; uniform float uForecast; uniform vec2 uSize;
      varying vec2 vLocal; varying float vSea; varying vec3 vN; varying float vH; varying vec3 vW;
      void main(){
        vec3 n = normalize(vN);
        vec3 moon = normalize(vec3(-0.45, 0.8, 0.35));
        float lam = max(dot(n, moon), 0.0);
        float h = vH / 1.6;
        vec3 low = vec3(0.040, 0.055, 0.045), mid = vec3(0.055, 0.070, 0.052), high = vec3(0.085, 0.085, 0.075);
        vec3 base = mix(low, mid, smoothstep(40.0, 260.0, h));
        base = mix(base, high, smoothstep(300.0, 750.0, h));
        base *= 0.85 + 0.3 * fbm(vLocal * 0.006);
        vec3 col = base * (0.25 + 1.15 * lam);
        // faint 100 m contours
        float ct = abs(fract(h / 100.0) - 0.5);
        col += vec3(0.03, 0.045, 0.045) * (1.0 - smoothstep(0.0, 0.035, 0.5 - ct)) * step(20.0, h);
        if (vSea > 0.5) {
          float wv = fbm(vLocal * 0.004 + vec2(uClock * 0.02, 0.0));
          col = vec3(0.012, 0.025, 0.05) + vec3(0.02, 0.035, 0.06) * wv;
        } else {
          vec4 fs = fireSample(vLocal);
          float n1 = fbm(vLocal * 0.004);
          float burned = smoothstep(0.38, 0.62, fs.g + (n1 - 0.5) * 0.55);
          float flick = fbm(vLocal * 0.018 + vec2(uClock * 0.7, -uClock * 1.1));
          float ember = smoothstep(0.74, 0.93, fbm(vLocal * 0.035 + vec2(uClock * 0.15, 0.0)));
          vec3 charred = vec3(0.022, 0.010, 0.007) * (0.6 + lam) + vec3(0.95, 0.24, 0.03) * ember * 0.8;
          col = mix(col, charred, burned);
          float core = smoothstep(0.72, 0.97, fs.g + (n1 - 0.5) * 0.3);
          float front = burned * (1.0 - core) * max(fs.r, 0.28) * smoothstep(0.25, 0.75, flick + 0.25);
          col += mix(vec3(1.05, 0.26, 0.03), vec3(1.9, 0.80, 0.14), flick) * front * 1.25;
          float hz = smoothstep(0.3, 0.7, fs.b + (n1 - 0.5) * 0.4) * (1.0 - burned);
          float stripes = smoothstep(0.55, 0.75, fract((vLocal.x - vLocal.y + uClock * 90.0) / 260.0)) * (1.0 - smoothstep(0.85, 1.0, fract((vLocal.x - vLocal.y + uClock * 90.0) / 260.0)));
          float pulse = 0.65 + 0.35 * sin(uClock * 2.2 + n1 * 6.0);
          vec3 hazeCol = vec3(0.13, 0.10, 0.09) * pulse + vec3(0.05, 0.03, 0.02) * stripes;
          col = mix(col, hazeCol, hz * 0.7);
          if (uForecast > 0.5) {
            float fa = smoothstep(0.4, 0.6, fs.a);
            float hatch = step(0.5, fract((vLocal.x + vLocal.y) / 160.0));
            col = mix(col, vec3(0.45, 0.30, 0.95), fa * (0.28 + 0.2 * hatch));
          }
        }
        if (uScan >= 0.0) {
          float yb = (1.0 - uScan) * uSize.y;
          float band = exp(-pow((vLocal.y - yb) / 260.0, 2.0));
          col += vec3(0.55, 0.95, 1.4) * band * 1.4;
        }
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  const mesh = new THREE.Mesh(g, m);
  scene.add(mesh);
  return mesh;
}
const terrain = buildTerrain();

// ---------------------------------------------------------------- roads
const roadData = (() => {
  const xy = b64(D.roads.xy, Uint16Array);
  const cl = b64(D.roads.close, Uint16Array);
  const n = D.roads.n;
  const pos = new Float32Array(n * 6);
  const cR = new Float32Array(n * 2), cL = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) {
    const x1 = xy[i * 4], y1 = xy[i * 4 + 1], x2 = xy[i * 4 + 2], y2 = xy[i * 4 + 3];
    pos.set([wx(x1), wy(x1, y1) + 7, wz(y1), wx(x2), wy(x2, y2) + 7, wz(y2)], i * 6);
    const r = cl[i * 2] === NEVER ? 1e9 : cl[i * 2], l = cl[i * 2 + 1] === NEVER ? 1e9 : cl[i * 2 + 1];
    cR[i * 2] = cR[i * 2 + 1] = r; cL[i * 2] = cL[i * 2 + 1] = l;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aCloseR', new THREE.BufferAttribute(cR, 1));
  g.setAttribute('aCloseL', new THREE.BufferAttribute(cL, 1));
  const m = new THREE.ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false,
    vertexShader: /* glsl */`
      attribute float aCloseR; attribute float aCloseL; varying float vR; varying float vL;
      void main(){ vR = aCloseR; vL = aCloseL; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */`
      uniform float uTime; uniform float uClock; varying float vR; varying float vL;
      void main(){
        vec4 c = vec4(0.55, 0.62, 0.72, 0.16);
        if (uTime > vL) c = vec4(1.35, 0.78, 0.12, 0.70 + 0.25 * sin(uClock * 3.0));
        if (uTime >= vR) c = vec4(2.2, 0.22, 0.12, 0.95);
        gl_FragColor = c; }`,
  });
  const lines = new THREE.LineSegments(g, m);
  lines.renderOrder = 2;
  scene.add(lines);
  return { lines };
})();

// ---------------------------------------------------------------- buildings
const B = D.buildings;
const bx = b64(B.x, Uint16Array), by = b64(B.y, Uint16Array);
const bsize = b64(B.size, Uint8Array), bfl = b64(B.floors, Uint8Array), bnode = b64(B.node, Int32Array);
const SPEEDS = D.speeds;
const NODE = {};
for (const s of SPEEDS) {
  const p = D.nodes.per_speed[s];
  NODE[s] = { lsdR: b64(p.lsdR, Int16Array), lsdL: b64(p.lsdL, Int16Array), walk: b64(p.walkR, Uint16Array) };
}
let speed = SPEEDS.includes('0.7') ? '0.7' : SPEEDS[0];

const buildings = (() => {
  const geo = new THREE.BoxGeometry(1, 1, 1);
  geo.translate(0, 0.5, 0);
  const aL = new THREE.InstancedBufferAttribute(new Float32Array(B.n), 1);
  const aR = new THREE.InstancedBufferAttribute(new Float32Array(B.n), 1);
  const aOk = new THREE.InstancedBufferAttribute(new Float32Array(B.n), 1);
  const aSel = new THREE.InstancedBufferAttribute(new Float32Array(B.n), 1);
  geo.setAttribute('aL', aL); geo.setAttribute('aR', aR); geo.setAttribute('aOk', aOk); geo.setAttribute('aSel', aSel);
  const m = new THREE.ShaderMaterial({
    uniforms: U,
    vertexShader: /* glsl */`
      attribute float aL; attribute float aR; attribute float aOk; attribute float aSel;
      varying float vL; varying float vR; varying float vOk; varying float vSel; varying vec3 vN; varying float vTop;
      void main(){ vL = aL; vR = aR; vOk = aOk; vSel = aSel; vN = normal; vTop = position.y;
        gl_Position = projectionMatrix * viewMatrix * modelMatrix * instanceMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */`
      uniform float uTime; uniform float uClock;
      varying float vL; varying float vR; varying float vOk; varying float vSel; varying vec3 vN; varying float vTop;
      void main(){
        vec3 green = vec3(0.18, 1.25, 0.42), amber = vec3(1.7, 0.95, 0.08), red = vec3(0.60, 0.05, 0.04), grey = vec3(0.16, 0.17, 0.19);
        vec3 c;
        if (vOk < 0.5) c = grey;
        else if (vR < 0.0 || uTime > vR) c = red;
        else if (vL >= 0.0 && uTime <= vL) c = green;
        else c = amber * (0.75 + 0.25 * sin(uClock * 4.0));
        float shade = vN.y > 0.5 ? 1.0 : 0.55 + 0.25 * abs(vN.x);
        c *= shade;
        if (vSel > 0.5) c = mix(c, vec3(3.0), 0.35 + 0.35 * sin(uClock * 6.0));
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
  const mesh = new THREE.InstancedMesh(geo, m, B.n);
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  for (let i = 0; i < B.n; i++) {
    const w = Math.max(bsize[i], 6) * B_H;
    const h = Math.max(bfl[i] * 3.2, 3.2) * B_V;
    p.set(wx(bx[i]), wy(bx[i], by[i]) - 2, wz(by[i]));
    s.set(w, h, w);
    M.compose(p, q, s);
    mesh.setMatrixAt(i, M);
  }
  mesh.instanceMatrix.needsUpdate = true;
  mesh.frustumCulled = false;
  scene.add(mesh);
  return { mesh, aL, aR, aOk, aSel };
})();

function applySpeed(s) {
  speed = s;
  const N = NODE[s];
  for (let i = 0; i < B.n; i++) {
    const k = bnode[i];
    if (k < 0) { buildings.aOk.array[i] = 0; buildings.aL.array[i] = -1; buildings.aR.array[i] = -1; continue; }
    buildings.aOk.array[i] = 1;
    buildings.aL.array[i] = N.lsdL[k];
    buildings.aR.array[i] = N.lsdR[k];
  }
  buildings.aOk.needsUpdate = buildings.aL.needsUpdate = buildings.aR.needsUpdate = true;
  document.querySelectorAll('[data-speed]').forEach((b) => b.classList.toggle('on', b.dataset.speed === s));
  updateCounts(true);
  if (selected >= 0) showCard(selected);
}

// state of one building at minute t, the rule recorded in finals3d_scene.json
function stateOf(i, t) {
  const k = bnode[i];
  if (k < 0) return 'na';
  const lo = NODE[speed].lsdL[k], hi = NODE[speed].lsdR[k];
  if (hi < 0 || t > hi) return 'late';
  if (lo >= 0 && t <= lo) return 'open';
  return 'unknown';
}

// ---------------------------------------------------------------- refuges and labels
(() => {
  const g = new THREE.CylinderGeometry(22, 22, 420, 12, 1, true);
  g.translate(0, 210, 0);
  const m = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.25, 1.1, 1.6), transparent: true, opacity: 0.14, depthWrite: false, side: THREE.DoubleSide });
  const cap = new THREE.SphereGeometry(45, 16, 12);
  const mc = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.3, 1.1, 1.5) });
  for (const [x, y] of D.refuges) {
    const beam = new THREE.Mesh(g, m);
    beam.position.set(wx(x), wy(x, y), wz(y));
    scene.add(beam);
    const s = new THREE.Mesh(cap, mc);
    s.position.set(wx(x), wy(x, y) + 30, wz(y));
    scene.add(s);
  }
})();
const labelLayer = document.getElementById('labels');
const labels = D.labels.filter((l) => l.kind === '읍면동').map((l) => {
  const el = document.createElement('div');
  el.className = 'lbl town';
  el.textContent = l.name.replace('사무소', '');
  labelLayer.appendChild(el);
  return { el, v: new THREE.Vector3(wx(l.x), wy(l.x, l.y) + 260, wz(l.y)), kind: l.kind, x: l.x, y: l.y, name: l.name };
});

// ---------------------------------------------------------------- embers and smoke
const burnCells = [];
for (let r = 0; r < D.fire.nrows; r++) {
  for (let c = 0; c < D.fire.ncols; c++) {
    const k = firstPass[r * D.fire.ncols + c];
    if (!k) continue;
    const x = D.fire.origin[0] + (c + 0.5) * D.fire.cell, y = D.fire.origin[1] + (r + 0.5) * D.fire.cell;
    if (x < 0 || y < 0 || x > W || y > L) continue;
    burnCells.push({ x, y, t: PASS[k - 1] });
  }
}
function particles(n, kind) {
  const pos = new Float32Array(n * 3), seed = new Float32Array(n), tOn = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const c = burnCells[(Math.random() * burnCells.length) | 0] || { x: 0, y: 0, t: 1e9 };
    const x = c.x + (Math.random() - 0.5) * D.fire.cell, y = c.y + (Math.random() - 0.5) * D.fire.cell;
    pos.set([wx(x), wy(x, y), wz(y)], i * 3);
    seed[i] = Math.random(); tOn[i] = c.t;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
  g.setAttribute('aOn', new THREE.BufferAttribute(tOn, 1));
  const smoke = kind === 'smoke';
  const m = new THREE.ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false,
    blending: smoke ? THREE.NormalBlending : THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      uniform float uTime; uniform float uClock; attribute float aSeed; attribute float aOn;
      varying float vA; varying float vS;
      void main(){
        float life = fract(uClock * ${smoke ? '0.05' : '0.22'} + aSeed);
        float age = uTime - aOn;
        float alive = step(0.0, age) * (1.0 - smoothstep(${smoke ? '300.0, 420.0' : '90.0, 200.0'}, age));
        vec3 p = position;
        p.y += life * ${smoke ? '2600.0' : '700.0'};
        p.x += life * ${smoke ? '2200.0' : '160.0'} * (0.6 + aSeed);
        p.z += sin(aSeed * 40.0 + uClock) * ${smoke ? '300.0' : '60.0'};
        vA = alive * (1.0 - life) * ${smoke ? '0.16' : '1.0'}; vS = life;
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_PointSize = ${smoke ? '(900.0 + 2600.0 * life)' : '(34.0 + 30.0 * aSeed)'} * (320.0 / -mv.z);
        gl_Position = projectionMatrix * mv; }`,
    fragmentShader: /* glsl */`
      varying float vA; varying float vS;
      void main(){ vec2 d = gl_PointCoord - 0.5; float r = length(d); if (r > 0.5) discard;
        float soft = 1.0 - smoothstep(0.0, 0.5, r);
        ${smoke ? 'gl_FragColor = vec4(vec3(0.20, 0.18, 0.17) + vec3(0.25, 0.08, 0.0) * (1.0 - vS), vA * soft);'
                : 'gl_FragColor = vec4(vec3(3.5, 1.4, 0.3) * soft, vA * soft);'} }`,
  });
  const pts = new THREE.Points(g, m);
  pts.frustumCulled = false;
  scene.add(pts);
  return pts;
}
const smoke = particles(2600, 'smoke');
const embers = particles(3200, 'embers');

// ---------------------------------------------------------------- UI: clock, timeline, counts
const $ = (id) => document.getElementById(id);
const pad = (n) => String(n).padStart(2, '0');
const T0 = new Date(D.t0_utc).getTime();
function kst(min) {
  const d = new Date(T0 + min * 60000 + 9 * 3600000);
  return { md: `${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일`, hm: `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}` };
}
function dur(min) {
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return h > 0 ? `${h}시간 ${m}분` : `${m}분`;
}
const passesIn = PASS.filter((t) => t <= HORIZON);
(() => { // timeline marks
  const bar = $('tl-track');
  for (let i = 0; i < passesIn.length; i++) {
    const t = passesIn[i];
    const mk = document.createElement('div');
    mk.className = 'pass';
    mk.style.left = `${(t / HORIZON) * 100}%`;
    mk.innerHTML = `<span>위성 ${kst(t).hm}</span>`;
    bar.appendChild(mk);
    const next = PASS[i + 1];
    if (next !== undefined) {
      const gap = document.createElement('div');
      gap.className = 'gap';
      gap.style.left = `${(t / HORIZON) * 100}%`;
      gap.style.width = `${(Math.min(next, HORIZON) - t) / HORIZON * 100}%`;
      bar.appendChild(gap);
    }
  }
})();

let simT = 0, playing = false, rate = 6; // replay minutes per second
const fmtN = (n) => n.toLocaleString('ko-KR');
let lastCountT = -1;
function updateCounts(force) {
  const t = Math.floor(simT);
  if (!force && t === lastCountT) return;
  lastCountT = t;
  let open = 0, unk = 0, late = 0, tot = 0;
  for (let i = 0; i < B.n; i++) {
    const s = stateOf(i, simT);
    if (s === 'na') continue;
    tot++;
    if (s === 'open') open++; else if (s === 'unknown') unk++; else late++;
  }
  $('n-open').textContent = fmtN(open); $('n-unk').textContent = fmtN(unk); $('n-late').textContent = fmtN(late);
  $('b-open').style.width = `${(open / tot) * 100}%`;
  $('b-unk').style.width = `${(unk / tot) * 100}%`;
  $('b-late').style.width = `${(late / tot) * 100}%`;
  $('n-tot').textContent = fmtN(tot);
}
function updateClock() {
  const k = kst(simT);
  $('clock-hm').textContent = k.hm;
  $('clock-md').textContent = k.md;
  $('clock-rel').textContent = `T+${pad(Math.floor(simT / 60))}:${pad(Math.floor(simT % 60))}`;
  $('tl-head').style.left = `${(simT / HORIZON) * 100}%`;
  // blind-gap banner
  const prev = [...PASS].reverse().find((p) => p <= simT);
  const next = PASS.find((p) => p > simT);
  const gapBanner = $('gap');
  if (prev !== undefined && next !== undefined && simT - prev > 3) {
    gapBanner.classList.add('on');
    $('gap-left').textContent = dur(next - simT);
    $('gap-since').textContent = dur(simT - prev);
  } else gapBanner.classList.remove('on');
}
function setTime(t) {
  const before = simT;
  simT = Math.min(Math.max(t, 0), HORIZON);
  U.uTime.value = simT;
  updateFireTex(simT);
  for (const p of PASS) if (before < p && simT >= p && p > 0) satelliteFlash(p);
  updateClock();
  updateCounts(false);
  if (selected >= 0) updateCardState(selected);
  captions();
}

// satellite pass: screen flash + sweep across the terrain
let scanStart = -1;
function satelliteFlash(p) {
  const f = $('flash');
  f.classList.remove('go'); void f.offsetWidth; f.classList.add('go');
  $('flash-t').textContent = `위성 관측 ${kst(p).hm}`;
  scanStart = performance.now();
}

// ---------------------------------------------------------------- camera
const CENTER = new THREE.Vector3(0, 0, 0);
function fireCentroid() {
  let sx = 0, sy = 0, n = 0;
  for (const c of burnCells) if (c.t <= PASS[1]) { sx += c.x; sy += c.y; n++; }
  return n ? { x: sx / n, y: sy / n } : { x: W / 2, y: L / 2 };
}
const FC = fireCentroid();
const VIEWS = {
  all: { p: [wx(W * 0.62), 26000, wz(-L * 0.28)], t: [wx(W * 0.5), 0, wz(L * 0.48)] },
  front: { p: [wx(FC.x + 5200), wy(FC.x, FC.y) + 5200, wz(FC.y - 7200)], t: [wx(FC.x), wy(FC.x, FC.y), wz(FC.y)] },
  coast: (() => {
    const c = labels.find((l) => l.name.startsWith('영덕읍')) || labels[0];
    return { p: [wx(c.x - 3500), wy(c.x, c.y) + 3800, wz(c.y - 5200)], t: [wx(c.x), wy(c.x, c.y), wz(c.y)] };
  })(),
};
let fly = null;
function flyTo(v, secs = 2.4) {
  fly = { p0: camera.position.clone(), t0: controls.target.clone(), p1: new THREE.Vector3(...v.p), t1: new THREE.Vector3(...v.t), s: performance.now(), d: secs * 1000 };
}
camera.position.set(wx(W * 0.5), 60000, wz(-L * 0.9));
controls.target.set(0, 0, 0);

// ---------------------------------------------------------------- picking and the house card
const ray = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let selected = -1;
function nearestTown(x, y) {
  let best = null, bd = Infinity;
  for (const l of labels) {
    if (l.kind !== '읍면동' && l.kind !== '시군구') continue;
    const d = (l.x - x) ** 2 + (l.y - y) ** 2;
    if (d < bd) { bd = d; best = l; }
  }
  return best ? best.name.replace('사무소', '') : '';
}
function speedLabel(s) { return { '1.2': '일반 보행 1.2 m/s', '0.7': '고령자 0.7 m/s', '0.5': '거동 불편 0.5 m/s' }[s] || `${s} m/s`; }
function showCard(i) {
  if (selected >= 0) buildings.aSel.array[selected] = 0;
  selected = i;
  buildings.aSel.array[i] = 1; buildings.aSel.needsUpdate = true;
  const k = bnode[i];
  $('card').classList.add('on');
  $('c-where').textContent = `${nearestTown(bx[i], by[i])} 인근 · 주건물 · 지상 ${bfl[i]}층`;
  $('c-speed').textContent = speedLabel(speed);
  if (k < 0) {
    $('c-dead').textContent = '이 건물은 보행망 분석 범위 밖입니다';
    $('c-walk').textContent = '';
    $('c-note').textContent = '';
  } else {
    const N = NODE[speed], lo = N.lsdL[k], hi = N.lsdR[k], wk = N.walk[k];
    let txt;
    if (hi < 0) txt = '위성 기록상 처음부터 걸어서 나갈 길이 없습니다';
    else if (lo >= HORIZON) txt = `분석 끝(${kst(HORIZON).hm})까지 계속 걸어서 나갈 수 있습니다`;
    else if (lo < 0) txt = `늦어도 ${kst(hi).hm}까지 떠나야 합니다 (더 이를 수도 있음: 위성이 보지 못한 시간)`;
    else if (lo === hi) txt = `${kst(hi).hm}까지 떠나야 합니다`;
    else txt = `${kst(lo).hm} ~ ${kst(hi).hm} 사이에 마감 (위성 관측 사이의 불확실성)`;
    $('c-dead').textContent = txt;
    $('c-walk').textContent = wk === NEVER ? '' : `지금 출발하면 대피소까지 도보 약 ${wk}분`;
    $('c-note').textContent = wk !== NEVER && wk > WALK_CAP_MIN ? `${WALK_CAP_MIN}분 넘게 걸어야 합니다: 고령자에게는 차량 구조가 필요할 수 있습니다` : '';
  }
  updateCardState(i);
}
function updateCardState(i) {
  const s = stateOf(i, simT);
  const el = $('c-state');
  el.className = 'state ' + s;
  el.textContent = { open: '지금 떠나면 걸어서 대피 가능', unknown: '위성으로는 판단할 수 없음', late: '걸어서 나가기엔 이미 늦음', na: '분석 범위 밖' }[s];
}
let downAt = null;
canvas.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerup', (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  mouse.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObject(buildings.mesh, false)[0];
  if (hit && hit.instanceId !== undefined) {
    showCard(hit.instanceId);
    const i = hit.instanceId, x = bx[i], y = by[i];
    flyTo({ p: [wx(x + 900), wy(x, y) + 1100, wz(y - 1500)], t: [wx(x), wy(x, y), wz(y)] }, 1.6);
  }
});
$('c-close').onclick = () => {
  $('card').classList.remove('on');
  if (selected >= 0) { buildings.aSel.array[selected] = 0; buildings.aSel.needsUpdate = true; }
  selected = -1;
};

// ---------------------------------------------------------------- captions (guided mode)
const CAPS = [
  [0, 20, () => `${kst(0).hm}, 위성이 영덕의 불을 봤습니다.`],
  [20, 120, () => `다음 위성 관측은 ${dur(PASS[1] - PASS[0])} 뒤입니다.`],
  [120, PASS[1] - 5, () => '그 사이 불이 어디까지 왔는지, 누구도 확실히 알 수 없었습니다.'],
  [PASS[1], PASS[1] + 60, () => `${kst(PASS[1]).hm}, 위성이 다시 봤을 때 불은 이미 여기까지 와 있었습니다.`],
  [PASS[1] + 60, HORIZON, () => '불빛이 꺼진 집: 걸어서 나가기엔 이미 늦은 집입니다.'],
];
let capOn = true;
function captions() {
  const el = $('caption');
  if (!capOn) { el.classList.remove('on'); return; }
  const c = CAPS.find(([a, b]) => simT >= a && simT < b);
  if (c) { const t = c[2](); if (el.textContent !== t) el.textContent = t; el.classList.add('on'); } else el.classList.remove('on');
}

// ---------------------------------------------------------------- controls wiring
$('play').onclick = () => { playing = !playing; if (playing && simT >= HORIZON) setTime(0); $('play').textContent = playing ? '일시정지' : '재생'; };
$('restart').onclick = () => { simT = -1; setTime(0); satelliteFlash(0); };
document.querySelectorAll('[data-rate]').forEach((b) => b.onclick = () => {
  rate = Number(b.dataset.rate);
  document.querySelectorAll('[data-rate]').forEach((x) => x.classList.toggle('on', x === b));
});
document.querySelectorAll('[data-speed]').forEach((b) => b.onclick = () => applySpeed(b.dataset.speed));
document.querySelectorAll('[data-view]').forEach((b) => b.onclick = () => flyTo(VIEWS[b.dataset.view]));
$('t-roads').onchange = (e) => { roadData.lines.visible = e.target.checked; };
$('t-smoke').onchange = (e) => { smoke.visible = embers.visible = e.target.checked; };
$('t-fc').onchange = (e) => { U.uForecast.value = e.target.checked ? 1 : 0; $('fc-legend').classList.toggle('on', e.target.checked); };
$('t-cap').onchange = (e) => { capOn = e.target.checked; captions(); };
const track = $('tl-track');
let dragging = false;
const scrub = (e) => { const r = track.getBoundingClientRect(); setTime(((e.clientX - r.left) / r.width) * HORIZON); };
track.addEventListener('pointerdown', (e) => { dragging = true; track.setPointerCapture(e.pointerId); scrub(e); });
track.addEventListener('pointermove', (e) => { if (dragging) scrub(e); });
track.addEventListener('pointerup', () => { dragging = false; });
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
  if (e.key === 'ArrowRight') setTime(simT + 10);
  if (e.key === 'ArrowLeft') setTime(simT - 10);
  if (e.key === '1') applySpeed(SPEEDS[0]);
  if (e.key === '2') applySpeed(SPEEDS[1]);
  if (e.key === '3') applySpeed(SPEEDS[2]);
});
$('start').onclick = () => {
  if (window.__guideOnStart) return guided();
  $('intro').classList.add('off');
  flyTo(VIEWS.all, 4.5);
  setTimeout(() => { satelliteFlash(0); }, 3600);
  setTimeout(() => { playing = true; $('play').textContent = '일시정지'; }, 5200);
};
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});


// ---------------------------------------------------------------- guided demo (hands-free)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let guideRun = 0;
function lateCount(s, t) {
  const N = NODE[s];
  let n = 0;
  for (let i = 0; i < B.n; i++) {
    const k = bnode[i];
    if (k >= 0 && (N.lsdR[k] < 0 || t > N.lsdR[k])) n++;
  }
  return n;
}
async function waitFor(pred, run) {
  while (!pred()) { if (run !== guideRun) throw new Error('stopped'); await sleep(80); }
}
async function guided() {
  const run = ++guideRun;
  const alive = () => { if (run !== guideRun) throw new Error('stopped'); };
  try {
    $('intro').classList.add('off');
    capOn = true; $('t-cap').checked = true;
    applySpeed(SPEEDS.includes('0.7') ? '0.7' : SPEEDS[0]);
    playing = false; setTime(0);
    flyTo(VIEWS.all, 3); await sleep(3200); alive();
    satelliteFlash(0); await sleep(2200); alive();
    rate = 12; playing = true;
    flyTo(VIEWS.front, 5); await sleep(5200); alive();
    await waitFor(() => simT >= PASS[1] + 4, run);
    playing = false; await sleep(3500); alive();
    flyTo(VIEWS.coast, 4); playing = true;
    await waitFor(() => simT >= HORIZON - 1, run);
    await sleep(1500); alive();
    const slow = SPEEDS[SPEEDS.length - 1];
    if (slow !== speed && lateCount(slow, simT) > lateCount(speed, simT)) {
      const el = $('caption');
      applySpeed(slow);
      el.textContent = `같은 불, 더 느린 걸음 (${slow} m/s): 불빛이 꺼진 집이 늘어납니다.`;
      el.classList.add('on');
      capOn = false; await sleep(6000); capOn = true; alive();
    }
    flyTo(VIEWS.all, 4);
  } catch (e) { /* a click on the timeline or a button stops the tour */ }
  rate = 6;
  document.querySelectorAll('[data-rate]').forEach((x) => x.classList.toggle('on', x.dataset.rate === '6'));
}
$('guide').onclick = () => guided();
$('start-guide').onclick = () => guided();
const stopGuide = () => { guideRun++; };
['play', 'restart', 'tl-track'].forEach((id) => $(id).addEventListener('pointerdown', stopGuide));

// ---------------------------------------------------------------- loop
const tmp = new THREE.Vector3();
let last = performance.now();
function frame(now) {
  const dt = Math.min((now - last) / 1000, 0.5);
  last = now;
  U.uClock.value = now / 1000;
  if (playing) {
    const nt = simT + dt * rate;
    setTime(nt);
    if (simT >= HORIZON) { playing = false; $('play').textContent = '재생'; }
  }
  if (scanStart >= 0) {
    const p = (now - scanStart) / 1600;
    U.uScan.value = p <= 1 ? p : -1;
    if (p > 1) scanStart = -1;
  }
  if (fly) {
    const k = Math.min((now - fly.s) / fly.d, 1), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
    camera.position.lerpVectors(fly.p0, fly.p1, e);
    controls.target.lerpVectors(fly.t0, fly.t1, e);
    if (k >= 1) fly = null;
  }
  controls.update();
  for (const l of labels) {
    tmp.copy(l.v).project(camera);
    const vis = tmp.z < 1 && Math.abs(tmp.x) < 1.05 && Math.abs(tmp.y) < 1.05;
    l.el.style.display = vis ? 'block' : 'none';
    if (vis) l.el.style.transform = `translate(${(tmp.x * 0.5 + 0.5) * window.innerWidth}px, ${(-tmp.y * 0.5 + 0.5) * window.innerHeight}px) translate(-50%, -100%)`;
  }
  composer.render();
  requestAnimationFrame(frame);
}
applySpeed(speed);
setTime(0);
$('tl-start').textContent = kst(0).hm;
$('tl-end').textContent = kst(HORIZON).hm;
$('sp-note').textContent = `건물 크기 ${B_H}배 · 높이 ${B_V}배 · 지형 높이 ${VEX}배 과장 표시`;
requestAnimationFrame(frame);
window.__wfg3d = { setTime, applySpeed, flyTo, VIEWS, stateOf, get simT() { return simT; }, showCard };
