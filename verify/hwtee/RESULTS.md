# hwtee results: the highway T was not offered for the owner's layout (owner bug 3, 2026-10-21)

Owner report (img3, LAN build of main 664a685): "connecting two highways like a T should prompt for creating the T
intersection and it doesn't". The stem ends with its stock caps against the through highway's side, no question.
The stock game has no prompt here. The question is hwask's (sc3netmod_hwask.c, the "Informe de Ingeniería" dialog).
Sheet: `MAIN\verify\hwtee\owner_shots\hwtee_sheet.png`.

## Cause
1. The owner's through highway ends 6 cells past the stem on the stem's right (seen from the stem), so its end cap sits
   at T frame dx 7. Measured in img3 against a dx-8 shot of my own in the same view: 233 px vs 218 px along the
   through highway, scaled by stem width (72 px vs 58 px), gives 6 cells for the owner vs 7 for dx 8.
2. hwt accepts exactly that case. Frame dx 7 has a capped twin (21255), and dx 8 (one past) must be empty or the cap
   (`hwt_straight_or_end` -> `hwcap_end`).
3. The release tree has `highway_core` installed. Its `hwyt` proof rule writes a ramp 21100 / 21101 one cell past every
   highway end (owner bugs 1-2, stream hwlone). At dx 8 `hwcap_end` reads that ramp as other highway and returns 0, and
   hwt refuses with reason "through highway". That reason was in hwt_run's do-not-log list, so nothing was logged.

In game, release build (sc3netmod from main 664a685, test tree = Simcity_release copy), turn 0 and turn 1:

| through highway end cap | result |
|---|---|
| dx 6 | no question (footprint: dx 6 of the far carriageway is a T cell without a capped twin) |
| dx 7 (the owner's case) | no question: proof ramp at dx 8 |
| dx 8 | question asked (ramp at dx 9 is outside the checked range) |
| far away (both drag orders, both turns) | question asked |

## Fix
- Cause removed by hwlone (child/hwlone a6ba6e4): the proof rule is opt-in (`SC3NETMOD_HWYT=1`), its ramps are removed
  by the next pass, the load pass included. Nothing to add here for the owner's drag.
- Tried and dropped: reading a proof ramp as no highway in `hwcap_rd`. The T then builds, but in the same pass the ramp
  past the far carriageway's end is reverted, and that revert retile leaves 15149 on through cells dx 3 / 4 and turns
  the near carriageway's dx 7 cap into plain 15051. Worse than the refusal, and moot once the rule is off.
- This stream (sc3netmod_hwt.c, marked task hwtee): `hwt_check` checks where the stem meets the through highway first
  (silent when there is none = a lone highway end), then the stem, then the rest of the through highway. A refusal
  with a through highway present is now logged:
  - `the through highway must run on 2 cells left of the stem (seen from the stem), nothing past its end`
  - `the through highway must run on 6 cells right of the stem (seen from the stem), nothing past its end`
  - `the stem must run straight 4 cells back from the through highway, nothing past its end`
  In each case the last cell may be that highway's end cap, and the cell past it must be empty (a proof ramp there
  gave the same refusal, hence "nothing past its end"). Same decisions as before, only the order and the reason
  text change.

## In-game check (sc3netmod = this worktree + main afca244's sc3netmod_hwy.c, byte-identical to child/hwlone a6ba6e4)
Instance `Simcity_stock_hwtee\re\harness\inst_hwtee`, fresh `lab.sc3` copies, funds 2,000,000.

| case | drags | log / cells |
|---|---|---|
| owner's layout, turn 0 | through (44,31)-(61,31), stem (55,18)-(55,29) toward it | no ramps written; `asking for the T at (54,29) turn 0`; Sí -> `full T at anchor (54,30) turn 0 ...: 50 cells written (1 capped)`; (61,30) stock cap 15054.2, (61,31) capped twin 21255.0, far carriageway dx 3 / 4 plain 15051.0, no 15149 |
| owner's layout, turn 1, stem dragged outward | through (131,10)-(131,30), stem (132,24)-(141,24) | asked; Sí -> `full T at anchor (131,23) turn 1 ...: 50 cells written (1 capped)`; (130,30) 21255.1, (131,30) 11237.0 |
| end cap 5 cells right | through (95,92)-(109,92), stem (104,79)-(104,90) | `T at anchor (103,91) turn 0 refused: the through highway must run on 6 cells right of the stem (seen from the stem)`; no other refusal line in the whole run |
| save + reload | `nr_drive.py save` | `save: 104 variant tile(s) written as base`; reload: `hwt ... kept=2, broken=0`, hwy load pass 0 written / 0 reverted |
| old city with ramps: made with the release-like DLL (old hwy.c) | owner's layout as above | 6 ramps written, T refused, saved (`ramp_saved.sc3`, 10 variant tiles) |
| that city loaded with the fix | - | `hwy: load: ... kept by no block -> removed (land), 3x3 retile` x6 (`6 reverted`); cells: stock caps 15053/15054 and 11235/11237 at every end, no ramp left |
| next drag: the stem re-dragged over itself | stem (55,18)-(55,29) | `asking for the T at (54,29) turn 0`; Sí -> `50 cells written (1 capped)`; same cells as the fresh case, no 15149 |

## Open
- A through highway ending 5 or fewer cells right of the stem (or 1 left) gets no T: the trumpet's loop and ramps need
  that length. A mirrored trumpet (loop on the other side) would be a new package. Owner call.
- An old city saved with the proof ramps: the ramps go on load, the load pass never asks (hwask default), so the
  question comes with the next drag that touches the T's area (checked: re-dragging the stem).
- The final reason strings ("nothing past its end") were compiled but not re-run in game; only the text changed.
- Defender quarantined a freshly built `mods_launch.exe` twice in this instance (13:44, 13:55). A copy from a sibling
  instance ran fine.
