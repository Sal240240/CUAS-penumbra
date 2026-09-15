"""Radar cross-section models for micro/mini UAS across bands.

Anchors (measured, VV):
  DJI Phantom 4 Pro: -15.0 dBsm @15 GHz, -12.4 dBsm @25 GHz
  DJI Mavic Pro:     -17.1 dBsm @15 GHz, -16.2 dBsm @25 GHz
  (Semkin et al., "Compact-Range RCS Measurements and Modeling of Small Drones
   at 15 GHz and 25 GHz", arXiv:1911.05926)
  Phantom-class spread 0.01-0.35 m2 depending on aspect/polarisation/props
  (Quevedo et al. 2019, IET RSN 10.1049/iet-rsn.2018.5646).

Frequency scaling uses the classical sphere-like regions in ka = 2*pi*a/lambda:
  Rayleigh (ka < 1):  sigma ~ (ka)^4 * sigma_res
  resonance (1..10):  sigma ~ sigma_res  (with +-3 dB ripple we ignore)
  optical  (> 10):    sigma ~ sigma_opt
where `a` is the characteristic half-dimension. This is a deliberately simple,
transparent model; WP3 replaces it with measured signatures.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict
from .constants import C0


@dataclass(frozen=True)
class TargetSignature:
    key: str
    name: str
    mass_kg: float
    span_m: float            # motor-to-motor diagonal / characteristic size
    rcs_opt_dbsm: float      # optical-region body RCS (from Ku/K-band measurements)
    n_rotors: int
    n_blades: int            # blades per rotor
    blade_len_m: float       # hub to tip
    rotor_rpm: float         # typical hover RPM
    blade_material: str      # 'carbon' | 'plastic'
    cruise_speed_mps: float
    class_label: str         # 'micro' (<2 kg) or 'mini' (2-15 kg) per DND definition


TARGETS: Dict[str, TargetSignature] = {
    "dji_mini": TargetSignature("dji_mini", "DJI Mini-class (249 g)", 0.249, 0.25, -22.0, 4, 2, 0.062, 9_000, "plastic", 12.0, "micro"),
    "dji_mavic": TargetSignature("dji_mavic", "DJI Mavic-class (0.9 kg)", 0.90, 0.35, -17.0, 4, 2, 0.11, 6_500, "plastic", 18.0, "micro"),
    "fpv_5in": TargetSignature("fpv_5in", "5-inch FPV racer (0.7 kg)", 0.70, 0.22, -20.0, 4, 3, 0.064, 20_000, "plastic", 35.0, "micro"),
    "phantom": TargetSignature("phantom", "DJI Phantom-class (1.4 kg)", 1.40, 0.35, -15.0, 4, 2, 0.12, 6_000, "plastic", 16.0, "micro"),
    "m30": TargetSignature("m30", "DJI Matrice 30-class (3.7 kg)", 3.70, 0.67, -10.0, 4, 2, 0.24, 4_500, "carbon", 20.0, "mini"),
    "hexa_10kg": TargetSignature("hexa_10kg", "10 kg hexacopter", 10.0, 1.10, -5.0, 6, 2, 0.30, 3_500, "carbon", 15.0, "mini"),
    "bird_gull": TargetSignature("bird_gull", "Gull (reference non-target)", 1.0, 0.40, -20.0, 0, 0, 0.30, 180, "n/a", 12.0, "bird"),
}


def _ka(char_size_m: float, freq_hz: float) -> float:
    lam = C0 / freq_hz
    return 2.0 * math.pi * (char_size_m / 2.0) / lam


def _region_factor_db(ka: float) -> float:
    if ka >= 1.0:
        return 0.0
    return 40.0 * math.log10(max(ka, 1e-6))   # (ka)^4 in dB


def body_rcs(target: TargetSignature, freq_hz: float) -> float:
    """Mean body RCS in dBsm at `freq_hz`."""
    return target.rcs_opt_dbsm + _region_factor_db(_ka(target.span_m, freq_hz))


def blade_rcs(target: TargetSignature, freq_hz: float) -> float:
    """Peak (broadside flash) RCS of one blade in dBsm.

    Anchor: blade flash 15-25 dB below body in the resonance/optical region
    (Fioranelli et al. 2015, IET RSN 'Classification of loaded/unloaded micro-drones
    using multistatic radar'), a further ~10 dB lower for dielectric (plastic) blades.
    """
    if target.n_blades == 0:
        return -80.0
    base = target.rcs_opt_dbsm - 20.0 - (10.0 if target.blade_material == "plastic" else 0.0)
    return base + _region_factor_db(_ka(2.0 * target.blade_len_m, freq_hz))
