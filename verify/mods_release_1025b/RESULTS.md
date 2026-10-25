# RESULTS - sc3mods release 2026-10-25b + LAN republish

Replaces `sc3mods-2026-10-25`. Built from `main` `def734b`: child/zoomcrash (ret 4 in the CITYZOOM skip paths: zooming in
with the minimap buttons on a window that allows x2 killed the process silently; hook_audit.py found no other ret-size
mismatch) and child/uiaudit (TIPDLG, MINIVIS, DLGONLY, MSOPEN). See `verify/zoomcrash`, `verify/uiaudit`.

8 binaries built from `def734b`, staged into `Simcity_release` (3,602 files, only the 8 binaries changed). Launch check
(SC3U.exe started directly, 45 s, own PID closed): 7 mods loaded, sc3resize EARLY patch before GZGraphicD's DllMain,
avstart on, only the benign `0xC0000096 @ SC3U+0x84122`, no Defender detection in the last 2 hours. No separate package
install test (zip files byte-identical to the staged folder).

LAN: `deploy_lan_release.sh`, verified through nginx. GitHub: `sc3mods-2026-10-25b`, target `def734b`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-25b, asset downloaded back, SHA-256 matches. The
2026-10-25 notes now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/version.dll | 115,200 | 53DC9CF3BC9FF45213352FB0086124C65B06D07AC65D571B13385BE34D14F85F |
| Apps/sc3resize.dll | 366,592 | 1232C2286CF1BD4B6081919BFDD7142B62F870C40A262AFA39992FF8078F0C8C |
| Apps/sc3bigcity.dll | 139,264 | 47ED320DB47E19BB1FD393ABA3927B7D346BFCC14AE93014D700571A822F7A45 |
| Apps/sc3overscroll.dll | 127,488 | B920066506313E22EAE469F472E1FA08B513048012AF8D8BE479D85EF54B203F |
| Apps/sc3simrun.dll | 121,856 | 1F3A58B6F1A5D30146C5EFDD76A7ED33958F436316201A08001E78662B748284 |
| Apps/sc3perf.dll | 190,464 | B66073B323C013EAE0D4EB466000E24B44002371E713433C2597E20A84ACDE9C |
| Apps/sc3netmod.dll | 390,144 | 711054C91DF99CC9F45CB183240104A0CBF2A5A69F156D5768A9DD6799165529 |
| Apps/sc3undo.dll | 147,968 | 269B5CB3643914122B9C6E2EAE6339A457AEBFAA526B88990137D459D739DB80 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| Jugar SimCity (mods).bat | 57 | 23BC06420083AF17C3B9B326C9372AE04A38B871BB3F0A5FFF7DDE9C3F2AD8C3 |
| `mods/netmod/**` | 109 files | each matches the manifest |
| `sc3mods_2026-10-25b.zip` | 42115776 | \3687C7627030DA4A88EA101DA0CBD7EA092AE2CF6811B7F0F664E60563EFCE0 |
