"""Evidence ledger: an auditable classifier of last resort.

The neural fusion network outputs a class distribution; a radar engineer cannot
audit a softmax. This module re-derives the decision from named physical
evidence with explicit log-odds on three axes, so that every published track
carries a justification an operator, a test director or a court can read:

  axis 'real'      : is this a real object (vs ghost intersection / clutter)?
  axis 'airborne'  : given real, is it airborne (vs ground vehicle)?
  axis 'drone'     : given airborne, is it a drone (vs bird)?

  [airborne] +2.5  Altitude 61 +- 8 m AGL: airborne, not a ground vehicle
  [airborne] +2.9  Seen by 5 illuminator/node pairs across 3 band(s)
  [drone   ] +2.8  HERM line spacing 216 Hz consistent with a rotor: 2 blades x 6480 rpm
  [drone   ] +1.9  Hovered 4.5 s with |v| < 1 m/s: birds cannot
  -> P(drone) = 0.99

Log-odds are calibrated against the simulator and re-fitted on field data in WP9.
The ledger and the network are fused as a product of experts with a cap on the
network's contribution so that auditable evidence always dominates a
confident-but-unexplainable neural score.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import math
import numpy as np
from ..physics import TARGETS
from ..tracking.schema import Track, EvidenceItem, CLASSES

ROTOR_RPM_RANGE = (2_500.0, 25_000.0)
BLADES = (2, 3)
BIRD_WINGBEAT_HZ = (1.5, 12.0)
MAX_VEHICLE_ALT_M = 6.0


@dataclass
class Observation:
    flash_hz: Optional[float] = None          # HERM line spacing measured on any pair
    tip_doppler_hz: Optional[float] = None    # micro-Doppler extent
    band_freq_hz: Optional[float] = None
    wingbeat_hz: Optional[float] = None
    n_pairs: int = 0
    n_bands: int = 0
    nis_sigma: Optional[float] = None         # multistatic consistency (normalised innovation, sigma units)
    hover_s: float = 0.0                      # time spent with |v| < 1 m/s while detected
    max_speed_mps: float = 0.0
    max_accel_mps2: float = 0.0
    alt_agl_m: Optional[float] = None
    alt_sigma_m: Optional[float] = None
    on_street_axis: bool = False              # trajectory constrained to a street line
    persistence_s: float = 0.0
    external_rf_detect: Optional[bool] = None # corroboration from an RF-emission sensor, if any


def _rotor_hypotheses(flash_hz: float) -> List[str]:
    out = []
    for nb in BLADES:
        rpm = flash_hz / nb * 60.0
        if ROTOR_RPM_RANGE[0] <= rpm <= ROTOR_RPM_RANGE[1]:
            close = min(TARGETS.values(), key=lambda t: abs(t.rotor_rpm - rpm) if t.n_blades == nb else 1e9)
            out.append(f"{nb} blades x {rpm:.0f} rpm (nearest catalogue: {close.name})")
    return out


def build_ledger(obs: Observation) -> List[EvidenceItem]:
    ev: List[EvidenceItem] = []
    R, A, D = "real", "airborne", "drone"
    # --- micro-Doppler ---------------------------------------------------------------
    if obs.flash_hz:
        hyp = _rotor_hypotheses(obs.flash_hz)
        if hyp:
            ev.append(EvidenceItem("micro_doppler", f"HERM line spacing {obs.flash_hz:.0f} Hz consistent with a rotor: " + "; ".join(hyp), +2.8, axis=D))
            ev.append(EvidenceItem("micro_doppler", "Periodic modulation present: a real moving scatterer, not a ghost", +1.0, axis=R))
        elif BIRD_WINGBEAT_HZ[0] <= obs.flash_hz <= BIRD_WINGBEAT_HZ[1]:
            ev.append(EvidenceItem("micro_doppler", f"Modulation at {obs.flash_hz:.1f} Hz lies in the avian wingbeat band", -2.2, axis=D))
            ev.append(EvidenceItem("micro_doppler", "Periodic modulation present: a real moving scatterer, not a ghost", +1.0, axis=R))
        else:
            ev.append(EvidenceItem("micro_doppler", f"Modulation at {obs.flash_hz:.0f} Hz matches neither rotor nor wingbeat", -0.3, axis=D))
    if obs.tip_doppler_hz and obs.band_freq_hz:
        lam = 299_792_458.0 / obs.band_freq_hz
        tip_mps = obs.tip_doppler_hz * lam / 2.0
        if tip_mps > 40.0:
            ev.append(EvidenceItem("micro_doppler", f"Micro-Doppler extent implies scatterer speed {tip_mps:.0f} m/s: only a propeller does that", +2.0, axis=D))
        elif tip_mps > 4.0:
            ev.append(EvidenceItem("micro_doppler", f"Micro-Doppler extent implies {tip_mps:.0f} m/s: wing-tip regime", -1.0, axis=D))
    if obs.wingbeat_hz:
        ev.append(EvidenceItem("micro_doppler", f"Wingbeat sidebands at {obs.wingbeat_hz:.1f} Hz", -2.5, axis=D))
    # --- kinematics ------------------------------------------------------------------
    if obs.hover_s >= 2.0:
        ev.append(EvidenceItem("kinematics", f"Hovered {obs.hover_s:.1f} s with |v| < 1 m/s: birds cannot (kestrels excepted, briefly)", +1.9, axis=D))
    if obs.max_speed_mps > 25.0:
        ev.append(EvidenceItem("kinematics", f"Peak speed {obs.max_speed_mps:.0f} m/s exceeds sustained flight of local birds", +1.2, axis=D))
    if obs.max_accel_mps2 > 6.0:
        ev.append(EvidenceItem("kinematics", f"Peak acceleration {obs.max_accel_mps2:.1f} m/s^2", +0.8, axis=D))
    if obs.alt_agl_m is not None:
        sig = obs.alt_sigma_m or 15.0
        if obs.alt_agl_m - 2 * sig > MAX_VEHICLE_ALT_M:
            ev.append(EvidenceItem("kinematics", f"Altitude {obs.alt_agl_m:.0f} +- {sig:.0f} m AGL: airborne, not a ground vehicle", +2.5, axis=A))
        elif obs.alt_agl_m + 2 * sig <= MAX_VEHICLE_ALT_M:
            ev.append(EvidenceItem("kinematics", f"Altitude {obs.alt_agl_m:.0f} +- {sig:.0f} m AGL: at street level", -3.0, axis=A))
    if obs.on_street_axis:
        ev.append(EvidenceItem("kinematics", "Trajectory confined to a street axis", -1.5, axis=A))
    # --- multistatic consistency & coverage ------------------------------------------
    if obs.n_pairs >= 3:
        ev.append(EvidenceItem("multistatic", f"Seen by {obs.n_pairs} illuminator/node pairs across {obs.n_bands} band(s)", +0.4 * min(obs.n_pairs, 6) + 0.3 * obs.n_bands, axis=R))
    elif obs.n_pairs > 0:
        ev.append(EvidenceItem("coverage", f"Only {obs.n_pairs} pair(s): position from ellipse intersection is weak", -0.6, axis=R))
    if obs.nis_sigma is not None:
        if obs.nis_sigma < 2.0:
            ev.append(EvidenceItem("multistatic", f"Multistatic residual {obs.nis_sigma:.1f} sigma: measurements agree on one object", +1.0, axis=R))
        else:
            ev.append(EvidenceItem("multistatic", f"Multistatic residual {obs.nis_sigma:.1f} sigma: possible ghost intersection", -1.5, axis=R))
    if obs.persistence_s >= 3.0:
        ev.append(EvidenceItem("persistence", f"Persistent for {obs.persistence_s:.1f} s", +0.6, axis=R))
    if obs.max_speed_mps > 0 and obs.alt_agl_m is None and obs.on_street_axis:
        ev.append(EvidenceItem("kinematics", "No altitude solution and street-constrained motion: treat as ground traffic", -1.0, axis=A))
    if obs.external_rf_detect is True:
        ev.append(EvidenceItem("external", "Independent RF-emission sensor reports a UAS link in this sector", +2.0, weight=0.8, axis=D))
    return ev


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def combine(ledger: List[EvidenceItem], net_probs: Optional[Dict[str, float]] = None,
            prior_real: float = 0.5, prior_airborne: float = 0.5, prior_drone: float = 0.5,
            net_cap_log_odds: float = 2.0) -> Dict[str, float]:
    """Product-of-experts fusion of the three-axis ledger with the network's class distribution.

    P(real) from the 'real' axis, P(airborne | real) from 'airborne', P(drone | airborne)
    from 'drone'. The network's corresponding log-odds are added with a cap so auditable
    evidence always dominates an unexplained neural score.
    """
    def lo(prior, axis):
        return math.log(prior / (1 - prior)) + sum(e.log_odds * e.weight for e in ledger if e.axis == axis)

    lo_r, lo_a, lo_d = lo(prior_real, "real"), lo(prior_airborne, "airborne"), lo(prior_drone, "drone")
    net = net_probs or {}
    if net:
        def capped(p_num, p_den):
            p = p_num / max(p_num + p_den, 1e-6)
            p = min(max(p, 1e-3), 1 - 1e-3)
            return float(np.clip(math.log(p / (1 - p)), -net_cap_log_odds, net_cap_log_odds))
        d, b, v, c = (net.get(k, 0.0) for k in ("drone", "bird", "vehicle", "clutter"))
        lo_r += capped(d + b + v, c)
        lo_a += capped(d + b, v)
        lo_d += capped(d, b)
    p_real, p_air, p_drone = _sigmoid(lo_r), _sigmoid(lo_a), _sigmoid(lo_d)
    return {"unknown": 0.0,
            "drone": p_real * p_air * p_drone,
            "bird": p_real * p_air * (1 - p_drone),
            "vehicle": p_real * (1 - p_air),
            "clutter": 1 - p_real}


def explain(track: Track) -> str:
    lines = [f"Track {track.track_id} [{track.status}] P(drone)={track.class_probs.get('drone', 0):.2f} "
             f"P(bird)={track.class_probs.get('bird', 0):.2f} conf={track.confidence:.2f}"]
    for e in sorted(track.evidence, key=lambda e: (e.axis, -abs(e.log_odds))):
        lines.append(f"  [{e.axis:8s}] {e.log_odds * e.weight:+.1f}  {e.statement}")
    return "\n".join(lines)
