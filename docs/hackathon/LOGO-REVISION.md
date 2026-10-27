# Magnifying-glass logo revision

The owner requested a magnifying glass instead of a camera-style lens, including the executable icon.
The built-in image tool edited the original project mark. Current art and the exact edit prompt are in
[BRAND.md](../../assets/brand/BRAND.md). Transparent PNG variants and the 16/24/32/48/64/128/256-pixel
Windows ICO were regenerated with the existing development-only derivative script. The app sidebar,
window/taskbar icon and executable now use the replacement. The welcome illustration is byte-identical.
Prior logo assets are preserved in `.partlens/brand-revisions/20261026T000026Z-d892ba`.

The first build passed packaged acceptance but could not replace the running executable. Its accepted
candidate and earlier binary were preserved. An idle app's unsent draft was retained before restarting;
it was not sent to any model. The accepted candidate was then installed into `dist/PartLens.exe`.

- Build: `.partlens/desktop-builds/20261026T000041Z-7fe0af.jsonl`.
- Completed installation: `.partlens/desktop-builds/20261026T000400Z-3b04cb.jsonl`.
- Embedded PE icon audit: `.partlens/desktop-audits/20261026T000403Z-32d258.jsonl`.
- Actual RT_ICON resources match all seven new ICO images byte-for-byte.
- Executable: 48,133,698 bytes; SHA-256 `3d1a61f51a38ff088dbc364a9920c4c2646269ff528c0d7e953790d3d1664a3c`.
- Packaged acceptance passed, including real bundled H-MEM cold recall and encrypted settings round-trip.
- CMD rerun: **346 passed**, `.partlens/validation/tests-20261026T000213Z-2653bb.txt`.

The initial concurrent CMD run had 345 passes and a Tk initialization failure while loading `vistaTheme.tcl`;
it remains recorded at `.partlens/validation/tests-20261026T000039Z-4b8ed7.txt`. The file was present at
inspection and the separate rerun passed. No engineering code, supplier interface, credential, paid
inference, publication or signing configuration changed. No supplier/model operation was needed.
