# STATUS relprep (round 2026-11-21b, prepare sc3mods-2026-11-21, do not publish)

## goal
Stage, smoke test, Jotti, zip and draft notes for sc3mods-2026-11-21 from main b6dfcfa. No swap, deploy or GitHub release.

## verdict
DONE, ready for the owner's call to publish. Record: verify/mods_release_1121/RESULTS.md (draft).
- stage/src: style_mix 1.2.0 installed (12 min), only the 5 style_mix files + overlay_base.txt changed. Backup
  stage/src_netmod_backup_20261121.
- stage/release_1121 (label 2026-11-21, 3,680 files): against LAN 2026-11-20, 16 changed + 1 added, all explained.
- Smoke (dev/rel1121, shipped files): Berlin + Sacramento load, OVMERGE 33 stock, STYLEPICK / SPMIX / CIVVAR on,
  NOPAUSE off by default, mods pages es + en with the 3 new rows, Police list 3 styles, City Properties Mix box,
  11 New City windows after the mods pages: 0 crashes. Only the usual start-up VEH line.
- Jotti 0/13 for the 4 changed DLLs.
- Zip stage/sc3mods_2026-11-21.zip, SHA-256 AAD800C2676712978AD8A00BD7A3DB91667A0B59973759085B3E201E13497E65.
- Notes draft verify/mods_release_1121/gh_notes.md.

## blocked on
nothing

## files owned
- verify/mods_release_1121/RESULTS.md (commit), and gitignored there: gh_notes.md, readme_new_in.txt, jotti_results.json,
  netpack_stylemix.log, stage.log, berlin_*.log, sacramento_*.log, owner_shots/01..13*.png
- re/sessions/STATUS_relprep.md
- gitignored: stage/build_1121, stage/bins_1121, stage/release_1121, stage/src (style_mix 1.2.0),
  stage/src_netmod_backup_20261121, stage/sc3mods_2026-11-21.zip, dev/rel1121 (smoke tree, prunable)
- dev/relprep/wt: no changes.

## game-harness need
none left (both game PIDs stopped).

## asks of other sessions
Orchestrator: owner call, then swap + LAN deploy + GitHub release (steps in RESULTS "Left for the orchestrator").
