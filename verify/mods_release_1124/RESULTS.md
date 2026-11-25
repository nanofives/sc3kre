# RESULTS (DRAFT) - sc3mods release 2026-11-24, prepared, not published

Round 2026-11-24f, child relprep2. Owner 2026-11-24: "Prepare it". Source: main 90a8b9fe. Not done (by the brief):
stage/release swap, LAN deploy, GitHub release.

| what | record |
|---|---|
| pw1024: sc3bigcity GRIDCAP (power / water fill caps scale with width above 256 cells) | verify/pw1024/RESULTS.md |
| lotgrowb: sc3simrun LOTGROW (9 SIMRCI rule slots), sc3resize mods page row "Non-square zoned buildings", lang key `resize.mt_lotgrow` | verify/lotgrowb/RESULTS.md |
| stylepal: style_mix 1.3.0 lot colours (new 2627D60E_netpack_set.DAT) | verify/stylepal/RESULTS.md |

Mod sources changed since 08c0357 (`git diff --stat 08c0357..HEAD -- re/harness/src re/harness/lang`): sc3bigcity.c,
sc3resize.c, sc3simrun.c, sc3simrun_lotgrow.c (new, included by sc3simrun.c), sc3simrun_lotgrow_tab.h, the 7 lang tables.
Nothing else.

## Stage source

- stage/src/mods/netmod backed up to `stage/src_netmod_backup_20261124` (robocopy, 201 MB), then
  `netpack.py uninstall style_mix` and `netpack.py install re/tools/netmod/examples/style_mix --tree stage/src --allow-tree`:
  14 min 17 s for both, all 25 packages re-merged, exit 0, log `netpack_stylemix.log`.
- Report: civic looks as in 1.2.0 (6 at +400000, 15 at +1500000, 15 at +2600000). Lot colour: European `lawn_soil` 113 buildings /
  2,176 pixel records recoloured (8 already match), Asian `lawn_soil` 118 / 2,064 (12), North American `lawn` 133 / 2,880 (8),
  0 skipped. Same numbers as stylepal's build report.
- Against the backup: 4 overlay files changed (Occupant/OccupantAttribs_Korea.IXF, Sprites/5432D60E_netpack_set.DAT,
  Sprites/547B7DF5_netpack_set.DAT, Sprites/CSAttrib_Korea.IXF), 1 added (Sprites/2627D60E_netpack_set.DAT), ledger.json and
  2 files under packs/ changed. `overlay_base.txt` and BUILDFAM.IXF unchanged.

## Build and stage

- stage/build_1124 from main 90a8b9fe (`build_mod.ps1`, CL cleared): sc3bigcity 143,872, sc3simrun 157,696, sc3resize
  762,880 bytes. `sc3lang.py check`: 374 keys in all 7 tables, 0 missing, 0 unknown, 0 format mismatches.
- stage/bins_1124 = bins_1121 + those 3 DLLs + the 7 lang tables.
- `stage_lan_release.py --game stage/src --bins stage/bins_1124 --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1124 --label 2026-11-24
  --community stage/community_1106`: 3,681 files, 784.3 MB (log `stage.log`).
- Against LAN 2026-11-21 (stage/release manifest): 14 changed, 1 added, 0 removed.

| file | why |
|---|---|
| Apps/sc3bigcity.dll | GRIDCAP |
| Apps/sc3simrun.dll | LOTGROW |
| Apps/sc3resize.dll | mods page row "Non-square zoned buildings", left-column row spacing 15 -> 14 px |
| Apps/sc3lang/{de,en,es,fr,it,nl,sv}.txt | key `resize.mt_lotgrow` (374 keys) |
| mods/netmod/overlay/Apps/Res/Occupant/OccupantAttribs_Korea.IXF | style_mix 1.3.0: prop 0x67 of the North American copies points at their own frame tables |
| mods/netmod/overlay/Apps/Res/Sprites/CSAttrib_Korea.IXF | style_mix 1.3.0: frame tables of the North American copies |
| mods/netmod/overlay/Apps/Res/Sprites/5432D60E_netpack_set.DAT, 547B7DF5_netpack_set.DAT | style_mix 1.3.0: European / Asian copies' lot pixels recoloured |
| mods/netmod/overlay/Apps/Res/Sprites/2627D60E_netpack_set.DAT (added) | style_mix 1.3.0: North American copies' own pixels (same kind as the two set DATs, EA pixels recoloured) |

## Smoke test (dev/rel1124, made with `sc3dev new rel1124 -Base stage/release_1124 -NoBuild`)

Shipped files only: stage/release_1124 sc3mods.dll in the tree's Apps, the 11 mod DLLs, perf.ini, sc3natworld.bin and
sc3lang in inst (byte compare against stage/release_1124/Apps: equal). Windowed, posted input, GZ menu posts
({0x025F0A91, item}) and Frida camera calls only. PIDs 16908, 21160, 12856, 20624, 2400, 3908 started and stopped by
this session. Harness claimed as relprep2.

| check | result | picture (`owner_shots/`) |
|---|---|---|
| Berlin start + load | `11 mod(s) loaded`, city drawn, sim running (TRIPMODES months advancing) | `01_berlin_loaded.png` |
| GRIDCAP | `--- GRIDCAP: power/water fill caps (600/500) scale with width/128 above 256 cells`. Berlin (256): stats lines only, `0 at the cap, 0 past the shipped cap` | |
| LOTGROW | `### LOTGROW: on, 9 of 9 rule slots armed` (Berlin and Sacramento). Berlin, 2 min: 6,529 Apply calls, 0.0547 ms per call, `non-square placed/considered: none (refused 0)` (no non-square package in the release tree) | |
| OVMERGE | Berlin and Sacramento `34 shadowed file(s) checked: 33 stock, 0 merged, 0 with a change the game does not see`, SYS.PAK (community lines) "nothing to merge" | |
| style_mix 1.3.0 | sc3netmod serves `Res\Sprites\2627D60E_netpack_set.DAT` from the overlay (SIMSPR opens it at 2.5 s), with 5432D60E / 547B7DF5. stylepick ON, Berlin `style European + mix`, Sacramento `style North American + mix` | |
| mods page, Spanish (Berlin) | both pages, new row "Zonas: edificios no cuadrados" (on) last in the left column "Simulación y edificios", clear of "Los cambios se aplican..." below it, nothing overlapping | `02_modspage_es.png`, `03_activar_mods_es.png` |
| mods page, English (Sacramento, `SC3MODS_LANG=en`) | "Non-square zoned buildings" (on), nothing overlapping | `04_sacramento_loaded_en.png`, `05_modspage_en.png`, `06_activar_mods_en.png` |
| 1024 city (`verify/pw1024/pw1024_repro_1024.sc3`) | `GRIDCAP power: 1022 iterations (shipped cap 600, now 4800), 0.68 ms: region x 0..1023 rows 495..524`, `GRIDCAP water: 1022 iterations (shipped cap 500, now 4000), 0.24 ms: region x 2..1023 rows 513..528`, 4 power and 3 water fills in 60 s, all end to end (shipped caps stopped at x 602 / 502, pw1024 arm A) | `08_pw1024_x610.png` (camera past the old cut) |
| Sacramento growth, European picked, Mix off | `stylepick: SetCityScheme from City Properties ... style European`, saves `style European written`. Growth runs below (step 7). The recoloured lawns show: the European copies' lots are green lawn, not the dark plots of 2026-11-21's picture | `07_city_properties_european_mix_off.png`, `verify/relprep2/style_pick_before_after.jpg` |

VEH lines:
- Every run: the usual start-up `0xC0000096 at SC3U.exe+0x84122`, once.
- The 1024 run only, at 4.86 s (load, before the first frame): `0xC0000005 at KERNEL32.DLL+0x2D2D0`, READ of
  `0x128CF000` (a page start, eax `FFFFF000`, esi `0x1000`), stack through KERNEL32+0x1CA70 and sc3resize.dll+0x49C77 /
  +0x49CDC, SIMSPR+0x4ECD3. A first-chance fault the VEH logger saw. The process ran on for 60 s after it, sim months
  advancing and 7 GRIDCAP fills logged. [UNCERTAIN] which sc3resize function is at +0x49C77 (not mapped here); the shape
  (page-by-page read loop in KERNEL32 called from sc3resize, which calls IsBadReadPtr 499 times) matches a pointer probe.
  It was not seen in Berlin, Sacramento or the three Sacramento runs.
- No crash in any run.

Logs: `berlin_*.log`, `sac_*.log`, `pw1024_*.log` here, style-pick runs in `verify/relprep2/runs/`. No BMP dumps left.

Not checked here: a non-square building growing (no such package in the release tree; game-tested by lotgrowb on the
same source), a 512 city, Asian copies' colours in game.

## Jotti

0 of 13 engines for each of sc3bigcity.dll (job uu1v3obzk0), sc3simrun.dll (7l8qymlasf), sc3resize.dll (e0vfhdsnwy):
stage/build_1124, the same bytes as stage/release_1124/Apps. `jotti_results.json`.

## Zip (built, not published)

The 2026-11-21 zip (SHA-256 AAD800C2... checked) unpacked to stage/zip_1124, with the 3 DLLs and Apps/sc3lang from
stage/release_1124, the 4 changed overlay files and the new 2627D60E_netpack_set.DAT, README.txt header
"Release 2026-11-24 (replaces 2026-11-21)" and a "NEW IN 2026-11-24" section (`readme_new_in.txt`). 200 entries (old order,
the new DAT first among the Sprites files): 193 equal to the LAN manifest, overlay SYS.PAK differs by design (no community
lines in the zip), README.txt and the 5 tools\bld_render files not in it, as in 2026-11-21. `testzip` clean.

`stage/sc3mods_2026-11-24.zip`, 106,839,831 bytes, SHA-256
BB53D9D8FE1DC60462D30A2B12A266F47EE56480BF60976FC5E5DD0DA191C8DA.

Draft GitHub notes: `verify/mods_release_1124/gh_notes.md`.

VOICE.md was not found at `C:\Users\maria\Desktop\Proyectos\VOICE.md` (or anywhere two levels under Proyectos). The text
follows the rules quoted in CLAUDE.md: no em-dashes, semicolons, emoji, ellipsis or intensifiers, numbers from the RESULTS
files only.

## Style-pick picture (step 7)

`verify/relprep2/style_pick_before_after.jpg`, notes in `verify/relprep2/NOTES.md`.

## Left for the orchestrator

- Owner call to publish. Then: stage/release -> stage/release_1121_old, stage/release_1124 -> stage/release, LAN deploy
  (15 files), GitHub `sc3mods-2026-11-24` with the zip, "superseded" line on the 2026-11-21 notes, repo README mods
  section (power and water on big maps, non-square zoned buildings row, lawn colours).
- dev/rel1124 (smoke tree, branch child/rel1124 with no commits) can be pruned. Its Cities holds test saves only
  (pw1024 copy, sp_churned*, autosaves); the stock city files there are untouched hard links.

## Published 2026-11-24

Owner: "Yes, publish". stage/release swapped (old: stage/release_1121_old), LAN deploy incremental (15 of 3,681 files,
48.3 MB, nginx check OK). GitHub `sc3mods-2026-11-24`, target f31ea5da, asset downloaded back, SHA-256
BB53D9D8FE1DC60462D30A2B12A266F47EE56480BF60976FC5E5DD0DA191C8DA matches. The 2026-11-21 notes start with a
"superseded" line. Repo README updated (power and water across big maps, lawns that match the city; the non-square
zoned buildings row came with lotgrowb).
