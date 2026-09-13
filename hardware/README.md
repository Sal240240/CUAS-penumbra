# PENUMBRA hardware

| Directory | What it contains | Fabrication-ready? |
|---|---|---|
| `antennas/` | LPDA (UHF, cellular) and patch-array (Wi-Fi) generators — real design equations, CSV build sheets, SVG drawings | Yes — geometry is fully scripted (see each script's docstring for the design reference) |
| `mech/` | Enclosure (base+lid) and pole/parapet mount bracket generators — parametric, watertight STL | Yes — run the script, print or CNC the STL |
| `interceptor/` | Talon airframe generator (roadmap item, RT-09) | Yes, as geometry — the vehicle itself is not a Sandbox 2027 deliverable |
| `pcb/` | RF/timing carrier board: full netlist + placement floorplan | Schematic-level only — routing/DRC needs a licensed PCB/RF engineer, see `pcb/README.md` |
| `bom/` | Per-node bill of materials, CAD 1,765.00/node, sourcing and supply-chain notes | N/A (documentation) |
| `drawings/` | Node assembly overview tying the above together | N/A (documentation) |

## Regenerating everything

All generators are plain Python against the same `penumbra` virtual environment used for the physics/ML core:

```bash
python hardware/antennas/logperiodic.py uhf
python hardware/antennas/logperiodic.py cellular
python hardware/antennas/patch_array.py
python hardware/mech/enclosure.py
python hardware/mech/mount_bracket.py
python hardware/interceptor/airframe.py
```

Each writes into its own `out/` directory (git-ignored — regenerate rather
than diff binary STL files) and prints a one-line summary of what it built,
including anything it deliberately did **not** compute (feed-point tuning,
structural load ratings, DRC) so that gap is never silent.

## The honesty line this hardware package holds

Per RT-10 in [`../docs/10_red_team_ledger.md`](../docs/10_red_team_ledger.md):
antenna, enclosure, mount, and airframe geometry is genuinely fabrication-
ready because a script determines every dimension. The RF/timing carrier
board is not claimed as fabrication-ready — it is a complete, checked
electrical design (every net, every placement decision, with rationale) that
still needs a PCB engineer's routing and DRC sign-off before it goes to a
board house. That distinction is the whole point: a program that gets shown
in front of thousands of people and DND evaluators does not get to blur it.
