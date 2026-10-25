# RESULTS - sc3mods release 2026-10-25 + LAN republish

Replaces `sc3mods-2026-10-24`, whose `version.dll` Windows Defender flags as `Program:Win32/Contebrew.A!ml` (real-time
protection, detected on LIVING-PC 2026-10-25 02:15, signatures 1.461.192.0). Built from `main` `4a291be`: child/loader2
(version.dll loads a built-in mod list from DllMain on a normal SC3U.exe start, no entry-point patch, no RWX on the exe,
`mods_launch.exe` dropped), sc3netmod AVFIRST + AVDEPOSIT (child/avflow) and AVSTART default on (child/bventry, owner call),
BVCOST / AVCOST / BVFIRST present but off. See `verify/loader2`, `verify/avflow`, `verify/bventry`.

## Build and stage

8 binaries (7 mods + version.dll) built from `4a291be` with `build_mod.ps1`, staged into `Proyectos\Simcity_release`
(old `mods_launch.exe` and the flagged `version.dll` deleted first). Manifest: 3,602 files, 8 binaries and the `.bat`
changed, `Apps/mods_launch.exe` removed. The `.bat` now starts `Apps\SC3U.exe`.

Launch check of the staged folder (SC3U.exe started directly, no env vars, windowed, 45 s, own PID closed after):
`sc3modldr` "7 mod(s) loaded (no exe patch, no VirtualProtect on .text)", sc3resize `EARLY: GZGraphicD ... patching before
its DllMain`, `avflow: avstart on`, 7 refcount blocks installed in sc3perf, LOGOBLACK on the logo, only the benign
`0xC0000096 @ SC3U+0x84122`. `Get-MpThreatDetection` for the last hour: none.

## LAN server

`deploy_lan_release.sh`: 9 of 3,602 files sent, 1.6 MB, verified through nginx. The updater does not delete files under
`Apps`, so PCs keep an old `mods_launch.exe` until removed by hand. It is not used.

## GitHub release

`sc3mods-2026-10-25` on nanofives/sc3kre, target `4a291be`:
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-25
121 entries (`README.txt` + 120 files, each matching the manifest). Asset downloaded back: SHA-256 matches. The
2026-10-24 notes now start with a "superseded, version.dll flagged" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/version.dll | 115,200 | ECCA9515EB1162483A3D8F65D1D96222E52B43F01FEEBA606D0341EC9B21C7C1 |
| Apps/sc3resize.dll | 363,008 | 9790DF7693E6F4357B72303BA5C7818CF320298D9C7C525ECC118F5745B62659 |
| Apps/sc3bigcity.dll | 139,264 | A020789B7717FB9AFEA2EF2ADE3ADD0E50C84835F7D97CF467E404DB7A60BC97 |
| Apps/sc3overscroll.dll | 127,488 | 8463FBA0D71B3D805F7D07F21631EB73F2EA6D45D818B3A0BCC87FF5BB459F22 |
| Apps/sc3simrun.dll | 121,856 | 2A7B9D1386F311771479FB611FE3D71897C1989C51BCAE0A751C49E61B1288C7 |
| Apps/sc3perf.dll | 190,464 | 1AF9C29D139B7C9F79313B30DD7A98B7849D51784AA1F15613B29FAF75B624EC |
| Apps/sc3netmod.dll | 390,144 | 0AD1D86C1FDDF4692F241BDF7A588E2AD6B4A871BDF068E2FCA0B790C226419D |
| Apps/sc3undo.dll | 147,968 | D7F882449E3C9ACCB88F2FB36C82FA26E3814F330BDC5BE48630F61897CEED42 |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| Jugar SimCity (mods).bat | 57 | 23BC06420083AF17C3B9B326C9372AE04A38B871BB3F0A5FFF7DDE9C3F2AD8C3 |
| `mods/netmod/**` | 109 files | each matches the manifest |
| `README.txt` | 7543 | \A89F8A9153F8ACBF0B55BEB65D3F16E09C97412FE1818DA15D7877B7DF2D3F3 |
| `sc3mods_2026-10-25.zip` | 42113606 | \A49AB272B9C212216CA02CCE855E1FA055DE0F623E3CF83C50F52266643CCDC |
