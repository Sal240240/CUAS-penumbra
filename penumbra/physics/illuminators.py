"""Illuminators of opportunity available in an Ottawa-class Canadian city.

Canada broadcasts ATSC (8-VSB, 6 MHz channels), *not* DVB-T, so the European
passive-radar literature's DVB-T numbers are translated here to ATSC channels.
Values marked `source` come from public records retrieved September 2026 and
must be re-verified against the ISED broadcast database before any deployment.

Every entry carries the fields the link budget needs. `duty_cycle` scales the
usable integration time for bursty sources (Wi-Fi). `eirp_dbw` is toward the
surveillance volume, not the peak of the pattern, unless noted.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Illuminator:
    key: str
    name: str
    kind: str                    # 'atsc', 'lte', 'nr', 'wifi', 'fm', 'leo'
    freq_hz: float
    bandwidth_hz: float
    eirp_dbw: float
    duty_cycle: float = 1.0
    typical_distance_m: float = 1000.0     # illuminator-to-surveillance-volume
    waveform_note: str = ""
    caf_sidelobe_note: str = ""
    location_note: str = ""
    source: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


ILLUMINATORS: Dict[str, Illuminator] = {}


def _add(i: Illuminator):
    ILLUMINATORS[i.key] = i
    return i


_add(Illuminator(
    key="cbot_dt", name="CBOT-DT (CBC Ottawa) ATSC ch.25", kind="atsc",
    freq_hz=539.0e6, bandwidth_hz=6.0e6,
    # ERP 311.485 kW -> 54.9 dBW ERP -> +2.15 dB = 57.1 dBW EIRP (main lobe, horizontal plane)
    eirp_dbw=57.1, typical_distance_m=15_700.0,
    waveform_note="8-VSB, continuous, noise-like payload; pilot tone at lower band edge and "
                  "segment/field sync produce deterministic CAF ridges that must be suppressed.",
    caf_sidelobe_note="Data-segment sync every 77.3 us and field sync every 24.2 ms create "
                      "delay/Doppler ambiguities; suppress by sync-blanking in the reference.",
    location_note="Ryan Tower, Camp Fortune, QC (45.509 N, 75.861 W), HAAT 426 m; ~15.7 km NNW of Parliament Hill.",
    source="Wikipedia 'CBOT-DT' (ERP 311.485 kW, ch.25, HAAT 426.4 m), retrieved 2026-09.",
    strengths=["highest EIRP in the region", "continuous 24/7", "UHF wavelength puts a 30 cm airframe in the resonance region -> strong body return", "elevated transmitter illuminates street canyons from above the skyline"],
    weaknesses=["6 MHz -> 50 m bistatic range resolution", "rotor blades are electrically small at UHF -> weak micro-Doppler", "single-site; geometry fixed"],
))
_add(Illuminator(
    key="chot_dt", name="CHOT-DT (TVA Gatineau) ATSC ch.32", kind="atsc",
    freq_hz=581.0e6, bandwidth_hz=6.0e6, eirp_dbw=52.6, typical_distance_m=15_700.0,
    location_note="Camp Fortune area, HAAT 358 m.",
    source="Wikipedia 'CHOT-DT' (ERP 111.4 kW), retrieved 2026-09.",
    strengths=["second independent UHF illuminator, 42 MHz from CBOT -> frequency diversity"],
    weaknesses=["same site as CBOT -> same bistatic geometry"],
))
_add(Illuminator(
    key="cfgs_dt", name="CFGS-DT (Noovo Gatineau) ATSC ch.34", kind="atsc",
    freq_hz=593.0e6, bandwidth_hz=6.0e6, eirp_dbw=51.8, typical_distance_m=15_700.0,
    source="Wikipedia 'CFGS-DT' (ERP 93.3 kW), retrieved 2026-09.",
))
_add(Illuminator(
    key="lte_700", name="LTE band 12/13/17 macro sector (700 MHz)", kind="lte",
    freq_hz=740.0e6, bandwidth_hz=10.0e6, eirp_dbw=30.0, typical_distance_m=600.0,
    waveform_note="OFDM downlink; always-on cell-specific reference signals give a stable "
                  "reference even at low traffic. Frame 10 ms, subframe 1 ms.",
    caf_sidelobe_note="CP and pilot periodicity create ambiguities at multiples of 1 ms / 10 ms; "
                      "reconstruct the reference from decoded PDSCH/CRS rather than raw capture.",
    location_note="Dozens of sectors across downtown Ottawa; every node sees several.",
    source="EIRP assumed 20 W PA + 17 dBi panel = 60 dBm = 30 dBW per sector (typical macro).",
    strengths=["dense, many simultaneous geometries -> multistatic Doppler-only tracking (Ji et al. 2025)", "short baselines -> strong echo"],
    weaknesses=["10 MHz -> 30 m resolution", "sector patterns are down-tilted; rooftop nodes may sit in sidelobes"],
))
_add(Illuminator(
    key="nr_n78", name="5G NR n78 massive-MIMO sector (3.5 GHz)", kind="nr",
    freq_hz=3_500.0e6, bandwidth_hz=100.0e6, eirp_dbw=40.0, typical_distance_m=400.0,
    waveform_note="OFDM; SSB bursts every 20 ms swept over beams; PDSCH traffic-dependent. "
                  "Use SSB/PBCH for a deterministic reference (Jopanya & Osorio 2025).",
    caf_sidelobe_note="Beam-swept illumination makes the reference time-varying; process per SSB beam index.",
    source="EIRP assumed 40 dBW (~70 dBm) per beam, mid-range for 64T64R AAUs.",
    strengths=["100 MHz -> 3 m resolution", "blades are ~1.5 wavelengths -> strong rotor micro-Doppler -> drone/bird discrimination", "Doppler at 3.5 GHz is 6.5x larger than at UHF for the same speed"],
    weaknesses=["beam sweeping = intermittent illumination", "higher path loss; 300-500 m per node", "traffic-dependent power"],
))
_add(Illuminator(
    key="wifi_5g", name="Wi-Fi 5 GHz access point (802.11ax/be, 80 MHz)", kind="wifi",
    freq_hz=5_500.0e6, bandwidth_hz=80.0e6, eirp_dbw=0.0, duty_cycle=0.3, typical_distance_m=60.0,
    waveform_note="Bursty OFDM; the mesh's own 802.11bf-capable backhaul links can be scheduled "
                  "to transmit sensing NDPs so illumination is guaranteed, not opportunistic.",
    source="ISED RSS-247: max 1 W EIRP (30 dBm) in 5.15-5.25 GHz indoor / 5.725-5.85 GHz up to 4 W.",
    strengths=["node-to-node links are under our control (IEEE 802.11bf-2025 sensing)", "80 MHz -> 3.7 m resolution", "fills street canyons below the cellular/TV illumination"],
    weaknesses=["very short range (~100 m)", "low EIRP", "bursty; effective integration time is duty-cycle limited"],
))
_add(Illuminator(
    key="fm_103", name="FM broadcast (CBO-FM 103.3, 100 kW ERP)", kind="fm",
    freq_hz=103.3e6, bandwidth_hz=0.2e6, eirp_dbw=52.2, typical_distance_m=15_700.0,
    source="Typical Ottawa class-C FM ERP 100 kW (CRTC records).",
    strengths=["huge EIRP", "classic PCL illuminator for aircraft"],
    weaknesses=["3 m wavelength: a 30 cm drone is deep in the Rayleigh region (~ -45 dBsm) -> essentially undetectable", "0.2 MHz -> 1.5 km resolution"],
))
_add(Illuminator(
    key="leo_ku", name="LEO broadband user downlink (Starlink Ku-band)", kind="leo",
    freq_hz=11_700.0e6, bandwidth_hz=240.0e6, eirp_dbw=35.0, typical_distance_m=550_000.0,
    waveform_note="OFDM, 240 MHz channels in 10.7-12.7 GHz; frame 1.333 ms with known "
                  "synchronization sequences (Humphreys et al. 2023, UT Austin).",
    caf_sidelobe_note="Satellite motion imposes large, fast-varying Doppler; the reference must be "
                      "tracked per pass. Beam hopping between cells gates the illumination.",
    source="Blazquez-Garcia et al. 2024, IET RSN 10.1049/rsn2.12446; Humphreys et al. arXiv 2210.11578. "
           "EIRP derived from ITU PFD limit ~ -140 dBW/m2/4 kHz over 240 MHz at 550 km.",
    strengths=["illumination from overhead: no urban shadowing on the transmit leg", "240 MHz -> 1.2 m resolution", "blades strongly resonant -> rich micro-Doppler"],
    weaknesses=["weak at the ground: needs a high-gain (dish/array) surveillance antenna -> narrow FOV", "research-grade (TRL 3); our Phase E option, not a Sandbox 2027 claim"],
))


def get_illuminator(key: str) -> Illuminator:
    return ILLUMINATORS[key]
