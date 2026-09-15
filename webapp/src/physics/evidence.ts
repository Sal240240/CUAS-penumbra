// Evidence ledger: an auditable classifier of last resort. Ported from
// penumbra/reasoning/evidence.py. Every published track carries a
// justification built from named physical evidence with explicit log-odds
// on three axes (real / airborne / drone), not an unaudited softmax.
import { TARGETS } from "./rcs";

export type Axis = "real" | "airborne" | "drone";

export interface EvidenceItem {
  kind: string;
  statement: string;
  logOdds: number;
  weight: number;
  axis: Axis;
}

export interface Observation {
  flashHz?: number;
  tipDopplerHz?: number;
  bandFreqHz?: number;
  wingbeatHz?: number;
  nPairs: number;
  nBands: number;
  nisSigma?: number;
  hoverS: number;
  maxSpeedMps: number;
  maxAccelMps2: number;
  altAglM?: number;
  altSigmaM?: number;
  onStreetAxis: boolean;
  persistenceS: number;
  externalRfDetect?: boolean;
}

const ROTOR_RPM_RANGE: [number, number] = [2_500.0, 25_000.0];
const BLADES = [2, 3];
const BIRD_WINGBEAT_HZ: [number, number] = [1.5, 12.0];
const MAX_VEHICLE_ALT_M = 6.0;

function rotorHypotheses(flashHz: number): string[] {
  const out: string[] = [];
  for (const nb of BLADES) {
    const rpm = (flashHz / nb) * 60.0;
    if (rpm >= ROTOR_RPM_RANGE[0] && rpm <= ROTOR_RPM_RANGE[1]) {
      let close = Object.values(TARGETS)[0];
      let bestDiff = Infinity;
      for (const t of Object.values(TARGETS)) {
        const diff = t.nBlades === nb ? Math.abs(t.rotorRpm - rpm) : 1e9;
        if (diff < bestDiff) { bestDiff = diff; close = t; }
      }
      out.push(`${nb} blades x ${rpm.toFixed(0)} rpm (nearest catalogue: ${close.name})`);
    }
  }
  return out;
}

export function buildLedger(obs: Observation): EvidenceItem[] {
  const ev: EvidenceItem[] = [];
  const push = (kind: string, statement: string, logOdds: number, axis: Axis, weight = 1.0) =>
    ev.push({ kind, statement, logOdds, weight, axis });

  if (obs.flashHz) {
    const hyp = rotorHypotheses(obs.flashHz);
    if (hyp.length > 0) {
      push("micro_doppler", `HERM line spacing ${obs.flashHz.toFixed(0)} Hz consistent with a rotor: ${hyp.join("; ")}`, 2.8, "drone");
      push("micro_doppler", "Periodic modulation present: a real moving scatterer, not a ghost", 1.0, "real");
    } else if (obs.flashHz >= BIRD_WINGBEAT_HZ[0] && obs.flashHz <= BIRD_WINGBEAT_HZ[1]) {
      push("micro_doppler", `Modulation at ${obs.flashHz.toFixed(1)} Hz lies in the avian wingbeat band`, -2.2, "drone");
      push("micro_doppler", "Periodic modulation present: a real moving scatterer, not a ghost", 1.0, "real");
    } else {
      push("micro_doppler", `Modulation at ${obs.flashHz.toFixed(0)} Hz matches neither rotor nor wingbeat`, -0.3, "drone");
    }
  }
  if (obs.tipDopplerHz && obs.bandFreqHz) {
    const lam = 299_792_458.0 / obs.bandFreqHz;
    const tipMps = (obs.tipDopplerHz * lam) / 2.0;
    if (tipMps > 40.0) push("micro_doppler", `Micro-Doppler extent implies scatterer speed ${tipMps.toFixed(0)} m/s: only a propeller does that`, 2.0, "drone");
    else if (tipMps > 4.0) push("micro_doppler", `Micro-Doppler extent implies ${tipMps.toFixed(0)} m/s: wing-tip regime`, -1.0, "drone");
  }
  if (obs.wingbeatHz) push("micro_doppler", `Wingbeat sidebands at ${obs.wingbeatHz.toFixed(1)} Hz`, -2.5, "drone");

  if (obs.hoverS >= 2.0) push("kinematics", `Hovered ${obs.hoverS.toFixed(1)} s with |v| < 1 m/s: birds cannot (kestrels excepted, briefly)`, 1.9, "drone");
  if (obs.maxSpeedMps > 25.0) push("kinematics", `Peak speed ${obs.maxSpeedMps.toFixed(0)} m/s exceeds sustained flight of local birds`, 1.2, "drone");
  if (obs.maxAccelMps2 > 6.0) push("kinematics", `Peak acceleration ${obs.maxAccelMps2.toFixed(1)} m/s^2`, 0.8, "drone");
  if (obs.altAglM !== undefined) {
    const sig = obs.altSigmaM ?? 15.0;
    if (obs.altAglM - 2 * sig > MAX_VEHICLE_ALT_M) push("kinematics", `Altitude ${obs.altAglM.toFixed(0)} +- ${sig.toFixed(0)} m AGL: airborne, not a ground vehicle`, 2.5, "airborne");
    else if (obs.altAglM + 2 * sig <= MAX_VEHICLE_ALT_M) push("kinematics", `Altitude ${obs.altAglM.toFixed(0)} +- ${sig.toFixed(0)} m AGL: at street level`, -3.0, "airborne");
  }
  if (obs.onStreetAxis) push("kinematics", "Trajectory confined to a street axis", -1.5, "airborne");

  if (obs.nPairs >= 3) push("multistatic", `Seen by ${obs.nPairs} illuminator/node pairs across ${obs.nBands} band(s)`, 0.4 * Math.min(obs.nPairs, 6) + 0.3 * obs.nBands, "real");
  else if (obs.nPairs > 0) push("coverage", `Only ${obs.nPairs} pair(s): position from ellipse intersection is weak`, -0.6, "real");
  if (obs.nisSigma !== undefined) {
    if (obs.nisSigma < 2.0) push("multistatic", `Multistatic residual ${obs.nisSigma.toFixed(1)} sigma: measurements agree on one object`, 1.0, "real");
    else push("multistatic", `Multistatic residual ${obs.nisSigma.toFixed(1)} sigma: possible ghost intersection`, -1.5, "real");
  }
  if (obs.persistenceS >= 3.0) push("persistence", `Persistent for ${obs.persistenceS.toFixed(1)} s`, 0.6, "real");
  if (obs.maxSpeedMps > 0 && obs.altAglM === undefined && obs.onStreetAxis) push("kinematics", "No altitude solution and street-constrained motion: treat as ground traffic", -1.0, "airborne");
  if (obs.externalRfDetect === true) push("external", "Independent RF-emission sensor reports a UAS link in this sector", 2.0, "drone", 0.8);

  return ev;
}

function sigmoid(x: number): number {
  return 1.0 / (1.0 + Math.exp(-x));
}

export interface ClassProbs {
  unknown: number;
  drone: number;
  bird: number;
  vehicle: number;
  clutter: number;
}

export function combine(ledger: EvidenceItem[], priorReal = 0.5, priorAirborne = 0.5, priorDrone = 0.5): ClassProbs {
  const lo = (prior: number, axis: Axis) => {
    const base = Math.log(prior / (1 - prior));
    const sum = ledger.filter((e) => e.axis === axis).reduce((s, e) => s + e.logOdds * e.weight, 0);
    return base + sum;
  };
  const pReal = sigmoid(lo(priorReal, "real"));
  const pAir = sigmoid(lo(priorAirborne, "airborne"));
  const pDrone = sigmoid(lo(priorDrone, "drone"));
  return {
    unknown: 0.0,
    drone: pReal * pAir * pDrone,
    bird: pReal * pAir * (1 - pDrone),
    vehicle: pReal * (1 - pAir),
    clutter: 1 - pReal,
  };
}
