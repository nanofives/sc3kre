# RESULTS - sc3mods release 2026-10-31 + LAN republish

Replaces `sc3mods-2026-10-29d`. Owner call 2026-10-31: "Publish a release with all of this" (round 2026-10-30,
`re/sessions/ROUND_1030.md`). Source as of `6373c75`.

| what | merge | record |
|---|---|---|
| sc3landfill: nearest-landfill routing, per-landfill fill in the "?" window, Vaciar ($50 per 1,000 t) | 1ffe939 | verify/landfill/RESULTS.md |
| sc3dataview: radiation layer 0x2735, trip success, congestion per network, edu/health capacity (V key) | 74c4e7d | verify/dataview/RESULTS.md |
| GRAPHAXIS + GRAPHNEW (5 graphs, `.sc3.graphs` history, autosaves too) | aa88137, 22b8a06, e27e886 | verify/graphaxis/RESULTS.md |
| PICKER eyedropper (minimap button, Ctrl+F) | 32e4630, 3447bd8 | verify/picker/RESULTS.md |
| BVGROW / DBVGROW / DAVGROW / DAVCUT: boulevard and diagonal edits bounded, no torn-down diagonals | a497251, 3dd2dca, 7686020 | verify/avslow/RESULTS.md, verify/avdiagbreak/RESULTS.md |

Not shipped as new: ports/airports research (notes only, b736fb7).

## Stage and checks

- `stage/bins_1031`: all 11 binaries built from main `6373c75` (10 mods + sc3mods.dll). Label `2026-10-31`, 3,614 files
  (+2: sc3landfill.dll, sc3dataview.dll), 706.4 MB.
- Launch check (stage/release patched, windowed, no input, 90 s): Craterville, `10 mod(s) loaded`, sc3landfill `READY:
  independent=1 ... UpdateCell hook on`, sc3dataview `AddLayer hooked` + `Cuadros page numbers hooked`, only the benign
  `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs and the two first-start ini files deleted, manifest re-hashed: 0
  changed, 0 missing, 0 extra.

LAN: 11 of 3,614 files sent (2.2 MB). Served label `2026-10-31`.

Zip: the 2026-10-29d zip with the 11 binaries replaced or added and README.txt updated (NEW IN 2026-10-31, the two
DLLs in WHAT'S INSIDE, landfill.ini / dataview.ini under OPTIONS). 134 entries. Every Apps and mods file matches the
staged manifest SHA-256 (132 checked, 0 mismatches), sc3mods_patch.ps1 equal to the stage copy.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3autosave.dll | 133120 | 88C55C654E5DD9DCA8C7D1152E1C3BBA905266541A92D81A67A37D88ACB3AF53 |
| Apps/sc3bigcity.dll | 140288 | 2B44A871B99231E0600328B63DC9ED5E1346DCA538553F793109235B80106BA6 |
| Apps/sc3dataview.dll | 152576 | 67CFC5FAAA20A491819173F7412BA34769E1B579465DB8495EAE4BFBAB45AC27 |
| Apps/sc3landfill.dll | 130048 | 5BC874EA716F3AB8090036EF35FBEF4084E82CA1E643FEFE62F05400974651BA |
| Apps/sc3mods.dll | 114176 | 9E22CCFC6FAF532BAACCAA81798E8E579504D760D6BA175CDA96E62C064080E1 |
| Apps/sc3netmod.dll | 425472 | 74015E190862EE5DCBB94EE3EFFFE0C44319B76BC13549CC5D19436E33EBB4CF |
| Apps/sc3overscroll.dll | 134144 | E68B1E8A79F4F4861F877C04C196318A7FD287899ECB4D0533C1FD8F191F077B |
| Apps/sc3perf.dll | 191488 | BF2CE48699514DD78872FD17A554ED097F3D0AE6D85E9CADF0E66B7FA15FFC5B |
| Apps/sc3resize.dll | 519680 | 66BB88B56C9B8A24B75C00B80F77C31E1B690AA7FDC98D416B5D02172EEC0180 |
| Apps/sc3simrun.dll | 121856 | A105C9D60C33B67BF4CE6A095A3995B1DF96BDE37D3B763C8B39EC1B1A034128 |
| Apps/sc3undo.dll | 148480 | 5E58DE18C0E1A70446DE8544D552EB61CFF1DA0721D5847D78FAC01C0F595E7D |
| `sc3mods_2026-10-31.zip` | 50,190,369 | D129F679E1C8BF7BCBE99432360C52B8F8FB8015E45F9207976F66C1F0212F91 |

Owner checks: real Ctrl+F and a real click on the picker, landfill "?" lines at a big UI scale and the fee, a city saved
after Vaciar loaded without the mod, the 10 / 100 year graph views over a long session.
