"""Urban scene description for the simulator.

Local ENU frame in metres, origin at the centre of the surveillance area
(for the Ottawa demo: Parliament Hill / Wellington St). Buildings are axis-
aligned boxes; this is a *stylised* downtown grid with block sizes and heights
representative of the Ottawa core, not a survey. WP1 replaces it with the
City of Ottawa 3-D building footprint dataset (open data, LiDAR-derived).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import numpy as np
from ..physics import ILLUMINATORS, Illuminator, Box


@dataclass(frozen=True)
class Node:
    node_id: str
    pos: np.ndarray                 # ENU, m (antenna phase centre)
    surv_gain_dbi: float = 6.0
    ref_gain_dbi: float = 10.0
    noise_figure_db: float = 5.0
    bands: tuple = ("atsc", "lte", "nr", "wifi")


@dataclass(frozen=True)
class PlacedIlluminator:
    illum: Illuminator
    pos: np.ndarray                 # ENU, m
    label: str = ""

    @property
    def key(self):
        return self.illum.key


@dataclass
class Scene:
    name: str
    buildings: List[Box]
    nodes: List[Node]
    illuminators: List[PlacedIlluminator]
    extent_m: float = 1200.0         # half-width of the surveillance square
    notes: str = ""

    def wifi_links(self):
        """Node-to-node links usable as 802.11bf sensing pairs (both directions)."""
        out = []
        for i, a in enumerate(self.nodes):
            for b in self.nodes[i + 1:]:
                d = float(np.linalg.norm(a.pos - b.pos))
                if d <= 450.0:
                    out.append((a, b, d))
        return out


def _stylised_blocks(rng: np.random.Generator, n_x: int = 7, n_y: int = 5, block=(110.0, 80.0),
                     street=(22.0, 22.0), h_range=(10.0, 36.0), tall_prob=0.12) -> List[Box]:
    boxes = []
    bw, bh = block
    sw, sh = street
    x_start = -(n_x * (bw + sw)) / 2.0
    y_start = -(n_y * (bh + sh)) / 2.0
    for i in range(n_x):
        for j in range(n_y):
            x0 = x_start + i * (bw + sw)
            y0 = y_start + j * (bh + sh)
            # each block: two or three buildings of differing height
            n_sub = int(rng.integers(2, 4))
            edges = np.linspace(x0, x0 + bw, n_sub + 1)
            for k in range(n_sub):
                h = float(rng.uniform(*h_range))
                if rng.random() < tall_prob:
                    h = float(rng.uniform(45.0, 100.0))
                boxes.append(Box(float(edges[k]), y0, float(edges[k + 1]), y0 + bh, h))
    return boxes


def demo_downtown_scene(seed: int = 7, n_nodes: int = 6) -> Scene:
    """Ottawa-core-like grid, ATSC from Camp Fortune, three LTE and two 5G sectors, six nodes."""
    rng = np.random.default_rng(seed)
    buildings = _stylised_blocks(rng)

    # Camp Fortune (45.509N, 75.861W) relative to Parliament Hill (45.4236N, 75.7009W):
    # dN = +9.5 km, dE = -12.5 km; tower on a 400 m ASL ridge, HAAT 426 m -> ~450 m above downtown ground.
    camp_fortune = np.array([-12_500.0, 9_500.0, 450.0])
    illums = [
        PlacedIlluminator(ILLUMINATORS["cbot_dt"], camp_fortune, "CBOT-DT ch.25"),
        PlacedIlluminator(ILLUMINATORS["chot_dt"], camp_fortune + np.array([60.0, 40.0, -20.0]), "CHOT-DT ch.32"),
        PlacedIlluminator(ILLUMINATORS["lte_700"], np.array([-420.0, 300.0, 38.0]), "LTE sector A"),
        PlacedIlluminator(ILLUMINATORS["lte_700"], np.array([380.0, -260.0, 42.0]), "LTE sector B"),
        PlacedIlluminator(ILLUMINATORS["lte_700"], np.array([60.0, 420.0, 35.0]), "LTE sector C"),
        PlacedIlluminator(ILLUMINATORS["nr_n78"], np.array([-150.0, -330.0, 40.0]), "5G n78 sector D"),
        PlacedIlluminator(ILLUMINATORS["nr_n78"], np.array([300.0, 180.0, 45.0]), "5G n78 sector E"),
    ]

    # Nodes on the taller rooftops ~250-350 m apart, 30-55 m AGL (site survey picks rooftops above the local median)
    ring = np.linspace(0, 2 * np.pi, n_nodes, endpoint=False) + 0.3
    radius = 330.0
    nodes = []
    for i, th in enumerate(ring):
        p = np.array([radius * np.cos(th), radius * 0.8 * np.sin(th), float(rng.uniform(30.0, 55.0))])
        nodes.append(Node(f"N{i+1:02d}", p))
    return Scene(
        name="ottawa-core-stylised",
        buildings=buildings, nodes=nodes, illuminators=illums, extent_m=600.0,
        notes="Stylised grid (7x5 blocks, 110x80 m, mostly 10-36 m tall with 12% towers of 45-100 m, matching the Ottawa core). Illuminator EIRPs from public records; positions approximate.",
    )
