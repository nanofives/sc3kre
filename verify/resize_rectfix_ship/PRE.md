# PRE-REGISTRATION — U-068 rect-fix SHIPPING as a patched SIMSPR.DLL code cave (committed BEFORE the run)

Owner: resizeship session. Committed to git before the lease (BOARD standing rule — git supplies the
tamper-evident timestamp). Date 2026-08-26. Owner greenlit building #1 (the rect-fix as a shipped patch);
#2 and #3 are NOT built.

## What is being tested — the PATCH, not the harness
The confirmed U-068 fix (`verify/u068_rectpush_test/RESULTS.md`, probe `da6f2080`) pushed `{0,0,w,h}` into
`iso+0x4d0` from the **harness** (phase C, `SC3PROBE_RESIZE_PUSHRECT`). This run tests whether a **patched
`SIMSPR.DLL`, loaded off disk with no injected push**, performs that same push itself, by installing a code
cave inside the iso Init `FUN_10005b42`.

The patch = `pe_patch.py --recipe resize_rectfix` (new, anchored to shipped SIMSPR sha `eec71500…`). Two
same-length overwrites, **independently `--diff`-verified 36 bytes / 5 runs, 512000→512000 (length
preserved)**, output sha `3841214dfcfa9019f186da9a2886a02b9e846aad9e6af22bdf166d52c826b28d`:
- **Cave** at VA `0x1006149a` (37 bytes over `.text` slack that shipped all-zero; end-of-`.text`, RVA
  `0x6149a`, inside `.text`'s RX page based at `0x10061000`): a trampoline that runs Init's original
  `call FUN_1000b70e`, then `push_back {0,0,*(iso+0x5c),*(iso+0x60)}` into `iso+0x4d0` via `FUN_10010586`,
  then returns. 33 of 37 bytes differ (4 coincide with existing zeros).
- **Hook** at VA `0x10005f55`: Init's `call FUN_1000b70e` (`e8 b4 57 00 00`) → `e8 40 b5 05 00` (rel32 to
  the cave). 3 bytes differ.

## The instrument — IDENTICAL to the confirmed run, one variable changed
Same probe `da6f2080`, same env (`SC3PROBE_RESIZE=1 RESIZETO=1280x1024 RESIZEAT=22 U068SURF=1 U068SRC=1
U068SHOT=1 RESIZE_PUSHRECT=1`), same city (Europolis), same switches. **The ONLY change: `Apps\SIMSPR.DLL`
is `shipped + resize_rectfix` instead of stock.** `RESIZE_PUSHRECT=1` is kept only so the run still emits
the three shots, the `U068PUSH> BEFORE` count log, and the shot-B full-present suppression — the harness
phase-C push still fires, but it fires AFTER shot B and after the `BEFORE` log, so neither reflects it.

Why this is a clean single-variable test: on stock SIMSPR the confirmed run logged `U068PUSH> iso+0x4d0
BEFORE … count=0` (Init erased the list, nothing repushed) and **shot B was BLACK**. If the patch works, my
cave repushes during the SAME forced Init, so the SAME `BEFORE` log should read **count=1** and shot B
should render the **city** — before any harness push. Construction stays at count 1 too (the ctor's push at
`FUN_1001c4a1:98` is erased by the later Init, then the cave re-adds one), so shot A is unchanged.

## Outcomes, committed in advance

| `U068PUSH> … BEFORE` count (post-Init, pre-phase-C) | conclusion |
|---|---|
| **count = 1** (stock was 0) | the cave EXECUTED inside the forced Init and `push_back` took — the PATCH drove it off disk, no harness push. Primary mechanism witness. |
| count = 0 | the cave did NOT fire or `push_back` failed → hook/trampoline wrong. The patch is broken; report, do not ship. |
| count ≥ 2 | an unexpected extra push (e.g. a construction rect not erased) → report and investigate; not necessarily fatal. |

| Shot B (post-resize, pre-phase-C-push, full-present suppressed) | conclusion |
|---|---|
| **CITY** (stock was BLACK) | the patched DLL renders the resized view through the game's own per-frame loop, no injected push → **the rect-fix ships**. |
| black | the list was not filled by the patch → cross-check `BEFORE` count; the cave/hook is wrong. |

| Whole run vs the cave executing from past-VirtualSize `.text` | conclusion |
|---|---|
| game runs the full duration and is killed on schedule (no AV) | the cave executes cleanly from the mapped-but-past-VSize `.text` tail — the owner's requested execution witness. |
| AV / crash at or after t+22 (Init/cave time) | the cave FAULTED → the hook or trampoline is wrong (per the owner: a fault indicts the hook, not the cave-page assumption). Report the fault address; do not ship. |

| Shot A (pre-resize control, 1024x768) | |
|---|---|
| Europolis renders in full | instrument sound. |
| black / empty | capture path broken → ABORT, conclude nothing about the patch. |

## VOID conditions
- Shot A not a city frame → capture path unproven → VOID, report only that.
- The run never reaches the resize (no `U068PUSH> BEFORE` line) → instrument mis-armed → VOID.

## Reported whatever happens
The `U068PUSH> BEFORE` count and `iso+0x7c`/`+0x524`; the three BMP verdicts (city vs black) by direct
view, esp. the shot-B flip; whether the run completed without AV; the staged DLL sha on disk. The HUD will
NOT reflow (item 2, `FUN_100270e5`) and this is upward-only (`U-069`) — both expected, not regressions.

## Provenance / config
The measurement DLL is **`shipped + resize_rectfix` ONLY** (isolate the cave; the camera recipes are
deliberately omitted so nothing else perturbs the iso/render path). Stock SIMSPR is restored first, the
resizefix build staged, and **the owner's three-recipe gentle build (`scroll_speed=8 + drag_divisor=4 +
drag_deadzone=2`, `--diff` 8 runs / 9 bytes) is re-staged and verified as the LAST action** (BOARD standing
rule — read it, do not reconstruct). Own game lease (`resizeship`). `-AtSec` under 800 (the `capture.ps1`
15-min lease bug). Probe unchanged (`da6f2080`), so no relink and no harness-claim contention. Probe/DLL
shas recorded in the run log.

## STATUS
Pre-registered, patch BUILT and `--diff`-verified (36 bytes, length preserved). **Not yet run — no lease
taken until this PRE.md is committed.**
