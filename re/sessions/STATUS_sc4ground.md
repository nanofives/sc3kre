# STATUS sc4ground (round 2026-11-20c)

Worktree `dev\sc4ground\wt` (branch child/sc4ground, from main 497191d), nothing committed. Results:
`verify/sc4ground/RESULTS.md`.

## goal

24 of 50 converted SC4 models stood 0.4 to 5.5 m above the SC3 lawn (sc4cmp). Measure why, land SC4's ground on the
lawn, look at the Alamo's missing flagpole, check in pictures and in game, rebuild the forum pictures, full suite.

## verdict + deciding evidence

- Cause: SC4 lot object word 4 = the object's height above the lot. 2,431 prop rows on 815 install lots are not 0
  (signs and billboards, 0.25-324 m); the converter dropped it, so the signs hung up to 5.49 m under the ground and
  bldrender.place (lowest point on the lawn) lifted the lot. 23 of the 24; Smith Tower is its own view box at -0.41 m.
- Fix (converter only): prop height added; every vertex below y = 0 raised to 0 (house uv moved by the view's
  projection); lot quad at 0.01, window triangle at 0; one zero-area triangle at y = 0 in every OBJ (`sc4base`).
  A cut at y = 0 was built first and dropped: it removed Wong Insurance's paved forecourt (a mesh face 0.13 m under 0).
- Alamo flag: not a converter fault. Native zoom 4 draws the pole; `baked` doubles zoom 3, where the 0.14 m pole is
  0.4 px and drops out. Not changed (renderer style).

## built

`sc4conv.py`, `views.py`, `props.py`, `catalog.py`, `lottex.py` (comment), `compare_sheet.py`, `sc4web.js` (same steps),
`re/analysis/SC4_FORMATS.md` section 14 + word 4 row.

## proven game-side vs static only

- Game-side: Small Shops and Ferrrara Inc. on their lots in sc4ci's city, before / after frames
  (`verify/sc4ground/owner_shots/`). Game PIDs started and stopped: 8856, 8440.
- Static: all 194 OBJs of the 50 models have their lowest point at 0; 17 forum pictures rebuilt and looked at;
  Python = page 21 of 21 on the install step (affected buildings byte for byte). Full suite (six args + SC3PACK_PACKS +
  SC4INSTALL): 40 of 41, the failure `pagetest.mjs landmarks` a Chrome start-up EBUSY, 6 of 6 on rerun. Non-SC4
  goldens: 975 files, 0 differ from main's golden_setup.
- [UNCERTAIN] whether SC4 hides model parts under its terrain: no SC4 screenshot.

## blocked on

Nothing.

## files owned

- re/tools/sc4conv/sc4conv.py
- re/tools/sc4conv/views.py
- re/tools/sc4conv/props.py
- re/tools/sc4conv/catalog.py
- re/tools/sc4conv/lottex.py
- re/tools/sc4conv/compare_sheet.py
- re/tools/bldimport/sc4web.js
- re/analysis/SC4_FORMATS.md
- re/sessions/STATUS_sc4ground.md
- (local, gitignored) verify/sc4ground/*, verify/sc4cmp/forum/* rebuilt

## game-harness need

None left: harness claim released, no game running.

## asks of other sessions

Owner call, optional: `baked_sharp` (native zoom 4) would keep thin details such as the Alamo's flagpole.
