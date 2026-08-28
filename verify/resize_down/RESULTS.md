# RESULTS — U-069 downward resize (2026-08-28). PRE git `5ddc2f1`.
# ⚠️ U-069 PREEMPTED — but the SEH catcher finally CAUGHT + LOCATED the intermittent crash.

## The intended U-069 test did NOT run cleanly
The windowed auto-maximize fired first (t+27.3s, before my scripted UP at t+40s), driving a resize to
**2048x1081** — and **step 7 (`FUN_10018cdf`) FAULTED**. The SEH catcher trapped it:

```
RZ *** FAULT CAUGHT *** code=0xC0000005 at SIMSPR.DLL+0xD005 (base 0x03310000) | executing STEP 7
RZ DEFER: resize to 800x600 held - render target has no backing yet (sub=0x0DFC0920) ...
```
The caught fault left the render target without a backing, so the subsequent **down-resize to 800x600
DEFERRED and never ran.** So **`U-069` is still unanswered** — the down path was preempted.

## ⭐ THE PRIZE: the crash is finally CAUGHT and LOCATED (the SEH catcher's whole purpose)
- **`0xC0000005` (access violation)** — a real AV, not a /GS overrun. My int[16384] overflow story is
  now doubly dead (this is an AV, and the census already refuted the count).
- **at `SIMSPR.DLL+0xD005` = `FUN_1000cedb+0x12a`** — the grid-B **type-2** tagger, reached from the
  step-7 `FUN_10018cdf` repaint.
- **Exact instruction (disassembled):** `+0x12a: cmp dword ptr [eax], edx` — the linked-list walk
  comparing `*node == id`. Two instructions earlier `+0x123 test eax,eax / je` proves **`eax` is
  non-null** but points to unreadable memory. **So a grid-B bucket holds a non-null but INVALID node
  pointer** (a stale bucket head `*edi`, or a dangling `node->next` at `+0x130 mov eax,[eax+4]`).

## Mechanism class: a DANGLING grid-B node dereferenced during the repaint (not a size ceiling)
The step-7 repaint (`FUN_10018cdf`) walks the 8x8 bucket grid via `FUN_1000cedb` while the grid is
being torn down/refilled by the resize (`FUN_1000ee29` zeroes it; `FUN_10018cdf`/`fa36` repopulate). A
bucket head or `next` pointing at a **freed node** → AV on the `cmp [eax]`. This is a **lifetime /
ordering hazard**, which explains the NONDETERMINISM directly: whether a stale pointer is live when the
walk hits it depends on interleaving and camera/content state — consistent with clean runs at the same
2048 size in `resize_crashhunt`/`resize_census` and a fault here. **NOT overflow, NOT a fixed size
ceiling.**

`[UNCERTAIN]` the exact stale-pointer source (bucket head vs a specific node's next, and which step
frees it). Closing it needs a runtime read at fault time (the SEH filter could log `eax`, `edi`, the
bucket index, and grid dims before returning) — a cheap next instrument, not a guess.

## Corrected standing
- The v3 crash was NEVER "not a real crash" — it IS a real intermittent AV in the repaint's grid-B
  walk. "Not reproducible under 5 conditions" was true because it is **state-dependent**, not
  size/zoom/timing-determined. Both statements now reconcile: an intermittent dangling-pointer AV.
- The load-readiness gate does NOT fix this (the gate passed here; the fault is post-gate).
- **This is the real open defect of the workstream** now that rendering/fill/extent all work: an
  intermittent dangling-grid-B-node AV in the repaint after a resize.

## Next (one lease) — turn the address into the root cause
Enhance the SEH filter to log, at fault time: `eax` (bad node), `edi`/bucket index, `this+0x384/0x388`
(grid dims), and whether `eax` is within a known heap region. Re-run and force the fault (auto-maximize
at 2048 a few times). That names the stale-pointer source and the step that frees it — then the fix
(ordering, or guard the walk) is specifiable.

## State
No orphan (0 processes). Owner build verified `f5b9f1d9` / `acefadf0`. Mod patches nothing on disk.
Lease + claim released. `U-069` remains OPEN (preempted).
