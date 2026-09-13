"""Rotor-blade micro-Doppler (Chen, *The Micro-Doppler Effect in Radar*, 2nd ed., ch. 3).

For a rotor with N blades of length L rotating at Omega rad/s, viewed with the
line of sight at elevation `beta_los` above the rotor plane, the baseband return
(monostatic) is

  s(t) = sum_k L * exp{ j (4 pi / lambda) [ R0 + (L/2) cos(beta_los) cos(Omega t + phi_k) ] }
                * sinc{ (2 L / lambda) cos(beta_los) cos(Omega t + phi_k) }      (Chen eq. 3.17-3.19)

with phi_k = phi0 + 2 pi k / N and sinc(x) = sin(pi x)/(pi x). The sinc term is the
"blade flash": it peaks when a blade is broadside to the LOS. Maximum Doppler is
f_max = 2 Omega L cos(beta_los) / lambda  (monostatic).

Bistatic geometry is folded in through the standard equivalent-monostatic
substitution lambda_eff = lambda / cos(beta_bistatic / 2), which is exact for
the Doppler magnitude and adequate for the flash structure at the bistatic angles
(< 120 deg) our mesh uses.
"""
from __future__ import annotations
import numpy as np


def rotor_return(t: np.ndarray, *, wavelength_m: float, n_blades: int, blade_len_m: float,
                 omega_rad_s: float, phi0: float = 0.0, beta_los_rad: float = 0.0,
                 beta_bistatic_rad: float = 0.0, r0_m: float = 0.0) -> np.ndarray:
    """Complex baseband rotor return (unit-amplitude blade scattering)."""
    lam_eff = wavelength_m / max(np.cos(beta_bistatic_rad / 2.0), 1e-3)
    k = 4.0 * np.pi / lam_eff
    proj = blade_len_m * np.cos(beta_los_rad)
    out = np.zeros_like(t, dtype=complex)
    for b in range(n_blades):
        phi = phi0 + 2.0 * np.pi * b / n_blades
        c = np.cos(omega_rad_s * t + phi)
        arg = (proj / lam_eff) * c          # sinc argument in "cycles"
        out += blade_len_m * np.exp(1j * k * (r0_m + 0.5 * proj * c)) * np.sinc(2.0 * arg)
    return out


def rotor_spectrum_extent(*, wavelength_m: float, blade_len_m: float, rpm: float,
                          beta_los_rad: float = 0.0, beta_bistatic_rad: float = 0.0) -> float:
    """Maximum blade-tip Doppler in Hz (one-sided)."""
    omega = rpm * 2.0 * np.pi / 60.0
    lam_eff = wavelength_m / max(np.cos(beta_bistatic_rad / 2.0), 1e-3)
    return 2.0 * omega * blade_len_m * np.cos(beta_los_rad) / lam_eff


def flash_rate_hz(n_blades: int, rpm: float) -> float:
    """Blade-flash repetition frequency (HERM line spacing)."""
    return n_blades * rpm / 60.0
