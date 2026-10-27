# Demo design: Easyduino RP2040

PartLens's demo and integration fixture is the **Easyduino RP2040** board by Hanqaqa, an open-source KiCad
design built for JLCPCB assembly.

| | |
|---|---|
| Source | https://github.com/Hanqaqa/Easyduino (`Raspberry Pi Pico 2040/Easyduino_RP2040.kicad_sch`) |
| Revision | commit `53b14b66d64f25c55f88971c1c1b51656126bd30` (2026-06-28) |
| Licence | CERN Open Hardware Licence Version 2 – Permissive (CERN-OHL-P-2.0), copy in `LICENSE-CERN-OHL-P-2.0.txt` |
| Files here | `bom.csv` only: a grouped BOM exported read-only from the schematic. No design files are copied or changed. |

`bom.csv` was produced with KiCad 10.0.6:

```sh
kicad-cli sch export bom -o bom.csv \
  --fields 'Reference,Value,Footprint,${QUANTITY},${DNP},LCSC,MPN,Manufacturer' \
  --labels 'Refs,Value,Footprint,Qty,DNP,LCSC,MPN,Manufacturer' \
  --group-by 'Value,Footprint,LCSC' --ref-range-delimiter '' Easyduino_RP2040.kicad_sch
```

PartLens can also import the schematic directly (`partlens.core.bom.import_kicad_schematic`), which runs the same
export.

PartLens analyses this BOM; it never modifies the design.
