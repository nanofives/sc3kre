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

---

## DIAGNOSTIC RESULT (2026-08-31) — the runtime model does not match the static analysis

Read-only diagnostic run (maximize, log, no modification). Findings and what they refute:

- `g_hud_top=0x0E2B58C8`, HUD own rect `this+0x14..0x20 = [0,544,599,600]` (bottom band, 800-era coords)
  -> confirms g_hud_top is the BOTTOM toolbar. HUD class vtable = `0x034640EC`.
- 6 children `this[0x2a..0x2f]` present, ALL class vtable `0x02EEE894` = **GZGraphicD+0x1E894**
  (GZGraphicD base this run 0x02ED0000). Their `vt+0xcc` target = `0x02ED9EA2` = **GZGraphicD+0x9EA2** =
  `FUN_10009ea2`, a 9-byte FLAG GETTER (`return *(this+0x34)>>1 & 1`) - **NOT a set-position.**
- Child rect@`+0xe0` = garbage; stored anchors `this+0x50..0x5f` = garbage.

**Three layers of the model are wrong for the actual runtime object:** the children are a GZGraphicD
raster-family class (not the SIMUI widgets `FUN_10024a96`'s source described), `vt+0xcc` is a flag
getter not set-position, and the decoded struct offsets (child rect `+0xe0`, anchors `+0x50`) do not
hold. The worker analyzed `FUN_10024a96`'s SIMUI source, but the objects in memory at `this[0x2a..0x2f]`
are a different class - so every reposition primitive derived from that source is invalid for these
objects.

**Assessment:** the deep HUD reflow is NOT converging. Each attempt/diagnostic reveals the prior model
was wrong at a new layer (guard toggling -> offsets -> class/slot semantics). Making these actual
runtime objects reflow would require re-identifying g_hud_top's true class (vt 0x034640EC) and the
GZGraphicD child class (vt+0x1E894) from scratch - their real geometry fields and a real set-position -
then repositioning + visual iteration, with the "scale" arm still needing art. That is a large,
low-confidence effort on top of an already very long session.

**Recommendation: BANK the completed viewport.** The HUD reflow is documented as attempted (destruct+
rebuild broke it; reposition blocked by a class/offset/slot mismatch) with the exact runtime evidence
for a future, dedicated effort. Mod is at the known-good viewport build (HUD changes are capture+log
only; nothing repositioned; the harmful rebuild stays disabled).

## Final status of this workstream

- Viewport (D-004 + render + zoom + stability): COMPLETE, owner-confirmed, shipped.
- HUD reflow: NOT achieved. Both clean approaches falsified; runtime object class/offsets differ from
  the static analysis (documented). Requires a dedicated re-RE of the live objects.

---

## ATTEMPT 2 - reposition the HUD WINDOW via its own SetRect (2026-08-31)

New angle from the geometry cluster: the HUD window rect is at `this+0x14..0x20`, GetRect = `vt+0xc0`
(`FUN_1006dcb7`), and **`vt+0xc8` = SetRect(x1,y1,x2,y2)** - the wrappers `FUN_1006dc1e/dc45/dc6c/dd0d`
all delegate to it with 4 rect coords. So instead of touching the mismatched child objects, move+widen
the WINDOW itself via its own framework method (no destruct, no child-class assumptions).

Step 12 now (after the read-only diag): if `g_hud_top` is wider-able, call its `vt+0xc8` (live-vtable
dispatch) with `[0, liveH-barH, liveW, liveH]` - dock the bottom toolbar to the bottom and span both
side edges, keeping its height. Before/after rect logged; VEH-guarded. Only the bottom bar (g_hud_top)
for now.

Expected PASS: log `HUD SetRect ... rect now [0,liveH-barH,liveW,liveH]` AND the bottom bar spans the
width without vanishing. If SetRect misbehaves (bar clips/blanks/moves wrong) the before/after rect +
VEH localize it. This is safer than the destruct+rebuild (framework method, no teardown).

---

## ATTEMPT 2 RESULT (2026-08-31) — bar docks + spans, but an FPS cost intrinsic to bar width

**PARTIAL SUCCESS.** Owner: "bottom bar is on the bottom of the screen" - the SetRect approach WORKS
geometrically. Log: `HUD SetRect vt+0xc8=0x033E6776 [0,544,599,600] -> [0,1025,2048,1081]`, rect
persisted, **no crash, no VEH fault**. The real window SetRect is `SIMUI FUN_10026776` (runtime
vt+0xc8; my earlier static vtable base was off by 0x10, now corrected). It sets the rect + repositions
5 internal parts by POSITION only (not size) - `[CONFIRMED @ SIMUI 0x10026776]`.

**Two issues:**
1. **FPS drop** while the bar is full-width. Owner: moving the window to a lower-res monitor makes the
   bar disappear (off-screen) and **the FPS drop stops** - so the cost is the bar's PER-FRAME DRAW
   scaling with width, not the one-shot SetRect. Mechanism `[UNCERTAIN]`: the docked bar (y1025-1081)
   overlaps the animated iso view's bottom, so the iso dirties that strip every frame and the
   2048-wide bar redraws over it each frame; cost scales with width. Diagnosing/fixing needs the bar's
   per-frame paint path (deep render RE).
2. **Did not re-fit on a smaller window** (the widen-only guard left it at 2048 off a smaller screen).
   FIXED this build: the guard now tracks the live client size (re-applies when the rect differs), so
   the bar re-docks to both larger and smaller windows.

## Assessment

The HUD bottom bar CAN be docked + spanned via its own framework SetRect (attempt 2, no teardown, no
crash) - a real "extend to edges" result. But full-width has an **intrinsic per-frame FPS cost** in this
engine (bar redraw scales with width, confirmed by the off-screen->FPS-recovers observation). Removing
it needs deep RE of the bar's paint (why width drives per-frame cost) - a separate optimization effort.

Options: (a) ship the viewport, leave HUD native (no reflow); (b) accept the docked-full-width bar WITH
the FPS cost; (c) deep-dive the bar per-frame paint to remove the FPS cost. The viewport remains the
solid, complete, low-risk deliverable.

---

## FPS FIX HYPOTHESIS (2026-08-31) — stop the iso above the bar

The FPS deep-dive worker TIMED OUT (900s, too broad). Testing the leading hypothesis directly instead,
using code we own (step 9): the per-frame cost is the animated iso view blitting UNDER the docked
2048-wide bar each frame (native res is fine because the iso stops above the bar there; our full-height
iso created the overlap). Fix: step 9 now pushes the iso present rect as `{0,0,w,ht-barH}` when the HUD
bar is captured, so the iso stops above the bar and never blits its region -> the bar is not re-dirtied
each frame. Self-gated on g_hud_top (no capture -> unchanged). barH from the captured bar's height.

Expected PASS: bar spans the bottom AND the FPS drop is gone (iso fills above the bar, bar below, no
black strip between). If a black strip appears or FPS is unchanged, the hypothesis is wrong -> revert
the step-9 change (it is isolated and self-gated).

---

## TIMING BUG FIXED (2026-08-31): wait for SIMUI before installing the wrap

The prior run's bar "didn't move" because SIMUI was not loaded when the watcher did its one-shot
`patch_hud_reflow` check ("HUD: SIMUI.DLL not loaded yet - capture NOT armed"). SIMUI loads later than
SIMSPR/GZGraphicD, and the wrap must be installed before the HUD constructs. Fixed: the watcher now
WAITS for SIMUI (up to ~30 s, 100 ms poll) after arming the resize, then installs the wrap - still well
before the city/HUD build. This re-enables both the bar dock/span (step 12 SetRect) and the FPS fix
(step 9 present-stops-above-bar) in one run. Next hand-test verifies the FPS hypothesis for real.

---

## FPS HYPOTHESIS FALSIFIED (2026-08-31)

Both fired this run (log): `[step 9] iso present stops above bar: ht 1081 -> 1025 (barH 56)` and
`[step 12] HUD SetRect [0,544,599,600] -> [0,1025,2048,1081]`. So the iso now presents into rows
[0,1025] and the bar is at [1025,1081] - they ABUT, no overlap. **FPS STILL DROPS** (owner). Therefore
the per-frame cost is NOT the animated iso re-dirtying the bar; the bar redraws every frame on its own,
cost scaling with width, independent of the iso.

Likely (UNCERTAIN, not read): the bottom TOOLBAR contains a per-frame/per-tick updating element (clock/
date, funds, RCI meters) that invalidates the whole bar each frame; at 2048 wide that full-bar repaint
is 2.5x the native cost -> the drop. Confirming needs the bar's invalidate path (which child dirties the
bar, and its paint) - the render RE that already TIMED OUT once as a broad query; a narrow "what
invalidates the bottom bar each frame" query would be the next attempt.

Reverting the step-9 present-above-bar change (it did not help and slightly shrinks the iso). The
docked full-width bar (step 12 SetRect) is achieved but carries an intrinsic per-frame FPS cost.

## Standing conclusion

- Viewport: COMPLETE, solid, owner-confirmed (the real deliverable).
- HUD bottom bar: CAN be docked + spanned full-width via its own SetRect (attempt 3), but full-width has
  an intrinsic per-frame redraw cost NOT caused by iso overlap (hypothesis falsified). Removing it needs
  deep, uncertain paint/invalidate RE.
