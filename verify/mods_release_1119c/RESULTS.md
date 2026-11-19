# RESULTS - sc3mods release 2026-11-19c + LAN 2026-11-19c

Replaces sc3mods-2026-11-19b. Owner calls 2026-11-19: "Test other civic buttons, and then Civic list dialog", then
"Yes, release". Source: main d771707.

| what | merges | record |
|---|---|---|
| Civic looks list window (stock catalog window class 0xe3091435 under our own mode id, press caught in SIMGEOM's command factory vtable 0x100291f4 +0x18), cycle kept as sc3resize.ini [buildings] civiclist=0 | df8b6c7 (merge before it) | verify/civdlg/RESULTS.md, re/analysis/CIVIC_REWARD.md section 6 |
| Checks of 2026-11-19b: 17 civic bases cycle, fire / school / hospital / college looks, rewards 1x1 / 3x3 / 4x4, 3x3 growable grows in Frankfurt (16 lots) | dca2fb0 | verify/civtest/RESULTS.md |
| README "Building tools" and docs/buildings civic section describe the list | d771707 | |

## Stage and checks

- sc3resize from main into stage/build_1119c (755,200 bytes). stage/bins_1119c = bins_1119b + it + the 7 lang tables
  (357 keys each, 0 missing). Jotti: 0 / 13.
- stage_lan_release.py label 2026-11-19c: 3,679 files, against 2026-11-19b exactly 8 changed (sc3resize.dll, 7 lang
  tables). stage/release swapped (old: stage/release_1119b_old), LAN deploy incremental (8 files, 0.9 MB), served label
  2026-11-19c 3679.
- Smoke: dev tree from the new stage with the shipped DLLs, xsect_sweep_built.sc3 loaded windowed: 11 mods loaded, lang
  357 keys, CIVVAR / NEWREWARD "not installed ... stock" lines, one VEH FAULT line = the usual startup 0xC0000096 at
  SC3U.exe+0x84122. City drawn (picture checked).

## Zip

The 2026-11-19b zip tree with sc3resize.dll and Apps/sc3lang from the stage, README.txt (header 2026-11-19c,
NEW IN 2026-11-19c). 198 entries: 191 equal to the LAN manifest, overlay SYS.PAK differs by design, README.txt and the
5 tools\bld_render files not in it. sc3mods_2026-11-19c.zip, SHA-256
3A81AB19E95515E53A11F70E4C3804172E5CEC52AEE57FF95682345F82740BE2.

GitHub: `sc3mods-2026-11-19c`, target d771707, asset downloaded back, SHA-256 matches. The 2026-11-19b notes start with
a "superseded" line.

Not checked: the list's other 5 languages in game (machine translations), double-click on an entry. The list shows a
fixed line, not the importer's description of the look.
