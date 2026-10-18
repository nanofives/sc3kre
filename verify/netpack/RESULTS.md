# netpack: RESULTS (2026-10-13)

**Verdict: the package system works end to end on stock DLLs.** Packages installed by `netpack.py` into
`mods\netmod\overlay` are read by the game through `sc3netmod.dll` with nothing under `Apps\` written; the variant
road, the reskinned highway and the variant's name all appear in game; uninstalling returns the tree to the stock
bytes. Overlay is the default delivery (decided by arm F), direct mode is kept for runs without the DLL.

Pre-registration: `PRE.md`, committed `8b381a8` before the first run. Tree: `Simcity_stock_netpack` (hard links of
`Simcity_stock`, stock DLLs, Spanish). Instances `re\harness\inst_netpack` (sc3netmod.dll + sc3resize.dll from
child/netpack, mods_launch -multi) and `inst_netpack_ctl` (sc3resize.dll only). City: copy of newpiece's
`TM_after.sc3` (Berlin, 7,419 straights stored as raw 20029, 194 highway 73 tiles). Every run in my own pid, all
stopped. Frames are desktop grabs (`np_drive.py grab`) or sc3resize's in-process dump; they stay in the instance
folders (game art, not committed).

## Arms

| arm | setup | result | prediction |
|---|---|---|---|
| F (pid 21572) | newpiece.py's 20029 files copied ONLY into `mods\netmod\overlay`, `SC3NETMOD_FILELOG=1` | F1 both TilingRules files: SIMNTWRK `GetFileAttributesA` + `CreateFileA`, redirected. F2 both Korea IXFs: GZResourceD `CreateFileA`, redirected. F3 SC3U and SIMSPR list `Res\Sprites\*.DAT` with `FindFirstFileA`, merged listing 31 entries incl. 1 from the overlay; SIMSPR then opens `4E3D0001_NewPiece20029.DAT`, redirected. F4 `SSimData\English\TrBlkAtt.IXF`: GZResourceD, redirected. Blue straights drawn (frame dump). `link_tree --verify`: 3,488 linked, 0 de-linked | F1-F4 met; overlay is the default |
| O (pid 34364) | both example packages installed with `netpack.py install` (overlay, 20 files) | O1 road cells read piece 20029 (Frida, e.g. (75,15) class `SIMNTWRK+0x2B5DC`, attrib `0x4e3d`) and draw blue. O2 the highway 73 cells ((73..74, 14..17), Frida) draw red; curves, ramps and 11258 stay grey. O3 `sc3netmod.log`: `table: ...\mods\netmod\tables\example_blue_road.txt: variant 20029 -> base 29`, `READY ... variants=1, cross=1 (16 site(s)), savebase=1, load=patched`. Overlay CSATTRIB.IXF and `4E3D0001_netpack.DAT` redirected | met |
| O (names) | same | `Text\English\SC3StringsNetpack.IXF` never opened: GZResourceD opens the Text containers by the names in `Default.ini [DBSegments]`, not by listing the folder | not pre-registered; led to arm N |
| N (pid 460) | names fix: the merge adds `0xa1096a4f=0x80c381d7;Res\Text\%Language%\SC3StringsNetpack.IXF` to `Default.ini [DBSegments]` in an overlay SYS.PAK (+67 bytes, only Default.ini changed) | SYS.PAK redirected for SC3U, simvariables and SIMINIT; the game boots; GZResourceD opens `SC3StringsNetpack.IXF` (redirected); the ? tool on a blue road shows **"Carretera azul"** (the ENGLISH folder holds the Spanish text in this install) | exploratory; first game load of a length-changing SYS.PAK |
| C (pid 38480) | same tree and packages, launched WITHOUT sc3netmod.dll | C1 highway 73 grey at the same view (minimap click centred tile (101,17), as in O); the 20029 cells hold no occupant (dropped, as newpiece arm R). C2 nothing under `Apps\` changed (overlay never written there; verified by the hash compare in U) | met |
| U (game tree) | after the runs: `uninstall example_reskin`, `uninstall example_blue_road` | `mods\netmod` deleted; the 3,488 stock files of the tree are byte-identical to `Simcity_stock` (sha256 each), 0 missing. The only extra files were sc3resize's frame dumps from my own shots (moved out) | met |

## Offline: `netpack.py selftest` (temporary hard-linked trees)

```
ok   U3 merge A+B == B+A, 21 files
ok   example_blue_road rules == newpiece.py rules_retarget (the game-proven 20029 edit)
ok   U5 refuses an id with a stock exemplar / a base on another network / an edit whose expect differs from the
     stock rule / two edits of one stock rule / a rule index past the file / a PNG whose size differs (7x5 vs 8x5)
ok   U6 export-art -> png_dir re-import: 20 frames, decoded pixels identical to the stock frames
ok   U1 overlay: nothing under Apps changed after installing both
ok   U4 overlay: id clash refused, tree unchanged
ok   U1 overlay: tree byte-identical after install A, B, uninstall B, A (3488 files); mods\ removed
ok   direct: 21 file(s) under Apps written
ok   U4 direct: id clash refused, tree unchanged
ok   U1 direct: tree byte-identical after install A, B, uninstall B, A (3488 files); mods\ removed
ok   U2 the 11 stock files the packages replace are unchanged in the hard-link source
```
(Output of the final run, after the rule edits moved to the format agreed with netrules: `rule_edits`, stock indexes,
`expect` guards. The example's rule file bytes are unchanged by that switch, so the game arms stand.) `build` twice on the same package: identical
outputs (sha256 of every file). Every live TilingRules file round-trips byte-identical through `netpack_rules`.

## Not covered

Direct mode in game (offline round trip only); `ini` edits other than the `[DBSegments]` line; packages on a 1024
city; the owner's dev install and the release layout (DLL in Apps); variants of rail, power, highway, pipe, subway;
PNG-authored art in game (the import path is checked offline: U5, U6).
