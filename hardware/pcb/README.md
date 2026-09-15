# RF/timing carrier board — electrical design + mechanical CAD

**What this is:**

1. **The electrical design** — every net and every component reference
   (`netlist.csv`), plus the placement floorplan and the reasoning behind it
   (`placement.md`).
2. **The mechanical CAD** — `python generate_board.py` emits
   `out/node_carrier.kicad_pcb` (a real, openable KiCad board) and
   `out/node_carrier_outline.dxf`. The board carries the profile on Edge.Cuts,
   the four M3 mounting holes on the same pattern as the enclosure's corner
   bosses, the RF shield-can keepouts and functional-zone courtyards from
   `placement.md`, and the full net list embedded. The generator re-parses what
   it wrote as a structural check, since KiCad itself is not available here to
   run a real DRC.

**What the board file deliberately does not contain: component footprints.**
A `.kicad_pcb` embeds full footprint geometry rather than referencing a library,
so emitting footprints would mean authoring land patterns for an AD9363, a Zynq
SoM, a ZED-F9T and an OCXO without the manufacturer drawings to check them
against. A board that looks finished but has wrong land patterns is a worse
deliverable than an honestly mechanical-only one — per RT-10/RT-14 in
[`docs/10_red_team_ledger.md`](../../docs/10_red_team_ledger.md), overclaiming
readiness on an RF board is exactly the mistake that costs credibility at the
first supplier call. What an engineer gets here is a correct board profile,
correct mounting, the intended floorplan, and the netlist — then places real
library footprints into it.

**What is NOT done here, and needs a licensed PCB/RF engineer:**

- Physical routing (especially the RF traces from U1/FLT1-3 to the antenna
  connectors — these need controlled-impedance microstrip/stripline, not
  hand-waved traces)
- Design-rule check (DRC) / electrical-rule check (ERC) sign-off
- Ground-plane and RF-shielding can layout around the AD9363, GNSS receiver,
  and OCXO — this is where a 6 GHz front end living next to a GNSS receiver
  either works cleanly or desenses itself
- Thermal and EMC pre-compliance review

## Contents

- `netlist.csv` — every net in the design: net name, the ref-des/pin pairs on
  it, and a one-line electrical note (power, RF, digital, or ground/shield)
- `placement.md` — a floorplan: which zone of the board each functional block
  occupies and why (RF isolation, thermal, connector access)
- `generate_board.py` — emits the KiCad board and DXF outline into `out/`
- Component references match `hardware/bom/node_bom.csv` exactly (U1-U6,
  FLT1-3) — the BOM is the same one used for the enclosure/cost estimate,
  not a separate list that could drift.
- The dimensioned drawing sheet for the board profile is
  `hardware/drawings/out/PNMB-PCB-001_board_profile.svg`, generated from the
  same constants as the board file.
