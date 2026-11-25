# RESULTS (DRAFT) - sc3mods release 2026-11-26, prepared, not published

Round relprep4 (child of the orchestrator). Source: main 48daabb2. Not done (by the brief): stage/release swap, LAN
deploy, GitHub release, repo README.

| what | record |
|---|---|
| stcompat: sc3netmod SPNEWSKIN (a New City takes the picked building set as its skin, `SC3NETMOD_SPNEWSKIN=0` = the 11-21 rule) | verify/stcompat/RESULTS.md |
| rewardlook: sc3resize REWARDLOOK (look picker for rewards and business deals) + style_mix 1.4.0 (`"rewards": true`), CIVSTYLE row relabelled | verify/rewardlook/RESULTS.md |

Sources changed since 62663e96 (`git diff --stat 62663e96..HEAD -- re/harness/src re/harness/lang re/tools/netmod`):
sc3netmod_stylepick.c (SPNEWSKIN), sc3resize.c and sc3resize_civic.c (REWARDLOOK, its switch, the row label key use),
the 7 lang tables (`resize.mt_civstyle` relabelled, new `resize.rl_desc_look` / `resize.rl_desc_stock`, 378 keys),
and the style_mix tooling: netpack_stylesets.py (REWARD_BASES, reward copies), netpack.py (report line),
netpack.schema.json (`rewards` key), stylemix_build.py (writes 1.4.0), examples/style_mix/{manifest.json, README.md}.
Nothing else. The other commits since 62663e96 touch notes, verify records and lab scripts only.

## Stage source

- stage/src/mods/netmod backed up to `stage/src_netmod_backup_20261126` (robocopy, 39,086 files, 214 MB), then
  `netpack.py uninstall style_mix --tree stage/src --allow-tree` and `netpack.py install
  re/tools/netmod/examples/style_mix --tree stage/src --allow-tree`: 14 min 7 s for both, all 25 packages re-merged,
  exit 0, log `netpack_stylemix.log` (gitignored).
- Report: reward looks 208, 8013, 8019, 8020, 8017, 8085 at +400000 (European), 243, 208, 8013, 219, 8019, 8011, 8020,
  8017, 8085 at +1500000 (Asian), the same 9 at +2600000 (North American). Civic looks and lot colours as in 1.3.0
  (European `lawn_soil` 113 / 2,176 recoloured, Asian 118 / 2,064, North American `lawn` 133 / 2,880, 0 skipped).
- Against the backup: exactly the 4 expected overlay files changed, with the sizes rewardlook measured:
  `Occupant/OccupantAttribs_Korea.IXF` 958,758 -> 969,532, `Sprites/CSAttrib_Korea.IXF` 851,808 -> 861,856,
  `Sprites/5432D60E_netpack_set.DAT` 11,155,014 -> 12,243,915, `Sprites/547B7DF5_netpack_set.DAT` 20,454,214 ->
  24,457,932. Also `ledger.json` and `packs/style_mix/{manifest.json, README.md}` (the installed package copy, not
  shipped). `2627D60E_netpack_set.DAT`, `overlay_base.txt` and BUILDFAM.IXF unchanged. Nothing else.

## Build and stage

- stage/build_1126 from main 48daabb2 (`build_mod.ps1`, CL cleared): sc3netmod 550,912 bytes, sc3resize 770,560.
  `sc3lang.py check`: 378 keys in all 7 tables, 0 missing, 0 unknown, 0 format mismatches, 0 not in cp1252.
- stage/bins_1126 = bins_1125 + those 2 DLLs + the 7 lang tables (byte compare: exactly those 9 differ). bins_1125's
  tables equal 62663e96's.
- `stage_lan_release.py --game stage/src --bins stage/bins_1126 --stock-modules original/modules --menu-bg
  stage/release/Apps/menu_bg.bmp --perf-ini stage/release/Apps/perf.ini --out stage/release_1126 --label 2026-11-26
  --community stage/community_1106`: 3,681 files, 789.4 MB, 42 s (log `stage.log`).
- Against LAN 2026-11-25 (stage/release manifest): 13 changed, 0 added, 0 removed.

| file | why |
|---|---|
| Apps/sc3netmod.dll | SPNEWSKIN |
| Apps/sc3resize.dll | REWARDLOOK (catalog GetSelected hook, look list for rewards), CIVSTYLE row label |
| Apps/sc3lang/{de,en,es,fr,it,nl,sv}.txt | `resize.mt_civstyle` relabelled, 2 new keys (378 keys) |
| mods/netmod/overlay/Apps/Res/Occupant/OccupantAttribs_Korea.IXF | style_mix 1.4.0: the 24 reward look exemplars |
| mods/netmod/overlay/Apps/Res/Sprites/CSAttrib_Korea.IXF | style_mix 1.4.0: their frame tables |
| mods/netmod/overlay/Apps/Res/Sprites/5432D60E_netpack_set.DAT, 547B7DF5_netpack_set.DAT | style_mix 1.4.0: European / Asian reward looks' pixels |

## Smoke test (dev/rel1126, made with `sc3dev new rel1126 -Base stage/release_1126 -NoBuild`)

Shipped files only: stage/release_1126 sc3mods.dll in the tree's Apps, the 11 mod DLLs, perf.ini, sc3natworld.bin and
sc3lang in inst (byte compare against stage/release_1126/Apps: equal). Windowed 800x600, posted input (sc3io), Frida
camera, tool-arm, skin and unlock calls only. Rewards opened through the real civic flyout button "Premios y
oportunidades", not the Frida 0x3b hotkey job. PIDs 13120, 16808, 7536 started and stopped by this session. Harness
claimed as relprep4. Pictures in `owner_shots/` (not committed).

| check | result | picture |
|---|---|---|
| Berlin, all mods (es) | `[+] 11 mod(s) loaded`, city drawn, sim running. `ROTPLACE> on`, `REWARDLOOK> on: ... 9 reward exemplars`, `stylepick: SPNEWSKIN on`. Load keeps the saved set (`skin 00000000 -> 00000000`) | `01_berlin_loaded.png` |
| TAB label (11-25) | Mayor's House tool armed, TAB: `ROTPLACE> TAB: rotation 1 (90 degrees) ... 0x000000F3 footprint 2x2`, cost label "Aspecto 1 de 2: Norteamericano \| §0" plus "Giro 90 grados (TAB)" | `02_berlin_tab_label.png` |
| landfill (11-25) | sc3landfill `READY`, `DEV>` landfill developer, `GROUPS>` 8 landfills / 719 cells, `STATS>` lines for all 8, blocked 0, stall 0 | |
| mods page, Spanish | "Cívicos y premios: estilos" (on) in "Simulación y edificios", "Girar con TAB al colocar" below it, nothing overlapping | `06_activar_mods_es.png` |
| reward picker, non-native look (Roadless Paradise, North American skin) | rewards unlocked (`civmod_lab.py unlock`), real button: Rewards list (8 rewards), Ayuntamiento picked: "Elegir aspecto" with Norteamérica / Europa / Asia, "Aspecto 2 de 3", European description. Log `CIVDLG> base 0xD0: picked entry 2 of 3 (Europeo)`, `REWARDLOOK> reward 0xD0: look 2 of 3, Europeo, key ... 0x00061B50`. Placed: occupant 400208, type 10120, cells 130..132 x 141..143, drawn European | `08_rewards_list.png`, `09_cityhall_b_looks.png`, `09_cityhall_d_placed.png` |
| SPNEWSKIN (English, `SC3MODS_LANG=en`) | main menu > Nueva Ciudad > Edificios Asian (Mix on) > OK > Aceptar este Terreno. Log `SetCityScheme from New City ...: asked set 6523F3D5, skin 00000000 -> 6523F3D5, style Asian + mix`, skin read back `0x6523f3d5` | `12_newcity_asian.png` |
| Asian rewards in that new city | Mayor's House: "Choose a look", "Asia: Casa del Alcalde" first, "The game's own reward, in this city's style (Asian)." Picked the original: `REWARDLOOK> reward 0xF3: the original (stock attrib)`, occupant 243 type 10110, drawn in the Asian set's look. City Hall original: occupant 208 type 10120, drawn Asian (same art as stcompat's Asian-skin picture `3_rewards_skin_na_vs_asian.png`) | `15_mayor_asian_b_looks.png`, `15_mayor_asian_d_placed.png`, `16_cityhall_asian_d_placed.png` |
| mods page, English | "Civic + rewards: game styles" (on), nothing overlapping | `17_activar_mods_en.png` |

- VEH: only the usual start-up `0xC0000096 at SC3U.exe+0x84122`, once per run. No crash.
- Autosave wrote `Berlin, Germany (auto 5 min).sc3` into dev/rel1126/tree/Cities only. Nothing written to MAIN\Cities.
- Logs: `work/run1/` (Berlin), `work/run2/` (Roadless Paradise), `work/run3/` (New City, en).
- Reward names in the list stay in the game's language (Spanish game text with `SC3MODS_LANG=en`), as in 11-25.

Not checked here: GigaMall (business deal) and a European city's rewards (same code path, listed open in rewardlook),
Shift+TAB (posted keys cannot carry Shift).

## Jotti

0 of 13 engines for sc3netmod.dll (job uekjixbfs2) and sc3resize.dll (g79ounbzgo), the stage/build_1126 bytes, equal
to stage/release_1126/Apps. `jotti_results.json`, uploader `work/jotti.py`.

## Zip (built, not published)

stage/zip_1125 copied to stage/zip_1126, with the 2 DLLs, Apps/sc3lang and the 4 overlay files from stage/release_1126,
README.txt header "Release 2026-11-26 (replaces 2026-11-25)", the sc3resize entry gains "looks of rewards and business
deals in every style", and a "NEW IN 2026-11-26" section (`readme_new_in.txt`). 200 entries in the 11-25 order
(`work/mkzip.py`). Against the 2026-11-25 zip exactly 14 differ (the 2 DLLs, the 7 tables, the 4 overlay files,
README.txt). Against stage/release_1126: 193 equal, overlay SYS.PAK differs by design (no community lines in the zip),
README.txt and the 5 tools\bld_render files are zip-only, as in 11-24 and 11-25. `testzip` clean.

`stage/sc3mods_2026-11-26.zip`, 111,341,275 bytes, SHA-256
2490A907DA45E6B7E7AD49F76D7BFC2928712BCE7C57445EDF82738A466514A4.

Draft GitHub notes: `gh_notes.md`. Draft repo README lines: `readme_lines.md`. Text written to the CLAUDE.md rules:
no em-dashes, semicolons, emoji, ellipsis or intensifiers, numbers only from the RESULTS files. The brief's row name
"Style picks new buildings" is shipped as "Style: new buildings only" (`resize.mt_stylepick`), the notes use the shipped
label.

## Left for the orchestrator

- Owner call to publish. Then: stage/release -> stage/release_1125_old, stage/release_1126 -> stage/release, LAN deploy
  (13 files), GitHub `sc3mods-2026-11-26` with the zip and `gh_notes.md`, "superseded" line on the 2026-11-25 notes,
  repo README lines from `readme_lines.md`.
- dev/rel1126 pruned at the end of this round (nothing in it needed).

## Published 2026-11-25

Owner: "Yes, publish". stage/release swapped (old: stage/release_1125_old), LAN deploy incremental (13 of 3,681 files,
40.0 MB, nginx check OK). GitHub `sc3mods-2026-11-26`, target 82ceeda7, asset downloaded back, SHA-256
2490A907DA45E6B7E7AD49F76D7BFC2928712BCE7C57445EDF82738A466514A4 matches. The 2026-11-25 notes start with a
"superseded" line. Repo README updated (rewards in every style, new cities take the picked style).
