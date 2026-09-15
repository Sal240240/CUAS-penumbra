"""Multi-target tracker over fused BEV detections.

Constant-velocity Kalman filter per track in ENU (x, y, z, vx, vy, vz), global
nearest-neighbour assignment (Hungarian) under a Mahalanobis gate, M-of-N
confirmation and miss-based deletion. Class probabilities are fused across
updates with a forgetting factor so a bird that briefly looks like a drone does
not stay a drone. This is the "fabric" tracker: cheap, deterministic, and easy
to certify. The multistatic UKF (multistatic.py) refines confirmed tracks
against raw bistatic measurements when they are available.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence
import itertools
import numpy as np
from scipy.optimize import linear_sum_assignment
from .schema import Track, CLASSES


@dataclass
class Detection:
    t_s: float
    pos_enu_m: np.ndarray               # (3,) — z may be a nominal altitude when only BEV is known
    pos_cov_m2: np.ndarray              # (3,3)
    confidence: float
    class_probs: Dict[str, float]
    pair_ids: Sequence[str] = ()
    node_ids: Sequence[str] = ()
    micro_doppler: Optional[Dict] = None   # e.g. {"flash_hz": 217, "tip_hz": 1700, "band": "nr"}


@dataclass
class TrackerConfig:
    gate_chi2: float = 13.8            # 3-dof 99.9%
    process_accel_std: float = 3.0     # m/s^2 (micro-UAS manoeuvre)
    confirm_m: int = 3
    confirm_n: int = 4
    max_misses_confirmed: int = 6
    max_misses_tentative: int = 2
    class_forget: float = 0.85


class Tracker:
    def __init__(self, cfg: TrackerConfig | None = None):
        self.cfg = cfg or TrackerConfig()
        self.tracks: List[Track] = []
        self._ids = itertools.count(1)
        self._state: Dict[str, np.ndarray] = {}     # 6-vector
        self._cov: Dict[str, np.ndarray] = {}
        self._hist: Dict[str, List[int]] = {}       # hit/miss history for M-of-N
        self._last_t: Optional[float] = None

    # --- Kalman primitives -------------------------------------------------------
    @staticmethod
    def _f(dt: float) -> np.ndarray:
        f = np.eye(6)
        f[0, 3] = f[1, 4] = f[2, 5] = dt
        return f

    def _q(self, dt: float) -> np.ndarray:
        s = self.cfg.process_accel_std ** 2
        q = np.zeros((6, 6))
        for i in range(3):
            q[i, i] = dt**4 / 4 * s
            q[i, i + 3] = q[i + 3, i] = dt**3 / 2 * s
            q[i + 3, i + 3] = dt**2 * s
        return q

    def predict(self, t_s: float):
        if self._last_t is None:
            self._last_t = t_s
        dt = max(t_s - self._last_t, 0.0)
        f, q = self._f(dt), self._q(dt)
        for tr in self.tracks:
            x, p = self._state[tr.track_id], self._cov[tr.track_id]
            x = f @ x
            p = f @ p @ f.T + q
            self._state[tr.track_id], self._cov[tr.track_id] = x, p
            tr.pos_enu_m, tr.vel_enu_mps = x[:3].copy(), x[3:].copy()
            tr.pos_cov_m2, tr.vel_cov = p[:3, :3].copy(), p[3:, 3:].copy()
        self._last_t = t_s

    # --- association ----------------------------------------------------------------
    def _gate_matrix(self, dets: List[Detection]) -> np.ndarray:
        h = np.zeros((3, 6)); h[0, 0] = h[1, 1] = h[2, 2] = 1.0
        cost = np.full((len(self.tracks), len(dets)), np.inf)
        for i, tr in enumerate(self.tracks):
            x, p = self._state[tr.track_id], self._cov[tr.track_id]
            for j, d in enumerate(dets):
                s = h @ p @ h.T + d.pos_cov_m2
                r = d.pos_enu_m - h @ x
                m2 = float(r @ np.linalg.solve(s, r))
                if m2 <= self.cfg.gate_chi2:
                    cost[i, j] = m2
        return cost

    def update(self, t_s: float, dets: List[Detection]) -> List[Track]:
        self.predict(t_s)
        h = np.zeros((3, 6)); h[0, 0] = h[1, 1] = h[2, 2] = 1.0
        assigned_t, assigned_d = set(), set()
        if self.tracks and dets:
            cost = self._gate_matrix(dets)
            big = cost.copy(); big[~np.isfinite(big)] = 1e6
            rows, cols = linear_sum_assignment(big)
            for i, j in zip(rows, cols):
                if np.isfinite(cost[i, j]):
                    self._kalman_update(self.tracks[i], dets[j], h, t_s)
                    assigned_t.add(i); assigned_d.add(j)
        for i, tr in enumerate(self.tracks):
            if i not in assigned_t:
                tr.n_misses += 1
                self._hist[tr.track_id].append(0)
        for j, d in enumerate(dets):
            if j not in assigned_d:
                self._spawn(d, t_s)
        self._lifecycle()
        return [t for t in self.tracks if t.status in ("tentative", "confirmed", "coasting")]

    def _kalman_update(self, tr: Track, d: Detection, h: np.ndarray, t_s: float):
        x, p = self._state[tr.track_id], self._cov[tr.track_id]
        s = h @ p @ h.T + d.pos_cov_m2
        k = p @ h.T @ np.linalg.inv(s)
        x = x + k @ (d.pos_enu_m - h @ x)
        p = (np.eye(6) - k @ h) @ p
        self._state[tr.track_id], self._cov[tr.track_id] = x, p
        tr.pos_enu_m, tr.vel_enu_mps = x[:3].copy(), x[3:].copy()
        tr.pos_cov_m2, tr.vel_cov = p[:3, :3].copy(), p[3:, 3:].copy()
        tr.t_s = t_s; tr.n_hits += 1; tr.n_updates += 1; tr.n_misses = 0
        self._hist[tr.track_id].append(1)
        a = self.cfg.class_forget
        tr.class_probs = {c: a * tr.class_probs.get(c, 0.0) + (1 - a) * d.class_probs.get(c, 0.0) for c in CLASSES}
        z = sum(tr.class_probs.values()) or 1.0
        tr.class_probs = {c: v / z for c, v in tr.class_probs.items()}
        tr.confidence = 0.8 * tr.confidence + 0.2 * d.confidence
        tr.supporting_pairs = sorted(set(tr.supporting_pairs) | set(d.pair_ids))
        tr.supporting_nodes = sorted(set(tr.supporting_nodes) | set(d.node_ids))

    def _spawn(self, d: Detection, t_s: float):
        tid = f"T{next(self._ids):04d}"
        tr = Track(tid, t_s, t_s, pos_enu_m=d.pos_enu_m.copy(), pos_cov_m2=d.pos_cov_m2.copy(),
                   class_probs=dict(d.class_probs), confidence=d.confidence, n_hits=1, n_updates=1,
                   supporting_pairs=list(d.pair_ids), supporting_nodes=list(d.node_ids))
        x = np.concatenate([d.pos_enu_m, np.zeros(3)])
        p = np.zeros((6, 6)); p[:3, :3] = d.pos_cov_m2; p[3:, 3:] = np.eye(3) * 15.0**2
        self._state[tid], self._cov[tid], self._hist[tid] = x, p, [1]
        self.tracks.append(tr)

    def _lifecycle(self):
        keep = []
        for tr in self.tracks:
            hist = self._hist[tr.track_id][-self.cfg.confirm_n:]
            if tr.status == "tentative":
                if sum(hist) >= self.cfg.confirm_m:
                    tr.status = "confirmed"
                elif tr.n_misses > self.cfg.max_misses_tentative:
                    tr.status = "lost"
            elif tr.status in ("confirmed", "coasting"):
                if tr.n_misses == 0:
                    tr.status = "confirmed"
                elif tr.n_misses > self.cfg.max_misses_confirmed:
                    tr.status = "lost"
                else:
                    tr.status = "coasting"
            if tr.status != "lost":
                keep.append(tr)
            else:
                tr.status = "archived"
        self.tracks = keep
