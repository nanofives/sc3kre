# SPEC — HUD/UI reflow + scaling for the resizable-window mod (owner, 2026-08-30)

Owner-confirmed behaviour for the HUD when the window is resized:

- **Aspect-based rule.** The trigger is the window's aspect ratio vs the original:
  - **Near the original aspect (grew ~proportionally / "square"): SCALE** — widgets get bigger.
  - **Elongated (stretched mostly one axis, aspect far from original): EXTEND** — panels/toolbars
    reposition and extend to the new edges, widget SIZE unchanged (no scaling on that axis).
- **Edge-scroll / mouse-scroll region** must sit at the REAL (resized) client edges, not the old
  800/1024 boundary.

Context: the in-city viewport is already complete (D-004, render, zoom, stability). This is the
remaining "row 5" gap - the HUD keeps its 1024x768 top-strip layout with margins at any resolution
>= 801 (SIMUI FUN_100270e5 has no branch above width 800; consumer FUN_10024a96).

Open feasibility questions (worker dig in flight, `verify/resize_ui/`):
- Can SIMUI widgets be SCALED larger at all, or are they fixed-size sprites (scaling => blocky upscale
  or new art)? If scaling is not feasible, the "square => scale" arm needs a fallback.
- Cleanest hook to override HUD layout for an arbitrary WxH (patch FUN_100270e5 to synthesize a table,
  or intercept FUN_10024a96 to rewrite anchors).
- Where the edge-scroll boundary is defined and whether it reads the live client rect.

Plan/design to follow once the dig returns.

---

## FEASIBILITY (worker dig, 2026-08-30 — verified against SIMUI/SIMSPR decomp)

Splits by risk. Three capabilities, three verdicts:

### 1. HUD reflow (reposition/extend to edges) — FEASIBLE
- The HUD is TABLE-DRIVEN by three hardcoded anchor tables, selected by resolution:
  - `SIMUI FUN_100270e5` (top strip, keyed on WIDTH via display `vt+0x90`; >=801 -> the 1024 table).
  - `SIMUI FUN_1004c3e9` and `SIMUI FUN_1004cdcd` (height-keyed siblings via `vt+0x94`).
- Anchors are CONSTANTS copied verbatim - **no arithmetic scaler exists** - so at width 1920 the 1024
  anchors cluster left and the right side is empty (the "margins"). Consumer `FUN_10024a96` turns each
  4 fields (X1,Y1,X2,Y2) into a widget box.
- **Hook:** trampoline the tail of `FUN_100270e5` (the live width is in hand via `vt+0x90`, height via
  `vt+0x94`) and rewrite the odd (X) fields to reflow against the true width before `FUN_10024a96`
  reads them. Must also patch the two height-keyed siblings for a full reflow. A mod must encode each
  anchor's edge-intent (right vs left group) since the table does not tag it.

### 2. HUD scaling (bigger widgets) — PARTIAL / UNCERTAIN
- The layout DOES pass an explicit W×H per widget (`vt+0xc(w,h)`, label `vt+0xb8`), so a bigger BOX is
  expressible. **But whether a bigger box magnifies the sprite or just frames native art is set by the
  widget draw method** (classes `0x100a44cc` / `0x100a42e4`), which the layout does not control.
  `[UNCERTAIN]` - the box sizes exactly match the shipped strip art (e.g. 358x18), so the conservative
  reading is **true "bigger UI" needs new/upscaled art**; the layout alone gives reposition + box
  resize, not free pixel magnification. Needs the widget draw method read to confirm.

### 3. Edge-scroll / mouse-scroll at true edges — FEASIBLE (cleanest)
- The edge band is built by `SIMSPR FUN_10043989` from view bound fields `+0xd8`(l)/`+0xdc`(t)/
  `+0xe0`(r)/`+0xe4`(b) - a DYNAMIC view rect, NOT a hardcoded 800/1024 literal, and no
  GetClientRect/GetCursorPos is in the compare. The game only refreshes it on message `0x624a8241`
  (or `FUN_10044323`), never on our resize - which is exactly why nav worked only in the top-left
  800x600 while the blit filled the window.
- **Fix (self-contained):** on resize, set `view+0xe0 = liveW`, `view+0xe4 = liveH`, `+0xd8=+0xdc=0`
  and call `FUN_10043989(view)`; or post `0x624a8241` with the packed client rect. Re-anchors the 8
  edge hit-rects to the true window edges in one shot.

## Recommended phasing
- **Phase 1 (feasible, clean, high value): edge-scroll at true edges.** Self-contained, one function,
  dynamic fields - also fixes the "input only in top-left 800x600" issue already on record.
- **Phase 2 (feasible, larger): HUD reflow (extend arm).** Reflow the 3 anchor tables against live
  W/H; per-widget edge-intent must be encoded.
- **Phase 3 (uncertain): HUD scaling (square arm).** Gated on reading the widget draw methods
  (`0x100a44cc`/`0x100a42e4`) to learn if boxes magnify art. May require new/upscaled assets.

---

## SCOPE CORRECTION (2026-08-30) — reflow needs a re-layout TRIGGER, not just a table rewrite

Decoded `FUN_100270e5` fully (ends `ret 4`, wrappable; ≥801 branch = the 1024 table; widgets A-D at
idx1-16 as (X1,Y1,X2,Y2), label group idx17-28). BUT the layout producer runs at **UI init**, keyed on
the display **resolution getter** (`vt+0x90`/`+0x94`), **not on a window resize**. The mod runs a fixed
windowed backbuffer and stretches it, so resizing the WINDOW does not change the UI's resolution and the
HUD layout **never re-runs**. Hooking the producer alone would never fire after the initial 800x600
layout.

**A real HUD reflow therefore needs THREE parts:**
1. **Trigger a UI re-layout** after each resize (re-invoke the layout path / broadcast the UI-resize
   the game uses for a mode change) - `[UNCERTAIN]` which message/function; needs a read.
2. **Make the resolution source report the live size** so the layout selects the right numbers
   (the `vt+0x90`/`+0x94` getters, or the object they read).
3. **Reflow the anchors** across all three tables (top strip `FUN_100270e5` + height-keyed
   `FUN_1004c3e9`/`FUN_1004cdcd`), with per-widget edge behaviour, + visual tuning over several
   hand-tests.

This is a multi-part workstream, larger than the viewport fix. The anchor-rewrite (part 3) is ready in
principle (proportional origin-scale keep-width for the elongated/extend arm); parts 1-2 are the gating
unknowns.

**Recommendation:** do the self-contained **edge-scroll at true edges** first (phase 1, feasible now,
fixes the input-only-in-top-left issue), then scope parts 1-2 of the HUD reflow with a focused read
before building. The "square -> scale" arm remains gated on the widget-draw-method read (may need art).
