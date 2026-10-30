# STATUS memleak (child of "SC3 mods page layout + autosave rotation + load crash")

## goal
Owner crash 2026-10-29 18:04 (MARIANO-PC, release 10-29c, Big One 1024, 2560x1351, 72 min): address space ran out
(private +18 MB/min), an autosave faulted half way and left the city locked, then a resize crashed at
GZGraphicD+0x1465D. Find the leak, fix it with an off switch, harden autosave / log cap / NULLBLIT.

## verdict + deciding RVA
**Cause found: sc3resize leaks the old DirectDraw surfaces on every view resize** (window size change and every
CITYZOOM x1/x2/x3 step). `rz_recreate_raster` clears the raster's +0x08 byte and calls FUN_10009efb again; its
vt+0x1dc FUN_1001420d does `this+0x44 = operator_new(0x100)` over the old raster with no release
[CONFIRMED @ GZGraphicD 0x10009efb, 0x1001420d]. The game's release is vt+0x1e8 FUN_10014410 [CONFIRMED @ 0x10014410].
Measured on LIVING-PC, Big One latest, 2540x1331, owner perf.ini / sc3resize.ini:
- 10 window resizes 2540x1331 <-> 2400x1250: private 638 -> 1013 MB, largest free 448 -> 169 MB.
- 10 zoom x1 <-> x2 round trips: private 342 -> 621 MB.
- VirtualQuery census: 59 blocks of 6,803,456 B (2540 x 1339 x 2), 20 of 6,041,600 B (2400 x 1258 x 2), 11 of 1,732,608 B.
Second, smaller part on the same path: resize step 8c (HIDE+SHOW on all 1,046,814 cells) left ~3.5 MB of re-decoded
sprite art per resize / CITYZOOM step (heap trace: SIMSPR FUN_10012b98 -> FUN_10012d91). The game's own transition
skips that loop when zoom group and rotation are unchanged [CONFIRMED @ SIMSPR 0x100071a3].
Ruled out (flat): sim at top speed 12 min / 4,131 days (+21 MB), camera tour, 80 road/bulldoze applies running and
paused (sc3undo bounded, +6 MB once), zone/terrain/level/highway churn, game zoom 4<->3, sc3perf MT_LOCKS pools (0.1 MB).
**FIXED** (15 min, sim at top speed, 1 resize pair + 1 x1/x2 round trip per minute): release 348 -> 1140 MB private,
largest free 701 -> 125; fixed 281 -> 325, 770 -> 731. verify/memleak/RESULTS.md.

## built (dev\memleak\inst, not released)
- sc3resize SURFFREE: release through vt+0x1e8 before each re-create. `SC3RESIZE_SURFFREE=0` = old behaviour.
- sc3resize RESHOWONCE: step 8c once per city view, skipped on later resizes / zoom steps. `SC3RESIZE_RESHOW=1` = every
  resize (old), `0` = never.
- sc3resize LOGTAIL: the 8 MB cap rotates (sc3resize.start.log + sc3resize.prev.log + sc3resize.log) instead of
  stopping. `SC3RESIZE_LOGTAIL=0` = old stop.
- sc3resize NULLLOCK: device vt+0x1c / +0x20 (FUN_10014649 begin / FUN_1001467e end) return 0 when +0x44 is NULL
  (the 10-29 crash site GZGraphicD+0x1465D). `SC3RESIZE_NULLLOCK=0` (or NULLBLIT=0) = off.
- sc3autosave MINFREE: skip the save when the largest free block < 64 MB (`min_free_mb=` in autosave.ini,
  `SC3AUTOSAVE_MINFREE=0` = off). FAULTFIX: after a fault inside the game's save, leave the city+0x1a8 critical section,
  lower city+0x144 back, close the progress object, then stop autosaving for the session with a log line.
  `SC3AUTOSAVE_FAULTFIX=0` = old behaviour.
- sc3perf: MT_LOCKS pool size logged once a minute (diagnostic only).

## proven game-side vs static only
- Leak, its size and the fix: game-side (A/B soaks and paused cycles, RESULTS.md). View drawing after x2 / x1 steps and
  a resize with step 8c skipped: frame dumps, verify/memleak/owner_shots (not to be committed). x3 not exercised.
- Stale pointers after the release: code audit clean, 0 VEH faults beyond the startup 0xC0000096 in every run, and a
  resize run with Ver datos + minimap open drew correctly (RESULTS "Stale-pointer check"). Alt+Enter not run (windowed rule,
  Alt cannot be posted).
- NULLLOCK, FAULTFIX: static only (disassembly / decompilation); the OOM state was not forced.
- MINFREE, LOGTAIL: built, not exercised past their thresholds.

## blocked on
nothing

## files owned (worktree dev\memleak\wt)
- re/harness/src/sc3resize.c (SURFFREE, RESHOWONCE, LOGTAIL, NULLLOCK blocks)
- re/harness/src/sc3autosave.c (MINFREE, FAULTFIX)
- re/harness/src/sc3perf.c (MT_LOCKS pool log line)
MAIN: re/sessions/STATUS_memleak.md, verify/memleak/RESULTS.md, verify/memleak/runs/*.txt, verify/memleak/*.out.
NOT to commit: verify/memleak/evidence_mariano_1029/* (owner logs + game save), verify/memleak/runs/*.log copies,
verify/memleak/owner_shots/*.png (game screenshots).

## game-harness need
none beyond dev\memleak\tree

## asks of other sessions
A process PID 1104 (another session's SC3U.exe) showed "no se encontró UV.dll" at 18:43 on LIVING-PC; not mine, left alone.
