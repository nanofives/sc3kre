# rotleak: every view rotation leaks memory (showcase report 2026-11-17) - RESULTS

Child `rotleak`, LIVING-PC, tree `dev\rotleak\tree` (base = staged 2026-11-17b), mods built from main d7d1ddb plus this
branch. City "Berlin, Germany" (256), client 800x600. Rotations are posted clicks on the minimap rotate button (752,567).
Memory is read from outside the process (GetProcessMemoryInfo PrivateUsage, VirtualQueryEx largest free block below
4 GB), so stock arms without sc3perf are measured the same way. The city is paused unless the row says "sim running".
No real mouse or keyboard was used.

## Verdict

**The leak is a stock SIMSPR bug. sc3perf's sprite loader made it about 5x faster.** Fixed in sc3perf block
**SPR_IMGREF** (off: `SC3PERF_SPR_IMGREF=0`, or perf.ini `spr_imgref=0`).

- `cISC3CitySpriteImageMgr::PrepareImage` (SIMSPR 0x10012b98, iface slot 0x38) gets a sprite image from
  `sc3spr_provider_make_bitmap` (0x10012d91, PrepareImage is its only caller). That function returns the provider's new
  image (`sc3spr_make_image_from_record` 0x1001daf5 builds a fresh object every call) already holding one reference,
  which the caller owns. PrepareImage then AddRefs it again at 0x10012bf0 (record kept, image re-made) and at 0x10012c5e
  (new record) [CONFIRMED @ 0x10012b98, disassembly].
- `UnprepareImage` (0x10012cd7) releases the image once when the cache count reaches 0 (0x10012d25) and then zeroes
  record+0xc [CONFIRMED @ 0x10012cd7]. The image keeps one reference and is never destroyed. Neither is its decoded QFS
  pixel buffer, allocated at 0x1001dd0f (return site +0x1dd14, the same site memleak's heap trace found holding 22 MB).
- Measured with Frida, all mods, 8 rotations (`trace1.out`): the AddRef returned **2** on 9,831 of 9,831 re-made images.
  The last Release returned **1** on 8,610 of them; the rest have more holders. **9,407** decoded buffers (95.8 MB) were
  allocated and **0 freed**, against +104 MB private.
- Each rotation (and each zoom) unprepares the old view's art and decodes the new one, so each one leaks. Stock leaks
  2.3 MB per rotation. sc3perf SPRITES (`spr_budget` 40, sleep 1 ms instead of 5.0 / 20 ms) decodes far more in the same
  seconds, so all mods leaked 15.4 MB per rotation. `SC3PERF_SPR_BUDGET=0` alone brings it back to the stock rate.
- Fix: the two AddRefs are jumped over (`eb 05` + 5 nops in place of `mov edx,[eax]; mov ecx,eax; call [edx+4]`). The
  cache adopts make_bitmap's reference, and UnprepareImage's Release destroys the image, which its zeroing of
  record+0xc already assumes. The patch verifies both sites, the bytes around them and both call targets, and touches
  nothing else. Images prepared before it applies (about 50 ms after start, before any city view exists) keep their
  extra reference. No image is ever released one time too many. City unload (`RealShutdown` 0x100123ff calls
  UnprepareImage until each count reaches 0) now frees every image too.

## Measurements

### Bisect (10 rotations per arm unless noted; `bisect1.out`, `bisect2.out`, `stock20.out`, `winonly40.out`, `mods40.out`)
| arm | MB per rotation |
|---|---|
| stock, windowed (loader + sc3winonly.dll), 40 rotations | 2.32 |
| stock, 15 s between rotations | 3.96 |
| all mods (release build), 40 rotations: 180 -> 796 MB, largest free 907 -> 298 MB | **15.40** |
| sc3resize / sc3bigcity / sc3overscroll / sc3simrun / sc3netmod / sc3undo / sc3autosave / sc3landfill / sc3dataview / sc3restore alone | 2.37 .. 2.67 |
| **sc3perf alone** | **12.65** |
| sc3perf, `SC3PERF_SPR_BUDGET=0` | 2.62 |
| sc3perf, `SPR_FOLLOW=0` / `SPR_REFCOUNT=0` / `RES_REFCOUNT_SIMSPR=0` | 12.63 .. 12.78 |

### 100 rotations, paused (`ab100.out`, `runs/*100.txt`)
| arm | private MB | largest free MB | MB per rotation (0-10 / 25-50 / 75-100) |
|---|---|---|---|
| stock (sc3winonly) | 94.5 -> 325.0 | 1043 -> 806 | 2.36 / 2.35 / 2.28 |
| all mods, `SC3PERF_SPR_IMGREF=0` (release behaviour) | 179.6 -> 1612.4 at rotation 93, **crash at 94** | 907 -> **0** | 15.5 |
| **all mods, fixed** | **179.0 -> 247.8** | **899 -> 852** | **0.72 / 0.64 / 0.62** |

The control's crash reproduces the showcase crashes: largest free block 0 MB at rotation 93, then
`SIMSPR+0x50E8A` (WRITE NULL) twice and `SIMSPR+0x1DB83` (READ NULL, inside sc3spr_make_image_from_record): allocations
failing.

### Use after free (orchestrator ask: nothing may still hold a freed image; `trace_fix2.out`)
Fixed build, all mods, sim running, 8 rotations. Every image whose Release returned 0 goes into a dead set. All
142 hookable methods of the image vtable (160 slots, 18 too short to hook) count calls whose `this` is a dead image.
An address leaves the set when msvcrt malloc / calloc / realloc / operator new returns it again, or when it is made into
a new image. **8,615 images destroyed, 0 calls on a destroyed image.** The first version of the watch, without the
re-allocation rule, counted calls from GZGraphicD's create path (QueryInterface 0x1000167c, raster build 0x1001420d)
on objects newly allocated at a freed address. Those stopped once re-allocation was tracked (`trace_fix.out`). The image
record (`cSC3ImageInfo`, returned by `GetImageInfo` 0x10012a7f) never outlives its image pointer: UnprepareImage zeroes
record+0xc in the shipped code, so no reader can reach a destroyed image through the record. A holder that copied the
pointer and reads the object's fields directly, without a method call, would not show in this watch. None showed in the
picture and soak runs below either.

### Functional checks, fixed and control (`runs/fcheck_*.txt`, pictures `owner_shots/sheet_fix.png`, `sheet_nofix.png`)
Sim running, all mods. Steps: 1 rotation, a full turn, zoom out, zoom in, keyboard scroll, minimap jump, rotation,
Ver datos opened plus map views 2 and 5 (with a rotation under the dialog), save (menu command 0x10009002) to a separate
copy of the city, then a second game loads the saved file and rotates. Both arms passed all 13 steps, 0 VEH faults after
the startup 0xC0000096, the save file was written (805,745 bytes) and loaded. The frames of the two arms show the same
buildings, roads, trees and map views. The differences come from the sim moving on (dates, a few lots).

### 15 min soak, sim running (`runs/soak_*.txt`)
Each minute: 6 rotations, 1 zoom out / in round trip, 2 minimap jumps.
| arm | private MB min 0 -> 15 | largest free MB | VEH faults |
|---|---|---|---|
| **fixed** | **189.4 -> 283.7** (90 rotations) | 1078 -> 831 | 0 |
| `SC3PERF_SPR_IMGREF=0` (release behaviour) | 190.3 -> 1,519.7 at minute 11 (66 rotations), **crash in minute 12** | 1078 -> 15 | SIMSPR+0x50E8A WRITE NULL x2, SIMSPR+0x1DB83 READ NULL (708 s) |

Same 15 minutes and workload: the release behaviour gains about 120 MB per minute and dies in minute 12, the same
signature as the 100-rotation control. The fixed build gains about 6 MB per minute (sim running, zooms and jumps
included) and ends with 831 MB largest free block.

## Residual (open)
The fixed build still grows 0.62 .. 0.72 MB per paused rotation, steady across 100, against 2.3 for stock and 15.4
before the fix. Split after 12 rotations (`trace_fix3.out`, `trace_fix4.out`):
- the working set (images prepared at the end): 13.5 .. 13.7 MB, expected;
- 471 .. 793 images that still had more than 3 references when the cache released them, 3.7 .. 6.1 MB of buffers. About
  70 new ones per rotation;
- about 260 destroyed images whose decoded buffer was not freed through msvcrt free / operator delete, 3.3 .. 3.8 MB.
The extra references come through QueryInterface (GZGraphicD FUN_1000167c AddRefs and returns `this+4` for iid
0x487534f, 200,172 calls in 8 rotations), and their Releases go through that second interface, which the tally did not
hook. Which holder keeps those images is not identified [UNCERTAIN: needs the Release side of the +4 interface tallied
per call site].

## Stock control and the fullscreen incident
`sc3dev run -Stock` set `SC3MODS_OFF=1`. The stock exe then runs in exclusive fullscreen: on LIVING-PC it switched the
display to 800x600, and about 3 minutes later it sat as a topmost 3840x2160 popup (style 0x94000000, exstyle 0x8) until
I stopped my PID. The first stock numbers (`stock20.out`, `stock40b.out`) come from that run and are not used above.
`sc3winonly.dll` (re/harness/src, test control, never shipped) makes the stock game windowed with only the byte
patches sc3resize uses for that: GZGraphicD+0x6cdac = 1, the +0x117d6 fullscreen re-force set to nop, FIX16
(16-bit 5-6-5 surface format) and per-monitor DPI v2. Without FIX16 the windowed stock game draws wrong colours. Without
the DPI call the 800x600 client shows as 2000x1500 and posted 800x600 clicks miss the HUD. `sc3dev run -Stock` now loads
only that DLL (built on first use).

## Files
Branch child/rotleak (worktree `dev\rotleak\wt`, commit c4308d9): re/harness/src/sc3perf.c (SPR_IMGREF),
re/harness/src/sc3winonly.c (new), re/scripts/build_mod.ps1 (`-Mod sc3winonly`), re/scripts/sc3dev.ps1 (`run -Stock`).
MAIN: verify/rotleak/{RESULTS.md, rotmem.py, rot_trace.py, fcheck.py, soak.py, *.sh, *.out, runs/*.txt},
re/sessions/STATUS_rotleak.md. Not to commit: owner_shots/, shots/ (game screenshots), runs/*.log.

## Owner check
- A long session that rotates and zooms a lot on a big city (the showcase city or a 1024 city). The corner FPS line's
  "mem" figure should stay near its start.
- 1024 cities were not run here. The code path is the same, and a 1024 city's view holds more art per rotation.
