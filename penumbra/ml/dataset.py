"""Synthetic training data: episodes of multi-pair range-Doppler surfaces with BEV labels.

Each sample = one CPI (frame) of the whole mesh:
  rd      float32 (n_pairs, n_delay, n_doppler)   CAF power, dB above noise floor
  bev_occ float32 (H, W)                           Gaussian heat-map of airborne targets
  bev_cls int64   (H, W)                           0 none, 1 drone, 2 bird, 3 vehicle
  targets list of dicts (id, label, x, y, z, vx, vy, class_key)

Geometry (pair positions, band, delay/Doppler axes) is stored once per episode so
the model can build its backprojection operators from the true scene geometry.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import numpy as np
from ..physics import C0, TARGETS
from ..sim import Scene, Node, PlacedIlluminator, demo_downtown_scene, render_rd_map_fast
from ..sim.targets import Target, drone_transit, drone_hover, drone_orbit, bird_flight, ground_vehicle

CLASS_NAMES = ["none", "drone", "bird", "vehicle"]
CLASS_ID = {n: i for i, n in enumerate(CLASS_NAMES)}
WINDOW_LOSS_DB = 8.0     # Blackman-Harris coherent-gain loss, matches process_pair()


@dataclass
class PairSpec:
    illum_label: str
    illum_key: str
    kind: str
    node_id: str
    tx: np.ndarray
    rx: np.ndarray
    fs: float
    freq_hz: float
    n_delay: int
    n_doppler: int
    max_doppler_hz: float
    t_int: float


def default_pairs(scene: Scene, n_delay: int = 48, n_doppler: int = 96) -> List[PairSpec]:
    """Processing configuration per band: sample rate sets the delay-bin size so that
    48 bins span the surveillance area (ATSC 50 m, LTE 30 m, NR 15 m bins)."""
    cfg = {"atsc": (6e6, 0.5, 200.0), "lte": (10e6, 0.25, 800.0), "nr": (20e6, 0.25, 2400.0)}
    pairs = []
    for il in scene.illuminators:
        if il.illum.kind not in cfg:
            continue
        fs, t_int, max_dop = cfg[il.illum.kind]
        for nd in scene.nodes:
            pairs.append(PairSpec(il.label, il.key, il.illum.kind, nd.node_id, il.pos.copy(), nd.pos.copy(),
                                  fs, il.illum.freq_hz, n_delay, n_doppler, max_dop, t_int))
    return pairs


def bev_axes(extent_m: float, size: int) -> Tuple[np.ndarray, np.ndarray]:
    xs = np.linspace(-extent_m, extent_m, size)
    return xs, xs.copy()


def backprojection_operator(pair: PairSpec, extent_m: float, size: int, alt_m: float = 50.0) -> np.ndarray:
    """(n_delay, size*size) weights mapping bistatic-range bins to BEV cells (ellipse bands).
    Each cell is assigned to the delay bin containing its bistatic range at the nominal
    altitude, with triangular weighting to the neighbouring bins (linear interpolation)."""
    xs, ys = bev_axes(extent_m, size)
    gx, gy = np.meshgrid(xs, ys, indexing="xy")
    p = np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, alt_m)], axis=1)
    r_t = np.linalg.norm(p - pair.tx, axis=1)
    r_r = np.linalg.norm(p - pair.rx, axis=1)
    base = np.linalg.norm(pair.tx - pair.rx)
    rb = r_t + r_r - base
    k = rb / (C0 / pair.fs)
    op = np.zeros((pair.n_delay, size * size), dtype=np.float32)
    k0 = np.floor(k).astype(int)
    frac = k - k0
    for j in range(size * size):
        for kk, w in ((k0[j], 1 - frac[j]), (k0[j] + 1, frac[j])):
            if 0 <= kk < pair.n_delay:
                op[kk, j] = w
    # normalise each delay bin by the number of cells it touches so long ellipses do not dominate
    counts = op.sum(axis=1, keepdims=True)
    return op / np.maximum(counts, 1.0)


def _random_targets(rng: np.random.Generator, extent: float, buildings, n_drones, n_birds, n_vehicles) -> List[Target]:
    tg = []
    keys = ["dji_mini", "dji_mavic", "fpv_5in", "phantom", "m30", "hexa_10kg"]
    for i in range(n_drones):
        key = keys[int(rng.integers(len(keys)))]
        mode = rng.random()
        z = float(rng.uniform(25.0, 120.0))
        if mode < 0.6:
            p0 = rng.uniform(-extent, extent, 2); p1 = rng.uniform(-extent, extent, 2)
            tg.append(drone_transit(f"D{i}", key, [*p0, z], [*p1, z], speed_mps=float(rng.uniform(3.0, 18.0))))
        elif mode < 0.8:
            tg.append(drone_hover(f"D{i}", key, [*rng.uniform(-extent, extent, 2), z], seed=int(rng.integers(1e6))))
        else:
            tg.append(drone_orbit(f"D{i}", key, [*rng.uniform(-extent * 0.6, extent * 0.6, 2)], float(rng.uniform(40, 150)), float(rng.uniform(4, 12)), z))
    for i in range(n_birds):
        tg.append(bird_flight(f"B{i}", [*rng.uniform(-extent, extent, 2), float(rng.uniform(20, 90))], float(rng.uniform(0, 360)),
                              speed_mps=float(rng.uniform(6, 16)), wingbeat_hz=float(rng.uniform(2.5, 9.0))))
    for i in range(n_vehicles):
        # along a street: constant x or constant y at a street coordinate
        if rng.random() < 0.5:
            x = float(rng.uniform(-extent, extent)); p0 = [x, -extent, 0]; p1 = [x, extent, 0]
        else:
            y = float(rng.uniform(-extent, extent)); p0 = [-extent, y, 0]; p1 = [extent, y, 0]
        tg.append(ground_vehicle(f"V{i}", p0, p1, speed_mps=float(rng.uniform(5, 18))))
    return tg


def _labels(targets: List[Target], t: float, extent: float, size: int, sigma_cells: float = 1.2):
    xs, ys = bev_axes(extent, size)
    occ = np.zeros((size, size), np.float32)
    cls = np.zeros((size, size), np.int64)
    rows = []
    for tg in targets:
        p = tg.pos(t); v = tg.vel(t)
        if abs(p[0]) > extent or abs(p[1]) > extent:
            continue
        cx = (p[0] + extent) / (2 * extent) * (size - 1)
        cy = (p[1] + extent) / (2 * extent) * (size - 1)
        gx, gy = np.meshgrid(np.arange(size), np.arange(size), indexing="xy")
        g = np.exp(-0.5 * (((gx - cx) ** 2 + (gy - cy) ** 2) / sigma_cells ** 2))
        if tg.label in ("drone", "bird"):
            occ = np.maximum(occ, g.astype(np.float32))
        cls[g > 0.5] = CLASS_ID[tg.label]
        rows.append({"id": tg.target_id, "label": tg.label, "x": float(p[0]), "y": float(p[1]), "z": float(p[2]),
                     "vx": float(v[0]), "vy": float(v[1]), "key": tg.sig.key})
    return occ, cls, rows


def generate_episode(scene: Scene, pairs: List[PairSpec], *, n_frames: int = 6, frame_dt: float = 0.5,
                     bev_size: int = 32, rng: np.random.Generator | None = None,
                     n_drones: int | None = None, n_birds: int | None = None, n_vehicles: int | None = None) -> Dict:
    rng = rng or np.random.default_rng()
    ext = scene.extent_m
    n_drones = int(rng.integers(0, 4)) if n_drones is None else n_drones
    n_birds = int(rng.integers(0, 3)) if n_birds is None else n_birds
    n_vehicles = int(rng.integers(0, 3)) if n_vehicles is None else n_vehicles
    targets = _random_targets(rng, ext * 0.9, scene.buildings, n_drones, n_birds, n_vehicles)
    il_by_label = {il.label: il for il in scene.illuminators}
    nd_by_id = {nd.node_id: nd for nd in scene.nodes}
    rd = np.zeros((n_frames, len(pairs), pairs[0].n_delay, pairs[0].n_doppler), np.float32)
    occ = np.zeros((n_frames, bev_size, bev_size), np.float32)
    cls = np.zeros((n_frames, bev_size, bev_size), np.int64)
    rows = []
    for f in range(n_frames):
        t0 = f * frame_dt
        for i, ps in enumerate(pairs):
            m, _, _, _ = render_rd_map_fast(scene, il_by_label[ps.illum_label], nd_by_id[ps.node_id], targets,
                                            t0=t0, fs=ps.fs, t_int=ps.t_int, n_delay=ps.n_delay,
                                            n_doppler=ps.n_doppler, max_doppler_hz=ps.max_doppler_hz, rng=rng)
            rd[f, i] = m - WINDOW_LOSS_DB * (m > 3.0)     # apply the window loss to signal cells only
        occ[f], cls[f], r = _labels(targets, t0 + pairs[0].t_int / 2, ext, bev_size)
        rows.append(r)
    return {"rd": rd, "bev_occ": occ, "bev_cls": cls, "targets": rows, "extent_m": ext, "bev_size": bev_size}


def build_dataset(n_episodes: int, seed: int = 0, scene: Scene | None = None, **kw) -> Tuple[Dict, List[PairSpec], Scene]:
    scene = scene or demo_downtown_scene()
    pairs = default_pairs(scene)
    rng = np.random.default_rng(seed)
    eps = [generate_episode(scene, pairs, rng=rng, **kw) for _ in range(n_episodes)]
    data = {
        "rd": np.concatenate([e["rd"] for e in eps]),
        "bev_occ": np.concatenate([e["bev_occ"] for e in eps]),
        "bev_cls": np.concatenate([e["bev_cls"] for e in eps]),
        "episode": np.repeat(np.arange(n_episodes), eps[0]["rd"].shape[0]),
        "targets": [r for e in eps for r in e["targets"]],
        "extent_m": scene.extent_m, "bev_size": eps[0]["bev_size"],
    }
    return data, pairs, scene
