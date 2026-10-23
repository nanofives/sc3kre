# STATUS uitoggle (child of "SC3: owner bugs 10-23"), 2026-10-23

State: **fixed, checked in game** (milestone 2). Worktree `Simcity_wt_uitoggle`, branch `child/uitoggle`, from `eeb27ce`.

Cause: the hide-UI button (the "_" at the minimap's bottom-right corner) re-triggered sc3resize's "city HUD became
visible" re-layout (written for accept terrain). Every unhide waited the 3000 ms readiness gate with presents held:
180 held presents, 3.09 s frozen picture. HUD scale off gives the same result (178, 3.1 s).

Fix: block UITOGGLE in `sc3resize.c`, off switch `SC3RESIZE_UITOGGLE=0`. No re-layout when the last pass saw the HUD
visible at this size. Immediate layout when the last pass was a resize done while hidden. Accept terrain unchanged.
The skip path also undoes the game's present-list reset (`iso+0x4d0` -> map-area rect), which otherwise halves fps
through HUDFIX's fallback.

Check: case A (same size) no HOLD, 60 fps, 0 fallback frames. Case B (resize while hidden) 1 held present, 19 ms pass.
Orchestrator's checks (same day, second turn): unhide dump served at +4.32 s before the fix vs +0.55 s after. Hide ->
2133x1130 -> unhide and hide -> 5 max/restore -> unhide both lay out at once (1 held present each). Accept terrain still
takes the old path with its 3000 ms gate (181 held, no UITOGGLE line), HUD correct.
Details + pictures: `verify/uitoggle/RESULTS.md`, `MAIN\verify\uitoggle\owner_shots\` (8 PNG frame dumps).

## Files to commit (from the worktree)
- `re/harness/src/sc3resize.c` (UITOGGLE block before `rz_poll`, the trigger call, `rz_ut_pass_done` after `rz_do_resize`, env read)
- `re/analysis/RESIZABLE_WINDOW.md` (one paragraph under "Accept terrain shows the hidden city HUD")
- `verify/uitoggle/RESULTS.md`
- from MAIN: `verify/uitoggle/owner_shots/*.png` (game frames, local only per the publish policy unless the orchestrator decides otherwise)

No ids taken. No game left running (my PIDs 18896, 15696, 18284, 21460 all closed).
