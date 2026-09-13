// Coverage analysis: how many (illuminator, node) pairs can see each point of
// the volume. Ported from penumbra/sim/coverage.py.
import { C0 } from "./constants";
import { bistaticGeometry, linkBudget, type Vec3 } from "./bistatic";
import { pathObstruction } from "./propagation";
import { bodyRcs, TARGETS } from "./rcs";
import type { Scene } from "./scene";

export interface CoverageResult {
  x: number[];
  y: number[];
  nPairs: number[][]; // [iy][ix]
  bestSnrDb: number[][];
  covered: boolean[][];
}

export interface CoverageOptions {
  targetKey?: string;
  altM?: number;
  stepM?: number;
  tIntS?: number;
  thresholdDb?: number;
  minPairs?: number;
  illumKinds?: string[];
}

export function coverageMap(scene: Scene, opts: CoverageOptions = {}): CoverageResult {
  const {
    targetKey = "dji_mavic", altM = 40.0, stepM = 40.0, tIntS = 0.5,
    thresholdDb = 13.0, minPairs = 3, illumKinds = ["atsc", "lte", "nr"],
  } = opts;
  const tg = TARGETS[targetKey];
  const e = scene.extentM;
  const xs: number[] = [];
  for (let v = -e; v <= e + 1e-9; v += stepM) xs.push(v);
  const ys: number[] = [];
  for (let v = -e; v <= e + 1e-9; v += stepM) ys.push(v);

  const pairs = scene.illuminators
    .filter((il) => illumKinds.includes(il.illum.kind))
    .flatMap((il) => scene.nodes.map((nd) => ({ il, nd })));

  const nPairs: number[][] = ys.map(() => xs.map(() => 0));
  const best: number[][] = ys.map(() => xs.map(() => -99.0));

  ys.forEach((y, iy) => {
    xs.forEach((x, ix) => {
      const p: Vec3 = [x, y, altM];
      const blocked = scene.buildings.some((b) => b.x0 <= x && x <= b.x1 && b.y0 <= y && y <= b.y1 && b.height > altM);
      if (blocked) return;
      for (const { il, nd } of pairs) {
        // A grid cell can land exactly on an illuminator or node position
        // (both are often round numbers); that geometry is undefined for the
        // bistatic equations and contributes no real information anyway, so
        // skip it rather than let it throw and blank the whole map.
        const dIl = Math.hypot(p[0] - il.pos[0], p[1] - il.pos[1], p[2] - il.pos[2]);
        const dNd = Math.hypot(p[0] - nd.pos[0], p[1] - nd.pos[1], p[2] - nd.pos[2]);
        if (dIl < 1.0 || dNd < 1.0) continue;
        const lam = C0 / il.illum.freqHz;
        const g = bistaticGeometry(il.pos, nd.pos, p);
        const [lt] = pathObstruction(il.pos, p, scene.buildings, lam);
        const [lr] = pathObstruction(nd.pos, p, scene.buildings, lam);
        const lb = linkBudget({
          eirpDbw: il.illum.eirpDbw, freqHz: il.illum.freqHz, bandwidthHz: il.illum.bandwidthHz,
          tIntS: tIntS * il.illum.dutyCycle, sigmaDbsm: bodyRcs(tg, il.illum.freqHz),
          rTM: g.rT, rRM: g.rR, baselineM: g.baseline, gRDbi: nd.survGainDbi,
          noiseFigureDb: nd.noiseFigureDb, extraPathLossDb: lt + lr, detectionThresholdDb: thresholdDb,
        });
        if (lb.snrDb >= thresholdDb) nPairs[iy][ix] += 1;
        best[iy][ix] = Math.max(best[iy][ix], lb.snrDb);
      }
    });
  });

  const covered = nPairs.map((row) => row.map((n) => n >= minPairs));
  return { x: xs, y: ys, nPairs, bestSnrDb: best, covered };
}
