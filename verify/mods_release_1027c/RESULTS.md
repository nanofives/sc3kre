# RESULTS - sc3mods release 2026-10-27c + LAN republish

Replaces `sc3mods-2026-10-27b`. Built from `main` `f9bfc29` (merge of `child/lateguard`, see `verify/lateguard/RESULTS.md`).
Only change: every mod (and sc3mods.dll on a late load) is inert unless sc3mods.dll loads it. With 10-27b an unpatched
SC3U.exe closed before any window (owner, MARIANO-PC, after one `update.bat` run on the old updater): the game's component
scan [CONFIRMED @ 0x0040b00f, 0x0048a575] LoadLibrary's every `*.dll` in Apps after GZGraphicD, so the mods initialised late
and crashed it (c0000005 @ SC3U+0x143a, reproduced in `Simcity_release` 10:05 and 10:06).

8 binaries built from `f9bfc29`, staged into `Simcity_release` (3,605 files), then patched like a player PC. Launch check
(patched exe started directly, 60 s, own PID closed, `SC3RESIZE_WINMEM=0`): 7 mods loaded during process init, sc3resize
`EARLY: GZGraphicD mapped ... patching before its DllMain`, only the benign `0xC0000096 @ SC3U+0x84122`, Defender 23 before,
23 after. The unpatched-exe stock start was proven by the child (main menu drawn, alive 60 s, one inert line per mod, control
with the 7c0dfcd DLLs dead in 0.7 s). Not re-run here because the stock exe opens fullscreen.

LAN: 8 of 3,605 files, 1.7 MB, verified through nginx. GitHub: `sc3mods-2026-10-27c`, target `f9bfc29`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-27c, asset downloaded back, SHA-256 matches. The 10-27b notes
now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3mods.dll | 114,176 | A9A8EDF7EF71F44CC00CEAB6CD2665DC102FACAF0B93F9D43F277631F3CC27B4 |
| Apps/sc3resize.dll | 429,056 | A456628DE643642A1CDFB3D313734AAF2F04FC12147ED462E04E0B83271255A6 |
| Apps/sc3bigcity.dll | 140,288 | 7B4E8E818B19B71D99B43654678DA010AA2BAFC521E9FC8A5BC53AE968904BD4 |
| Apps/sc3overscroll.dll | 128,000 | 936C4BBBC6FAF7F2CD98A48A165610318AA99FEDC8248B051BE8BF538ACA8FB8 |
| Apps/sc3simrun.dll | 121,856 | C292578941F6FC8A5CBED22011869F623A721FBBAE728635C87999CB68E75987 |
| Apps/sc3perf.dll | 190,464 | 77454BA9802CE0CD1FAAFA3572FF3B2303D6629A32D9D27276967B5CE182BBA5 |
| Apps/sc3netmod.dll | 398,848 | EDC2D4D4B851EE4B7B7D3C1EEF5EF64031C4B44E161FB1CABFFAE7704AD04EEE |
| Apps/sc3undo.dll | 148,480 | 1F0F5FAD38CA5AA695135B6203C58F725825238D787215C99765CABDD8FB7011 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| sc3mods_patch.ps1 | 14,304 | B6553521BCB5D82EDAC5999FF5D397E62FECC521337A535824C4F871761AE8CF |
| README.txt | 13,601 | 186D6A569644B9116D5DB46284EFDC1ED9C8AC291A11B3FFFC07DC768A39ADAF |
| `mods/netmod/**` | 113 files | same as the staged folder |
| `sc3mods_2026-10-27c.zip` | 43,146,869 | C8467CEA3FE49EE9589C37DA4D7E5261A384778E17AAA5B8381425A83A5F2078 |
