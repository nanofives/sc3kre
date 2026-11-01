# RESULTS - sc3mods release 2026-11-01 + LAN republish

Replaces `sc3mods-2026-10-31`. Owner call 2026-11-01: "Publish a release with these fixes". Source as of `c590087`.

| what | merge | record |
|---|---|---|
| graphfix: axis from the page-local plot rect (first draw was 40/34 px off), labels clamped inside | dcc1ee6 | verify/graphfix/RESULTS.md |
| pickerui: eyedropper cursor, minimap button art, no banner, tooltip not covered (RCIFIX band only) | 0d60663 | verify/pickerui/RESULTS.md |
| davtouch: DAVTOUCH / DBVTOUCH, a touching road keeps the diagonal band | 1513e4f | verify/davtouch/RESULTS.md |
| avrbtchain: DAVTWO two-way look twins 21830..21835, diagonal_avenue 0.7.0 | c590087 | verify/avrbtchain/RESULTS.md |
| cyantri: lab tool only (nb_drive highlight refresh), nothing shipped | 7ee5ed9 | verify/cyantri/RESULTS.md |

## Stage and checks

- Stage source: `diagonal_avenue` 0.7.0 reinstalled in `stage\src` (pack copied from stage\src, manifest + `two_2183*.lanes.json`
  + README from main's example, `netpack uninstall` + `install --tree stage\src --allow-tree`; it is now last in the ledger).
- `stage/bins_1101`: 11 binaries from main `c590087`. Label `2026-11-01`, 3,614 files, 706.6 MB.
- Launch check (stage/release patched, windowed, no input, 90 s, Berlin): `10 mod(s) loaded`, sc3netmod reads
  `diagonal_avenue.txt: variant 21830..21835`, no bad table lines, GRAPHAXIS and PICKER detours on, only the benign
  `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs and first-start ini files deleted, manifest re-hashed: 0 changed, 0 missing,
  0 extra.

LAN: 67 of 3,614 files sent (56.4 MB: the 11 binaries plus the regenerated netmod overlay). Served label `2026-11-01`.

Zip: the 2026-10-31 zip with the 11 binaries replaced, `mods/` replaced from the stage, README.txt (NEW IN 2026-11-01).
134 entries, 132 files checked against the staged manifest, 0 mismatches.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3autosave.dll | 133120 | 64D8BE3D01045C0509BBCCA0F47204A7E4F8675E4B660577383865C23600A72A |
| Apps/sc3bigcity.dll | 140288 | 88A152415A3AE7882DB3AA032EEC32F9F25CB486FADC749660CE52432BB6C53C |
| Apps/sc3dataview.dll | 152576 | C16BB10E3D3540581EA45E068A16DBBB70B604FC01B84AC77D410E8BBCD457E4 |
| Apps/sc3landfill.dll | 130048 | 5586DCF99F7FC69996B5905F8A9F8BEFBC1A82BA491E2C2A4D65F09E4F468D88 |
| Apps/sc3mods.dll | 114176 | 8A8354A4DF4A8203DA239063F5FA6EFEEFE1E3661FB785DB5ED3550F289ED0B8 |
| Apps/sc3netmod.dll | 437760 | 70912197630AF7AF2BA7FAD6481E165FFBEA47727D1B79A6BE8771BDE4A7DEC8 |
| Apps/sc3overscroll.dll | 134144 | 1510C3246E3A6BEF1CE4EF0BE93A08DD547A7FF0235076EDC339CD7AEEE0BA86 |
| Apps/sc3perf.dll | 191488 | 4A661E475E93DD4298DF3F6BC2834313ABD7D8B37BF4ACF6F8A1391D0C73AF99 |
| Apps/sc3resize.dll | 529920 | 0EDAEA498ECDC2C265A046FAC661A06AF408A4B05DFF764E2F6B5D2FEB7025A1 |
| Apps/sc3simrun.dll | 121856 | 6358206E47BCF048C08B6D04742580B6E1629C8B9C368B2EDE801AF661E64818 |
| Apps/sc3undo.dll | 148480 | 8FE511799260346276D2699A7B88325B330B78C435DC58132B3EB40FE5055311 |
| `sc3mods_2026-11-01.zip` | 50,266,703 | 6E203272AE35FE65E8D872DBE11C81739C4B0C84A1F635E987C1474B6FE957D4 |

Owner checks: picker cursor with the real mouse and pointer size, the Big One diagonal after loading (lower avenue x 584/585
is now two-way), touching roads on diagonals in normal play.
