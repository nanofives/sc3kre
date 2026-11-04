# RESULTS - sc3mods release 2026-11-04 + LAN republish

Replaces `sc3mods-2026-11-03d`. Owner call 2026-11-04: publish saltfix (verify/saltfix/RESULTS.md: salt water by flood from the
map edge over open water, rivers and lakes fresh; new terrain automatic, existing city through "Recalcular agua salada").
Source: main `4d52b33`.

- `stage/bins_1104` = `stage/bins_1103d` with `sc3resize.dll` rebuilt from 4d52b33 (dev/rel1104). Since bfd16f7 only sc3resize.c,
  the new sc3resize_saltfix.c and the 7 language tables changed.
- Languages: 3 new keys (336 per table, `sc3lang.py check` clean). Page C opened in-game with the GAME language switched
  (sc3resize.ini [language] folder = ENGLISH (Spanish on this install), English-UK, FRENCH, GERMAN, ITALIAN, DUTCH, SWEDISH):
  sc3mods detected each language, the new "Agua salada solo en el mar" row, the "now, in this city" heading and the
  "Recalcular agua salada" checkbox fit in all 7, checkbox unticked. Sheet: verify/saltfix/owner_shots/page_all_languages.png.
- `stage_lan_release.py --game stage/src --bins stage/bins_1104 --stock-modules original/modules --menu-bg stage/release/Apps/menu_bg.bmp
  --perf-ini stage/release/Apps/perf.ini --out stage/release_1104 --label 2026-11-04`: 3,622 files, 707.1 MB. Against 11-03d:
  changed Apps/sc3resize.dll and Apps/sc3lang/*.txt (7), 0 added, 0 removed.
- Launch check (release_1104 patched, windowed, Berlin, no input, 100 s after unpause): LANG es 336 keys, `SALTFIX> on`,
  STATIONWARN scan 86 / 2 not connected, GHOSTFIX on; only the benign `0xC0000096 @ SC3U+0x84122`. A second short start
  (no city) logged `11 mod(s) loaded`. After each: `-Restore`, 12 logs + dataview.ini + landfill.ini deleted, manifest
  re-hashed: 0 changed, 0 missing, 0 extra.

Zip: the 11-03d zip with Apps/sc3resize.dll and Apps/sc3lang/*.txt replaced, README.txt updated (header, NEW IN 2026-11-04).
142 entries, 141 checked against the staged manifest, 0 mismatches. `sc3mods_2026-11-04.zip` 50,727,424 bytes, SHA-256
A0A40EDCB4C5EABE634374D26AE538BD297BE288BA24C01E7044606CD4624BA0.

GitHub: `sc3mods-2026-11-04`, target `176990a`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-04, asset
downloaded back, SHA-256 matches. The 11-03d notes start with a "superseded" line.
LAN: deployed from `stage/release_1104`, served label `2026-11-04`, served sc3resize.dll and sc3lang/fr.txt match the stage.
Then `stage/release` -> `stage/release_1103d_old`, `stage/release_1104` -> `stage/release`.
