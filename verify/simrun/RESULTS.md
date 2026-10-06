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
