# T3 — simulation-level tiling test — RESULTS (attempt 1)

**VERDICT: VOID.** The pre-registered validity gate failed — the sim did not advance in the
unpaused arm — so no simulation-level conclusion can be drawn. This is the pre-registered
"plausible-but-wrong success" guard (PRE.md outcome 3) firing correctly, not a finding about tiling.
The render-path fence STANDS.

Run 2026-08-27, session `roadtypes`, runner `re/harness/t3_run.ps1`, PRE committed `2822d1b` before
the lease. Fixture Liverpool, England.sc3 (N=192, sha `59bdc7c6`). Install untouched (owner's build);
all game content restored + hash-verified after each arm (`59bdc7c6` fixture, `9926948a` Set.txt).

## What was measured (oracle: `transit_layer.py --sum`, camera-independent)

| arm | rules | sim | surf_live | rail_live | surf_snap |
|---|---|---|---|---|---|
| baseline (pre-run) | stock | — | 621,831 | 2,381 | 410,237 |
| **C** (paused control) | stock | paused | **621,831** | 2,381 | 410,237 |
| **A** (stock) | stock | **unpaused** | **621,831** | 2,381 | 410,237 |
| **B** (`Set.txt`→`{99999}`) | broken road tiling | unpaused | 621,831 | 2,381 | 410,237 |

All three arms reproduce the baseline grids **exactly**.

## Why VOID — the gate failed, with the strongest possible evidence

The gate was `surf_live(A) ≠ surf_live(C)` (the clock-advanced assertion via the oracle). It failed:
`A == C == baseline`. A section-level diff of the decompressed saves is conclusive:

- **`C` (paused) vs `A` (unpaused): 0 of 61 sections differ — the two saves are BYTE-IDENTICAL.**
  If the sim had ticked even once in `A`, its date/RCI/budget/etc. would differ from paused `C`.
  They do not. **The sim clock did not advance in the unpaused arm.**
- `baseline` vs `C`: 14 sections differ — pure load→save nondeterminism (RNG/timestamp/transit stats
  scalars/budget). Present equally in `A` (since A≡C), so not simulation.
- `A` vs `B`: 4 sections differ (network layer `0x2147c2dd` ×2 + two others) — the broken-`Set.txt`
  **load/render-path** effect on what serialises, NOT a simulation effect (the sim did not run).

## Root cause — the unpause posted OK but did not resume the clock

`capture.log`: `### GZMSG: POST {0xC2A35D80,0,0,0} -> POST OK (queued; delivered on pump)`, then speed
`0xC2684065,3`, then a 90 s wait, then Save. **The message was posted and queued** — but the sim did
not resume (A≡C proves it). This is exactly the hazard the preamble names: **a confirmed code path is
not a confirmed cause.** `msg:0xc2a35d80` was game-verified by `bigcities` (suspend-depth `+0x140`
1→0, tick cursor advancing) in ITS context; **it did NOT resume a path-loaded saved city (Liverpool)
here.** Most likely the load applies a suspend depth > 1 (one decrement leaves it paused) or the
path-load coordinator differs from bigcities' case — unproven, `[UNCERTAIN]`, and NOT to be assumed.

**Coordination note (belongs to bigcities, who owns the primitive):** `0xc2a35d80` as a single post
does not unpause a path-loaded save. Consumers must witness the clock, not the POST.

## What attempt 2 needs (before spending another lease)

1. **An INDEPENDENT clock-advanced witness, checked BEFORE the arms** — not the oracle and not
   `GZMSG POST OK`. Options: the probe's `SuspendCnt` fnlog (`-gzlog`) to watch suspend depth reach 0
   after the unpause (⚠️ mind the cave/fnlog hook-address collision), or a decoded/visible sim DATE
   that advances. Post `0xc2a35d80` repeatedly until suspend depth is 0 if the load stacks suspends.
2. **A run long enough for the traffic grids to update** — verify the sim DATE advances by ≥1–2
   sim-months (the live-density grid may only refresh on the monthly pass `FUN_100093e9`). 90 s of
   wall time bought zero sim time here because the clock never started; once it does, re-derive N
   from an observed date delta, not a wall-clock guess.
3. Re-run the same 3-arm design unchanged once the clock is proven to move — the oracle, fixture,
   Set.txt lever and controls are all validated and ready.

## Discipline that held
- The oracle-based gate caught a null unpause that `GZMSG POST OK` would have masked. Without it,
  `B ≈ A` would have been mis-reported as "tiling is render-only." It is not — the sim never ran.
- Install untouched (render-independent oracle); `Set.txt` + fixture restored and hash-verified in a
  `finally`; no `-filetrace` (no startup-race crash); no foreign process killed. Lease released.
- Scratch saves `liv_{A,B,C}.sc3` are modified game content in this (gitignored) dir — deleted after
  the read; never committed.
