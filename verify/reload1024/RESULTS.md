# reload1024 RESULTS (2026-10-23/24)

Owner report: "I retried to load Europolis 1024 for a second time after I loaded it once and the game crashed".
Owner log: `owner_log/` (fault STRTSIM.DLL+0x11908 READ 0x8, ~1 s after the "Cargando" box).
Verdict: **fixed** (sc3perf STRTSIM_REFCOUNT). A second crash, while playing a 1024 city reloaded over a 1024 city
(pre-existing, also on HEAD), is **fixed too** (sc3perf SIMGROUP_REFCOUNT, section 5).

## 1. Cause (found with stacks)

- Fault: the strike-crowd producer (STRTSIM vtable 0x1002c594, Linux name cSSStrikeCrowdProducer) on message
  0x826cb9b6 (OccupantInserted): FUN_10011036 -> std::set<occupant*> insert FUN_10011399 -> FUN_10011861 -> rebalance
  FUN_100118e3. Owner registers: edi = &header->parent = 0x1B82690C, so the set header (0x1B826908) and the new node
  (0x1B826900) overlap.
- STRTSIM's small objects come from its own SGI-style pool: allocate FUN_10002ea6 (free lists STRTSIM+0x32ab0
  [(n+7)>>3], spinlock +0x32af4), deallocate FUN_10002fdd, refill FUN_1000304f [CONFIRMED @ STRTSIM 0x10002ea6,
  0x10002fdd]. Overlapping blocks = a block on the free list twice.
- Frida probe (CModule on the pool + set destructor FUN_1001125c + the producer's Release and dtor), run d5:
  ```
  producer Release refs 1: GZServiceD+0x3c4c < STRTSIM+0x110fc < STRTSIM+0x111cd < STRTSIM+0x144df < SIMCITY+0x6a36
  producer dtor  (inside its own Shutdown)
  producer Release refs 0: STRTSIM+0x144ea < STRTSIM+0x110fc < SIMCITY+0x6a36
  producer dtor  (second time)
  SET DESTROYED TWICE, DOUBLE FREE block n 20 freed twice by STRTSIM+0x11283, 1 pool op apart
  ```
  The layer shutdown (STRTSIM FUN_100142bb) calls the producer's Shutdown (0x144df). The message server's unregister
  (GZServiceD 0x3c4c) released it from 1 to 0 and destroyed it. Then the layer's own Release (0x144ea) destroyed it
  again. Its set header went into the pool twice, two later allocations shared one block, and the next OccupantInserted
  crashed in the pool (STRTSIM+0x2F01, our runs) or in the set rebalance (STRTSIM+0x11908, owner).
- Why the count was one short: the producer's AddRef 0x10010569 (`inc [ecx+0xc]`) and Release 0x100110fc (if-nonzero
  decrement) are not atomic. GZServiceD's dispatch AddRefs and Releases every listener around each message
  (0x1000399b / 0x100039dc), and occupant messages reach the producer from the sim thread and the game thread. A 1024
  city sends hundreds of thousands. Lost updates go both ways: one short = this crash; one over = the producer leaks.
  Measured on HEAD with lifetrace: h1 destroyed it twice (crashed at the load), h3 never destroyed it.

## 2. Fix: sc3perf STRTSIM_REFCOUNT (perf.ini `strtsim_refcount=0` turns it off)

AddRef 0x10010569 and the two Releases of that template (0x100110fc producer, 0x100076a8 the class at vtable
0x1002b0fc = the STRTSIM layer's +0x104 object) are replaced by atomic versions with the same results (an over-release
at 0 still destroys, as the game does). Byte-checked against the shipped STRTSIM, armed at 0.2 s before any city.
Extended (`strtsim_refcount_all=0` off, default on): the same template in all 14 STRTSIM classes that use it (4 AddRefs
0x10010569 / 0x10003310 / 0x10015599 / 0x10021980, 14 Releases, offset and destructor read from each body's bytes).

Owner sequence: start on Europolis 1024, maximized (3840x1984, HUD scale 3.3), speed 4, ~3 min, Load City -> a copy
of Europolis 1024.

| arm | loads | crashed at the load | producer at teardown |
|---|---|---|---|
| before (HEAD logic), a6..d5 + h1..h6 | 18 | 5 (a6, a7, c2, d5, h1) | h1 destroyed twice, h3 never (leak), rest once |
| STRTSIM_REFCOUNT on (e1-6, f1/2/5/7/8/9/13/14, g1-4, k1-3, n1-3) | 24 | **0** | destroyed exactly once in all 16 traced teardowns (e1-6, g1-4, k1-3, n1-3), 0 double frees |
| my DLL with `strtsim_refcount=0` (f10) | 1 | 1 (owner signature, STRTSIM+0x2F01) | |

## 3. Second defect, fixed: worker shadows kept the first city's grid (sc3perf RELOAD, `reload_shadow=0` off)

Berlin (256) -> Europolis 1024 in one game: TRAFFIC_MT shadow layers are built once from the first city's traffic
layer and kept its 256x256 marker grid and iterator. Before: 39,336 of 87,038 background trips faulted (msvcrt memset
in the grid clear, sc3netmod rf_close -> ld_mark), then the game stopped presenting (0 fps).
Fix: `mt_reshape_shadow` gives a shadow the new layer's iterator and a grid of the new size when the layer or its grid
size changes. Final build, one game: Berlin -> 1024, grids 256 -> 1024, 190k trips, 0 faults, 60 fps after 3 min;
then 1024 -> Berlin, grids 1024 -> 256, 357k trips total, 0 faults, 60 fps after 2.5 min.

## 4. Other plain-refcount listeners (report only, not fixed)

`plain_refcount_vtables.txt`: vtables whose AddRef/Release slots use the same plain inc/dec templates (not covered by
sc3perf LAYER_REFCOUNT, whose templates call a stats object). STRTSIM 14 (2 now covered: 0x1002B0FC, 0x1002C594),
SIMDSTR 5, SIMADV 3, SCENARIO 1, SIMGEOM 1, SIMSPR 1. Which of them receive cross-thread messages is not determined;
STRTSIM 0x1002C7C8 is a sim-group member re-added on every city load (grouptrace).

## 5. Crash while playing a 1024 city reloaded over a 1024 city: pre-existing, FIXED (sc3perf SIMGROUP_REFCOUNT)

~25 s after unpausing the reloaded city, the sim thread's registry walk (SIMCITY FUN_10001914) calls a sim group's
Simulate (FUN_1000e93f), which calls vt+0x10 on a "member" whose vtable reads 0x61666544 ("Defa": the mayor name
"Defacto" written into freed memory during the load). The freed "member" was never added through the group's only
add path (FUN_1000e7a7, the only caller of the vector push FUN_1000ebeb): the group itself was freed while still
registered, and its vectors read garbage. The group's base AddRef 0x10010d0d (`inc [ecx+4]`) and if-nonzero Release
0x10010d14 (count 0: vt+0x98(1)) are plain, reached through the adjustor thunks 0x1000e787 / 0x1000e78f. Same race
class as section 1, an `ecx` form of the template that neither LAYER_REFCOUNT nor my first scan matched.

Fix: sc3perf SIMGROUP_REFCOUNT (`simgroup_refcount=0` off) makes both bodies atomic with the same results.

| reload then play 120-240 s, no probe | died |
|---|---|
| HEAD sc3perf (f4, f6, h2, h3, h4, h6) | 1 of 6 |
| my build without SIMGROUP (f1, f2, f7, f9, g1-g4, k1, k2, p1, q1, q2) | 8 of 13 |
| **with SIMGROUP_REFCOUNT (r1-r8)** | **0 of 8** (all 8 loads clean too) |

Ruled out on the way: the producer and the STRTSIM layer's +0x104 object (lifetrace), sc3perf LIST_FIND
(`list_find=0`: q2 still died), the 12 other STRTSIM plain-refcount classes (all made atomic in p1: still died; kept on
as `strtsim_refcount_all`, same race class). Heavier probes masked the crash (Frida on the pool or RtlFreeHeap).

## 6. Report only: more plain-refcount classes, not fixed

`plain_refcount_vtables.txt` (esi form) and `plain_refcount_vtables_ecx.txt` (ecx form, adjustor thunks followed):
about 60 more vtables in 17 DLLs (SIMRCI 8, SIMDSTR 7+5, SIMECO 6, SIMINIT 6, SIMSERV 6 with 0x1001F2C8 already in
SPR_REFCOUNT, SIMGEOM 5+1, SIMUTIL 4, SIMADV 1+3, SIMMISC 3, SCENARIO 3+1, STRTSIM 3 more, SimTransit 2, SIMDIRT 2,
SIMUI 2, AUDIO 1, GZResourceD 1). Which of them are touched from two threads is not determined; the two that crashed
here (STRTSIM producer, SIMCITY sim group) both receive sim-thread and game-thread traffic.

## Pictures (`owner_shots/`)
- `1_europolis1024_reloaded_running_fixed.png`: Europolis 1024 reloaded over itself, 4 min of play, final build (run r8).
- `2_berlin_then_europolis1024_running_fixed.png`: Berlin -> Europolis 1024, 3 min of play (build before SIMGROUP).
- `3_europolis1024_then_berlin_running_fixed.png`: then -> Berlin, 2.5 min of play (build before SIMGROUP).

## How the runs were driven
- Load City lists `MAIN\Cities` (the registered install), not the test tree. The test tree's Cities was reached through
  the dialog's "Buscar en" folder tree (Proyectos -> Simcity_stock_reload1024 -> Cities, double click).
- Probes and drivers: worktree `re/tools/reload1024/` (poolwatch4.py = pool double-free / write-after-free detector,
  lifetrace.py, freetrace.py, grouptrace2.py, prodtrace.py, plainref.py, plainref2.py; cycle.sh / batch.sh / lifebatch.sh /
  postplay.sh carry this PC's maximized click coordinates and scratchpad paths: adjust before reuse).
