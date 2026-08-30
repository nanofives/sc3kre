# PRE-REGISTRATION — device present batch around the repaint (step 10 v2)

Committed **before** the hand-test. Owner is the instrument.

## Why

Step-10-alone (`FUN_1000db86` repaint, no device batch) hand-tested FAIL (`verify/resize_pipeline/`).
Two owner observations localized the fix: **rotating does nothing** (refutes the transition/repaint
path), and **only a data/utility overlay toggle and back fixes it**. The distinctive thing that path
does is the **device present batch** at `FUN_1001818c:53-55`:
```
(*(cMapView+0x14)+0x240)()   device begin batch - binds the recreated surface
(*(cMapView+0x18)+0x144)()   iso whole-view repaint = FUN_1000db86
(*(cMapView+0x14)+0x244)()   device end batch - PRESENTS
```
`cMapView = g_bridge`; `device = *(bridge+0x14)` (GZGraphicD device); `iso = *(bridge+0x18)`.

## The change (`re/harness/src/sc3resize.c`, step 10)

Wrap the repaint in the device batch, exactly as the toggle: `device+0x240` (begin), then
`FUN_1000db86(iso)` (by RVA = iso vt+0x144, PE-verified), then `device+0x244` (end/present). The device
`+0x240/+0x244` are called through the **live device vtable** (as the engine does), gated: `device`
readable, its vtable readable to `0x248`. If the device is unavailable it logs
`device batch REFUSED` and does the repaint alone (the prior, known-insufficient behavior). Under the
SEH catcher (`g_rz_step = 10`). Steps 1-9 retained. No on-disk change.

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log `device batch begin` + `device batch end +0x244 - presented` AND after a resize the **whole city renders with NO layer toggle** | **PASS — defects A+B fixed, resize mod complete end-to-end** |
| `device batch REFUSED` (bad device ptr) | **VOID** — `bridge+0x14` is not the device for this build/state; re-derive |
| Batch runs (begin+end logged) but the view is still blank until a toggle | **FAIL** — the batch pair is not the operative part either; the repair is elsewhere in the data-view path (`FUN_100182ba` SetDataView(0) base-view logic beyond the batch). Report; next would be to replicate `FUN_100182ba(mode=0)` |
| `FAULT CAUGHT` at step 10 (code + MODULE+RVA) | **FAIL** — a device slot or the repaint faulted; the log localises it. `+0x240/+0x244` are unverified device-vtable slots, so a fault here means they are not what the toggle uses on this device |
| Whole city renders but flickers once | **PASS with note** — cosmetic |
| Crash / hang | **FAIL** — restore, report last `RZ` line |

**Decisive:** after a resize, with NO layer toggle, does the whole city render.

## Falsifiability

If the batch begin+end both run with no fault and the screen is still blank without a toggle, then the
device present batch is NOT the operative part, and the repair lives deeper in the SetDataView base-view
path (`FUN_100182ba` mode 0, which switches the active renderer `this+0x80`/`this+0x2c` before the
batch). That would be the next build; not another repaint variant.

## Protocol

Harness claimed `handtest`. Owner launches, resizes by hand, reports what renders **before** any layer
control. Prior log archived `re/harness/sc3resize_handtest.step10a.log`. Install (`SIMSPR f5b9f1d9`,
`GZGraphicD acefadf0`) verified before/after; no on-disk change.

## STATUS

Built + string-verified (`device batch begin`/`end`/`REFUSED`, `done (all 10 steps)`; steps 1-9
retained; PE32; install intact). Batch bracket is verbatim `FUN_1001818c:53-55`. Pre-registered.
Awaiting the owner hand-test.


---

## RESULT (2026-08-30) + the real lead

**FAIL.** Step 10 v2 reproduced `FUN_1001818c:53-55` verbatim — log `device batch begin` /
`FUN_1000db86` / `device batch end +0x244 - presented`, `iso+0x32c=1`, **no fault** — and the screen was
still blank until a manual toggle. So the **device present batch is NOT the operative part** either.
Owner also reported **rotating does nothing** (only a data/utility overlay toggle and back fixes it).

Falsified now: 8a/8b (sprite re-register), 8c (tile re-register), step-10-alone (repaint), step-10-v2
(device batch), rotation. Five mechanisms.

**The real lead (from reading `FUN_10018cdf` + `FUN_100182ba` SetDataView):** our **step 7 is calling
`FUN_10018cdf` with the WRONG args**. `FUN_10018cdf(this, layer, rend, rend2, p4, force)` sets
`this+0x28 = layer` (the active layer) unconditionally and gates its full-grid refresh on `bVar7||force`.

- Step 7 (ours): `FUN_10018cdf(bridge, 0, *(bridge+0x78), *(bridge+0xa8), 0, 0)` → **layer = 0** (nulls
  the active layer `bridge+0x28`) and **force = 0** (refresh only if the layer changed).
- SetDataView(0) (the toggle's return-to-base): `FUN_10018cdf(bridge, *(bridge+0x2c), *(bridge+0x80),
  *(bridge+0x80), 0, 1)` → **base layer** (not null), base renderer, and **force = 1**.

So the resize leaves the active layer NULL with no forced refresh; the toggle restores a valid base
layer and forces the repaint. `[CONFIRMED @ SIMSPR 0x10018cdf, 0x100182ba]` for the arg difference;
`[UNCERTAIN]` that fixing it repairs the screen (five prior hypotheses were falsified).

**Next build (`verify/resize_setdataview/`):** add a step that calls the SetDataView(0) core with force —
`FUN_10018cdf(bridge, *(bridge+0x2c), *(bridge+0x80), *(bridge+0x80), 0, 1)` — after step 7, restoring a
valid base layer and forcing the grid refresh. Base renderer is always valid (unlike overlay renderers),
so this is the safe half of the toggle.
