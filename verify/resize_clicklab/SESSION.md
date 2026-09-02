# SESSION.md — resize/input + HUD layout, 2026-09-01/02

Consolidated record of one session. Six defects closed, all **owner-verified in the running game**;
two open. Everything here was validated as **live memory writes** and is **not yet in `sc3resize.c`** —
see "Bake-in list" at the end, which is the whole point of this file.

## The pattern that explains the whole session

Every defect was the same shape: **a rect that still holds the native 800x600 layout**, on a window
the mod never touched. There is no single "window size" in this engine — a window carries four
independent position/extent representations, and the view carries two more. Fixing one says nothing
about the others.

| field | read by | drives |
|---|---|---|
| `+0x14..+0x20` | `FUN_1004ecd3` (view), `FUN_1004efcd` (SIMUI) | hit testing |
| `+0x80..+0x8c` | `FUN_1006ddbd` via the origin sum | hit testing for SIMUI classes; **absolute** on containers, **parent-local** on children |
| `+0x90` | the generic painter | paint destination |
| `+0x88/+0x8c` on the ROOT | `vt+0xa0`/`vt+0xa4` from `FUN_00443331` | the hover label's placement clamp |
| view `+0xd4..+0xe0` | `FUN_1004947d` per mouse-move | **arms/disarms the right-drag pan** |
| view `+0x178..+0x1c4` | `FUN_10043989` builds them | edge-scroll bands |

## Closed, with evidence

### 1. The relocated HUD is clickable — the headline
Owner hand-test, cluster mode, 2048x1081: tool buttons change the tool, panels open, panels drag
anywhere in the client area. Closes `R-REACHED` → `P-PASS` → `B-CONSUMED` → **action confirmed**. The
ancestor-rect widening already in the mod is what unblocked it. `RESULTS.md`.

### 2. Hover label was clamped to 800x600
Placed at the cursor then clamped into the ROOT window's extent, which was stale.
`root+0x88 = 2048`, `+0x8c = 1081`. Right edge went 798 → 2000, top 582 → 1036 across 51 samples.
`[CONFIRMED @ SC3U 0x00443331, 0x00441d3e, 0x00441d45]`. `TOOLTIP.md`, `ROOTRECT_RESULTS.md`.

### 3. The map took no clicks outside the old viewport
`FUN_1004ecd3` rejects any point outside `this+0x14..+0x20`, stale at `[0 0 800 600]`.
Widened → zoning works outside. Traced per-click: inside → `vt+0xe4` ret=1 and the handler runs;
outside → ret=0 and the handler never runs. `[CONFIRMED @ SIMSPR 0x1004ecd3]`. `MAPCLICK_PRE.md`.

### 4. Right-drag camera pan died outside the old viewport
**A different rect.** `FUN_1004947d` tests every mouse-move against view `+0xd4..+0xe0` and calls
`FUN_1004a37e` → `FUN_10042cfe(this,0,0,0)` when outside, zeroing the drag anchor `+0x1ec/+0x1ee` and
both velocities `+0x1f4/+0x1f8`. Measured stale at **`[0 0 704 544]`** — the native screen minus the
side panel and the bar. Widened → pan works. `[CONFIRMED @ SIMSPR 0x1004947d, 0x1004a37e, 0x10042cfe]`

⚠️ **Order matters: SIMUI RECOMPUTES this rect.** `FUN_10014a5d` takes the root bounds, clips the right
edge by the side panel and the bottom by the bar, and broadcasts `0x624a8241`; `FUN_10048d7a` unpacks
it and calls `FUN_10043989`. Measured live: after the HUD windows were moved, the rect had been
rewritten to `[0 0 1952 1025]` = client − 96 wide − 56 tall. **Write the bounds AFTER the HUD moves,
or expect them clobbered.**

### 5. A widget stranded at the old viewport corner
A 26x26 button in a `SIMUI+0xa4d64` container at `[774 574 800 600]`, hanging off the **root**, not off
the HUD tree the mod walks — which is why the cluster relocation never moved it. Moved to
`[2022 1055 2048 1081]`.

⚠️ Two mistakes worth keeping:
- **Poking `+0x14..+0x20` moved the hit test and left the pixels behind** (owner: "the functionality
  moved, visually the button is still on the original position"). The fix is the framework's own
  `vt+0xc8` SetRect, the path already proven on the bar and side panel.
- **SetRect on a container PROPAGATES to its children.** Calling it again on the child double-moved
  it to `[4044 2110]`. Parent only.

### 6. Bottom-edge HUD alignment
Owner-driven tuning via `re/tools/frida_nudge.py`. Final: bar `[1248 1033 1847 1089]`,
RCI `[1847 1009 1888 1097]`, minimap `[1888 925 2048 1089]`, corner button `[2022 1063 2048 1089]`,
side panel `[1952 489 2048 931]`.

Things learned the hard way here:
- **HUD art is TOP-ANCHORED in its rect.** A rect taller than the art paints the surplus black — my
  72-tall bar produced exactly the "black bar below the bottom bar" the owner then reported. The rect
  must match the art height (56) and be positioned, not stretched.
- **The minimap class refuses to resize.** SetRect with a taller rect returned its own height back
  (asked `[1888 917 2048 1089]`, got `[1888 917 2048 1081]`). Positionable, not resizable.
- **A window vacating a region leaves stale pixels** — two stale lines above the bar, and **magenta**
  (this engine's unpainted colour key) above the minimap. Nothing repaints a region nobody owns.
- I introduced a bug and caught it: the minimap's hit rect drifted 8 px taller than its window rect
  after a failed resize attempt, so clicks would have registered where nothing was drawn. Resynced.

## Open

- ⛔ **Ghost strip on the INCREMENTAL scroll path.** Right-drag pan leaves a stale strip; a minimap
  jump repaints it correctly. So the full repaint is fine and the incremental scroll's repaint region
  is computed from a clipped extent. Strips measure ~96 px on the right and ~56 px at the bottom —
  exactly the native side-panel width and bar height. Static read in flight.
- ⛔ **Edge scroll unchanged.** I widened the band block `+0x178..+0x1c4` to a 2048x1081 geometry
  (margins 48/64, band starts 1984 and 1033) and **predicted edge scroll would improve. It did not.**
  So those fields are not what the edge-scroll check consults, or something recomputes them. My call,
  wrong, recorded.

## Method notes earned this session

- ⛔⛔ **External pixel capture of SC3U is nondiagnostic — third instance.** A GDI `CopyFromScreen`
  grab of this DirectDraw window **does not contain the HUD layer**. Five captures across three runs
  read as "the cluster HUD is not on screen"; the owner refuted it by looking. Same class as the
  `resize_census` surface-fill proxy and the retired `PrintWindow` shot. **Ask the owner or read
  inside the process.**
- **A posted click near a screen edge scrolls the camera**, so region-diffing a synthetic click is
  dominated by the whole frame translating. That voided the automated visual test (`V-AMBIG`).
- **`-EnvVars` under `pwsh -File` embeds quotes and the flags never reach the DLL.** Cost one arm;
  caught only by the `FLAGS>` echo line, which is why that line exists.
- **`Select-Object -First N` on a long-running capture kills the pipeline** before it writes its JSON.
  Lost one trace's raw output (the printed lines survived in the task log).

## Bake-in list — none of this is in the mod yet

All six live only as memory writes in one process. `re/tools/frida_widen.py` already does 1–4 and 5 by
**discovery** (root via `sink+0x38`; the view by `vt+0xe4 == SIMSPR+0x4ecd3`; corner widgets by rect
geometry), which is the logic `sc3resize.c` needs:

1. `root+0x88/+0x8c` = client size.
2. view `+0x1c/+0x20` = client size.
3. view `+0xdc/+0xe0` = client size — **after** the HUD moves.
4. corner widgets: `vt+0xc8` SetRect by `(clientW-800, clientH-600)`, parent only, and keep an
   absolute `+0x80..+0x8c` in step while leaving a parent-local one alone.
5. the bottom-edge offsets from §6.
6. ⚠️ tighten the corner-widget heuristic: it also matched the hover label (`SC3U+0xd3bcc`) parked near
   the old corner. Harmless (the label is repositioned on the next hover) but sloppy.
