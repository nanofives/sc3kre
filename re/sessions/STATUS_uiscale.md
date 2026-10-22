# STATUS uiscale (2026-10-22)

State: FIXED, waiting for the orchestrator to commit. Detail: `verify/uiscale/RESULTS.md`.

- HUD scale Auto is the default (no ini / no scale key = Auto = min(cw/800, ch/600), per present, so start + every
  resize). Preferencias lists Auto first. Old ini scale=0 without ver=2 read as Auto once. Saves write ver=2.
- City cost label drawn at the HUD factor, clear of the pointer (below, or above near the bottom, left of the enlarged
  panel/minimap). HUD tooltips unchanged. Opt-out `SC3RESIZE_COSTLABEL_SCALE=0`.
- stage_lan_release.py: sc3resize.ini in APPS_SKIP (per-PC prefs must not ship).
- No ids taken, no tables or packages changed. Edits only in HUDOPT, HUDSCALE collect / DLGSCALE slot / TIPCURSOR stubs.

Files to commit:
- worktree `Simcity_wt_uiscale` (branch child/uiscale): `re/harness/src/sc3resize.c`, `re/analysis/HUD_SCALE.md`,
  `re/scripts/lan_release/stage_lan_release.py`
- MAIN: `verify/uiscale/RESULTS.md`, `verify/uiscale/owner_shots/*.png` (7), `re/sessions/STATUS_uiscale.md`

Open: drawn pointer size at (CursorBaseSize 32, dpi 240) not measured (clearance 80 assumed, SM_CYCURSOR says 64).
