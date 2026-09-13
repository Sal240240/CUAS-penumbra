# Physics and link budget

Referenced from RT-02 in [`10_red_team_ledger.md`](10_red_team_ledger.md).
This is the narrative version of what `penumbra/physics/bistatic.py` computes
exactly — read that module's docstring for the equations themselves and
`webapp/src/pages/Simulator.tsx` to run it interactively.

## Why coherent processing, not incoherent perturbation sensing

The original SKYWEAVE concept proposed detecting a UAS from "correlated
disturbances in ambient electromagnetic propagation" without committing to a
specific measurement model. Worked through concretely, that idea is
incoherent RSSI/CSI perturbation sensing — and the numbers do not support it
at useful range. A 0.9 kg drone with roughly -17 dBsm body RCS perturbs a UHF
link by a few tenths of a dB at tens of metres; there is no way to pull that
out of link noise at hundreds of metres without more processing gain than an
incoherent measurement provides.

Passive coherent radar (Griffiths & Baker, 2017) gets that processing gain
from cross-correlating a clean reference copy of the illuminator's signal
against the same signal after it has propagated through the environment and
reflected off a target. Integrated over time `T_int` with bandwidth `B`, the
coherent gain is `B * T_int` — for a 6 MHz ATSC channel over 0.5 s that is
**+65 dB**. That is the entire difference between "a drone perturbs the
link by a fraction of a dB, undetectable" and "a drone at 1.2 km produces a
usable SNR after processing." Coherent cross-ambiguity processing (see
`penumbra/dsp/caf.py`) is therefore not an implementation detail — it is the
reason the concept can work at all.

## Two floors, not one

`penumbra/physics/bistatic.py::link_budget()` computes both detectability
floors and reports whichever is worse:

1. **Thermal noise:** `SNR_th = P_r * T_int / (k * T0 * F)`. This dominates
   at short baselines with good direct-signal cancellation (e.g. the mesh's
   own 5-6 GHz Wi-Fi links).
2. **Direct-signal interference (DSI) residual:** the direct path from
   illuminator to receiver is vastly stronger than any target echo; after
   cancellation (ECA, `penumbra/dsp/dsi.py`, ~50 dB) the residual sidelobe
   floor of a noise-like reference sits `10*log10(B*T_int)` dB below its own
   peak. This dominates at long UHF baselines, where the direct path from a
   311 kW broadcast transmitter is enormous relative to a drone echo even
   after 50 dB of cancellation.

Neither number alone tells the truth; the simulator, the offline analysis,
and this document all report `min(SNR_thermal, SNR_dsi)` for exactly that
reason.

## Worked example: CBOT-DT vs. a hovering Mavic-class drone

Inputs: CBOT-DT ATSC ch.25 (57.1 dBW EIRP, 6 MHz, 539 MHz), a node 300 m from
the target with the illuminator 15.7 km away, 0.5 s integration, no extra
path loss.

| Quantity | Value |
|---|---|
| Body RCS at 539 MHz (`body_rcs`, DJI Mavic-class) | -17.0 dBsm (unchanged from the catalogue optical-region value — at this frequency `ka ~= 1.98` already clears the `ka >= 1` threshold in `rcs.py`, so the Rayleigh scaling does not apply) |
| Received power | -128.4 dBW |
| Direct-path power | -44.0 dBW |
| Thermal-noise floor | 67.5 dB |
| DSI floor | 30.3 dB |
| **Usable SNR** | **30.3 dB** (DSI-limited) |
| Range resolution (c/B) | 50.0 m |
| Doppler resolution (1/T) | 2.0 Hz |

Run this exact scenario yourself in the webapp's link-budget simulator (it
computes from a TypeScript port checked for bit-for-bit numerical agreement
with the Python source — see `webapp/README.md`).

## What this document does not claim

None of the above has been validated against a real ATSC-illuminated echo —
that is Gate 1 of the program (`docs/10_red_team_ledger.md` RT-01, and the
Program page of the webapp). The RCS model is a deliberately simple
frequency-scaling approximation anchored to measured Ku/K-band data (Semkin
et al. 2019), not a measured UHF signature; WP3 replaces it. The purpose of
this document is to show the reasoning is falsifiable and specific, not that
it is already proven.
