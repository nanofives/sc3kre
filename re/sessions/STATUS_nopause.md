# STATUS nopause (round 2026-11-21, child of the popslow orchestrator)

## STATE (2026-11-21 14:00): DONE, one owner call open (Query)
Results: `verify/nopause/RESULTS.md` (worktree dev/nopause/wt), pictures `verify/nopause/owner_shots/` (MAIN + worktree).
Nothing of mine is running.

## goal
Owner 2026-11-21 "Yes, add a switch": a mods page row, OFF by default, that keeps the simulation running while Budget,
Preferencias (incl. the mods page), Query, the landmark list and the Rewards list are open. Stock exactly when off.

## verdict + deciding RVA
- Built in **sc3simrun** (NOPAUSE block): it already owns the camera SimHiddenPause fix and the trace hook on the same
  city vtable slots (SIMCITY 0x10013260 +0x21c / +0x220, slot addresses 0x1001347c / 0x10013480). Holds skipped by
  return address: Budget SIMMISC 0x1000c294 / 0x1000c301, Preferencias SIMUI 0x10010a84 / 0x10010b85, landmark / Rewards
  lists SIMUI 0x100119c2 / 0x10011ac9, and the city view hold SIMSPR 0x100490ac / 0x10049074 only while one of those is
  counted. All call sites byte-checked at arming.
- Measured speed 3 (nominal 1.50): on 1.46-1.53 days/s with each window open; off and stock 0.00, held 100%.
- **Query left stock (lab switch SC3SIMRUN_NOPAUSE_QUERY=1), owner call:** sc3_ui_query_handle_tile SIMUI 0x10010c39 also
  takes cISC3City::Lock vt+0x234 for the whole window life (Unlock vt+0x238 at its end). Hold skipped + lock kept =
  clock counted 125 days in 20 s while the bar date and population stood still, then caught up on close.
- Checks with the switch on: budget edit across a year end (kept, funds not reverted), landmark + reward placed from the
  lists, mods page row written to sc3mods.ini and read at the next start, Save and reload.
- Found, not changed: sc3perf BUSY sampler `is_retaddr` (sc3perf+0x586E) faults on a stale module range when a module
  unloads during a stall (hit once when a Frida probe detached during a cheetah month pass). Fix suggestion in RESULTS.

## built
- re/harness/src/sc3simrun.c NOPAUSE block, env SC3SIMRUN_NOPAUSE=1/0, simrun.ini [sim] run_under_windows=0, export
  sc3simrun_nopause(out[7]).
- re/harness/src/sc3resize.c MODTOGGLE row "+SC3SIMRUN_NOPAUSE" ("Sin pausa en ventanas" / "No pause in pop-ups"),
  left-column rows 17 px (MT_LEFT_DY) so the page layout below is unchanged.
- re/harness/lang/*.txt key resize.mt_nopause (es/en extracted, fr/de/it/nl/sv merged, sc3lang check clean).

## proven game-side vs static only
Game-side: rates on/off, hold/release pairing, arming byte checks, budget/lists/mods page/save checks, query lock effect.
Static only: that the sim thread waits on the city lock during Query (decomp + the frozen bar date; not traced).

## blocked on
Nothing.

## files owned (worktree dev/nopause/wt)
- re/harness/src/sc3simrun.c, re/harness/src/sc3resize.c
- re/harness/lang/{es,en,fr,de,it,nl,sv}.txt
- re/tools/nopause_probe.py, re/tools/nopause_check.py, re/tools/nopause_unpause.py
- verify/nopause/RESULTS.md (owner_shots/, ab/, check*/ and logs stay gitignored)
- re/sessions/STATUS_nopause.md (MAIN), MAIN verify/nopause/owner_shots/ (pictures, gitignored)
- dev/nopause/inst/perf.ini (copy of the shipped one; not in git)

## game-harness need
Own tree dev/nopause/tree only, sc3dev run, test slot.

## asks of other sessions
- Owner: Query under the switch (keep stock, or also drop the city lock with the risk above).
- Whoever owns sc3perf: `__try` around the reads in `is_retaddr` (BUSY sampler).
- Release: GitHub README mods section needs a line for the new row when this ships.
