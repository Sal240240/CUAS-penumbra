"""Direct-signal and clutter cancellation: Extensive Cancellation Algorithm (ECA).

Colone, O'Hagan, Lombardo & Baker, "A multistage processing algorithm for
disturbance removal and target detection in passive bistatic radar",
IEEE Trans. AES 45(2), 2009.

The surveillance signal is projected onto the orthogonal complement of the
subspace spanned by delayed copies of the reference (delays 0..K-1 samples):

  s_clean = s_surv - X (X^H X)^-1 X^H s_surv ,   X = [ref, D ref, ..., D^(K-1) ref]

Rather than forming the N x K matrix X (576 MB for a 0.25 s ATSC CPI with 24
taps) we solve the normal equations from correlations computed with FFTs:

  (X^H X)[i, j] = r_rr(i - j)   (Toeplitz; r_rr = autocorrelation of the reference)
  (X^H s)[i]    = r_sr(i)       (cross-correlation of surveillance with reference)

and subtract the K-tap FIR-filtered reference. Memory is O(N), time O(N log N).

Design note (recorded in the red-team ledger): a blocked ECA-B with short blocks
cancels slow targets too — an echo at f_d rotates only f_d * T_block cycles per
block, so T_block must be >> 1/f_d. The notch half-width is ~1/T_block; with the
full CPI (0.25-0.5 s) it is 2-4 Hz, which removes wind-blown clutter but keeps a
drone at 10 Hz. `block` is exposed for slowly-varying multipath but defaults to the
whole record.
"""
from __future__ import annotations
import numpy as np
from scipy.fft import fft, ifft, next_fast_len
from scipy.linalg import solve_toeplitz


def _eca_full(surv: np.ndarray, ref: np.ndarray, k_taps: int) -> np.ndarray:
    n = len(surv)
    nfft = next_fast_len(2 * n)
    r_f = fft(ref, nfft)
    s_f = fft(surv, nfft)
    r_rr = ifft(r_f * np.conj(r_f))[:k_taps]          # autocorrelation, lags 0..K-1
    r_sr = ifft(s_f * np.conj(r_f))[:k_taps]          # cross-correlation, lags 0..K-1
    # Toeplitz system A c = b with A[i,j] = r_rr(i-j): first column r_rr, first row conj(r_rr)
    coef = solve_toeplitz((r_rr, np.conj(r_rr)), r_sr)
    c_f = fft(coef, nfft)
    est = ifft(c_f * r_f)[:n]
    return surv - est


def eca_cancel(surv: np.ndarray, ref: np.ndarray, k_taps: int = 32, block: int | None = None) -> np.ndarray:
    """Remove direct-path and zero-Doppler multipath (delays < k_taps samples) from `surv`."""
    surv = np.asarray(surv, dtype=complex)
    ref = np.asarray(ref, dtype=complex)
    n = min(len(surv), len(ref))
    surv = surv[:n]
    ref = ref[:n]
    if block is None or block >= n:
        return _eca_full(surv, ref, k_taps)
    out = np.empty(n, dtype=complex)
    for start in range(0, n, block):
        stop = min(start + block, n)
        out[start:stop] = _eca_full(surv[start:stop], ref[start:stop], k_taps)
    return out


def eca_cancel_doppler(surv: np.ndarray, ref: np.ndarray, fs: float, k_taps: int = 64,
                       doppler_shifts_hz=(0.0,)) -> np.ndarray:
    """Sequential Doppler-extended ECA (after Colone et al. 2009, 'ECA-CD').

    Clutter that moves slowly (wind-blown vegetation, +-3 Hz at UHF) sits just outside
    the zero-Doppler notch and is 20-40 dB stronger than a micro-UAS echo. Each pass
    cancels the delayed-reference subspace in a frame shifted by one small Doppler
    offset, widening the notch to cover the moving-clutter band while leaving targets
    beyond it untouched. Sequential passes are not jointly orthogonal but converge
    within 1-2 dB of the joint solution for a handful of offsets.
    """
    surv = np.asarray(surv, dtype=complex)
    n = min(len(surv), len(ref))
    t = np.arange(n) / fs
    out = surv[:n].copy()
    for f in doppler_shifts_hz:
        if f == 0.0:
            out = eca_cancel(out, ref, k_taps=k_taps)
        else:
            rot = np.exp(-2j * np.pi * f * t)
            out = eca_cancel(out * rot, ref, k_taps=k_taps) * np.conj(rot)
    return out
