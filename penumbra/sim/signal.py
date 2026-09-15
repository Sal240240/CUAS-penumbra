"""Synthetic passive-radar signals for one (illuminator, node) pair.

Two paths produce the same product — a bistatic range-Doppler surface:

* `simulate_pair_iq` + `process_pair`: full IQ synthesis (noise-like reference
  waveform, direct-path leakage, static and wind-blown multipath, thermal noise,
  target echoes with fractional delay, bistatic Doppler and rotor micro-Doppler),
  followed by ECA cancellation, the cross-ambiguity function and 2-D CFAR.
  This is the fidelity path used to validate the fast renderer and the edge DSP.

* `render_rd_map_fast`: draws the expected CAF surface directly from the link
  budget (peak SNRs, positions, HERM lines) on top of an exponential noise
  floor and a zero-Doppler clutter ridge. ~1000x faster; used to generate the
  bulk ML training set. A unit test checks that both paths place a target in the
  same delay/Doppler cell with the same SNR to within 2 dB.

All powers are absolute (watts) so the two paths cannot drift apart.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Sequence
import numpy as np
from ..physics import (C0, K_BOLTZ, T0_K, bistatic_geometry, bistatic_doppler, received_power_w,
                       body_rcs, blade_rcs, path_obstruction, undb, db, rotor_return,
                       rotor_spectrum_extent)
from ..physics.bistatic import direct_path_power_w
from ..physics.microdoppler import flash_rate_hz
from ..dsp import cross_ambiguity, caf_axes, eca_cancel, eca_cancel_doppler, ca_cfar_2d
from .scene import Scene, Node, PlacedIlluminator
from .targets import Target


@dataclass
class EchoTruth:
    target_id: str
    label: str
    delay_s: float
    doppler_hz: float
    p_body_w: float
    p_blade_w: float
    snr_body_db: float          # expected CAF-output SNR of the body return
    snr_blade_db: float
    flash_hz: float
    tip_doppler_hz: float
    obstructed_edges: int
    extra_loss_db: float


@dataclass
class PairFrame:
    illum_key: str
    illum_label: str
    node_id: str
    fs: float
    t_int: float
    freq_hz: float
    p_direct_surv_w: float
    p_noise_w: float
    truths: List[EchoTruth]
    surv: np.ndarray | None = None
    ref: np.ndarray | None = None
    meta: Dict = field(default_factory=dict)


def _fractional_delay(x: np.ndarray, delay_samples: float) -> np.ndarray:
    n = len(x)
    f = np.fft.fftfreq(n)
    return np.fft.ifft(np.fft.fft(x) * np.exp(-2j * np.pi * f * delay_samples))


def _echo_truths(scene: Scene, il: PlacedIlluminator, node: Node, targets: Sequence[Target],
                 t0: float, fs: float, t_int: float, eirp_w: float, p_dir_surv: float,
                 dsi_cancellation_db: float) -> List[EchoTruth]:
    lam = C0 / il.illum.freq_hz
    f_noise = undb(node.noise_figure_db)
    p_noise = K_BOLTZ * T0_K * f_noise * fs
    g_surv = undb(node.surv_gain_dbi)
    out = []
    for tg in targets:
        p = tg.pos(t0 + t_int / 2)
        v = tg.vel(t0 + t_int / 2)
        g = bistatic_geometry(il.pos, node.pos, p)
        loss_t, n_t = path_obstruction(il.pos, p, scene.buildings, lam)
        loss_r, n_r = path_obstruction(node.pos, p, scene.buildings, lam)
        extra = loss_t + loss_r
        sig_body = undb(body_rcs(tg.sig, il.illum.freq_hz))
        sig_blade = undb(blade_rcs(tg.sig, il.illum.freq_hz))
        p_body = received_power_w(eirp_w, 1.0, g_surv, lam, sig_body, g.r_t, g.r_r, undb(3.0 + extra))
        p_blade = received_power_w(eirp_w, 1.0, g_surv, lam, sig_blade, g.r_t, g.r_r, undb(3.0 + extra))
        n_int = fs * t_int * il.illum.duty_cycle
        fd = bistatic_doppler(il.pos, node.pos, p, v, lam)
        if tg.label == "drone" and tg.sig.n_blades > 0:
            flash = flash_rate_hz(tg.sig.n_blades, tg.rotor_rpm)
            tip = rotor_spectrum_extent(wavelength_m=lam, blade_len_m=tg.sig.blade_len_m, rpm=tg.rotor_rpm,
                                        beta_bistatic_rad=g.beta_rad)
        elif tg.label == "bird":
            flash = tg.wingbeat_hz
            tip = 2.0 * 2.5 / lam       # wingtip ~2.5 m/s
        else:
            flash, tip = 0.0, 0.0
        # CAF-output SNR is bounded by the thermal floor and by the DSI residual floor
        # (residual = direct leakage / cancellation, spread over B*T cells) -- see physics/bistatic.py
        floor_w = p_noise / n_int + p_dir_surv * undb(-dsi_cancellation_db) / n_int
        snr_body = p_body / floor_w
        snr_blade = max(p_blade, 1e-30) / floor_w
        out.append(EchoTruth(
            tg.target_id, tg.label, g.r_bistatic / C0, fd, p_body, p_blade,
            float(db(snr_body)), float(db(snr_blade)),
            flash, tip, n_t + n_r, extra))
    return out


def simulate_pair_iq(scene: Scene, il: PlacedIlluminator, node: Node, targets: Sequence[Target], *,
                     t0: float = 0.0, fs: float | None = None, t_int: float = 0.25,
                     rng: np.random.Generator | None = None, n_static_clutter: int = 12,
                     n_wind_clutter: int = 4, ref_snr_db: float = 40.0,
                     surv_front_to_back_db: float = 15.0) -> PairFrame:
    """Synthesise reference and surveillance IQ for one pair over one CPI."""
    rng = rng or np.random.default_rng(0)
    fs = fs or il.illum.bandwidth_hz
    n = int(round(fs * t_int))
    lam = C0 / il.illum.freq_hz
    eirp_w = undb(il.illum.eirp_dbw)
    baseline = float(np.linalg.norm(node.pos - il.pos))
    p_noise = K_BOLTZ * T0_K * undb(node.noise_figure_db) * fs
    p_dir_surv = direct_path_power_w(eirp_w, 1.0, undb(node.surv_gain_dbi - surv_front_to_back_db), lam, baseline)
    truths = _echo_truths(scene, il, node, targets, t0, fs, t_int, eirp_w, p_dir_surv, min(ref_snr_db, 50.0))

    t = np.arange(n) / fs
    ref_clean = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2.0)   # unit power
    if il.illum.duty_cycle < 1.0:      # bursty illuminator: gate the waveform
        burst = 2e-3
        gate = ((t % (burst / il.illum.duty_cycle)) < burst).astype(float)
        ref_clean = ref_clean * gate

    surv = np.sqrt(p_dir_surv) * ref_clean.copy()
    # static multipath: delays 0.2..6 us, 15..45 dB below the direct leakage, zero Doppler
    for _ in range(n_static_clutter):
        d = rng.uniform(0.2e-6, 6e-6) * fs
        a = np.sqrt(p_dir_surv * undb(-rng.uniform(15.0, 45.0)))
        surv += a * np.exp(1j * rng.uniform(0, 2 * np.pi)) * _fractional_delay(ref_clean, d)
    # wind-blown clutter: small Doppler spread +-3 Hz
    for _ in range(n_wind_clutter):
        d = rng.uniform(0.3e-6, 4e-6) * fs
        a = np.sqrt(p_dir_surv * undb(-rng.uniform(35.0, 55.0)))
        fd = rng.uniform(-3.0, 3.0)
        surv += a * _fractional_delay(ref_clean, d) * np.exp(2j * np.pi * fd * t)
    # targets
    for tg, tr in zip(targets, truths):
        delayed = _fractional_delay(ref_clean, tr.delay_s * fs)
        carrier = np.exp(2j * np.pi * tr.doppler_hz * t)
        body = np.sqrt(tr.p_body_w) * delayed * carrier
        surv += body
        if tr.p_blade_w > 0 and tg.label == "drone":
            g = bistatic_geometry(il.pos, node.pos, tg.pos(t0 + t_int / 2))
            rot = np.zeros(n, dtype=complex)
            for r in range(tg.sig.n_rotors):
                rot += rotor_return(t, wavelength_m=lam, n_blades=tg.sig.n_blades, blade_len_m=tg.sig.blade_len_m,
                                    omega_rad_s=tg.rotor_rpm * 2 * np.pi / 60.0 * (1.0 + 0.02 * r),
                                    phi0=tg.rotor_phase + r * 1.1, beta_los_rad=np.radians(15.0),
                                    beta_bistatic_rad=g.beta_rad)
            rot /= (tg.sig.blade_len_m * tg.sig.n_blades * tg.sig.n_rotors)   # unit peak
            surv += np.sqrt(tr.p_blade_w) * delayed * carrier * rot
        elif tg.label == "bird":
            wing = 1.0 + 0.6 * np.cos(2 * np.pi * tg.wingbeat_hz * t)
            # wing return: amplitude modulated at the wingbeat, frequency modulated by the wingtip velocity
            phase = (0.5 * tr.tip_doppler_hz / max(tg.wingbeat_hz, 0.1)) * np.sin(2 * np.pi * tg.wingbeat_hz * t)
            surv += np.sqrt(tr.p_body_w) * 0.3 * delayed * carrier * wing * np.exp(1j * phase)
    surv += np.sqrt(p_noise / 2.0) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    ref = ref_clean + np.sqrt(undb(-ref_snr_db) / 2.0) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    return PairFrame(il.key, il.label, node.node_id, fs, t_int, il.illum.freq_hz, p_dir_surv, p_noise,
                     truths, surv, ref, meta={"t0": t0})


@dataclass
class RdProduct:
    rd_db: np.ndarray            # (n_delay, n_doppler) power in dB relative to noise floor
    detections: np.ndarray       # bool mask
    delay_s: np.ndarray
    doppler_hz: np.ndarray
    bistatic_range_m: np.ndarray
    noise_floor_db: float


def process_pair(frame: PairFrame, *, n_delay: int = 48, n_batch: int | None = None,
                 eca_taps: int | None = None, pfa: float = 1e-5, max_doppler_hz: float = 400.0) -> RdProduct:
    """ECA -> CAF -> CFAR. `eca_taps` must span the whole clutter delay extent: multipath
    left uncancelled beyond the last tap leaks into every delay bin through the reference
    autocorrelation sidelobes (-10log10(N) dB) and buries targets 60 dB weaker than it."""
    if n_batch is None:
        n_batch = max(1, int(frame.fs / (2 * max_doppler_hz)))
    if eca_taps is None:
        eca_taps = n_delay + 16
    # Doppler-extended cancellation: notch 0 and +-1/T (covers wind-blown clutter to ~+-2/T)
    d = 1.0 / frame.t_int
    clean = eca_cancel_doppler(frame.surv, frame.ref, frame.fs, k_taps=eca_taps,
                               doppler_shifts_hz=(0.0, d, -d))
    caf = cross_ambiguity(clean, frame.ref, frame.fs, n_delay, n_batch)
    ax = caf_axes(frame.fs, n_delay, n_batch, len(clean))
    power = caf ** 2
    floor = float(np.median(power))
    rd_db = 10 * np.log10(power / floor + 1e-12)
    # The ECA notch leaves a residual zero-Doppler ridge; blank it to the noise level before
    # CFAR so it neither trains the threshold nor triggers detections (notch half-width ~ 1.5/T).
    notch = np.abs(ax.doppler_hz) <= 2.5 / frame.t_int
    p_cfar = power.copy()
    p_cfar[:, notch] = floor
    det, _, _ = ca_cfar_2d(p_cfar, guard=1, train=4, pfa=pfa)
    det[:, notch] = False
    return RdProduct(rd_db, det, ax.delay_s, ax.doppler_hz, ax.bistatic_range_m, float(10 * np.log10(floor)))


def render_rd_map_fast(scene: Scene, il: PlacedIlluminator, node: Node, targets: Sequence[Target], *,
                       t0: float = 0.0, fs: float | None = None, t_int: float = 0.25, n_delay: int = 48,
                       n_doppler: int = 128, max_doppler_hz: float = 400.0, rng: np.random.Generator | None = None,
                       clutter_residual_db: float = 12.0, dsi_cancellation_db: float = 40.0,
                       surv_front_to_back_db: float = 15.0) -> tuple[np.ndarray, List[EchoTruth], np.ndarray, np.ndarray]:
    """Expected CAF power surface in dB above the noise floor, plus truths and axes."""
    rng = rng or np.random.default_rng(0)
    fs = fs or il.illum.bandwidth_hz
    eirp_w = undb(il.illum.eirp_dbw)
    baseline = float(np.linalg.norm(node.pos - il.pos))
    p_dir_surv = direct_path_power_w(eirp_w, 1.0, undb(node.surv_gain_dbi - surv_front_to_back_db), lam := C0 / il.illum.freq_hz, baseline)
    truths = _echo_truths(scene, il, node, targets, t0, fs, t_int, eirp_w, p_dir_surv, dsi_cancellation_db)
    delay = np.arange(n_delay) / fs
    doppler = np.linspace(-max_doppler_hz, max_doppler_hz, n_doppler, endpoint=False)
    df = doppler[1] - doppler[0]
    # exponential noise floor (|CAF|^2 of noise is chi-square with 2 dof)
    p = rng.exponential(1.0, size=(n_delay, n_doppler))
    # zero-Doppler clutter ridge after ECA: residual decaying with delay, Doppler-spread by wind
    for k in range(n_delay):
        amp = undb(clutter_residual_db - 2.0 * k) if k < 12 else 0.0
        if amp > 0:
            p[k] += amp * np.exp(-0.5 * (doppler / 2.5) ** 2) * rng.exponential(1.0, n_doppler)
    dd, ff = np.meshgrid(np.arange(n_delay), np.arange(n_doppler), indexing="ij")
    for tr in truths:
        kd = tr.delay_s * fs
        kf = (tr.doppler_hz + max_doppler_hz) / df
        if not (0 <= kd < n_delay):
            continue
        body = undb(tr.snr_body_db)
        blob = np.exp(-0.5 * ((dd - kd) / 0.7) ** 2 - 0.5 * ((ff - kf) / 0.9) ** 2)
        p += body * blob
        if tr.snr_blade_db > 0 and tr.flash_hz > 0 and tr.label == "drone":
            # HERM lines: spectral lines every flash_hz out to +-tip Doppler, decaying
            n_lines = int(min(tr.tip_doppler_hz / max(tr.flash_hz, 1.0), 40))
            for m in range(1, n_lines + 1):
                for sgn in (-1, 1):
                    fk = kf + sgn * m * tr.flash_hz / df
                    if 0 <= fk < n_doppler:
                        w = undb(tr.snr_blade_db) / n_lines * (1.0 - 0.6 * m / n_lines)
                        p += w * np.exp(-0.5 * ((dd - kd) / 0.7) ** 2 - 0.5 * ((ff - fk) / 0.9) ** 2)
        elif tr.label == "bird" and tr.snr_body_db > 0:
            # wingbeat: narrow modulation sidebands within +-15 Hz
            for m in (1, 2):
                for sgn in (-1, 1):
                    fk = kf + sgn * m * tr.flash_hz / df
                    if 0 <= fk < n_doppler:
                        p += body * 0.15 / m * np.exp(-0.5 * ((dd - kd) / 0.7) ** 2 - 0.5 * ((ff - fk) / 0.9) ** 2)
    return 10 * np.log10(p + 1e-12), truths, delay, doppler
