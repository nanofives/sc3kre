# RESULTS - sc3mods release 2026-10-26b + LAN republish

Replaces `sc3mods-2026-10-26`. Built from `main` `f0f5b15`: nativetext (look B, RCI bars), zoomband (REPAINT8), vdscroll,
menumask, avxroad round 2 (AVXEND + 28 repainted junction art folders), slopeend (SLE + package road_slope_ends), and the
launcher change (no root SC3U.exe, no .bat; the LAN updater makes a shortcut). See each `verify/<name>/RESULTS.md`.

Road data: the avxroad art and the `road_slope_ends` package were installed into the stage source `Simcity_stock_avint`
(netpack install from `Simcity_wt_slopeend`'s example dir with its art; the avxroad tree's netmod copied over).

8 binaries built from `f0f5b15`, staged into `Simcity_release` (3,602 files: 8 binaries + 23 road-data files changed, 2
added). Launch check with Berlin loaded (SC3U.exe started directly, 75 s, own PID closed): 7 mods loaded, `sle: road slope
ends on, 4 slope piece(s)` and 1 sloped end capped on load, only the benign `0xC0000096 @ SC3U+0x84122`, no Defender
detection in the last 2 hours. No separate package install test (zip files byte-identical to the staged folder).

LAN: 33 of 3,602 files, 16.4 MB, verified through nginx. GitHub: `sc3mods-2026-10-26b`, target `f0f5b15`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-26b, asset downloaded back, SHA-256 matches. The
2026-10-26 notes now start with a "superseded" line. The zip has no `.bat` any more (README: start `Apps\SC3U.exe`).

| file | bytes | SHA-256 |
|---|---|---|
| Apps/version.dll | 115,200 | E555A051C428508BD612A76C812BBFEB98AFA43BFC4FD2F433AE985AA6FD62DF |
| Apps/sc3resize.dll | 423,424 | 74574DB5905728CA4F18793CFF5C590BB25602558E2A4155C166D5D6A29C31F6 |
| Apps/sc3bigcity.dll | 139,264 | 8C59C93EB8F42F31D0E18C121DAAB2B80113FA1041898A33B6F8ED489D7D145B |
| Apps/sc3overscroll.dll | 127,488 | AAD01BDC1EF9CB348656BA75B196B5368594197555196D4B2F3D07127F3BA36B |
| Apps/sc3simrun.dll | 121,856 | FD70B00AA6885D7C0FC4B392C2F1BCD7906736BD1A2E4B31019AD9E9A7C214D4 |
| Apps/sc3perf.dll | 190,464 | 378689BD27574C1A23F8A3921D499831819FC865039FAEF4B06A40CF72CE9AE3 |
| Apps/sc3netmod.dll | 396,288 | 973D8752FC70EF4B7D86DBB384C6027E3956926C94DEA9A2F7B816C1264BD06B |
| Apps/sc3undo.dll | 147,968 | 3F57D724C5EFB1ADC6597D5C89379EBFEC0FEB6078D223140E9C3590ACC17BDD |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| `mods/netmod/**` | 111 files | each matches the manifest |
| `sc3mods_2026-10-26b.zip` | 42582163 | \5B4ECAF15DF79CF293212DBC28F53438B22FC2031642D452B30D3A6E1A7D878 |
