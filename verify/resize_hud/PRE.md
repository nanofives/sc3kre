# PRE-REGISTRATION — HUD top-strip reflow proof (2026-08-30)

Committed before the hand-test. Owner is the instrument. FIRST INCREMENT of the HUD reflow: the TOP
STRIP only. If it works, extend to the height-keyed side/panel tables.

## What it does

1. **Wrap `FUN_100270e5`** (SIMUI top-strip anchor-table producer, `__thiscall(this, outTable)` `ret 4`):
   capture `this` (=ecx, the HUD window) into `g_hud_top`, run the original, then `rz_hud_reflow(table)`.
2. **`rz_hud_reflow`**: read the tag (native res), get live width via `GetClientRect(g_hwnd)`; if wider
   than native, origin-scale each of the 4 top-strip widgets' X by live/native and KEEP its width
   (extend, keep size). Y and the label group untouched. No-op at/below native (construction safe).
3. **Resize step 12**: if `g_hud_top` captured, drive the guarded destruct+rebuild
   `FUN_100266c1(this)` then `FUN_10024a96(this)` (both `__fastcall(this)`), re-running the wrapped
   producer -> reflowed anchors at the live width. Guard/idempotency verified: teardown runs only if
   built (`vt+0xf0(0x4000)`!=0), keeps `this`, doesn't detach; builder runs only if not-built.

All in memory, no on-disk change. VEH crash logger retained. Viewport steps 1-11 unchanged.

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log `HUD reflow: ... native N -> live M` + `[step 12] HUD rebuild returned` AND after maximizing the top status strip **spreads across the wider window** (widgets keep size, positioned across the width) | **PASS - top-strip reflow works; extend to panels next** |
| Rebuild runs but the top strip looks unchanged (still clustered left) | **PARTIAL** - reflow ran but the look needs tuning (origin-scale vs edge-anchor); iterate the formula |
| `*** VEH FAULT ***` at step 12 / in FUN_100266c1 / FUN_10024a96 | **FAIL** - the destruct+rebuild is not safe as sequenced; the log localizes it |
| Top strip widgets overlap, vanish, or are misplaced | **FAIL** - the field mapping or reflow math is off; report what moved where |
| HUD strip gone entirely after resize | **FAIL** - teardown detached / rebuild didn't re-register; report |
| Crash / hang | **FAIL** - restore, report last RZ line + any VEH fault |

**Decisive:** after maximizing, does the top status strip use the extra width (widgets spread, sizes
kept) without crashing or vanishing.

## Falsifiability

If step 12 runs clean (no fault) but the strip is unchanged, the producer wrap did not reflow (tag/
GetClientRect path) OR the rebuild read a cached layout - report the `HUD reflow` log line (or its
absence). If widgets misplace, the idx->X mapping (idx 1/3/5/7/9/11/13/15) is wrong for this build.

## Protocol

Harness claimed `handtest`. Owner launches, maximizes, observes the TOP status strip (city name / date /
funds bar) - does it spread across the width. Reports + the log. Prior log archived
`re/harness/sc3resize_handtest.viewportfinal.log`. Install (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`)
verified before/after; no on-disk change.

## STATUS

Built + string-verified (`FUN_100270e5 wrapped`, `HUD reflow: tag native`, `step 12] HUD rebuild`,
`done (all 12 steps)`; PE32; install intact). Producer ret 4 + builder/destructor conventions +
destruct/rebuild idempotency all confirmed from the decomp. Pre-registered. Awaiting the owner hand-test.
