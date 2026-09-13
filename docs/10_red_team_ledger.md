# Red-Team Ledger — the parallel assessment process

This ledger is the "second track" that ran alongside every design decision in
PENUMBRA. For each decision it records the option chosen, the strongest
alternative, the attack on the chosen option, and what would change the verdict.
Entries are never deleted; a reversed decision gets a new entry that cites the old one.

The standard each entry is held to: **is this the best option available, and
would it survive a hostile technical reviewer at DND/DRDC?**

---

## RT-01 — Keep the ambient-RF concept at all, or pivot?

**Chosen:** keep passive ambient-RF sensing as the core, but change *what* is measured
(see RT-02).

**Alternatives attacked:**
- *Neuromorphic event cameras*: excellent for fast small objects, but optical -> explicitly
  one of the four incumbent modalities the challenge de-prioritises; also "optical systems
  may face operating restrictions" in the 2027 urban sandbox notes.
- *Infrasound / distributed acoustic*: acoustic is an incumbent modality; urban SNR poor.
- *Magnetic / electrostatic signatures*: physics gives < 20 m range for a 1 kg drone; dead end.
- *LiDAR curtains*: optical, short range, expensive per unit volume.

**Attack on the choice:** the report's own positioning note admits DND has already seen
"ambient electromagnetic sensing" concepts in the 2025 sandbox. Novelty must therefore be
architectural and evidential, not the word "passive".

**What would flip it:** if WP3 physics validation (Gate 1) fails to show a repeatable
UHF body return on a Mini-class drone at 300 m, the program stops and publishes the
negative result. That is written into the test plan, not hidden.

## RT-02 — "Correlated propagation disturbances" (SKYWEAVE) vs coherent cross-ambiguity processing

**Chosen:** coherent passive-radar processing (reference channel + surveillance channels,
cross-ambiguity function, direct-signal cancellation) as the primary observable; link-level
channel-perturbation sensing (the SKYWEAVE idea) demoted to a short-range NLOS cue on the
mesh's own 802.11bf links.

**Why:** the SKYWEAVE report never committed to a measurement model. Incoherent
RSSI/CSI perturbation has no processing gain; at UHF a -20 dBsm target perturbs a link by
fractions of a dB at tens of metres. The cross-ambiguity function buys 10·log10(B·T) — 65 dB
for a 6 MHz ATSC channel over 0.5 s — which is the entire difference between "maybe" and
"detects a 249 g drone at 1.2 km" (`penumbra/physics/bistatic.py`, `docs/01_physics_and_link_budget.md`).

**Attack:** coherent PCL is a known field (Griffiths & Baker 2017). Differentiation must
come from the *mesh* (RT-04), the *multi-band split* (RT-03), the *evidence reasoning* (RT-07)
and the *Canadian illuminator mapping* (ATSC, not DVB-T — every European result must be
re-derived; we did).

## RT-03 — Single band vs multi-band

**Chosen:** three concurrent bands with different jobs:
| band | illuminator | job | limiting physics |
|---|---|---|---|
| UHF 470–608 MHz | ATSC TV (Camp Fortune, 311 kW) | area detection to ~1–2 km/node; airframe is in the resonance region | 6 MHz -> 50 m resolution; blades electrically small -> no micro-Doppler |
| 700 MHz–3.8 GHz | LTE / 5G NR | precision multistatic Doppler tracking (sub-metre with 3+ nodes, Ji et al. 2025); rotor micro-Doppler on Mavic-class and larger | beam sweeping; ~0.5–1 km/node |
| 5–6 GHz | the mesh's own Wi-Fi 6E/802.11bf backhaul | street-canyon fill, guaranteed illumination we control, rotor micro-Doppler on the smallest plastic-bladed drones at < 150 m | very short range |

**Attack:** three receivers per node triples RF cost. **Response:** the AD9361/AD9363
family covers 70 MHz–6 GHz in one part; the cost is antennas, not radios. The node BOM
holds this to ~CAD 1.9k (`hardware/bom/`).

**Numbers that forced it:** blade RCS of a Mini-class drone is -58 dBsm at 539 MHz but
-52 dBsm at 3.5–5.5 GHz *and* the geometry is 10x closer on the mesh links, so the
micro-Doppler SNR advantage of the mesh links is > 25 dB.

## RT-04 — Mesh density: what does "low-cost sensor network" have to mean?

**Chosen:** design spacing of 250–400 m in dense urban core, nodes at >= 15 m AGL.

**Why:** knife-edge diffraction over a single 35 m roof costs ~20 dB at UHF, which cuts
per-node range from 2.2 km to ~220 m. Any point must be seen by >= 3 node/illuminator
pairs with <= 1 diffracting edge to keep multistatic tracking observable. Simulation
(`penumbra/sim/coverage.py`) evaluates this for a scene rather than asserting it.

**Attack:** more nodes = more timing sync burden. **Response:** GNSS-disciplined OCXO on
every node (RT-06); the reference channel removes illuminator frequency error per node,
so only the inter-node clock matters, and only at the 1 Hz / 100 ns level.

## RT-05 — LEO Ku-band (Starlink) illumination: headline or footnote?

**Chosen:** footnote (Phase E research option). Link budget gives 170–300 m on
micro-class targets with a 35 dBi dish, i.e. a narrow-beam staring sensor — not a mesh
node. Overclaiming Starlink would be the single easiest thing for a reviewer to shoot down.

## RT-06 — Timing: GPS-disciplined OCXO vs White Rabbit / PTP vs free-running TCXO

**Chosen:** u-blox ZED-F9T PPS disciplining a 10 MHz OCXO on a custom carrier board;
PTP over the backhaul as a fallback when GNSS is jammed (which, at a CUAS event, it may be).

**Attack:** GNSS-denied operation. **Response:** OCXO holdover of 1e-9/day keeps
inter-node Doppler error < 1 Hz at 740 MHz for > 1 hour; the reference channel is
self-calibrating against the illuminator; PTP holds the network to ~1 us, enough for
50 m range bins.

## RT-07 — "AI-first" vs "physics-first" ML

**Chosen:** a physics-conditioned multimodal model (`penumbra/ml/model.py`) whose inputs are
already CAF range-Doppler surfaces and micro-Doppler spectrograms, with the node/illuminator
geometry embedded as tokens. It outputs an occupancy heat-map with calibrated uncertainty,
and a separate *evidence ledger* (`penumbra/reasoning/`) explains each track in terms a
radar engineer can audit (HERM line spacing vs blade count, multistatic consistency,
kinematic plausibility).

**Attack:** synthetic-to-real gap. **Response:** the simulator is physics-based, the
classifier head is pre-trained on public measured micro-Doppler data (KTH 77 GHz set,
DIAT-uSAT), and Gate 3 requires retraining on the WP6 urban background dataset. The
web-app states the sim-to-real caveat rather than hiding it.

## RT-08 — Name

"SKYWEAVE" reads as a consumer brand. Rejected candidates: LATTICE (Anduril's C2 product),
ARGUS/SENTINEL/AEGIS (saturated), UMBRA (an existing SAR company). **Chosen: PENUMBRA** —
the partial shadow an object casts in ambient illumination, which is literally the
observable. Sub-systems: *Penumbra Node* (sensor), *Penumbra Fabric* (mesh + fusion),
*Penumbra Talon* (interceptor).

## RT-09 — Defeat layer (added after user direction, citing Tornyol)

**Chosen:** track-cued autonomous net-capture interceptor with a drag parachute, plus a
tethered net launcher for point defence. Designed, costed and simulated; **not**
demonstrated at the 2027 urban sandbox, which the applicant guide prohibits ("does not permit
the demonstration of defeating target drones in an urban environment").

**Why net, not ram / jam / laser:** in a city, whatever you defeat lands on someone.
Net + parachute is the only effector family with a controlled descent. RF jamming needs
an ISED radio-authorisation exemption that civilian operators cannot obtain. Kinetic
ramming (the Tornyol approach, 40 g drone vs a mosquito) scales badly to a 2 kg target
over a crowd. What we *do* take from Tornyol: cheap autonomous hunters cued by a fixed
sensor array that identifies targets by wing/rotor micro-Doppler, with terminal guidance on
the hunter itself.

**Attack:** intercept of a 20 m/s FPV drone by a net drone is hard. **Response:** the
interceptor is a 7-inch quad at 30+ m/s with a vision-based terminal seeker; the mesh's
job is to put it within 30 m of the target with < 3 m error, which the multistatic Doppler
tracker delivers. Engagement geometry is simulated in `penumbra/sim/intercept.py`.

## RT-10 — Hardware deliverable honesty

**Chosen:** everything that can be made fabrication-ready by script *is* (antenna Gerbers,
enclosure and mount STL/3MF, interceptor airframe, drawings). The RF/timing carrier PCB is
delivered as a complete KiCad schematic, netlist, placement and BOM — routing and DRC
sign-off remain a PCB engineer's task and the docs say so. Overclaiming "manufacture-ready"
on an unrouted RF board would be a mistake that costs credibility at the first supplier call.

## RT-11 — Training data

**Chosen:** (1) physics-based synthetic data from our simulator (primary, unlimited,
labelled), (2) public measured micro-Doppler sets fetched by `data/fetch_datasets.py`
(KTH/SAAB 77 GHz drone/bird/human set, CC-BY-4.0; DIAT-uSAT X-band; DroneDetect RF as a
negative-modality reference), (3) the program's own WP4/WP6 captures. No dataset exists
for ATSC-illuminated drone echoes; we say so and make collecting it a Gate-2 deliverable.

## RT-12 — Web application

**Chosen:** React + TypeScript + Vite static build for AWS Amplify Hosting, with the
physics ported to TypeScript (`webapp/src/physics/`) so the interactive simulators compute
in-browser from the same equations as the Python. Restrained editorial design, real
photographs (CC-licensed, credited), no stock "AI glow" aesthetics.

**Status:** built. Every ported module (`bistatic.ts`, `rcs.ts`, `illuminators.ts`,
`propagation.ts`, `scene.ts`, `coverage.ts`, `evidence.ts`) was checked against its Python
source on shared scenarios and matched to full floating-point precision (see
`webapp/README.md`, "Physics parity"). One real bug surfaced in the process: a coverage-map
grid cell can land exactly on an illuminator or node position (both tend to be round
numbers), which threw out of `bistatic_geometry` and blanked the page — fixed in both
`coverage.ts` and `penumbra/sim/coverage.py` by skipping a pair when the point is within 1 m
of either endpoint, with a regression test (`tests/test_sim_coverage.py`).

## RT-13 — BOM reconciliation

**Chosen:** itemize the node BOM in full (`hardware/bom/node_bom.csv`), including two RF
band-select filter/LNA stages per receive path that RT-03's order-of-magnitude estimate
didn't itemize. Itemized total: **CAD 1,765/node**, against RT-03's "~CAD 1.9k" estimate.

**Why the filters were missing before:** RT-03 costed the radio (AD9361/AD9363) and antennas
but not the front-end filtering a receiver simultaneously covering ATSC, LTE/5G, and Wi-Fi
actually needs to avoid one band's strong in-band signal desensing another — a real omission,
not a rounding difference.

**Verdict:** the refined number is close enough to the original order-of-magnitude estimate
(7% lower) that RT-03's design conclusion (single radio family, cost is in antennas/filters
not silicon) still holds. Recorded here per this ledger's own rule: a reversed or refined
decision gets a new entry, not a silent edit.

## RT-14 — Hardware fabrication scripts

**Chosen:** script every geometry that can be fully determined by equations (LPDA antennas
via Carrel 1961, a microstrip patch array via Balanis sec. 14.2, a watertight enclosure and
pole/parapet mount via parametric CSG, the Talon airframe) to real output files (CSV build
sheets, SVG drawings, STL solids) rather than describing them in prose.

**What was deliberately not scripted:** the RF/timing carrier board is delivered as a full
netlist and placement floorplan (`hardware/pcb/`) but not as native KiCad project files —
the environment this was built in has no KiCad install to validate a `.kicad_sch`/`.kicad_pcb`
file against, and handing over an unverified project file would be a worse failure mode than
handing over a checked plain-text equivalent. Same principle as RT-10, applied to the actual
deliverable this time rather than stated as an intention.

## RT-15 — Training-data access reality check

**Chosen:** verify all three RT-11 datasets against their actual hosting pages before writing
any fetch code, rather than trusting the citation. Result: the KTH/SAAB 77 GHz set (Zenodo,
DOI 10.5281/zenodo.5845259) is genuinely open, CC-BY-4.0, no login — `data/fetch_datasets.py`
downloads and checksums it automatically. DIAT-uSAT and DroneDetect are both IEEE DataPort
datasets gated behind a subscription, a free-account login, or (for DIAT-uSAT) an emailed
educational-access request — none of that is a URL a script can fetch, so the script documents
the manual steps instead of pretending otherwise.
