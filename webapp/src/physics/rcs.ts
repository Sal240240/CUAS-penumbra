// Radar cross-section models for micro/mini UAS across bands.
// Ported from penumbra/physics/rcs.py — see that file's docstring for the
// measured anchors (Semkin et al. arXiv:1911.05926; Quevedo et al. 2019) and
// the frequency-scaling model (Rayleigh / resonance / optical regions).
import { C0 } from "./constants";

export interface TargetSignature {
  key: string;
  name: string;
  massKg: number;
  spanM: number;
  rcsOptDbsm: number;
  nRotors: number;
  nBlades: number;
  bladeLenM: number;
  rotorRpm: number;
  bladeMaterial: "carbon" | "plastic" | "n/a";
  cruiseSpeedMps: number;
  classLabel: "micro" | "mini" | "bird" | "vehicle";
}

export const TARGETS: Record<string, TargetSignature> = {
  dji_mini: { key: "dji_mini", name: "DJI Mini-class (249 g)", massKg: 0.249, spanM: 0.25, rcsOptDbsm: -22.0, nRotors: 4, nBlades: 2, bladeLenM: 0.062, rotorRpm: 9_000, bladeMaterial: "plastic", cruiseSpeedMps: 12.0, classLabel: "micro" },
  dji_mavic: { key: "dji_mavic", name: "DJI Mavic-class (0.9 kg)", massKg: 0.90, spanM: 0.35, rcsOptDbsm: -17.0, nRotors: 4, nBlades: 2, bladeLenM: 0.11, rotorRpm: 6_500, bladeMaterial: "plastic", cruiseSpeedMps: 18.0, classLabel: "micro" },
  fpv_5in: { key: "fpv_5in", name: "5-inch FPV racer (0.7 kg)", massKg: 0.70, spanM: 0.22, rcsOptDbsm: -20.0, nRotors: 4, nBlades: 3, bladeLenM: 0.064, rotorRpm: 20_000, bladeMaterial: "plastic", cruiseSpeedMps: 35.0, classLabel: "micro" },
  phantom: { key: "phantom", name: "DJI Phantom-class (1.4 kg)", massKg: 1.40, spanM: 0.35, rcsOptDbsm: -15.0, nRotors: 4, nBlades: 2, bladeLenM: 0.12, rotorRpm: 6_000, bladeMaterial: "plastic", cruiseSpeedMps: 16.0, classLabel: "micro" },
  m30: { key: "m30", name: "DJI Matrice 30-class (3.7 kg)", massKg: 3.70, spanM: 0.67, rcsOptDbsm: -10.0, nRotors: 4, nBlades: 2, bladeLenM: 0.24, rotorRpm: 4_500, bladeMaterial: "carbon", cruiseSpeedMps: 20.0, classLabel: "mini" },
  hexa_10kg: { key: "hexa_10kg", name: "10 kg hexacopter", massKg: 10.0, spanM: 1.10, rcsOptDbsm: -5.0, nRotors: 6, nBlades: 2, bladeLenM: 0.30, rotorRpm: 3_500, bladeMaterial: "carbon", cruiseSpeedMps: 15.0, classLabel: "mini" },
  bird_gull: { key: "bird_gull", name: "Gull (reference non-target)", massKg: 1.0, spanM: 0.40, rcsOptDbsm: -20.0, nRotors: 0, nBlades: 0, bladeLenM: 0.30, rotorRpm: 180, bladeMaterial: "n/a", cruiseSpeedMps: 12.0, classLabel: "bird" },
};

function ka(charSizeM: number, freqHz: number): number {
  const lam = C0 / freqHz;
  return (2.0 * Math.PI * (charSizeM / 2.0)) / lam;
}

function regionFactorDb(kaVal: number): number {
  if (kaVal >= 1.0) return 0.0;
  return 40.0 * Math.log10(Math.max(kaVal, 1e-6));
}

export function bodyRcs(target: TargetSignature, freqHz: number): number {
  return target.rcsOptDbsm + regionFactorDb(ka(target.spanM, freqHz));
}

export function bladeRcs(target: TargetSignature, freqHz: number): number {
  if (target.nBlades === 0) return -80.0;
  const base = target.rcsOptDbsm - 20.0 - (target.bladeMaterial === "plastic" ? 10.0 : 0.0);
  return base + regionFactorDb(ka(2.0 * target.bladeLenM, freqHz));
}
