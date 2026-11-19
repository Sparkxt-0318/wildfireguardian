// 3D view of the crossing (three.js r180, vendored; bare "three" resolved by the import map in index.html).
//
// Frame: right-handed, metres. -z = straight ahead along the GNSS course, +x = right of the path, +y = up.
// Along-course distance s (State geometry/depth distances, measured from the vehicle's ground point under the
// sensor head) maps to z = -s. Ground height y(s) = road profile dz (geometry.profile, from the DEM or the IMU
// plane, relative to the vehicle's ground point), interpolated linearly and extended with the end slopes.
//
// Drawing assumptions (illustrative, stated in the legend): the road is drawn 7 m wide and the flame zone spans
// the road plus 2 m each side (the camera only sees the path bearing; lateral extent is not measured). The sensor
// head is assumed at the FRONT of the roof, so the vehicle box spans s = -length .. 0. The vehicle box is tilted
// by the road slope under it. The flame zone is a slab following the ground from the near edge: solid from
// d to d + depth (combined value), translucent from d + depth to d + depth_hi (90 % upper end); a line marks
// d + depth_lo. The first solid radar echo beyond the flame is a post at its horizontal distance on the path.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { F } from "./fields.js";
import { sv, num, fmt, fmtRange, groundAt } from "./model.js";

const ROAD_HALF_W = 3.5;
const FLAME_HALF_W = ROAD_HALF_W + 2.0;
const DEFAULT_TARGET = new THREE.Vector3(0, 1, -9);

function cssColor(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  try { return new THREE.Color(v || fallback); } catch (e) { return new THREE.Color(fallback); }
}

// Slab following the ground between s = a and s = b (a < b), half width hw, height h above the ground.
function slabGeometry(a, b, hw, h, ground) {
  const n = Math.max(1, Math.ceil((b - a) / 0.25));
  const pos = [];
  const idx = [];
  for (let i = 0; i <= n; i++) {
    const s = a + (b - a) * (i / n);
    const y0 = ground(s);
    const z = -s;
    pos.push(-hw, y0, z, hw, y0, z, hw, y0 + h, z, -hw, y0 + h, z);   // LB, RB, RT, LT
  }
  for (let i = 0; i < n; i++) {
    const p = 4 * i, q = 4 * (i + 1);
    for (let k = 0; k < 4; k++) {
      const k2 = (k + 1) % 4;
      idx.push(p + k, q + k, q + k2, p + k, q + k2, p + k2);
    }
  }
  const last = 4 * n;
  idx.push(0, 3, 2, 0, 2, 1);                                      // near face
  idx.push(last, last + 1, last + 2, last, last + 2, last + 3);    // far face
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

// Ribbon on the ground between s = a and b, half width hw, lifted by dy.
function ribbonGeometry(a, b, hw, ground, dy, step) {
  const n = Math.max(1, Math.ceil((b - a) / (step || 0.5)));
  const pos = [];
  const idx = [];
  for (let i = 0; i <= n; i++) {
    const s = a + (b - a) * (i / n);
    const y = ground(s) + dy;
    pos.push(-hw, y, -s, hw, y, -s);
  }
  for (let i = 0; i < n; i++) {
    const p = 2 * i;
    idx.push(p, p + 1, p + 3, p, p + 3, p + 2);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

export function createScene(container, labelLayer) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const col = {
    bg: cssColor("--scene-bg", "#dfe6ee"), ground: cssColor("--scene-ground", "#b7c2a5"), road: cssColor("--scene-road", "#59606b"),
    line: cssColor("--scene-road-line", "#f2f2f2"), vehicle: cssColor("--scene-vehicle", "#c62828"), sensor: cssColor("--scene-sensor", "#1d2633"),
    flame: cssColor("--scene-flame", "#ff6a00"), flameInt: cssColor("--scene-flame-int", "#ffb347"), front: cssColor("--scene-flame-front", "#ffd23f"),
    near: cssColor("--scene-near", "#ffe066"), echo: cssColor("--scene-echo", "#00a3c4"), tick: cssColor("--scene-tick", "#ffffff"),
  };
  scene.background = col.bg;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x445544, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(20, 40, 10);
  scene.add(sun);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 2000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.maxPolarAngle = Math.PI * 0.495;

  // dynamic groups, rebuilt on each update (a few hundred vertices; cheap at 5 Hz)
  const world = new THREE.Group();
  scene.add(world);
  let labels = [];       // {pos: Vector3, node: HTMLElement}
  let dirty = true;
  let lastKey = "";
  let alive = true;
  let curL = 8;

  function resetView(vehLen) {
    const L = num(vehLen) || 8;
    camera.position.set(9, 9, L + 10);
    controls.target.copy(DEFAULT_TARGET);
    controls.update();
    dirty = true;
  }
  resetView(8);
  controls.addEventListener("change", () => { dirty = true; });

  function clearWorld() {
    world.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
    });
    world.clear();
    for (const l of labels) l.node.remove();
    labels = [];
  }

  function label(text, x, y, z, cls) {
    const node = document.createElement("div");
    node.className = "lbl" + (cls ? " " + cls : "");
    node.textContent = text;
    labelLayer.appendChild(node);
    labels.push({ pos: new THREE.Vector3(x, y, z), node });
  }

  function mat(color, opacity, extra) {
    return new THREE.MeshLambertMaterial(Object.assign({ color, transparent: opacity < 1, opacity,
      side: THREE.DoubleSide, depthWrite: opacity >= 1 }, extra || {}));
  }

  function update(state) {
    const s = state || {};
    const ps = sv(s, F.profileS), pdz = sv(s, F.profileDz);
    const profOk = sv(s, F.profileValid) === true && Array.isArray(ps) && ps.length >= 2;
    const ground = (x) => (profOk ? groundAt(ps, pdz, x) : 0);
    const L = num(sv(s, F.vehLength)), W = num(sv(s, F.vehWidth)), H = num(sv(s, F.vehHeight));
    const d = num(sv(s, F.nearEdge)), dLo = num(sv(s, F.nearEdgeLo)), dHi = num(sv(s, F.nearEdgeHi));
    const fh = num(sv(s, F.flameHeight));
    const depthOk = sv(s, F.depthValid) === true;
    const D = depthOk ? num(sv(s, F.depthM)) : null, Dlo = depthOk ? num(sv(s, F.depthLo)) : null, Dhi = depthOk ? num(sv(s, F.depthHi)) : null;
    const echo = num(sv(s, F.farEcho));
    const camH = num(sv(s, F.cameraHeight));
    const key = JSON.stringify([profOk ? ps : null, profOk ? pdz : null, L, W, H, d, dLo, dHi, fh, D, Dlo, Dhi, echo, camH,
      sv(s, F.vehLabel), sv(s, F.occluded), sv(s, F.slopeSource)]);
    if (key === lastKey) return;
    lastKey = key;
    if (L !== null) curL = L;
    clearWorld();

    const far = Math.max(35, (d || 0) + (Dhi || Dlo || D || 0) + 8, (echo || 0) + 6, profOk ? Math.min(80, ps[ps.length - 1]) : 0);
    const near = -((L || 8) + 8);

    // terrain and road
    world.add(new THREE.Mesh(ribbonGeometry(near - 10, far + 20, 40, ground, -0.04, 1.0), mat(col.ground, 1)));
    world.add(new THREE.Mesh(ribbonGeometry(near, far, ROAD_HALF_W, ground, 0, 0.5), mat(col.road, 1)));
    const cl = [];
    for (let x = Math.ceil(near); x < far; x += 3) cl.push(new THREE.Vector3(0, ground(x) + 0.02, -x), new THREE.Vector3(0, ground(x + 1.5) + 0.02, -(x + 1.5)));
    world.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(cl), new THREE.LineBasicMaterial({ color: col.line })));
    // distance ticks every 5 m along the road edge
    const tk = [];
    for (let x = 5; x <= far; x += (x < 30 ? 5 : 10)) {
      const y = ground(x) + 0.03;
      tk.push(new THREE.Vector3(ROAD_HALF_W - 0.8, y, -x), new THREE.Vector3(ROAD_HALF_W + 0.3, y, -x));
      label(x + " m", ROAD_HALF_W + 0.6, y + 0.1, -x, "tick");
    }
    world.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(tk), new THREE.LineBasicMaterial({ color: col.tick })));

    // vehicle box to scale, behind the sensor head (s = -L .. 0), tilted with the road under it
    if (L !== null && W !== null && H !== null) {
      const sc = -L / 2;
      const slope = Math.atan2(ground(0) - ground(-L), L);
      const box = new THREE.Mesh(new THREE.BoxGeometry(W, H, L), mat(col.vehicle, 1));
      box.rotation.x = slope;
      box.position.set(0, ground(sc) + (H / 2) / Math.cos(slope), -sc);
      world.add(box);
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(box.geometry), new THREE.LineBasicMaterial({ color: col.sensor }));
      edges.rotation.copy(box.rotation);
      edges.position.copy(box.position);
      world.add(edges);
      const hs = camH !== null ? camH : H + 0.1;
      const head = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.25, 0.35), mat(col.sensor, 1));
      head.position.set(0, ground(0) + hs, 0.2);
      world.add(head);
      label((sv(s, F.vehLabel) || "vehicle") + " " + L.toFixed(1) + "×" + W.toFixed(1) + "×" + H.toFixed(1) + " m",
        0, ground(sc) + H + 0.6, -sc);
    }

    if (d !== null) {
      // near-edge interval band on the road
      const a = dLo !== null ? dLo : d, b = dHi !== null ? dHi : far;
      if (b > a) world.add(new THREE.Mesh(ribbonGeometry(a, b, ROAD_HALF_W, ground, 0.03, 0.25), mat(col.near, 0.55)));
      const h = fh !== null && fh > 0 ? fh : 0.3;
      // flame front wall at the near edge
      const wall = new THREE.Mesh(new THREE.PlaneGeometry(2 * FLAME_HALF_W, h), mat(col.front, 0.9, { emissive: col.front, emissiveIntensity: 0.5 }));
      wall.position.set(0, ground(d) + h / 2, -d + 0.01);
      world.add(wall);
      label("near edge " + fmt(d, 1, "m") + (dLo !== null || dHi !== null ? " [" + fmtRange(dLo, dHi, 1) + "]" : "") +
        (sv(s, F.occluded) === true ? " hidden by crest" : ""), -FLAME_HALF_W, ground(d) + 0.2, -d);
      if (fh !== null) {
        const x = FLAME_HALF_W + 0.3;
        const ln = [new THREE.Vector3(x, ground(d), -d), new THREE.Vector3(x, ground(d) + fh, -d)];
        world.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ln), new THREE.LineBasicMaterial({ color: col.sensor })));
        label("flame height " + fmt(fh, 2, "m") + " [" + fmtRange(sv(s, F.flameHeightLo), sv(s, F.flameHeightHi), 2) + "]", x, ground(d) + fh + 0.3, -d);
      }
      // depth: combined value solid, 90 % interval translucent
      if (D !== null && D > 0) {
        world.add(new THREE.Mesh(slabGeometry(d, d + D, FLAME_HALF_W, h, ground), mat(col.flame, 0.92, { emissive: col.flame, emissiveIntensity: 0.25 })));
        if (Dhi !== null && Dhi > D) world.add(new THREE.Mesh(slabGeometry(d + D, d + Dhi, FLAME_HALF_W, h, ground), mat(col.flameInt, 0.3)));
        if (Dlo !== null && Dlo < D) {
          const y = ground(d + Dlo) + 0.05;
          const ln = [new THREE.Vector3(-FLAME_HALF_W, y, -(d + Dlo)), new THREE.Vector3(FLAME_HALF_W, y, -(d + Dlo))];
          world.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ln), new THREE.LineBasicMaterial({ color: col.sensor })));
        }
        label("depth " + fmt(D, 2, "m") + " (90 %: " + fmtRange(Dlo, Dhi, 2) + ")", -FLAME_HALF_W * 0.5, ground(d + D / 2) + h + 0.5, -(d + D / 2));
      } else {
        label("depth unknown", 0, ground(d) + h + 0.5, -d);
      }
    } else {
      label("no flame base on the path", 0, ground(12) + 0.5, -12);
    }

    // first solid echo beyond the flame
    if (echo !== null) {
      // marker only: the post height is drawn to stand above the flame, it is not a measured height
      const ph = Math.max(2.2, (fh || 0) + 1.0);
      const post = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, ph, 12), mat(col.echo, 1));
      post.position.set(0, ground(echo) + ph / 2, -echo);
      world.add(post);
      const cap = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 12), mat(col.echo, 1));
      cap.position.set(0, ground(echo) + ph + 0.1, -echo);
      world.add(cap);
      label("first solid echo " + fmt(echo, 1, "m"), 0, ground(echo) + ph + 0.6, -echo);
    }
    if (!profOk) label("no road profile: drawn flat", 0, 0.2, 3);
    dirty = true;
  }

  const v = new THREE.Vector3();
  function placeLabels(w, h) {
    for (const l of labels) {
      v.copy(l.pos).project(camera);
      const vis = v.z < 1 && v.x > -1.1 && v.x < 1.1 && v.y > -1.1 && v.y < 1.1;
      l.node.style.display = vis ? "" : "none";
      if (vis) {
        l.node.style.left = ((v.x + 1) / 2 * w).toFixed(0) + "px";
        l.node.style.top = ((1 - v.y) / 2 * h).toFixed(0) + "px";
      }
    }
  }

  function resize() {
    const w = Math.max(1, container.clientWidth), h = Math.max(1, container.clientHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    dirty = true;
  }
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
  if (ro) ro.observe(container); else window.addEventListener("resize", resize);
  resize();

  function frame() {
    if (!alive) return;
    if (dirty) {
      dirty = false;
      renderer.render(scene, camera);
      placeLabels(container.clientWidth, container.clientHeight);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  return {
    update,
    resetView: () => resetView(curL),
    dispose() { alive = false; if (ro) ro.disconnect(); clearWorld(); renderer.dispose(); renderer.domElement.remove(); },
    info: () => ({ objects: world.children.length, labels: labels.length, renderer: "WebGL" }),
  };
}
