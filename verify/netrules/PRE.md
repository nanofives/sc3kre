# netrules in-game check: pre-registration (2026-10-13)

Written before the run. Fills in the exact edit, city and cell once chosen (addendum below, also before the run).

## Claim under test
`netrules preview` predicts, from the save and an edited TilingRules directory, which tiles change when the game
re-tiles a region. One in-game run checks that prediction on a stock tree (Simcity_stock_netrules, hard-linked, rule
files replaced by delete + copy, never edited in place).

## Arms
- A (control): stock rules, same city copy, same retile message (GZ 0x637c0dab over the same rectangle). Expect no
  tile change in the rectangle beyond what `netrules preview` predicts for the stock rules.
- B (edit): edited rules, same city, same message. Expect exactly the tiles `preview` lists as changed, with the
  listed (id, state).

## Pass / fail
Pass: every tile in the rectangle read back live (nr_drive.py cells) equals the simulator's prediction for that arm,
or each difference falls in a disagreement class the validation table already measures for that net.
Fail: any predicted change that does not happen, or a change outside the prediction with no class.

## Addendum 1 (filled before the run, 2026-10-13)
- edit: `verify/netrules/edit_straight.json`, applied with `netrules apply-edits` (netpack_rules.apply): stock rule 21
  of ROAD_GRND_SimpleRules.txt (selector 5, no conditions, self 29/0) gets results self 29/1. Lint: no new finding.
- city: Farmsville.sc3 (copy in the instance folder, hash checked against MAIN\Cities before the run).
- trigger: GZ message 0x637c0dab {mask 1, 100<<16|128, 110<<16|128} posted with `nr_drive.py retile 1 100,128,110,128`
  (FUN_10013afe -> FUN_100151f1: HWAY then ROAD over the rectangle).
- read-back: `nr_drive.py cells 90,124,119,132` (x 90..119, z 124..132) before and after the message, per arm.
- prediction files: `nr_predict.py predict` -> predA.json (stock rules), predB.json (edited), window margin 3.
- Arm A predicted: no surface network cell in the window changes (0 of the window's cells differ from the save).
- Arm B predicted: 22 cells change, all on z=128: x=95..114 29/0 -> 29/1, x=94 29/0 -> 39/0, x=115 29/0 -> 39/2.
  Nothing else in the window changes. (`netrules preview --rect 100,128,110,128` lists the same 22.)
- before-read: in both arms the window must equal the save before the message (else the run is void, not a fail).
