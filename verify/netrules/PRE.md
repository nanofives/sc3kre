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

## Addendum 1 (filled before the run)
- edit: TBD
- city / rectangle: TBD
