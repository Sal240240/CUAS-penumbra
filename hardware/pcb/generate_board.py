"""Generate the node carrier board's mechanical CAD: a KiCad board file and a DXF outline.

What this produces, and why only this:

  * `node_carrier.kicad_pcb` — a real, openable KiCad board carrying the parts of
    the design that are geometrically determined and verifiable here:
      - the board profile on Edge.Cuts (140 x 90 mm, sized to the enclosure
        cavity in hardware/mech/enclosure.py)
      - the four mounting holes, on the same pattern as the enclosure's corner
        bosses, so the board and the printed enclosure actually fit each other
      - RF shield-can keepout outlines and functional-zone courtyards on the
        documentation layers, matching hardware/pcb/placement.md
      - the full net list from hardware/pcb/netlist.csv, embedded in the board
  * `node_carrier_outline.dxf` — the same profile and holes as a DXF, which is
    what a board house or a machinist actually wants for the mechanical profile.

  What it deliberately does NOT produce: component footprints with pad geometry.
  A .kicad_pcb embeds full footprint definitions rather than referencing a
  library, so emitting footprints here would mean authoring land patterns for an
  AD9363, a Zynq SoM, a ZED-F9T and an OCXO without the manufacturer drawings to
  check them against. A board that looks finished but has wrong land patterns is
  a worse deliverable than one that is honestly mechanical-only — see RT-10/RT-14
  in docs/10_red_team_ledger.md. The engineer who opens this gets a correct board
  profile, correct mounting, the intended floorplan, and the net list, and places
  real library footprints into it.

Usage: python generate_board.py [--out DIR]
"""
from __future__ import annotations
import argparse
import csv
import os
from typing import List, Tuple

from kiutils.board import Board
from kiutils.items.common import Net, Position
from kiutils.items.gritems import GrCircle, GrLine, GrRect, GrText

BOARD_W_MM = 140.0
BOARD_H_MM = 90.0
MOUNT_HOLE_DIA_MM = 3.2          # M3 clearance, matches enclosure.py BOSS_HOLE_DIA
MOUNT_INSET_MM = 8.0             # matches enclosure.py _corner_positions inset
EDGE_LAYER = "Edge.Cuts"
DOC_LAYER = "Dwgs.User"
NOTE_LAYER = "Cmts.User"

# Functional zones from placement.md: (label, x0, y0, x1, y1, note)
ZONES: List[Tuple[str, float, float, float, float, str]] = [
    ("RF-EDGE-UHF", 6.0, 4.0, 60.0, 22.0, "ANT_UHF_REF/SURV SMA + FLT1 pair"),
    ("RF-EDGE-CELL", 78.0, 4.0, 134.0, 22.0, "ANT_CELL_REF/SURV SMA + FLT2 pair"),
    ("U1-AD9363", 40.0, 28.0, 100.0, 50.0, "RF transceiver, shield can"),
    ("U3-U4-TIMING", 6.0, 54.0, 46.0, 78.0, "GNSS + OCXO, own shield can"),
    ("U2-SOM", 52.0, 54.0, 96.0, 78.0, "Zynq SoM header footprint"),
    ("U6-WIFI", 102.0, 40.0, 134.0, 66.0, "Wi-Fi 6E module + FLT3 + patch connector"),
    ("PWR1", 6.0, 80.0, 40.0, 87.0, "PoE DC-DC"),
    ("U5-RJ45", 60.0, 80.0, 110.0, 87.0, "Ethernet PHY + magnetics + RJ45"),
]

# Shield cans: the two blocks that must be RF-isolated from each other and from
# the SoM's switching noise (placement.md "Zone rationale").
SHIELD_CANS = [("SHIELD-RF", 38.0, 26.0, 102.0, 52.0), ("SHIELD-TIMING", 4.0, 52.0, 48.0, 80.0)]


def mount_hole_positions() -> List[Tuple[float, float]]:
    return [
        (MOUNT_INSET_MM, MOUNT_INSET_MM),
        (BOARD_W_MM - MOUNT_INSET_MM, MOUNT_INSET_MM),
        (MOUNT_INSET_MM, BOARD_H_MM - MOUNT_INSET_MM),
        (BOARD_W_MM - MOUNT_INSET_MM, BOARD_H_MM - MOUNT_INSET_MM),
    ]


def load_nets(netlist_csv: str) -> List[str]:
    with open(netlist_csv, newline="") as f:
        return [row["net"] for row in csv.DictReader(f) if row.get("net")]


def build_board(netlist_csv: str) -> Board:
    board = Board.create_new()

    # --- board profile on Edge.Cuts -------------------------------------------------
    corners = [(0.0, 0.0), (BOARD_W_MM, 0.0), (BOARD_W_MM, BOARD_H_MM), (0.0, BOARD_H_MM)]
    for i in range(4):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % 4]
        board.graphicItems.append(
            GrLine(start=Position(X=x0, Y=y0), end=Position(X=x1, Y=y1), layer=EDGE_LAYER, width=0.1))

    # --- mounting holes (routed openings on Edge.Cuts) -------------------------------
    for (cx, cy) in mount_hole_positions():
        board.graphicItems.append(
            GrCircle(center=Position(X=cx, Y=cy),
                     end=Position(X=cx + MOUNT_HOLE_DIA_MM / 2.0, Y=cy),
                     layer=EDGE_LAYER, width=0.1))

    # --- functional zones + shield cans on the documentation layers ------------------
    for label, x0, y0, x1, y1, note in ZONES:
        board.graphicItems.append(
            GrRect(start=Position(X=x0, Y=y0), end=Position(X=x1, Y=y1), layer=DOC_LAYER, width=0.12))
        board.graphicItems.append(
            GrText(text=f"{label}: {note}", position=Position(X=x0 + 0.5, Y=y0 - 1.2, angle=0), layer=NOTE_LAYER))

    for label, x0, y0, x1, y1 in SHIELD_CANS:
        board.graphicItems.append(
            GrRect(start=Position(X=x0, Y=y0), end=Position(X=x1, Y=y1), layer=NOTE_LAYER, width=0.25))
        board.graphicItems.append(
            GrText(text=label, position=Position(X=x0 + 0.5, Y=y1 + 2.0, angle=0), layer=NOTE_LAYER))

    board.graphicItems.append(GrText(
        text="PENUMBRA node carrier - mechanical only: profile, mounting, floorplan, nets. "
             "Footprints and routing are the PCB engineer's task (see hardware/pcb/README.md).",
        position=Position(X=4.0, Y=BOARD_H_MM + 4.0, angle=0), layer=NOTE_LAYER))

    # --- nets --------------------------------------------------------------------
    for i, name in enumerate(load_nets(netlist_csv), start=1):
        board.nets.append(Net(number=i, name=name))

    return board


def write_dxf(path: str) -> None:
    """Minimal DXF R12 with the board profile and mounting holes.

    R12 entity-only DXF is the lowest-common-denominator format every board house
    and CAM tool reads; writing it directly avoids a CAD dependency for what is
    four lines and four circles.
    """
    lines = ["0", "SECTION", "2", "ENTITIES"]

    def add_line(x0, y0, x1, y1, layer="OUTLINE"):
        lines.extend(["0", "LINE", "8", layer,
                      "10", f"{x0:.3f}", "20", f"{y0:.3f}", "30", "0.0",
                      "11", f"{x1:.3f}", "21", f"{y1:.3f}", "31", "0.0"])

    def add_circle(cx, cy, r, layer="HOLES"):
        lines.extend(["0", "CIRCLE", "8", layer,
                      "10", f"{cx:.3f}", "20", f"{cy:.3f}", "30", "0.0", "40", f"{r:.3f}"])

    corners = [(0.0, 0.0), (BOARD_W_MM, 0.0), (BOARD_W_MM, BOARD_H_MM), (0.0, BOARD_H_MM)]
    for i in range(4):
        add_line(*corners[i], *corners[(i + 1) % 4])
    for (cx, cy) in mount_hole_positions():
        add_circle(cx, cy, MOUNT_HOLE_DIA_MM / 2.0)
    for label, x0, y0, x1, y1, _ in ZONES:
        for a, b, c, d in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
            add_line(a, b, c, d, layer="PLACEMENT")

    lines.extend(["0", "ENDSEC", "0", "EOF"])
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None) -> None:
    here = os.path.dirname(__file__)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=os.path.join(here, "out"))
    p.add_argument("--netlist", default=os.path.join(here, "netlist.csv"))
    args = p.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    board = build_board(args.netlist)
    pcb_path = os.path.join(args.out, "node_carrier.kicad_pcb")
    board.to_file(pcb_path)

    dxf_path = os.path.join(args.out, "node_carrier_outline.dxf")
    write_dxf(dxf_path)

    # Round-trip validation: re-parse what we just wrote. This is the only
    # structural check available without KiCad itself, so it is worth doing
    # rather than assuming the writer produced something loadable.
    reloaded = Board.from_file(pcb_path)
    n_edge = sum(1 for g in reloaded.graphicItems if getattr(g, "layer", None) == EDGE_LAYER)
    print(f"board: {BOARD_W_MM:.0f} x {BOARD_H_MM:.0f} mm, {len(mount_hole_positions())} M3 mounting holes")
    print(f"zones: {len(ZONES)} functional, {len(SHIELD_CANS)} shield cans, {len(reloaded.nets) - 1} nets embedded")
    print(f"round-trip re-parse OK: {n_edge} Edge.Cuts items, {len(reloaded.graphicItems)} graphic items total")
    print(f"wrote {pcb_path}")
    print(f"wrote {dxf_path}")
    print("Mechanical only by design: no footprints, no routing, no DRC — see hardware/pcb/README.md.")


if __name__ == "__main__":
    main()
