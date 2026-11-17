# Motorcomm switch ICs: JTAG, SPI flash and UART pins

Researched 2026-11-16. Covers the YT9215 family (S, SC/SCH, RB). Tags: **[V]** verified in a datasheet or netlist, **[I]** inferred, **[C]** conflicting between sources.

## Headline findings

1. **The three YT9215 variants have three different pinouts.** Each one is a pin-for-pin drop-in for a different Realtek part. The Motorcomm selection guide (2023-03-08, `attachments/裕太微电子产品选型20230308.pdf` in the board repo) says so **[V]**:
   - YT9215S matches the RTL8367S;
   - YT9215RB matches the RTL8367RB-VB;
   - YT9215SC/SCH matches the RTL8367SC.

   So pin numbers from one variant's datasheet **cannot** be used for another. `switch-embedded-cpu.md` (2026-10-22) quoted YT9215SC pin numbers and said the S has "the same LQFP-128 pinout family". That is wrong for pin numbers. The XTAL pins show it: they are 83/84 on the S, 87/88 on the SC and 89/90 on the RB.
2. **Every YT9215 variant has the RISC-V MCU** **[V]**. The selection guide marks S, RB and SC all "内置RISC-V" (built-in RISC-V). The S and RB datasheets both list "Integrated RISC-V microprocessor", the `DIS_MCU` strap, SPI flash, two UARTs and two JTAG groups. This corrects the memory note that only the SC has the CPU.
3. **The newest datasheet drops JTAG.** The 2025 YT9215SCH datasheet (V1.03, 2025-02-10) removed every JTAG pin name. The same pins are now listed as GPIO, LED and I²C only. UART and SPI-flash pins remain. Either Motorcomm stopped documenting JTAG or it is disabled in production silicon **[I]**. Treat JTAG as unconfirmed until it has been probed.
4. **The 2025 SCH datasheet is the first public MCU description** **[V]**:
   - 64 KB SRAM, 16 KB boot ROM and 2 KB I-cache.
   - SPI NOR flash up to 8 MB, single or dual I/O, 3-byte addressing.
   - Boot modes: execute in place (XIP) from flash, flash→RAM, or EEPROM→RAM.

## YT9215S (RTL8367S pinout, used on the mirrored board)

Sources: YT9215S Datasheet Draft_01 (2022-11-08, `attachments/YT9215S_Datasheet_draft_V0.1.pdf` in the repo). Also Draft_05 (2023-02-21) on [LCSC/szlcsc](https://atta.szlcsc.com/upload/public/pdf/source/20230829/432918AE041FF2F1E459558942DE4628.pdf). Both drafts give the same pin numbers **[V]**.

The board netlist (`schematic/netlist-schematic.enet`) uses an RTL8367S-CG symbol. It has XTAL on 83/84 and nRESET on 86, and the author reports it boots with a YT9215S fitted. That confirms the shipping S silicon uses this pinout **[V]**.

### SPI flash

One interface. The `SPF_MUX_SEL` strap on pin 48 picks which pins it uses. Pin 48 has an internal pull-down, and pull-down selects **SPF1**.

| Signal | SPF0 (pull pin 48 up) | SPF1 (pin 48 low, the default) |
|---|---|---|
| SCK | 48 (GPIO9, RGMII TXD0) | 77 (GPIO40, P2LED1) |
| SI (chip output → flash DI/IO0) | 49 (GPIO10, RGMII TXCTL) | 71 (GPIO34, P4LED1) |
| SO (flash DO/IO1 → chip) | 53 (GPIO14, RGMII RXD0) | 72 (GPIO35, P3LED1) |
| CS# | 54 (GPIO15, RGMII RXD1) | 76 (GPIO39, `DISAUTOLOAD` strap) |

- `EN_SPIF` (pin 74, GPIO37/P3LED0) is the enable strap: pull up to enable **[V]**.
- SPF0 takes over the extension-port RGMII/MII pins. If the adapter's MCU link uses that port, flash has to go on SPF1 **[I]**.
- **Strap clash [I]:** on SPF1, CS# is the `DISAUTOLOAD` strap pin. The usual CS# pull-up therefore latches DISAUTOLOAD=1. In the SCH boot table that means "no action", so nothing would load. This needs a bench test, or a pull-down on CS# during reset. The S datasheet has no boot-mode table, so this conclusion borrows the SCH table.

### JTAG (two groups, both shared with LEDs and straps) [V]

| Signal | JTAG0 | JTAG1 |
|---|---|---|
| TCK | 73 (GPIO36, `EN_PWRLIGHT` strap) | 79 (GPIO44, `EN_PHY` strap) |
| TMS | 79 (GPIO44, shared with JTAG1 TCK) | 71 (GPIO34, P4LED1) |
| TDI | 81 (GPIO46, LED_CK, `SMI_SEL` strap) | 72 (GPIO35, P3LED1) |
| TDO | 80 (GPIO45, LED_DA) | 77 (GPIO40, P2LED1) |

- Pin 79 is listed as both JTAG1_TCK and JTAG0_TMS in both drafts. The two groups cannot be used at once **[V]**.
- JTAG1 uses the same pins as SPF1 (71/72/77), so it cannot coexist with flash on SPF1 **[I]**.
- There is no TRST and no pin that selects JTAG. Whether the pins become JTAG after reset, or only after a register write, is not documented. The same is true of whether they reach the RISC-V debug module or only boundary scan **[I]**.

### UART

| UART | RX | TX |
|---|---|---|
| UART0 | 45 (GPIO6, RGMII TXD3, SWITCH_ID_1 strap) | 46 (GPIO7, RGMII TXD2) |
| UART1 | 19 (GPIO2, INTERRUPT) | 75 (GPIO38, P2LED0, `DIS_MCU` strap) |
| UART2 | 73 (GPIO36, `EN_PWRLIGHT` strap) | 75 (same pin as UART1 TX) **[C]** |

- UART0 appears in the pin table of both drafts and in the Draft_05 UART table. The Draft_01 UART table leaves it out.
- On the RTL8367S symbol, pins 45/46 are labelled UART_RX/UART_TX. So UART0 is the Realtek-compatible console position **[V]**.
- TX on 75 for both UART1 and UART2 is what the datasheet says. It is probably a typo for one of them **[C]**.

### Other boot-related straps (S)

- Pin 75 `DIS_MCU`: pull-up disables the MCU.
- Pin 76 `DISAUTOLOAD`.
- Pin 70 `EEPROM_MOD`: selects EEPROM size above or at most 16 Kbit.
- I²C EEPROM: SCL on 87, SDA on 88 (GPIO48/49, also the slave MDC/MDIO).

### How the mirrored board wires these pins [V, from the netlist]

| Pin | Function | Board net and parts | Strap level |
|---|---|---|---|
| 45, 46 (UART0) | console | **no net, no pad** | — |
| 19 (UART1 RX) | — | no net | — |
| 48 SPF_MUX_SEL | — | no net (internal PD → SPF1) | 0 |
| 74 EN_SPIF | P3_LED0 | R27 4.7 k to GND, R31 to LED | 0 → flash off |
| 75 DIS_MCU / UART1-2 TX | P2_LED0 | R19 4.7 k to GND, R25 to LED | **0 → MCU enabled** |
| 76 DISAUTOLOAD / SPF1_CS | DISAUTOLOAD | R11 4.7 k to 3V3, TP14 | 1 → no autoload |
| 73 JTAG0_TCK / UART2_RX | EN_PWRLIGHT | R12 4.7 k to 3V3 | 1 |
| 79 JTAG1_TCK / JTAG0_TMS | P1_LED0 | R17 to 3V3, R23 to LED | 1 |
| 80 JTAG0_TDO | P0_LED1 | R16 to 3V3, R22 to LED | 1 |
| 81 JTAG0_TDI | P0_LED0 | R15 to 3V3, R21 to LED | 1 |
| 71 JTAG1_TMS / SPF1_SI | P4_LED1 | R30 to 3V3, R34 to LED | 1 |
| 72 JTAG1_TDI / SPF1_SO | P3_LED1 | R28 to GND, R32 to LED | 0 |
| 77 JTAG1_TDO / SPF1_SCK | P2_LED1 | R20 to GND, R26 to LED | 0 |
| 87, 88 (EEPROM I²C) | — | no net | — |

What the wiring means:
- The board runs with the MCU **enabled** but with no flash and no EEPROM. In the SCH table, DISAUTOLOAD=1 is "no action". So the MCU probably sits in its boot ROM doing nothing **[I]**.
- To probe JTAG0 or JTAG1, or UART2 (RX 73 / TX 75), lift the 470 Ω LED resistors and tap the 4.7 k strap pads. Leaving the LEDs on loads TCK and TDO **[I]**.
- UART0 has no pad, so it means soldering to the LQFP leads 45/46.

## YT9215SC / YT9215SCH (RTL8367SC pinout, LQFP-128 with EPAD)

Sources: [YT9215SC Draft_07, 2023-02-28](https://atta.szlcsc.com/upload/public/pdf/source/20251231/E8DA45036F659501F9799590211A88C7.pdf) and [YT9215SCH V1.03, 2025-02-10](https://atta.szlcsc.com/upload/public/pdf/source/20251231/76B4B53D0DFB99DA2607FBF198C74D22.pdf).

| Function | Pins | Notes |
|---|---|---|
| SPF0 | SCK 49, SI 50, SO 54, CS 55 | `SPF_MUX_SEL` on 49, pull-up selects SPF0 **[V]** |
| SPF1 (default) | SO 78, SI 79, CS 81, SCK 83 | **[V]** both docs |
| EN_SPIF / DIS_MCU / DISAUTOLOAD | 75 / 76 / 77 | **[V]** |
| UART0 | RX 46, TX 47 | **[V]** both docs |
| UART1 | RX 70 (DIS_SPIS strap), TX 76 (DIS_MCU strap) | **[V]** both docs |
| JTAG0 | TCK 73, TMS 72, TDI 74, TDO 90 | Draft_07 only; **removed in V1.03** |
| JTAG1 | TCK 83, TMS 81, TDI 84, TDO 67 | Draft_07 only; **removed in V1.03** |
| EEPROM / slave I²C | SCL 91, SDA 92 | slave SPI on 90–93 |

SCH V1.03 boot table (Table 25) **[V]**:

| DISAUTOLOAD | DIS_MCU | EN_SPIF | DIS_SPIS | SMI_SEL | Loads |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 1 | 1 | EEPROM → MCU RAM |
| 0 | 0 | 1 | X | X | **XIP from SPI flash** |
| 0 | 1 | 0 | X | X | EEPROM → registers |
| 0 | 1 | 1 | X | X | Flash → RAM (as printed; odd with the MCU disabled) **[C]** |
| others | | | | | no action |

## YT9215RB (RTL8367RB-VB pinout)

Source: [YT9215RB Draft_05, 2023-02-16 (LCSC)](https://datasheet.lcsc.com/datasheet/pdf/762da1ba434211a9b4be1fec673c7fcf.pdf?productCode=C5449202) **[V]**.

| Function | Pins |
|---|---|
| SPF0 | SCK 44 (`SPF_MUX_SEL`), SI 45, SO 49, CS 50 |
| SPF1 | SO 80, SI 81, CS 83, SCK 84 |
| JTAG0 | TCK 75, TMS 74, TDI 76, TDO 92 |
| JTAG1 | TCK 84, TMS 83, TDI 85, TDO 20 |
| UART0 | RX 41, TX 42 |
| UART1 | RX 72, TX 78 (`DIS_MCU` strap) |
| Straps | EN_SPIF 77, DIS_MCU 78, DISAUTOLOAD 79 |

## Other Motorcomm parts

- YT8512, YT8521, YT8531 and YT8821 are plain PHYs. The selection guide lists no CPU for any of them. They have MDIO, LEDs and straps, with no JTAG, UART or flash interface. These pin lists were not checked in detail, because nothing debug-related is there to find.
- YT8614 (a QSGMII PHY) is the same.
- YT9218N/MB, an 8-port relative, is in the Linux driver's chip table. No datasheet was checked for it.
- The Linux driver (`drivers/net/dsa/motorcomm/chip.c`) identifies variants by `CHIP_ID` 0x80008 (major 0x9002 = YT9215) plus `CHIP_MODE`: 1 = SC, 2 = S, 3 = RB.
- The latched strap values can be read back over MDIO from `PON_STRAP_VAL` (0x80324). This gives a way to check DIS_MCU/EN_SPIF levels on real hardware **[V]**.

## Community and SDK status

- No public firmware, SDK, OpenOCD config, boot-ROM dump or forum write-up was found for the YT9215 MCU. Searches covered English and Chinese terms.
- The image format and signing for flash or EEPROM boot are still unknown.

## Implications for the adapter

- If we use the YT9215S, strap `DIS_MCU` (pin 75) high as planned and leave `EN_SPIF` low. That is the opposite of the mirrored board, which leaves the MCU enabled.
- To keep a debug option open cheaply, put 0402 pads on:
  - pins 45/46 (UART0);
  - pins 73/75 (UART2);
  - the JTAG0 set 73/79/80/81.

  Most of these already carry strap resistors, so a test pad per net costs almost nothing.
- A first bench experiment on the mirrored board needs no new PCB:
  1. Tie DIS_MCU low, as the board already does.
  2. Scan JTAG0 at R12/R17/R16/R15 after lifting R21/R22/R23 for an IDCODE.
  3. Listen on UART0 (pins 45/46) and UART2 for boot-ROM output.

## Photographed LX-IS601F V2.0 boards (added 2026-11-16)

Tim's photographed boards (silkscreen LX-IS601F V2.0) carry a **YT9215SCH**, not a YT9215S, so the SC/SCH pin numbers above apply, not the S numbers **[V, chip marking on two boards]**. Annotated photo: `lx-is601f-board/lx-is601f-debug-pins-annotated.png`.

Pin 1 is the lead beside the small dimple; pins 65–96 face the crystal Y6, pins 33–64 face R44/R89/R92/R93. Traced from top-side photos only **[I]**:

| Function | Pin | Where it lands |
|---|---|---|
| UART0 RX / TX | 46 / 47 | no trace, chip leads only |
| UART1 RX / TX | 70 / 76 | each to a via just above the chip (76 is also DIS_MCU) |
| SPF1 SCK / SI / SO / CS | 83 / 79 / 78 / 81 | 83, 78, 81 to vias; 79 has no trace |
| SPF0 SCK / SI / SO / CS | 49 / 50 / 54 / 55 | chip-side pads of R93 / R92 / R89 / R44 |
| JTAG0 TCK / TMS / TDI / TDO (2023 draft names) | 73 / 72 / 74 / 90 | 72, 73 are LED traces; 74 to a via; 90 no trace |
| JTAG1 TCK / TMS / TDI / TDO (2023 draft names) | 83 / 81 / 84 / 67 | vias for 83, 81, 84; 67 no trace |
| EN_SPIF / DIS_MCU / DISAUTOLOAD | 75 / 76 / 77 | vias |

Not known: where the vias go on other layers, strap levels, and what the far pads of R44/R89/R92/R93 connect to. A bottom-side photo and a continuity check would settle these. One oddity: pin 86 (AVDDH in the datasheet) appears to run to R22 beside the crystal, which was not resolved.
