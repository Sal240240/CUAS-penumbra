"""Bistatic radar geometry and the passive-radar link budget.

Conventions
-----------
Positions are 3-vectors in a local ENU frame (metres). Velocities in m/s.
Illuminator (transmitter) T, receiver node R, target P.

  R_t = |P - T|, R_r = |P - R|, L = |T - R|  (baseline)
  bistatic range  R_b = R_t + R_r - L        (delay relative to the direct path)
  bistatic Doppler f_d = -(1/lambda) * d(R_t + R_r)/dt
                       = -(1/lambda) * v . (u_t + u_r)
  where u_t = (P - T)/R_t and u_r = (P - R)/R_r.

Radar equation (Willis, *Bistatic Radar*, 2nd ed., eq. 4.1):
  P_r = P_t G_t G_r lambda^2 sigma_b / ((4 pi)^3 R_t^2 R_r^2 L_sys)

After cross-ambiguity processing over an integration time T_int with signal
bandwidth B, the coherent processing gain is B*T_int. Two floors bound
detectability (Griffiths & Baker, *An Introduction to Passive Radar*, 2017):

  1. thermal:  SNR_th = P_r T_int / (k T0 F)
  2. direct-signal-interference (DSI) residual:
       the direct path arrives at P_dir = P_t G_t G_r,ref lambda^2 / ((4 pi L)^2),
       cancellation removes C dB of it, and the CAF sidelobe floor of a noise-like
       signal sits 10log10(B T_int) dB below its own peak, so
       SNR_dsi = (P_r / P_dir) * 10^(C/10) * (B T_int)   [as a ratio]

The usable SNR is the smaller of the two. This is what the documentation, the
simulator and the web calculator all use, so they cannot disagree.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
from .constants import C0, K_BOLTZ, T0_K


def db(x):
    return 10.0 * np.log10(x)


def undb(x_db):
    return 10.0 ** (np.asarray(x_db, dtype=float) / 10.0)


@dataclass(frozen=True)
class BistaticGeometry:
    r_t: float          # transmitter-target distance, m
    r_r: float          # receiver-target distance, m
    baseline: float     # transmitter-receiver distance, m
    r_bistatic: float   # R_t + R_r - L, m
    beta_rad: float     # bistatic angle at the target, rad
    u_t: np.ndarray     # unit vector T->P
    u_r: np.ndarray     # unit vector R->P


def bistatic_geometry(tx: np.ndarray, rx: np.ndarray, target: np.ndarray) -> BistaticGeometry:
    tx = np.asarray(tx, float); rx = np.asarray(rx, float); target = np.asarray(target, float)
    d_t = target - tx
    d_r = target - rx
    r_t = float(np.linalg.norm(d_t))
    r_r = float(np.linalg.norm(d_r))
    if r_t == 0.0 or r_r == 0.0:
        raise ValueError("target coincides with transmitter or receiver")
    baseline = float(np.linalg.norm(rx - tx))
    u_t = d_t / r_t
    u_r = d_r / r_r
    # bistatic angle: angle at the target between the two look directions
    cos_beta = float(np.clip(np.dot(-u_t, -u_r), -1.0, 1.0))
    beta = math.acos(cos_beta)
    return BistaticGeometry(r_t, r_r, baseline, r_t + r_r - baseline, beta, u_t, u_r)


def bistatic_range(tx, rx, target) -> float:
    return bistatic_geometry(tx, rx, target).r_bistatic


def bistatic_angle(tx, rx, target) -> float:
    return bistatic_geometry(tx, rx, target).beta_rad


def bistatic_doppler(tx, rx, target, velocity, wavelength_m: float) -> float:
    """Bistatic Doppler shift in Hz. Positive when the sum-range is decreasing."""
    g = bistatic_geometry(tx, rx, target)
    v = np.asarray(velocity, float)
    range_rate = float(np.dot(v, g.u_t) + np.dot(v, g.u_r))
    return -range_rate / wavelength_m


def received_power_w(p_t_w, g_t, g_r, wavelength_m, sigma_m2, r_t, r_r, loss_lin=1.0) -> float:
    """Bistatic radar equation. All linear units."""
    return (p_t_w * g_t * g_r * wavelength_m**2 * sigma_m2) / ((4 * math.pi) ** 3 * r_t**2 * r_r**2 * loss_lin)


def direct_path_power_w(p_t_w, g_t, g_r_ref, wavelength_m, baseline_m) -> float:
    """Friis free-space power on the reference (direct-path) channel."""
    return p_t_w * g_t * g_r_ref * (wavelength_m / (4 * math.pi * baseline_m)) ** 2


@dataclass(frozen=True)
class LinkBudget:
    p_r_dbw: float
    p_direct_dbw: float
    snr_thermal_db: float
    snr_dsi_db: float
    snr_db: float                 # min of the two floors
    processing_gain_db: float
    range_resolution_m: float     # c / B (bistatic, along the sum-range)
    doppler_resolution_hz: float  # 1 / T_int
    detectable: bool


def link_budget(*, eirp_dbw: float, freq_hz: float, bandwidth_hz: float, t_int_s: float,
                sigma_dbsm: float, r_t_m: float, r_r_m: float, baseline_m: float,
                g_r_dbi: float = 6.0, g_r_ref_dbi: float = 10.0, noise_figure_db: float = 5.0,
                system_loss_db: float = 3.0, dsi_cancellation_db: float = 50.0,
                extra_path_loss_db: float = 0.0, detection_threshold_db: float = 13.0) -> LinkBudget:
    """Full passive-radar link budget for one illuminator/node/target triple.

    eirp_dbw            illuminator EIRP toward the target (dBW). ERP + 2.15 dB.
    extra_path_loss_db  diffraction / foliage / building penetration on the two legs.
    detection_threshold_db  13 dB ~ Pd 0.9 at Pfa 1e-6 for a Swerling-1-ish target.
    """
    lam = C0 / freq_hz
    p_t = undb(eirp_dbw)
    p_r = received_power_w(p_t, 1.0, undb(g_r_dbi), lam, undb(sigma_dbsm), r_t_m, r_r_m,
                           undb(system_loss_db + extra_path_loss_db))
    p_dir = direct_path_power_w(p_t, 1.0, undb(g_r_ref_dbi), lam, baseline_m)
    gp = bandwidth_hz * t_int_s
    snr_th = p_r * t_int_s / (K_BOLTZ * T0_K * undb(noise_figure_db))
    snr_dsi = (p_r / p_dir) * undb(dsi_cancellation_db) * gp
    snr = min(snr_th, snr_dsi)
    return LinkBudget(
        p_r_dbw=float(db(p_r)), p_direct_dbw=float(db(p_dir)),
        snr_thermal_db=float(db(snr_th)), snr_dsi_db=float(db(snr_dsi)), snr_db=float(db(snr)),
        processing_gain_db=float(db(gp)), range_resolution_m=C0 / bandwidth_hz,
        doppler_resolution_hz=1.0 / t_int_s, detectable=bool(db(snr) >= detection_threshold_db),
    )


def max_detection_range_m(*, r_t_m: float, threshold_db: float = 13.0, r_r_grid=None, **kw) -> float:
    """Largest receiver-target range at which link_budget() clears the threshold.
    r_t_m is held fixed (illuminator far away compared with node-target ranges)."""
    if r_r_grid is None:
        r_r_grid = np.geomspace(20.0, 20_000.0, 400)
    best = 0.0
    for r_r in r_r_grid:
        lb = link_budget(r_t_m=r_t_m, r_r_m=float(r_r), detection_threshold_db=threshold_db, **kw)
        if lb.snr_db >= threshold_db:
            best = float(r_r)
    return best
