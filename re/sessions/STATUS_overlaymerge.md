# STATUS overlaymerge (round 2026-11-21, Simtropolis feedback stream 2) - DONE

## goal
A player's farm mod "installs without errors but never shows in game". With sc3netmod the game reads
`mods\netmod\overlay\<path>` instead of `<path>` for every file the overlay holds, so a mod that edits the stock Apps
copy afterwards is never read. List the shadowed files, detect player changes against stock hashes, merge them into the
served copy where the format allows, warn in the log and on screen otherwise.

## verdict + deciding code
- Cause: our DLL. `sc3netmod.c` OVERLAY `ov_map` serves `overlay\X` for any X in the overlay list whatever `<root>\X`
  holds. 34 files shadowed (same list in stage\src, stage\release, dev tree): BUILDFAM.IXF, TRBLKATT/VPATHATT x7
  languages, 18 TilingRules texts, SYS.PAK. Reproduced in game (run C).
- Fix: OVMERGE, `re/harness/src/sc3netmod_ovmerge.c`: three-way merge at DllMain against
  `mods\netmod\overlay_base.txt` (stock hashes, `re/tools/netmod/overlay_base.py`), merged copy in
  `%TEMP%\sc3netmod_merge_<pid>\` served instead. IXF per record (TXT! records per line, BuildingCount by deltas),
  SYS.PAK per member + ini line, TilingRules warn only. `SC3NETMOD_OVMERGE=0` = old behaviour. sc3perf OVWARN shows
  unmerged files on screen 90 s (`SC3PERF_OVWARN=0`). No mods page row needed.

## built
sc3netmod.dll + sc3perf.dll in dev/overlaymerge/inst (2026-11-21), clean build.

## proven game-side vs static only
- Offline (DLL's own merge code in ovmerge_host.exe): 21/21, `re/tools/netmod/ovmerge_test.py`.
- Game: run A (shipped tree, community in both copies) = 33 stock + SYS.PAK "already has it", no warning. Run C
  (test mods, OVMERGE=0) = BuildFam/SYS.PAK from the overlay, FarmMod.IXF never opened. Run B (test mods, OVMERGE on)
  = merged BUILDFAM / SYS.PAK served to GZResourceD / SC3U / simvariables, FarmMod.IXF (named only by the merged
  Default.ini row) opened by GZResourceD, red warning on screen for the TilingRules edit. STYLEMIX=0 filters the merged
  BUILDFAM. Pictures: MAIN\verify\overlaymerge\owner_shots\.
- Not shown: farms regrowing with the new weights (churn does not regrow Farmsville's farms in 10 min; family objects
  are not kept in memory after load).

## blocked on
nothing

## files owned (not committed, orchestrator commits by path)
- re/harness/src/sc3netmod_ovmerge.c (new, IGNORED by .gitignore: `git add -f`)
- re/tools/netmod/ovmerge_host.c (new, IGNORED by .gitignore: `git add -f`)
- re/tools/netmod/overlay_base.py, re/tools/netmod/ovmerge_test.py (new)
- re/harness/src/sc3netmod.c, re/harness/src/sc3perf.c
- re/harness/lang/{de,en,es,fr,it,nl,sv}.txt
- re/tools/netmod/netpack.py, re/scripts/lan_release/stage_lan_release.py
- verify/overlaymerge/RESULTS.md, re/sessions/STATUS_overlaymerge.md

## game-harness need
none beyond sc3dev run. Tree restored to its own files after the tests (.ovmerge-orig backups removed); the tree keeps
a generated mods\netmod\overlay_base.txt.

## asks of other sessions
Release: `mods\netmod\overlay_base.txt` must ship beside `mods\netmod\overlay\` (zip and LAN). stage_lan_release.py
builds it into stage\src on the next stage if missing; netpack install keeps it current. Player reply: ask which farm
mod and which files it edits (a TilingRules edit would still only warn).
