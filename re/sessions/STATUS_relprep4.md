# STATUS relprep4 (2026-11-25: prepare sc3mods-2026-11-26, do not publish)

## goal
Stage, smoke, Jotti, zip and notes for sc3mods-2026-11-26 (SPNEWSKIN + REWARDLOOK + style_mix 1.4.0). No swap, deploy
or GitHub release.

## verdict
DONE, ready for the owner's call to publish. Record: verify/mods_release_1126/RESULTS.md (draft).
- stage/src: style_mix 1.4.0 reinstalled (14 min 7 s, exit 0), exactly the 4 expected overlay files changed.
  Backup stage/src_netmod_backup_20261126.
- stage/release_1126 against LAN 2026-11-25: 13 changed (sc3netmod, sc3resize, 7 lang tables, 4 overlay files),
  0 added, 0 removed.
- Smoke clean: Berlin all mods (es), TAB label, landfill STATS, mods page row es + en, reward picker (European City Hall
  placed in a North American city through the real button), New City Asian -> skin 6523F3D5 and Asian rewards.
- Jotti 0/13 for both DLLs. Zip stage/sc3mods_2026-11-26.zip, SHA-256
  2490A907DA45E6B7E7AD49F76D7BFC2928712BCE7C57445EDF82738A466514A4.

## blocked on
nothing.

## files owned
- committed: verify/mods_release_1126/RESULTS.md, re/sessions/STATUS_relprep4.md
- gitignored: verify/mods_release_1126/{gh_notes.md, readme_new_in.txt, readme_lines.md, jotti_results.json,
  netpack_stylemix.log, stage.log, owner_shots/, work/}, stage/build_1126, stage/bins_1126, stage/release_1126,
  stage/zip_1126, stage/sc3mods_2026-11-26.zip, stage/src_netmod_backup_20261126
- dev/rel1126 removed (sc3dev remove).

## game-harness need
none left (PIDs 13120, 16808, 7536 started and stopped by this session, claim released).

## asks of other sessions
Orchestrator: owner call, then swap + LAN deploy + GitHub release + README lines (RESULTS "Left for the orchestrator").
