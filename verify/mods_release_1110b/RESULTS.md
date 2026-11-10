# RESULTS - sc3mods release 2026-11-10b + LAN 2026-11-10b

Replaces `sc3mods-2026-11-10` (GitHub) and LAN `2026-11-10`. Owner call 2026-11-10: "Rescan first, and then Merge +
release". Source: main `f7710d5` (merge of child/crashguard `66f556d`).

| what | commit | record |
|---|---|---|
| VALVEREF: sc3resize graphs (`gn_ctx`) and RCI bars (`rcb_read`) no longer Release the borrowed GetSpecificLayer pointer (the players' crash after ~100 game months) | 66f556d | verify/crashguard/RESULTS.md |
| sc3perf RCZERO + VALVESHUT (ported from thronevintagetech's SC3KU package), RCTRACE diagnostic (off by default) | 66f556d | verify/crashguard/RESULTS.md |
| build_mod.ps1 AVVERSION: VERSIONINFO resource in every mod DLL (Bitdefender Gen:Variant.Draftor.8144 on sc3netmod) | 66f556d | verify/avflag/RESULTS.md |

## Build and scan

- `stage/build_1110b`: all 12 mod DLLs built from main with `build_mod.ps1` (every one carries version info now).
  `stage/bins_1110b` = `stage/bins_1110` with those 12 DLLs (sc3lang tables identical, sc3natworld.bin unchanged).
- Jotti's malware scan (13 engines incl. BitDefender, eScan, G DATA), the exact 12 release DLLs: **0 of 13 on each**.
  Windows Defender (MpCmdRun) found nothing in the same builds.

| DLL | SHA-256 prefix |
|---|---|
| sc3autosave.dll | c06e0a52ef78e568 |
| sc3bigcity.dll | e152a1df4b3e8f43 |
| sc3dataview.dll | 7099682f8d0c1be9 |
| sc3landfill.dll | d86fba7aaa76afb7 |
| sc3mods.dll | 1891524f8ad616a0 |
| sc3netmod.dll | 00e3024cd2150bb3 |
| sc3overscroll.dll | 80b0546637443d76 |
| sc3perf.dll | 563056f431f0b020 |
| sc3resize.dll | f25a3f9d206c951d |
| sc3restore.dll | 784275dfaf91e7f8 |
| sc3simrun.dll | 070e8d73f9d9ed13 |
| sc3undo.dll | fd0acd607a321990 |

## Stage and checks

- `stage_lan_release.py --game stage/src --bins stage/bins_1110b --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1110b --label 2026-11-10b
  --community stage/community_1106`: 3,645 files, 712.3 MB. Against LAN 2026-11-10: 12 changed (the 12 DLLs),
  0 added, 0 removed.
- Launch check (release_1110b patched with its own `sc3mods_patch.ps1`, SC3U.exe started directly with no SC3* overrides
  except SC3RESIZE_WINMEM=0 for a window, Berlin, no input, ~2 min): `11 mod(s) loaded`, `CRASHGUARD> rc_zero=1 ...
  valve_lock=1`, `VALVESHUT> SIMRCI ...: guard=1 hold=1 lock=1`, avenue_ends.txt variants read; only the benign
  `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, 13 logs + dataview.ini + landfill.ini deleted, manifest re-hashed:
  0 changed, 0 missing, 0 extra.
- The crash fix itself was proven in the dev tree (verify/crashguard/RESULTS.md): the old build crashed at game day 3073
  on Europolis 1024 at speed 4, the fixed one ran past day 3588 with the valve layer count flat at 102.

LAN: `deploy_lan_release.sh stage/release_1110b` sent 12 of 3,645 files (2.7 MB). Served label `2026-11-10b`, served
sc3resize.dll = staged. `stage/release` -> `stage/release_1110_old`, `stage/release_1110b` -> `stage/release`.

Zip: the 11-10 zip (downloaded back, SHA-256 983B2771... as recorded) with the 12 `Apps/sc3*.dll` replaced from the stage
and README.txt updated (header line now 2026-11-10b, it still said 2026-11-09; NEW IN 2026-11-10b; the four new perf.ini
lines under OPTIONS). 159 entries, 158 checked against the staged manifest, 0 mismatches (README.txt is not in it),
121 mods files = manifest. `sc3mods_2026-11-10b.zip` 51,925,923 bytes, SHA-256
79A68384F78C3BD80128BF0A741B828EE24DF58D1EBB6F0DE9EEB326AE86E8F2.

Not checked: New City / Load City from a loaded city with this build (needs a free screen, owner check), English-UK.
