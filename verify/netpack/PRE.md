# netpack: pre-registration (2026-10-13, before any game run)

Task: a generic package format for network mods (variants, reskins, rule edits, ini additions), a `netpack` CLI
(new / validate / build / install / uninstall / list with a ledger), `sc3netmod.dll` reading every installed pack,
two example packs, and a round-trip test. Owner intent: the FRAMEWORK, not content; blue road 20029 is a fixture.

Tree: `C:\Users\maria\Desktop\Proyectos\Simcity_stock_netpack` (hard links of `Simcity_stock`, `link_tree.py`, stock
DLLs, Spanish). Instance: `Simcity_stock_netpack\re\harness\inst_netpack\` (mods_launch -multi, sc3resize.dll for the
in-process DUMP, sc3netmod.dll from child/netpack). Own PID only.

## Delivery decision to settle by evidence: overlay vs direct

- **Overlay**: `install` writes nothing under `Apps\`. Built files go to `<root>\mods\netmod\overlay\<path relative to
  root>`; `sc3netmod.dll` IAT-hooks `CreateFileA`, `GetFileAttributesA`, `FindFirstFileA`, `FindNextFileA`, `FindClose`
  in every loaded module (re-armed after every `LoadLibraryA/ExA`) and serves a read-only open of `<root>\Apps\Res\X`
  from the overlay when `overlay\Apps\Res\X` exists; directory listings are merged.
  Static basis: every game module imports those five as ANSI kernel32 functions, `fopen`/`_sopen` go through the
  shipped `MSVCRT.DLL`, which imports `CreateFileA` itself (import tables read with pefile 2026-10-13). No module
  imports a W file API.
- **Direct**: `install --mode direct` writes the same files into `Apps\Res` (new files, plus copies of the edited
  stock files; originals backed up under `mods\netmod\backup\` with hashes in the ledger).

### Arm F (file log), overlay only, the newpiece blue-road files placed ONLY in the overlay
Run with `SC3NETMOD_FILELOG=1`, load a 256 city copy, open the road tool, stop.
Predictions (each one a pass/fail line):
- F1 `TilingRules\ROAD_GRND_Set.txt` and `ROAD_GRND_SimpleRules.txt` are opened through a hooked `CreateFileA` and the
  log says "redirected".
- F2 `Res\Occupant\OccupantAttribs_Korea.IXF` and `Res\Sprites\CSAttrib_Korea.IXF` are opened (existence check
  and/or open) through a hooked function and redirected.
- F3 `Res\Sprites` is listed with `FindFirstFileA`; the merged listing returns the overlay's new `*.DAT`, and that
  DAT is then opened through `CreateFileA` and redirected.
- F4 `SSimData\<lang>\TrBlkAtt.IXF` is opened through a hooked function and redirected.
If any of F1..F4 fails, overlay cannot deliver that file class: `direct` becomes the default for it and the reason
goes in `re/analysis/NETPACK.md`.

### Arm O (overlay render), both example packs installed with `--mode overlay`
City: copy of newpiece's `TM_after.sc3` (Berlin, 7,419 raw 20029 straights, highways present). Frame dumps
(`np_drive.py shot`) at 2 zooms; Frida cell read on 3 straights and 3 highway cells.
- O1 road straights read piece 20029 live and draw blue (example_blue_road).
- O2 highway piece 73 cells draw with the example_reskin recolour; stock highway pieces other than 73 unchanged.
- O3 `sc3netmod.log` lists the variant 20029 -> 29 from the pack table under `mods\netmod\`, not from
  `Apps\Res\netmod_variants.txt` (absent in this tree).
### Arm C (control), same tree, same city, launched WITHOUT sc3netmod.dll
- C1 highway 73 draws stock grey (the overlay is not read without the DLL).
- C2 the stock install files are untouched by the run (hash compare of every file the packs would touch).

### Arm U (round trip, offline, both modes)
- U1 `hash(tree)` before install == after `install A; install B; uninstall B; uninstall A`, for every file under the
  tree except `re\` (instance logs/saves), for `--mode overlay` and for `--mode direct`. `mods\netmod\` is removed when
  the last pack goes.
- U2 `Simcity_stock` (the hard-link source) hashes unchanged after both modes.
- U3 install order A,B and B,A build byte-identical merged containers (deterministic merge).
- U4 a third pack declaring an id already used by an installed pack is refused by `install`, tree unchanged.
- U5 `validate` refuses: a PNG whose size differs from the base frame, a base on another network, a variant id with a
  stock exemplar, a rule edit whose match count differs from `expect`.

Not tested here (out of scope, listed so they are not claimed): Occupant.ini / SYS.PAK edits in game; packs on a
1024 city; the owner's dev install (MAIN\Apps); highway/rail/power variants with crossings.
