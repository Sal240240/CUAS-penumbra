"""Penumbra Talon airframe generator — roadmap item, not a Sandbox deliverable.

A 7-inch-class X-frame quadcopter airframe (center plate + four arms sized for
7-inch propellers), generated as a flat-plate design suitable for CNC or
water-jet cutting from 3 mm carbon-fibre or G10 sheet. This is the airframe
only: motors, ESCs, flight controller, battery, vision seeker, and the net/
parachute payload mechanism are BOM line items (see docs/10_red_team_ledger.md
RT-09) that mount to this plate, not part of this geometry.

Per RT-09 and the applicant guide for the urban sandbox, no defeat mechanism
is demonstrated at Sandbox 2027 — this exists for the costed long-term
roadmap (hardware/bom/) only.

Usage: python airframe.py [--prop-in 7.0] [--out DIR]
"""
from __future__ import annotations
import argparse
import math
import os
import numpy as np
import trimesh

PLATE_THICKNESS_MM = 3.0
ARM_WIDTH_MM = 22.0
MOTOR_MOUNT_HOLE_DIA = 3.2
MOTOR_MOUNT_PATTERN_MM = 16.0  # common 2306/2207-class motor bolt spacing
CENTER_PLATE_SIZE_MM = 90.0


def build_airframe(prop_in: float) -> trimesh.Trimesh:
    prop_mm = prop_in * 25.4
    # On an X-frame, adjacent motors are 90 deg apart around the center, at
    # arm length L from it; their separation is L*sqrt(2). Require that to
    # clear the prop diameter with a 10% margin: L = prop_mm*1.10/sqrt(2).
    # Wheelbase (diagonal, motor to opposite motor) is then 2L.
    arm_center_len_mm = prop_mm * 1.10 / math.sqrt(2.0)
    wheelbase_mm = 2.0 * arm_center_len_mm
    arm_len_mm = arm_center_len_mm - CENTER_PLATE_SIZE_MM / 2.0 * math.sqrt(2.0) / 2.0

    center = trimesh.creation.box(extents=[CENTER_PLATE_SIZE_MM, CENTER_PLATE_SIZE_MM, PLATE_THICKNESS_MM])
    center.apply_translation([0, 0, PLATE_THICKNESS_MM / 2])

    # Standoff/electronics mounting holes in a 30.5 mm square (common FC pattern)
    for sx in (-1, 1):
        for sy in (-1, 1):
            hole = trimesh.creation.cylinder(radius=1.6, height=PLATE_THICKNESS_MM * 3, sections=16)
            hole.apply_translation([sx * 15.25, sy * 15.25, PLATE_THICKNESS_MM / 2])
            center = center.difference(hole, engine="manifold")

    frame = center
    for angle_deg in (45, 135, 225, 315):
        theta = math.radians(angle_deg)
        arm = trimesh.creation.box(extents=[arm_len_mm, ARM_WIDTH_MM, PLATE_THICKNESS_MM])
        # position the arm so its inner edge meets the center plate corner and
        # it points outward at this angle
        arm.apply_translation([arm_len_mm / 2, 0, PLATE_THICKNESS_MM / 2])
        rot = trimesh.transformations.rotation_matrix(theta, [0, 0, 1])
        arm.apply_transform(rot)
        offset = (CENTER_PLATE_SIZE_MM / 2.0 - 5.0)
        arm.apply_translation([offset * math.cos(theta), offset * math.sin(theta), 0])
        frame = frame.union(arm, engine="manifold")

        # Motor mounting bolt pattern at the tip of each arm
        tip_x = (offset + arm_len_mm - 8.0) * math.cos(theta)
        tip_y = (offset + arm_len_mm - 8.0) * math.sin(theta)
        for hx in (-1, 1):
            for hy in (-1, 1):
                lx = hx * MOTOR_MOUNT_PATTERN_MM / 2
                ly = hy * MOTOR_MOUNT_PATTERN_MM / 2
                # rotate the local hole offset into the arm's frame
                rx = lx * math.cos(theta) - ly * math.sin(theta)
                ry = lx * math.sin(theta) + ly * math.cos(theta)
                hole = trimesh.creation.cylinder(radius=MOTOR_MOUNT_HOLE_DIA / 2, height=PLATE_THICKNESS_MM * 3, sections=16)
                hole.apply_translation([tip_x + rx, tip_y + ry, PLATE_THICKNESS_MM / 2])
                frame = frame.difference(hole, engine="manifold")

    return frame, wheelbase_mm


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prop-in", type=float, default=7.0)
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    args = p.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    frame, wheelbase = build_airframe(args.prop_in)
    path = os.path.join(args.out, "talon_airframe.stl")
    frame.export(path)
    print(f"Talon airframe: {args.prop_in:.0f}-inch prop class, wheelbase {wheelbase:.0f} mm, "
          f"watertight={frame.is_watertight}, mass-equivalent volume={frame.volume/1000:.1f} cm^3 "
          f"(x density of chosen sheet material)")
    print("Roadmap item per RT-09 — not fabricated or flown for the Sandbox 2027 demonstration.")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
