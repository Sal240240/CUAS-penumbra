# Node bill of materials

`node_bom.csv` is the machine-readable BOM. Per-node total: **CAD 1,765.00**
at ~50-unit quantity, September 2026 distributor list pricing. This refines
the RT-03 order-of-magnitude estimate (~CAD 1.9k) in
[`docs/10_red_team_ledger.md`](../../docs/10_red_team_ledger.md) once the
band-select filter/LNA stages (FLT1-3) were itemized — see RT-13 there.

## Sourcing notes

- **U1/U6 (RF transceiver, Wi-Fi module):** Digi-Key/Mouser/Avnet all stock
  the AD9363 and common Wi-Fi 6E modules; lead times were normal (2-6 weeks)
  as of September 2026. Verify current allocation before committing to a
  build quantity.
- **U2 (SoM):** Trenz Electronic (Germany) and Avnet both distribute
  Zynq-7020 SoMs into Canada; confirm ITAR/export-control status is clear for
  the specific SoM part number before a DND-facing procurement (most
  commercial Zynq SoMs are not ITAR-controlled, but this must be verified per
  part, not assumed).
- **FLT1-3 (filters/LNAs):** Mini-Circuits ships from the US; a Canadian
  supply-chain assessment (per the report's deliverables list) should also
  price Pasternack and check whether any Canadian RF house
  (e.g., Norsat, Communications & Power Industries Canada) stocks equivalents
  to reduce cross-border lead time and duty exposure.
- **Antennas/enclosure/bracket:** fabricated in-house from the scripts in
  `hardware/antennas/` and `hardware/mech/` — no external antenna vendor
  dependency for the prototype run.

## FX exposure

Roughly 60% of the per-node cost (U1-U6, FLT1-3) is USD-denominated
component cost converted to CAD. A 10% CAD depreciation against USD would
raise the per-node cost by roughly CAD 105 — material at prototype
quantities (WP4, ~10 nodes) but worth locking in supplier quotes before a
larger WP5 distributed-network buy (~30-50 nodes).

## Canadian supply-chain assessment (preliminary)

This is a starting point, not the formal assessment the report's deliverables
list (section 15.3) calls for:

| Category | Canadian sourcing | Import dependency |
|---|---|---|
| RF/digital silicon (U1-U6) | None identified at prototype scale | High — US/Asia fabless vendors |
| Filters/LNAs (FLT1-3) | Norsat (BC) makes comparable modules at higher spec/cost tiers | Medium |
| Antennas (ANT1-3) | Fully in-house (scripted fabrication) | None |
| Enclosure/bracket | Any Canadian machine shop or 3D-print bureau | None |
| GNSS/OCXO (U3/U4) | None identified | High — single-source-adjacent (u-blox, Rakon) |

The timing chain (U3/U4) is the thinnest part of the supply chain — worth a
second-source study before scaling past WP5.
