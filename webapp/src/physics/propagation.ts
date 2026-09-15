// Urban propagation: building occlusion and knife-edge diffraction.
// Ported from penumbra/physics/propagation.py (ITU-R P.526-15 single/multiple
// knife-edge diffraction, Deygout 1966 method).
import type { Vec3 } from "./bistatic";

export interface Box {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  height: number;
}

export function boxContainsXY(b: Box, x: number, y: number): boolean {
  return b.x0 <= x && x <= b.x1 && b.y0 <= y && y <= b.y1;
}

export function fresnelNu(hM: number, d1M: number, d2M: number, wavelengthM: number): number {
  const d1 = Math.max(d1M, 1e-3);
  const d2 = Math.max(d2M, 1e-3);
  return hM * Math.sqrt((2.0 * (d1 + d2)) / (wavelengthM * d1 * d2));
}

export function knifeEdgeLossDb(nu: number): number {
  if (nu <= -0.78) return 0.0;
  return 6.9 + 20.0 * Math.log10(Math.sqrt((nu - 0.1) ** 2 + 1.0) + nu - 0.1);
}

function clipSegmentToBoxXY(p: Vec3, q: Vec3, b: Box): [number, number] | null {
  const d: [number, number] = [q[0] - p[0], q[1] - p[1]];
  let t0 = 0.0;
  let t1 = 1.0;
  const bounds: [number, number][] = [[b.x0, b.x1], [b.y0, b.y1]];
  for (let axis = 0; axis < 2; axis++) {
    const [lo, hi] = bounds[axis];
    if (Math.abs(d[axis]) < 1e-12) {
      if (p[axis] < lo || p[axis] > hi) return null;
      continue;
    }
    const ta = (lo - p[axis]) / d[axis];
    const tb = (hi - p[axis]) / d[axis];
    const tLo = Math.min(ta, tb);
    const tHi = Math.max(ta, tb);
    t0 = Math.max(t0, tLo);
    t1 = Math.min(t1, tHi);
    if (t0 > t1) return null;
  }
  return [t0, t1];
}

export function segmentIntersectsBox(p: Vec3, q: Vec3, b: Box): boolean {
  const clip = clipSegmentToBoxXY(p, q, b);
  if (clip === null) return false;
  const [t0, t1] = clip;
  const z0 = p[2] + t0 * (q[2] - p[2]);
  const z1 = p[2] + t1 * (q[2] - p[2]);
  return Math.min(z0, z1) < b.height;
}

type Edge = [number, number, number, number]; // t_along, h_above_line, d1, d2

function edgesAlong(p: Vec3, q: Vec3, buildings: Box[]): Edge[] {
  const length = Math.hypot(q[0] - p[0], q[1] - p[1], q[2] - p[2]);
  const edges: Edge[] = [];
  for (const b of buildings) {
    const clip = clipSegmentToBoxXY(p, q, b);
    if (clip === null) continue;
    const [t0, t1] = clip;
    const cands: [number, number][] = [];
    for (const tm of [t0, t1]) {
      if (tm > 0.0 && tm < 1.0) {
        const h = b.height - (p[2] + tm * (q[2] - p[2]));
        cands.push([tm, h]);
      }
    }
    if (cands.length === 0) continue;
    let best = cands[0];
    for (const c of cands) if (c[1] > best[1]) best = c;
    const [tm, h] = best;
    if (h > 0.0) edges.push([tm, h, tm * length, (1.0 - tm) * length]);
  }
  return edges;
}

function deygout(edges: Edge[], wavelengthM: number, depth = 0, maxDepth = 2): number {
  if (edges.length === 0) return 0.0;
  const nus = edges.map(([, h, d1, d2]) => fresnelNu(h, d1, d2, wavelengthM));
  let k = 0;
  for (let i = 1; i < nus.length; i++) if (nus[i] > nus[k]) k = i;
  const mainNu = nus[k];
  const loss = knifeEdgeLossDb(mainNu);
  if (loss <= 0.0 || depth >= maxDepth) return loss;
  const tMain = edges[k][0];
  const dMain = edges[k][2];
  const totalLen = edges[k][2] + edges[k][3];
  const left = edges.filter((e) => e[0] < tMain);
  const right = edges.filter((e) => e[0] > tMain);
  const leftR: Edge[] = left
    .filter((e) => dMain - e[2] > 1.0)
    .map((e) => [e[0], e[1], e[2], dMain - e[2]]);
  const rightR: Edge[] = right
    .filter((e) => e[2] - dMain > 1.0)
    .map((e) => [e[0], e[1], e[2] - dMain, totalLen - e[2]]);
  return loss + deygout(leftR, wavelengthM, depth + 1, maxDepth) + deygout(rightR, wavelengthM, depth + 1, maxDepth);
}

export const MAX_EXCESS_LOSS_DB = 45.0;

export function pathObstruction(p: Vec3, q: Vec3, buildings: Box[], wavelengthM: number): [number, number] {
  const edges = edgesAlong(p, q, buildings);
  const nBuildings = new Set(edges.map((e) => Math.round(e[0] * 1e6))).size;
  if (edges.length === 0) return [0.0, 0];
  return [Math.min(deygout(edges, wavelengthM), MAX_EXCESS_LOSS_DB), nBuildings];
}
