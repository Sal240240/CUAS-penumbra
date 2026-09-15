"""Coverage analysis: how many (illuminator, node) pairs can see each point of the volume.

For every grid cell at altitude `alt_m` and every pair, the link budget (with
knife-edge losses on both legs) is evaluated for the reference target. A cell is
"covered" when >= `min_pairs` pairs clear the detection threshold: three pairs is
the minimum for a multistatic position fix from bistatic ranges alone; four gives
a velocity vector from Doppler with one redundancy.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..physics import C0, TARGETS, body_rcs, link_budget, path_obstruction, bistatic_geometry
from .scene import Scene


@dataclass
class CoverageResult:
    x: np.ndarray
    y: np.ndarray
    n_pairs: np.ndarray          # (ny, nx) count of pairs above threshold
    best_snr_db: np.ndarray      # (ny, nx)
    covered: np.ndarray          # bool (ny, nx)


def coverage_map(scene: Scene, *, target_key: str = "dji_mavic", alt_m: float = 40.0, step_m: float = 40.0,
                 t_int_s: float = 0.5, threshold_db: float = 13.0, min_pairs: int = 3,
                 illum_kinds=("atsc", "lte", "nr")) -> CoverageResult:
    tg = TARGETS[target_key]
    e = scene.extent_m
    xs = np.arange(-e, e + 1e-9, step_m)
    ys = np.arange(-e, e + 1e-9, step_m)
    n_pairs = np.zeros((len(ys), len(xs)), dtype=int)
    best = np.full((len(ys), len(xs)), -99.0)
    pairs = [(il, nd) for il in scene.illuminators if il.illum.kind in illum_kinds for nd in scene.nodes]
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            p = np.array([x, y, alt_m])
            if any(b.contains_xy(x, y) and b.height > alt_m for b in scene.buildings):
                continue
            for il, nd in pairs:
                # A grid cell can land exactly on an illuminator or node position
                # (both are often round numbers); that geometry is undefined for
                # the bistatic equations and contributes no real information
                # anyway, so skip it rather than crash the whole coverage pass.
                if np.linalg.norm(p - il.pos) < 1.0 or np.linalg.norm(p - nd.pos) < 1.0:
                    continue
                lam = C0 / il.illum.freq_hz
                g = bistatic_geometry(il.pos, nd.pos, p)
                lt, _ = path_obstruction(il.pos, p, scene.buildings, lam)
                lr, _ = path_obstruction(nd.pos, p, scene.buildings, lam)
                lb = link_budget(eirp_dbw=il.illum.eirp_dbw, freq_hz=il.illum.freq_hz, bandwidth_hz=il.illum.bandwidth_hz,
                                 t_int_s=t_int_s * il.illum.duty_cycle, sigma_dbsm=body_rcs(tg, il.illum.freq_hz),
                                 r_t_m=g.r_t, r_r_m=g.r_r, baseline_m=g.baseline, g_r_dbi=nd.surv_gain_dbi,
                                 noise_figure_db=nd.noise_figure_db, extra_path_loss_db=lt + lr,
                                 detection_threshold_db=threshold_db)
                if lb.snr_db >= threshold_db:
                    n_pairs[iy, ix] += 1
                best[iy, ix] = max(best[iy, ix], lb.snr_db)
    return CoverageResult(xs, ys, n_pairs, best, n_pairs >= min_pairs)
