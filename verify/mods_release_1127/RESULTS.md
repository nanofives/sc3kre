# RESULTS - sc3mods release 2026-11-27

Source: main 9e6ebc91 (crash1127: sc3netmod OVSTALE + sc3perf NULLIMG, record verify/crash1127/RESULTS.md).
Owner choice 2026-11-27: "You delete, I guard" (guard + stale-file check, released).

## Build and stage
- stage/build_1127 from main 9e6ebc91 (`build_mod.ps1`, CL cleared): sc3perf 212,480 bytes, sc3netmod 551,424.
- stage/bins_1127 = bins_1126 + those 2 DLLs (byte compare: exactly those 2 differ).
- `stage_lan_release.py --game stage/src --bins stage/bins_1127 --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1127 --label 2026-11-27
  --community stage/community_1106`: 3,681 files, 789.4 MB.
- Against LAN 2026-11-26 (stage/release manifest): 2 changed (Apps/sc3netmod.dll, Apps/sc3perf.dll), 0 added, 0 removed.

## Smoke test (dev/rel1127, base stage/release_1127, shipped files only, byte-compared)
| check | result |
|---|---|
| Berlin, all mods | `[+] 11 mod(s) loaded`, view up 60 s, `ovstale: 0 stale overlay file(s) dropped`, `NULLIMG> 2 of 2 SIMSPR sites guarded`, 0 NULLIMG hits, only the benign `0xC0000096 @ SC3U+0x84122` |
| owner's Europolis 1024 + the owner's stale CSATTRIB.IXF in the overlay | `ovstale: 1 stale overlay file(s) dropped: CSATTRIB.IXF`, view up 60 s, 0 NULLIMG hits, only the benign VEH line (11-26 build: VEH FAULT SIMSPR+0x15B9 and exit) |

## Jotti
0 of 13 engines for sc3perf.dll (job 6c9rhcozuo) and sc3netmod.dll (vrhel4hm1v), the stage/release_1127 bytes.
`jotti_results.json`.

## Zip
stage/zip_1126 -> stage/zip_1127 with the 2 DLLs and README.txt (header "Release 2026-11-27 (replaces 2026-11-26)" and
a "NEW IN 2026-11-27" section, 13 lines added, 1 changed, bytes kept as Latin-1). `work/mkzip.py` in the 11-26 entry
order: 200 entries, `testzip` clean, against the 2026-11-26 zip exactly 3 differ (the 2 DLLs, README.txt).
`stage/sc3mods_2026-11-27.zip`, 111,342,695 bytes, SHA-256
D05ABA973B7D501AFDDDA1A1C88FC6D4A39E12D8379E5CBAB357186F50BF0BC8.
