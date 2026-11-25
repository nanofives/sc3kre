# RESULTS (DRAFT) - sc3mods release 2026-11-25, prepared, not published

Round relprep3 (child of the orchestrator). Source: main 8b647cbb. Not done (by the brief): stage/release swap, LAN
deploy, GitHub release, repo README.

| what | record |
|---|---|
| lfstall: sc3landfill LFSTALL (landfill stopped taking garbage in a second city of the same game) | verify/lfstall/RESULTS.md |
| rotplace: sc3resize ROTPLACE (TAB turns a square plopped building while placing), lang key `resize.rotplace_label` | verify/rotplace/RESULTS.md |
| rotrow: mods page row "TAB rotates when placing" (`-SC3RESIZE_ROTPLACE`), lang key `resize.mt_rotplace` | verify/rotrow/RESULTS.md |

Mod sources changed since 25040c54 (`git diff --stat 25040c54..HEAD -- re/harness/src re/harness/lang`):
sc3landfill.c (LFSTALL), sc3resize.c (ROTPLACE hooks, key, ini/env, Mover keeps the rotation, the mods page row and
its layout), sc3resize_placehints.c (the rotation line of the cost label), sc3resize_rotplace.c (new, included by
sc3resize.c), the 7 lang tables (2 keys each: `resize.rotplace_label`, `resize.mt_rotplace`). Nothing else. The other
commits since 25040c54 touch notes, verify records and scripts only.

## Build and stage

- stage/build_1125 from main 8b647cbb (`build_mod.ps1`, CL cleared): sc3landfill 136,192 bytes, sc3resize 767,488.
  `sc3lang.py check`: 376 keys in all 7 tables, 0 missing, 0 unknown, 0 format mismatches, 0 not in cp1252.
- stage/bins_1125 = bins_1124 + those 2 DLLs + the 7 lang tables (byte compare: exactly those 9 differ).
- stage/src unchanged since 2026-11-24 (no package changes in this release).
- `stage_lan_release.py --game stage/src --bins stage/bins_1125 --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1125 --label 2026-11-25
  --community stage/community_1106`: 3,681 files, 784.3 MB, 37 s (log `stage.log`).
- Against LAN 2026-11-24 (stage/release manifest): 9 changed, 0 added, 0 removed.

| file | why |
|---|---|
| Apps/sc3landfill.dll | LFSTALL: groups, pendings and developer per city (keyed by the garbage valve), router drops phantom pending, self-heal |
| Apps/sc3resize.dll | ROTPLACE (TAB / Shift+TAB, cost label line, Mover keeps rotation) and its mods page row, left column layout for the 8th row |
| Apps/sc3lang/{de,en,es,fr,it,nl,sv}.txt | keys `resize.rotplace_label` and `resize.mt_rotplace` (376 keys) |

## Smoke test (dev/rel1125, made with `sc3dev new rel1125 -Base stage/release_1125 -NoBuild`)

Shipped files only: stage/release_1125 sc3mods.dll in the tree's Apps, the 11 mod DLLs, perf.ini, sc3natworld.bin and
sc3lang in inst (byte compare against stage/release_1125/Apps: equal). Windowed, posted input, the game's Load City
menu command (`{0x025F0A91, 0x10009301}`), Frida camera and tool-arm calls only. PIDs 20604 and 16348 started and
stopped by this session. Harness claimed as relprep3. Pictures in `owner_shots/` (not committed).

| check | result | picture |
|---|---|---|
| Berlin, all mods (es) | `[+] 11 mod(s) loaded`, city drawn, sim running, `ROTPLACE> on`. sc3landfill `DEV>` and STATS for Berlin's 8 landfills (blocked 0) | `01_berlin_loaded.png` |
| TAB on the Mayor's House (Berlin, es) | stock tool armed (10110), TAB: log `ROTPLACE> TAB: rotation 1 (90 degrees) ... 0x0000277E`, cost label "$0" plus the line "Giro 90 grados (TAB)" | `02_berlin_mayor_tab_rot0.png`, `03_berlin_mayor_tab_rot1_label.png` |
| TAB, English (Moscow, `SC3MODS_LANG=en`) | two TABs: rotation 1 then 2, label "$0" plus "Rotation 180 degrees (TAB)" | `07_moscow_mayor_tab_rot2_label_en.png` |
| mods page, Spanish | "Girar con TAB al colocar" (on), 8th row under "Simulación y edificios". Notes, city heading and "Recalcular agua salada" clear of Volver, nothing overlapping | `04_modspage_es.png`, `05_activar_mods_es.png` |
| mods page, English | "TAB rotates when placing" (on), nothing overlapping. Autosave shows unchecked: turned off for this run, see below | `10_modspage_en.png`, `11_activar_mods_en.png` |
| LFSTALL repro shape | Moscow first (1 landfill, 191 cells: `DEV>`, STATS blocked 0, `BOOK>` equal), then Load City Farmsville in the same game. On its first sim tick: `DEV> landfill developer 0x179E0A40 ..., a new city's (the previous one was dropped)` and `CITY> new city (valve 0x15F9E878, was 0x15AABAF0): 1 landfill(s) and their pendings dropped`. Top speed, about 5 minutes (May 1904 to Nov 1908): fill 490,223 / 578,945 / 632,557 / 660,103 / 671,013, pending 988 / 968 / 1,012 / 1,108 / 1,192, blocked 0, stall 0, heals 0, every `BOOK>` line equal (valve room = sum of cell room, valve waiting = sum of pendings) | `06_moscow_loaded_en.png`, `08_farmsville_loaded_after_load_city.png`, `09_farmsville_after_5min.png` |

- The run 2 inst had `sc3mods.ini [mods] sc3autosave.dll=0` (deleted afterwards): Load City lists MAIN\Cities and
  sc3autosave writes beside the loaded city. Nothing was written to MAIN\Cities.
- VEH: only the usual start-up `0xC0000096 at SC3U.exe+0x84122`, once per run. No crash.
- Logs: `work/run1/`, `work/run2/` (resize.log and every mod log).

Not checked here: a placement with a turned building (the Mayor's House cell was red in Berlin and Moscow, both already
have one; rotplace placed all four rotations on the same code), Shift+TAB (posted keys cannot carry Shift, as in
rotplace: needs owner check), the self-heal (not triggered, as in lfstall).

## Jotti

0 of 13 engines for sc3landfill.dll (job 88aljoopsb) and sc3resize.dll (eeolqyi2oj), the stage/release_1125 bytes.
One more entry reads "Filetype not supported". `jotti_results.json`.

## Zip (built, not published)

The 2026-11-24 zip (SHA-256 BB53D9D8... checked) unpacked as stage/zip_1124, copied to stage/zip_1125, with the 2 DLLs
and Apps/sc3lang from stage/release_1125, README.txt header "Release 2026-11-25 (replaces 2026-11-24)", one more line
on the sc3resize entry ("TAB turns a building while you place it") and a "NEW IN 2026-11-25" section
(`readme_new_in.txt`). 200 entries in the old order (`work/mkzip.py`). Against the 2026-11-24 zip exactly 10 differ
(the 2 DLLs, the 7 tables, README.txt). `testzip` clean.

`stage/sc3mods_2026-11-25.zip`, 106,845,564 bytes, SHA-256
62295817A4C89DFC07778898ED86022EC0F0A23B66A9CE6EAF3679875BD6CC59.

Draft GitHub notes: `gh_notes.md`. Draft repo README lines: `readme_lines.md`. Text written to the CLAUDE.md rules:
no em-dashes, semicolons, emoji, ellipsis or intensifiers, numbers only from the RESULTS files.

## Left for the orchestrator

- Owner call to publish. Then: stage/release -> stage/release_1124_old, stage/release_1125 -> stage/release, LAN deploy
  (9 files), GitHub `sc3mods-2026-11-25` with the zip and `gh_notes.md`, "superseded" line on the 2026-11-24 notes,
  repo README lines from `readme_lines.md`.
- dev/rel1125 (smoke tree, branch child/rel1125 with no commits) can be pruned.
