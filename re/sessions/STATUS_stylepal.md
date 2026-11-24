# STATUS stylepal (round 2026-11-23d): style copies' lot colours

## goal
Evidence and mock-ups only: why European / Asian style copies read as another neighbourhood in a North American city
(owner's picture verify/forumshots/owner_palette_complaint.png), recolour options on the copies only, their cost.
Nothing installed or built until the owner picks.

## verdict (done, details verify/stylepal/RESULTS.md, pictures verify/stylepal/owner_shots 01-07)
- The dark blob is mostly four yard filler lots, not houses: 3032 / 3034 / 3041 / 3042 (class 3300, 1x1). Their North
  American art is a bright lawn with a vegetable patch, a pool yard, a play yard, a fenced lawn. The European art (the
  Asian set uses the identical pixels) is dark allotment gardens and a dirt yard. They are 3,355 of 7,131 European
  copies in the Sacramento after-save, 450 of 667 within 30 cells of the owner's camera.
- Measured (Lab, zoom 3, lot diamond): European lawn L 36-44 against North American 52-61 on the same ids, a* -15..-19
  against -26..-29 (duller), brown soil 0.28-0.52 of the lot against 0.01-0.26, pools 0 against up to 0.07.
- Scene (pixels where new buildings grew, owner's camera): lawn L 55 -> 43, a* -30 -> -17, brown share 0.15 -> 0.33.
- Mock-ups a / b / c taken in game in the dev tree (Sacramento, owner's camera, offset 0,0 to the owner's frame), plus
  Moscow with 10,595 North American copies grown by the style pick (now / a / b).
- Recommendation: c for European / Asian copies (scene lawn share back to the host's 0.48), a for North American
  copies, buildings untouched. Owner picks before anything is built.

## built
Nothing in the worktree. Tools in verify/stylepal/work (gitignored): extract.py, measure.py, recolor.py, run_scene.py,
moscow_grow.py, lab.py / sp_lab.py (copies of forumshots' with a menucmd job).

## proven game-side vs static only
Game-side: the recoloured copy art draws in game (Sacramento frames a, b, c). Static: the class measurements.

## blocked on
Nothing.

## files owned
None to commit. Local only: verify/stylepal/** (EA art), dev/stylepal/tree overlay DAT edits (restored to original
after each run; originals kept in dev/stylepal/orig).

## game-harness need
Harness claimed 2026-11-23 20:54, released 21:26 (handed to pw1024 on request). No game of mine running.

## asks of other sessions
None.

## handoff (reboot 2026-11-24 13:30)
Safe point. Steps 1-5 done, no game or test run of mine open, the dev tree's art is back to the original.
Next: wait for the owner to pick a / b / c (recommended: c for European and Asian copies, a for North American).
After the pick, build it in netpack `style_sets` / `netpack_stylesets.py`. Then do the per-id lawn tuning (RESULTS.md, Verdict 4).

## owner pick (2026-11-24, Happy question card)
- European and Asian copies in a North American host: option c.
- North American copies in a European or Asian host: option a (own frame tables + about 10 MB of pixels, netpack_stylesets change).
- One art variant (tuned for a North American host), not per-host DATs.
- Per-id tuning: yes, match each copy to its own base building's lawn, not the class mean.
Not built yet: the build is a new round for the orchestrator to brief.

## round 2026-11-24e: build (brief re/sessions/ROUND_2026-11-24e_stylepal_build.md): DONE
verdict: built, style_mix 1.3.0. Details and numbers: verify/stylepal/RESULTS.md "Build" section.
- Worktree had been reaped: recreated dev\stylepal\wt on child/stylepal reset to main 3b561f75.
- European / Asian copies: option c per building (host = the North American art of the same id). North American
  copies: option a per building (host = the other sets' art), own frame tables (group 0x2627D60F) and pixels
  (2627D60E_netpack_set.DAT, 13.7 MB). 7,120 records recoloured, 0 buildings skipped.
- Scene, owner's camera: lawn L 42.5 (now) -> 53.6 built (host 55.5, mock-up c 49.9), lawn share 0.39 -> 0.46 (host
  0.47), brown 0.35 -> 0.28. Moscow North American copies: lawn L 52.4 -> 41.3 (mock-up a 43.0).
- Game: Sacramento + Moscow pictures (owner_shots 10-13), save + reload same look, save with 7,131 European copies
  loaded with the package removed: alive after 60 s, no fault but the benign SC3U+0x84122 probe.
- Size 31.7 -> 45.5 MB. Build 1.9 s -> 2 min 14 s, so every netpack install / uninstall takes about 2 min more.
  Measured today: install 823 s, uninstall 1,172 s (suite running beside them part of the time).

## proven game-side vs static only
Game-side: built art draws (Sacramento, Moscow), save/reload, package-removed load. Static: per-building numbers.

## checks
- Building suite normal mode: 41 of 41 passed (verify/stylepal/suite/run.log), covers qfs.py.
- netpack.py validate examples/style_mix: passes.
- netpack.py selftest: started, no output after 70 min, stopped (same as earlier rounds, verify/batslots); not a result.
  It covers the road examples, not style_sets.

## files owned (worktree dev\stylepal\wt, uncommitted, for the orchestrator to commit by path)
- re/tools/netmod/netpack_lotcolour.py (new)
- re/tools/netmod/netpack_stylesets.py
- re/tools/netmod/netpack.py
- re/tools/netmod/netpack.schema.json
- re/tools/netmod/examples/style_mix/manifest.json (1.3.0)
- re/tools/netmod/examples/style_mix/README.md
- re/tools/qfs.py (back-reference speed-up, same output)
Local only: verify/stylepal/** (EA art, results), dev\stylepal\tree (style_mix 1.3.0 installed, ledger + packs
copied from stage\src: the tree is now a netpack tree, sc3dev remove needs -Force).

## stage source note
stage\src still has style_mix 1.2.0: re-install from main after the merge (RESULTS "Stage source for the next release").

## game-harness need
Claimed 2026-11-24 17:0x as stylepal, released at the end of this round.
