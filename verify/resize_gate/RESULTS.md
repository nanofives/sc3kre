# RESULTS — load-readiness gate witness (2026-08-28). ⭐ OUTCOME 1: PASS. PRE git `7ba3dbd`.

Early external resize (~t+5s, during load), gate at default 3000 ms, `MINZOOM=0`, dense Europolis.

```
### RESIZE: bridge captured 0x0E1771A0 ...; readiness gate = 3000 ms   (t+5395 ms)
RZ   DEFER: resize to 2048x1152 held - only 735 ms since bridge capture (< 3000). Will retry.  (t+6134)
RZ   size change: client 2048x1152 vs render target 800x600                                    (t+8408)
RZ   extent AFTER: ... -> 2048x1152  dirtygrid=16x12 cell=128x96 (cell sizes plausible)
RZ   ---- done (all 9 steps) ----                                                              (t+8511)
```

**The gate does exactly its job:** the during-load resize attempt at t+6.1s was **deferred** (735 ms
since bridge, under the 3000 ms gate), and the resize **landed on a later poll at t+8.4s** — ~3000 ms
after bridge capture, once ready — completing all 9 steps with **no fault**. Deferring is a no-op retry,
so nothing is lost; the resize still happens.

## What this buys
The mod no longer acts on a resize during the first seconds of city load — the one condition that
correlated (weakly, non-reproducibly) with the v3 crash. It is preventive hygiene: cheap, and it closes
the only plausible-but-unproven crash correlate left. Tunable via `SC3RESIZE_READYMS`; the backing-check
half (`*(R+0x44)+0xf0` nonzero) also defers until the renderer has drawn a frame, independent of the
timer.

## Scope unchanged
On-screen correctness at large sizes is still `D-004`-ambiguous (screenshot not decisive); downward
resize `U-069` untested. The gate does not address those — it addresses *when* the routine fires.

## State
No fault, no orphan. Owner build verified `f5b9f1d9` / `acefadf0`. Mod patches nothing on disk. Lease +
claim released.
