"""Micro-Doppler spectrogram and HERM-line (blade flash) analysis."""
from __future__ import annotations
import numpy as np
from scipy.signal import stft


def spectrogram(x: np.ndarray, fs: float, nperseg: int = 256, noverlap: int | None = None):
    """Return (t, f, |S| in dB) with the frequency axis centred (fftshift)."""
    if noverlap is None:
        noverlap = nperseg * 3 // 4
    f, t, s = stft(x, fs=fs, nperseg=nperseg, noverlap=noverlap, return_onesided=False, window="hann")
    f = np.fft.fftshift(f)
    s = np.fft.fftshift(s, axes=0)
    return t, f, 20.0 * np.log10(np.abs(s) + 1e-12)


def herm_line_spacing(x: np.ndarray, fs: float, f_min: float = 20.0, f_max: float = 2000.0) -> float:
    """Estimate the blade-flash repetition frequency from the envelope periodicity.

    The rotor return's magnitude is periodic at N_blades * rpm / 60 Hz; the
    autocorrelation of |x|^2 peaks at that period. Returns the estimated
    line spacing in Hz (0.0 if none found in [f_min, f_max]).
    """
    env = np.abs(np.asarray(x)) ** 2
    env = env - env.mean()
    spec = np.abs(np.fft.rfft(env))
    freqs = np.fft.rfftfreq(len(env), d=1.0 / fs)
    mask = (freqs >= f_min) & (freqs <= f_max)
    if not mask.any():
        return 0.0
    k = np.argmax(spec[mask])
    return float(freqs[mask][k])
