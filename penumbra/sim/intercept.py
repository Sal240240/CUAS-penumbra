"""Penumbra Talon engagement simulation: track-cued net-capture interceptor.

Engagement sequence
  1. The fabric publishes a confirmed drone track with position error sigma_p and
     velocity error sigma_v (from the tracker covariance, see tracking/multistatic.py
     geometric_dop and the UKF state covariance).
  2. Talon launches from its dock and flies proportional navigation (PN, N'=4) on the
     fabric track, which is refreshed every `track_dt_s`.
  3. Inside `seeker_acquire_range_m`, the interceptor's own vision-based terminal
     seeker takes over with a much lower position-error floor (`seeker_sigma_m`);
     guidance runs at `guidance_hz` for the remainder of the engagement.
  4. Capture succeeds when miss distance <= `net_radius_m` at closest point of approach.

This is a kinematic PN model (Zarchan, *Tactical and Strategic Missile Guidance*,
7th ed., ch. 2-5), not a 6-DOF airframe simulation: it answers "can the mesh's
tracking accuracy and Talon's speed/turn budget close the loop," not "will this
exact airframe fly." Per RT-09 (docs/10_red_team_ledger.md), this module is a
roadmap/costing tool — Sandbox 2027 does not permit demonstrating a defeat
mechanism, and no engagement described here is flown at that event.

Proportional navigation
  a_cmd = N' * V_c * lambda_dot            (true PN, commanded normal to LOS)
where V_c is closing velocity and lambda_dot the LOS rotation rate. Commanded
acceleration is capped at `max_accel_mps2` (airframe/motor limited).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional
import numpy as np


@dataclass(frozen=True)
class InterceptorConfig:
    speed_mps: float = 32.0                 # 7-inch racer class, sustained
    max_accel_mps2: float = 88.0            # ~9 g turn budget
    nav_gain: float = 4.0                   # PN constant N'
    net_radius_m: float = 1.3               # capture envelope (deployed net + margin)
    guidance_hz: float = 50.0               # onboard guidance loop rate
    track_hz: float = 4.0                   # fabric track update rate (fused, not raw)
    reaction_delay_s: float = 0.30          # launch decision + spin-up
    seeker_acquire_range_m: float = 30.0     # vision seeker takeover range
    seeker_sigma_m: float = 0.4             # terminal seeker position-error floor
    fabric_sigma_p_m: float = 3.0           # mid-course cueing error (fabric track, at handoff range)
    max_flight_time_s: float = 25.0         # battery/endurance ceiling


@dataclass
class EngagementResult:
    captured: bool
    miss_distance_m: float
    time_to_intercept_s: float
    handoff_range_m: float
    seeker_acquired: bool
    interceptor_track: np.ndarray           # (n, 3) ENU positions
    target_track: np.ndarray                # (n, 3) ENU positions
    time: np.ndarray                        # (n,)
    reason: str                             # human-readable outcome note


def _cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.cross(a, b)


def _pn_accel(rel_pos: np.ndarray, rel_vel: np.ndarray, closing_speed: float, nav_gain: float) -> np.ndarray:
    """True PN acceleration command, 3-D, normal to the line of sight.

    lambda_dot (vector form) = (rel_pos x rel_vel) / |rel_pos|^2
    a_cmd = N' * V_c * (lambda_dot x los_hat)   -- keeps the command normal to LOS.
    """
    r2 = float(np.dot(rel_pos, rel_pos))
    if r2 < 1e-6:
        return np.zeros(3)
    los_hat = rel_pos / np.sqrt(r2)
    lambda_dot = _cross(rel_pos, rel_vel) / r2
    a = nav_gain * closing_speed * _cross(lambda_dot, los_hat)
    return a


def simulate_engagement(
    *,
    dock_pos: np.ndarray,
    target_pos_fn: Callable[[float], np.ndarray],
    target_vel_fn: Callable[[float], np.ndarray],
    cfg: InterceptorConfig = InterceptorConfig(),
    handoff_range_m: float = 900.0,
    launch_error_seed: int = 0,
    dt_s: float = 0.02,
) -> EngagementResult:
    """Simulate one PN engagement from cued launch to capture or miss.

    `handoff_range_m` is the target-to-dock range at which the fabric hands off a
    confirmed track and Talon launches (a scenario input, not a physical limit —
    see sim/coverage.py for what range the mesh can actually confirm a track at).
    """
    rng = np.random.default_rng(launch_error_seed)
    dock_pos = np.asarray(dock_pos, float)

    t = 0.0
    interceptor_pos = dock_pos.copy()
    interceptor_vel = np.zeros(3)
    seeker_acquired = False
    positions_i: List[np.ndarray] = [interceptor_pos.copy()]
    positions_t: List[np.ndarray] = [target_pos_fn(0.0)]
    times: List[float] = [0.0]

    next_track_update = cfg.reaction_delay_s
    cued_target_pos = target_pos_fn(0.0) + rng.normal(0.0, cfg.fabric_sigma_p_m, 3)
    cued_target_vel = target_vel_fn(0.0)
    launched = False

    min_range = float("inf")
    prev_miss: Optional[float] = None
    captured = False
    reason = "flight time exceeded before closest approach"

    steps = int(cfg.max_flight_time_s / dt_s)
    for _ in range(steps):
        t += dt_s
        true_target_pos = target_pos_fn(t)
        true_target_vel = target_vel_fn(t)

        # Track refresh: fabric (coarse, periodic) until seeker acquisition, then
        # seeker (fine, every guidance tick) takes over.
        rel_true = true_target_pos - interceptor_pos
        range_now = float(np.linalg.norm(rel_true))
        if not seeker_acquired and range_now <= cfg.seeker_acquire_range_m:
            seeker_acquired = True
        if seeker_acquired:
            cued_target_pos = true_target_pos + rng.normal(0.0, cfg.seeker_sigma_m, 3)
            cued_target_vel = true_target_vel
        elif t >= next_track_update:
            cued_target_pos = true_target_pos + rng.normal(0.0, cfg.fabric_sigma_p_m, 3)
            cued_target_vel = true_target_vel
            next_track_update += 1.0 / cfg.track_hz

        if t < cfg.reaction_delay_s:
            positions_i.append(interceptor_pos.copy())
            positions_t.append(true_target_pos.copy())
            times.append(t)
            continue

        rel_pos = cued_target_pos - interceptor_pos
        rel_vel = cued_target_vel - interceptor_vel

        if not launched:
            # Boost phase: launch along the initial lead line to the cued track,
            # not from a zero-velocity state (which makes the first PN command,
            # a small correction normal to an already-near-collision LOS, define
            # an essentially arbitrary heading).
            interceptor_vel = rel_pos / max(np.linalg.norm(rel_pos), 1e-6) * cfg.speed_mps
            launched = True
        else:
            closing_speed = -float(np.dot(rel_pos, rel_vel)) / max(np.linalg.norm(rel_pos), 1e-6)
            a_cmd = _pn_accel(rel_pos, rel_vel, max(closing_speed, 0.0), cfg.nav_gain)
            a_norm = float(np.linalg.norm(a_cmd))
            if a_norm > cfg.max_accel_mps2:
                a_cmd = a_cmd * (cfg.max_accel_mps2 / a_norm)
            interceptor_vel = interceptor_vel + a_cmd * dt_s
            speed = float(np.linalg.norm(interceptor_vel))
            interceptor_vel = interceptor_vel * (cfg.speed_mps / speed)
        interceptor_pos = interceptor_pos + interceptor_vel * dt_s

        miss_now = float(np.linalg.norm(true_target_pos - interceptor_pos))
        min_range = min(min_range, miss_now)

        positions_i.append(interceptor_pos.copy())
        positions_t.append(true_target_pos.copy())
        times.append(t)

        if miss_now <= cfg.net_radius_m:
            captured = True
            reason = "within net radius at closest approach"
            break
        # Closest point of approach has passed once post-guidance range starts
        # opening again on consecutive steps (compare miss_now to the previous
        # step's miss_now, not to the running minimum, so a transient wobble
        # mid-engagement does not falsely end it).
        if prev_miss is not None and miss_now > prev_miss and t > cfg.reaction_delay_s + 0.5:
            reason = f"closest approach {min_range:.2f} m exceeds net radius {cfg.net_radius_m:.2f} m"
            break
        prev_miss = miss_now

    return EngagementResult(
        captured=captured,
        miss_distance_m=min_range if np.isfinite(min_range) else float("nan"),
        time_to_intercept_s=t,
        handoff_range_m=handoff_range_m,
        seeker_acquired=seeker_acquired,
        interceptor_track=np.asarray(positions_i),
        target_track=np.asarray(positions_t),
        time=np.asarray(times),
        reason=reason,
    )


def monte_carlo_pk(
    *,
    dock_pos: np.ndarray,
    target_pos_fn: Callable[[float], np.ndarray],
    target_vel_fn: Callable[[float], np.ndarray],
    cfg: InterceptorConfig = InterceptorConfig(),
    handoff_range_m: float = 900.0,
    n_runs: int = 200,
) -> dict:
    """Monte Carlo capture probability under cueing-error and seeker-noise draws."""
    outcomes = [
        simulate_engagement(
            dock_pos=dock_pos, target_pos_fn=target_pos_fn, target_vel_fn=target_vel_fn,
            cfg=cfg, handoff_range_m=handoff_range_m, launch_error_seed=seed,
        )
        for seed in range(n_runs)
    ]
    captures = [o.captured for o in outcomes]
    misses = np.array([o.miss_distance_m for o in outcomes])
    return {
        "n_runs": n_runs,
        "pk": float(np.mean(captures)),
        "miss_distance_mean_m": float(np.nanmean(misses)),
        "miss_distance_p90_m": float(np.nanpercentile(misses, 90)),
        "seeker_acquire_rate": float(np.mean([o.seeker_acquired for o in outcomes])),
    }
