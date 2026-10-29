# STATUS vdradio (child, 2026-10-29)

## goal
Owner report 2026-10-29: "cambiar el mapa de contaminación no funciona cuando está grande la UI". In Ver datos, the pollution
panel's radios (aire / agua / basuras) do not change the map when the HUD is scaled up.

## verdict + deciding RVA
FIXED (VDRADIO block in sc3resize, `SC3RESIZE_VDRADIO=0` off). Full write-up: `verify/vdradio/RESULTS.md`.

Radios use the map view's ShowLayer / HideLayer (SIMUI `0x10043252` / `0x100432ba`), which set the layer wrapper's byte
+0xc (vt `0x100a811c`). The render `0x10043882` / draw `0x10043937` skip a wrapper with +0xc = 0. The VERDATOS twin (a Clone)
came out with every layer shown (measured: native `1 1 0 0`, twin `1 1 1 1`), and `mn_state` ignored the bytes. Fix: copy
the native's shown bytes into the twin's wrappers (paired by the shared inner layer +8) at the clone and on every change,
then redraw the twin at once (no re-clone). VDSCROLL and DLGSCALE are not involved.

## built
`dev/vdradio/inst/sc3resize.dll` (474,112 bytes), clean build, no warnings.

## proven game-side vs static only
- Game-side, Berlin 2560x1351 HUD 2.252x: before = the same stacked map for all radios. VERDATOS-off control = 3 different
  maps. After = the same 3 maps as the control, drawn sharp. Crime panel: unchanged by the fix.
- Europolis 1024: one radio switch = 227 to 235 ms twin redraw (texture 1024). Berlin: 26 to 28 ms.
- Static: the ShowLayer / render / Clone chain above.

## blocked on
Nothing.

## files owned (worktree dev/vdradio/wt)
- `re/harness/src/sc3resize.c` (VDRADIO block, env switches SC3RESIZE_VDRADIO, SC3RESIZE_VDRADIO_DIAG)
- `re/tools/vdradio_lab.py` (repro driver, posted input only)
- `verify/vdradio/RESULTS.md`
- MAIN `re/sessions/STATUS_vdradio.md` (this file)

Not for git: `MAIN\verify\vdradio\owner_shots\` (6 pictures), `MAIN\verify\vdradio\runs\` (logs + strips, frame dumps deleted).

## game-harness need
None now. No game running.

## asks of other sessions
None. Open note for the orchestrator: MININAT (minimap twin) uses the same Clone and is likely to start with every layer shown
too. Not reported, so not changed.
