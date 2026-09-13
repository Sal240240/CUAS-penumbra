"""Multistatic refinement: unscented Kalman filter on raw bistatic range and Doppler.

State x = [x, y, z, vx, vy, vz]. For each associated (illuminator, node) pair i:
  z_i = [ R_t,i + R_r,i - L_i ,  -(v . (u_t,i + u_r,i)) / lambda_i ]
which is nonlinear in position, so we use the UKF (Julier & Uhlmann 2004) rather
than linearising. With >= 3 pairs the position is observable from ranges alone;
Doppler from >= 3 non-collinear pairs observes velocity (Ji et al. 2025 show
sub-metre tracking with Doppler only when receivers are dense).

Measurement noise: sigma_R = 0.3 * c/B (sub-bin interpolation), sigma_f = 0.3 / T.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Sequence
import numpy as np
from ..physics import C0, bistatic_geometry


@dataclass
class BistaticMeasurement:
    pair_id: str
    tx: np.ndarray
    rx: np.ndarray
    wavelength_m: float
    r_bistatic_m: float
    doppler_hz: float
    sigma_r_m: float
    sigma_f_hz: float


def _h(x: np.ndarray, meas: Sequence[BistaticMeasurement]) -> np.ndarray:
    out = []
    for m in meas:
        g = bistatic_geometry(m.tx, m.rx, x[:3])
        fd = -float(np.dot(x[3:], g.u_t) + np.dot(x[3:], g.u_r)) / m.wavelength_m
        out += [g.r_bistatic, fd]
    return np.asarray(out)


class MultistaticUKF:
    def __init__(self, x0: np.ndarray, p0: np.ndarray, accel_std: float = 3.0, alpha=1e-2, beta=2.0, kappa=0.0):
        self.x = np.asarray(x0, float).copy()
        self.p = np.asarray(p0, float).copy()
        self.q_std = accel_std
        n = 6
        self.lam = alpha**2 * (n + kappa) - n
        self.wm = np.full(2 * n + 1, 1.0 / (2 * (n + self.lam)))
        self.wc = self.wm.copy()
        self.wm[0] = self.lam / (n + self.lam)
        self.wc[0] = self.wm[0] + (1 - alpha**2 + beta)

    def _sigma(self):
        n = 6
        s = np.linalg.cholesky((n + self.lam) * (self.p + 1e-9 * np.eye(n)))
        pts = [self.x] + [self.x + s[:, i] for i in range(n)] + [self.x - s[:, i] for i in range(n)]
        return np.asarray(pts)

    def predict(self, dt: float):
        f = np.eye(6); f[0, 3] = f[1, 4] = f[2, 5] = dt
        s2 = self.q_std**2
        q = np.zeros((6, 6))
        for i in range(3):
            q[i, i] = dt**4 / 4 * s2; q[i, i + 3] = q[i + 3, i] = dt**3 / 2 * s2; q[i + 3, i + 3] = dt**2 * s2
        self.x = f @ self.x
        self.p = f @ self.p @ f.T + q

    def update(self, meas: Sequence[BistaticMeasurement]) -> float:
        """Returns the normalised innovation squared (NIS) for consistency monitoring."""
        if not meas:
            return 0.0
        pts = self._sigma()
        z_pts = np.asarray([_h(p, meas) for p in pts])
        z_hat = self.wm @ z_pts
        r = np.diag([v for m in meas for v in (m.sigma_r_m**2, m.sigma_f_hz**2)])
        pzz = r.copy()
        pxz = np.zeros((6, len(z_hat)))
        for i in range(len(pts)):
            dz = z_pts[i] - z_hat
            dx = pts[i] - self.x
            pzz += self.wc[i] * np.outer(dz, dz)
            pxz += self.wc[i] * np.outer(dx, dz)
        k = pxz @ np.linalg.inv(pzz)
        z = np.asarray([v for m in meas for v in (m.r_bistatic_m, m.doppler_hz)])
        inn = z - z_hat
        self.x = self.x + k @ inn
        self.p = self.p - k @ pzz @ k.T
        return float(inn @ np.linalg.solve(pzz, inn))


def geometric_dop(meas: Sequence[BistaticMeasurement], x: np.ndarray) -> float:
    """Range-only geometric dilution of precision at state x (trace of (H^T H)^-1)."""
    rows = []
    for m in meas:
        g = bistatic_geometry(m.tx, m.rx, x[:3])
        rows.append(g.u_t + g.u_r)
    h = np.asarray(rows)
    try:
        return float(np.sqrt(np.trace(np.linalg.inv(h.T @ h))))
    except np.linalg.LinAlgError:
        return float("inf")
