# R8 schematics

[Open the PDF](infrabot-pcb-4p3-R8-schematic.pdf)

Six sheets cover the core-module interface, power supply, Ethernet and clocks, communication/debug interfaces, display connection and front-panel controls. The PDF uses ordinary engineering borders and bottom-right title blocks. There is no presentation cover. Bookmarks select individual sheets.

The editable schematics are grouped by circuit function, with local connections drawn directly. Power rails and connections between functional blocks still use named nets. Component identities, part numbers, footprints and the 338 assigned pin networks are preserved.

`native-svg-R8.zip` is the native SVG export of the current source. `provenance.json` records source hashes, the PDF hash, native checks and rendering checks. Vendor reference schematics are not redistributed here.

## Optional PDF rebuild

The regular verifier needs only Python's standard library. Rebuilding the PDF also requires ReportLab, pypdf and system Rsvg/Cairo/PyGObject. On Ubuntu, run these commands from the repository root:

```bash
sudo apt install python3-gi python3-cairo gir1.2-rsvg-2.0 fonts-liberation fonts-noto-cjk
python3 -m venv .build/pdf-venv
.build/pdf-venv/bin/python -m pip install -r tools/pdf-requirements.txt
/usr/bin/python3 -B tools/check_schematic_text.py
.build/pdf-venv/bin/python -B tools/build_schematic_pdf.py
```

`--svg-python` selects the system Python used for SVG rendering. The builder reads the frozen SVG export; it does not edit hardware files. After a schematic change, export new SVG sheets in EDA before rebuilding the PDF and updating the checked manifest. Font versions can affect the PDF byte hash.

The layout tool applies `tools/schematic_text_adjustments.json` after arranging functional blocks. It records reviewed label positions and local wire paths so regeneration preserves their clearance. `tools/check_schematic_text.py` measures actual font ink bounds in the exported SVG and checks text/wire overlap, text/text overlap and different-net wire/pin-stem crossings. Separate text objects must also have at least 1.5 native drawing units of ink clearance; this catches nearly touching labels that an intersection test misses. Inspect all rendered PDF pages as well; this geometry check is not an electrical review.

The PDF renderer also applies `tools/schematic_pdf_text_offsets.json`: pin-number baselines are lifted clear of their pin strokes, two USB-C numbers are separated from no-connect marks, and RJ45 signal names and internal notes are moved clear of symbol artwork. These offsets address font placement differences identified by comparing the editor's native PNG with the PDF render. They affect text presentation only. The raw native SVG export, embedded libraries and pin identities are preserved. The renderer and clearance checker share the same preparation function.

The project remains a development draft. The drawings do not replace supplier process review or physical validation.
