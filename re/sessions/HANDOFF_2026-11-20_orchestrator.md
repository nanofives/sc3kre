# Handoff 2026-11-20 (orchestrator "SC3 Simtropolis feedback triage"), before the LIVING-PC reboot

Safe point: nothing running. All children finished and merged, main pushed (origin/main 5bea3fc + this file).
No game, no test run, no background job of mine is active.

## State

- Latest mods release: **sc3mods-2026-11-19c** on GitHub (civic looks list window) and on the LAN server
  (served label 2026-11-19c, 3,679 files). stage/release = 2026-11-19c (old: stage/release_1119b_old, _1118b_old).
  Records: verify/mods_release_1119b/RESULTS.md, verify/mods_release_1119c/RESULTS.md.
- Importer page (docs/buildings/importer, live on GitHub Pages) and guide (docs/buildings) are current with:
  civic / reward kinds, landmark description, SC4 landmark lots, the player's SimCity 4 install as a source
  ("Open SC4 game": civic buildings, parks, rewards, landmarks), SC4's own props from the install, SC4 lot textures.
  Sample pack zip (release sample-buildings-2026-11-18) re-uploaded with the current importer files.
- SimCity 4 Deluxe is installed on LIVING-PC by Steam for the SC4 work:
  C:\Program Files (x86)\Steam\steamapps\common\SimCity 4 Deluxe\ (EA content, read in place only).
  Steam was started by this session (PID 9616), it will not come back after the reboot by itself.

## Rounds done in this stretch (briefs in re/sessions, results in verify/<stream>/RESULTS.md)

- 2026-11-19i: civrew (research, re/analysis/CIVIC_REWARD.md), plop2 (landmark follow-ups)
- 2026-11-19j: civmod (civic looks, new rewards, loader declares reward types, Mover fix) -> released 2026-11-19b
- 2026-11-19k: civtest (all 17 civic bases, reward lots, 3x3 growable), civdlg (list window) -> released 2026-11-19c
- 2026-11-19l: sc4civ, sc4baseprops, sc4lottex (all merged; SC4_FORMATS.md sections 10-12)

## Waiting on the owner (question card was on screen when the reboot warning came)

1. SimCity 4 game props and lot textures are ON by default whenever the page has them. Keep on (my
   recommendation) or off by default?
2. Next step: (a) update the Simtropolis buildings post, (b) test commercial / industrial SC4 packs (needs the
   owner's downloads on \\mariano-server\Compartido), or (c) stop.

Re-ask both after the reboot if no answer arrived.

## Simtropolis drafts (owner pastes them, none posted yet as far as known)

All in .happy-share/cmwgg6bdp01jhmz1b3kp9os44/ (generators in verify/showcase/site/):
- simtropolis_post_1119c.html + _links.html (reply to the thread, make_st_post_1119c.py). Corrected: OBJ only.
- simtropolis_gallery_1119c.html + _links.html (junction gallery highlights)
- simtropolis_buildings_post.html + _links.html (buildings + SimCity 4, make_st_post_buildings.py).
  **Out of date**: still says SC4 civic / parks / rewards, SC4's own props and lot textures are not done. Update
  from verify/sc4civ, sc4baseprops, sc4lottex RESULTS.md if the owner picks it (no pictures of SC4 art).

## Open items (not started)

- SC4: lighting side in 2 of 4 rotations and camera angle (inherent), commercial / industrial packs barely tested,
  94 animated prop rows (type 0x29A5D1EC) unread, 21 SC4 parks / rewards without their own model, Large High School
  skipped (one view piece 59.66 px off), owner's real folder pick of the SC4 install untested.
- Civic list window shows a fixed line, not the importer's description of the look.
- Importer page header still says "OBJ, glTF, GLB or FBX" although install reads OBJ only (guide is right).
- Steam / retail Baapp.exe hash for the render kit (owner).
- Leftover dev folders dev\airsea, dev\bldrender, dev\civtest: worktrees already removed, folders held by idle
  child sessions. Delete after the reboot (`pwsh re/scripts/sc3dev.ps1 prune` or remove the empty folders).
- Happy close_child returns 415 for every child: they stay idle, nothing to do.

## Memory

project-civic-reward.md (11-19b/c facts) is in the PFB memory dir and indexed in MEMORY.md.
