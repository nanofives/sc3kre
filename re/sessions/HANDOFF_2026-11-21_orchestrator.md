# Handoff 2026-11-21 (orchestrator "SC3 Simtropolis feedback triage")

Safe point: nothing of mine running. main pushed (last: eb249e1 CHILD_PROTOCOL suite modes, 35b125c round brief).

## State

- Latest mods release: **sc3mods-2026-11-20** (GitHub + LAN, non-square buildings drawn whole, record
  verify/mods_release_1120/RESULTS.md). stage/release = 2026-11-20.
- Importer page live with: civic / reward / landmark kinds, non-square lots + 5x5, SC4 from downloads and from the
  player's install (civic, parks, rewards, landmarks, opt-in shops / offices / industry / farms box), SC4 props and lot
  textures, ground fix, tree black-patch fix (peel until none left), smooth title / button font, scrollbar fix.
- Building suite: run_all.sh now starts suite.py, modes SUITE_CHANGED / normal / SUITE_DEEP (CHILD_PROTOCOL.md 2).
- Simtropolis drafts in .happy-share/cmwgg6bdp01jhmz1b3kp9os44/: simtropolis_buildings_post.html (+_links, names
  sc3mods-2026-11-20, side-by-side SC4 pictures from verify/sc4cmp/forum), simtropolis_post_1119c.html, the gallery
  post. None posted as far as known.

## Running round: re/sessions/ROUND_2026-11-21_simtropolis_feedback.md (owner order, one at a time)

1. **popslow** (child cmwqdh0x46ymdnz1ck9g00jpb, workspace dev\popslow): paused for a reboot, its handoff is
   re/sessions/STATUS_popslow.md. Findings so far: budget / Preferencias / Query / landmark and Rewards lists stop the
   date in stock too (cISC3City::SimHiddenPause SIMCITY 0x100058ac), mods do not change it. Reunirse, advisors,
   petitions do not slow the date with the mods (1.49-1.50 days/s at speed 3), the mods make those pop-ups much
   cheaper per frame than stock. Left: Review flyout windows, trace the pause callers, RESULTS.md. Possible owner call:
   keep the sim running while those windows are open (changes stock behaviour).
2. overlaymerge, 3. stylepick, 4. civicstyle: not started (briefs in the round file).
Then a reply to the player (draft, owner posts).

## Owner calls on record (2026-11-20/21)

SC4 game props and lot textures on by default. SC4 landmarks / rewards keep SimCity 4's lot. Maxis SC4 building pictures
OK in forum posts, community ones not. Smooth title / button font. Suite: all five speed-ups, install set kept at 28.
