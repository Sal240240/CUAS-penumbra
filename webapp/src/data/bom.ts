// Sensor-node bill of materials. Mirrored exactly in hardware/bom/node_bom.csv —
// keep the two in sync. Prices are 2026-09 unit list/distributor prices in CAD
// at qty ~50; see hardware/bom/README.md for sourcing notes and the caveat on
// FX and allocation risk.
export interface BomLine {
  ref: string;
  part: string;
  mpn: string;
  function: string;
  qty: number;
  unitCostCad: number;
  note: string;
}

export const NODE_BOM: BomLine[] = [
  { ref: "U1", part: "RF transceiver module, 70 MHz–6 GHz, 2x2 MIMO", mpn: "Analog Devices AD9363 + RF front-end", function: "UHF/LTE/5G/Wi-Fi surveillance + reference channel RX (2 ch.)", qty: 1, unitCostCad: 220.00, note: "Same silicon family across all three RF bands — antennas and filters differ, radio does not" },
  { ref: "U2", part: "SoC carrier / baseband compute", mpn: "Xilinx Zynq-7020 SoM (e.g. Trenz TE0720)", function: "FPGA fabric for ECA/CAF front end + ARM cores for edge software", qty: 1, unitCostCad: 380.00, note: "FPGA absorbs the cross-ambiguity FFT load; ARM runs Linux edge stack" },
  { ref: "U3", part: "GNSS timing receiver", mpn: "u-blox ZED-F9T", function: "PPS discipline for the OCXO; RTK-grade position for node survey", qty: 1, unitCostCad: 220.00, note: "Time-only firmware profile" },
  { ref: "U4", part: "10 MHz OCXO, ±1e-9/day", mpn: "Rakon RPFOX85 or equiv.", function: "Holdover reference during GNSS-denied intervals", qty: 1, unitCostCad: 165.00, note: "See docs — jamming a CUAS demo's own GNSS is a plausible adversary move" },
  { ref: "U5", part: "Gigabit Ethernet PHY + PoE PD", mpn: "TI DP83867 + TPS2372", function: "Backhaul + power over the same drop", qty: 1, unitCostCad: 38.00, note: "" },
  { ref: "U6", part: "802.11ax/be radio + PA (mesh backhaul / 5–6 GHz sensing)", mpn: "Qualcomm/MTK Wi-Fi 6E module", function: "Mesh backhaul; doubles as the 5–6 GHz illuminator/receiver", qty: 1, unitCostCad: 42.00, note: "802.11bf sensing NDP support required — verify per silicon revision" },
  { ref: "FLT1", part: "UHF (470–608 MHz) band-select filter + LNA", mpn: "e.g. Mini-Circuits BPF/LNA pair", function: "Protects the reference/surveillance chain from adjacent strong signals before the ADC", qty: 2, unitCostCad: 45.00, note: "Reference + surveillance channel, one each" },
  { ref: "FLT2", part: "700 MHz–3.8 GHz band-select filter + LNA", mpn: "e.g. Mini-Circuits BPF/LNA pair", function: "Same role for the LTE/5G channels", qty: 2, unitCostCad: 50.00, note: "Reference + surveillance channel, one each" },
  { ref: "FLT3", part: "5–6 GHz band-select filter + LNA", mpn: "e.g. Mini-Circuits BPF/LNA pair", function: "Same role for the Wi-Fi sensing channel", qty: 1, unitCostCad: 35.00, note: "" },
  { ref: "ANT1", part: "UHF log-periodic, 470–608 MHz", mpn: "hardware/antennas/uhf_logperiodic.py output", function: "ATSC surveillance + reference antennas (2x)", qty: 2, unitCostCad: 58.00, note: "Fabrication-ready: script emits full element geometry" },
  { ref: "ANT2", part: "700 MHz–3.8 GHz log-periodic", mpn: "hardware/antennas/cellular_logperiodic.py output", function: "LTE/5G surveillance + reference antennas (2x)", qty: 2, unitCostCad: 46.00, note: "Fabrication-ready" },
  { ref: "ANT3", part: "5–6 GHz patch array, 4-element", mpn: "hardware/antennas/wifi_patch_array.py output", function: "Mesh backhaul + Wi-Fi sensing", qty: 1, unitCostCad: 34.00, note: "Fabrication-ready" },
  { ref: "PWR1", part: "PoE++ splitter + DC-DC (5 V/3.3 V/1.8 V rails)", mpn: "TI PMP-class reference design", function: "Power conditioning", qty: 1, unitCostCad: 28.00, note: "" },
  { ref: "ENC1", part: "IP66 enclosure, UV-stable ASA", mpn: "hardware/mech/enclosure.py output (3D printed or injection-moulded)", function: "Weatherproofing, pole/rooftop mount", qty: 1, unitCostCad: 65.00, note: "Fabrication-ready" },
  { ref: "MNT1", part: "Pole/parapet mount bracket, 316 stainless", mpn: "hardware/mech/mount_bracket.py output", function: "Fixed-node mounting", qty: 1, unitCostCad: 40.00, note: "Fabrication-ready" },
  { ref: "MISC", part: "Connectors, cabling, fasteners, thermal, assembly labour", mpn: "—", function: "Assembly", qty: 1, unitCostCad: 100.00, note: "Lumped allowance" },
];

export const NODE_BOM_TOTAL_CAD = NODE_BOM.reduce((sum, l) => sum + l.qty * l.unitCostCad, 0);
