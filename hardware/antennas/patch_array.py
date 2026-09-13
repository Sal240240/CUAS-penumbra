"""Microstrip patch antenna array generator (5-6 GHz mesh Wi-Fi sensing link).

Single-patch dimensions from the standard transmission-line model (Balanis,
Antenna Theory: Analysis and Design, 4th ed., sec. 14.2, eq. 14.6-14.19).
Elements are then arranged as a 2x2 or 1x4 array on a common substrate with
half-wavelength (in the substrate) spacing for a broadside beam.

Output: a CSV build sheet (patch W/L, array spacing, substrate spec) and a
top-view SVG. This determines the copper geometry; it does not replace a
full-wave (HFSS/openEMS) simulation of feed-point impedance matching, which
WP4 should run before board fabrication.

Usage: python patch_array.py [--freq-hz 5.5e9] [--er 4.3] [--h-mm 1.6] [--rows 2] [--cols 2]
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import os

C0 = 299_792_458.0


def design_patch(freq_hz: float, er: float, h_m: float) -> dict:
    lam0 = C0 / freq_hz
    w = (C0 / (2.0 * freq_hz)) * math.sqrt(2.0 / (er + 1.0))
    er_eff = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 * (1.0 + 12.0 * h_m / w) ** -0.5
    delta_l = 0.412 * h_m * (er_eff + 0.3) * (w / h_m + 0.264) / ((er_eff - 0.258) * (w / h_m + 0.8))
    l_eff = C0 / (2.0 * freq_hz * math.sqrt(er_eff))
    length = l_eff - 2.0 * delta_l
    # Inset feed point (50 ohm match), eq. 14.65 approximation region:
    # y0 such that R_in(y0) = 50 ohm; the common closed-form estimate is
    # y0 ~ (L/2) * cos^-1(sqrt(50/R_edge)) but R_edge needs the full cavity
    # model — left as a WP4 tuning parameter, not asserted here.
    return {
        "freq_hz": freq_hz, "er": er, "h_mm": h_m * 1000.0,
        "width_mm": w * 1000.0, "length_mm": length * 1000.0,
        "eff_dielectric_const": er_eff, "free_space_wavelength_mm": lam0 * 1000.0,
    }


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freq-hz", type=float, default=5.5e9)
    p.add_argument("--er", type=float, default=4.3, help="substrate relative permittivity (FR4 ~4.3)")
    p.add_argument("--h-mm", type=float, default=1.6, help="substrate thickness, mm")
    p.add_argument("--rows", type=int, default=2)
    p.add_argument("--cols", type=int, default=2)
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    args = p.parse_args(argv)

    patch = design_patch(args.freq_hz, args.er, args.h_mm / 1000.0)
    lam_g = patch["free_space_wavelength_mm"] / math.sqrt(patch["eff_dielectric_const"])
    spacing = 0.5 * lam_g  # half-guided-wavelength element spacing, broadside array

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "patch_array.csv")
    svg_path = os.path.join(args.out, "patch_array.svg")
    json_path = os.path.join(args.out, "patch_array.json")

    board_w = args.cols * patch["width_mm"] + (args.cols - 1) * spacing + 20.0
    board_h = args.rows * patch["length_mm"] + (args.rows - 1) * spacing + 20.0

    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["element", "row", "col", "center_x_mm", "center_y_mm", "width_mm", "length_mm"])
        idx = 1
        for r in range(args.rows):
            for c in range(args.cols):
                cx = 10.0 + patch["width_mm"] / 2.0 + c * (patch["width_mm"] + spacing)
                cy = 10.0 + patch["length_mm"] / 2.0 + r * (patch["length_mm"] + spacing)
                w.writerow([idx, r + 1, c + 1, f"{cx:.2f}", f"{cy:.2f}", f"{patch['width_mm']:.2f}", f"{patch['length_mm']:.2f}"])
                idx += 1

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {board_w:.0f} {board_h:.0f}" font-family="monospace">']
    lines.append(f'<rect width="{board_w:.0f}" height="{board_h:.0f}" fill="#0a0d10"/>')
    lines.append(f'<rect x="2" y="2" width="{board_w-4:.0f}" height="{board_h-4:.0f}" fill="none" stroke="#647882" stroke-dasharray="4 3"/>')
    for r in range(args.rows):
        for c in range(args.cols):
            x = 10.0 + c * (patch["width_mm"] + spacing)
            y = 10.0 + r * (patch["length_mm"] + spacing)
            lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{patch["width_mm"]:.1f}" height="{patch["length_mm"]:.1f}" fill="#5eead4" opacity="0.85"/>')
    lines.append(f'<text x="10" y="{board_h-6:.0f}" fill="#647882" font-size="9">{args.rows}x{args.cols} array, {args.freq_hz/1e9:.2f} GHz, er={args.er}, h={args.h_mm} mm</text>')
    lines.append("</svg>")
    with open(svg_path, "w") as f:
        f.write("\n".join(lines))

    with open(json_path, "w") as f:
        json.dump({**patch, "rows": args.rows, "cols": args.cols, "element_spacing_mm": spacing,
                   "board_w_mm": board_w, "board_h_mm": board_h,
                   "design_reference": "Balanis, Antenna Theory: Analysis and Design, 4th ed., sec. 14.2"}, f, indent=2)

    print(f"Patch: {patch['width_mm']:.1f} x {patch['length_mm']:.1f} mm on er={args.er} h={args.h_mm} mm substrate")
    print(f"Array: {args.rows}x{args.cols}, spacing {spacing:.1f} mm, board {board_w:.0f} x {board_h:.0f} mm")
    print("Feed-point inset distance is NOT computed here (needs full cavity-model or full-wave "
          "tuning) — left as a WP4 task, not asserted.")
    print(f"wrote {csv_path}, {svg_path}, {json_path}")


if __name__ == "__main__":
    main()
