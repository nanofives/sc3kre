# RESULTS - sc3mods release 2026-10-25d + LAN republish

Replaces `sc3mods-2026-10-25c`. Built from `main` `9825dc4`: child/spr47b70 (sc3resize SHAREREAD: read-only resource
opens share reads, a failed right-drag marker load retries then is skipped, fixing the stock SIMSPR+0x47B70 null read;
sc3netmod OVPIN; `verify/spr47b70`).

8 binaries built from `9825dc4`, staged into `Simcity_release` (3,602 files, only the 8 binaries changed). Launch check
(SC3U.exe started directly, 45 s, own PID closed): 7 mods loaded, `SHAREREAD: on`, only the benign
`0xC0000096 @ SC3U+0x84122`, no Defender detection in the last 2 hours. No separate package install test (zip files
byte-identical to the staged folder).

LAN: 8 of 3,602 files, 1.6 MB, verified through nginx. GitHub: `sc3mods-2026-10-25d`, target `9825dc4`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-25d, asset downloaded back, SHA-256 matches. The
2026-10-25c notes now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/version.dll | 115,200 | 0D7D994BD59EE916F5A749FE6AA2087A4C7B5441DD041EF3A60451D2E7381232 |
| Apps/sc3resize.dll | 376,320 | 9BD2E25D37F45059F56D18266653D7793BF4F71F0153F05F2E8B5BA923BA5D3E |
| Apps/sc3bigcity.dll | 139,264 | A63CEE1AF6C471CAC113C0D9215EA6385B6FA38F7F314B77A6FDC5A9CA973FC3 |
| Apps/sc3overscroll.dll | 127,488 | 68650F1CD72B44B8A9BE66C27D5E810425E97E9911D33B9A76B21AD2C16D15D5 |
| Apps/sc3simrun.dll | 121,856 | 0C53E1974E80CBB7D8FD66B4DFA5BA62A76C89A760D72AC132E738D1B4160DBE |
| Apps/sc3perf.dll | 190,464 | A0F9BD015B560A583F9297D884122D3B718F734352A19C46C360C72E6378E222 |
| Apps/sc3netmod.dll | 390,656 | 6DBB368114AB54AF25FD1C9BB0F165056E180F91B8916957454C401D21DE85BA |
| Apps/sc3undo.dll | 147,968 | 6E4B65B577F1EEBA50A8EA97FEC891AE7DEA6C3914E9787C21F6BB9CA4132435 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| Jugar SimCity (mods).bat | 57 | 23BC06420083AF17C3B9B326C9372AE04A38B871BB3F0A5FFF7DDE9C3F2AD8C3 |
| `mods/netmod/**` | 109 files | each matches the manifest |
| `sc3mods_2026-10-25d.zip` | 42121193 | \ED2CDA0792A421657C06D6759DC921E3575E67EF86C9703537A76869BA3C7E8 |
