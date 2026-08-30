# PRE-REGISTRATION — restore base view with forced refresh (step 11)

Committed **before** the hand-test. Owner is the instrument.

## Why

Reading `FUN_10018cdf` + `FUN_100182ba` (SetDataView) exposed a **bug in the existing routine**, not a
missing step. `FUN_10018cdf(this, layer, rend, rend2, p4, force)` sets `this+0x28 = layer` (active layer)
unconditionally and gates its full-grid refresh on `bVar7 || force`.

- **Step 7 (ours):** `FUN_10018cdf(bridge, 0, *(bridge+0x78), *(bridge+0xa8), 0, 0)` → layer **0** (nulls
  the active layer) and force **0**.
- **SetDataView(0)** (toggle's return-to-base): `FUN_10018cdf(bridge, *(bridge+0x2c), *(bridge+0x80),
  *(bridge+0x80), 0, 1)` → **base layer**, **base renderer**, force **1**.

So the resize leaves the active layer null with no forced refresh; the toggle restores it. This fits why
every prior fix failed (none restored the active layer): 8a/8b, 8c, step-10 repaint, step-10 device
batch, and rotation are all falsified.

## The change (`re/harness/src/sc3resize.c`, new step 11)

After step 10, add: `FUN_10018cdf(bridge, *(bridge+0x2c), *(bridge+0x80), *(bridge+0x80), 0, 1)` —
SetDataView(0)'s core, bypassing its mode-guard so it runs even though mode is already 0, with force=1.
Base renderer `*(bridge+0x80)` is always valid (unlike overlay renderers). Since step 7 nulled
`bridge+0x28`, `bVar7` here is true → `FUN_100184d9` re-register + the forced grid refresh both run.
Guarded: base layer/renderer readable, else `REFUSE`; under the SEH catcher (`g_rz_step = 11`). Steps
1-10 retained. No on-disk change.

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log `[step 11] ... returned - active layer bridge+0x28 = <non-null base layer>` AND after a resize the **whole city renders with NO layer toggle** | **PASS — defects A+B fixed, resize mod complete end-to-end** |
| Step 11 runs, active layer becomes the base layer, but the screen is still blank until a toggle | **FAIL** — restoring the base layer + forced refresh is still not the toggle's operative effect; the remaining difference is the overlay-enter half (`FUN_1001af3e`/service register) or the SIMCITY controller. Report; the honest next step is to replicate the FULL SetDataView round-trip or ship with the workaround |
| Log `[step 11] REFUSE` (base layer/renderer null) | **VOID** — `bridge+0x2c`/`0x80` are not the base layer/renderer for this state; re-derive |
| `FAULT CAUGHT` at step 11 | **FAIL** — `FUN_10018cdf` faulted with the base args; log localises it |
| Whole city renders but flickers once | **PASS with note** |
| Crash / hang | **FAIL** — restore, report last `RZ` line |

**Decisive:** after a resize, with NO layer toggle, does the whole city render.

## Falsifiability

If step 11 sets `bridge+0x28` to the valid base layer (logged) with no fault and the screen is STILL
blank without a toggle, then restoring the base layer + forced refresh is not sufficient — the operative
effect is in the overlay-enter half or the SIMCITY controller, and the honest options become: (a)
replicate the full `SetDataView(overlay)`+`SetDataView(0)` round-trip (risk: overlay renderer may be
null), or (b) ship D-004 with the documented one-click layer-toggle workaround.

## Protocol

Harness claimed `handtest`. Owner launches, resizes by hand, reports what renders **before** any layer
control. Prior log archived `re/harness/sc3resize_handtest.step10b.log`. Install (`SIMSPR f5b9f1d9`,
`GZGraphicD acefadf0`) verified before/after; no on-disk change.

## STATUS

Built + string-verified (`step 11] FUN_10018cdf`, `SetDataView(0) core`, `done (all 11 steps)`,
`11=baseview`; steps 1-10 retained; PE32; install intact). Arg difference vs SetDataView(0) confirmed
from the decomp. Pre-registered. Awaiting the owner hand-test.
