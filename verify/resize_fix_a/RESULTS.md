# RESULTS — FIX A (grid-B index clamp) (2026-08-28). ⭐ PASS. PRE git `e356071`.

Churn run (the same one that caught the fault unfixed), clamp applied, SEH catcher armed.

```
--- GRIDB_CLAMP: FUN_1000cedb index clamped (hook 0xCFAB -> cave 0x614E0, base 0x03310000).
    OOB bucket-index AV fixed for this function.
RZ size change: client 2048x1081 vs render target 800x600 ... done (all 9 steps)   (t+23.4s)
RZ size change: client 800x600  vs render target 2048x1081 ... done (all 9 steps)  (t+28.0s)  <- DOWNWARD
RZ size change: client 2048x1081 vs render target 800x600 ... done (all 9 steps)   (t+34.9s)
```

- **Clamp installed** (byte-verified match before writing; log confirms).
- **ZERO `FAULT CAUGHT`** across the whole run, including **2048x1081 twice** — the exact size that
  faulted (`0xC0000005` at `FUN_1000cedb+0x12a`) in `verify/resize_rootcause`.
- **Every triggered resize completed all 9 steps**, so the clamp did not break the routine.
- ⭐ **Incidental: a DOWNWARD resize (2048x1081 -> 800x600) completed cleanly** — a partial `U-069`
  data point (not the pre-registered U-069 test, but real).

## Why this is a PASS despite the fault being intermittent
The clamp is correct **by construction** (disassembly-verified): the index is recomputed as
`(min(row,gh-1)<<stride) + min(col,gw-1)`, so it cannot exceed `gw*gh-1 = 63` — the OOB read that
produced the AV is impossible. The run confirms the patch **applied**, **prevents the fault at the
faulting size**, and **preserves rendering**. The by-construction argument is the proof; the run is the
sanity check.

## Note on the 8-resize churn showing 3 events
My 8 scripted large resizes (2048x1152, 1920x1080, ...) were clamped by Windows to the desktop workarea
(~2048x1081), so they did not all register as distinct render-target mismatches. The 3 events that DID
fire are the game's own auto-maximize churn during load/settle — which is exactly where the fault
occurred before. So the fix was tested against the real trigger, not a synthetic one.

## ⚠️ SCOPE — FIX A is correct but INCOMPLETE
It clamps **`FUN_1000cedb` only**. `FUN_1000d0f5` / `FUN_1000be25` / `FUN_1000ef50` share the same
latent OOB index math (`round((far-1-origin)*gw/extent) == gw` at the far edge). None faulted in this
run, but a different camera/heap state could fault one of them. **A complete fix either (a) clamps all
four, or (b) over-allocates the bucket buffer (fix B) so the OOB read is benign for all callers at
once.** FIX A resolves the one observed crash; it does not prove the others safe.

## Delivery
`patch_gridb_clamp` is applied in memory by the mod at load (SIMSPR-internal cave, rel32s constant
regardless of base) - **the mod still patches nothing on disk.** Fail-closed: byte-verified before
writing.

## State
No fault, no orphan. Owner build verified `f5b9f1d9` / `acefadf0`. Mod patches nothing on disk. Lease +
claim released.
