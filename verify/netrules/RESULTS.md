# netrules in-game check: results (2026-10-13)

Pre-registration: `PRE.md` (addenda 1 and 2 committed before the retile message was sent in either arm).

## Verdict: PASS
A rules edit applied with `netrules apply-edits` (netpack_rules.apply) changed exactly the tiles the simulator
predicted, in the game, on stock DLLs: 22 of 22 predicted changes happened, and the other 12 network cells of the
window stayed as predicted. The stock-rules control arm changed nothing, also as predicted.

## Setup
- Tree: `Simcity_stock_netrules` (hard-linked stock tree, SIMNTWRK at the anchor hash), instance
  `re\harness\inst_netrules`, city `nv_conn.sc3` = Farmsville.sc3 (SHA-256 9776E016...4EB7, same as MAIN\Cities).
- Edit: `edit_straight.json`: ROAD_GRND_SimpleRules.txt stock rule 21 (selector 5, no conditions) results
  self 29/0 -> self 29/1. Edited file SHA-256 A593CF5E...D9E7 (`run/ROAD_GRND_SimpleRules.edited.txt`).
  Installed for arm B by delete + copy of the hard link, restored afterwards as a hard link to Simcity_stock
  (hash back to 4C3182BD...9158, stock).
- Trigger: `nr_drive.py retile 1 100,128,110,128` = GZ message 0x637c0dab {1, 100<<16|128, 110<<16|128}.
- Read-back: `nr_drive.py cells 90,124,119,132` before and after, compared with `nr_predict.py compare`.

## Arms
| arm | rules | PID | before == save | after == prediction | predicted changes that happened |
|---|---|---|---|---|---|
| A | stock | 36924 | 34/34 | 34/34 | 0 of 0 |
| B | edited | 22272 | 34/34 | 34/34 | 22 of 22 |

Arm B changes, all on z=128: x=95..114 29/0 -> 29/1, x=94 29/0 -> 39/0, x=115 29/0 -> 39/2. The two end pieces
are a knock-on effect (their neighbours turned 29/1, which the final stage reads through the exemplar
connectivity masks), and they were predicted before the run, not fitted after it.

Files: `run/predA.json`, `run/predB.json`, `run/liveA_before.jsonl`, `run/liveA_after.jsonl`,
`run/liveB_before.jsonl`, `run/liveB_after.jsonl`.

## Not covered
- Visual check pending: display asleep (taskbar clock 9:48 against a real 11:42, frames pure white). The result
  rests on the live occupant read, not on a picture.
- One edit, one city, one rectangle, ROAD only. The other nets are covered by the offline validation table only.
- Arm A shows the message changes nothing with stock rules here; arm B is what shows the message really re-tiles.

## Tooling notes from the run
- On this tree the main loop removes posted messages with PeekMessageA(PM_REMOVE) and WM_JOB never reached
  DispatchMessageA (600 peeks in 2 s, our message returned once, 0 dispatches), so nr_drive.py now also runs jobs
  from a PeekMessageA return hook.
- A 30x9 `cells` job never returned within 120 s while each of its rows took about 2 s; nr_drive reads one row per
  job. Cause not looked into.
- The tips dialog at load blocks input; `re/tools/dismiss_tips.py` with SC3_PID clears it (needed two tries once).
