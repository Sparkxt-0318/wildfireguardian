#!/usr/bin/env node
// Route logger model for the website: replaces the FireBeetle 2 ESP32-E vendor model (DFRobot STEP, redistribution
// terms unconfirmed) with plain boxes of the same outline (PCB, RF module can, USB-C), drops the vendor geometry from
// the file, and leaves every other part and the node names as exported.
//
//   GLTF_TRANSFORM=/path/node_modules node tools/logger_standin.mjs <route_logger_assembled_web.glb> <out.glb>
import { createRequire } from 'module';
import { resolve } from 'path';
const req = createRequire(resolve(process.env.GLTF_TRANSFORM || '.', 'x.js'));
const { NodeIO } = req('@gltf-transform/core');
const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
const { prune, dedup } = req('@gltf-transform/functions');

const [src, out] = process.argv.slice(2);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(src);
const root = doc.getRoot(), buf = root.listBuffers()[0];
const fb = root.listNodes().find(n => n.getName() === 'firebeetle2_esp32e');
const bbox = name => {                     // world-space box of one vendor mesh (its node has no transform)
  const n = fb.listChildren().find(c => c.getName() === `firebeetle2_esp32e__${name}`);
  const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
  for (const p of n.getMesh().listPrimitives()) {
    const a = p.getAttribute('POSITION'), v = [];
    for (let i = 0; i < a.getCount(); i++) { a.getElement(i, v); for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], v[k]); hi[k] = Math.max(hi[k], v[k]); } }
  }
  return { lo, hi, mat: n.getMesh().listPrimitives()[0].getMaterial() };
};
const parts = { pcb: bbox('fb_pcb'), can: bbox('fb_metal'), usb: bbox('fb_usb') };
const box = (name, { lo, hi, mat }) => {
  const P = [], N = [], I = [];
  const f = (ax, s) => {                   // one face of the box, normal along axis ax with sign s
    const [u, w] = [0, 1, 2].filter(k => k !== ax), base = P.length / 3;
    for (const [a, b] of [[0, 0], [1, 0], [1, 1], [0, 1]]) {
      const p = []; p[ax] = s > 0 ? hi[ax] : lo[ax]; p[u] = a ? hi[u] : lo[u]; p[w] = b ? hi[w] : lo[w];
      P.push(...p); const n = [0, 0, 0]; n[ax] = s; N.push(...n);
    }
    const cw = (ax === 1) === (s > 0);       // keep faces pointing outward
    I.push(...(cw ? [0, 2, 1, 0, 3, 2] : [0, 1, 2, 0, 2, 3]).map(i => i + base));
  };
  for (let ax = 0; ax < 3; ax++) { f(ax, 1); f(ax, -1); }
  const acc = (arr, type, T) => doc.createAccessor().setType(type).setArray(new T(arr)).setBuffer(buf);
  const prim = doc.createPrimitive().setAttribute('POSITION', acc(P, 'VEC3', Float32Array))
    .setAttribute('NORMAL', acc(N, 'VEC3', Float32Array)).setIndices(acc(I, 'SCALAR', Uint16Array)).setMaterial(mat);
  return doc.createNode(`firebeetle2_esp32e__standin_${name}`).setMesh(doc.createMesh(`standin_${name}`).addPrimitive(prim));
};
for (const c of fb.listChildren()) { fb.removeChild(c); c.dispose(); }
for (const [k, v] of Object.entries(parts)) fb.addChild(box(k, v));
await doc.transform(prune(), dedup());
await io.write(out, doc);
console.log(Object.fromEntries(Object.entries(parts).map(([k, v]) => [k, v.lo.map((x, i) => +(v.hi[i] - x).toFixed(1))])));
