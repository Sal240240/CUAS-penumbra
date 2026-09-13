"""Canonical PENUMBRA track schema (internal). C2 adapters translate from this.

Field set follows the program's interface control document: identity, timing,
kinematics with uncertainty, classification with confidence, evidence provenance,
quality and lifecycle status. Everything the operator display or a downstream
C2 system might need is here; nothing is inferred later from partial data.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import numpy as np

STATUS = ("tentative", "confirmed", "coasting", "lost", "archived")
CLASSES = ("unknown", "drone", "bird", "vehicle", "clutter")


@dataclass
class EvidenceItem:
    kind: str                # 'micro_doppler' | 'kinematics' | 'multistatic' | 'persistence' | 'coverage' | 'external'
    statement: str           # human-readable, auditable
    log_odds: float          # contribution to drone-vs-not (natural log)
    weight: float = 1.0      # reliability weight (sensor trust)
    source: str = ""         # node/pair id
    axis: str = "drone"      # 'real' (object vs ghost/clutter) | 'airborne' (vs ground vehicle) | 'drone' (vs bird)


@dataclass
class Track:
    track_id: str
    t_s: float                                  # last update, seconds (UTC epoch or sim time)
    created_s: float
    status: str = "tentative"
    pos_enu_m: np.ndarray = field(default_factory=lambda: np.zeros(3))
    pos_cov_m2: np.ndarray = field(default_factory=lambda: np.eye(3) * 400.0)
    vel_enu_mps: np.ndarray = field(default_factory=lambda: np.zeros(3))
    vel_cov: np.ndarray = field(default_factory=lambda: np.eye(3) * 25.0)
    lat_deg: Optional[float] = None
    lon_deg: Optional[float] = None
    alt_hae_m: Optional[float] = None
    class_probs: Dict[str, float] = field(default_factory=lambda: {c: (1.0 if c == "unknown" else 0.0) for c in CLASSES})
    confidence: float = 0.0                     # calibrated detection confidence (0-1)
    n_hits: int = 0
    n_misses: int = 0
    n_updates: int = 0
    supporting_pairs: List[str] = field(default_factory=list)
    supporting_nodes: List[str] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)
    quality: float = 0.0                        # 0-1: geometry + coverage + residual health
    notes: str = ""

    @property
    def age_s(self) -> float:
        return self.t_s - self.created_s

    @property
    def speed_mps(self) -> float:
        return float(np.linalg.norm(self.vel_enu_mps[:2]))

    @property
    def course_deg(self) -> float:
        vx, vy = self.vel_enu_mps[:2]
        return float((np.degrees(np.arctan2(vx, vy)) + 360.0) % 360.0)   # bearing from north, clockwise

    @property
    def top_class(self) -> str:
        return max(self.class_probs, key=self.class_probs.get)

    def to_dict(self) -> Dict:
        d = asdict(self)
        for k in ("pos_enu_m", "pos_cov_m2", "vel_enu_mps", "vel_cov"):
            d[k] = np.asarray(getattr(self, k)).tolist()
        d["age_s"] = self.age_s
        d["speed_mps"] = self.speed_mps
        d["course_deg"] = self.course_deg
        d["top_class"] = self.top_class
        return d
