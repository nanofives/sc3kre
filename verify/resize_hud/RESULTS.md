# RESULTS — HUD top-strip reflow proof, 2026-08-30

**VERDICT: FAIL. The driven destruct+rebuild breaks the HUD.** Owner: a strip "disappeared when
resized, never came back." Reverted: the HUD wrap + step 12 are gated OFF; the mod is back to the
known-good viewport build. No crash (VEH clean). The reflow MATH and the producer wrap worked; the
**rebuild trigger** is the wrong mechanism.

## What the log showed

- `[step 12] HUD rebuild` ran on every resize, no `*** VEH FAULT ***` (only the benign startup
  `0xC0000096` probe). So destruct+rebuild did not crash.
- **`HUD reflow: tag native 800 -> live N` fired only on ALTERNATE resizes** (1st, 3rd, 5th - lines
  49/106/163) and was **absent** on the 2nd/4th (lines 77/134). The reflow log is emitted from inside
  the producer `FUN_100270e5`, so its absence means the producer did NOT run on those rebuilds - i.e.
  `FUN_10024a96`'s build **guard-returned** (`if (FUN_1006db32(this) != 0) return`, the built-flag
  `vt+0xf0(0x4000)`).
- So the built-flag does NOT cleanly toggle SET->CLEAR across my `FUN_100266c1` (destruct) then
  `FUN_10024a96` (build): the destruct tears the strip down, and on the next resize the build is
  skipped, leaving it torn down. **Strip vanishes and does not return** - exactly the owner report.

## Corrections to assumptions

- **`FUN_100270e5` lays out the BOTTOM toolbar, not the top status strip** (owner: "bottom strip
  disappeared"; `g_hud_top=0x0E44EC50`, producer picked the native-800 table). My "top strip" label was
  wrong; it is the bottom strip's producer.
- The right/side strip was unchanged - expected (height-keyed tables `FUN_1004c3e9`/`FUN_1004cdcd` not
  touched).
- **The destruct+rebuild pair is NOT a clean idempotent re-layout.** Earlier I read the two guards as a
  clean toggle; the run proves otherwise (alternate skips). That reasoning was wrong.

## The fix direction: REPOSITION, not rebuild

Do not tear down and rebuild. Instead, after the producer wrap reflows the anchor table (that part
works), **reposition the EXISTING child widgets in place** - call each child's set-position/set-rect
vtable slot with the reflowed coords. No teardown, no build guard, no vanish risk. Needs (read-only):
- the child widgets' set-position vtable slot (from `FUN_10024a96`'s placement of `this[0x2a..0x2f]`
  via `vt+0xcc`/`vt+0xc8`), and the child<->anchor mapping;
- confirm repositioning updates hit-testing (same stored rects).

Alternatively, find whether a lighter "re-apply layout" method exists on the HUD window vtable that
re-reads the table without a full teardown.

## Status

- Viewport (D-004 + render + zoom + stability) intact and known-good; HUD reflow gated off.
- HUD reflow: first approach (driven destruct+rebuild) FALSIFIED. Next: reposition-in-place, gated on a
  read of the child set-position slot. The producer wrap + reflow math are reusable.
