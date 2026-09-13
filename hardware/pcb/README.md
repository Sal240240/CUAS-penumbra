# RF/timing carrier board — schematic-level design package

**What this is:** a complete electrical design — every net, every component
reference, and a placement floorplan — expressed as plain documentation
(`netlist.csv`, `placement.md`) rather than native KiCad project files.

**Why not native KiCad files:** the development environment this package was
produced in does not have KiCad installed, so a `.kicad_sch`/`.kicad_pcb` file
written here could not be opened or DRC-checked before delivery. Handing over
an unverified binary-ish project file and calling it "the schematic" would be
worse than handing over a checked, plain-text equivalent — per RT-10 in
[`docs/10_red_team_ledger.md`](../../docs/10_red_team_ledger.md), overclaiming
readiness on an RF board is exactly the mistake that costs credibility at the
first supplier call. A PCB engineer can transcribe `netlist.csv` into KiCad
(or Altium/Eagle) directly; every net and reference designator needed to do
that is here.

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
- Component references match `hardware/bom/node_bom.csv` exactly (U1-U6,
  FLT1-3) — the BOM is the same one used for the enclosure/cost estimate,
  not a separate list that could drift.
