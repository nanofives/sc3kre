# RESULTS - sc3mods release 2026-11-03d + LAN republish

Replaces `sc3mods-2026-11-03c`. Owner call 2026-11-03: publish modtoggle (verify/modtoggle/RESULTS.md, "Activar mods" page,
`sc3mods.ini [mods]/[env]`), "in all languages". Source: main `bfd16f7`.

- `stage/bins_1103d` = `stage/bins_1103c` with `sc3resize.dll` and `sc3mods.dll` rebuilt from bfd16f7 (dev/rel1103d). Since
  9309a63 only sc3resize.c, sc3mods.c and the 7 language tables changed.
- Languages: 27 new keys `resize.mt_*` in all 7 tables (333 keys each, `sc3lang.py check` clean). The page and the
  "Activar mods..." button were opened in-game with `SC3MODS_LANG` = en, fr, de, it, nl, sv (es in verify/modtoggle): every
  table loaded with 333 keys, every caption fits its column, accents drawn. Pictures (not for git):
  verify/modtoggle/owner_shots/activar_mods_all_languages.png and activar_mods_<lang>.png.
- `stage_lan_release.py --game stage/src --bins stage/bins_1103d --stock-modules original/modules --menu-bg stage/release/Apps/menu_bg.bmp
  --perf-ini stage/release/Apps/perf.ini --out stage/release_1103d --label 2026-11-03d`: 3,622 files, 707.1 MB. Against 11-03c:
  changed Apps/sc3resize.dll, Apps/sc3mods.dll and Apps/sc3lang/*.txt (7), 0 added, 0 removed.
- Launch check (release_1103d patched, windowed, Berlin, no input, ~100 s after unpause): `11 mod(s) loaded`, LANG es 333 keys,
  LANGSEL 7 languages, PLACEHINTS on, STATIONWARN scan 86 / 2 not connected, GHOSTFIX on; only the benign
  `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, 12 logs + dataview.ini + landfill.ini deleted, manifest re-hashed: 0 changed,
  0 missing, 0 extra.

Zip: the 11-03c zip with Apps/sc3resize.dll, Apps/sc3mods.dll and Apps/sc3lang/*.txt replaced, README.txt updated (header,
NEW IN 2026-11-03d, sc3mods.ini under OPTIONS). 142 entries, 141 checked against the staged manifest, 0 mismatches.
`sc3mods_2026-11-03d.zip` 50,720,316 bytes, SHA-256 422B30897478386D25BAEE5B11A930587E9D5A83F68210A86813E87BFDD27960.
