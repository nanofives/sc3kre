# RESULTS - sc3mods release 2026-11-27b

Source: main a8ce39c9 (animrot: sc3perf ANIMROT, record verify/animrot/RESULTS.md), built at b217761f (a status file
on top, no source change). Player report on Simtropolis 2026-11-26: a TAB-rotated Spaceport or Science Center turns
except the part that holds the animation. Owner choice 2026-11-27: "Publish now".

## Build and stage
- stage/build_1127b from main (`build_mod.ps1 -Mod sc3perf`, CL cleared): sc3perf.dll 218,624 bytes, SHA-256
  FDAAACB53004B2293458967239B9313C51637113CAADF7DE0EFF89A195A77B2E.
- stage/bins_1127b = bins_1127 + that DLL (byte compare: exactly sc3perf.dll differs).
- `stage_lan_release.py --game stage/src --bins stage/bins_1127b --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1127b --label 2026-11-27b
  --community stage/community_1106`: 3,681 files, 789.4 MB (`stage.log`).
- Against LAN 2026-11-27 (stage/release manifest): 1 changed (Apps/sc3perf.dll), 0 added, 0 removed.

## Smoke test (dev/rel1127b, made with `sc3dev new rel1127b -Base stage/release_1127b -NoBuild`)
Shipped files only: stage/release_1127b sc3mods.dll in the tree's Apps, the 11 mod DLLs, perf.ini, sc3natworld.bin and
sc3lang in inst (byte compare against stage/release_1127b/Apps: equal). Windowed, no input sent. Harness claimed as
relprep1127b and released. PIDs 22228 and 26276, started by `sc3dev run` and stopped by PID.

| check | result |
|---|---|
| `AnimRotPowered2.sc3` (verify/animrot: powered Spaceports, Science Centers and coal plants at rotations 0-3), all mods, 85 s | `[+] 11 mod(s) loaded`, `ANIMROT> animated building sprites ... 11 slots + StartAnimation, ViewChange's SetAnimMachine call`, three machines `starts at zoom 2 slot 3 / 2 / 0 (view 1)` for rotations 2 / 1 / 3, draw counter past 1,000, only the benign `0xC0000096 @ SC3U+0x84122` |
| Berlin, all mods, 80 s | `[+] 11 mod(s) loaded`, ANIMROT and LOTRECT installed, `ovstale: 0 stale overlay file(s) dropped`, view up and responding, only the benign VEH line |

The pictures of the fix itself (rotations 0-3, four views, powered and unpowered, switch on and off, no mods) are the
animrot round's: `verify/animrot/owner_shots/` and `verify/animrot/RESULTS.md`.

## Jotti
0 of 13 engines for sc3perf.dll (job dhqntdkhsu), the stage/release_1127b bytes. `jotti_results.json`.

## Zip
stage/zip_1127 -> stage/zip_1127b with the DLL and README.txt (header "Release 2026-11-27b (replaces 2026-11-27)" and
a "NEW IN 2026-11-27b" section, 14 lines added, 1 changed). `work/mkzip.py` in the 11-27 entry order: 200 entries,
`testzip` clean, against the 2026-11-27 zip exactly 2 differ (Apps/sc3perf.dll, README.txt).
`stage/sc3mods_2026-11-27b.zip`, 111,345,707 bytes, SHA-256
C3D0F050A9D3B5D8BAA2D9D119169ACB606E7FDC05BFF3313A23598508B7F069.
