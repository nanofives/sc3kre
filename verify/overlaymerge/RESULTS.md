# overlaymerge: other mods' edits of files the netmod overlay shadows (2026-11-21)

Round 2026-11-21 (Simtropolis feedback), stream 2. Player: "I tried to install this agricultural mod ... it doesn't
appear in-game ... doesn't throw any errors when it installs" (mod not named yet).

## Verdict

Cause: our own code. sc3netmod's OVERLAY block (`ov_map`, sc3netmod.c) answers every read-only open of `<root>\X` with
`mods\netmod\overlay\X` when the overlay holds X, whatever `<root>\X` holds now. A mod that edits the stock Apps copy of
such a file after our install is written to disk and never read. Reproduced in the dev tree (run C below): with a
hand-made farm mod in `Apps\Res\BUILDFAM.IXF` and `Apps\Sys\SYS.PAK`, the game opened both files from the overlay, and
the segment the mod's new `[DBSegments]` row names was never opened.

Fix: OVMERGE (new `re/harness/src/sc3netmod_ovmerge.c`, included by sc3netmod.c). At start-up (DllMain, before the
hooks) sc3netmod hashes the Apps copy of every shadowed file against the stock SHA-256 in
`mods\netmod\overlay_base.txt`. Stock: nothing changes. Changed: a three-way merge (base = stock hashes, ours = the
overlay file as it is now, theirs = the player's file) into `%TEMP%\sc3netmod_merge_<pid>\`, and that copy is served.
What cannot be merged is logged `### ovmerge` and shown on screen by sc3perf (OVWARN) for the first 90 s.
Switches: `SC3NETMOD_OVMERGE=0` (old behaviour), `SC3PERF_OVWARN=0` (no on-screen lines). No mods page row: nothing
for a player to choose, the merge only acts on files another mod changed.

## Files the overlay shadows

Same 34 files in `stage\src` (release source), `stage\release` (LAN 2026-11-20) and this tree. They follow the installed
packages, so `py -3.12 re/tools/netmod/overlay_base.py --tree <root> --check` lists them for any tree.

| Folder | Files | Merge |
|---|---|---|
| `Apps\Res` | `BUILDFAM.IXF` | IXF per record, "TXT!" records line by line |
| `Apps\Res\SSimData\<lang>` x7 (DUTCH, ENGLISH, English-UK, FRENCH, GERMAN, ITALIAN, SWEDISH) | `TRBLKATT.IXF`, `VPATHATT.IXF` (English-UK: `TrBlkAtt.IXF`, `VPathAtt.IXF`) | IXF per record (binary: both sides changed = conflict) |
| `Apps\Res\TilingRules` | `Collapse.txt`, `DIAG_Set.txt`, `{HWAY,POWR,RAIL,ROAD}_GRND_{Complex_Convert,Convert,Protected,Set}.txt` (18) | none: warning |
| `Apps\Sys` | `SYS.PAK` | per member, then per ini line |

The other 96 overlay files are new names (81 `Res\Sprites`, 14 `Res\Text\<lang>`, 1 `Res\Occupant`): they shadow no
stock file by path. Not checked: whether a new overlay segment holds a resource key {type, group, instance} that a
player's own new segment also uses (GZ load order decides that, not this block).

## How the merge works

Base file `mods\netmod\overlay_base.txt` (`re/tools/netmod/overlay_base.py`, 0.95 MB for the 34 files): per file the
stock SHA-256, per IXF record `{group, instance, type}` + FNV-1a 64 of the payload, per SYS.PAK member its name + FNV,
and for text records per keyed line FNV hashes of key, value and whole line, plus `BuildingCount`. Hashes only, no EA
text or data. Built from the GOG 2.0.949 stock files (the tool refuses a non-stock source; `netpack.py install` falls
back to `original\gog_2.0.949` when the tree's Apps is patched, as the LAN tree's community SYS.PAK is).

Per record / member / keyed line: changed only by theirs -> theirs; changed only by ours -> ours; same change on both ->
kept once; changed differently on both -> ours kept, counted as a conflict (warning). New records, members, lines and
sections from theirs are added (a new line after the nearest earlier line of theirs that ours has, in the same section).
`BuildingCount` = ours + (theirs - stock). A BUILDFAM `Key: g,t,id,weight` line is keyed by its id, so a weight change
is a value change; ini keys that repeat in a section (Default.ini `[DBSegments]`) are matched by whole line.
When the merge changes nothing (the overlay already holds the change, as after `community_patch.ps1`) the overlay file
is served as before. STYLEMIX off (`SC3NETMOD_STYLEMIX=0`) filters the merged BUILDFAM.

Cost at start: 203 to 234 ms in game for the 34 files (cold reads), 31 to 62 ms warm (host runs).

## Offline test: 21/21

`py -3.12 re/tools/netmod/ovmerge_test.py` compiles the DLL's own merge source into `ovmerge_host.exe` (with stubs),
builds a fake game root per case in `%TEMP%\ovmerge_test` (EA files stay out of the repo) and checks the served file
with `ixf_parse` / `syspak_parse`. Run under test-slot, 2026-11-21:

| Case | Result |
|---|---|
| stock game files | nothing merged, no warning |
| farm mod (BUILDFAM family 25: Windmill weight 60, Hans Silo 0, Tool Shed removed + count 9 -> 8; a new family 0x7F) | family 25 = our 15 style-mix lines + the farm edits in place, count 24 -> 23; family 0x7F added; the other 30 families ours byte for byte; no warning |
| SYS.PAK mod (SC3ZoneLayer.ini farms up to land value 125; Default.ini new `[DBSegments]` row; new member FarmMod.ini) | zone member from theirs, row added before `[ResourceFactories]` with our 2 rows kept, member added, every other member ours, archive round-trips |
| community patch in both copies (what community_patch.ps1 does) | overlay served, "already has it", no warning |
| community patch in Apps only, against the zip's overlay (stage\src) | petition lines 0xD9..0xDB and `NumberOfPetitionerMessages` 210 -> 212 merged, no warning |
| overlay already patched by us (a bat_growables-style line in family 25) + the farm mod | both kept, count 24 |
| same Key line, different weight on both sides | ours kept, one line for the id, warning names BUILDFAM.IXF |
| TilingRules edit | overlay served, warning names ROAD_GRND_Set.txt |
| all three mods | 2 merged, 1 warned |
| `SC3NETMOD_OVMERGE=0` / no base file | nothing checked |

Also checked: `netpack.apply_outputs` (overlay mode) writes `overlay_base.txt` and removes it when the last file goes.
`netpack.py selftest` was started and stopped after 70 min without output (as in verify/batslots); not a result.

## In game (dev\overlaymerge, windowed, posted keys only)

| Run | Setup | Evidence |
|---|---|---|
| A | tree as shipped: community lines in both SYS.PAK copies | `ovmerge: 34 shadowed file(s) checked in 203 ms: 33 stock, 0 merged, 0 with a change the game does not see`; SYS.PAK "nothing to merge, the overlay copy already has it"; sc3perf `OVWARN> sc3netmod: no unmerged change, nothing to show`; start as normal (`A_shipped_tree_menu.png`) |
| C | farm + SYS.PAK + rules test mods, `SC3NETMOD_OVMERGE=0` (the player's case) | FILELOG: `Apps\Sys\SYS.PAK -> ...\mods\netmod\overlay\Apps\Sys\SYS.PAK`, `Apps\Res\BuildFam.IXF -> ...\overlay\Apps\Res\BUILDFAM.IXF` (GZResourceD.dll); `FarmMod.IXF` opened 0 times; no on-screen line (`C_ovmerge_off_end.png`) |
| B | same mods, OVMERGE on (Farmsville) | log: family 25 merged (3 line changes, count 24 -> 23), record 0x7F added, Default.ini row added, SC3ZoneLayer.ini taken from theirs, FarmMod.ini added, ROAD_GRND_Set.txt `###` not mergeable; FILELOG: `SYS.PAK -> %TEMP%\sc3netmod_merge_10480\33_SYS.PAK` (SC3U.exe, simvariables.dll), `BuildFam.IXF -> ...\00_BUILDFAM.IXF` (GZResourceD.dll), and `filelog: CreateFileA "...\Apps\Res\FarmMod.IXF" ... -> ok (GZResourceD.dll)`: the game loaded the segment only the merged Default.ini names. On screen, red: "Otro mod cambió archivos que el mod de carreteras reemplaza: ROAD_GRND_Set.txt / El juego no ve ese cambio. Detalles en sc3netmod.log" (`B_ovmerge_on_t35.png`) |
| STYLEMIX | farm mod only, `SC3NETMOD_STYLEMIX=0` | the filtered copy is made from the merged file: count 23, `405000,0` (set line at weight 0), `5000,60`, `5003,0` |

Pictures in `MAIN\verify\overlaymerge\owner_shots\` (gitignored).

Not shown in game: farms growing with the new weights. Farmsville under `anarchy_ind=5000` for 8 and 10 minutes at
speed 4 regrew almost no farm lots (677/516/16 plowed/wheat/windmill at start, 676/511/16 after 5 min), and the
SIMGEOM family objects are not kept after load (0 objects with vtable SIMGEOM+0x29130 in a read-only Frida scan:
AddFamily copies the members into the rule lists, BUILDING_PICK.md). The proof that the game reads the farm edit is
the merged BUILDFAM served to GZResourceD plus the offline content check of that file.

## Release notes for the orchestrator

- `mods\netmod\overlay_base.txt` must ship beside `mods\netmod\overlay\` (zip and LAN). `stage_lan_release.py` now
  stages it and builds it into the source tree when missing; `netpack.py install` keeps it current.
- Without the file (an older release folder) sc3netmod logs "not checked" and behaves as before.
- Players with another mod's TilingRules edit, or a line changed differently on both sides, see the red lines for 90 s.

## Files

`re/harness/src/sc3netmod_ovmerge.c` (new), `re/harness/src/sc3netmod.c`, `re/harness/src/sc3perf.c` (OVWARN),
`re/harness/lang/*.txt` (`perf.ovwarn_files`, `perf.ovwarn_hint`, 7 languages), `re/tools/netmod/overlay_base.py`,
`ovmerge_host.c`, `ovmerge_test.py` (new), `re/tools/netmod/netpack.py`, `re/scripts/lan_release/stage_lan_release.py`.
