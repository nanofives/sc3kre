# RESULTS - sc3mods release 2026-10-27d + LAN republish

Replaces `sc3mods-2026-10-27c`. Built from `child/audiodiv` `f151258` (= 10-27c `413a64f` + the AUDIODIV fix, see
`verify/audiodiv/RESULTS.md`), not from `main`, so the unreleased `sc3autosave` (main 9c29c95) is not in it. Merged into
`main` as `ab3b0d9` after publishing. Only change: sc3overscroll guards the stock `AUDIO.DLL` divide by an empty cell box
(`FUN_1000ae7a` / `FUN_1000ae06`, idiv at +0xaee8 / +0xae74). Owner crash MARIANO-PC 12:43: `C0000094` at `AUDIO.DLL+0xAEE8`,
camera past the edge at cityzoom x2/x3 with the pipes view open.

## Stage source rebuilt from the LAN server

The stage source `Proyectos\Simcity_stock_avint` was deleted by the folder consolidation (2026-10-27), and the first stage
attempt then emptied `Proyectos\Simcity_release` (`stage_lan_release.py` removes `--out` before it copies). Recovery: the
10-27c release was downloaded from the LAN server with `sc3_update.ps1 -InstallRoot Simcity\stage\src` (3,604 files, 0
failed), its exe restored to the anchor (`sc3mods_patch.ps1 -Restore`, SHA `49DD55E1...`), and the release staged from it
into the new location `Simcity\stage\release`. Check: the staged manifest against the server's showed 3,605 vs 3,605 files,
exactly the 8 rebuilt binaries changed, nothing missing. The netpack ledger that lived in `Simcity_stock_avint` is gone: a
future road-package change needs a new stage source with a ledger (`stage\src` only has the installed overlay and tables).

## Checks

Launch check (`stage\release` patched like a player PC, started directly, 60 s, own PID closed, `SC3RESIZE_WINMEM=0`):
7 mods loaded, `AUDIODIV: AUDIO.DLL at 0x00D00000, FUN_1000ae06 / FUN_1000ae7a return 0 on an empty cell box`, sc3resize
`EARLY` before GZGraphicD, only the benign `0xC0000096 @ SC3U+0x84122`, Defender 23 before, 23 after. The crash repro and the
fixed runs are the child's (2 of 2 crashes without the guard, 3 of 3 survived with it, 256 and 1024 cities).

LAN: 8 of 3,605 files, 1.7 MB, verified through nginx. GitHub: `sc3mods-2026-10-27d`, target `f151258`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-27d, asset downloaded back, SHA-256 matches. The 10-27c notes
now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3mods.dll | 114,176 | B48E327EB27136DC1E62C76698911B383FCDD03BF4811F064713EED8CC93EDE1 |
| Apps/sc3resize.dll | 429,056 | 929092A8AD577E7A69765E74D171024591DE4F912ED784439DAD149C8512739D |
| Apps/sc3bigcity.dll | 140,288 | 8B1337DE1A24975985FA83EBEE794921BAA7B034A8DEB7E92A5628868200CCA2 |
| Apps/sc3overscroll.dll | 129,536 | 437380E3ADD0EE29427E676DB12F9DA630E0494E51D912AF3BFAE0F5C0F2A296 |
| Apps/sc3simrun.dll | 121,856 | 353DFB6696E552B9169D74E2163DD90A936C0572080A9D5A5DC1A2CBA4CB46CD |
| Apps/sc3perf.dll | 190,464 | 861CF44B495D016DC6082CF52A6089B8EBF71C7D3FADCC7E2A46B618DC1CBD2D |
| Apps/sc3netmod.dll | 398,848 | 4F6EDDACEBBD2A91B8B02B55C5F48928DFE7E2D83212B4AB40F7DFF73EDD5FC2 |
| Apps/sc3undo.dll | 148,480 | 831EC658AAAC9A39E9AF43EC745AFD636915D0FBD5B6032AA2AA919DD0471C7A |
| Apps/perf.ini | 2,103 | A4C2D0A33FFDB98605ABAF75E4BB8EA9D5A9444F0C8FDAF93AF7707443B7BC04 |
| Apps/menu_bg.bmp | 4,717,638 | 10792812B2BAED12A62D9207FE47FB0E3FD827E3B5B642F3C2C8A253856945AE |
| sc3mods_patch.ps1 | 14,304 | B6553521BCB5D82EDAC5999FF5D397E62FECC521337A535824C4F871761AE8CF |
| README.txt | 13,977 | 066039768C80D8485F55DD9D71C7268864E997FCD2B154F7E0853E6A0A6C00A9 |
| `mods/netmod/**` | 113 files | same as the staged folder |
| `sc3mods_2026-10-27d.zip` | 43,147,738 | 1825C9FD298B21A6549B8B7EF79FEDA525788D54F4ABFE5F97F97A60C5CF1156 |
