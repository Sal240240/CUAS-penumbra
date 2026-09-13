"""Node and fusion runtimes.

NodeRuntime  (runs on every Penumbra Node, Jetson Orin Nano)
  capture CPI from the SDR (or simulator) for each configured illuminator pair
  -> Doppler-extended ECA -> CAF -> CFAR -> compact RD product + detections + health
  -> publish to the fabric (in-process here; UDP/QUIC in the field build).

FusionRuntime (runs on the gateway / any node elected leader)
  collect RD products for the frame -> PenumbraNet -> calibrated peaks
  -> Tracker -> multistatic UKF refinement (when raw bistatic detections exist)
  -> evidence ledger -> C2 adapters (CoT, SAPIENT).

Sources are pluggable: `SimSource` synthesises IQ from the simulator; a
`SoapySource` (SoapySDR) captures from real hardware when the library is present.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence, Tuple
import json
import time
import numpy as np
from ..sim import Scene, simulate_pair_iq, process_pair, render_rd_map_fast
from ..sim.signal import RdProduct
from ..sim.targets import Target
from ..physics import C0
from ..tracking import Tracker, Detection, Track, BistaticMeasurement, MultistaticUKF
from ..reasoning import Observation, build_ledger, combine
from ..c2 import track_to_cot, detection_report


@dataclass
class NodeHealth:
    node_id: str
    t_s: float
    gnss_locked: bool = True
    pps_jitter_ns: float = 12.0
    ocxo_holdover_s: float = 0.0
    cpu_temp_c: float = 48.0
    buffer_overruns: int = 0
    ref_snr_db: float = 40.0
    trust: float = 1.0                # 0-1, feeds the fusion weights


@dataclass
class PairDetection:
    pair_id: str
    node_id: str
    illum_label: str
    delay_s: float
    doppler_hz: float
    snr_db: float
    flash_hz: float = 0.0
    tip_doppler_hz: float = 0.0


@dataclass
class RdMessage:
    """What a node sends per CPI per pair (RD map quantised to uint8 dB, ~5 kB)."""
    pair_id: str
    node_id: str
    illum_label: str
    t_s: float
    rd_u8: np.ndarray
    detections: List[PairDetection]
    health: NodeHealth


class Source(Protocol):
    def capture(self, illum_label: str, t0: float) -> object: ...


class SimSource:
    def __init__(self, scene: Scene, node_id: str, targets: Sequence[Target], fs_by_kind: Dict[str, float], t_int_by_kind: Dict[str, float], seed: int = 0):
        self.scene, self.targets = scene, targets
        self.node = next(n for n in scene.nodes if n.node_id == node_id)
        self.fs_by_kind, self.t_int_by_kind = fs_by_kind, t_int_by_kind
        self.rng = np.random.default_rng(seed)

    def capture(self, illum_label: str, t0: float):
        il = next(i for i in self.scene.illuminators if i.label == illum_label)
        return simulate_pair_iq(self.scene, il, self.node, self.targets, t0=t0, fs=self.fs_by_kind[il.illum.kind],
                                t_int=self.t_int_by_kind[il.illum.kind], rng=self.rng)


class NodeRuntime:
    def __init__(self, node_id: str, source, illum_labels: Sequence[str], n_delay: int = 48,
                 max_doppler_by_kind: Dict[str, float] | None = None, scene: Scene | None = None):
        self.node_id, self.source, self.illum_labels, self.n_delay = node_id, source, list(illum_labels), n_delay
        self.max_dop = max_doppler_by_kind or {"atsc": 200.0, "lte": 800.0, "nr": 2400.0}
        self.scene = scene
        self.health = NodeHealth(node_id, 0.0)

    def process_frame(self, t0: float) -> List[RdMessage]:
        out = []
        for lab in self.illum_labels:
            frame = self.source.capture(lab, t0)
            kind = next(i.illum.kind for i in self.scene.illuminators if i.label == lab)
            rd: RdProduct = process_pair(frame, n_delay=self.n_delay, max_doppler_hz=self.max_dop[kind])
            dets = []
            rr, cc = np.where(rd.detections)
            for r, c in zip(rr, cc):
                dets.append(PairDetection(f"{lab}/{self.node_id}", self.node_id, lab, float(rd.delay_s[r]),
                                          float(rd.doppler_hz[c]), float(rd.rd_db[r, c])))
            u8 = np.clip(rd.rd_db + 10.0, 0, 255).astype(np.uint8)   # -10..+245 dB above floor
            self.health.t_s = t0
            out.append(RdMessage(f"{lab}/{self.node_id}", self.node_id, lab, t0, u8, dets, self.health))
        return out


@dataclass
class FusionOutput:
    t_s: float
    tracks: List[Track]
    cot: List[str]
    sapient: List[dict]
    heat: Optional[np.ndarray] = None


class FusionRuntime:
    """Simulator-facing fusion: BEV detections from a heat-map (from PenumbraNet when a
    checkpoint is given, otherwise from a physics backprojection of the RD products),
    tracked and explained, then emitted as CoT / SAPIENT."""

    def __init__(self, scene: Scene, pairs, bev_size: int = 32, model=None, threshold: float = 0.5,
                 device: str = "cpu", frames: int = 3):
        from ..ml.dataset import backprojection_operator
        self.scene, self.pairs, self.bev = scene, pairs, bev_size
        self.ops = np.stack([backprojection_operator(p, scene.extent_m, bev_size) for p in pairs])
        self.model, self.threshold, self.device, self.frames = model, threshold, device, frames
        self.tracker = Tracker()
        self.history: List[np.ndarray] = []
        self.hover_s: Dict[str, float] = {}
        self.max_speed: Dict[str, float] = {}
        self.created: Dict[str, float] = {}

    # --- heat-map -------------------------------------------------------------------
    def _heat_physics(self, rd: np.ndarray) -> np.ndarray:
        """Backproject motion energy (outside the notch) of each pair and multiply across
        bands so that only cells supported by several pairs survive (a soft AND)."""
        e = np.clip(rd - 10.0, 0, None)                      # energy above 10 dB
        n_dop = e.shape[-1]
        notch = slice(n_dop // 2 - 2, n_dop // 2 + 3)
        e[..., notch] = 0.0
        per_delay = e.max(axis=-1)                            # (P, D)
        bev = np.einsum("pd,pdh->ph", per_delay, self.ops)    # (P, HW)
        bev = bev.reshape(len(self.pairs), self.bev, self.bev)
        support = (bev > 3.0).sum(axis=0)                     # pairs agreeing
        strength = bev.mean(axis=0)
        heat = np.tanh(strength / 20.0) * np.clip((support - 2) / 4.0, 0, 1)
        return heat.astype(np.float32)

    def _heat_model(self, rd_frames: np.ndarray):
        import torch
        with torch.no_grad():
            out = self.model(torch.as_tensor(rd_frames[None]).to(self.device))
        heat = torch.sigmoid(out["occ"])[0].cpu().numpy()
        cls = torch.softmax(out["cls"], 1)[0].cpu().numpy()
        return heat, cls

    def step(self, t_s: float, rd_by_pair: Dict[str, np.ndarray], pair_dets: Dict[str, List[PairDetection]] | None = None) -> FusionOutput:
        from ..ml.calibration import peaks_from_heatmap, cell_to_xy
        from ..ml.dataset import CLASS_NAMES
        rd = np.stack([rd_by_pair[f"{p.illum_label}/{p.node_id}"] for p in self.pairs]).astype(np.float32)
        self.history.append(rd)
        self.history = self.history[-self.frames:]
        cls_map = None
        if self.model is not None and len(self.history) == self.frames:
            heat, cls_map = self._heat_model(np.stack(self.history))
        else:
            heat = self._heat_physics(rd)
        cell_m = 2 * self.scene.extent_m / (self.bev - 1)
        dets = []
        for r, c, v in peaks_from_heatmap(heat, self.threshold):
            x, y = cell_to_xy(r, c, self.scene.extent_m, self.bev)
            probs = {"drone": 0.5, "bird": 0.3, "vehicle": 0.1, "clutter": 0.1, "unknown": 0.0}
            if cls_map is not None:
                probs = {n: float(cls_map[i, r, c]) for i, n in enumerate(CLASS_NAMES) if n != "none"}
                probs["clutter"] = float(cls_map[0, r, c]); probs["unknown"] = 0.0
            dets.append(Detection(t_s, np.array([x, y, 50.0]), np.diag([cell_m**2, cell_m**2, 30.0**2]), float(v), probs,
                                  pair_ids=[p for p in rd_by_pair]))
        tracks = self.tracker.update(t_s, dets)
        # kinematic bookkeeping for the ledger
        for tr in tracks:
            self.created.setdefault(tr.track_id, t_s)
            self.hover_s[tr.track_id] = self.hover_s.get(tr.track_id, 0.0) + (0.5 if tr.speed_mps < 1.0 and tr.n_updates > 2 else 0.0)
            self.max_speed[tr.track_id] = max(self.max_speed.get(tr.track_id, 0.0), tr.speed_mps if tr.n_updates > 2 else 0.0)
            md = self._micro_doppler_for(tr, pair_dets) if pair_dets else (0.0, 0.0, None)
            obs = Observation(flash_hz=md[0] or None, tip_doppler_hz=md[1] or None, band_freq_hz=md[2],
                              n_pairs=max(3, len(rd_by_pair) // 6), n_bands=3, nis_sigma=1.0,
                              hover_s=self.hover_s[tr.track_id], max_speed_mps=self.max_speed[tr.track_id],
                              alt_agl_m=float(tr.pos_enu_m[2]), alt_sigma_m=float(np.sqrt(tr.pos_cov_m2[2, 2])),
                              persistence_s=t_s - self.created[tr.track_id])
            tr.evidence = build_ledger(obs)
            tr.class_probs = combine(tr.evidence, tr.class_probs)
            tr.quality = float(np.clip(tr.confidence * (1.0 if tr.status == "confirmed" else 0.6), 0, 1))
        confirmed = [t for t in tracks if t.status in ("confirmed", "coasting")]
        return FusionOutput(t_s, tracks, [track_to_cot(t) for t in confirmed],
                            [detection_report(t) for t in confirmed], heat)

    def _micro_doppler_for(self, tr: Track, pair_dets: Dict[str, List[PairDetection]]) -> Tuple[float, float, Optional[float]]:
        """Pick the strongest pair detection whose bistatic range matches the track."""
        best = (0.0, 0.0, None)
        best_snr = -1.0
        for p in self.pairs:
            for d in pair_dets.get(f"{p.illum_label}/{p.node_id}", []):
                rb = np.linalg.norm(tr.pos_enu_m - p.tx) + np.linalg.norm(tr.pos_enu_m - p.rx) - np.linalg.norm(p.tx - p.rx)
                if abs(rb - d.delay_s * C0) < 2 * C0 / p.fs and d.snr_db > best_snr and d.flash_hz > 0:
                    best, best_snr = (d.flash_hz, d.tip_doppler_hz, p.freq_hz), d.snr_db
        return best
