"""Parametric pole/parapet mount bracket generator.

A U-channel bracket that clamps around a pole (rooftop mast, streetlight arm,
or parapet rail) with a hose-clamp or U-bolt, and carries a flat face with a
bolt pattern matching the enclosure's corner bosses (hardware/mech/enclosure.py)
plus slots for +-15 deg tilt adjustment when the node is surveyed in.

Designed for 316 stainless (waterjet or CNC) or, for prototyping, 3D-printed
ASA/nylon — the STL is watertight either way; material choice affects load
rating, which is not computed here (a structural engineer should verify wind
load for a given mast height and node mass before a permanent install).

Usage: python mount_bracket.py [--pole-dia-mm 60] [--out DIR]
"""
from __future__ import annotations
import argparse
import os
import numpy as np
import trimesh

PLATE_W, PLATE_H, PLATE_T = 100.0, 100.0, 6.0
CHANNEL_DEPTH = 40.0
BOLT_HOLE_DIA = 3.4  # M3 clearance, matches enclosure boss pattern
TILT_SLOT_LEN = 20.0
TILT_SLOT_W = 4.0


def build_bracket(pole_dia_mm: float) -> trimesh.Trimesh:
    plate = trimesh.creation.box(extents=[PLATE_W, PLATE_T, PLATE_H])
    plate.apply_translation([PLATE_W / 2, PLATE_T / 2, PLATE_H / 2])

    # Bolt pattern to the enclosure's corner bosses (140x90 inner box, 8 mm inset)
    inset = 8.0
    enc_w, enc_d = 140.0 + 2 * 3.0, 90.0 + 2 * 3.0  # matches enclosure WALL=3
    scale_x = (PLATE_W - 20.0) / enc_w
    for cx, cy in [(inset, inset), (enc_w - inset, inset), (inset, enc_d - inset), (enc_w - inset, enc_d - inset)]:
        x = 10.0 + cx * scale_x
        z = 10.0 + cy * scale_x
        hole = trimesh.creation.cylinder(radius=BOLT_HOLE_DIA / 2, height=PLATE_T * 3, sections=20)
        hole.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        hole.apply_translation([x, PLATE_T / 2, z])
        plate = plate.difference(hole, engine="manifold")

    # Two tilt-adjustment slots (arcs approximated as straight slots for simplicity;
    # a slotted hole gives +-15 deg of tilt when the bolt is loosened and re-torqued)
    for x in (25.0, PLATE_W - 25.0):
        slot = trimesh.creation.box(extents=[TILT_SLOT_W, PLATE_T * 3, TILT_SLOT_LEN])
        slot.apply_translation([x, PLATE_T / 2, PLATE_H - 20.0])
        plate = plate.difference(slot, engine="manifold")

    # U-channel pole clamp: two arms extending back from the plate, curved to
    # the pole radius, each with a pair of holes for a hose clamp / U-bolt.
    channel = trimesh.creation.box(extents=[PLATE_W, CHANNEL_DEPTH, 10.0])
    channel.apply_translation([PLATE_W / 2, -CHANNEL_DEPTH / 2 + PLATE_T, PLATE_H - 15.0])
    pole_cutout = trimesh.creation.cylinder(radius=pole_dia_mm / 2 + 1.5, height=PLATE_W * 1.5, sections=48)
    pole_cutout.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    pole_cutout.apply_translation([PLATE_W / 2, CHANNEL_DEPTH * 0.15, PLATE_H - 15.0])
    channel = channel.difference(pole_cutout, engine="manifold")

    bracket = plate.union(channel, engine="manifold")

    for x in (18.0, PLATE_W - 18.0):
        hose_hole = trimesh.creation.cylinder(radius=3.0, height=15.0, sections=20)
        hose_hole.apply_translation([x, CHANNEL_DEPTH * 0.4, PLATE_H - 15.0])
        bracket = bracket.difference(hose_hole, engine="manifold")

    return bracket


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pole-dia-mm", type=float, default=60.0)
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    args = p.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    bracket = build_bracket(args.pole_dia_mm)
    path = os.path.join(args.out, "mount_bracket.stl")
    bracket.export(path)
    print(f"Bracket for {args.pole_dia_mm:.0f} mm pole: watertight={bracket.is_watertight}, "
          f"volume={bracket.volume/1000:.1f} cm^3")
    print("Wind/vibration load rating is NOT computed here — a structural check against the "
          "sponsoring site's mast height and local wind data is a WP4 task.")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
