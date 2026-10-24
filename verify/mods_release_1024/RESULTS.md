# RESULTS - sc3mods release 2026-10-24 + LAN republish

Replaces `sc3mods-2026-10-23`. Built from `main` `aa65ffd`: the four owner reports of 2026-10-23 (child/minimap,
child/uitoggle, child/perfscale, child/reload1024) and the refcount census (child/refaudit), see their
`verify/<name>/RESULTS.md`. Same package layout as 2026-10-23, road data included (owner call 2026-10-23).

## Build and stage

9 binaries built from `aa65ffd` with `build_mod.ps1`, staged into `Proyectos\Simcity_release` with
`stage_lan_release.py` (stage source `Simcity_stock_avint`, `perf.ini` + `menu_bg.bmp` unchanged). Manifest: 3,603 files,
only the 9 binaries changed, `Cities/Europolis 1024.sc3` still a seed.

Launch check of the staged folder (25 s, windowed, own PID closed after): 7 mods loaded, `RES_REFCOUNT` (GZResourceD,
SCENARIO, SIMSPR, SIMUI, STRTSIM occupant), `SIMGROUP_REFCOUNT`, `STRTSIM_REFCOUNT` (14 classes) all installed, LOGOBLACK on
the logo, only the benign `0xC0000096 @ SC3U+0x84122`. No separate package install test: the zip files are byte-identical
to the staged folder (manifest SHA-256, 0 mismatches).

## LAN server

`deploy_lan_release.sh`: 9 of 3,603 files sent, 1.7 MB, verified through nginx at `:8088/simcity/manifest.json`.

## GitHub release

`sc3mods-2026-10-24` on nanofives/sc3kre, target `aa65ffd`:
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-24
122 entries (`README.txt` + 121 files). Asset downloaded back: SHA-256 matches. The 2026-10-23 notes now start with a
"superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/mods_launch.exe | 147,968 | E01D44ED6B0C319B0AD83B77E5FD4D28E52839B84797E9C1679B5203B813D383 |
| Apps/version.dll | 117,248 | D4941506E9E4ABAF74F5EE69CE490E456BA3234390FC30AC2A96015F260C892C |
| Apps/sc3resize.dll | 363,008 | 739FB32688BC6C5692F9EDA93DA95452158374767D4381E38EB3D64F749487D2 |
| Apps/sc3bigcity.dll | 139,264 | 7601EA2395B9AFF49C5DC50ED12B81CA898E08C3E5C084CEEC58588D8E8540A6 |
| Apps/sc3overscroll.dll | 127,488 | D8EA8C161F99AD0B6334898082964EF4686A398AAA43738DB5EE27483B8C3C7A |
| Apps/sc3simrun.dll | 121,856 | 5B0FEC17311EB6FB6421BE7B6223D8C74375BF4B0CE32663EC225A732276D248 |
| Apps/sc3perf.dll | 190,464 | 7C03D1953BC2FF4D2D416085386677BE1269DBAEEC89A173679B3994E3D4FC35 |
| Apps/sc3netmod.dll | 380,416 | 0F20D1A9C05FAA0058C6FA9DDDBDF79F854D4548D5A99DA1A707712C1F4D7653 |
| Apps/sc3undo.dll | 147,968 | E2A485F9D2489A54F3D2C71EFECFB9D1066EA062A59F36E8B26F2CA34A0F005B |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| Jugar SimCity (mods).bat | 64 | 70F3E4370A98BB02547F7B3C54A02B940D857ACB76A5E657E6B9D7F54D714C22 |
| `mods/netmod/**` | 109 files | each matches the manifest |
| `README.txt` | 6740 | \004A8341A3A5E33DDCCEF3C391219C73BEE1DA683324132B8AD88204C7AA92B |
| `sc3mods_2026-10-24.zip` | 42191779 | \F2F90CC47F702F8F6182113AFD0A8C27721906DBD6C7FFAE45A2707D9946966 |
