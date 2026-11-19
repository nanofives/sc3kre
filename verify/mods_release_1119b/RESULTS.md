# RESULTS - sc3mods release 2026-11-19b + LAN 2026-11-19b

Replaces sc3mods-2026-11-19. Owner calls 2026-11-19: civic buildings "Cycle looks", new rewards "Yes, build it",
Mover fix "Yes, with the next build", reward safety "Loader declares", then "Page side, then release" and
"Yes, release". Source: main 3f4c90d.

| what | merges | record |
|---|---|---|
| Civic looks on the stock civic buttons (CIVVAR, sc3resize hook on the shared call SIMGEOM 0x1000b1a3), mods page row "Civic buildings: more looks" | 289d3ce | verify/civmod/RESULTS.md, re/analysis/CIVIC_REWARD.md |
| New rewards (NEWREWARD, own ini through the game's ini class, unlock SIMADV 0x1000a7fa), row "New rewards" | 289d3ce, 95bbdfb | same |
| Reward types declared by sc3mods.dll before CitySim.ini, rewards in PlugIn\bldimport_rewards, sc3mods_patch -Restore / --restore move it to Apps\sc3mods_off\PlugIn | 95bbdfb | same, sections 4 to 6 |
| Mover for imported landmarks (type 18000) and new rewards | 289d3ce | same |

## Stage and checks

- DLLs from main into stage/build_1119b: sc3mods (126,976 bytes), sc3resize (748,544 bytes). stage/bins_1119b =
  bins_1118b + those + the 7 lang tables (352 keys each, 0 missing). Jotti: 0 / 13 each.
- stage_lan_release.py label 2026-11-19b: 3,679 files, against 2026-11-18b exactly 11 changed (2 DLLs, 7 lang tables,
  sc3mods_patch.ps1 and .sh). stage/release swapped (old: stage/release_1118b_old), LAN deploy incremental (11 files,
  1.1 MB), served label 2026-11-19b 3679.
- Smoke: dev tree from the new stage with the shipped DLLs (sc3mods.dll in tree\Apps, the rest in inst),
  xsect_sweep_built.sc3 loaded windowed. 11 mods loaded, lang 352 keys, log "CIVVAR> no civic variants ... the civic
  buttons are stock", "NEWREWARD> no reward rows ... rewards are stock", stylemix on, HWYSPEED on, one VEH FAULT line =
  the usual startup 0xC0000096 at SC3U.exe+0x84122. City drawn (picture checked).

## Zip

The 2026-11-19 zip tree with the 2 DLLs, Apps/sc3lang and both patch scripts from the stage, README.txt (header
2026-11-19b, NEW IN 2026-11-19b, sc3resize line). 198 entries: 191 equal to the LAN manifest, overlay SYS.PAK differs
by design, README.txt and the 5 tools\bld_render files not in it (the LAN stage has no tools folder).
sc3mods_2026-11-19b.zip, SHA-256 7183D4BE0925F41D8100E93BE5B32D4DEF8A9683509D19F79EDF7B3B20E51F21.

GitHub: `sc3mods-2026-11-19b`, target 3f4c90d, asset downloaded back, SHA-256 matches. The 2026-11-19 notes start with
a "superseded" line. Repo README "Building tools" updated.

Not checked: the bare unpatched exe after -Restore (fullscreen only, civmod run C is the stand-in), civic bases other
than police, reward lots other than 2x2, the mods page in languages other than Spanish.
