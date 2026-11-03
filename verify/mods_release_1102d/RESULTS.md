# RESULTS - sc3mods release 2026-11-02d + LAN republish

Replaces `sc3mods-2026-11-02c`. Owner call 2026-11-02: publish round 11-02b (re/sessions/ROUND_2026-11-02b_owner_feedback.md)
plus modlang. Binaries built from main `3339ade` (dev/rel1102d).

| what | record |
|---|---|
| restorefix: recycling-center restore killed the building (SIMECO 0x10003441 reads date vt+0x34/0x38), charged only when verified, Reconstruir (free for 11-02c victims), Vida Útil title / arrows / hourglass | verify/restorefix/RESULTS.md |
| modlang: mod text in Apps\sc3lang\{es,en,fr,de,it,nl,sv}.txt (277 keys, 5 machine translations), detection in sc3mods.dll | verify/modlang/RESULTS.md |
| transitmap: Mapa de transporte público (Ver datos slot 10) from per-origin-cell trip counts | verify/transitmap/RESULTS.md |
| vdcolors / vdcolors2: Cuadros red/green bars + legend; RCI A/P letters at the bottom, continuous tracks | verify/vdcolors/RESULTS.md |
| placehints: airport/seaport zone preview, plop land value halo | verify/placehints/RESULTS.md |
| hudpos: Bolsa next to the minimap, "?" left, picker halo, dark line | re/sessions/STATUS_hudpos.md |

## Stage and checks

- `stage/bins_1102d`: all 11 mods + sc3mods.dll built from 3339ade.
- `stage_lan_release.py --game stage/src --bins stage/bins_1102d --stock-modules original/modules --menu-bg stage/release/Apps/menu_bg.bmp
  --perf-ini stage/release/Apps/perf.ini --out stage/release_1102d --label 2026-11-02d`: 3,622 files, 707.0 MB. Against 11-02c:
  12 DLLs changed, Apps/sc3lang/*.txt (7) added, 0 removed.
- Launch check (release_1102d patched, windowed, Berlin, no input, 100 s): `11 mod(s) loaded`, LANG "Preferencias" -> es with
  277 keys, RESTOREFIX / RESTORE / VDTABS / RCIBARS / PLACEHINTS / HUDPOS / SIRENS / transit panel all on; only the benign
  `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, 12 logs + dataview.ini + landfill.ini deleted, manifest re-hashed: 0 changed,
  0 missing, 0 extra. No clicks in this check (each child checked its own).

Zip: the 11-02c zip with the 12 DLLs replaced, Apps/sc3lang/*.txt added, README.txt updated (header, sc3lang line,
NEW IN 2026-11-02d with the recycling-center warning). 142 entries, 141 checked against the staged manifest, 0 mismatches.
`sc3mods_2026-11-02d.zip` 50,692,107 bytes, SHA-256 953BFE73205A16853CC3B3FC245EBC812D2EE45B6239B39950F1092322F91987.

GitHub: `sc3mods-2026-11-02d`, target `fa5aec8`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-02d, asset
downloaded back, SHA-256 matches. The 11-02c notes start with a "superseded" line that points recycling-center users to Reconstruir.

LAN: `deploy_lan_release.sh stage/release_1102d` sent 19 of 3,622 files (2.7 MB). Served label `2026-11-02d`; served
sc3resize.dll, sc3mods.dll and sc3lang/fr.txt SHA-256 match the stage. Then `stage/release` -> `stage/release_1102c_old`,
`stage/release_1102d` -> `stage/release`.
