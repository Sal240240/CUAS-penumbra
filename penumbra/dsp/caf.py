"""Cross-ambiguity function (CAF) for passive radar.

  CAF(tau, f_d) = sum_n s_surv[n] * conj(s_ref[n - tau]) * exp(-j 2 pi f_d n / fs)

Implemented with the "direct FFT" method: for each delay bin, multiply the
surveillance signal by the conjugate delayed reference, then take an FFT over
decimated blocks (batches) to obtain the Doppler axis. Decimation by `n_batch`
limits the unambiguous Doppler to +- fs/(2*n_batch), which we choose to cover the
target Doppler span with margin. This is the standard batches algorithm
(Griffiths & Baker 2017, sec. 8.2) and is what the edge software runs on the GPU.

Output magnitude is normalised so that a unit-amplitude echo at the correct
delay/Doppler integrates to |CAF| = N (coherent gain), i.e. power gain N^2 against
noise power N.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class CafAxes:
    delay_s: np.ndarray
    doppler_hz: np.ndarray
    bistatic_range_m: np.ndarray


def caf_axes(fs: float, n_delay: int, n_batch: int, n_samples: int, c0: float = 299_792_458.0) -> CafAxes:
    n_dop = n_samples // n_batch
    delay = np.arange(n_delay) / fs
    doppler = np.fft.fftshift(np.fft.fftfreq(n_dop, d=n_batch / fs))
    return CafAxes(delay, doppler, delay * c0)


def cross_ambiguity(surv: np.ndarray, ref: np.ndarray, fs: float, n_delay: int, n_batch: int,
                    window: str | bool = "blackmanharris") -> np.ndarray:
    """Return |CAF| as an array of shape (n_delay, n_doppler), Doppler axis fftshifted."""
    surv = np.asarray(surv, dtype=complex)
    ref = np.asarray(ref, dtype=complex)
    n = min(len(surv), len(ref))
    n_dop = n // n_batch
    n_use = n_dop * n_batch
    out = np.empty((n_delay, n_dop), dtype=float)
    if window is True or window == "hann":
        win = np.hanning(n_dop)
    elif window == "blackmanharris":
        from scipy.signal.windows import blackmanharris
        win = blackmanharris(n_dop)          # -92 dB sidelobes: keeps wind clutter out of the target bins
    else:
        win = np.ones(n_dop)
    for k in range(n_delay):
        r = np.zeros(n_use, dtype=complex)
        r[k:] = ref[: n_use - k]
        prod = surv[:n_use] * np.conj(r)
        batched = prod.reshape(n_dop, n_batch).sum(axis=1)   # decimate by summing each batch
        spec = np.fft.fftshift(np.fft.fft(batched * win))
        out[k] = np.abs(spec)
    return out
