"""Log-periodic dipole array (LPDA) design generator.

Classical Carrel design equations (R. Carrel, "The Design of Log-Periodic
Dipole Antennas," IRE International Convention Record, vol. 9, pt. 1,
pp. 61-75, 1961; also Balanis, Antenna Theory: Analysis and Design, 4th ed.,
sec. 11.6). Given a frequency range and a scale factor tau, this computes
element count, lengths, spacings, and boom length, and emits:

  - a CSV build sheet any machinist can cut from (element #, length, position)
  - a dimensioned top-view SVG drawing
  - a JSON summary (gain estimate, boom length, apex half-angle)

This is fabrication-ready in the sense RT-10 (docs/10_red_team_ledger.md)
defines: geometry is fully determined by the script, not sketched.
Manufacturing tolerance, element diameter/tubing selection, and boom material
are noted but left to the fabricator.

Usage: python logperiodic.py <band> [--tau 0.88] [--sigma 0.05] [--out DIR]
  band: 'uhf' (470-608 MHz, ATSC ch.14-36) or 'cellular' (700 MHz-3.8 GHz)
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import os
from dataclasses import dataclass

C0 = 299_792_458.0  # m/s


@dataclass
class LpdaDesign:
    band: str
    f_low_hz: float
    f_high_hz: float
    tau: float
    sigma: float
    alpha_deg: float
    n_elements: int
    lengths_mm: list
    positions_mm: list  # distance from the apex (feed end) to each element
    spacings_mm: list  # gap between consecutive elements
    boom_length_mm: float
    estimated_gain_dbi: float


BANDS = {
    "uhf": (470.0e6, 608.0e6, "PENUMBRA UHF surveillance/reference antenna (ATSC ch.14-36 coverage)"),
    "cellular": (700.0e6, 3_800.0e6, "PENUMBRA LTE/5G surveillance/reference antenna"),
}


def design_lpda(f_low_hz: float, f_high_hz: float, tau: float = 0.88, sigma: float = 0.05) -> LpdaDesign:
    lam_max = C0 / f_low_hz
    lam_min = C0 / f_high_hz
    l1 = lam_max / 2.0  # longest (lowest-frequency) half-wave dipole
    l_min = lam_min / 2.0  # shortest (highest-frequency) half-wave dipole

    n = 1 + math.ceil(math.log(l_min / l1) / math.log(tau))
    n = max(n, 3)

    alpha_rad = math.atan((1.0 - tau) / (4.0 * sigma))

    lengths = [l1 * (tau ** i) for i in range(n)]
    # Distance from the apex (the virtual vertex beyond the shortest element,
    # where all elements would converge if extended) to element i:
    #   R_i = L_i / (2 tan(alpha))
    # Element 0 (longest, lowest frequency) is farthest from the apex; element
    # N-1 (shortest, highest frequency) is closest to it and is the feed end.
    r_from_apex = [length / (2.0 * math.tan(alpha_rad)) for length in lengths]
    boom_length = r_from_apex[0] - r_from_apex[-1]
    # Re-reference to the feed end (element N-1) at 0 mm, increasing toward
    # the longest element — the distance a machinist actually marks out from.
    positions = [r - r_from_apex[-1] for r in r_from_apex]
    spacings = [positions[i] - positions[i + 1] for i in range(n - 1)]

    # Rough order-of-magnitude gain estimate only: published LPDA design charts
    # (e.g. Balanis sec. 11.6) show gain rising with sigma and with tau over the
    # sigma=0.03-0.21, tau=0.8-0.95 design region, typically spanning ~6-9 dBi.
    # This is a coarse linear fit to that trend, not a digitized curve — treat
    # it as a starting point for a method-of-moments simulation, not a spec.
    estimated_gain_dbi = 6.0 + 40.0 * sigma - 10.0 * (0.9 - tau)

    return LpdaDesign(
        band="", f_low_hz=f_low_hz, f_high_hz=f_high_hz, tau=tau, sigma=sigma,
        alpha_deg=math.degrees(alpha_rad), n_elements=n,
        lengths_mm=[l * 1000.0 for l in lengths],
        positions_mm=[p * 1000.0 for p in positions],
        spacings_mm=[s * 1000.0 for s in spacings],
        boom_length_mm=boom_length * 1000.0,
        estimated_gain_dbi=estimated_gain_dbi,
    )


def write_csv(design: LpdaDesign, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["element", "length_mm", "position_from_feed_end_mm", "spacing_to_next_mm", "diameter_mm_suggested"])
        for i in range(design.n_elements):
            spacing = design.spacings_mm[i] if i < len(design.spacings_mm) else ""
            # rule of thumb: element diameter ~1/150 of the longest element for rigidity without excess mass
            dia = design.lengths_mm[0] / 150.0
            w.writerow([i + 1, f"{design.lengths_mm[i]:.2f}", f"{design.positions_mm[i]:.2f}",
                        f"{spacing:.2f}" if spacing != "" else "", f"{dia:.2f}"])


def write_svg(design: LpdaDesign, path: str, label: str) -> None:
    boom = design.boom_length_mm
    max_len = design.lengths_mm[0]
    margin = 40
    w = boom + 2 * margin
    h = max_len + 2 * margin
    scale_note = f"1 unit = 1 mm; boom {boom:.0f} mm; longest element {max_len:.0f} mm"
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" font-family="monospace">']
    lines.append(f'<rect width="{w:.0f}" height="{h:.0f}" fill="#0a0d10"/>')
    lines.append(f'<text x="10" y="20" fill="#5eead4" font-size="12">{label}</text>')
    lines.append(f'<text x="10" y="{h-10:.0f}" fill="#647882" font-size="10">{scale_note}</text>')
    cy = h / 2.0
    # boom line
    lines.append(f'<line x1="{margin:.1f}" y1="{cy:.1f}" x2="{margin+boom:.1f}" y2="{cy:.1f}" stroke="#9fb0b8" stroke-width="2"/>')
    for i in range(design.n_elements):
        x = margin + design.positions_mm[i]
        half = design.lengths_mm[i] / 2.0
        lines.append(f'<line x1="{x:.1f}" y1="{cy-half:.1f}" x2="{x:.1f}" y2="{cy+half:.1f}" stroke="#e7edf0" stroke-width="1.6"/>')
    lines.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("band", choices=list(BANDS.keys()))
    p.add_argument("--tau", type=float, default=0.88)
    p.add_argument("--sigma", type=float, default=0.05)
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    args = p.parse_args(argv)

    f_low, f_high, label = BANDS[args.band]
    design = design_lpda(f_low, f_high, args.tau, args.sigma)
    design.band = args.band

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, f"lpda_{args.band}.csv")
    svg_path = os.path.join(args.out, f"lpda_{args.band}.svg")
    json_path = os.path.join(args.out, f"lpda_{args.band}.json")

    write_csv(design, csv_path)
    write_svg(design, svg_path, label)
    with open(json_path, "w") as f:
        json.dump({
            "band": design.band, "f_low_hz": design.f_low_hz, "f_high_hz": design.f_high_hz,
            "tau": design.tau, "sigma": design.sigma, "apex_half_angle_deg": design.alpha_deg,
            "n_elements": design.n_elements, "boom_length_mm": design.boom_length_mm,
            "estimated_gain_dbi": design.estimated_gain_dbi,
            "design_reference": "Carrel 1961 (IRE Int'l Conv. Record); Balanis, Antenna Theory 4th ed. sec. 11.6",
        }, f, indent=2)

    print(f"{label}")
    print(f"  {design.n_elements} elements, tau={design.tau}, sigma={design.sigma}, "
          f"apex half-angle={design.alpha_deg:.1f} deg")
    print(f"  boom length: {design.boom_length_mm:.1f} mm, "
          f"longest element: {design.lengths_mm[0]:.1f} mm, "
          f"shortest: {design.lengths_mm[-1]:.1f} mm")
    print(f"  estimated gain: {design.estimated_gain_dbi:.1f} dBi (coarse trend estimate — verify by simulation)")
    print(f"  wrote {csv_path}, {svg_path}, {json_path}")


if __name__ == "__main__":
    main()
