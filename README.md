# PENUMBRA

A passive multistatic RF sensing mesh for urban counter-UAS detection and
tracking, prepared as a technical concept and R&D program for the Canadian
DND/CAF IDEaS CUAS Urban Sandbox context. **Detection and tracking only** —
see [Non-goals](#non-goals).

Formerly "SKYWEAVE" (an earlier, less-differentiated ambient-EM-sensing
concept). The rename and the underlying architecture pivot — from an
uncommitted "ambient disturbance" idea to coherent passive bistatic/
multistatic radar — are documented with their reasoning in
[`docs/10_red_team_ledger.md`](docs/10_red_team_ledger.md); treat that ledger,
not any earlier report, as the source of truth for what this program actually
claims.

## What it is

Six-plus rooftop/pole-mounted receive-only nodes exploit illuminators of
opportunity already broadcasting across a city — ATSC television, LTE/5G
downlink, and the mesh's own Wi-Fi backhaul — as a passive coherent radar.
Cross-correlating a reference channel against a surveillance channel recovers
bistatic range and Doppler with real coherent processing gain; a
physics-conditioned detector and an auditable evidence ledger turn that into
confidence-scored tracks a C2 system can consume.

## Repository layout

| Path | Contents |
|---|---|
| `penumbra/` | The physics/DSP/ML/tracking/reasoning/C2 Python core — see `penumbra/__init__.py` for the sub-package map |
| `webapp/` | React + TypeScript + Vite site: architecture explainer, an in-browser physics-parity link-budget simulator, a coverage-map visualizer, an evidence-ledger demo, and the program plan — see `webapp/DEPLOYMENT.md` for AWS Amplify hosting |
| `hardware/` | Antenna/enclosure/mount/interceptor fabrication-file generators, the node BOM, and the RF/timing carrier board's schematic-level design — see `hardware/README.md` for what is and is not fabrication-ready |
| `data/` | `fetch_datasets.py` — the public micro-Doppler/RF datasets used for ML pretraining, with real licenses/access terms, not a blanket "scrape" |
| `docs/` | Program documentation, including the red-team ledger |
| `tests/` | pytest suite for the Python core |

## Quickstart

```bash
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -e ".[ml,hardware,dev]"
pytest

cd webapp
npm install
npm run dev
```

## Honesty framing this project holds itself to

- **Detection and tracking only.** No autonomous engagement is part of the
  Sandbox concept; a net-capture interceptor exists as a costed roadmap item
  (RT-09) and is explicitly not demonstrated at the event.
- **No claim that the physics is proven.** The program is gated (see
  `webapp` → Program page, or the original report's section 12.1): a negative
  result at Gate 1 stops the program and publishes why.
- **"Fabrication-ready" means the script actually determines the geometry.**
  Antennas, enclosure, mount, and interceptor airframe do; the RF/timing PCB
  does not (see `hardware/README.md`) — that needs a licensed PCB/RF
  engineer's routing and DRC sign-off.
- **Every physics equation in the webapp is checked against the Python core**
  for exact numerical agreement, not just visually similar (see
  `webapp/README.md`, "Physics parity").

## Non-goals

- No autonomous engagement or defeat mechanism in the detection system itself.
- No person-identification capability.
- No claim that PENUMBRA replaces radar, optical, acoustic, or RF-emission
  sensing — it is a complementary layer for a layered CUAS architecture.
