# memleak: 1024 address-space exhaustion (owner crash 2026-10-29) - RESULTS

Child `memleak`, LIVING-PC, tree `dev\memleak\tree` (base = release sc3mods-2026-10-29c), city "Big One latest.sc3"
(the owner's 1024 autosave from the crashed session), the owner's perf.ini / sc3resize.ini / bigcity.ini (size 1024),
window 2540x1331 (the owner's client). Memory from sc3perf's CSV (va_used / private / largest free block) or, where
sc3perf was off, VirtualQueryEx from outside. All input posted (sc3io keys, resize_client); no real mouse.

## Verdict

**The leak is sc3resize's view resize.** It runs on every window size change and on every CITYZOOM x1/x2/x3 step,
and it left two things behind each time:

1. **SURFFREE** - the old DirectDraw surfaces. `rz_recreate_raster` clears the raster's +0x08 byte and calls
   FUN_10009efb again; its vt+0x1dc FUN_1001420d does `this+0x44 = operator_new(0x100)` over the old raster with no
   release [CONFIRMED @ GZGraphicD 0x10009efb, 0x1001420d]. The game's release is vt+0x1e8 FUN_10014410 (+0x48 and
   +0x44: vt+4, then the deleting destructor) [CONFIRMED @ 0x10014410], and nothing called it. VirtualQuery census of a
   leaking game: 59 private blocks of exactly 6,803,456 B (2540 x (1331+8 slack) x 2), 20 of 6,041,600 B (2400 x 1258 x 2),
   11 of 1,732,608 B (the x2 view). With the fix: 1 block of that size.
2. **RESHOWONCE** - sprite art. Resize step 8c runs HIDE (FUN_10006c67) + SHOW (FUN_10006efc) on every occupied cell
   of the whole grid (1,046,814 cells on Big One). A two-phase heap trace (allocations made during 3 x1/x2 round trips
   still alive after 3 more) put 22 MB on SIMSPR 0x1001dd14 < FUN_10012d91 < FUN_10012b98 (the art cache get, which
   decodes on a miss) < FUN_100015a8 (drawable vt+0x34 = FUN_10001592), reached from this pass: ~3.5 MB per resize or
   CITYZOOM step. Two narrower variants did not help (only cells loaded at the current zoom: all of them are; vt+0x34
   then vt+0x38 so no cache count reaches 0: same growth), so the mechanism inside the art cache is not pinned down
   [UNCERTAIN: which holder keeps the re-decoded art alive]. What is confirmed: with step 8c off the cycles are flat,
   and the game's own view transition FUN_100071a3 skips this loop when rotation and zoom group are unchanged
   [CONFIRMED @ SIMSPR 0x100071a3], which is always the case in a resize. Frame dumps after x2 / x1 steps and a
   2400x1250 -> 2540x1331 resize drew the same view with and without it (owner_shots/). The fix keeps step 8c for the
   first layout of each city view (the case it was added for, 2026-08-29) and skips it on later resizes and steps.

The game's own zoom 4 <-> 3 (all mods, 2540x1331) does not leak: 238 -> 239 MB over 10 cycles (the loop above is
skipped there). Neither do the sim, traffic or the building tools (below).

## Measurements

### Ruled out (flat or bounded)
| run | what | private MB |
|---|---|---|
| base_all | all mods, sim at top speed, 12 min, 4,131 days, camera tour 5 min | 261 -> 282 |
| run_all | 40 road + bulldoze cycles (80 applies), sim running | 291 -> 291 |
| paused_all | 40 road + bulldoze cycles, sim paused (sc3undo journals) | 292 -> 298 (first 5 cycles, then flat) |
| paused tools | 15 cycles each: zone/dezone, raise/lower, raise/level, highway/bulldoze (153 applies) | 298 -> 298 |
| e8_all_big | game zoom 4/3/4 x10, all mods, 2540x1331 | 238 -> 239 |
| sc3perf MT_LOCKS | worker free lists after 52k routed trips | 16 chunks, 0.1 MB |

### The leak, release behaviour (paused, nothing else changing)
| run | cycles | private MB | largest free MB |
|---|---|---|---|
| held session, release build | 10 zoom x1/x2 round trips | 342 -> 621 (+28 per cycle) | 739 -> 462 |
| held session, release build | 10 window resizes 2540x1331 <-> 2400x1250 | 638 -> 1013 (+37 per cycle) | 448 -> 169 |
| paused_nofix (SURFFREE=0) | 10 zoom + 10 resize round trips | 274 -> 525 -> 816 | 766 -> 254 |
| paused_fix (SURFFREE only) | same | 238 -> 299 -> 417 | 793 -> 619 |
| paused_fix_noreshow (step 8c off) | same | 225 -> 225 -> 283 | 815 -> 783 |
| h1_final (SURFFREE + RESHOWONCE, the defaults) | same | 227 -> 227 -> 286 | 814 -> 792 |

h1_final, resize part: +26 on the first round trip (the 2400x1250 buffers appear once), then +8, +6, +3, +4, +4, +4,
+2, +1, +1 MB. The zoom part is flat to the MB.

### 15 min soak, sim at top speed, each minute 1 resize pair + 1 zoom round trip
| arm | private MB min 1 -> 15 | largest free MB |
|---|---|---|
| SURFFREE=0 (release behaviour) | 348 -> 1140 (~57 MB/min) | 701 -> 125 |
| SURFFREE only | 297 -> 553 (~18 MB/min) | 738 -> 481 |
| SURFFREE + RESHOWONCE (defaults) | 281 -> 325 (~3 MB/min, ~1.5 MB/min in the last 5 min) | 770 -> 731 |

Same city, same workload, same 15 minutes: the release build ends at 1,140 MB private with a 125 MB largest free
block, the fixed build at 325 MB with 731 MB. The sim alone on this city (base_all) grew 21 MB in 12 min.

The owner's session (MARIANO-PC, 72 min, 4,328 s): private 107 -> 1,405 MB, largest free 1,134 -> 6 MB. Their logs
show 8 CITYZOOM x1 -> x2 steps in the first 49 min (each followed by +10..32 MB) and window resize lines
(PARENT, correlation 0.76 with growth per minute); sim days 0.45, tool applies 0.23.

## Stale-pointer check (orchestrator ask: anything still holding the released raster)
- Code audit of sc3resize.c, sc3resize_ntext.c, sc3perf.c: every read of a raster's bits (+0xf0/+0xf4) is into a local,
  re-read at each use. The persistent copies are g_cz_surf / g_cz_devsurf (CITYZOOM Blt identity checks: SURFFREE
  clears them before the release, the resize re-reads them after), g_czp_frame (DEFER only, and rz_do_resize turns DEFER
  off before rebuilding; re-captured from the live frame each frame) and g_nt_lsurf (compared, never dereferenced).
  sc3perf's overlay takes the Blt source at call time and patches only the shared DirectDraw vtable. The startcrash
  device+0xb0 cache holds the SCREEN device's primary (built by vt+0x204), which this path does not release.
- VEH faults: every run log with SURFFREE on (~2,000 releases over 15 sessions, sim running in several) has exactly one
  fault line, the startup 0xC0000096 at SC3U+0x84122 at ~0.2 s that the release build logs too. One extra READ fault
  (trace_fix session) was inside dbghelp during my Frida heap trace's ACCURATE backtrace, not game code; that resize
  finished normally 1.5 s later.
- vd_fix (all fixes, Ver datos open on the crime map, native minimap on as shipped, 2540x1331): 5 window resize round
  trips with the dialog open, 62 SURFFREE releases, 0 faults, game alive at the end, private 245 -> 299 MB (the first
  2400x1250 round trip +28, then 6..9). Dialog map, minimap, city and HUD drew correctly before, during and after
  (owner_shots/verdatos_open_before_2400_after_resizes.png). With the dialog open the posted +/- keys mostly did not reach
  the city view: 2 CITYZOOM steps registered out of 10 asked, no fault on those. Zoom steps with the dialog closed are
  covered above (h1_final, paused cycles).
- Alt+Enter fullscreen was NOT run: tests stay windowed (standing rule), and Alt cannot be posted to the game
  (GetKeyState never sees a posted modifier). Owner check.

## Hardening (built, each with an off switch)
- **sc3autosave MINFREE**: before a save, the largest free address block is measured; under 64 MB the save is skipped
  with a log line (the owner's failed save ran at 62 MB, the ones before at 78 MB and more). `min_free_mb=` in
  autosave.ini, `SC3AUTOSAVE_MINFREE=0` = no check.
- **sc3autosave FAULTFIX**: after a fault inside the game's save (SIMCITY 0x1000429d), the mod leaves the city+0x1a8
  critical section as often as the game thread entered it, lowers city+0x144 back with vt+0x220, closes the progress
  object (FUN_100026a8, swallowed) and clears city+0x1a4, then stops autosaving for the session with a log line.
  `SC3AUTOSAVE_FAULTFIX=0` = old behaviour. Static only: the OOM fault was not forced.
- **sc3resize LOGTAIL**: the 8 MB cap rotates instead of stopping (sc3resize.start.log = first 8 MB, sc3resize.prev.log =
  the 8 MB before the current file). `SC3RESIZE_LOGTAIL=0` = old stop. The owner's log filled with SRCRECT + SIDEKIDS
  lines (~16 per second, all session long): worth quietening separately.
- **sc3resize NULLLOCK**: the crash site GZGraphicD+0x1465D is FUN_10014649 (device vt+0x1c, begin(flags)) reading
  `[this+0x44]` = NULL when flags & 0x7ec; vt+0x20 FUN_1001467e (end) does the same. Same null-raster class as NULLBLIT.
  Both now return 0 (their own "raster refused" path) and go through the NULLBLIT episode log + screen rebuild.
  `SC3RESIZE_NULLLOCK=0` = off. Static only.

## Files to commit (worktree dev\memleak\wt)
- re/harness/src/sc3resize.c (SURFFREE, RESHOWONCE, LOGTAIL, NULLLOCK)
- re/harness/src/sc3autosave.c (MINFREE, FAULTFIX)
- re/harness/src/sc3perf.c (MT_LOCKS pool line once a minute, diagnostic)
MAIN: verify/memleak/RESULTS.md, verify/memleak/runs/*.txt, verify/memleak/*.out, re/sessions/STATUS_memleak.md.
Not to commit: verify/memleak/evidence_mariano_1029/ (owner logs + save), verify/memleak/runs/*.log,
verify/memleak/owner_shots/*.png (game screenshots: never force-add, the repo is public).

## Off switches
`SC3RESIZE_SURFFREE=0`, `SC3RESIZE_RESHOW=1` (every resize, old) / `0` (never), `SC3RESIZE_LOGTAIL=0`,
`SC3RESIZE_NULLLOCK=0`, `SC3AUTOSAVE_MINFREE=0` (or autosave.ini `min_free_mb=0`), `SC3AUTOSAVE_FAULTFIX=0`.

## Not done / owner check
- An owner hand test on MARIANO-PC: play Big One with zoom steps and resizes for an hour, check the corner FPS line's
  "mem" figure stays near its start, and that the view draws right after x2/x3 steps and window resizes.
- x3 (needs a client of 3840 wide or more) was not exercised here; same code path as x2.
- Alt+Enter fullscreen toggle and CITYZOOM steps with Ver datos open (keys do not reach the view): owner check.
- The SRCRECT + SIDEKIDS log lines (~16 per second all session) are what filled the 8 MB log; not changed here.
