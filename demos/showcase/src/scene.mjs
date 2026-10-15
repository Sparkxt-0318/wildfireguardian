import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { heightAt, pointAlong } from './data.mjs';
import { createDevice } from './device.mjs';

// One shared height field is used for the land, roads, vegetation and markers.
// All motion is an illustrative fixture, driven by the transport's time.
const clamp = THREE.MathUtils.clamp;
const lerp = THREE.MathUtils.lerp;
const CYAN = 0x91e5d5;
const MINT = 0xc8f7b3;
const WARM = 0xffa252;
const deviceAnchor = [-40, 23];

function seeded(seed = 1257) {
  let a = seed >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function inIsland(x, z, inset = 0) {
  const qx = Math.max(Math.abs(x) - (58 - inset), 0);
  const qz = Math.max(Math.abs(z) - (40 - inset), 0);
  return qx * qx + qz * qz <= 144;
}

function mappedPoint(u, v) {
  const z = v * 52;
  const corner = Math.max(Math.abs(z) - 40, 0);
  const maxX = 58 + Math.sqrt(Math.max(0, 144 - corner * corner));
  const x = u * maxX;
  return [x, heightAt(x, z), z];
}

function distanceToPath(x, z, points) {
  let best = Infinity;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    const dx = b[0] - a[0], dz = b[1] - a[1];
    const s = clamp(((x - a[0]) * dx + (z - a[1]) * dz) / (dx * dx + dz * dz || 1), 0, 1);
    best = Math.min(best, Math.hypot(x - a[0] - dx * s, z - a[1] - dz * s));
  }
  return best;
}

function drapedPoints(points, spacing = .65, offset = .25) {
  const output = [];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    const n = Math.max(1, Math.ceil(Math.hypot(a[0] - b[0], a[1] - b[1]) / spacing));
    for (let j = 0; j < n; j++) {
      const t = j / n, x = lerp(a[0], b[0], t), z = lerp(a[1], b[1], t);
      output.push(new THREE.Vector3(x, heightAt(x, z) + offset, z));
    }
  }
  if (points.length) {
    const [x, z] = points[points.length - 1];
    output.push(new THREE.Vector3(x, heightAt(x, z) + offset, z));
  }
  return output;
}

function ribbon(points, width, color, opacity = 1, offset = .3) {
  const path = drapedPoints(points, .5, offset);
  const positions = [], indices = [];
  for (let i = 0; i < path.length; i++) {
    const a = path[Math.max(0, i - 1)], b = path[Math.min(path.length - 1, i + 1)];
    const dx = b.x - a.x, dz = b.z - a.z, length = Math.hypot(dx, dz) || 1;
    for (const sign of [-1, 1]) {
      const x = path[i].x + dz / length * width * .5 * sign;
      const z = path[i].z - dx / length * width * .5 * sign;
      positions.push(x, heightAt(x, z) + offset, z);
    }
    if (i < path.length - 1) indices.push(2 * i, 2 * i + 2, 2 * i + 1, 2 * i + 1, 2 * i + 2, 2 * i + 3);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const material = new THREE.MeshBasicMaterial({color, opacity, transparent: opacity < 1, side: THREE.DoubleSide, depthWrite: opacity === 1, toneMapped: false});
  const mesh = new THREE.Mesh(geometry, material);
  mesh.renderOrder = opacity < 1 ? 2 : 1;
  return mesh;
}

function pathLine(points, color, opacity, offset = .5, dashed = false) {
  const geometry = new THREE.BufferGeometry().setFromPoints(drapedPoints(points, .5, offset));
  const material = dashed
    ? new THREE.LineDashedMaterial({color, opacity, transparent: true, dashSize: 1.1, gapSize: .65, toneMapped: false})
    : new THREE.LineBasicMaterial({color, opacity, transparent: true, toneMapped: false});
  const line = new THREE.Line(geometry, material);
  if (dashed) line.computeLineDistances();
  return line;
}

function terrain(data) {
  const group = new THREE.Group();
  const nx = 144, nz = 112;
  const vertices = [], indices = [], colors = [], points = [];
  const low = new THREE.Color('#152c2a'), middle = new THREE.Color('#253d37'), high = new THREE.Color('#474d42');
  const color = new THREE.Color();
  for (let j = 0; j <= nz; j++) {
    for (let i = 0; i <= nx; i++) {
      const p = mappedPoint(i / nx * 2 - 1, j / nz * 2 - 1);
      points.push(p);
      vertices.push(...p);
      const h = clamp(p[1] / 27, 0, 1);
      color.copy(h < .55 ? low : middle).lerp(h < .55 ? middle : high, h < .55 ? h / .55 : (h - .55) / .45);
      const variation = Math.sin(p[0] * .48 + p[2] * .18) * Math.cos(p[2] * .34) * .035;
      color.offsetHSL(variation * .1, variation, variation);
      colors.push(color.r, color.g, color.b);
      if (i < nx && j < nz) {
        const a = j * (nx + 1) + i;
        indices.push(a, a + nx + 1, a + 1, a + 1, a + nx + 1, a + nx + 2);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const land = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({vertexColors: true, roughness: .97, metalness: .02}));
  land.receiveShadow = true;
  group.add(land);

  const perimeter = [];
  for (let i = 0; i <= nx; i++) perimeter.push(points[i]);
  for (let j = 1; j <= nz; j++) perimeter.push(points[j * (nx + 1) + nx]);
  for (let i = nx - 1; i >= 0; i--) perimeter.push(points[nz * (nx + 1) + i]);
  for (let j = nz - 1; j > 0; j--) perimeter.push(points[j * (nx + 1)]);
  const sidePos = [], sideColors = [], sideIndices = [];
  const topColor = new THREE.Color('#223830'), bottomColor = new THREE.Color('#0a1916');
  for (let i = 0; i <= perimeter.length; i++) {
    const p = perimeter[i % perimeter.length];
    sidePos.push(...p, p[0], -6, p[2]);
    sideColors.push(topColor.r, topColor.g, topColor.b, bottomColor.r, bottomColor.g, bottomColor.b);
    if (i < perimeter.length) sideIndices.push(i * 2, i * 2 + 1, i * 2 + 2, i * 2 + 1, i * 2 + 3, i * 2 + 2);
  }
  const sideGeometry = new THREE.BufferGeometry();
  sideGeometry.setAttribute('position', new THREE.Float32BufferAttribute(sidePos, 3));
  sideGeometry.setAttribute('color', new THREE.Float32BufferAttribute(sideColors, 3));
  sideGeometry.setIndex(sideIndices);
  sideGeometry.computeVertexNormals();
  const sides = new THREE.Mesh(sideGeometry, new THREE.MeshStandardMaterial({vertexColors: true, roughness: .9, side: THREE.DoubleSide}));
  sides.castShadow = true;
  group.add(sides);
  // A quiet section line makes the geographic cutaway legible.
  for (const level of [-5.7, -4.85]) {
    const linePoints = perimeter.map(p => new THREE.Vector3(p[0] * 1.001, level, p[2] * 1.001));
    linePoints.push(linePoints[0]);
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(linePoints), new THREE.LineBasicMaterial({color: 0x5c8775, transparent: true, opacity: level < -5 ? .22 : .065})));
  }

  // Marching squares follows this exact vertex grid, including the rounded corners.
  const fine = [], major = [];
  const cross = (a, b, h) => {
    if ((a[1] < h) === (b[1] < h)) return null;
    const t = (h - a[1]) / (b[1] - a[1]);
    return [lerp(a[0], b[0], t), h + .10, lerp(a[2], b[2], t)];
  };
  for (let level = 1; level <= 28; level++) {
    const h = level * 1.05, target = level % 4 === 0 ? major : fine;
    for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
      const a = j * (nx + 1) + i;
      const cell = [points[a], points[a + 1], points[a + nx + 2], points[a + nx + 1]];
      const crosses = [];
      for (let k = 0; k < 4; k++) {
        const point = cross(cell[k], cell[(k + 1) % 4], h);
        if (point) crosses.push(point);
      }
      for (let k = 1; k < crosses.length; k += 2) target.push(...crosses[k - 1], ...crosses[k]);
    }
  }
  for (const [positions, opacity] of [[fine, .10], [major, .23]]) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    group.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({color: 0xb4c8a8, transparent: true, opacity, depthWrite: false})));
  }
  return group;
}

function forest(data) {
  const group = new THREE.Group();
  const random = seeded(750319);
  const samples = [];
  const roads = data.roads.map(r => r.points);
  for (let z = -47; z <= 47; z += 2.5) for (let x = -65; x <= 65; x += 2.5) {
    const px = x + (random() - .5) * 2.15, pz = z + (random() - .5) * 2.15;
    const h = heightAt(px, pz);
    const fireDistance = Math.hypot(px - data.fire.center[0], pz - data.fire.center[1]);
    const roadDistance = Math.min(...roads.map(points => distanceToPath(px, pz, points)));
    if (!inIsland(px, pz, 2) || h < 2.4 || roadDistance < 2.2 || fireDistance < data.fire.radius * 1.02 || Math.hypot(px - deviceAnchor[0], pz - deviceAnchor[1]) < 7 || random() < .38) continue;
    const density = Math.sin(px * .085 + pz * .062) * .5 + .5;
    if (random() < density * .52) continue;
    samples.push({x: px, z: pz, h, size: .5 + random() * .69, rotation: random() * Math.PI, tone: random()});
  }
  // Stable shuffle keeps the reduced vegetation count spatially balanced.
  for (let i = samples.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [samples[i], samples[j]] = [samples[j], samples[i]];
  }
  const trunkGeo = new THREE.CylinderGeometry(.08, .15, 1.25, 4);
  const crownGeo = new THREE.IcosahedronGeometry(1, 1);
  const trunk = new THREE.InstancedMesh(trunkGeo, new THREE.MeshStandardMaterial({color: 0x453e2d, roughness: 1}), samples.length);
  const crowns = new THREE.InstancedMesh(crownGeo, new THREE.MeshStandardMaterial({color: 0xffffff, roughness: 1, flatShading: true}), samples.length * 2);
  const dummy = new THREE.Object3D(), color = new THREE.Color();
  samples.forEach((tree, i) => {
    dummy.rotation.set(0, tree.rotation, 0);
    dummy.position.set(tree.x, tree.h + tree.size * .6, tree.z);
    dummy.scale.set(tree.size, tree.size, tree.size);
    dummy.updateMatrix();
    trunk.setMatrixAt(i, dummy.matrix);
    for (let layer = 0; layer < 2; layer++) {
      dummy.position.set(tree.x + (layer ? .36 : -.16) * tree.size, tree.h + tree.size * (1.25 + layer * .56), tree.z + (layer ? -.25 : .1) * tree.size);
      dummy.scale.set(tree.size * (1.1 - layer * .22), tree.size * (1.07 - layer * .16), tree.size * (.95 - layer * .1));
      dummy.updateMatrix();
      crowns.setMatrixAt(i * 2 + layer, dummy.matrix);
      color.setHSL(.37 + tree.tone * .042, .15 + tree.tone * .16, .073 + tree.tone * .065 + layer * .01);
      crowns.setColorAt(i * 2 + layer, color);
    }
  });
  crowns.castShadow = true;
  crowns.receiveShadow = true;
  group.add(trunk, crowns);
  group.userData.treeCount = samples.length;
  group.userData.setLowEffects = value => {
    trunk.count = value ? Math.ceil(samples.length * .58) : samples.length;
    crowns.count = trunk.count * 2;
  };
  return group;
}

function radialTexture(kind) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
  if (kind === 'smoke') {
    gradient.addColorStop(0, 'rgba(185,192,181,.85)');
    gradient.addColorStop(.36, 'rgba(146,159,150,.55)');
    gradient.addColorStop(.7, 'rgba(123,142,133,.23)');
    gradient.addColorStop(1, 'rgba(105,122,116,0)');
  } else {
    gradient.addColorStop(0, 'rgba(255,235,170,.8)');
    gradient.addColorStop(.2, 'rgba(255,146,44,.38)');
    gradient.addColorStop(.5, 'rgba(236,91,23,.10)');
    gradient.addColorStop(1, 'rgba(226,74,12,0)');
  }
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeBurnFootprint(radius) {
  const sectors = 96, rings = 5;
  const coordinates = [[0, 0]], alpha = [.89], indices = [];
  for (let ring = 1; ring <= rings; ring++) {
    const r = ring / rings;
    for (let i = 0; i < sectors; i++) {
      const angle = i / sectors * Math.PI * 2;
      const irregular = 1 + .087 * Math.sin(angle * 3 + .7) + .048 * Math.sin(angle * 7 - .4);
      coordinates.push([Math.cos(angle) * r * radius * irregular, Math.sin(angle) * r * radius * irregular]);
      alpha.push(.86 * (1 - THREE.MathUtils.smoothstep(r, .62, 1)));
      if (ring === 1) indices.push(0, 1 + (i + 1) % sectors, 1 + i);
      else {
        const a = 1 + (ring - 2) * sectors + i, b = 1 + (ring - 2) * sectors + (i + 1) % sectors;
        const c = a + sectors, d = b + sectors;
        indices.push(a, b, c, b, d, c);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(coordinates.length * 3), 3).setUsage(THREE.DynamicDrawUsage));
  geometry.setAttribute('aFade', new THREE.Float32BufferAttribute(alpha, 1));
  geometry.setIndex(indices);
  const material = new THREE.ShaderMaterial({
    vertexShader: 'attribute float aFade; varying float vFade; void main(){vFade=aFade;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader: 'varying float vFade; void main(){gl_FragColor=vec4(.019,.025,.022,vFade);}',
    transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false,
  });
  const patch = new THREE.Mesh(geometry, material);
  patch.frustumCulled = false;
  patch.renderOrder = -1;
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array((sectors + 1) * 3), 3).setUsage(THREE.DynamicDrawUsage));
  const edge = new THREE.Line(edgeGeometry, new THREE.LineBasicMaterial({color: 0xd28d51, transparent: true, opacity: .25, depthWrite: false, toneMapped: false}));
  edge.frustumCulled = false;
  const group = new THREE.Group(); group.add(patch, edge);
  return {group, update(cx, cz, scale) {
    const positions = geometry.attributes.position;
    coordinates.forEach(([x, z], i) => {
      const px = cx + x * scale, pz = cz + z * scale;
      positions.setXYZ(i, px, heightAt(px, pz) + .13, pz);
    });
    positions.needsUpdate = true;
    const boundary = edgeGeometry.attributes.position;
    for (let i = 0; i <= sectors; i++) {
      const source = 1 + (rings - 1) * sectors + i % sectors;
      const x = positions.getX(source), z = positions.getZ(source);
      boundary.setXYZ(i, x, heightAt(x, z) + .28, z);
    }
    boundary.needsUpdate = true;
  }};
}

function makeFire(data) {
  const group = new THREE.Group();
  const random = seeded(4409);
  const center = data.fire.center, radius = data.fire.radius;
  if (!(radius > 0)) return {group, update() {}};
  const hot = [], seeds = [], sizes = [], colors = [];
  const flameColor = new THREE.Color();
  // Small separate clusters give the fire a footprint instead of one giant cone.
  const clusters = [];
  for (let i = 0; i < 9; i++) {
    const theta = i * 2.39996;
    const r = radius * (.17 + .5 * Math.sqrt(i / 8));
    clusters.push([center[0] + Math.cos(theta) * r, center[1] + Math.sin(theta) * r]);
  }
  for (let i = 0; i < 270; i++) {
    const c = clusters[i % clusters.length];
    const x = c[0] + (random() - .5) * radius * .33;
    const z = c[1] + (random() - .5) * radius * .33;
    hot.push(x, heightAt(x, z) + .55, z);
    seeds.push(random(), random(), random());
    sizes.push(2.4 + random() * 4.4);
    flameColor.setRGB(1, .22 + random() * .48, .025 + random() * .1);
    colors.push(flameColor.r, flameColor.g, flameColor.b);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(hot, 3));
  geometry.setAttribute('aSeed', new THREE.Float32BufferAttribute(seeds, 3));
  geometry.setAttribute('aSize', new THREE.Float32BufferAttribute(sizes, 1));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  const material = new THREE.ShaderMaterial({
    uniforms: {uTime: {value: 0}, uPixelRatio: {value: 1}, uGrowth: {value: 1}},
    vertexShader: `
      attribute vec3 aSeed;
      attribute float aSize;
      attribute vec3 color;
      uniform float uTime;
      uniform float uPixelRatio;
      uniform float uGrowth;
      varying vec3 vColor;
      varying float vLife;
      void main(){
        float phase=fract(aSeed.x + uTime*(0.20+aSeed.y*0.17));
        vec3 p=position;
        p.x+=sin(phase*6.2831+aSeed.z*14.)*.6*phase;
        p.z+=phase*phase*.8;
        p.y+=phase*(2.3+aSeed.y*5.2)*uGrowth;
        vec4 mv=modelViewMatrix*vec4(p,1.);
        gl_Position=projectionMatrix*mv;
        gl_PointSize=clamp(aSize*(1.-phase*.64)*uPixelRatio*310./max(1.,-mv.z),1.,60.);
        vColor=color;
        vLife=sin(phase*3.14159)*.75+.18;
      }`,
    fragmentShader: `
      varying vec3 vColor;
      varying float vLife;
      void main(){
        vec2 p=gl_PointCoord*2.-1.;
        float d=length(p*vec2(1.,.82));
        float alpha=pow(max(0.,1.-d),1.9)*vLife;
        if(alpha<.015) discard;
        vec3 color=mix(vColor,vec3(1.,.86,.45),pow(max(0.,1.-d),4.)*.7);
        gl_FragColor=vec4(color,alpha);
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
  });
  const flames = new THREE.Points(geometry, material);
  flames.frustumCulled = false;
  group.add(flames);
  const glowTexture = radialTexture('glow');
  const glows = [];
  clusters.forEach((c, i) => {
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({map: glowTexture, color: 0xff861f, transparent: true, opacity: .6, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false}));
    glow.position.set(c[0], heightAt(...c) + 1.2, c[1]);
    glow.scale.set(9 + i % 3, 6 + i % 3, 1);
    glows.push({sprite: glow, center: c});
    group.add(glow);
  });
  const flameCanvas = document.createElement('canvas');
  flameCanvas.width = 128; flameCanvas.height = 256;
  const flameCtx = flameCanvas.getContext('2d');
  const flameGradient = flameCtx.createLinearGradient(0, 256, 0, 0);
  flameGradient.addColorStop(0, 'rgba(255,201,73,.3)');
  flameGradient.addColorStop(.15, 'rgba(255,223,118,.97)');
  flameGradient.addColorStop(.48, 'rgba(255,139,37,.88)');
  flameGradient.addColorStop(.85, 'rgba(234,70,17,.5)');
  flameGradient.addColorStop(1, 'rgba(205,44,9,0)');
  flameCtx.fillStyle = flameGradient;
  flameCtx.shadowBlur = 9; flameCtx.shadowColor = 'rgba(255,117,23,.7)';
  flameCtx.beginPath();
  flameCtx.moveTo(62, 252);
  flameCtx.bezierCurveTo(4, 242, 14, 183, 39, 144);
  flameCtx.bezierCurveTo(58, 114, 79, 80, 68, 7);
  flameCtx.bezierCurveTo(109, 57, 67, 126, 94, 163);
  flameCtx.bezierCurveTo(127, 208, 111, 253, 62, 252);
  flameCtx.fill();
  const flameTexture = new THREE.CanvasTexture(flameCanvas);
  flameTexture.colorSpace = THREE.SRGBColorSpace;
  const tongues = [];
  for (let i = 0; i < 26; i++) {
    const c = clusters[i % clusters.length];
    const x = c[0] + (random() - .5) * 3.7, z = c[1] + (random() - .5) * 3.7;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map: flameTexture, transparent: true, opacity: .82, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false}));
    sprite.center.set(.5, .05);
    sprite.position.set(x, heightAt(x, z) + .2, z);
    const phase = random() * Math.PI * 2, size = 3.5 + random() * 3.8;
    sprite.scale.set(size * .45, size, 1);
    tongues.push({sprite, size, phase, center: [x, z]});
    group.add(sprite);
  }
  const smokeTexture = radialTexture('smoke');
  const smoke = [];
  for (let i = 0; i < 38; i++) {
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map: smokeTexture, color: i % 3 ? 0x8f9185 : 0xb0aa98, transparent: true, opacity: .2, depthWrite: false}));
    const c = clusters[i % clusters.length];
    smoke.push({sprite, center: c, phase: random(), speed: .025 + random() * .023, size: 6 + random() * 4, drift: .7 + random()});
    group.add(sprite);
  }
  const emberPositions = [], emberSeeds = [], emberSize = [], emberColors = [];
  for (let i = 0; i < 65; i++) {
    const c = clusters[i % clusters.length];
    emberPositions.push(c[0], heightAt(...c) + 2, c[1]);
    emberSeeds.push(random(), random(), random());
    emberSize.push(.18 + random() * .3);
    emberColors.push(1, .46 + random() * .35, .07);
  }
  const emberGeo = new THREE.BufferGeometry();
  emberGeo.setAttribute('position', new THREE.Float32BufferAttribute(emberPositions, 3));
  emberGeo.setAttribute('aSeed', new THREE.Float32BufferAttribute(emberSeeds, 3));
  emberGeo.setAttribute('aSize', new THREE.Float32BufferAttribute(emberSize, 1));
  emberGeo.setAttribute('color', new THREE.Float32BufferAttribute(emberColors, 3));
  const emberMat = material.clone();
  emberMat.uniforms.uGrowth.value = 3.4;
  const embers = new THREE.Points(emberGeo, emberMat);
  embers.frustumCulled = false;
  group.add(embers);
  const footprint = makeBurnFootprint(radius);
  group.add(footprint.group);
  const light = new THREE.PointLight(0xff842a, 80, radius * 3, 1.8);
  light.position.set(center[0], heightAt(...center) + 5, center[1]);
  group.add(light);
  let burnX = center[0], burnZ = center[1], burnScale = .84, lastFootprintTime = null;
  const shifted = ([x, z]) => [burnX + (x - center[0]) * burnScale, burnZ + (z - center[1]) * burnScale];
  // Bounded choreography only: this is not an ignition, spread or fuel model.
  const evolveFootprint = time => {
    const phase = clamp(time / 108, 0, 1);
    burnScale = .84 + .23 * phase;
    burnX = center[0] + 2.5 * phase;
    burnZ = center[1] - 1.3 * phase;
    footprint.update(burnX, burnZ, burnScale);
    for (const [geo, original, offset] of [[geometry, hot, .55], [emberGeo, emberPositions, 2]]) {
      const positions = geo.attributes.position;
      for (let i = 0; i < positions.count; i++) {
        const [x, z] = shifted([original[i * 3], original[i * 3 + 2]]);
        positions.setXYZ(i, x, heightAt(x, z) + offset, z);
      }
      positions.needsUpdate = true;
    }
    for (const f of [...glows, ...tongues]) {
      const [x, z] = shifted(f.center);
      f.sprite.position.set(x, heightAt(x, z) + (f.size ? .2 : 1.2), z);
    }
    light.position.set(burnX, heightAt(burnX, burnZ) + 5, burnZ);
  };
  return {group, getCenter: () => [burnX, burnZ], getFootprint: () => ({center: [burnX, burnZ], scale: burnScale, radius: radius * burnScale, scripted: true}), update(time, lowEffects, ratio) {
    if (time !== lastFootprintTime) { evolveFootprint(time); lastFootprintTime = time; }
    material.uniforms.uTime.value = time;
    material.uniforms.uPixelRatio.value = ratio;
    material.uniforms.uGrowth.value = .9 + .13 * Math.sin(time * .032);
    emberMat.uniforms.uTime.value = time;
    emberMat.uniforms.uPixelRatio.value = ratio;
    embers.visible = !lowEffects;
    tongues.forEach((f, i) => {
      f.sprite.visible = !lowEffects || i % 2 === 0;
      const flicker = 1 + Math.sin(time * (2.6 + i * .027) + f.phase) * .15;
      f.sprite.scale.set(f.size * .46 / flicker, f.size * flicker, 1);
      f.sprite.material.rotation = Math.sin(time * 1.4 + f.phase) * .08;
    });
    smoke.forEach((s, i) => {
      s.sprite.visible = !lowEffects || i % 3 === 0;
      const phase = (s.phase + time * s.speed) % 1;
      const rise = phase * 25;
      const [sourceX, sourceZ] = shifted(s.center);
      s.sprite.position.set(sourceX + phase * phase * 14 * s.drift, heightAt(sourceX, sourceZ) + 3 + rise, sourceZ + phase * 4);
      const size = s.size * (.45 + phase * 1.2);
      s.sprite.scale.set(size * 1.1, size, 1);
      s.sprite.material.opacity = Math.sin(phase * Math.PI) * .5;
      s.sprite.material.rotation = s.phase * 6 + phase * .3;
    });
    light.intensity = 70 + Math.sin(time * 3.7) * 8 + Math.sin(time * 7.9) * 4;
  }};
}

function markerAt(point, color, kind = 'point') {
  const group = new THREE.Group();
  const [x, z] = point;
  group.position.set(x, heightAt(x, z) + .65, z);
  const poleHeight = kind === 'destination' ? 6.7 : 3.3;
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(.045, .045, poleHeight, 6), new THREE.MeshBasicMaterial({color, transparent: true, opacity: .5, toneMapped: false}));
  stem.position.y = poleHeight * .5;
  group.add(stem);
  const dot = new THREE.Mesh(new THREE.SphereGeometry(kind === 'destination' ? .38 : .25, 12, 8), new THREE.MeshBasicMaterial({color, toneMapped: false}));
  dot.position.y = poleHeight;
  group.add(dot);
  const ring = new THREE.Mesh(new THREE.RingGeometry(.65, .85, 40), new THREE.MeshBasicMaterial({color, side: THREE.DoubleSide, transparent: true, opacity: .95, toneMapped: false}));
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = .07;
  group.add(ring);
  const halo = new THREE.Mesh(new THREE.RingGeometry(1.3, 1.36, 56), new THREE.MeshBasicMaterial({color, side: THREE.DoubleSide, transparent: true, opacity: .26, toneMapped: false}));
  halo.rotation.x = -Math.PI / 2;
  halo.position.y = .08;
  group.add(halo);
  if (kind === 'destination') {
    const flagShape = new THREE.Shape();
    flagShape.moveTo(0, 0); flagShape.lineTo(1.7, -.4); flagShape.lineTo(0, -1.1); flagShape.closePath();
    const flag = new THREE.Mesh(new THREE.ShapeGeometry(flagShape), new THREE.MeshBasicMaterial({color, side: THREE.DoubleSide, toneMapped: false}));
    flag.position.y = poleHeight - .3;
    group.add(flag);
  }
  return group;
}

function makeTravellerTail(points) {
  const samples = 56, positions = new Float32Array(samples * 2 * 3), fades = [], indices = [];
  let length = 0;
  for (let i = 1; i < points.length; i++) length += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
  for (let i = 0; i < samples; i++) {
    const fade = (i / (samples - 1)) ** 1.5;
    fades.push(fade, fade);
    if (i < samples - 1) indices.push(i * 2, i * 2 + 2, i * 2 + 1, i * 2 + 1, i * 2 + 2, i * 2 + 3);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage));
  geometry.setAttribute('aFade', new THREE.Float32BufferAttribute(fades, 1));
  geometry.setIndex(indices);
  const material = new THREE.ShaderMaterial({
    vertexShader: 'attribute float aFade; varying float vFade; void main(){vFade=aFade;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader: 'varying float vFade; void main(){gl_FragColor=vec4(.64,1.,.88,vFade*.7);}',
    transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, toneMapped: false,
  });
  const mesh = new THREE.Mesh(geometry, material); mesh.frustumCulled = false; mesh.renderOrder = 3;
  let lastProgress = null;
  return {mesh, length: Math.min(12, length), update(progress) {
    mesh.visible = progress > .0001;
    if (progress === lastProgress) return;
    lastProgress = progress;
    const begin = Math.max(0, progress - 12 / Math.max(1, length));
    const sampled = Array.from({length: samples}, (_, i) => pointAlong(points, lerp(begin, progress, i / (samples - 1))));
    for (let i = 0; i < samples; i++) {
      const a = sampled[Math.max(0, i - 1)], b = sampled[Math.min(samples - 1, i + 1)];
      const dx = b[0] - a[0], dz = b[1] - a[1], distance = Math.hypot(dx, dz) || 1;
      const halfWidth = .27 + .43 * i / (samples - 1);
      for (let side = 0; side < 2; side++) {
        const sign = side ? 1 : -1;
        const x = sampled[i][0] + dz / distance * halfWidth * sign;
        const z = sampled[i][1] - dx / distance * halfWidth * sign;
        geometry.attributes.position.setXYZ(i * 2 + side, x, heightAt(x, z) + .57, z);
      }
    }
    geometry.attributes.position.needsUpdate = true;
  }};
}

function makeJourney(data) {
  const group = new THREE.Group(), compare = new THREE.Group();
  for (const road of data.roads) {
    group.add(ribbon(road.points, 1.28, 0x111f1d, 1, .18));
    group.add(ribbon(road.points, .63, 0x81928a, .47, .22));
    group.add(pathLine(road.points, 0xb7c2b5, .17, .245));
  }
  group.add(ribbon(data.routes.selected, 3.5, CYAN, .045, .27));
  group.add(ribbon(data.routes.selected, 1.65, CYAN, .14, .30));
  group.add(ribbon(data.routes.selected, .46, CYAN, 1, .34));
  group.add(pathLine(data.routes.selected, 0xdcfff6, .85, .37));
  compare.add(ribbon(data.routes.comparator, 1.6, WARM, .10, .36));
  compare.add(pathLine(data.routes.comparator, 0xf5bd88, .9, .47, true));
  group.add(compare);
  const start = markerAt(data.start, 0xe4ede4);
  const destination = markerAt(data.destination, MINT, 'destination');
  const traveller = markerAt(data.start, 0xd2fff4);
  traveller.children[0].visible = false;
  traveller.children[1].position.y = .6;
  traveller.children[1].scale.setScalar(1.5);
  const travellerHalo = new THREE.Mesh(new THREE.SphereGeometry(1.4, 16, 8), new THREE.MeshBasicMaterial({color: CYAN, transparent: true, opacity: .08, depthWrite: false, toneMapped: false}));
  travellerHalo.scale.y = .4;
  travellerHalo.position.y = .2;
  traveller.add(travellerHalo);
  group.add(start, destination, traveller);
  const movingTail = makeTravellerTail(data.routes.selected);
  group.add(movingTail.mesh);
  const trail = new THREE.Group();
  if (Array.isArray(data.deviceTrace) && data.deviceTrace.length > 1) trail.add(pathLine(data.deviceTrace, 0xccddb9, .45, .55, true));
  group.add(trail);
  return {group, compare, traveller, trail, start, destination, movingTail};
}

function makeCompass() {
  const group = new THREE.Group();
  const center = new THREE.Vector3(56, -5.6, 64);
  const points = [];
  for (let i = 0; i <= 72; i++) {
    const t = i / 72 * Math.PI * 2;
    points.push(new THREE.Vector3(center.x + Math.cos(t) * 3, center.y, center.z + Math.sin(t) * 3));
  }
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({color: 0x98b5a5, transparent: true, opacity: .3})));
  const arrowGeo = new THREE.BufferGeometry();
  arrowGeo.setAttribute('position', new THREE.Float32BufferAttribute([center.x, center.y + .01, center.z - 2.6, center.x - .8, center.y + .01, center.z + 1.6, center.x, center.y + .01, center.z + .7, center.x, center.y + .01, center.z - 2.6, center.x, center.y + .01, center.z + .7, center.x + .8, center.y + .01, center.z + 1.6], 3));
  group.add(new THREE.Mesh(arrowGeo, new THREE.MeshBasicMaterial({color: 0x9fb9a8, side: THREE.DoubleSide, transparent: true, opacity: .65})));
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const ctx = c.getContext('2d'); ctx.fillStyle = '#adbfaf'; ctx.font = '400 29px sans-serif'; ctx.textAlign = 'center'; ctx.fillText('N', 32, 41);
  const texture = new THREE.CanvasTexture(c);
  const n = new THREE.Sprite(new THREE.SpriteMaterial({map: texture, transparent: true, opacity: .65, depthWrite: false}));
  n.position.set(center.x, center.y + .2, center.z - 5); n.scale.set(2, 2, 1); group.add(n);
  return group;
}

function disposeObject(group) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  group.traverse(object => {
    if (object.geometry) geometries.add(object.geometry);
    const mats = object.material ? (Array.isArray(object.material) ? object.material : [object.material]) : [];
    for (const material of mats) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  geometries.forEach(g => g.dispose());
  textures.forEach(t => t.dispose());
  materials.forEach(m => m.dispose());
}

export async function createScene(host, initialData, onInteraction = () => {}) {
  if (!host) throw new Error('The scene host is missing.');
  const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true, powerPreference: 'high-performance', preserveDrawingBuffer: true});
  renderer.setClearColor(0x07130f, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.07;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.className = 'terrain-canvas';
  renderer.domElement.setAttribute('aria-label', 'Illustrative three-dimensional terrain, scripted fire and route');
  renderer.domElement.style.cssText = 'width:100%;height:100%;display:block;touch-action:none;outline:none;';
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x07130f, .00115);
  const camera = new THREE.PerspectiveCamera(37, 1, .5, 700);
  camera.position.set(126, 105, 144);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 7, 0);
  controls.enableDamping = true;
  controls.dampingFactor = .065;
  controls.minDistance = 24;
  controls.maxDistance = 440;
  controls.minPolarAngle = .18;
  controls.maxPolarAngle = Math.PI * .47;
  controls.enablePan = true;
  controls.screenSpacePanning = false;
  controls.rotateSpeed = .48;
  controls.zoomSpeed = .75;
  controls.update();
  let manual = false, disposed = false, view = 'cinematic';
  let lastState = null, currentData = initialData, lowEffects = false;
  const interaction = () => { manual = true; onInteraction(); };
  controls.addEventListener('start', interaction);
  const ambient = new THREE.HemisphereLight(0xc8e5d8, 0x182e22, .82);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xffe5bd, 2.55);
  sun.position.set(-95, 105, 28);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.left = -100; sun.shadow.camera.right = 100;
  sun.shadow.camera.top = 100; sun.shadow.camera.bottom = -100;
  sun.shadow.camera.near = 20; sun.shadow.camera.far = 260;
  sun.shadow.bias = -.001;
  sun.shadow.normalBias = .24;
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0x9dd7c8, .65);
  rim.position.set(65, 60, -100);
  scene.add(rim);
  const stage = new THREE.Group();
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(650, 650), new THREE.ShadowMaterial({color: 0x000000, opacity: .32}));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -6.35; ground.receiveShadow = true;
  stage.add(ground);
  const grid = new THREE.GridHelper(240, 24, 0x618576, 0x618576);
  grid.position.y = -6.2;
  grid.material.transparent = true;
  grid.material.opacity = .075;
  grid.material.depthWrite = false;
  stage.add(grid, makeCompass());
  scene.add(stage);
  // Keep the product fill light in the scene throughout playback: changing light counts at chapter boundaries recompiles every lit material.
  const productFill = new THREE.PointLight(0xb2d4e0, 90, 34, 2);
  productFill.position.set(deviceAnchor[0] + 10, heightAt(...deviceAnchor) + 23, deviceAnchor[1] + 13);
  scene.add(productFill);
  let landscape, vegetation, fire, journey;
  const device = await createDevice(THREE);
  let deviceStatus = device.ready ? 'loading' : 'ready';
  device.ready?.then(ok => { deviceStatus = ok ? 'ready' : 'unavailable'; }).catch(() => { deviceStatus = 'unavailable'; });
  device.group.position.y += 9.2;
  const deviceStage = new THREE.Group();
  deviceStage.position.set(deviceAnchor[0], heightAt(...deviceAnchor) + 1.1, deviceAnchor[1]);
  deviceStage.rotation.y = -.28;
  deviceStage.add(device.group);
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(5.8, 6.3, .7, 56), new THREE.MeshStandardMaterial({color: 0x142e26, roughness: .65, metalness: .35}));
  plinth.position.y = -.5;
  deviceStage.add(plinth);
  const plinthRing = new THREE.Mesh(new THREE.TorusGeometry(5.9, .035, 5, 72), new THREE.MeshBasicMaterial({color: 0xa9ddbf, transparent: true, opacity: .6}));
  plinthRing.rotation.x = Math.PI / 2; plinthRing.position.y = -.16;
  deviceStage.add(plinthRing);
  const deviceLight = new THREE.PointLight(0xd9f3df, 85, 45, 1.3);
  deviceLight.position.set(9, 20, 15);
  deviceStage.add(deviceLight);
  scene.add(deviceStage);
  function build(data) {
    if (landscape) {
      for (const object of [landscape, vegetation, fire.group, journey.group]) { scene.remove(object); disposeObject(object); }
    }
    currentData = data;
    landscape = terrain(data);
    vegetation = forest(data);
    fire = makeFire(data);
    journey = makeJourney(data);
    scene.add(landscape, vegetation, fire.group, journey.group);
  }
  build(initialData);
  let hostWidth = 1, hostHeight = 1;
  function resize() {
    if (disposed) return;
    const rect = host.getBoundingClientRect();
    hostWidth = Math.max(1, rect.width); hostHeight = Math.max(1, rect.height);
    camera.aspect = hostWidth / hostHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(hostWidth, hostHeight, false);
  }
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  resize();
  const idealPosition = new THREE.Vector3(), idealTarget = new THREE.Vector3();
  function cameraFrame(state) {
    const time = clamp(state.time || 0, 0, 108);
    const aspectCorrection = camera.aspect < .95 ? 1.42 : camera.aspect < 1.25 ? 1.16 : 1;
    const [tx, tz] = pointAlong(currentData.routes.selected, clamp((time - 24) / 58, 0, 1));
    if (view === 'overview') {
      idealTarget.set(0, 5, 0);
      idealPosition.set(0, 200 * aspectCorrection, .01);
    } else if (view === 'follow') {
      const next = pointAlong(currentData.routes.selected, clamp((time - 24) / 58 + .04, 0, 1));
      const dx = next[0] - tx, dz = next[1] - tz, length = Math.hypot(dx, dz) || 1;
      idealTarget.set(tx + dx * 1.1, heightAt(tx, tz) + 2, tz + dz * 1.1);
      idealPosition.set(tx - dx / length * 33 + 17, heightAt(tx, tz) + 35, tz - dz / length * 33 + 25);
    } else if (state.chapter === 2) {
      idealTarget.set(deviceAnchor[0] + 2, heightAt(...deviceAnchor) + 9, deviceAnchor[1] - 2);
      idealPosition.set(deviceAnchor[0] + 42 * aspectCorrection, heightAt(...deviceAnchor) + 37 * aspectCorrection, deviceAnchor[1] + 56 * aspectCorrection);
    } else {
      const angle = -.04 + time / 72 * .11;
      const radius = (state.chapter === 1 ? 188 : 196) * aspectCorrection;
      idealPosition.set(Math.sin(.72 + angle) * radius, (state.chapter === 1 ? 124 : 124) * aspectCorrection, Math.cos(.72 + angle) * radius);
      idealTarget.set(state.chapter === 1 ? 3 : -1, 7, state.chapter === 1 ? 2 : -2);
    }
  }
  function setView(next) {
    view = next || 'cinematic'; manual = false;
    // Overview is a north-up map. Orbit remains available in both 3D views.
    controls.enabled = view !== 'overview';
    camera.up.set(0, view === 'overview' ? 0 : 1, view === 'overview' ? -1 : 0);
  }
  function reset() {
    setView('cinematic');
    const state = {...lastState, time: 0, chapter: 0, view: 'cinematic'};
    cameraFrame(state);
    camera.position.copy(idealPosition);
    controls.target.copy(idealTarget);
    controls.update();
  }
  function update(state, deltaSeconds = 0) {
    if (disposed) return;
    lastState = state;
    if (state.data && state.data !== currentData) build(state.data);
    if (state.view && state.view !== view) setView(state.view);
    const t = clamp(Number(state.time) || 0, 0, 108);
    const nextLow = !!state.lowEffects;
    if (nextLow !== lowEffects) {
      lowEffects = nextLow;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lowEffects ? 1 : 1.5));
      renderer.shadowMap.enabled = !lowEffects;
      resize();
    }
    vegetation.visible = state.layers?.forest !== false;
    fire.group.visible = state.layers?.fire !== false && currentData.fire.radius > 0;
    vegetation.userData.setLowEffects(lowEffects);
    fire.update(t, lowEffects, renderer.getPixelRatio());
    journey.compare.visible = !!state.compare;
    journey.trail.visible = state.chapter === 2;
    const progress = clamp((t - 24) / 58, 0, 1);
    const [x, z] = pointAlong(currentData.routes.selected, progress);
    journey.traveller.position.set(x, heightAt(x, z) + .75, z);
    journey.movingTail.update(progress);
    journey.traveller.children[3].material.opacity = .15 + Math.sin(t * 2) * .06;
    deviceStage.visible = state.chapter === 2;
    device.update?.(t);
    if (view === 'overview' || (!manual && !state.cameraManual)) {
      cameraFrame(state);
      const blend = view === 'overview' ? 1 : deltaSeconds > 0 ? Math.min(1, deltaSeconds * 1.65) : 1;
      camera.position.lerp(idealPosition, blend);
      controls.target.lerp(idealTarget, blend);
    }
    if (view === 'overview') camera.lookAt(controls.target);
    else controls.update();
    renderer.render(scene, camera);
  }
  function projectLabels() {
    const fireCenter = fire.getCenter?.() || currentData.fire.center;
    const labels = [
      ['start', journey.start.position.clone().add(new THREE.Vector3(0, 5, 0)), true],
      ['destination', journey.destination.position.clone().add(new THREE.Vector3(0, 8, 0)), true],
      ['fire', new THREE.Vector3(fireCenter[0], heightAt(...fireCenter) + 10, fireCenter[1]), fire.group.visible],
      ['device', deviceStage.position.clone().add(new THREE.Vector3(0, 20, 0)), deviceStage.visible],
      ['traveller', journey.traveller.position.clone().add(new THREE.Vector3(0, 3, 0)), true],
    ];
    return labels.map(([id, position, enabled]) => {
      position.project(camera);
      return {id, x: (position.x * .5 + .5) * hostWidth, y: (-position.y * .5 + .5) * hostHeight, visible: !!enabled && position.z > -1 && position.z < 1 && Math.abs(position.x) < .95 && Math.abs(position.y) < .95};
    });
  }
  device.ready?.then(() => {
    if (disposed) return;
    const wasVisible = deviceStage.visible;
    deviceStage.visible = true;
    const warming = renderer.compileAsync(scene, camera);
    deviceStage.visible = wasVisible;
    warming.catch(() => {});
  });
  const diagnostics = () => ({drawCalls: renderer.info.render.calls, triangles: renderer.info.render.triangles, points: renderer.info.render.points, trees: vegetation.userData.treeCount, renderer: 'Three.js / WebGL', pixelRatio: renderer.getPixelRatio(), lowEffects, cameraManual: manual, view, fireFootprint: fire.getFootprint?.() || null, travellerTailLength: journey.movingTail.length, viewport: {width: hostWidth, height: hostHeight}, device: {status: deviceStatus, ...(device.metadata || device.group?.userData || {})}, fixture: currentData.mode === 'fixture'});
  function dispose() {
    if (disposed) return;
    disposed = true;
    observer.disconnect();
    controls.removeEventListener('start', interaction);
    controls.dispose();
    device.dispose?.();
    disposeObject(scene);
    renderer.dispose();
    renderer.domElement.remove();
  }
  update({time: 0, chapter: 0, view: 'cinematic', layers: {forest: true, fire: true}, compare: false, lowEffects: false, data: initialData}, 0);
  return {update, setView, reset, resize, dispose, getDiagnostics: diagnostics, projectLabels};
}
