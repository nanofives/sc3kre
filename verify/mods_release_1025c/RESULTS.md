# RESULTS - sc3mods release 2026-10-25c + LAN republish

Replaces `sc3mods-2026-10-25b`. Built from `main` `8587f2c`: child/verdatos (Ver datos maps drawn natively at the dialog
scale, texture sized to the on-screen diamond edge; `verify/verdatos`).

8 binaries built from `8587f2c`, staged into `Simcity_release` (3,602 files, only the 8 binaries changed). Launch check
(SC3U.exe started directly, 45 s, own PID closed): 7 mods loaded, sc3resize EARLY patch before GZGraphicD's DllMain,
avstart on, only the benign `0xC0000096 @ SC3U+0x84122`, no Defender detection in the last 2 hours. No separate package
install test (zip files byte-identical to the staged folder).

LAN: 8 of 3,602 files, 1.6 MB, verified through nginx. GitHub: `sc3mods-2026-10-25c`, target `8587f2c`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-25c, asset downloaded back, SHA-256 matches. The
2026-10-25b notes now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/version.dll | 115,200 | 56FC1ECAEA1FEEA35E78B2CCD12918AA3C9C72553964DD570A88C688E9534F1B |
| Apps/sc3resize.dll | 374,272 | 522D39C2DB06D98C25343F26F290888CC7B43AC1F0518F089AB64B82208BD5F1 |
| Apps/sc3bigcity.dll | 139,264 | 68A14DCAF3A2D05F9D326586EDFF744F1401D36C22808F76B96BA4D4A968EE91 |
| Apps/sc3overscroll.dll | 127,488 | 52544BFEDA1352173F2034C3CFEA495EE3DEB107A180C2C92F6CA6E3E9599987 |
| Apps/sc3simrun.dll | 121,856 | F29C16D758038C236DCB178FDAA536A8BD27DAE3C3783F82DB5170FF0B1D33ED |
| Apps/sc3perf.dll | 190,464 | C1D292926478F3BC4F2097B64C0FE6C5902D71949AC21B2BAABCD8A339737E36 |
| Apps/sc3netmod.dll | 390,144 | 636AF5AC18C3CAFAC8ED296DB622D417027CD33C0B263C29300A989408643A1D |
| Apps/sc3undo.dll | 147,968 | D2666AE3A1DD6D3BBCA8D5ED4DC9CC471923300BB7E0B72E3176D6281519A6B3 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| Jugar SimCity (mods).bat | 57 | 23BC06420083AF17C3B9B326C9372AE04A38B871BB3F0A5FFF7DDE9C3F2AD8C3 |
| `mods/netmod/**` | 109 files | each matches the manifest |
| `sc3mods_2026-10-25c.zip` | 42119858 | \F0ADAE6BD4E7C24E9620CC189F5CA90E34758A2EDEB67AE04AC4B63F33D7EA8 |
