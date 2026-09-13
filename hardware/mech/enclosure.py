"""Parametric IP66-class node enclosure generator.

A two-piece (base + lid) weatherproof box sized around the node electronics
stack (Zynq SoM + RF front-end + OCXO/GNSS board, see hardware/bom/node_bom.csv),
with corner mounting bosses, a gasket channel, and cable-gland bores for
PoE/Ethernet entry. Produces watertight STL solids ready for FDM printing in
an outdoor-rated material (ASA or ASA-CF) or for quoting an injection-mould
tool at volume.

This determines the geometry; it does not replace an actual IP66 ingress test
(a printed gasket channel is a good approximation of, not a certified
substitute for, a compression-moulded silicone gasket — note this to
whoever quotes fabrication).

Usage: python enclosure.py [--out DIR]
"""
from __future__ import annotations
import argparse
import os
import trimesh
import numpy as np

# Interior clearance around the electronics stack (mm) — see hardware/bom/README.md
# for the board stack this is sized to.
INNER_W, INNER_D, INNER_H = 140.0, 90.0, 45.0
WALL = 3.0
LID_H = 12.0
BOSS_DIA = 8.0
BOSS_HOLE_DIA = 3.2  # M3 clearance
GLAND_DIA = 10.0


def _corner_positions(w: float, d: float, inset: float) -> list:
    return [
        (inset, inset), (w - inset, inset),
        (inset, d - inset), (w - inset, d - inset),
    ]


def build_base(out_w: float, out_d: float, base_h: float) -> trimesh.Trimesh:
    base = trimesh.creation.box(extents=[out_w, out_d, base_h])
    base.apply_translation([out_w / 2, out_d / 2, base_h / 2])

    cavity = trimesh.creation.box(extents=[INNER_W, INNER_D, base_h])
    cavity.apply_translation([out_w / 2, out_d / 2, base_h / 2 + WALL])
    base = base.difference(cavity, engine="manifold")

    # Gasket channel: a shallow groove around the rim of the base
    rim_outer = trimesh.creation.box(extents=[out_w - 2 * WALL * 0.6, out_d - 2 * WALL * 0.6, 2.0])
    rim_outer.apply_translation([out_w / 2, out_d / 2, base_h - 1.0])
    rim_inner = trimesh.creation.box(extents=[out_w - 2 * WALL * 1.6, out_d - 2 * WALL * 1.6, 2.2])
    rim_inner.apply_translation([out_w / 2, out_d / 2, base_h - 1.0])
    groove = rim_outer.difference(rim_inner, engine="manifold")
    base = base.difference(groove, engine="manifold")

    # Corner standoff bosses with M3 pilot holes, inside the cavity floor
    for cx, cy in _corner_positions(INNER_W, INNER_D, 8.0):
        ox, oy = (out_w - INNER_W) / 2 + cx, (out_d - INNER_D) / 2 + cy
        boss = trimesh.creation.cylinder(radius=BOSS_DIA / 2, height=10.0, sections=24)
        boss.apply_translation([ox, oy, WALL + 5.0])
        hole = trimesh.creation.cylinder(radius=BOSS_HOLE_DIA / 2, height=12.0, sections=24)
        hole.apply_translation([ox, oy, WALL + 5.0])
        boss = boss.difference(hole, engine="manifold")
        base = base.union(boss, engine="manifold")

    # Cable-gland bore through one end wall for the PoE/Ethernet drop
    gland = trimesh.creation.cylinder(radius=GLAND_DIA / 2, height=WALL * 3, sections=32)
    gland.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    gland.apply_translation([WALL * 1.5, out_d / 2, base_h / 2])
    base = base.difference(gland, engine="manifold")

    return base


def build_lid(out_w: float, out_d: float, lid_h: float) -> trimesh.Trimesh:
    lid = trimesh.creation.box(extents=[out_w, out_d, lid_h])
    lid.apply_translation([out_w / 2, out_d / 2, lid_h / 2])
    skirt_outer = trimesh.creation.box(extents=[out_w - 2 * WALL * 1.1, out_d - 2 * WALL * 1.1, lid_h * 0.6])
    skirt_outer.apply_translation([out_w / 2, out_d / 2, lid_h * 0.3])
    skirt_inner = trimesh.creation.box(extents=[out_w - 2 * WALL * 1.9, out_d - 2 * WALL * 1.9, lid_h * 0.6 + 1.0])
    skirt_inner.apply_translation([out_w / 2, out_d / 2, lid_h * 0.3])
    skirt = skirt_outer.difference(skirt_inner, engine="manifold")
    lid = lid.union(skirt, engine="manifold")

    for cx, cy in _corner_positions(INNER_W, INNER_D, 8.0):
        ox, oy = (out_w - INNER_W) / 2 + cx, (out_d - INNER_D) / 2 + cy
        hole = trimesh.creation.cylinder(radius=BOSS_HOLE_DIA / 2, height=lid_h * 2, sections=24)
        hole.apply_translation([ox, oy, lid_h / 2])
        lid = lid.difference(hole, engine="manifold")

    return lid


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    args = p.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    out_w = INNER_W + 2 * WALL
    out_d = INNER_D + 2 * WALL
    base_h = INNER_H + WALL

    base = build_base(out_w, out_d, base_h)
    lid = build_lid(out_w, out_d, LID_H)

    base_path = os.path.join(args.out, "node_enclosure_base.stl")
    lid_path = os.path.join(args.out, "node_enclosure_lid.stl")
    base.export(base_path)
    lid.export(lid_path)

    print(f"Base: {out_w:.0f} x {out_d:.0f} x {base_h:.0f} mm, watertight={base.is_watertight}, "
          f"volume={base.volume/1000:.1f} cm^3")
    print(f"Lid:  {out_w:.0f} x {out_d:.0f} x {LID_H:.0f} mm, watertight={lid.is_watertight}, "
          f"volume={lid.volume/1000:.1f} cm^3")
    print(f"wrote {base_path}, {lid_path}")
    print("Print in ASA or ASA-CF for UV/weather resistance; the gasket channel is sized for a "
          "3 mm silicone cord, not printed as a seal itself.")


if __name__ == "__main__":
    main()
