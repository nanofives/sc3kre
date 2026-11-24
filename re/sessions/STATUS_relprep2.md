# STATUS relprep2 (round 2026-11-24f, prepare next sc3mods release, do not publish; then style-pick picture)

## goal
Stage (style_mix 1.3.0 into stage/src), build sc3bigcity / sc3simrun / sc3resize from main 90a8b9fe, smoke test, Jotti,
zip, notes draft. Then re-take the style-pick before / after picture. No swap, deploy or GitHub release.

## verdict
DONE, ready for the owner's call to publish. Record: verify/mods_release_1124/RESULTS.md (draft).
- stage/src: style_mix 1.3.0 installed (14 min 17 s), 4 overlay files changed + 2627D60E_netpack_set.DAT added, report
  numbers = stylepal's. Backup stage/src_netmod_backup_20261124.
- stage/release_1124 (label 2026-11-24, 3,681 files): against LAN 2026-11-21, 14 changed + 1 added, all explained.
- Smoke (dev/rel1124, shipped files): Berlin + Sacramento load, GRIDCAP + LOTGROW 9/9 armed, new DAT served, mods pages
  es + en with the new row (nothing overlapping), 1024 repro city power x 0..1023 and water x 2..1023. No crash.
  One extra first-chance VEH line on the 1024 load (KERNEL32+0x2D2D0 from sc3resize+0x49C77, game ran on), in RESULTS.
- Jotti 0/13 for the 3 changed DLLs.
- Zip stage/sc3mods_2026-11-24.zip, SHA-256 BB53D9D8FE1DC60462D30A2B12A266F47EE56480BF60976FC5E5DD0DA191C8DA.
- Notes draft verify/mods_release_1124/gh_notes.md.
- Picture verify/relprep2/style_pick_before_after.jpg (camera 165,165, Sandbox on, churn then 4 min without churn),
  notes verify/relprep2/NOTES.md.

## blocked on
nothing. VOICE.md is missing from Proyectos (text written to the CLAUDE.md rules).

## files owned
- verify/mods_release_1124/RESULTS.md (commit), and gitignored there: gh_notes.md, readme_new_in.txt, jotti_results.json,
  netpack_stylemix.log, stage.log, berlin_*.log, sac_*.log, pw1024_*.log, owner_shots/01..08*.png
- verify/relprep2/** (NOTES.md, picture, work scripts, runs, fd)
- re/sessions/STATUS_relprep2.md
- gitignored: stage/build_1124, stage/bins_1124, stage/release_1124, stage/src (style_mix 1.3.0),
  stage/src_netmod_backup_20261124, stage/zip_1124, stage/sc3mods_2026-11-24.zip, dev/rel1124 (smoke tree, prunable)
- dev/rel1124/wt: no changes.

## game-harness need
none left (all 6 game PIDs stopped, harness claim released).

## asks of other sessions
Orchestrator: owner call, then swap + LAN deploy + GitHub release (steps in RESULTS "Left for the orchestrator").
