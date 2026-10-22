# Intermittent startup death at ~0.3 s (item 1 of the sc3undo leftovers, 2026-10-21)

Status: FIXED 2026-10-22 (owner approved): stream onramp dropped every remaining protection restore and pinned modules in sc3perf; 30 of 30 clean starts (verify/onramp/RESULTS.md). The text below is the 2026-10-21 diagnosis.

## Runs that died on 2026-10-20

| run | lifetime | last lines | read |
|---|---|---|---|
| n1 | ~1 s | sc3resize ends at QUERYID (219 ms), sc3undo at "snapshots in" | **fault logged**, below |
| t7 | ~1 s | sc3undo logged `BTN> bar vtable SIMUI+0xa40ec: Init and child-notify wrapped` at 63 ms | the early SIMUI vtable patch, fixed the same day (`verify/undo_mod/RESULTS.md`, found-and-fixed 2) |
| handtest2, 1st try | - | log overwritten by the 2nd try | no evidence |

## n1: a page-protection race between two mods

`verify/undo_mod/n1/resize.log` (sc3resize's VEH logger):

```
[216.165 ms][tid fa4c] RZ *** VEH FAULT *** code=0xC0000005 at sc3bigcity.dll+0x5F59 (base 0x627D0000)
[216.223 ms][tid fa4c] RZ VEH access=WRITE addr=0x0404C155
```

SIMSPR was based at 0x04040000 in that run, so the write target is SIMSPR+0xC155. In the same milliseconds, on
another thread, sc3resize logged its GRIDB_CLAMP hooks at SIMSPR+0xC412 and +0xCFAB, on the same 4 KB page
(0xC000-0xCFFF). The GRIDB_CLAMP loop (`sc3resize.c`, the `VirtualProtect(hook, c->stolen, old, &old)` restore after
each hook) puts the page back to its old protection after writing. If that lands between sc3bigcity's own
VirtualProtect to RWX and its write, the write faults. The same class of crash was fixed once already
(2026-10-09, sc3bigcity+0x5B89 memcpy) by leaving the pages RWX in sc3bigcity and part of sc3resize; about 58 live
restores remain across sc3resize (31), sc3simrun (9), sc3overscroll (8), sc3undo (3) and others.

The benign `0xC0000096 at SC3U.exe+0x84122` is in every run, healthy ones included.

## Loop 1 (re/tools/startup_loop.py)

18 launches, 15 s apart, `verify/undo_mod/roadless.sc3`, the 2026-10-20 bin mod set (resize, bigcity, overscroll,
simrun, startsize, perf, undo): 18 alive at 10 s, 0 died. The race needs two threads to interleave inside a few
microseconds, so a loop of this size is not expected to show it.

## Fix options (not applied)

1. Drop the remaining restores (the 2026-10-09 approach). Denied by the auto-mode classifier on 2026-10-21 as a
   security weakening (code pages stay writable); needs the owner's approval.
2. One per-process lock around every load-time patch in every mod. Keeps protections. Risk: some patches run in
   loader notifications under the loader lock, so a lock holder that calls into the loader can deadlock.

Diagnostics added: `mods_launch.exe` prints `game exited, code = 0x... after N ms`.
