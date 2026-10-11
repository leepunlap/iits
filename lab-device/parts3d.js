/**
 * The kit's part geometry, shared by the viewer (blueprint3d.html) and the solver
 * (blueprint_solve.html) so a model renders identically in both.
 *
 * The kit is Technic-style: beams with round holes, right-angle cross blocks and pins.
 * One unit = one hole pitch (8 mm); one brick height = 1.2 units.
 */
import * as THREE from './vendor/three/three.module.js';

export const STUD = 1;
export const BRICK_H = 1.2;

const boxGeo = new THREE.BoxGeometry(1, 1, 1);
const studGeo = new THREE.CylinderGeometry(0.24, 0.24, 0.18, 16);

export const matOf = (b, opts = {}) => new THREE.MeshStandardMaterial(Object.assign({
  color: new THREE.Color(b.color || '#c91a09'), roughness: 0.5, metalness: 0.05,
}, opts));

/** A beam: `holes` round holes along its length, rounded ends, extruded to `h` (default 0.9). */
export function beamMesh(b) {
  const n = b.holes || 5, h = b.h ?? 0.9, r = 0.5;
  const shape = new THREE.Shape();
  shape.moveTo(r, 0);
  shape.lineTo(n - r, 0);
  shape.absarc(n - r, r, r, -Math.PI / 2, Math.PI / 2, false);
  shape.lineTo(r, 2 * r);
  shape.absarc(r, r, r, Math.PI / 2, (3 * Math.PI) / 2, false);
  for (let i = 0; i < n; i += 1) {
    const hole = new THREE.Path();
    hole.absarc(i + 0.5, r, 0.315, 0, Math.PI * 2, true);
    shape.holes.push(hole);
  }
  const geo = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: false, curveSegments: 16 });
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, h, -2 * r);
  return new THREE.Mesh(geo, matOf(b));
}

/** A right-angle cross block: two 2-hole segments joined at 90°, with four outward pins. */
export function crossblockMesh(b) {
  const g = new THREE.Group();
  const m = matOf(b);
  const H = 0.9;
  const segment = (len, alongX) => {
    const sh = new THREE.Shape();
    sh.moveTo(0.5, 0); sh.lineTo(len - 0.5, 0);
    sh.absarc(len - 0.5, 0.5, 0.5, -Math.PI / 2, Math.PI / 2, false);
    sh.lineTo(0.5, 1); sh.absarc(0.5, 0.5, 0.5, Math.PI / 2, (3 * Math.PI) / 2, false);
    for (let i = 0; i < len; i += 1) {
      const hole = new THREE.Path(); hole.absarc(i + 0.5, 0.5, 0.315, 0, Math.PI * 2, true); sh.holes.push(hole);
    }
    const geo = new THREE.ExtrudeGeometry(sh, { depth: H, bevelEnabled: false, curveSegments: 14 });
    geo.rotateX(-Math.PI / 2); geo.translate(0, H, -1);
    const mesh = new THREE.Mesh(geo, m);
    if (!alongX) { mesh.rotation.y = Math.PI / 2; mesh.position.set(0.5, 0, 0.5); }
    return mesh;
  };
  g.add(segment(b.lenA || 2, true), segment(b.lenB || 2, false));
  const pinGeo = new THREE.CylinderGeometry(0.24, 0.24, 0.75, 12);
  const pin = (x, y, z, axis) => {
    const p2 = new THREE.Mesh(pinGeo, m);
    if (axis === 'x') { p2.rotation.z = Math.PI / 2; } else if (axis === 'z') { p2.rotation.x = Math.PI / 2; }
    p2.position.set(x, y, z); g.add(p2);
  };
  const H2 = H / 2;
  pin(1.0, H2, 2.05, 'z'); pin(2.0, H2, 2.05, 'z');
  pin(2.05, H2, 1.0, 'x'); pin(2.05, H2, 2.0, 'x');
  return g;
}

/** A pin: a short cylinder with a stop ridge. */
export function pinMesh(b) {
  const g = new THREE.Group();
  const m = matOf(b);
  const len = b.len || 1.6;
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, len, 12), m);
  shaft.rotation.z = Math.PI / 2; shaft.position.set(len / 2, 0, 0);
  const stop = new THREE.Mesh(new THREE.CylinderGeometry(0.33, 0.33, 0.22, 12), m);
  stop.rotation.z = Math.PI / 2; stop.position.set(0.75, 0, 0);
  g.add(shaft, stop);
  return g;
}

/** A studded brick (the fallback for non-Technic parts). */
export function brickMesh(b) {
  const g = new THREE.Group();
  const m = matOf(b);
  const w = (b.w || 2) * STUD, d = (b.d || 2) * STUD, h = (b.h || 1) * BRICK_H;
  const body = new THREE.Mesh(boxGeo, m);
  body.scale.set(w, h, d); body.position.set(w / 2, h / 2, d / 2);
  g.add(body);
  for (let i = 0; i < (b.w || 2); i += 1) {
    for (let j = 0; j < (b.d || 2); j += 1) {
      const s = new THREE.Mesh(studGeo, m);
      s.position.set((i + 0.5) * STUD, h + 0.09, (j + 0.5) * STUD);
      g.add(s);
    }
  }
  return g;
}

/** One placed part, with its position and optional yaw. */
export function buildPart(b) {
  const g = (b.type === 'beam') ? beamMesh(b)
          : (b.type === 'crossblock') ? crossblockMesh(b)
          : (b.type === 'pin') ? pinMesh(b) : brickMesh(b);
  g.position.set(b.x || 0, b.y || 0, b.z || 0);
  if (b.rotY) g.rotation.y = (b.rotY * Math.PI) / 180;
  return g;
}

/** The whole model as one Group (parts keep their order, so index i = model.bricks[i]). */
export function buildModel(model) {
  const root = new THREE.Group();
  (model.bricks || []).forEach((b) => root.add(buildPart(b)));
  root.updateMatrixWorld(true);            // callers that read matrixWorld depend on this
  return root;
}
