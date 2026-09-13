"""Urban propagation: building occlusion and knife-edge diffraction.

Single knife-edge diffraction loss (ITU-R P.526-15, eq. 31, valid for nu > -0.78):
  J(nu) = 6.9 + 20 log10( sqrt((nu - 0.1)^2 + 1) + nu - 0.1 )  dB
  nu = h * sqrt( 2 (d1 + d2) / (lambda d1 d2) )
where h is the obstacle height above the direct line (negative = clear), d1, d2 the
distances from the edge to each terminal.

Buildings are axis-aligned boxes (x0, y0, x1, y1, height). A path that clips a box
is treated as diffracted over its roof edge nearest the crossing, which is the
dominant mechanism for rooftop/pole-mounted nodes looking into a street canyon.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple
import numpy as np


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    height: float

    def contains_xy(self, x, y) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


def fresnel_nu(h_m: float, d1_m: float, d2_m: float, wavelength_m: float) -> float:
    d1 = max(d1_m, 1e-3)
    d2 = max(d2_m, 1e-3)
    return h_m * math.sqrt(2.0 * (d1 + d2) / (wavelength_m * d1 * d2))


def knife_edge_loss_db(nu: float) -> float:
    if nu <= -0.78:
        return 0.0
    return 6.9 + 20.0 * math.log10(math.sqrt((nu - 0.1) ** 2 + 1.0) + nu - 0.1)


def _clip_segment_to_box_xy(p: np.ndarray, q: np.ndarray, b: Box) -> Optional[Tuple[float, float]]:
    """Liang-Barsky clip of the 2-D segment p->q against the box; returns (t_in, t_out)."""
    d = q[:2] - p[:2]
    t0, t1 = 0.0, 1.0
    for axis, (lo, hi) in enumerate(((b.x0, b.x1), (b.y0, b.y1))):
        if abs(d[axis]) < 1e-12:
            if p[axis] < lo or p[axis] > hi:
                return None
            continue
        ta = (lo - p[axis]) / d[axis]
        tb = (hi - p[axis]) / d[axis]
        t_lo, t_hi = min(ta, tb), max(ta, tb)
        t0, t1 = max(t0, t_lo), min(t1, t_hi)
        if t0 > t1:
            return None
    return t0, t1


def segment_intersects_box(p, q, b: Box) -> bool:
    """True if the 3-D segment passes through the building volume."""
    p = np.asarray(p, float)
    q = np.asarray(q, float)
    clip = _clip_segment_to_box_xy(p, q, b)
    if clip is None:
        return False
    t0, t1 = clip
    z0 = p[2] + t0 * (q[2] - p[2])
    z1 = p[2] + t1 * (q[2] - p[2])
    return min(z0, z1) < b.height


def _edges_along(p: np.ndarray, q: np.ndarray, buildings, wavelength_m: float):
    """Candidate knife-edges: (t_along, h_above_line, d1, d2) for each obstructing roof."""
    length = float(np.linalg.norm(q - p))
    edges = []
    for b in buildings:
        clip = _clip_segment_to_box_xy(p, q, b)
        if clip is None:
            continue
        t0, t1 = clip
        # one edge per building, placed where the line is lowest over the roof
        # (entry or exit face depending on the slope of the path)
        cands = [(tm, b.height - (p[2] + tm * (q[2] - p[2]))) for tm in (t0, t1) if 0.0 < tm < 1.0]
        if not cands:
            continue
        tm, h = max(cands, key=lambda c: c[1])
        if h > 0.0:
            edges.append((tm, h, tm * length, (1.0 - tm) * length))
    return edges


def _deygout(edges, wavelength_m: float, depth: int = 0, max_depth: int = 2) -> float:
    """Deygout (1966) multiple-edge method as in ITU-R P.526-15 sec. 4.5.2:
    take the edge with the largest Fresnel parameter as the main edge, then treat the
    sub-paths on either side of it recursively (limited to `max_depth`)."""
    if not edges:
        return 0.0
    nus = [fresnel_nu(h, d1, d2, wavelength_m) for (_, h, d1, d2) in edges]
    k = int(np.argmax(nus))
    main_nu = nus[k]
    loss = knife_edge_loss_db(main_nu)
    if loss <= 0.0 or depth >= max_depth:
        return loss
    t_main = edges[k][0]
    left = [e for e in edges if e[0] < t_main]
    right = [e for e in edges if e[0] > t_main]
    # sub-paths: distances are re-referenced to the main edge as a terminal
    d_main = edges[k][2]
    total_len = edges[k][2] + edges[k][3]
    left_r = [(e[0], e[1], e[2], d_main - e[2]) for e in left if d_main - e[2] > 1.0]
    right_r = [(e[0], e[1], e[2] - d_main, total_len - e[2]) for e in right if e[2] - d_main > 1.0]
    return loss + _deygout(left_r, wavelength_m, depth + 1, max_depth) + _deygout(right_r, wavelength_m, depth + 1, max_depth)


MAX_EXCESS_LOSS_DB = 45.0   # beyond this, building scatter (ITU-R P.1411 NLOS) dominates diffraction


def path_obstruction(p, q, buildings: Iterable[Box], wavelength_m: float) -> Tuple[float, int]:
    """Excess loss (dB) along p->q via the Deygout multiple-knife-edge method, and the
    number of obstructing buildings. Capped at MAX_EXCESS_LOSS_DB (site-general NLOS
    urban measurements at UHF rarely exceed ~40 dB excess over free space at < 1 km)."""
    p = np.asarray(p, float)
    q = np.asarray(q, float)
    edges = _edges_along(p, q, list(buildings), wavelength_m)
    n_buildings = len({round(e[0], 6) for e in edges})
    if not edges:
        return 0.0, 0
    return min(_deygout(edges, wavelength_m), MAX_EXCESS_LOSS_DB), n_buildings
