# STATUS popslow (round 2026-11-21, child of "SC3 Simtropolis feedback triage")

## STATE (2026-11-21 13:10): DONE, no game change
Results: `verify/popslow/RESULTS.md` (worktree dev/popslow/wt). Review flyout survey and hold-caller trace done after
the 12:17 reboot. Verdict: the mods cause no slowdown; modal windows pause the sim in stock exactly as with the mods
(same two SimHiddenPause callers per window, traced in both builds). Nothing of mine is running.

## goal
Player (Simtropolis 2026-11-21): "the simulation speed drops when a pop-up menu appears". Measure game days per real
second, frames and UI-thread CPU with common pop-ups closed / open, stock vs mods, Normal vs Auto 2.0x HUD; find the
cause with evidence; fix what the mods cause.

## verdict + deciding RVA
- **Modal windows stop the date completely, in the stock game and with the mods, identically**: Budget, Preferencias
  (and the mods page inside it), Query, the landmark list, the Rewards list. 0 days in every open window, clock held 100%,
  all of it the coordinator UI hold city+0x144 (cISC3City::SimHiddenPause, SIMCITY 0x100058ac, vt+0x21c: +0x144 += 1 and
  clock Pause), and the clock callback skips every fire while the pause count is non-zero (`cmp [esi+0x54],0; jne`
  SIMCITY 0x1000a885). Static example: sc3_ui_query_handle_tile (SIMUI 0x10010c39) calls vt+0x21c at entry and vt+0x220
  at its end with the query dialog's vt+0x2c between; the hold lasts as long as the window is open (measured), so that call
  does not return while the window is open. Paused time is dropped, not replayed (Resume restarts the time base).
- **Non-modal windows do not slow the date** (Reunirse, advisor page, petition, ticker-opened advisor page, flyouts):
  speed 3 (nominal 1.50 days/s) mods 800x600 1.49-1.50 open vs 1.45-1.55 closed, mods 2x 1.50 vs 1.50; stock 1.15-1.50
  (noisier: stock month pass holds the clock 2-9%).
- **Frames**: stock text dialogs cost 49-93 ms of UI-thread CPU per frame (1.3-5.0 frames/s; 3-4 ms/frame closed).
  Mods (shipped perf.ini sysmem=1): 3.6-5.0 ms/frame at 800x600, 9.7-11.6 at 2x (7-9 closed). Mods page at 2x 17.8 ms/frame
  (it holds the date anyway). Agent animation uses elapsed time per tick, capped 250 ms
  (cSC3OccupantManagerAnim::DoAnimationTick SC3U 0x00426140), so low frame rates do not slow cars above ~4 fps.
- Cheetah on 2 cores (stand-in for a weak PC): stock and mods both show long stalls with nothing open (UI thread blocked,
  frames ~0.3/s, clock held 70-100%), too noisy to show a pop-up effect; no consistent direction.
- Hold callers (SimHiddenPause SIMCITY 0x100058ac), identical stock and mods: the window's own call (Budget SIMMISC
  cIGZGameCommand::Execute 0x1000c22f, Preferencias/mods page SIMUI 0x10010a56, Query SIMUI 0x10010c39, landmark/Rewards
  lists SIMUI FUN_10011919) plus the SIMSPR city view cIGZWin::DoMessage 0x10048d7a. No mod takes a hold. Non-modal
  windows (Reunirse, advisor, petition, flyouts, Review flyout windows) take none.
- Dev trap found: dev `inst` has no perf.ini, so sysmem=0 there (Reunirse 5 fps at 800x600 mods). The release ships
  `Apps/perf.ini` with sysmem=1: copy `stage/release/Apps/perf.ini` into `dev/<name>/inst/` to measure the player's config
  (done for popslow).

## built
Nothing in the game yet. Tools (worktree): re/tools/popslow_meter.py (ReadProcessMemory meter: days, clock pause,
coordinator counters, thread CPU), popslow_ab.py (closed/open driver, Frida frame + heartbeat counters, UI tree,
dialog mapping for DLGSCALE, speed post), popslow_run.py (one arm: launch, unpause, resize, affinity, drive, stop own PID),
popslow_table.py (markdown tables), popslow_holdtrace.py (hold/release callers, run in both builds).

## data
verify/popslow/ab/ab.jsonl (all windows), ab_stock_s3_partial.jsonl (first, interrupted stock run), logs
verify/popslow/ab_s3.log, ab_b2.log, ab_stock_s3_partial.log, grabs verify/popslow/ab/*.png (half size).

## blocked on
Nothing.

## files owned
- re/tools/popslow_meter.py, popslow_ab.py, popslow_run.py, popslow_table.py, popslow_holdtrace.py
- verify/popslow/RESULTS.md (the only tracked file there; raw data ab/, holdtrace_*.jsonl, logs stay gitignored)
- re/sessions/STATUS_popslow.md (MAIN)
- dev/popslow/inst/perf.ini (copy of the shipped one; not in git)

## game-harness need
Own tree dev/popslow/tree only, runs through sc3dev run, test slot.

## asks of other sessions
None. Side note: the stock Reunirse list page opened off-client (1296,506) in a fresh stock process after a 1600x1200
mods run (REUNIRSE_POSITION.md: slot storage not traced); measured by moving it with MoveTo vt+0xcc.
