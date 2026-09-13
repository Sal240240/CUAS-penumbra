# Node assembly overview

One fixed node = one of each of the following, bolted together in this order:

1. **Enclosure base** (`hardware/mech/out/node_enclosure_base.stl`) — carrier
   board, DC-DC, and the four RF filter/LNA modules mount to the four corner
   bosses (M3, see `hardware/pcb/placement.md` for the board layout they hold).
2. **Carrier board** — built to `hardware/pcb/netlist.csv` +
   `hardware/pcb/placement.md`; BOM in `hardware/bom/node_bom.csv`.
3. **Antennas**, external, connected by SMA/U.FL pigtail through the
   enclosure wall:
   - 2x UHF log-periodic (`hardware/antennas/out/lpda_uhf.*`) — reference and
     surveillance channel
   - 2x cellular log-periodic (`hardware/antennas/out/lpda_cellular.*`)
   - 1x 5-6 GHz patch array (`hardware/antennas/out/patch_array.*`), mounted
     flush to the enclosure lid (patch antennas radiate broadside — the lid
     face is the correct mounting surface, not the side wall)
4. **Enclosure lid** (`hardware/mech/out/node_enclosure_lid.stl`) — silicone
   gasket cord in the moulded channel, 4x M3 to the base.
5. **Mount bracket** (`hardware/mech/out/mount_bracket.stl`) — bolts to the
   same four corner bosses from outside the enclosure (through-holes align
   with the enclosure's own mounting pattern; see `mount_bracket.py`'s
   `MOTOR_MOUNT_PATTERN`-style scaling comment), then clamps to the pole or
   parapet rail with a hose clamp or U-bolt through the two hose-clamp holes.

Cable entry (PoE/Ethernet) is through the single gland bore in the base's end
wall, sized for a standard RJ45-terminated Cat6 gland fitting.

This is a bolt-together mechanical plan, not a torque/sealing spec — a
technician doing the first physical build should treat gasket compression,
gland tightening, and RF connector torque as things to verify by inspection,
not assume from this document.
