// Bistatic radar geometry and the passive-radar link budget.
// Ported from penumbra/physics/bistatic.py — keep in exact numerical
// agreement with that module (see webapp/README.md "Physics parity").
//
// Radar equation (Willis, Bistatic Radar, 2nd ed., eq. 4.1):
//   P_r = P_t G_t G_r lambda^2 sigma_b / ((4 pi)^3 R_t^2 R_r^2 L_sys)
//
// Two detectability floors (Griffiths & Baker, An Introduction to Passive
// Radar, 2017): thermal noise, and direct-signal-interference (DSI) residual
// after cancellation. The usable SNR is the smaller of the two.
import { C0, K_BOLTZ, T0_K } from "./constants";

export type Vec3 = [number, number, number];

export function db(x: number): number {
  return 10.0 * Math.log10(x);
}

export function undb(xDb: number): number {
  return 10.0 ** (xDb / 10.0);
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}
function norm(a: Vec3): number {
  return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
}
function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
function scale(a: Vec3, s: number): Vec3 {
  return [a[0] * s, a[1] * s, a[2] * s];
}

export interface BistaticGeometry {
  rT: number; // transmitter-target distance, m
  rR: number; // receiver-target distance, m
  baseline: number; // transmitter-receiver distance, m
  rBistatic: number; // R_t + R_r - L, m
  betaRad: number; // bistatic angle at the target, rad
  uT: Vec3; // unit vector T->P
  uR: Vec3; // unit vector R->P
}

export function bistaticGeometry(tx: Vec3, rx: Vec3, target: Vec3): BistaticGeometry {
  const dT = sub(target, tx);
  const dR = sub(target, rx);
  const rT = norm(dT);
  const rR = norm(dR);
  if (rT === 0 || rR === 0) {
    throw new Error("target coincides with transmitter or receiver");
  }
  const baseline = norm(sub(rx, tx));
  const uT: Vec3 = scale(dT, 1 / rT);
  const uR: Vec3 = scale(dR, 1 / rR);
  const cosBeta = Math.max(-1, Math.min(1, dot(scale(uT, -1), scale(uR, -1))));
  const beta = Math.acos(cosBeta);
  return { rT, rR, baseline, rBistatic: rT + rR - baseline, betaRad: beta, uT, uR };
}

export function bistaticDoppler(tx: Vec3, rx: Vec3, target: Vec3, velocity: Vec3, wavelengthM: number): number {
  const g = bistaticGeometry(tx, rx, target);
  const rangeRate = dot(velocity, g.uT) + dot(velocity, g.uR);
  return -rangeRate / wavelengthM;
}

export function receivedPowerW(
  pTW: number, gT: number, gR: number, wavelengthM: number, sigmaM2: number,
  rT: number, rR: number, lossLin = 1.0,
): number {
  return (pTW * gT * gR * wavelengthM ** 2 * sigmaM2) / ((4 * Math.PI) ** 3 * rT ** 2 * rR ** 2 * lossLin);
}

export function directPathPowerW(pTW: number, gT: number, gRRef: number, wavelengthM: number, baselineM: number): number {
  return pTW * gT * gRRef * (wavelengthM / (4 * Math.PI * baselineM)) ** 2;
}

export interface LinkBudget {
  pRDbw: number;
  pDirectDbw: number;
  snrThermalDb: number;
  snrDsiDb: number;
  snrDb: number; // min of the two floors
  processingGainDb: number;
  rangeResolutionM: number; // c / B (bistatic, along the sum-range)
  dopplerResolutionHz: number; // 1 / T_int
  detectable: boolean;
}

export interface LinkBudgetInput {
  eirpDbw: number;
  freqHz: number;
  bandwidthHz: number;
  tIntS: number;
  sigmaDbsm: number;
  rTM: number;
  rRM: number;
  baselineM: number;
  gRDbi?: number;
  gRRefDbi?: number;
  noiseFigureDb?: number;
  systemLossDb?: number;
  dsiCancellationDb?: number;
  extraPathLossDb?: number;
  detectionThresholdDb?: number;
}

export function linkBudget(input: LinkBudgetInput): LinkBudget {
  const {
    eirpDbw, freqHz, bandwidthHz, tIntS, sigmaDbsm, rTM, rRM, baselineM,
    gRDbi = 6.0, gRRefDbi = 10.0, noiseFigureDb = 5.0, systemLossDb = 3.0,
    dsiCancellationDb = 50.0, extraPathLossDb = 0.0, detectionThresholdDb = 13.0,
  } = input;
  const lam = C0 / freqHz;
  const pT = undb(eirpDbw);
  const pR = receivedPowerW(pT, 1.0, undb(gRDbi), lam, undb(sigmaDbsm), rTM, rRM, undb(systemLossDb + extraPathLossDb));
  const pDir = directPathPowerW(pT, 1.0, undb(gRRefDbi), lam, baselineM);
  const gp = bandwidthHz * tIntS;
  const snrTh = (pR * tIntS) / (K_BOLTZ * T0_K * undb(noiseFigureDb));
  const snrDsi = (pR / pDir) * undb(dsiCancellationDb) * gp;
  const snr = Math.min(snrTh, snrDsi);
  return {
    pRDbw: db(pR),
    pDirectDbw: db(pDir),
    snrThermalDb: db(snrTh),
    snrDsiDb: db(snrDsi),
    snrDb: db(snr),
    processingGainDb: db(gp),
    rangeResolutionM: C0 / bandwidthHz,
    dopplerResolutionHz: 1.0 / tIntS,
    detectable: db(snr) >= detectionThresholdDb,
  };
}

export function maxDetectionRangeM(
  input: Omit<LinkBudgetInput, "rRM"> & { rRGrid?: number[] },
): number {
  const thresholdDb = input.detectionThresholdDb ?? 13.0;
  const grid = input.rRGrid ?? geomspace(20.0, 20_000.0, 400);
  let best = 0.0;
  for (const rR of grid) {
    const lb = linkBudget({ ...input, rRM: rR, detectionThresholdDb: thresholdDb });
    if (lb.snrDb >= thresholdDb) best = rR;
  }
  return best;
}

export function geomspace(a: number, b: number, n: number): number[] {
  const logA = Math.log(a);
  const logB = Math.log(b);
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    out.push(Math.exp(logA + ((logB - logA) * i) / (n - 1)));
  }
  return out;
}
