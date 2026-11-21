# RESULTS (DRAFT) - sc3mods release 2026-11-21, prepared, not published

Round 2026-11-21b, child relprep. Owner 2026-11-21: "Prepare a release". Source: main b6dfcfa. Not done (by the
brief): stage/release swap, LAN deploy, GitHub release.

| what | merges | record |
|---|---|---|
| nopause: sc3simrun NOPAUSE + mods page row "No pause in pop-ups" (off) | 4f257a9 | verify/nopause/RESULTS.md |
| sc3perf stall sampler reads return-address bytes under a guard | 5ffc661 | verify/nopause/RESULTS.md ("Found on the way") |
| overlaymerge: sc3netmod OVMERGE, sc3perf OVWARN, mods/netmod/overlay_base.txt, stage_lan_release.py | d45c96d | verify/overlaymerge/RESULTS.md |
| stylepick: sc3netmod STYLEPICK, sc3resize Mix box + row, style_mix 1.1.0 | 4cbf5f7 | verify/stylepick/RESULTS.md |
| civicstyle: sc3resize civic style looks + row, style_mix 1.2.0 | e5e3000 | verify/civicstyle/RESULTS.md |
| lang tables (373 keys) | the merges above | |

## Stage source

- stage/src/mods/netmod backed up to `stage/src_netmod_backup_20261121`, then `netpack.py uninstall style_mix` and
  `netpack.py install re/tools/netmod/examples/style_mix --tree stage/src` (1.2.0): 12 min 16 s for both, all 25 packages
  re-merged, log `netpack_stylemix.log`. Merge report: civic looks 6 at +400000, 15 at +1500000, 15 at +2600000
  (156 North American copies, 166 family lines). Against the backup: exactly the 5 files style_mix writes changed
  (overlay BUILDFAM.IXF, Occupant/OccupantAttribs_Korea.IXF, Sprites/CSAttrib_Korea.IXF, Sprites/5432D60E_netpack_set.DAT,
  Sprites/547B7DF5_netpack_set.DAT), plus ledger.json, packs/style_mix, and the new `overlay_base.txt` (952,695 bytes,
  34 shadowed files). 148 other files equal.

## Build and stage

- stage/build_1121 from main b6dfcfa (`build_mod.ps1`, CL cleared): sc3simrun 141,312, sc3perf 211,456, sc3netmod 550,912,
  sc3resize 762,368 bytes. `sc3lang.py check`: 373 keys in all 7 tables, 0 missing, 0 unknown, 0 format mismatches.
- stage/bins_1121 = bins_1120 + those 4 DLLs + the 7 lang tables.
- `stage_lan_release.py --game stage/src --bins stage/bins_1121 --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1121 --label 2026-11-21
  --community stage/community_1106`: 3,680 files, 770.4 MB (log `stage.log`).
- Against LAN 2026-11-20 (stage/release manifest): 16 changed, 1 added, 0 removed.

| file | why |
|---|---|
| Apps/sc3netmod.dll | OVMERGE, STYLEPICK |
| Apps/sc3perf.dll | stall sampler guard, OVWARN |
| Apps/sc3resize.dll | nopause row, Mix box + stylepick row, civic style looks + row |
| Apps/sc3simrun.dll | NOPAUSE |
| Apps/sc3lang/{de,en,es,fr,it,nl,sv}.txt | new keys (373) |
| mods/netmod/overlay/Apps/Res/BUILDFAM.IXF | style_mix 1.2.0 family lines (North American copies) |
| mods/netmod/overlay/Apps/Res/Occupant/OccupantAttribs_Korea.IXF | style_mix 1.2.0 exemplars (copies + civic looks) |
| mods/netmod/overlay/Apps/Res/Sprites/CSAttrib_Korea.IXF | style_mix 1.2.0 frame tables |
| mods/netmod/overlay/Apps/Res/Sprites/5432D60E_netpack_set.DAT, 547B7DF5_netpack_set.DAT | style_mix 1.2.0 set pixels (civic looks) |
| mods/netmod/overlay_base.txt (added) | OVMERGE stock hashes |

The overlay SYS.PAK is unchanged against 2026-11-20 (the community step gave the same 3 changes).

## Smoke test (dev/rel1121, made with `sc3dev new rel1121 -Base stage/release_1121 -NoBuild`)

Shipped files only: stage/release_1121 sc3mods.dll in the tree's Apps, the 11 mod DLLs, perf.ini, sc3natworld.bin and
sc3lang in inst (mod DLLs removed from the tree's Apps). Windowed 800x600, posted input and GZ message posts only
(menu commands {0x025F0A91, item}), PIDs 19248 and 18424 started and stopped by this session.

| check | result | picture |
|---|---|---|
| Berlin start + load | `11 mod(s) loaded`, city drawn | `01_berlin_loaded.png` |
| OVMERGE | `ovmerge: 34 shadowed file(s) checked in 16 ms: 33 stock, 0 merged, 0 with a change the game does not see`; SYS.PAK (community lines) "nothing to merge, the overlay copy already has it"; sc3perf `OVWARN> sc3netmod: no unmerged change, nothing to show`. Sacramento: 33 stock in 31 ms | |
| STYLEPICK | `stylepick: ON`; Berlin `load: no saved style (style = the city's set, mix on)`, `SetCityScheme from load ... skin 00000000 -> E523F3FB, style European + mix`; Sacramento `style North American + mix` | |
| SPMIX / CIVVAR | `SPMIX> on`, `CIVVAR> on: ... style looks on (style_mix copies +400000 / +1500000 / +2600000 ...)` | |
| NOPAUSE | `### NOPAUSE: off (stock ...)` (default) | |
| mods page, Spanish | both pages, new rows "Sin pausa en ventanas" (off), "Cívicos: estilos del juego" (on), "Estilo: solo edificios nuevos" (on), nothing overlapping | `02_modspage_es.png`, `03_activar_mods_es.png` |
| mods page, English (`SC3MODS_LANG=en`, Sacramento) | "No pause in pop-ups", "Civic buildings: game styles", "Style: new buildings only", nothing overlapping | `10_modspage_en.png`, `11_activar_mods_en.png` |
| Police civic list, Berlin | "Europa: Comisaría" (base key 0xD2, the city's style), "Norteamérica" 0x27AD12, "Asia" 0x16E432, each with its picture; Esc = no tool (`CIVDLG> ... window closed without a pick`) | `04_police_list_berlin.png`, `05_police_list_asia.png` |
| Police civic list, Sacramento (English) | "North America" first, then Europe, Asia, "Look 1 of 3" | `12_police_list_sacramento_en.png` |
| City Properties | "Mezclar los tres estilos" / "Mix all three styles" box ticked under Edificios (cities with no saved style), Esc = no SetCityScheme | `06_city_properties_berlin.png`, `13_city_properties_sacramento_en.png` |
| New City after the mods pages | 11 New City windows (1, then 10 cycles of: Preferences > mods page > Activar mods > Esc, Esc > New > "No" > window > Esc), all drawn with the Mix box, **0 crashes**, process alive after each, no new VEH line | `07_newcity_1.png`, `08_newcity_10x_contact.png` (the 10 cycle grabs) |

VEH lines: one per run, the usual start-up `0xC0000096 at SC3U.exe+0x84122` (684 ms in Berlin). Nothing else.
The stylepick GZGraphicD+0x18C7A crash did not show in these 11 windows.

Logs: `berlin_*.log`, `sacramento_*.log` (gitignored). No BMP dumps were made.

Not checked here: NOPAUSE switched on, placing a civic look, a farm-style mod edit (all game-tested on the same
source by their streams).

## Jotti

0 of 13 engines for each of sc3simrun.dll, sc3perf.dll, sc3netmod.dll, sc3resize.dll (stage/build_1121, the same bytes
as stage/release_1121/Apps). `jotti_results.json`.

## Zip (built, not published)

The 2026-11-20 zip tree (SHA-256 947C6B73... checked) with the 4 DLLs and Apps/sc3lang from stage/release_1121, the 5
changed overlay files and overlay_base.txt from it, README.txt header "Release 2026-11-21 (replaces 2026-11-20)" and a
"NEW IN 2026-11-21" section (`readme_new_in.txt`). 199 entries: 192 equal to the LAN manifest, overlay SYS.PAK differs by
design (no community lines in the zip), README.txt and the 5 tools\bld_render files not in it, as in 2026-11-20.

`stage/sc3mods_2026-11-21.zip`, 94,745,136 bytes, SHA-256
AAD800C2676712978AD8A00BD7A3DB91667A0B59973759085B3E201E13497E65.

Draft GitHub notes: `verify/mods_release_1121/gh_notes.md`.

## Left for the orchestrator

- Owner call to publish. Then: stage/release -> stage/release_1120_old, stage/release_1121 -> stage/release, LAN deploy
  (17 files), GitHub `sc3mods-2026-11-21` with the zip, "superseded" line on the 2026-11-20 notes, repo README mods section.
- dev/rel1121 (smoke tree, branch child/rel1121 with no commits) can be pruned.

## Published 2026-11-21

Owner: "Yes, release". stage/release swapped (old: stage/release_1120_old), LAN deploy, served label 2026-11-21
3,680 files. GitHub `sc3mods-2026-11-21`, target 08c0357, asset downloaded back, SHA-256
AAD800C2676712978AD8A00BD7A3DB91667A0B59973759085B3E201E13497E65 matches. The 2026-11-20 notes start with a
"superseded" line. Repo README updated (civic styles, no-pause row, SimCity 4-style picker, overlay merge).
