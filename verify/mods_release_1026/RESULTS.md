# RESULTS - sc3mods release 2026-10-26 + LAN republish

Replaces `sc3mods-2026-10-25d`. Built from `main` `c2276dd`: child/winprimary (WINPRIMARY: a saved window off the primary
monitor is moved onto it), child/newcitydlg (DLGCLASS, DLGOCC; `verify/newcitydlg`), child/avxroad (AVXDROP;
`verify/avxroad`).

8 binaries built from `c2276dd`, staged into `Simcity_release` (3,602 files, only the 8 binaries changed). Launch check
(SC3U.exe started directly, 45 s, own PID closed): 7 mods loaded, only the benign `0xC0000096 @ SC3U+0x84122`, no Defender
detection in the last 2 hours. No separate package install test (zip files byte-identical to the staged folder).

LAN: 8 of 3,602 files, 1.6 MB, verified through nginx. GitHub: `sc3mods-2026-10-26`, target `c2276dd`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-26, asset downloaded back, SHA-256 matches. The
2026-10-25d notes now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/version.dll | 115,200 | 202C6C98F2AE5F9D6CC006E3561252DFF243B0232D41DDED9CC387790C288BC7 |
| Apps/sc3resize.dll | 379,392 | 62648F0256678722C80036360E345D84D92801D6C3DF67BE760AC8252F1A4575 |
| Apps/sc3bigcity.dll | 139,264 | FB686FA593C5FEE05C664A29F431F79E6377EC9C4C651AEA5027E962EF97835C |
| Apps/sc3overscroll.dll | 127,488 | 941DF8561E546772F85DFA82AB1AAE1365E6280A8A0DD698D2F443A0D7F0A0E5 |
| Apps/sc3simrun.dll | 121,856 | D4C8FF3FFCAC880C5F4B6350788BBF05F9B7C170ADDE6B49D60A23E0F92AF9C2 |
| Apps/sc3perf.dll | 190,464 | 329A69F9185419CAD33D23CA8EDF65C9B9638894690F18A31518F32A6F42434D |
| Apps/sc3netmod.dll | 391,680 | FC3409C128A5E72A25E6773533878F36096595F5F4A4EA70F52F5F976F903F80 |
| Apps/sc3undo.dll | 147,968 | 6F4C2C3643FBD00D8F318293132941E2D22C8DD0EB36CE53DD5BB5AB39986AA8 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| Jugar SimCity (mods).bat | 57 | 23BC06420083AF17C3B9B326C9372AE04A38B871BB3F0A5FFF7DDE9C3F2AD8C3 |
| `mods/netmod/**` | 109 files | each matches the manifest |
| `sc3mods_2026-10-26.zip` | 42123971 | \D1C39C7CA7D7A7944CFB47C77F47E061926C711F89E582AA615E81F0CC06C1D |
