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

---

## FOLLOW-UP (2026-08-30) — reposition path also has NO clean hook; conclusion

Dug the reposition redesign (worker + PE resolution). Findings:
- **Child<->anchor map** (builder `FUN_10024a96`): the 4 data children `this[0x2c/0x2d/0x2e/0x2f]` =
  boxes A/B/D/C. But in the builder they get **only SIZE** set (`vt+0xc`); their **POSITION is set by
  their containers** `this[0x2a]/[0x2b]` via `vt+0x40` at build time. So they cannot be repositioned
  by a simple per-child `vt+0xcc` call - the container owns their placement.
- **The stored absolute anchors** `this[0x50..0x6b]` (A/B/C/D client-coord rects) have **no observed
  runtime reader** - rewriting them repositions nothing.
- **The lighter-relayout candidate `vt+0xc0` = `FUN_1006dcb7` is just a GetRect getter**
  (`[CONFIRMED @ SIMUI 0x1006dcb7]`, 18 bytes: copies `this+0x14..0x20` out). NOT a relayout.
- **No `OnSize`/`Layout`/`Recalc` slot** found in the HUD window vtable (RVA 0xa40dc, Init@+0x34).
- Hit-testing: `FUN_1000c546` is a message router, not the point-in-widget test; the real hit-test
  dispatcher was not located `[UNCERTAIN]`.

**Conclusion: SC3's HUD has no clean runtime re-layout path.** It is built once, per window, at a fixed
resolution, positioning children through container layout with no responsive/relayout machinery. Both
tried approaches fail cleanly:
- destruct+rebuild: breaks the HUD (build guard skips alternate rebuilds -> strip vanishes).
- reposition-in-place: children are positioned via containers, anchors have no runtime reader, no
  relayout method exists.

A full HUD reflow therefore requires **reimplementing the container layout** (reposition each container
and re-run its `vt+0x40` child placement, with per-child edge design + hit-test re-verification) - a
large, uncertain effort, not a hook. The "square->scale" arm additionally needs new/upscaled art.

**Recommendation: bank the completed viewport; treat full HUD reflow as a separate, larger project.**
A cheaper partial that IS feasible if wanted: **dock each HUD window to the resized edges** (move the
whole window via `vt+0xcc`), so the bottom toolbar sits at the bottom and side panels at the sides -
bars are correctly placed but do NOT stretch. Not full reflow, but low-risk.

## Status

- Viewport COMPLETE and known-good; HUD reflow gated off (mod restored).
- HUD reflow: both clean approaches falsified/blocked; no clean hook exists. Documented negative.

---

## DEEP APPROACH - DIAGNOSTIC build (2026-08-30)

Committing to the deep reflow; instrument-first. This build is READ-ONLY: the producer wrap captures the
HUD window `this` (g_hud_top); step 12 logs, after a resize, the HUD own rect, the 6 children
`this[0x2a..0x2f]` (ptr / vtable / candidate own-rect at child+0xe0..0xec / vt+0xcc set-pos target),
and the stored native anchors `this[0x50..0x5f]`. **Moves nothing** - the HUD stays intact. Purpose: map
the real widget structure so attempt 2 repositions the right widgets via vt+0xcc without guessing.
Expected: `[HUDDIAG]` lines in the log; no visual change; no crash. Then design the in-place reposition.
