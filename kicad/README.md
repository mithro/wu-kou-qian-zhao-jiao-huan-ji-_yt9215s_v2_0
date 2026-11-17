# KiCad version of the YT9215S 5-port switch

A KiCad 9 conversion of pankanwen's design, made with **KiCad's own EasyEDA Pro
importer** from [`../easyeda/YT9215S-5-port-switch.epro`](../easyeda/), not redrawn by
hand. Same author, credit and licence (CC BY-NC-SA 3.0) as the rest of this repository;
see the [top-level README](../README.md).

Open `YT9215S-5-port-switch.kicad_pro` in KiCad 9.0 or newer.

![PCB, top (KiCad 3D render)](render/pcb-3d-top.png)

## Files

| Path | Contents |
| --- | --- |
| `YT9215S-5-port-switch.kicad_pro` | Project (open this) |
| `YT9215S-5-port-switch.kicad_sch`, `1_P1.kicad_sch`, `2_P2.kicad_sch` | Schematic: root sheet, P1 (switch chip, power, crystal, LED, reset), P2 (five RJ45 ports) |
| `YT9215S-5-port-switch.kicad_pcb` | PCB, 2 layers, 100 × 65 mm, zones filled |
| `YT9215S-5--easyedapro.kicad_sym`, `YT9215S-5-port-switch.pretty/` | Project symbol and footprint libraries written by the importer |
| [`render/`](render/) | `schematic.pdf` and per-sheet PNGs, `pcb-layers.pdf` (one page per layer), top/bottom copper PNGs, top/bottom 3D renders |
| [`reports/`](reports/) | KiCad ERC and DRC (with schematic parity) reports, and `net-compare.txt` |
| [`tools/`](tools/) | `fixup_import.py` (the post-import fixes below) and `compare_nets.py` (schematic vs PCB connectivity check) |

## How it was made

1. KiCad 9.0.9 (Ubuntu PPA), *Import Non-KiCad Project → EasyEDA (JLCEDA) Pro Project*
   on the `.epro` for the PCB, and *Schematic Editor → File → Import → Non-KiCad
   Schematic* on the same `.epro` for the schematic. The `.epro2` file is a newer
   format that KiCad 9 can't read. The untouched importer output is the first commit
   that added this directory.
2. `tools/fixup_import.py` (run with KiCad's Python) fixes the importer problems below.
   It is the second commit, so the diff shows exactly what changed.

### Importer problems found and fixed

| Problem in the raw import | Effect | Fix |
| --- | --- | --- |
| The `.epro` stores every SMD pad with a 0.001 mm placeholder hole, and the importer turned all **367 SMD pads into all-layer through-hole pads** | Board unmanufacturable; each SMD pad shorted bottom-layer tracks (61 shorts) | Pads with a hole under 0.01 mm become SMD pads on their footprint's side. Result: 250 top + 117 bottom SMD pads and 89 PTH pads, exactly what EasyEDA's own board statistics report (`../pcb/pcb-info.txt`) |
| EasyEDA net names are global, but wire net names became KiCad *local* labels | The 10 port-LED nets (`P0_LED0` … `P4_LED1`) were cut between sheet P1 (switch chip) and sheet P2 (RJ45 LEDs) | Local labels used on both sheets with no global label become global labels |
| Schematic symbols point at a footprint library `YT9215S-5--easyedapro` that doesn't exist (the PCB importer wrote `YT9215S-5-port-switch.pretty`) | 249 ERC footprint-link warnings; no symbol→footprint link | Each symbol's footprint is set to the one the PCB uses for that reference |
| Footprint library has case-only duplicates (`C0402`/`c0402`, `R0402`/`r0402`, `RJ45-…`/`rj45-…`, `Test-Point-0.5mm`/`test-point-0.5mm`) | Breaks checkouts on macOS/Windows | Unused lowercase copies removed; the used one renamed `Test-Point-0.5mm_1` |
| PCB footprint Values empty | No values on the board or in a PCB BOM | Copied from the schematic |
| EasyEDA design rules not imported (KiCad default 0.2 mm clearance) | ~500 false clearance errors | Default net class set to the EasyEDA rules: 4 mil (0.1016 mm) clearance, 10 mil track, 24/12 mil via |
| Copper zones not filled | | Zones refilled |

### Checks after the fixes

* **Connectivity: schematic and PCB match.** `reports/net-compare.txt` compares every
  multi-pin net pin by pin: 55 of the 56 schematic nets are identical on the PCB, and
  the 56th (GND) differs only by the switch chip's exposed GND pad, which the design draws as a free pad
  (`Pad_e346`, number 129) on the PCB rather than as a symbol pin. Before the fixes,
  the 10 LED nets differed.
* **Routing: 0 unrouted connections**, same as EasyEDA (96 nets, 345 vias).
* **DRC** (`reports/drc.rpt`): 140 violations, down from 1448. What remains is mostly
  in the original design or cosmetic:
  * 6 `shorting_items` / 6 `solder_mask_bridge`: GND tracks run into USB1's two
    unconnected mounting holes (pads 1 and 2 of the USB-C footprint have no net on the
    PCB). Probably harmless (shell to GND) but worth a look.
  * Silkscreen overlaps, courtyard overlaps, 11 board-edge clearance hits against
    KiCad's default 0.5 mm edge rule, 21 tracks in footprint keepout areas, 4 doubled
    vias, 4 single-spoke thermals, and 1 unconnected item (a top and a bottom
    GND zone not joined near 98, 68 mm).
* **Schematic parity** (165): 146 `net_conflict` are only net *names* (EasyEDA's
  `$1N4948` style names on the PCB vs KiCad's `Net-(U1-BS)` / `/P1/NRST` names);
  connectivity is the same. Running *Tools → Update PCB from Schematic* (F8) in KiCad
  renames them. 29 `lib_footprint_mismatch` are board footprints that differ slightly
  from the library copy (EasyEDA keeps per-instance footprints). Test points have no
  value in the schematic (16). The two sheet-frame symbols (`?`) show as missing
  footprints.
* **ERC** (`reports/erc.rpt`): 353, down from 613. These are typical for an imported
  design: pins without power-flag drivers, label/wire endpoint warnings from how
  EasyEDA draws net labels, local and global labels sharing a name, and 6 unconnected
  U2 pins (I²C `SDA/SCK`, unused GPIO) which are also unconnected on the PCB.

### Not converted

* **3D models.** The `.epro` has no component 3D models, so KiCad's 3D view shows bare
  pads. The board's STEP model is in [`../pcb/pcb-3d.step`](../pcb/).
* The EasyEDA fonts (Century Gothic) aren't available; KiCad substitutes its own font
  for the board title text.
* The U2 symbol is still the RTL8367S-CG symbol from the original design; fit a YT9215S
  (see the top-level README).
