# sc3simrun — pre-registration (2026-10-06)

Mod: `re/harness/src/sc3simrun.c`. One byte, SIMSPR `0x1004401a` `75 12` -> `EB 12`, so the view's scroll
step (`FUN_10043daf`) never takes the coordinator camera hold (`vt+0x21c`, `+0x144`, clock Pause).

## What stage 0 measured (no patch, 3 runs, Europolis, resume posted after load)

- Coordinator suspend depth `+0x140` stays 0 the whole time. It is not what stops the sim on camera moves.
- The clock pause count (clock `+0x54`) goes to 1 for the spans of drag, held right button and arrow scroll,
  and the tick cursor (`+0x4c`) does not advance in those spans.
- Run 3 caller log: every camera hold is `SIMSPR 0x1004402e` (return of the `vt+0x21c` call in
  `FUN_10043daf`), every matching release is `SIMSPR 0x10042b29` (view tick `FUN_10042a95`).
  3 of 3 camera phases. Other holds seen (SIMUI `0x10013f4f`, SC3U `0x1003ba1a`, SIMCITY `0x10003a3d`)
  are all during load, before the first camera input.

## Arms (same fixture, same driver `drive.py`, same phase script)

Phases: idle 8 s, right-drag 8 s (continuous motion), idle 8 s, right button held still 6 s, idle 6 s,
arrow scroll ~8 s, idle 6 s. Trace on (`SC3SIMRUN_TRACE=1`).

| arm | `simrun.ini` | prediction |
|---|---|---|
| A control | `run_while_scrolling=0` | patched=0. At least one `HOLD ret=SIMSPR 0x1004402e` per camera phase. Cursor advance during drag, held and arrows each **0 or 1** (a tick can land at the boundary). |
| B mod | `run_while_scrolling=1` | patched=1. **Zero** holds from `SIMSPR 0x1004402e`. Clock `+0x54` = 0 for every sample inside drag, held and arrows. Cursor advance in each camera phase **>= 50%** of the same-run idle rate for that duration. Camera moved: before/after frames differ. |

## Soak (B only, after A/B)

3 min of continuous right-drag (back and forth) plus 30 s of arrows, sim running. Pass = process alive at
the end, no exception in the log, cursor advanced during the drag, frame shows the city (not black).

## Fail / void rules

- A that does not freeze in a camera phase means the instrument or the fixture changed: void the pair.
- B with any `0x1004402e` hold, or a frozen cursor in a camera phase, is a FAIL.
- A crash in B or the soak is a FAIL, report as such (the stock pause may have been protecting a race).
