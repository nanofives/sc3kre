# STATUS relprep3 (2026-11-25: ROTPLACE mods page row, then prepare sc3mods-2026-11-25, do not publish)

## goal
Part 1: mods page row for sc3resize ROTPLACE, merged to main. Part 2: stage, smoke, Jotti, zip and notes for
sc3mods-2026-11-25 (LFSTALL + ROTPLACE + its row). No swap, deploy or GitHub release.

## verdict
DONE, ready for the owner's call to publish.
- Part 1: row "Girar con TAB al colocar" / "TAB rotates when placing" (`-SC3RESIZE_ROTPLACE`), key `resize.mt_rotplace`
  in all 7 tables, off/on round trip proven over restarts. child/rotrow 403a0757 merged no-ff into main a464cdfe, then
  8b647cbb on main restores it.txt's line endings (a sed in rotrow had rewritten its CRLF; content was right).
  dev/rotrow removed. Record: verify/rotrow/RESULTS.md.
- Part 2: verify/mods_release_1125/RESULTS.md (draft). stage/release_1125 against LAN 2026-11-24: 9 changed (sc3landfill,
  sc3resize, 7 lang tables), 0 added, 0 removed. Smoke clean (Berlin all mods, TAB label es + en, mods page row es + en,
  Moscow then Load City Farmsville: landfill keeps filling, BOOK equal). Jotti 0/13 for both DLLs. Zip
  stage/sc3mods_2026-11-25.zip, SHA-256 62295817A4C89DFC07778898ED86022EC0F0A23B66A9CE6EAF3679875BD6CC59.

## blocked on
nothing.

## files owned
- committed: verify/rotrow/RESULTS.md, re/harness/src/sc3resize.c, re/harness/lang/*.txt (Part 1),
  verify/mods_release_1125/RESULTS.md, re/sessions/STATUS_relprep3.md
- gitignored: verify/rotrow/owner_shots, verify/mods_release_1125/{gh_notes.md, readme_new_in.txt, readme_lines.md,
  jotti_results.json, stage.log, owner_shots/, work/}, stage/build_1125, stage/bins_1125, stage/release_1125,
  stage/zip_1125, stage/sc3mods_2026-11-25.zip, dev/rel1125 (smoke tree, prunable)

## game-harness need
none left (PIDs 13860, 4520, 1288, 20604, 16348 started and stopped by this session, claim released).

## asks of other sessions
Orchestrator: owner call, then swap + LAN deploy + GitHub release + README lines (RESULTS "Left for the orchestrator").
