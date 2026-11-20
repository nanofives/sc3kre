# STATUS sc4cmp (round 2026-11-20b)

## goal
Forum-ready side-by-side pictures, SimCity 4 left, SimCity 3000 right, SimCity 4's own buildings only.

## verdict
Done. 12 pictures + one four-sides picture in `MAIN\verify\sc4cmp\forum\` (local, gitignored), 4 more in `forum\extra\`.
The SC4 side is the converter's own SC4 view boxes, props and full-lot textures drawn through SC4's fitted camera. Against
SC4's own building pictures: 99.96-100% of drawn pixels opaque in SC4's picture, mean difference 4.8-10.4 of 255 (resampling).
Captions and numbers: `verify/sc4cmp/RESULTS.md`.

## built
- `re/tools/sc4conv/compare_sheet.py` (renderer + sheet layout + check, no SC4 data)
- local only: `MAIN\verify\sc4cmp\work\` (conv output, `match_ingame.py`, `ingame.json`, `only.txt`)

## proven game-side vs static only
Static only: pictures from the bldrender frames and existing frame dumps (rounds sc4ci, sc4lottex). The game was not run.

## blocked on
Nothing.

## files owned (orchestrator commits, both need `git add -f`)
- `re/tools/sc4conv/compare_sheet.py` (ignored by `/re/tools/*`)
- `re/sessions/STATUS_sc4cmp.md` (ignored by `/re/*`)
- `verify/sc4cmp/RESULTS.md`

## game-harness need
None.

## asks of other sessions
- Converter: 24 of 50 converted models reach below SC4's ground (Small Shops, Retail Stores, Ferrrara Inc., Smith Tower).
  `bldrender.place` puts the lowest vertex on the lawn, so they stand 0.4-5.5 m above it with a second lawn edge.
  RESULTS.md section 5. Rerun compare_sheet.py after a fix.
- City Hall (`RW46x34_CityHall_03C1`): a grey hook above the dome in the SC3 frame, not in SC4's picture.
