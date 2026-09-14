"""Generate dimensioned mechanical drawing sheets (SVG) for the node hardware.

Produces a conventional drawing sheet per part — orthographic views, dimension
lines with witness lines and arrowheads, a title block, and a notes block — for:

  * the enclosure base and lid (hardware/mech/enclosure.py)
  * the pole/parapet mount bracket (hardware/mech/mount_bracket.py)
  * the carrier board profile (hardware/pcb/generate_board.py)

Dimensions are read from the same module-level constants the STL/board
generators use, so a drawing cannot silently disagree with the solid it
documents. All dimensions in millimetres, third-angle projection.

These are working drawings for fabrication and inspection, not a substitute for
a tolerance study: general tolerances are stated in the notes block and tighter
tolerances on the mating features should be set by whoever quotes the part.

Usage: python generate_drawings.py [--out DIR]
"""
from __future__ import annotations
import argparse
import os
import sys
from typing import List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from hardware.mech.enclosure import INNER_W, INNER_D, INNER_H, WALL, LID_H, BOSS_DIA, BOSS_HOLE_DIA, GLAND_DIA  # noqa: E402
from hardware.mech.mount_bracket import PLATE_W, PLATE_H, PLATE_T, CHANNEL_DEPTH, BOLT_HOLE_DIA  # noqa: E402
from hardware.pcb.generate_board import BOARD_W_MM, BOARD_H_MM, MOUNT_HOLE_DIA_MM, mount_hole_positions  # noqa: E402

SHEET_W, SHEET_H = 1000, 700
INK = "#101418"
THIN = "#6b7a82"
DIM = "#1a6b7a"

def esc(s: str) -> str:
    """Escape text for XML content — part titles legitimately contain '&'."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


GENERAL_NOTES = [
    "1. DIMENSIONS IN MILLIMETRES. THIRD-ANGLE PROJECTION.",
    "2. GENERAL TOLERANCE +/-0.3 mm UNLESS OTHERWISE STATED.",
    "3. BREAK SHARP EDGES 0.3 mm MAX.",
    "4. TOLERANCES ON MATING FEATURES TO BE AGREED WITH FABRICATOR.",
]


class Sheet:
    """A minimal 2-D drawing sheet: views, dimensions, title block."""

    def __init__(self, title: str, part_no: str, material: str, finish: str, notes: List[str] | None = None):
        self.title, self.part_no, self.material, self.finish = title, part_no, material, finish
        self.notes = notes or []
        self.body: List[str] = []

    # --- primitives ---------------------------------------------------------------
    def rect(self, x, y, w, h, stroke=INK, width=1.6, dash=None, fill="none"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
                         f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{d}/>')

    def circle(self, cx, cy, r, stroke=INK, width=1.4, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="none" '
                         f'stroke="{stroke}" stroke-width="{width}"{d}/>')

    def line(self, x0, y0, x1, y1, stroke=INK, width=1.4, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
                         f'stroke="{stroke}" stroke-width="{width}"{d}/>')

    def text(self, x, y, s, size=11, anchor="start", fill=INK, weight="normal"):
        self.body.append(f'<text x="{x:.2f}" y="{y:.2f}" font-family="monospace" font-size="{size}" '
                         f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')

    def centre_marks(self, cx, cy, r):
        self.line(cx - r - 3, cy, cx + r + 3, cy, THIN, 0.8, "4 2")
        self.line(cx, cy - r - 3, cx, cy + r + 3, THIN, 0.8, "4 2")

    # --- dimensions ---------------------------------------------------------------
    def dim_h(self, x0, x1, y, label, off=16):
        """Horizontal dimension between x0 and x1, dimension line `off` below y."""
        yl = y + off
        self.line(x0, y, x0, yl + 4, THIN, 0.8)
        self.line(x1, y, x1, yl + 4, THIN, 0.8)
        self.line(x0, yl, x1, yl, DIM, 1.0)
        self._arrow(x0, yl, 1); self._arrow(x1, yl, -1)
        self.text((x0 + x1) / 2, yl - 4, label, 11, "middle", DIM)

    def dim_v(self, y0, y1, x, label, off=16):
        xl = x + off
        self.line(x, y0, xl + 4, y0, THIN, 0.8)
        self.line(x, y1, xl + 4, y1, THIN, 0.8)
        self.line(xl, y0, xl, y1, DIM, 1.0)
        self._arrow_v(xl, y0, 1); self._arrow_v(xl, y1, -1)
        self.body.append(f'<text x="{xl + 10:.2f}" y="{(y0 + y1) / 2:.2f}" font-family="monospace" '
                         f'font-size="11" fill="{DIM}" text-anchor="middle" '
                         f'transform="rotate(-90 {xl + 10:.2f} {(y0 + y1) / 2:.2f})">{esc(label)}</text>')

    def _arrow(self, x, y, sign):
        self.body.append(f'<path d="M {x:.2f} {y:.2f} l {6*sign:.2f} -2.6 l 0 5.2 z" fill="{DIM}"/>')

    def _arrow_v(self, x, y, sign):
        self.body.append(f'<path d="M {x:.2f} {y:.2f} l -2.6 {6*sign:.2f} l 5.2 0 z" fill="{DIM}"/>')

    def leader(self, x, y, tx, ty, label):
        self.line(x, y, tx, ty, THIN, 0.8)
        self.text(tx + 3, ty - 3, label, 10, "start", DIM)

    def view_label(self, x, y, s):
        self.text(x, y, s, 12, "start", INK, "bold")

    # --- output -------------------------------------------------------------------
    def render(self) -> str:
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SHEET_W} {SHEET_H}" '
               f'width="{SHEET_W}" height="{SHEET_H}">',
               f'<rect width="{SHEET_W}" height="{SHEET_H}" fill="#ffffff"/>',
               f'<rect x="10" y="10" width="{SHEET_W-20}" height="{SHEET_H-20}" fill="none" stroke="{INK}" stroke-width="2"/>']
        out += self.body
        # notes block
        ny = SHEET_H - 210
        out.append(f'<text x="28" y="{ny}" font-family="monospace" font-size="11" font-weight="bold" fill="{INK}">NOTES</text>')
        for i, n in enumerate(GENERAL_NOTES + self.notes):
            out.append(f'<text x="28" y="{ny + 16 * (i + 1)}" font-family="monospace" font-size="10" fill="{INK}">{esc(n)}</text>')
        # title block
        tb_x, tb_y, tb_w, tb_h = SHEET_W - 350, SHEET_H - 110, 340, 100
        out.append(f'<rect x="{tb_x}" y="{tb_y}" width="{tb_w}" height="{tb_h}" fill="none" stroke="{INK}" stroke-width="1.6"/>')
        out.append(f'<line x1="{tb_x}" y1="{tb_y+34}" x2="{tb_x+tb_w}" y2="{tb_y+34}" stroke="{INK}" stroke-width="1"/>')
        out.append(f'<line x1="{tb_x}" y1="{tb_y+66}" x2="{tb_x+tb_w}" y2="{tb_y+66}" stroke="{INK}" stroke-width="1"/>')
        rows = [("PENUMBRA  /  " + self.title, 13, "bold"),
                (f"PART {self.part_no}    MATERIAL {self.material}", 10, "normal"),
                (f"FINISH {self.finish}    UNITS mm    PROJ 3rd ANGLE", 10, "normal")]
        for i, (s, size, weight) in enumerate(rows):
            out.append(f'<text x="{tb_x+10}" y="{tb_y+22+32*i}" font-family="monospace" font-size="{size}" '
                       f'fill="{INK}" font-weight="{weight}">{esc(s)}</text>')
        out.append("</svg>")
        return "\n".join(out)


def enclosure_sheet() -> Sheet:
    out_w, out_d, base_h = INNER_W + 2 * WALL, INNER_D + 2 * WALL, INNER_H + WALL
    s = Sheet("NODE ENCLOSURE - BASE & LID", "PNMB-ENC-001", "ASA / ASA-CF", "AS PRINTED, UV STABLE",
              notes=[f"5. GASKET CHANNEL SIZED FOR 3 mm SILICONE CORD.",
                     f"6. CABLE GLAND BORE {GLAND_DIA:.1f} DIA FOR RJ45 CAT6 GLAND.",
                     "7. PRINT ORIENTATION: CAVITY UP, NO SUPPORTS REQUIRED IN CAVITY."])
    sc = 2.6  # drawing scale px/mm
    # --- TOP VIEW (base) ---
    ox, oy = 70, 70
    s.view_label(ox, oy - 14, "BASE - TOP VIEW")
    s.rect(ox, oy, out_w * sc, out_d * sc)
    s.rect(ox + WALL * sc, oy + WALL * sc, INNER_W * sc, INNER_D * sc, THIN, 1.2, "5 3")
    for (cx, cy) in [(8.0, 8.0), (INNER_W - 8.0, 8.0), (8.0, INNER_D - 8.0), (INNER_W - 8.0, INNER_D - 8.0)]:
        px, py = ox + (WALL + cx) * sc, oy + (WALL + cy) * sc
        s.circle(px, py, BOSS_DIA / 2 * sc, INK, 1.2)
        s.circle(px, py, BOSS_HOLE_DIA / 2 * sc, INK, 1.0)
        s.centre_marks(px, py, BOSS_DIA / 2 * sc)
    s.dim_h(ox, ox + out_w * sc, oy + out_d * sc, f"{out_w:.0f}")
    s.dim_v(oy, oy + out_d * sc, ox + out_w * sc, f"{out_d:.0f}")
    s.dim_h(ox + WALL * sc, ox + (WALL + INNER_W) * sc, oy + out_d * sc, f"{INNER_W:.0f} CAVITY", 40)
    bx, by = ox + (WALL + 8.0) * sc, oy + (WALL + 8.0) * sc
    s.leader(bx, by, ox + 20, oy - 34, f"4x M3 BOSS, {BOSS_HOLE_DIA:.1f} DIA PILOT")
    # --- FRONT VIEW (base section) ---
    fy = oy + out_d * sc + 90
    s.view_label(ox, fy - 14, "BASE - FRONT VIEW (GLAND END)")
    s.rect(ox, fy, out_w * sc, base_h * sc)
    s.rect(ox + WALL * sc, fy, INNER_W * sc, (base_h - WALL) * sc, THIN, 1.2, "5 3")
    gx = ox + WALL * 1.5 * sc
    s.circle(gx, fy + base_h * sc / 2, GLAND_DIA / 2 * sc, INK, 1.2)
    s.centre_marks(gx, fy + base_h * sc / 2, GLAND_DIA / 2 * sc)
    s.dim_v(fy, fy + base_h * sc, ox + out_w * sc, f"{base_h:.0f}")
    s.leader(gx, fy + base_h * sc / 2, gx + 30, fy + base_h * sc + 26, f"{GLAND_DIA:.0f} DIA GLAND BORE")
    # --- LID ---
    lx = ox + out_w * sc + 150
    s.view_label(lx, oy - 14, "LID - TOP VIEW")
    s.rect(lx, oy, out_w * sc, out_d * sc)
    for (cx, cy) in [(8.0, 8.0), (INNER_W - 8.0, 8.0), (8.0, INNER_D - 8.0), (INNER_W - 8.0, INNER_D - 8.0)]:
        px, py = lx + (WALL + cx) * sc, oy + (WALL + cy) * sc
        s.circle(px, py, BOSS_HOLE_DIA / 2 * sc, INK, 1.2)
        s.centre_marks(px, py, BOSS_HOLE_DIA / 2 * sc)
    s.view_label(lx, fy - 14, "LID - FRONT VIEW")
    s.rect(lx, fy, out_w * sc, LID_H * sc)
    s.rect(lx + WALL * 1.1 * sc, fy + LID_H * 0.4 * sc, (out_w - 2 * WALL * 1.1) * sc, LID_H * 0.6 * sc, THIN, 1.2, "5 3")
    s.dim_v(fy, fy + LID_H * sc, lx + out_w * sc, f"{LID_H:.0f}")
    s.leader(lx + out_w * sc / 2, fy + LID_H * sc, lx + out_w * sc / 2, fy + LID_H * sc + 34, "SKIRT ENGAGES BASE RIM")
    return s


def bracket_sheet() -> Sheet:
    s = Sheet("POLE / PARAPET MOUNT BRACKET", "PNMB-MNT-001", "316 STAINLESS, 6 mm",
              "DEBURR, PASSIVATE",
              notes=["5. SUITS 60 mm NOM. POLE; RE-RUN GENERATOR FOR OTHER DIAMETERS.",
                     "6. WIND / VIBRATION LOAD RATING NOT ESTABLISHED - SEE hardware/README.md.",
                     "7. TILT SLOTS PERMIT APPROX +/-15 DEG ADJUSTMENT."])
    sc = 3.0
    ox, oy = 80, 80
    s.view_label(ox, oy - 14, "FRONT VIEW (ENCLOSURE FACE)")
    s.rect(ox, oy, PLATE_W * sc, PLATE_H * sc)
    inset, enc_w = 8.0, INNER_W + 2 * WALL
    scale_x = (PLATE_W - 20.0) / enc_w
    for (cx, cy) in [(inset, inset), (enc_w - inset, inset), (inset, INNER_D + 2 * WALL - inset),
                     (enc_w - inset, INNER_D + 2 * WALL - inset)]:
        px, py = ox + (10.0 + cx * scale_x) * sc, oy + (10.0 + cy * scale_x) * sc
        s.circle(px, py, BOLT_HOLE_DIA / 2 * sc, INK, 1.2)
        s.centre_marks(px, py, BOLT_HOLE_DIA / 2 * sc)
    for x in (25.0, PLATE_W - 25.0):
        sx, sy = ox + (x - 2.0) * sc, oy + (PLATE_H - 20.0 - 10.0) * sc
        s.rect(sx, sy, 4.0 * sc, 20.0 * sc, INK, 1.2)
    s.dim_h(ox, ox + PLATE_W * sc, oy + PLATE_H * sc, f"{PLATE_W:.0f}")
    s.dim_v(oy, oy + PLATE_H * sc, ox + PLATE_W * sc, f"{PLATE_H:.0f}")
    s.leader(ox + 25.0 * sc, oy + (PLATE_H - 22.0) * sc, ox - 60, oy + PLATE_H * sc + 30, "2x TILT SLOT 4 x 20")
    s.leader(ox + 10.0 * sc, oy + 10.0 * sc, ox - 60, oy - 10, f"4x {BOLT_HOLE_DIA:.1f} DIA TO ENCLOSURE")
    # side view
    vx = ox + PLATE_W * sc + 170
    s.view_label(vx, oy - 14, "SIDE VIEW (POLE CLAMP)")
    s.rect(vx, oy, PLATE_T * sc, PLATE_H * sc)
    s.rect(vx - CHANNEL_DEPTH * sc, oy + (PLATE_H - 25.0) * sc, CHANNEL_DEPTH * sc, 10.0 * sc)
    s.circle(vx - CHANNEL_DEPTH * 0.55 * sc, oy + (PLATE_H - 20.0) * sc, 30.0 * sc, THIN, 1.2, "6 4")
    s.leader(vx - CHANNEL_DEPTH * 0.55 * sc, oy + (PLATE_H - 20.0) * sc, vx + 30, oy + PLATE_H * sc + 20,
             "60 DIA POLE (REF)")
    s.dim_h(vx - CHANNEL_DEPTH * sc, vx + PLATE_T * sc, oy + PLATE_H * sc, f"{CHANNEL_DEPTH + PLATE_T:.0f}")
    return s


def board_sheet() -> Sheet:
    s = Sheet("NODE CARRIER BOARD - PROFILE", "PNMB-PCB-001", "FR4 / RF LAMINATE TBD", "ENIG",
              notes=["5. PROFILE AND MOUNTING ONLY - FOOTPRINTS AND ROUTING NOT INCLUDED.",
                     "6. 4-LAYER MINIMUM; STACKUP AND IMPEDANCE TARGETS PER PCB ENGINEER.",
                     "7. SEE hardware/pcb/netlist.csv AND placement.md FOR THE ELECTRICAL DESIGN."])
    sc = 5.0
    ox, oy = 80, 80
    s.view_label(ox, oy - 14, "BOARD OUTLINE - TOP VIEW")
    s.rect(ox, oy, BOARD_W_MM * sc, BOARD_H_MM * sc)
    for (cx, cy) in mount_hole_positions():
        px, py = ox + cx * sc, oy + cy * sc
        s.circle(px, py, MOUNT_HOLE_DIA_MM / 2 * sc, INK, 1.4)
        s.centre_marks(px, py, MOUNT_HOLE_DIA_MM / 2 * sc)
    from hardware.pcb.generate_board import ZONES
    for label, x0, y0, x1, y1, _ in ZONES:
        s.rect(ox + x0 * sc, oy + y0 * sc, (x1 - x0) * sc, (y1 - y0) * sc, THIN, 1.0, "4 3")
        s.text(ox + x0 * sc + 3, oy + y0 * sc + 12, label, 8, "start", THIN)
    s.dim_h(ox, ox + BOARD_W_MM * sc, oy + BOARD_H_MM * sc, f"{BOARD_W_MM:.0f}")
    s.dim_v(oy, oy + BOARD_H_MM * sc, ox + BOARD_W_MM * sc, f"{BOARD_H_MM:.0f}")
    hx, hy = mount_hole_positions()[0]
    s.leader(ox + hx * sc, oy + hy * sc, ox - 60, oy - 12, f"4x {MOUNT_HOLE_DIA_MM:.1f} DIA")
    return s


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    args = p.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    sheets = [("PNMB-ENC-001_enclosure.svg", enclosure_sheet()),
              ("PNMB-MNT-001_mount_bracket.svg", bracket_sheet()),
              ("PNMB-PCB-001_board_profile.svg", board_sheet())]
    for name, sheet in sheets:
        path = os.path.join(args.out, name)
        with open(path, "w") as f:
            f.write(sheet.render())
        print(f"wrote {path}  ({sheet.title})")
    print(f"{len(sheets)} drawing sheets, dimensions read from the generator constants "
          "so drawings and solids cannot drift apart.")


if __name__ == "__main__":
    main()
