# STATUS costlabel (2026-10-22)

State: FIXED, waiting for the orchestrator to commit.

- Cause: sc3resize HUDSCALE enlarged the city cost label (a floating window) about the bottom-right corner whenever it lay
  inside the native HUD box. Detail: `re/analysis/HUD_SCALE.md` "City cost label pulled up-left", `verify/costlabel/RESULTS.md`.
- Fix: floating windows enlarged only when the game's cursor was on the enlarged HUD AND the rect touches a native HUD
  window (latched per window and rect). Opt-out `SC3RESIZE_HUDSCALE_FLOATALL=1`.
- Class check (orchestrator ask) not added: exe+0xd3bcc is also every HUD tooltip's window. The HUD-touch test is the guard.
- No ids taken. No tables or packages changed.

Files to commit:
- worktree `Simcity_wt_costlabel` (branch child/costlabel): `re/harness/src/sc3resize.c`, `re/analysis/HUD_SCALE.md`
- MAIN: `verify/costlabel/RESULTS.md`, `verify/costlabel/owner_shots/*.png` (10), `re/sessions/STATUS_costlabel.md`
