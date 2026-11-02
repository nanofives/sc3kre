# STATUS transitmap (round 2026-11-02b)

## goal
Owner: "add world map section below mapa de zonas to show places where people are not using public transit".

## verdict + deciding RVA
Done. The sim stores no trip mode (SimTransit 0x100070d0 / 0x100093e9 keep counts only). TRIPMODES' pop hook
(SimTransit 0x100072f8) sees each trip's origin node (type 0x80, rect +4..+0x10), so a new TRIPCELLS block counts
trips and transit trips per origin cell. sc3dataview adds an 11th Ver datos panel at the empty icon slot 10 under Mapa de
zonas (SIMUI FUN_10044430 call at 0x1004436b), a traffic-panel instance with its own vtable copy.

## built
dev/transitmap/inst: all 11 mods from main be42ba9 + this change (sc3resize, sc3dataview rebuilt).

## proven game-side vs static only
Game-side (Berlin, runs T1/T3/T4 in MAIN\verify\transitmap\runs): panel, icon, title, legend, caption, map data,
coordinates (2,680 of 2,698 raw cells match the game's trip bit), switch away/back, Usar mapa -> minimap. No FAULT.
Not run: English, a city with buses, 1024 city, city reload, many dialog reopen cycles.

## blocked on
Nothing.

## files owned (worktree dev/transitmap/wt, not staged)
- re/harness/src/sc3resize_vdbars.c   (TRIPCELLS block, exports sc3resize_tripcell / _tripcells_build / _tripcells_info, TRIPMODES slot [6] = any transit)
- re/harness/src/sc3dataview.c        (TRANSIT block: panel, layer 0x2750, caption; SC3DATAVIEW_TRANSIT=0 off)
- re/tools/dataview_lab.py            (NAME:vk<hex> step)
- verify/transitmap/RESULTS.md
Pictures (not to stage): MAIN\verify\transitmap\owner_shots\*.png, runs in MAIN\verify\transitmap\runs.

## game-harness need
None (lab done).

## asks of other sessions
- modlang: new inline strings in sc3dataview.c TRANSIT block (title, legend x2, caption lines).
- README mods section: one line for the new map (orchestrator at release).
