# RESULTS — System-B grid re-show (step 8c), 2026-08-30

**VERDICT: FAIL, and it is a decisive negative.** Step 8c executed completely and correctly and produced
**no visual change** — buildings and roads still require a manual data-layer toggle after a resize.

Pre-registration: `PRE.md`, committed before the run (`24d67ec`). This is the pre-registered outcome
"8c runs (occupied>0, re-shown>0) but buildings/roads still missing until a layer toggle → FAIL — the
per-cell show is not sufficient / not the same as the toggle path; report counts, do not iterate blind."

## What the log proves

```
[step 8c] grid re-show 256x256: 65536 occupied, 65536 re-shown, 0 bad (hide+show +0x38/+0x34 per cell)
---- done (all 9 steps) ----
```

- The grid walk ran over the **entire** 256x256 city: **65536 occupied cells, 65536 re-shown, 0 bad**,
  no `REFUSE`, no `FAULT CAUGHT`. The cell layout, dims, and call args were all correct.
- So `FUN_10006c67` (hide, `+0x38`) then `FUN_10006efc` (show, `+0x34`) were invoked for **every**
  building and road drawable in the city — and nothing appeared on screen.
- STOREDRECT still working, `done (all 9 steps)`, install unchanged (`SIMSPR f5b9f1d9`,
  `GZGraphicD acefadf0`).

## What this decisively falsifies

**The defect is NOT in re-registering the tile drawables.** The drawable `+0x34` show method is called
for every cell and the objects still do not draw — yet the same objects appear after a data-layer
toggle. Therefore the missing ingredient is **downstream of the per-cell show**: in the render /
composite pipeline that `+0x34` feeds, which the data-view toggle resets and a per-cell re-issue does
not. Re-issuing the show over the grid is **not** the toggle's mechanism.

This retires the whole "re-register the drawables" line of attack:
- 8a/8b (sprite grid `iso+0x380` via `FUN_1000c9bd`) — ran clean, no visible fix.
- 8c (tile grid `iso+0x24` via `FUN_10006c67`/`FUN_10006efc`) — ran clean over all 65536 cells, no
  visible fix.

Both drove the exact primitives the engine uses; neither reproduced the toggle. The toggle does
something these do not, and it is not at the drawable-registration layer.

## What the data-layer toggle does that we have NOT reproduced

`FUN_100071a3` (the rotate/zoom transition engine) is reached **only** from `FUN_10006a55` (rotate) and
`FUN_10006752` (zoom) — never from the data view. So the data-view toggle is a **different, cross-DLL
path** (SIMUI/SIMCITY, not in the SIMSPR export). It switches the whole render MODE (3D city ->
flat colour overlay) and back, which plausibly re-composites the full frame or resets a render-target /
pipeline state that a resize leaves stale. That reset — not drawable re-registration — is the actual
repair, and it has not been located.

`[UNCERTAIN]` — the specific downstream pipeline/state the toggle resets is **not identified**. Do not
build another drawable-re-register variant against this; that class is exhausted.

## Status

- **`D-004` remains CONFIRMED** — the resizable window fills the physical monitor (the core deliverable).
- **Defects A + B remain OPEN.** A manual data-layer toggle is a working one-click workaround after each
  resize.
- Two fix hypotheses at the drawable-registration layer are now **falsified** (8a/8b, 8c). The next
  lead is the **render-mode/composite reset** the data-view toggle performs, which requires either the
  cross-DLL data-view handler (SIMUI/SIMCITY) or a test of whether a real rotate/zoom transition
  (`FUN_10006a55`, a heavier path than 8c) also repairs it.

## What was NOT done

No on-disk change. No further blind iteration on drawable re-registration (the pre-registration
forbids it and the result justifies the stop).
