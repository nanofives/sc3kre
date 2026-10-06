# sc3simrun: results (2026-10-06)

Pre-registration: `PRE.md` (commit `83ac0f4`). Fixture: `Cities\Europolis.sc3`, resize mod for windowed play,
resume posted once after load, input through `sc3io` (posted messages, no cursor). Rate = sim tick cursor
(clock `+0x4c`) advance per second.

## Verdict: PASS. A freezes in every camera phase, B runs at the idle rate in every camera phase, soak clean.

| phase | A stock: advance (clock paused samples) | B mod: advance (clock paused samples) |
|---|---|---|
| idle 8 s | 4 (0/129) | 4 (0/129) |
| right-drag 8 s | **0** (131/133) | **4** (0/133) |
| idle 8 s | 3 | 4 |
| right button held 6 s | **0** (97/97) | **3** (0/97) |
| idle 6 s | 3 | 3 |
| arrows 8 s | **1** (99/130) | **4** (0/121) |
| idle 6 s | 3 | 13 (see note) |

- A: `patched=0`. One `HOLD ret=SIMSPR 0x1004402e` in each of the 3 camera phases. Prediction met (0, 0, 1).
- B: `patched=1`. **Zero** `0x1004402e` holds. Clock pause 0 in every camera-phase sample. Advance 4, 3, 4,
  all at the ~0.5/s idle rate (prediction was >= 50% of it). Camera moved: 59% of pixels changed
  before → mid-drag, the same as A.

**Soak (B):** 180 s of continuous right-drag + 35 s of arrows. Advance 90 over the drag (0.50/s) and 17 over
the arrows (0.49/s), idle rate 0.51/s. Process alive at the end, no exception, final frame renders the city
normally. In-game date 3/31/2088 → 7/18/2088 with the camera moving the whole time.

## Notes

- B idle 6 s after the held button: one 3 ms hold from `SIMSPR 0x1004359c` (`FUN_10043540`), when the right
  button is released. That is a zoom/rotate-style bracket with its own release (`0x100435ea`). In A the same
  bracket did not log because the scroll hold already owned the `+0x174` flag. Same behaviour in both, momentary.
- B last idle, 13 ticks: cursor jumps of +11 and +6 while the coordinator's `+0x148` path pauses the clock
  (`SIMCITY 0x100059e7` / `0x10005a33`, `vt+0x22c`/`+0x230`). Not the camera path. Stage-0 run 3 shows the
  same `+0x148` bracket with no mod. `[UNCERTAIN]` what drives `+0x148` and why the cursor jumps there. It does
  not affect this verdict.
- Not tested: zoom and rotate (left stock on purpose, they are momentary brackets), edge scrolling in
  fullscreen (same `FUN_10043daf` step as arrows), the other three mods loaded together, owner hand test.

## Hand test follow-up (2026-10-06): date overprint and arrows stopping on mouse move

Owner hand test (all four mods, maximized 2560x1351 on a 125% display) found two defects. Post-hoc A/B, all four
mods, Europolis, speed 3, `run_while_scrolling` 0 (A) vs 1 (B), date field cropped from `sc3io` grabs:

| window | A (mod off) | B (mod on) |
|---|---|---|
| default 1000x750 | clean, frozen while scrolling | clean, keeps changing while scrolling |
| maximized 2560x1351 | **smears, from the camera-still phase on** | **smears, from the camera-still phase on** |

- **Date overprint is not caused by sc3simrun.** It appears with the patch off and with the camera never moved,
  only at the large window. It belongs to the large-window status bar layout (`sc3resize`), or to stock code that
  only shows there. `[UNCERTAIN]` which of the two: a stock-size run without `sc3resize` at a large window is not
  possible, so the next step is to read how the date field is erased.
- **Arrows stopping when the mouse moves: not reproduced with posted input.** Arrows held through the key-state
  spoof plus posted `WM_MOUSEMOVE`: about 70% of pixels change between every pair of frames in both arms, so the
  camera kept moving. A real mouse produces something a posted move does not. Needs an owner run with the mod off
  to tell stock from mod.
