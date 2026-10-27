# RESULTS - sc3mods release 2026-10-27e + LAN republish

Replaces `sc3mods-2026-10-27d`. Owner call 2026-10-27: "Publish a mods release with sc3autosave". Target `main` `6c14438`.
Only change: the new mod `sc3autosave.dll` (`verify/autosave/RESULTS.md`) and `sc3mods.dll` rebuilt with it in its load
list. The other 7 mod DLLs, `perf.ini`, `menu_bg.bmp`, `sc3mods_patch.ps1` and `mods/netmod/**` are the 10-27d files,
byte-identical (copied from the 10-27d zip, hashes below match the 10-27d table), so players download 2 new files.
`git diff f151258 main -- re/harness/src` showed no other shipped source change.

## Stage

`stage/bins_1027e` = 7 DLLs from the 10-27d zip + `sc3mods.dll` and `sc3autosave.dll` built from main with
`re/scripts/build_mod.ps1`. Staged with
`stage_lan_release.py --game stage/src --bins stage/bins_1027e --stock-modules original/modules --menu-bg <10-27d menu_bg.bmp> --perf-ini <10-27d perf.ini> --out stage/release --label 2026-10-27e`:
3,606 files (10-27d: 3,605), exe = anchor `49DD55E1...`.

## Checks

Launch check (`stage/release` patched like a player PC with `sc3mods_patch.ps1`, started directly with Frankfurt,
`SC3AUTOSAVE_SECONDS=30`, `SC3RESIZE_WINMEM=0`, `SC3MODS_MULTI=1`, own PID closed after the save):
- `sc3mods.log`: 8 mods loaded, sc3autosave last.
- `sc3autosave.log`: progress service wrapped (vtable SC3U `0x004CF59C`), `SAVE> #1 ...Frankfurt, Germany.autosave1.sc3,
  705,742 B, 187 ms`, city name kept.
- sc3resize VEH: only the benign `0xC0000096 @ SC3U+0x84122`.
- Defender 23 before, 23 after.
- Then `sc3mods_patch.ps1 -Restore` (exe back to `49DD55E1...`), run logs and the autosave file deleted, all 3,606
  manifest files re-hashed: 0 changed.

LAN: `deploy_lan_release.sh` sent 2 of 3,606 files (0.2 MB). Served manifest label `2026-10-27e`, served
`Apps/sc3autosave.dll` SHA-256 matches. GitHub: `sc3mods-2026-10-27e`, target `6c14438`,
https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-27e, asset downloaded back, SHA-256 matches. The 10-27d
notes now start with a "superseded" line.

Publish policy: before pushing main, the 4 game screenshots under `verify/autosave/owner_shots/` were untracked
(`6c14438`). `autosave2_loaded.png` had already reached the public repo with `5b97e48` (pushed by the 10-27d session).
It is still in history: removing it needs a history rewrite, owner's call.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3mods.dll | 114,176 | 1FE2B8847C7F801364064A654C0913224564E137B56598352D43CA2D4AF1CE36 |
| Apps/sc3autosave.dll | 126,976 | 3184FBE3D467663AC2497DF04094E50B91EDBD5035C0388ECDB8BA2489F28B78 |
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
| README.txt | 15,792 | 28ED4572DCD167D67FE7A454D1EF9508CA061C264EAC09395C8F0134B5414997 |
| `mods/netmod/**` | 113 files | same as 10-27d and the staged folder |
| `sc3mods_2026-10-27e.zip` | 43,219,400 | 701FBF45F9D9FF0A4C91C7D7B86D359A3FE6740B8E55DC755F3FE9DD4A1DE734 |

## Still open (owner)

From `verify/autosave/RESULTS.md`: the indicator seen over the game while it is in front, the player's own Save still
showing the game's box, an autosave with a dialog open, a never-saved city, the freeze on a 1024 city.
