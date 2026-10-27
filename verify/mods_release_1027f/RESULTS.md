# RESULTS - sc3mods release 2026-10-27f + LAN republish

Replaces `sc3mods-2026-10-27e`. Owner call 2026-10-27: "Release it as sc3mods-2026-10-27f". Target `main` `95b033b`.
Only change: `sc3resize.dll` with VDPANELONLY (`verify/vdpanelonly/RESULTS.md`: the "Mapa de vecinos" region map was flat
grey with the interface scaled up). `git diff 9133775 main -- re/harness/src` = `sc3resize.c` only, 14 lines. The other 8
DLLs and every other file are the 10-27e files (`verify/mods_release_1027e/RESULTS.md`), byte-identical.

## Stage and checks

`stage/bins_1027f` = `stage/bins_1027e` with `sc3resize.dll` rebuilt from main. Staged like 10-27e with
`--label 2026-10-27f`: 3,606 files, exe = anchor.

Launch check (`stage/release` patched, Craterville, `SC3AUTOSAVE_SECONDS=30`): the first start ran stock ("SC3U.exe is
not patched ... no mods loaded", every mod inert) although the patch had printed its backup line; the exe was patched
when checked right after (`E5B6330C...`). The second start: 8 mods loaded, `SAVE> #1 ...Craterville.autosave1.sc3, 554,430 B,
203 ms`, city name kept, only the benign `0xC0000096 @ SC3U+0x84122`. Defender 23 before and after. Then `-Restore` (anchor
`49DD55E1...`), logs and the autosave deleted, 3,606 manifest files re-hashed: 0 changed.
[UNCERTAIN] why the first start used the unpatched exe: the game was started right after the patch script returned;
not reproduced. The fix itself was checked in the dev tree at 2560x1351 (`verify/vdpanelonly`); this launch was at the
default size, where VERDATOS does not run.

LAN: 1 of 3,606 files (0.4 MB), served label `2026-10-27f`, served `Apps/sc3resize.dll` SHA-256 matches. GitHub:
`sc3mods-2026-10-27f`, target `95b033b`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-27f, asset
downloaded back, SHA-256 matches. The 10-27e notes now start with a "superseded" line.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 429,056 | AC4EA4DAB24C22B2EB49BE31CAB9B7BE51992B6FB4368527C1449D076B43D704 |
| README.txt | 16,259 | B1302F20047DF1B00E06D468F944E0588FBF90E33EEB7311DFF56F0DD6B241A3 |
| every other file | | as `verify/mods_release_1027e/RESULTS.md` |
| `sc3mods_2026-10-27f.zip` | 43,219,650 | 8D890DE8F9B922183DEEBD31482A12480D82D4916640FDD31AF15EF8C25FD0B4 |
