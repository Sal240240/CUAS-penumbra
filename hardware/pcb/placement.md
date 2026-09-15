# Node carrier board — placement floorplan

Board outline: 140 x 90 mm (matches the enclosure cavity in
`hardware/mech/enclosure.py`), 4-layer minimum (signal / ground / power /
signal), ENIG finish for the RF connector pads.

```
+----------------------------------------------------------+
| ANT_UHF_REF   ANT_UHF_SURV        ANT_CELL_REF  ANT_CELL_SURV
|  (edge SMA)     (edge SMA)          (edge SMA)     (edge SMA)
|   [FLT1_REF]    [FLT1_SURV]         [FLT2_REF]    [FLT2_SURV]
|                                                              |
|        [ U1  AD9363 RF transceiver + shield can ]           |
|                                                              |
|  [ U3 GNSS ]      [ U2 Zynq SoM socket/header ]   [ U6 WiFi ]|
|  [ U4 OCXO ]                                       [FLT3]    |
|   (own shield can, kept >20mm from U6/Wi-Fi)      ANT_PATCH  |
|                                                    (edge conn)|
|  [ PWR1 DC-DC ]        [ U5 PHY + magnetics ]   [ J_RJ45 ]   |
|                                                              |
+----------------------------------------------------------+
```

## Zone rationale

- **RF edge, top:** all four UHF/cellular antenna connectors on one edge,
  closest to their respective filter/LNA (FLT1/FLT2), which sit immediately
  before U1's RX inputs — minimizes lossy/noisy RF trace length before the
  first active gain stage.
- **U1 (AD9363), center:** equidistant from both RF edges; under its own
  shield can to isolate the sensitive front end from the SoM's switching
  digital noise and from U6's own transmitter.
- **U3/U4 (GNSS + OCXO), left of center, own shield can:** timing accuracy is
  the thing the whole multistatic tracker depends on (see
  `penumbra/tracking/multistatic.py`) — this block gets physical isolation
  from the Wi-Fi PA (U6) and the SoM's digital switching, not just a
  schematic-level ground connection.
- **U6 (Wi-Fi/backhaul), right edge, away from GNSS:** a 2.4/5/6 GHz PA is a
  plausible desense source for the L1/L5 GNSS bands if placed close to U3;
  right-edge placement plus the shield cans buys margin. Verify with a
  measured isolation test in WP4, not assumed from placement alone.
- **U5 (Ethernet PHY) + RJ45, bottom edge:** aligns with the enclosure's
  cable-gland bore (`hardware/mech/enclosure.py`), which is on one end wall.
- **PWR1 (DC-DC), bottom center:** short, wide traces to both the RJ45 PoE
  input and the star-ground point; physically separated from the RF zone.

## Stackup guidance (not a finished stackup)

A 4-layer board with signal/ground/power/signal, ground plane directly under
the RF signal layer for controlled impedance, is the usual starting point for
a board this mixed — but the actual impedance targets depend on the dielectric
a fabricator quotes (FR4 vs. a lower-loss RF laminate like Rogers 4350B for
the >3 GHz paths) and are a PCB engineer's call, not asserted here.
