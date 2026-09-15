// Urban scene description for the in-browser simulator.
// Ported from penumbra/sim/scene.py. The building layout uses a seeded PRNG
// (mulberry32, not numpy's PCG64) so it is deterministic but not bit-identical
// to the Python demo scene — it is a stylised Ottawa-core-like grid for
// visualization, not a survey, in both implementations.
import type { Vec3 } from "./bistatic";
import type { Box } from "./propagation";
import { ILLUMINATORS, type Illuminator } from "./illuminators";

export interface Node {
  nodeId: string;
  pos: Vec3;
  survGainDbi: number;
  refGainDbi: number;
  noiseFigureDb: number;
}

export interface PlacedIlluminator {
  illum: Illuminator;
  pos: Vec3;
  label: string;
}

export interface Scene {
  name: string;
  buildings: Box[];
  nodes: Node[];
  illuminators: PlacedIlluminator[];
  extentM: number;
  notes: string;
}

function mulberry32(seed: number) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function stylisedBlocks(
  rng: () => number, nX = 7, nY = 5, block: [number, number] = [110.0, 80.0],
  street: [number, number] = [22.0, 22.0], hRange: [number, number] = [10.0, 36.0], tallProb = 0.12,
): Box[] {
  const boxes: Box[] = [];
  const [bw, bh] = block;
  const [sw, sh] = street;
  const xStart = -(nX * (bw + sw)) / 2.0;
  const yStart = -(nY * (bh + sh)) / 2.0;
  for (let i = 0; i < nX; i++) {
    for (let j = 0; j < nY; j++) {
      const x0 = xStart + i * (bw + sw);
      const y0 = yStart + j * (bh + sh);
      const nSub = 2 + Math.floor(rng() * 2);
      for (let k = 0; k < nSub; k++) {
        const ex0 = x0 + (k / nSub) * bw;
        const ex1 = x0 + ((k + 1) / nSub) * bw;
        let h = hRange[0] + rng() * (hRange[1] - hRange[0]);
        if (rng() < tallProb) h = 45.0 + rng() * (100.0 - 45.0);
        boxes.push({ x0: ex0, y0, x1: ex1, y1: y0 + bh, height: h });
      }
    }
  }
  return boxes;
}

export function demoDowntownScene(seed = 7, nNodes = 6): Scene {
  const rng = mulberry32(seed);
  const buildings = stylisedBlocks(rng);

  const campFortune: Vec3 = [-12_500.0, 9_500.0, 450.0];
  const illums: PlacedIlluminator[] = [
    { illum: ILLUMINATORS.cbot_dt, pos: campFortune, label: "CBOT-DT ch.25" },
    { illum: ILLUMINATORS.chot_dt, pos: [campFortune[0] + 60.0, campFortune[1] + 40.0, campFortune[2] - 20.0], label: "CHOT-DT ch.32" },
    { illum: ILLUMINATORS.lte_700, pos: [-420.0, 300.0, 38.0], label: "LTE sector A" },
    { illum: ILLUMINATORS.lte_700, pos: [380.0, -260.0, 42.0], label: "LTE sector B" },
    { illum: ILLUMINATORS.lte_700, pos: [60.0, 420.0, 35.0], label: "LTE sector C" },
    { illum: ILLUMINATORS.nr_n78, pos: [-150.0, -330.0, 40.0], label: "5G n78 sector D" },
    { illum: ILLUMINATORS.nr_n78, pos: [300.0, 180.0, 45.0], label: "5G n78 sector E" },
  ];

  const nodes: Node[] = [];
  const radius = 330.0;
  for (let i = 0; i < nNodes; i++) {
    const th = (2 * Math.PI * i) / nNodes + 0.3;
    const pos: Vec3 = [radius * Math.cos(th), radius * 0.8 * Math.sin(th), 30.0 + rng() * 25.0];
    nodes.push({ nodeId: `N${String(i + 1).padStart(2, "0")}`, pos, survGainDbi: 6.0, refGainDbi: 10.0, noiseFigureDb: 5.0 });
  }
  return {
    name: "ottawa-core-stylised",
    buildings, nodes, illuminators: illums, extentM: 600.0,
    notes: "Stylised grid (7x5 blocks, 110x80 m, mostly 10-36 m tall with ~12% towers of 45-100 m), matching the Ottawa core in character. Illuminator EIRPs are from public records; positions are approximate.",
  };
}
