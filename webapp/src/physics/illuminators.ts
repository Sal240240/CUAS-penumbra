// Illuminators of opportunity available in an Ottawa-class Canadian city.
// Ported from penumbra/physics/illuminators.py — see that file for full
// citations (Wikipedia broadcast records, ISED RSS-247, Ji et al. 2025,
// Humphreys et al. arXiv:2210.11578, Blazquez-Garcia et al. 2024).
export interface Illuminator {
  key: string;
  name: string;
  kind: "atsc" | "lte" | "nr" | "wifi" | "fm" | "leo";
  freqHz: number;
  bandwidthHz: number;
  eirpDbw: number;
  dutyCycle: number;
  typicalDistanceM: number;
  locationNote: string;
  source: string;
  strengths: string[];
  weaknesses: string[];
}

export const ILLUMINATORS: Record<string, Illuminator> = {
  cbot_dt: {
    key: "cbot_dt", name: "CBOT-DT (CBC Ottawa) ATSC ch.25", kind: "atsc",
    freqHz: 539.0e6, bandwidthHz: 6.0e6, eirpDbw: 57.1, dutyCycle: 1.0, typicalDistanceM: 15_700.0,
    locationNote: "Ryan Tower, Camp Fortune, QC (45.509 N, 75.861 W), HAAT 426 m; ~15.7 km NNW of Parliament Hill.",
    source: "Wikipedia 'CBOT-DT' (ERP 311.485 kW, ch.25, HAAT 426.4 m), retrieved 2026-09.",
    strengths: ["highest EIRP in the region", "continuous 24/7", "UHF puts a 30 cm airframe in the resonance region", "elevated transmitter illuminates street canyons from above the skyline"],
    weaknesses: ["6 MHz -> 50 m bistatic range resolution", "rotor blades electrically small at UHF -> weak micro-Doppler", "single site; fixed geometry"],
  },
  chot_dt: {
    key: "chot_dt", name: "CHOT-DT (TVA Gatineau) ATSC ch.32", kind: "atsc",
    freqHz: 581.0e6, bandwidthHz: 6.0e6, eirpDbw: 52.6, dutyCycle: 1.0, typicalDistanceM: 15_700.0,
    locationNote: "Camp Fortune area, HAAT 358 m.",
    source: "Wikipedia 'CHOT-DT' (ERP 111.4 kW), retrieved 2026-09.",
    strengths: ["second independent UHF illuminator, 42 MHz from CBOT -> frequency diversity"],
    weaknesses: ["same site as CBOT -> same bistatic geometry"],
  },
  lte_700: {
    key: "lte_700", name: "LTE band 12/13/17 macro sector (700 MHz)", kind: "lte",
    freqHz: 740.0e6, bandwidthHz: 10.0e6, eirpDbw: 30.0, dutyCycle: 1.0, typicalDistanceM: 600.0,
    locationNote: "Dozens of sectors across downtown Ottawa; every node sees several.",
    source: "EIRP assumed 20 W PA + 17 dBi panel = 60 dBm = 30 dBW per sector (typical macro).",
    strengths: ["dense, many simultaneous geometries -> multistatic Doppler-only tracking (Ji et al. 2025)", "short baselines -> strong echo"],
    weaknesses: ["10 MHz -> 30 m resolution", "sector patterns down-tilted; rooftop nodes may sit in sidelobes"],
  },
  nr_n78: {
    key: "nr_n78", name: "5G NR n78 massive-MIMO sector (3.5 GHz)", kind: "nr",
    freqHz: 3_500.0e6, bandwidthHz: 100.0e6, eirpDbw: 40.0, dutyCycle: 1.0, typicalDistanceM: 400.0,
    locationNote: "SSB bursts every 20 ms swept over beams; use SSB/PBCH for a deterministic reference.",
    source: "EIRP assumed 40 dBW (~70 dBm) per beam, mid-range for 64T64R AAUs.",
    strengths: ["100 MHz -> 3 m resolution", "blades ~1.5 wavelengths -> strong rotor micro-Doppler", "Doppler 6.5x larger than UHF for same speed"],
    weaknesses: ["beam sweeping = intermittent illumination", "higher path loss; 300-500 m per node", "traffic-dependent power"],
  },
  wifi_5g: {
    key: "wifi_5g", name: "Wi-Fi 5 GHz access point (802.11ax/be, 80 MHz)", kind: "wifi",
    freqHz: 5_500.0e6, bandwidthHz: 80.0e6, eirpDbw: 0.0, dutyCycle: 0.3, typicalDistanceM: 60.0,
    locationNote: "The mesh's own 802.11bf-capable backhaul links, scheduled to transmit sensing NDPs.",
    source: "ISED RSS-247: max 1 W EIRP (30 dBm) in 5.15-5.25 GHz indoor / 5.725-5.85 GHz up to 4 W.",
    strengths: ["node-to-node links under our control (IEEE 802.11bf-2025 sensing)", "80 MHz -> 3.7 m resolution", "fills street canyons"],
    weaknesses: ["very short range (~100 m)", "low EIRP", "bursty; duty-cycle-limited integration time"],
  },
  fm_103: {
    key: "fm_103", name: "FM broadcast (CBO-FM 103.3, 100 kW ERP)", kind: "fm",
    freqHz: 103.3e6, bandwidthHz: 0.2e6, eirpDbw: 52.2, dutyCycle: 1.0, typicalDistanceM: 15_700.0,
    locationNote: "Typical Ottawa class-C FM ERP.",
    source: "Typical Ottawa class-C FM ERP 100 kW (CRTC records).",
    strengths: ["huge EIRP", "classic PCL illuminator for aircraft"],
    weaknesses: ["3 m wavelength: a 30 cm drone is deep Rayleigh (~-45 dBsm) -> essentially undetectable", "0.2 MHz -> 1.5 km resolution"],
  },
  leo_ku: {
    key: "leo_ku", name: "LEO broadband user downlink (Starlink Ku-band)", kind: "leo",
    freqHz: 11_700.0e6, bandwidthHz: 240.0e6, eirpDbw: 35.0, dutyCycle: 1.0, typicalDistanceM: 550_000.0,
    locationNote: "Research option only (Phase E) — footnote, not a Sandbox 2027 claim.",
    source: "Blazquez-Garcia et al. 2024, IET RSN 10.1049/rsn2.12446; Humphreys et al. arXiv:2210.11578.",
    strengths: ["illumination from overhead: no urban shadowing on the transmit leg", "240 MHz -> 1.2 m resolution"],
    weaknesses: ["weak at ground level: needs a high-gain dish -> narrow FOV", "research-grade (TRL 3)"],
  },
};

export function getIlluminator(key: string): Illuminator {
  return ILLUMINATORS[key];
}
