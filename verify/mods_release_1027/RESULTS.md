# RESULTS - sc3mods release 2026-10-27 + LAN republish

Replaces `sc3mods-2026-10-26b`. Built from `main` `fe40300`: nativetext round 3 (no letter flicker) and avslope (avenue
slope art for 21718..21725, BVS + package boulevard_slopes 27100..27111). See `verify/nativetext`, `verify/avslope`.

Road data: in the stage source `Simcity_stock_avint`, `avenue_lanes` was uninstalled and reinstalled at 0.2.0 from
`Simcity_wt_avslope`'s example dir (the full art incl. the 8 slope pieces), and `boulevard_slopes` 1.0.0 was installed from
the same worktree. 18 packages, 96 overlay files.

8 binaries built from `fe40300`, staged into `Simcity_release` (3,604 files: 8 binaries + 56 road-data files changed, 2
added). Launch check with Frankfurt loaded (SC3U.exe started directly, 75 s, own PID closed): 7 mods loaded, `bvs:` tables
loaded, only the benign `0xC0000096 @ SC3U+0x84122`, no Defender detection in the last 2 hours. No separate package install
test (zip files byte-identical to the staged folder).

LAN: 66 of 3,604 files, 52.4 MB, verified through nginx. GitHub: `sc3mods-2026-10-27`, target `fe40300`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-27, asset downloaded back, SHA-256 matches. The 2026-10-26b
notes now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/version.dll | 115,200 | A544899522AD6DCCB3BC7070F3ED241295163954022EC607CFA7B4DF23D63C81 |
| Apps/sc3resize.dll | 429,056 | 9599C707488E20141C940A0D9436A8BAAF073659735252B0873BDBED22202350 |
| Apps/sc3bigcity.dll | 139,264 | AE402309B2ED5220DD2BCFF20FB6CC8159F47A68F8E12C77A99E1321268153FF |
| Apps/sc3overscroll.dll | 127,488 | 32FB032ABCDA8D171B81B8078F563EB06D7B0B2848F273EBFC1A843201B5EFA7 |
| Apps/sc3simrun.dll | 121,856 | 85BA3D6ACF87F62E96BA090DB2574D3DD24914ED14E7F90C37557984F5DBB099 |
| Apps/sc3perf.dll | 190,464 | 577DBFF8045C2A4FE38D233B7BF82463AD9C1E0AE02179C12AF991C13DEF64AC |
| Apps/sc3netmod.dll | 397,824 | 3145FA12B7FDC0B3DC1499D4C68C418BFF84F36A44303F5F9DE7B766DB678DF7 |
| Apps/sc3undo.dll | 147,968 | 9EB594E0299B4F14F0481C963EF51D7E6A631DEC927EB0E36D3445776F8E75B2 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| `mods/netmod/**` | 113 files | each matches the manifest |
| `sc3mods_2026-10-27.zip` | 43139349 | \4506D348CB1279F2F427C97FE95C46102F2F369BF373A43BB46E795DB91BA5F |
