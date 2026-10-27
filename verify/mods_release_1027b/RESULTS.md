# RESULTS - sc3mods release 2026-10-27b + LAN republish

Replaces `sc3mods-2026-10-27`. Built from `main` `c2149d8` (merge of `child/importldr`, see `verify/importldr/RESULTS.md`).
Only change: the mod loader. Windows Defender quarantined the 10-27 `Apps\version.dll` (SHA A5448995...) as
`Program:Win32/Contebrew.A!ml` on MARIANO-PC (game fails `0xc0000906`) and on LIVING-PC (`Simcity_release`, 2026-10-27 8:42,
signatures 1.461.224.0), hours after the 10-27 launch check passed clean. The loader is now `Apps\sc3mods.dll`, imported by
the player's own `SC3U.exe` after `sc3mods_patch.ps1` adds the import descriptor. No game exe is shipped or hosted.

8 binaries built from `c2149d8` (`sc3mods` replaces `sc3modldr`), staged into `Simcity_release` (3,605 files, 5 seed, the
stock anchor `SC3U.exe` is now a seed). Then the release folder was patched like a player PC (`sc3mods_patch.ps1 -Apps
Apps`, patched SHA `E5B6330C...27BE2`, backup `SC3U.exe.orig`). Launch check (patched `SC3U.exe` started directly, 75 s,
own PID closed, `SC3RESIZE_WINMEM=0`): `sc3mods.log` "static import, process init", 7 mods loaded, sc3resize
`EARLY: GZGraphicD mapped ... patching before its DllMain`, only the benign `0xC0000096 @ SC3U+0x84122`. Defender
detections 23 before, 23 after.

LAN: 10 of 3,605 files, 1.7 MB, verified through nginx. The server keeps the stock exe (manifest hash = anchor), the old
`version.dll` is no longer in the manifest, and `sc3_update.ps1` deletes ours from each PC and runs the patcher. A PC on the
older updater needs `update.bat` twice (the first run fetches the new updater).

GitHub: `sc3mods-2026-10-27b`, target `c2149d8`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-27b,
asset downloaded back, SHA-256 matches. The 2026-10-27 notes now start with a "superseded" line naming the quarantine.
The zip adds `sc3mods_patch.ps1` at its root and the README install step 2 (run it once). 125 files.

A clean launch does not prove the ML will not flag `sc3mods.dll` later: the 10-27 `version.dll` was also clean at launch.
What changed is the shape (no system-DLL name, no export forwarding).

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3mods.dll | 113,664 | 262AE11B19F56AE72EF4617DCC26AEAFE15865D69127A23138BA5FC0B82F4227 |
| Apps/sc3resize.dll | 429,056 | 6EE839AE60854E159ED6670136C740BCCA1681E42480F60D4E0C4C67BCCBF9E1 |
| Apps/sc3bigcity.dll | 139,264 | 1BDD644E90774F42FE78AB1FD8B48E72E499131A412086CA2B68425E8B92BE18 |
| Apps/sc3overscroll.dll | 127,488 | 89D70861927CD2769C45838EB57E45A2437D0F1842057CA17473C76BF6552624 |
| Apps/sc3simrun.dll | 121,856 | 4F72EB61C64B2612A576998EE46BE20F7E7096640B5365D5FFB5FB36F0A769BF |
| Apps/sc3perf.dll | 190,464 | 633D8B9E9551847B43B6931A42A5BE25F49F46FBA1E740E47C1EABF45FA6E2F6 |
| Apps/sc3netmod.dll | 397,824 | B52A0352B7AAC8B685319474E9CEED446860945F243809033377C7ABC220F0BD |
| Apps/sc3undo.dll | 147,968 | D206E463F5DFF7377045FE9DDD010D85702E144CD1C67201E1BC06C6B5EA15BF |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| sc3mods_patch.ps1 | 14,304 | B6553521BCB5D82EDAC5999FF5D397E62FECC521337A535824C4F871761AE8CF |
| README.txt | 13,166 | 2E197FB54C0CA744B33C8381C8DD25D7ABC530671D6B4BBE6C5A8107993E8482 |
| `mods/netmod/**` | 113 files | same as the staged folder |
| `sc3mods_2026-10-27b.zip` | 43,143,998 | 433360079244EAC9903CBF44606617375D03F635846A30F4CD3E24F66907DF27 |
