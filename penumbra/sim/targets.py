"""Target kinematics: drones, birds and ground vehicles as sampled trajectories."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
import numpy as np
from ..physics import TARGETS, TargetSignature


@dataclass
class Target:
    target_id: str
    sig: TargetSignature
    pos_fn: Callable[[float], np.ndarray]      # t -> ENU position (m)
    vel_fn: Callable[[float], np.ndarray]      # t -> ENU velocity (m/s)
    rotor_rpm: float = 0.0
    rotor_phase: float = 0.0
    wingbeat_hz: float = 0.0                   # birds
    label: str = "drone"                       # 'drone' | 'bird' | 'vehicle'

    def pos(self, t): return np.asarray(self.pos_fn(t), float)
    def vel(self, t): return np.asarray(self.vel_fn(t), float)


def _linear(p0, v):
    p0 = np.asarray(p0, float); v = np.asarray(v, float)
    return (lambda t: p0 + v * t), (lambda t: v)


def drone_transit(target_id: str, sig_key: str, p0, p1, speed_mps: Optional[float] = None, rpm_scale: float = 1.0) -> Target:
    sig = TARGETS[sig_key]
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    speed = speed_mps if speed_mps is not None else sig.cruise_speed_mps * 0.6
    d = p1 - p0
    v = d / max(np.linalg.norm(d), 1e-9) * speed
    pf, vf = _linear(p0, v)
    return Target(target_id, sig, pf, vf, rotor_rpm=sig.rotor_rpm * rpm_scale * 1.15, label="drone")


def drone_hover(target_id: str, sig_key: str, p, jitter_m: float = 0.3, seed: int = 0) -> Target:
    sig = TARGETS[sig_key]
    p = np.asarray(p, float)
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 2 * np.pi, 3)
    w = np.array([0.4, 0.55, 0.7]) * 2 * np.pi

    def pf(t):
        return p + jitter_m * np.sin(w * t + ph)

    def vf(t):
        return jitter_m * w * np.cos(w * t + ph)
    return Target(target_id, sig, pf, vf, rotor_rpm=sig.rotor_rpm, label="drone")


def drone_orbit(target_id: str, sig_key: str, centre, radius_m: float, speed_mps: float, alt_m: float) -> Target:
    sig = TARGETS[sig_key]
    c = np.asarray(centre, float)
    w = speed_mps / radius_m

    def pf(t):
        return np.array([c[0] + radius_m * np.cos(w * t), c[1] + radius_m * np.sin(w * t), alt_m])

    def vf(t):
        return np.array([-radius_m * w * np.sin(w * t), radius_m * w * np.cos(w * t), 0.0])
    return Target(target_id, sig, pf, vf, rotor_rpm=sig.rotor_rpm * 1.1, label="drone")


def bird_flight(target_id: str, p0, heading_deg: float, speed_mps: float = 11.0, wingbeat_hz: float = 4.0) -> Target:
    sig = TARGETS["bird_gull"]
    th = np.radians(heading_deg)
    v = np.array([speed_mps * np.cos(th), speed_mps * np.sin(th), 0.0])
    p0 = np.asarray(p0, float)

    def pf(t):
        # gentle undulation at the wingbeat rate and a slow meander
        return p0 + v * t + np.array([0.0, 2.0 * np.sin(0.15 * t), 0.4 * np.sin(2 * np.pi * wingbeat_hz * t)])

    def vf(t):
        return v + np.array([0.0, 0.3 * np.cos(0.15 * t), 0.4 * 2 * np.pi * wingbeat_hz * np.cos(2 * np.pi * wingbeat_hz * t)])
    return Target(target_id, sig, pf, vf, wingbeat_hz=wingbeat_hz, label="bird")


def ground_vehicle(target_id: str, p0, p1, speed_mps: float = 12.0) -> Target:
    """A car: strong RCS (~+10 dBsm), zero altitude, constrained to a street."""
    sig = TargetSignature("car", "Passenger car", 1500.0, 4.5, 10.0, 0, 0, 0.0, 0, "n/a", speed_mps, "vehicle")
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    p0[2] = 1.0; p1[2] = 1.0
    d = p1 - p0
    v = d / max(np.linalg.norm(d), 1e-9) * speed_mps
    pf, vf = _linear(p0, v)
    return Target(target_id, sig, pf, vf, label="vehicle")
