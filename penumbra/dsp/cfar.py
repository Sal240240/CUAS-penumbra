"""Two-dimensional cell-averaging CFAR on a range-Doppler power surface."""
from __future__ import annotations
import numpy as np
from scipy.ndimage import uniform_filter


def ca_cfar_2d(power: np.ndarray, guard: int = 2, train: int = 8, pfa: float = 1e-5):
    """Return (detections_bool, threshold, alpha).

    The threshold factor alpha for CA-CFAR with N training cells is
      alpha = N (pfa^(-1/N) - 1)
    (Richards, *Fundamentals of Radar Signal Processing*, eq. 6.24).
    """
    p = np.asarray(power, dtype=float)
    size_out = 2 * (guard + train) + 1
    size_in = 2 * guard + 1
    sum_out = uniform_filter(p, size=size_out, mode="reflect") * size_out**2
    sum_in = uniform_filter(p, size=size_in, mode="reflect") * size_in**2
    n_train = size_out**2 - size_in**2
    noise = (sum_out - sum_in) / n_train
    alpha = n_train * (pfa ** (-1.0 / n_train) - 1.0)
    thr = alpha * noise
    return p > thr, thr, alpha
