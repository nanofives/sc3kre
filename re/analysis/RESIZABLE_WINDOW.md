# RESIZABLE_WINDOW.md — consolidated handoff (2026-08-29)

> ✅✅ **SHIPPED 2026-10-06 — owner hand test passed.** Release package `sc3resize_2026-10-06`
> (`verify/resize_release/RESULTS.md`): resizable window, HUD spans, map input everywhere, dialogs
> follow the window, edge scrolling off. No environment needed.
>
> **Current state: §6 (rewritten 2026-10-05) and the last section (2026-09-02 to 2026-09-07).** The
> SHIPPED banner below is history: the HUD is no longer left native, it tracks the window in cluster mode.

Single authoritative summary of the resizable-window / arbitrary-resolution mod for
**SimCity 3000 Unlimited**. Supersedes the scattered `verify/resize_*` records for orientation; those
remain the primary evidence (each has a committed `PRE.md` + `RESULTS.md`).

> ✅ **SHIPPED 2026-08-31 — VIEWPORT, HUD left native.** The mod resizes the in-city view to fill an
> arbitrary window: `D-004` confirmed on a real monitor, city renders with no toggle, zoom in/out
> stable, crash fixed (grid-B clamps + zoom-blit guard rows). Delivered as `sc3resize.dll` +
> `resize_launch.exe`, patching nothing on disk. **The HUD is left NATIVE by design:** it can be docked
> + spanned full-width (`verify/resize_hud`, attempt 3, SIMUI SetRect `vt+0xc8`), but full-width has an
> INTRINSIC per-frame composite cost (engine recomposites the HUD window every frame; not invalidation-
> or overlap-driven - three hypotheses falsified), and true per-widget reflow/scaling hit engine class/
> offset mismatches. HUD reflow is documented with full runtime evidence in `verify/resize_hud/` for a
> future engine-level pass; the shipped build does not install the HUD wrap.

---

## 1. What it does, and how complete it is

Makes the in-city isometric view **re-render correctly after the game window is resized** — the defect
tracked as `U-068` (post-resize the view was black / clipped to 800x600). Delivered as an **injected
DLL** (`sc3resize.dll` + `resize_launch.exe`), patching **nothing on disk**.

**Verified in a headless harness (dense city, Europolis):**
- Renders a **full-window frame at 2048x1152** — render target `iso+0x74` and blit-dest `iso+0x4ec`
  both censused **~100% / full bounding box** (`verify/resize_census`).
- Handles resize **UP and DOWN** — upward to 2048x1152, downward 2048x1081->800x600 and
  1280x1024->800x600, all complete with the frame at the correct extent (`verify/resize_u069_v2`).
- The **crash is root-caused and fixed engine-wide** (see §4).
- **Load-readiness gate** prevents acting mid-city-load (`verify/resize_gate`).

**The one thing NOT verifiable here — `D-004`:** the final DirectDraw **primary flip to a physical
monitor**. The headless harness reconstructs frames from the raster composite; it cannot see the real
present to a screen.

⛔ **HAND-TESTED 2026-08-29 AND IT FAILED.** On a real 2048x1152 display, maximizing left the city drawn
in the **top-left at the pre-resize size**. The routine completed all 9 steps and both surfaces reported
2048x1081, with zero faults — so the failure is in the present, not the render. See §6 and
`verify/resize_handtest/RESULTS.md`.

✅ **FIXED AND RE-TESTED THE SAME DAY — `D-004` IS CONFIRMED.** The stored-RECT write (§8/§8b, delivered
in `verify/resize_storedrect/`) makes the resized view reach the physical monitor and fill the window.
Six writes, zero refusals, five resize cycles, zero faults. §8's causal claim is **confirmed, not
falsified**.

✅✅ **RENDER FIXED 2026-08-30 (step 11) — the whole city renders after a resize with NO manual toggle.**
Root cause: the resize's step 7 called `FUN_10018cdf(bridge, layer=0, ..., force=0)`, which **nulled the
active layer `bridge+0x28`**; nothing downstream could draw. Step 11 replays SetDataView(0)'s core —
`FUN_10018cdf(bridge, *(bridge+0x2c) base layer, *(bridge+0x80) base renderer, .., force=1)` — restoring
the active layer and forcing the grid refresh. Owner-confirmed: terrain, zones, buildings, roads all
render. Defects A and B CLOSED. `verify/resize_setdataview/`.

✅✅ **ZOOM FIXED + STABLE 2026-08-30 — the in-city viewport is COMPLETE end-to-end.** The
zoom-after-resize crash was `GZGraphicD FUN_1000239d` (zoom-scaled 16bpp blit) writing one scanline past
the render target, which is allocated exactly `height` rows. Fix: allocate `RZ_SURFACE_SLACK=8` guard
rows (`rz_recreate_raster`) + tolerate them in the poll settle-check (`rz_poll`, else it churned every
frame -> black + a zoom-out race crash). Owner-confirmed: resize fills the monitor, city renders with no
toggle, zoom in/out renders and does not crash. Localized via the retained VEH crash logger.
`verify/resize_zoomcrash/` + `verify/resize_zoomfix/`.

⏭️ **OPEN (new workstream, the always-known "row 5" gap): the HUD/UI does not reflow** - it keeps the
1024x768 layout with margins. Owner feature request 2026-08-30: extend the UI borders (keep height when
stretched one axis; scale up when the window grows squarely) and match the edge-scroll margin to the new
bounds. Scoped separately; needs SIMUI layout RE.

⛔ **(historical, now FIXED) two rendering defects, root-caused §9:**
- **A. Resize does not repaint the new area.** Black except moving traffic; camera motion restores
  terrain/zones. Cause: the resize never runs the System-B field repaint `FUN_100071a3` for the newly
  exposed region; only scroll triggers it.
- **B. The RESIZE drops buildings and roads** (CORRECTED — not a launch defect; owner: "upon launching
  i can see the game fine, everything breaks when i resize"). Cause: **step 8 calls the leaf
  `FUN_1000fa36` instead of the real object re-register `FUN_1000c9bd`**, skipping the fine-grid clear,
  the tag-2 region pickup, and the draw-key recompute. `patch_windowed`/`FIX16` **exonerated** (live at
  launch, city fine). One root cause, verified against the decomp. Fix options in §9.

Also new: the view now fills the window but **navigation only works in the top-left 800x600**, the
inverse of the pre-fix behaviour. Input picking reads a different size source than the blit. Not
investigated. Full record: `verify/resize_storedrect/RESULTS.md`.

---

## 2. The mechanism — the minimal Init-FREE resize routine (9 steps)

`WM_SIZE` never re-rendered the iso view because the renderer has **no resize entry point** — only the
constructor ever sized the view, and the game's `WM_SIZE` handler republishes the window object's
**stale stored size** (`FUN_100185f5` reads `vt+0x68`, not `lParam`/`GetClientRect`). The fix drives a
resize routine per-frame off a size mismatch, **without calling Init** (Init's `vt+0x10` teardown and
`iso+0x24` realloc are the stale-state sources). Validated over 6 harness runs (`verify/resize_minimal`).

| # | step | key fact |
|---|---|---|
| 1 | extent: `iso+0x5c = iso+0x54 + w`, `iso+0x60 = iso+0x58 + h`, mirror `+0x64..0x70` | ⚠️ WORLD space, **moving origin** — left/top routinely NEGATIVE (measured -848,2924). Absolute w/h gave a negative height -> BLACK |
| 2 | `FUN_100059fb(w,h,&gw,&gh,0)` | the game's own dirty-grid table |
| 3 | `FUN_1000e2c0(iso,gw,gh)` | realloc dirty grid + recompute cell sizes |
| 4 | `FUN_1000ee29(iso,8,8,0)` | grid B is 8x8 at EVERY resolution; **omitting this HANGS `FUN_10018cdf`** |
| 5 | `FUN_10009efb` replay on `iso+0x74` (render target) | +0x08 guard cleared, original 8-arg tuple |
| 6 | `FUN_10009efb` replay on `iso+0x4ec` (device surface) | **measured necessary** — the engine won't |
| 7 | `FUN_10018cdf(bridge,0,b+0x78,b+0xa8,0,0)` | tile-cache refill + repaint (~47 ms) |
| 8 | `FUN_1000fa36(iso,1,0)` | re-register drawables from the persistent `iso+0x3a4`; omitting = terrain only (32 colours vs 463) |
| 9 | present rect: erase+push `{0,0,w,h}` into `iso+0x4d0` (`FUN_1001084b`+`FUN_10010586`) | the DLL does this itself — `resize_rectfix` is Init-gated and does NOT fire here |

**The bridge** (owns the iso view + city) is captured by hooking `FUN_10016eba`; `iso = bridge+0x18`.
The routine runs on the game thread from the per-frame heartbeat hook at `GZGraphicD+0x18c58`.

---

## 3. Delivery

| file | role |
|---|---|
| `re/harness/src/sc3resize.c` | the mod (carve of `sc3probe.c`'s `rz_minimal_resize`, + display patches + clamps + gate) |
| `re/harness/src/resize_launch.c` | launcher/injector (CreateProcess SUSPENDED + CreateRemoteThread(LoadLibraryA)) |
| `re/harness/build_resize.ps1` | 32-bit x86 build (PE32, must match SC3U.exe) |
| `re/harness/bin/sc3resize.dll`, `resize_launch.exe` | built artifacts (gitignored harness) |

**All patches are applied IN MEMORY at load** (the mod changes no file on disk):
- `patch_windowed` (`GZGraphicD+0x6cdac`=1, nop `+0x117d6`) + `patch_surfacefmt` (16bpp cave at
  `+0x19349`) — replicate the harness `-windowed -fix16` the routine was validated under. ⚠️ **These
  were a confound**: v1/v2 launched fullscreen because the DLL lacked them; caught 2026-08-28.
- `patch_gridb_clamp` — the crash fix, §4.
- ⛔ **WndProc subclass — THIS CLAIM WAS FALSE, corrected 2026-08-29.** It said the subclass "makes a
  real `WM_SIZE` publish the true client size (why the on-disk `wmsize_setrect` GZGraphicD patch is
  OPTIONAL under this mod)". **Read the source: `re/harness/src/sc3resize.c:721-731`. `rz_wndproc`
  calls the original proc, `logf`s `lParam`, and returns. It writes nothing.** It is an OBSERVER.
  The same false claim is in the mod's own header comment (`sc3resize.c:44`) and its function comment
  (`:719`). The log line `RZ WM_SIZE 2048x1081` is the message parameter being echoed, not evidence
  that anything in the engine learned the new size.
  ✅ **NOW TRUE, as of the same day.** `rz_set_stored_rect` was added (`verify/resize_storedrect/`,
  pre-registered `a85a7f2`): on `WM_SIZE` it reads the window object from the global
  `GZGraphicD+0x6cdb8` and writes `win+0x40 = win+0x38 + w`, `win+0x44 = win+0x3c + h`, behind an
  expect-or-refuse vftable check (`*(DWORD *)win == gz_base + 0x1f740`). Six writes, zero refusals,
  hand-witnessed. So `wmsize_setrect` **is** optional again — but for the first time that is a
  measured statement rather than an assumed one.

Env knobs (set before launch; loader inherits): `SC3RESIZE_LOG`, `SC3RESIZE_READYMS` (gate ms, default
3000), `SC3RESIZE_MINZOOM`, `SC3RESIZE_CENSUS` (dev/witness only).

---

## 4. The crash — root cause + fix (the biggest single thread of work)

**Symptom:** intermittent crash on resize at large sizes (`0xC000041D` / `0xC0000005`).

**Root cause (`verify/resize_rootcause`):** an **out-of-bounds grid-B bucket index**. The 8x8 bucket
grid has 64 entries; the far-edge cell computes `index = round((far-1-origin)*8/extent)` which **rounds
up to 8** (== grid dim) at the far edge, so `bucket[row*8+col]` reaches index 64..71, reading past the
array. `cmp [eax],edx` then dereferences a garbage "node" -> AV. **Latent even at native res**
(`round(799*8/800)=8`); it only crashes when the memory past the array is unreadable, hence
**intermittent / heap-layout-dependent**. (This reconciled "real crash" with "not reproducible under 5
controlled conditions" — `verify/resize_crashhunt`.)

**Fix A — `patch_gridb_clamp` (`verify/resize_fix_a`): all 4 grid-B walkers clamped, engine-wide.**
Each cave recomputes the index with `row=min(row,gh-1)`, `col=min(col,gw-1)` so `index <= gw*gh-1 = 63`
(proven by construction, capstone-verified). Table-driven, fail-closed byte checks, position-independent
(SIMSPR-internal rel32s), in memory.

| function | hook RVA | cave RVA | note |
|---|---|---|---|
| `FUN_1000cedb` | 0xcfab | 0x614e0 | type-2 tagger (the one that faulted) |
| `FUN_1000d0f5` | 0xd281 | 0x61520 | zoom>=3 builder (clone) |
| `FUN_1000be25` | 0xc412 | 0x61560 | zoom<3 builder (clone) |
| `FUN_1000ef50` | 0xef50 | 0x615a0 | type-1 tagger; clamps incoming params on the stack to avoid its ABSOLUTE `cmp [0x10072670]` (relocation-safe) |

Witnessed under a churn of resizes: all four install, **zero faults**, every resize completes.
⛔ Enlarging grid B does NOT work (the round-up scales); alt "fix B" (over-allocate the bucket buffer)
was designed but not needed once all four clamps landed.

---

## 5. Companion on-disk patches (pe_patch recipes, NOT required by the DLL)

Built earlier for a patch-only/hand-test path; kept for reference. Recipes in `re/tools/pe_patch.py`:
- `resize_rectfix` (SIMSPR) — Init-time present-rect push. **Init-gated**, so inert under the Init-free
  DLL routine (this was a real design trap, corrected in `verify/resize_ship`).
- `wmsize_setrect` (GZGraphicD) — makes `WM_SIZE` publish the real client size. Optional under the DLL
  (the subclass does it in C).
- `resizable_frame` + `close_button_quit` (GZGraphicD) — draggable frame + X-quits. In the owner's
  standing GZGraphicD build (`acefadf0`).
- `bridge_stash` (SIMSPR) — pure-DLL bridge-pointer stash (witness tool).

Owner's standing install: `SIMSPR.DLL` `f5b9f1d9` (camera build), `GZGraphicD.dll` `acefadf0`. The DLL
mod works alongside these and needs none of the resize on-disk recipes.

---

## 6. What is DONE vs OPEN (rewritten 2026-10-05; the 2026-08-29 version was stale)

Status as of commit `83d679a` (work through 2026-09-07). Each item cites the commit or `verify/`
record that carries the evidence. "Owner" = confirmed by the owner looking at a real monitor.
HUD items apply to **cluster mode** (`SC3RESIZE_CLUSTER=1`), which the 2026-08-28 package does not
enable by default.

### Done

**Viewport (in-city view)**
- Resize fills the window on a real monitor, up and down. `D-004` confirmed 2026-08-29 by the
  stored-RECT write (§3, `verify/resize_storedrect/`). Owner.
- The whole city renders after a resize with no manual layer toggle (step 11, 2026-08-30,
  `verify/resize_setdataview/`). Owner.
- Zoom in/out after a resize renders and does not crash (8 guard rows, 2026-08-30,
  `verify/resize_zoomfix/`). Owner.
- Grid-B OOB crash fixed engine-wide, all 4 walkers clamped (§4).
- Bottom-strip defect fixed: the final present blitted the 8 guard rows into a client-sized
  destination and squashed the frame. Source clamped to the destination height, `PRESENTFIX`
  (`a90ec5f`). Owner.

**HUD (cluster mode)**
- ✅ **Full-width bar and full-height side panel ON by default** (owner 2026-10-05, `b68bdca` +
  `verify/resize_spandefault/RESULTS.md`). The flip exposed three side-panel defects, all fixed: buttons
  stuck under the minimap at native (`dy <= 0` early return), a duplicate button group when a category
  is open (overlay anchored at the item, not native + dy), and flyout click targets 94 px above their
  icons (sub-tool windows now placed at native + dy). Verified: stock layout at native, identical
  offsets at 1680x979, click on the drawn icon lands on the right tool, back to stock after resizes.
  `=0` on `SC3RESIZE_BARSPAN` / `SC3RESIZE_SIDESPAN` opts out.
- ✅ **Dialogs follow the window** (owner hand test 2026-10-05, `verify/resize_dialogs/RESULTS.md`).
  Centered in the map area when opened at a non-native size, re-centered on resize unless dragged
  (then clamped), stock placement kept at 800x600. The RCI no longer draws over a dialog. The HUD
  window cache no longer captures dialogs and drops freed windows (the hand-test fault in
  GZWIND+0x1EF7A was a SetRect on a closed dialog). `SC3RESIZE_DIALOGS=0` opts out.
- Edge scrolling OFF in windowed mode (owner 2026-10-05, `SC3RESIZE_EDGESCROLL`, default 0).
- Bar FPS cost fixed: the SIMUI tile loop's step is the source rect at `hud+0xd0..+0xd8`, set to
  the client width so the loop runs ~1 time instead of ~128 (`cc687b8`, owner, `SRCRECT` default 1).
- Bar, side panel, minimap and RCI track the window both ways (`7bf1df2`), across repeated resizes
  (absolute placement from cached native rects, `8067c46`), back to native size (`db1fd42`), and
  across minimize/restore (`a2b8ad4`). RCI sits in the native order console | RCI | minimap
  (`1d7a2f2`). RCI overhang above the bar re-composited at present time, `RCIFIX` (2026-09-05).
- Minimize/corner widget re-anchored a few times a second, so a framework relayout cannot leave it
  visible but unclickable (2026-09-03, `rz_corner_reanchor`).
- `KIDFIX` (2026-09-07): child painter windows are no longer translated twice. A/B in
  `verify/resize_sidekidfix/RESULTS.md`.
- `ARTGUARD` (2026-09-07): the side panel no longer vanishes after a tool click plus a resize.
  Section "2026-09-02 to 2026-09-07" below.

**Window**
- Drag-resizable: `WM_GETMINMAXINFO` track limits widened (`8067c46`), and `WM_NCHITTEST`
  answers edge codes over the border where the game said `HTCLIENT` (`db1fd42`).

**Input**
- The relocated HUD is clickable: tool buttons change the tool, panels open and drag (owner
  hand-test 2026-09-01, `1980948`).
- Hover label unclamped from 800x600 (`f103a66`).
- Dead-map root cause (city view rect still 800x600) and six input-geometry fixes baked into the
  mod (`beff2c4`, `7a67b9f`).
- Map clicks hit-test to the correct tile at native and maximized size, measured 2026-09-07 on a
  100%-scaled virtual display (local note `verify/offscreen/MAP_INPUT.md`).
- Flyout sub-tool buttons are left where the game puts them. Moving them split their hit-rects
  from their icons (2026-09-05, `SUBMOVE` default 0). Side-panel hit rects are re-derived after a
  move (`rz_cascade_derived`).

**Tooling**
- `re/tools/sc3io.py` is the one capture path and the one input path (section below).

### Open

1. **Owner hand-test of the 2026-09-03 to 2026-09-07 fixes on a rebuilt DLL.** None of `KIDFIX`,
   `ARTGUARD`, `RCIFIX`, the corner re-anchor or the flyout change has been looked at by the owner.
   `re/harness/bin/sc3resize.dll` predates the last source edit. Rebuild first.
2. ✅ **FIXED 2026-10-05: map input beyond the native 800x600** (`verify/resize_mapinput/RESULTS.md`,
   A/B PASS). The city view's local AND hit rects now follow the client (`SC3RESIZE_VIEWFIX`, default 1),
   so the cascade can no longer reset the hit rect. Moves and right-drag pan work past the old area,
   and the control arm reproduces the dead zone. Zoning past 800x600 is for the owner's hand test.
3. **Edge-scroll band:** `EDGEFIX` (`03ca3c3`) rebuilds the bands from native + delta, measured
   correct at 1920x1009 and back at 800x600. But `+0x177` is "scroll in progress", and every SIMSPR
   starter of a scroll is keyboard-driven, so the bands may never start a scroll from the mouse
   alone. Owner question pending: does the native game scroll with the mouse at the edge and no key?
3b. **Maximize crash 2026-10-05** (`verify/resize_maxcrash/`): null dest sub-surface in GZGraphicD
   `FUN_10014894`. RCIFIX guarded, VEH now names the caller. 34 cycles clean since. Owner confirmed the
   monitors changed at that moment: the topology change is the likely trigger.
3c. ✅ Owner hand test passed 2026-10-06.
4. ~~**Shippable package is stale.**~~ ✅ Released 2026-10-06 (`verify/resize_release/`). Old text: The only packaged `sc3resize.dll` + `resize_launch.exe` is from
   2026-08-28. Cluster mode needs `SC3RESIZE_CLUSTER=1`. Bake the defaults and rerun the offline
   gates.
5. **UI scale-up when the window grows in both directions** (owner 2026-08-30, second half). Today
   the HUD extends. Not started. Constraint known: the side panel's `SetRect` override
   `SIMUI FUN_1004e20b` forces the width to its 96-wide raster.
6. **A root window created while already maximized caches a resized rect as its native one**
   (`final/run.log`, `RESULTS_ARTGUARD.md`). Harmless for children. A root would be translated a
   second time on the next resize. Not yet observed to bite.
7. **Tracker debt** (end of this file). Write with `py re/scripts/tracker.py batch`.
8. Cosmetic: the camera can scroll to empty corners at large sizes.

**Method notes worth keeping (cost paid once):** always control the **display mode** (the v1/v2
confound); a **confirmed code path is not a confirmed cause** (three wrong crash root-causes before the
SEH catcher located it — build the fault-catcher first); **fail-closed byte checks** caught two
self-inflicted patch bugs without ever mispatching a hot function.

---

## 7. Primary evidence (committed PRE.md + RESULTS.md each)

`verify/resize_minimal` (9-step routine) · `resize_wmsize_poll` + `resize_wmsize_cave` (stored-rect) ·
`resize_ship` (DLL carve + display-mode confound) · `resize_rootcause` (OOB cause) ·
`resize_crashhunt` (not-reproducible + SEH) · `resize_fix_a` (all 4 clamps) · `resize_gate` (readiness)
· `resize_census` (fill at 2048x1152) · `resize_u069_v2` (downward). Cost/design: `RESIZE_DELIVERY_COST.md`.

---

## 8. Where the resize STOPS — the primary blit, identified 2026-08-29

Found after the `D-004` hand-test failed (`verify/resize_handtest/RESULTS.md`). Worker-drafted from the
decomp export, **every function below re-read and verified locally** before it was written here.

**The chain, all `GZGraphicD.dll`:**

| hop | RVA | what it does |
|---|---|---|
| WndProc | `0x10017e2f` | `param_2 == 3 \|\| param_2 == 5` (WM_MOVE / WM_SIZE) -> `vt+0x30`, called with **NO arguments** `[CONFIRMED @ 0x10017e2f:126-129]` |
| republish | `0x100185f5` | builds the dest rect from the window object's **stored** size and publishes it `[CONFIRMED @ 0x100185f5]` |
| present | `0x10018c58` | `IDirectDrawSurface::Blt` to the visible surface `[CONFIRMED @ 0x10018c58]` |

**`FUN_100185f5` — the rect is built from the stored size, not the live client area:**
```c
local_14.x = (**(code **)(*param_1 + 0x68))();   // vt+0x68 = STORED WIDTH
local_14.y = (**(code **)(*param_1 + 0x6c))();   // vt+0x6c = STORED HEIGHT
ClientToScreen((HWND)param_1[0xd], &local_c);     // (0,0)
ClientToScreen((HWND)param_1[0xd], &local_14);    // (w,h)
...
piVar3 = (int *)FUN_1001a7ad();                   // display singleton
piVar3 = (int *)(**(code **)(*piVar3 + 0x24))();
(**(code **)(*piVar3 + 0x28))(&local_2c);         // publish the rect
```
`param_1[0xd]` (= `win+0x34`) is the HWND. The stored size behind the getters was measured earlier as
`vt+0x68 = *(win+0x40) - *(win+0x38)` (`sc3resize.c:42`, prior measurement, not re-derived here).

**`FUN_10018c58` — the actual present, and it is the SAME RVA the mod hooks as its per-frame heartbeat
(`GZGraphicD+0x18c58`):**
```c
iVar1 = (**(code **)(**(int **)((int)this + 4) + 0x14))      // vtable+0x14 = Blt
          (*(int **)((int)this + 4), param_3, param_1[1], param_2, param_1[0x37], param_1 + 0x1e);
if (iVar1 == -0x7789fe3e) { ... (**(code **)(... + 0x60))(...) ... retry the same Blt ... }
```
ABI check, all three independently correct: `IDirectDrawSurface` slot `+0x14` = `Blt`, slot `+0x60` =
`IsLost`, and `-0x7789fe3e` = `0x887601C2` = `DDERR_SURFACELOST`. Blt, recover, retry.
Mapping `Blt(lpDestRect, lpDDSrcSurface, lpSrcRect, dwFlags, lpDDBltFx)`: **dest rect = `param_3`,
src surface = `param_1[1]`, src rect = `param_2`** — all **caller-supplied**, none computed here.

**So the failure is:** the mod resizes the SIMSPR surfaces (`iso+0x74`, `iso+0x4ec`) and never touches
the GZGraphicD window object. `FUN_100185f5` keeps publishing an 800x600 rect, and `FUN_10018c58` keeps
Blt-ing an 800x600 block into the window's top-left. That is the observed pixel.

**The fix target:** update the window object's stored width/height on `WM_SIZE` (or intercept `vt+0x30`
/ `FUN_100185f5` so the published rect matches the resized surfaces). **Recreating the SIMSPR surfaces
alone can never help, because the primary Blt does not read them for its geometry.** This is what
`wmsize_setrect` was built to do, and §3's claim that the DLL made it optional was false.

### 8b. The vftable read, 2026-08-29 — inference replaced by bytes

Done by parsing `Apps/GZGraphicD.dll` directly (the vftable is static `.rdata`; no Ghidra project lock
needed). This **corrects the worker report** and closes two of its three open items.

⛔ **`0x100212bc` was WRONG.** It is an auto-named `globals.csv` row (line 89, `vftable,pointer`) with
**zero xrefs anywhere in the decomp**, and its second dword points into `.data`. It is not the window
class vtable. Anyone re-deriving this from `globals.csv` alone will make the same mistake.

**The real window-object vftable is `0x1001f740`** `[CONFIRMED, GZGraphicD]`. Two constructor sites
install it, and both write a second base-class vftable alongside:
```
RVA 0x17bf7   C7 00 40 F7 01 10      mov dword [eax],    0x1001f740   <- primary, object offset +0x00
RVA 0x17bfd   C7 40 04 30 F7 01 10   mov dword [eax+4],  0x1001f730   <- second base class
RVA 0x17c04   A3 B8 CD 06 10         mov [0x1006cdb8], eax            <- object stored to a GLOBAL
RVA 0x17c6e   C7 01 40 F7 01 10      mov dword [ecx],    0x1001f740
RVA 0x17c74   C7 41 04 30 F7 01 10   mov dword [ecx+4],  0x1001f730
```

**Key slots, read from the file:**

| slot | target | body |
|---|---|---|
| `vt+0x20` | `0x10017c0a` | `lea esi,[ecx+0x38]` + `movsd` x4 — GetRect, copies the stored RECT |
| **`vt+0x30`** | **`0x100185f5`** | **the republish function — the WndProc dispatch is now BYTE-PROVEN, not ABI inference** |
| `vt+0x68` | `0x10017c1e` | `mov eax,[ecx+0x40]; sub eax,[ecx+0x38]; ret` = **right - left = WIDTH** |
| `vt+0x6c` | `0x10017c25` | `mov eax,[ecx+0x44]; sub eax,[ecx+0x3c]; ret` = **bottom - top = HEIGHT** |
| `vt+0xc0` | `0x10018c58` | the primary Blt |

**The stored size is a RECT at `win+0x38..win+0x44`** — `+0x38` left, `+0x3c` top, `+0x40` right,
`+0x44` bottom. HWND is `win+0x34` (`param_1[0xd]` in `FUN_100185f5`). This independently confirms the
earlier measurement recorded at `sc3resize.c:42` (`vt+0x68 = *(win+0x40) - *(win+0x38)`).

**The window object is reachable from a fixed global: `GZGraphicD+0x6cdb8`** `[CONFIRMED]`. The
registered WndProc thunk at RVA `0x17e11` loads `this` from it before calling `FUN_10017e2f`:
```
FF 74 24 10          push [esp+0x10]
8B 0D B8 CD 06 10    mov ecx, [0x1006cdb8]     <- the window object
FF 74 24 10 (x3)     push the remaining 3 args
E8 03 00 00 00       call 0x10017e2f
C2 10 00             ret 0x10
```

**Fix specification (NOT built, NOT tested):** in the DLL's existing `WM_SIZE` subclass, read
`win = *(void **)(GZGraphicD_base + 0x6cdb8)`, then set `win+0x40 = win+0x38 + newW` and
`win+0x44 = win+0x3c + newH` (write right/bottom relative to the existing left/top rather than
zeroing them, since `FUN_100185f5` maps the rect through `ClientToScreen` and left/top may carry a
position). `FUN_100185f5` then publishes a correctly sized rect and `FUN_10018c58` Blts the full
window. This is what the subclass was documented as already doing and does not (§3).
⚠️ Under the BOARD standing rules this needs a committed `PRE.md` with the pass/fail spelled out, an
`IsBadReadPtr` gate + expect-or-refuse vftable check (`*(DWORD *)win == base + 0x1f740`) before any
write, and a fresh owner hand-test — it is unverified until a real display shows it.

`[UNCERTAIN]` — still not established:

- ~~The `vt+0x30` body and the raw backing-field offset for the stored size.~~ ✅ **RESOLVED in §8b** —
  vftable `0x1001f740`, `vt+0x30 = FUN_100185f5`, stored RECT at `win+0x38..+0x44`. No Ghidra needed;
  the table is static `.rdata` and was read from the PE.
- The **caller** that hands `param_3`/`param_2` to `FUN_10018c58`. It is invoked virtually and has no
  textual caller in the export, so "the rect it receives is the one published by `FUN_100185f5`" is
  **inference from the DirectDraw ABI, not a byte-proven link**.
- `FUN_100185f5`'s guard `(**(code **)(*piVar3 + 0x34))() == 0` was read as "windowed" by the worker.
  That is an unproven label; mechanically it is a char-returning singleton getter gating the
  ClientToScreen branch.
- The iOS oracle is **useless here**: that build is OpenGL-ES and has no DirectDraw primary-blit analog.

---

## 9. Defects A + B root-caused, 2026-08-29 — step 8 calls the leaf, not the routine

After the stored-RECT fix confirmed `D-004`, the two remaining rendering defects were diagnosed and
**verified against the SIMSPR decompilation** (worker-drafted, re-read locally). One root cause.

**Two draw systems on the iso view** (all `SIMSPR.DLL`):
- **A. Sprites/objects** (buildings, roads): hash-map `iso+0x3a4` -> fine grid `iso+0x380`, drawn by
  `FUN_1000af7c` off `iso+0x380`. **Scroll never rebuilds `iso+0x380`.**
- **B. Terrain/zone tiles**: `iso+0x24` map grid, repainted by scroll routine `FUN_100071a3`. **Self-
  heals on camera move** — why terrain/zones return and buildings/roads do not.

**Step 8 (`FUN_1000fa36(iso,1,0)`) is the innermost leaf of the real re-register.** Its sole caller
`FUN_1000c9bd` `[CONFIRMED @ 0x1000c9bd]` first `FUN_1000edd9` (clear `iso+0x380`) then a region scan
adding tag-2 nodes via `FUN_1000cedb`, THEN `FUN_1000fa36` (tag-1). The grandparent `FUN_10006a55`
(view-change handler) additionally runs `FUN_1000c8f9` (recompute every object draw key `wrapper+0x24`)
and `FUN_100071a3` (System-B repaint) — sequence at `0x10006a55` lines 60-69:
`b70e -> e248 -> c8f9 -> 071a3 -> b352 -> c9bd`. The mod runs only the final leaf, with `purge=0`, so it
skips: the grid clear, the tag-2 region pickup, the draw-key recompute, and the System-B repaint.

**Defect B** = `iso+0x380` object grid never properly rebuilt + scroll never touches it -> buildings/
roads gone at every camera position. **Defect A** = System-B field repaint `FUN_100071a3` not run for
the newly exposed region -> black until a scroll triggers it.

### Step 10 + device batch — the defect is the PRESENT, localized 2026-08-30

Progress after 8c falsified drawable re-registration:
- **Step 10 (iso whole-view repaint `FUN_1000db86` = iso vt+0x144, PE-verified) ALONE: FAIL.** Ran clean
  (`iso+0x32c=1`, no fault), screen unchanged. `verify/resize_pipeline/`.
- **Owner: rotating the view does NOTHING; only a data/utility overlay toggle and back fixes it.** This
  refutes the transition/repaint path entirely and points at the **device present batch** the base-view
  return runs (`FUN_1001818c:53-55`): `device+0x240` begin -> iso `+0x144` repaint -> `device+0x244`
  end, `device = *(bridge+0x14)`. Rotation repaints but never runs this batch.
- **Next build (`verify/resize_present/`):** wrap step 10's repaint in that device batch, verbatim. The
  `+0x240/+0x244` device slots are called through the live vtable (unverified statically), guarded +
  SEH. `[UNCERTAIN]` until hand-tested. Falsification: if begin+end run with no fault and the screen is
  still blank, the repair is deeper in `FUN_100182ba` SetDataView(0), not the batch.

Falsified so far: 8a/8b (sprite re-register), 8c (tile re-register), step-10-alone (repaint), rotation.

### 8c RESULT — drawable re-registration is FALSIFIED (2026-08-30)

Step 8c (extract `FUN_100071a3`'s inner loop: per-cell `FUN_10006c67` hide + `FUN_10006efc` show over
the whole `iso+0x24` grid, `verify/resize_gridreshow/`, pre-reg `24d67ec`) **ran completely and fixed
nothing**. Log: `grid re-show 256x256: 65536 occupied, 65536 re-shown, 0 bad`, zero faults — the
drawable `+0x34` show was invoked for every building and road, and they still did not draw; a manual
data-layer toggle is still required.

**This decisively falsifies the whole "re-register the drawables" line.** Both 8a/8b (sprite grid) and
8c (tile grid) drove the exact engine primitives and neither reproduced the toggle. The defect is
**downstream of per-cell registration** — in the render/composite pipeline the `+0x34` show feeds. The
data-view toggle switches the whole render MODE (3D -> flat overlay) and back via a **cross-DLL**
(SIMUI/SIMCITY) path that is NOT `FUN_100071a3`, and that mode round-trip resets whatever a resize
leaves stale. `[UNCERTAIN]` — the specific stale pipeline state is not identified. **Do not build another
drawable-re-register variant; that class is exhausted.** Next lead: the cross-DLL data-view handler, or
a test of whether a real rotate/zoom transition also repairs it.

### Option 1 RESULT + the layer-toggle finding (2026-08-29)

Option 1 was built (step 8 -> `FUN_1000c8f9` + `FUN_1000c9bd`, `verify/resize_objreregister/`,
pre-registered `d596089`) and hand-tested. **It ran clean but did NOT visibly fix defect B** on a plain
resize: log shows `[step 8a]`/`[step 8b] FUN_1000c9bd returned` on all cycles, zero faults, but the
owner reports "same as before".

**⭐ Decisive new finding: a data-layer toggle fully repairs the render.** Switching to a data view
(water lines) and back to the buildings view after a resize makes the **whole scene render**, buildings
and roads included. **This refutes the earlier "objects are gone / cross-DLL placement" hypothesis** —
the objects are present and renderable; the resize leaves them undrawn and a full view/layer rebuild
clears it. (Owner caveat: the workaround was not tested on the pre-fix build, so it is an engine
property, not a credit to option 1.)

**Corollary that narrows the draw class:** the OLD step 8 already called `FUN_1000fa36` (tag-1 re-add of
`iso+0x3a4` objects) and buildings/roads were missing then too — so **buildings/roads are almost
certainly NOT tag-1 objects**. They are either tag-2 region sprites (pickup guarded by `2 < iso+0x28`
and the exposed-rect list `iso+0x4c4`) or layer-visibility tile drawables. `[UNCERTAIN]` — a worker read
of the data-view/layer-switch handler is in flight to settle which and to extract the exact rebuild
delta the layer toggle runs that step 8 does not.

### Fix options (NONE built)

| # | change | fixes | risk |
|---|---|---|---|
| 1 (surgical) | replace step 8 `FUN_1000fa36(iso,1,0)` with `FUN_1000c8f9(iso)` then `FUN_1000c9bd(iso, iso+0x54, 1)` | **B** (and A's object half); A's terrain half may need #2's `FUN_100071a3` | small blast radius, stays in the spirit of the Init-free routine; `FUN_1000c9bd` region pickup depends on `iso+0x4c4`/zoom guard being set at step-8 time `[UNCERTAIN]` |
| 2 (canonical) | after the resize, call `FUN_10006a55` (the whole view-change handler) instead of the hand-rolled System-A steps | **A and B together** | bigger hammer; takes rotation/coord params and calls `FUN_1000a513`/`FUN_10008dd4` — may move/rotate the view or undo Init-free guarantees; needs its args reverse-engineered |

Recommendation on record: **#1 first** — it targets the severe defect (buildings/roads never return)
with minimal risk to the validated 9-step routine, and if defect A's terrain half persists, add
`FUN_100071a3` for the exposed region as a step 7b rather than adopting the whole `FUN_10006a55`.
Any build needs a committed `PRE.md` + an owner hand-test (the log cannot see the pixels).

---

# HUD BAR / FPS — THE COMPLETE CHAIN (2026-09-01, `verify/resize_hudlab/`, runs 1-20)

**Headline: the full-width HUD bar's FPS cost is a TILING LOOP in SIMUI, not a compositor property.**
The claim that closed this workstream in 2026-08 — *"intrinsic to this engine's per-frame
compositing... would mean changing the compositor"* — is **refuted by measurement**.

## The chain, all four links proven

```
SIMUI FUN_10026841        tile loop, one blit per step
  -> GZGraphicD FUN_10014894+0x76   blit ONE rect (clip via vt+0xac, format check, no loop)
    -> GZGraphicD FUN_10018c58+0x31 the engine's Blt wrapper  (= sub vtable +0x2c)
      -> IDirectDrawSurface::Blt    (COM vtable +0x14)
```

`[CONFIRMED @ SIMUI 0x10026841, GZGraphicD 0x10014894, vtable 0x1001f0ac+0x2c]`

## The loop

```c
iVar4 = *(param_1 + 0xd8) - *(param_1 + 0xd0);   // STEP = the SOURCE RECT's width
do {
    vt[0x118](*(param_1 + 0xac), param_1 + 0xd0, &local_14, 0);
    local_c -= iVar4;  local_14 -= iVar4;
} while (*(param_1 + 0x130) < local_c);
```

Tiles right-to-left from the bar's right edge (`+0x2c`) to `+0x130`. Measured at 2048 wide:
**~46 DirectDraw blits per frame, 6892-8538 calls per 8 s, 93% of ALL Blt time**; ~0 at native width.

## The HUD bar object, decoded

Children `this[0x2a..0x2f]` are at byte offsets `+0xa8..+0xbc` (`0x2a * 4 = 0xa8`).

| child | offset | dims | how it is drawn |
|---|---|---|---|
| `[0x2a]` background | `+0xa8` | 600x56 | once, src `+0xc0` -> dest `+0x120` |
| **`[0x2b]` filler** | **`+0xac`** | **16x64** | **TILED** in the loop, src rect `+0xd0` |
| `[0x2c]` | `+0xb0` | 136x18 | once |
| `[0x2d]` | `+0xb4` | 112x18 | once |
| `[0x2e]` | `+0xb8` | 104x18 | once |
| `[0x2f]` | `+0xbc` | 148x18 | once |

All six are `GZGraphicD+0x1E894` rasters with pitch == width*2 (fix16).

## Surface plumbing (useful well beyond the HUD)

- `sub+0x04` = `IDirectDrawSurface*`; `sub+0x74` = `DDSCAPS.dwCaps` (DDSD at `sub+0x0c`, caps at
  DDSD+0x68); `sub+0xe8` = the OWNING raster; `sub+0xe4` = lock depth.
- **`sub+0xf0` (bits) / `sub+0xf4` (pitch) are written ONLY by the LOCK** (`sub->vt[0x0c]` =
  `FUN_10018a82`), never by create (`sub->vt[0x40]` = `FUN_10019273`). `bits == 0` immediately after
  a recreate is CORRECT for every surface of this class.
- Unlock (`sub->vt[0x10]` = `FUN_10018b53`) does **not** clear `sub+0xf0`, which is why raw reads
  keep working and why an out-of-band unlock is destructive (refcount inversion).

## What was eliminated, each by measurement

| excluded | how |
|---|---|
| surface residency | caps byte-identical `0x00006040` VIDMEM at both widths (run 11) |
| pixel throughput | 6x SMALLER blits, 7.7x slower (run 12) |
| our recreated surface | 600(ours) returns to 600(engine) baseline within 0.03% (runs 14, 15) |
| source-surface width | widening `[0x2b]` to 2048 changed nothing - the step is the source RECT (runs 17, 20) |

## Fix candidate — a FIELD WRITE, not a code patch (NOT YET TESTED)

The surface is already widened. Widening the **source rect** `+0xd0..+0xd8` widens the step, turning
~46 iterations into ~2. Same class of write as the shipping `vt+0xc8` SetRect. `[UNCERTAIN]`: that
the blit path honours a wider source rect from that field.

## ⚠️ Tracker debt

`functions.csv` has NOT been updated with these names (`SIMUI 0x10026841`, `GZGraphicD 0x10014894 /
0x10018a82 / 0x10018b53 / 0x10019273`). Deliberately deferred rather than risk a bulk write at the
end of a long session - the file is keyed on **(module, rva)** and a careless write has already
damaged it once. Do this as a dedicated, verified edit.

Added 2026-10-05 from the 09-07 work, same treatment: `SIMUI 0x1006d2d0` (paint), `0x1006d438`
(rebuild source rect), `0x1006d56c` (surface keep/release), `0x1006db90` (base SetRect),
`0x1004e20b` (side panel SetRect), `0x1006de62` (hit-test), `0x1006ccda` / `0x1006d1af` (input
walks). `GZWIND 0x10025790` (key-state leaf), `0x10020947` (key sink), `0x10020108` (SetFocus).
`SIMSPR 0x10049265` (city view OnKeyDown), `0x1004979a` (arrow scroll), `0x10048a2d` (tool
delegate install/clear). Check each row's current name and confidence first.

---

# ⭐ THE VERTICAL UI IS THE EASIER CASE — `SIMUI FUN_1004e63e` (2026-09-01, static, no lease)

Owner asked whether moving the vertical/side UI might behave differently. **It does, and in our
favour.** Found by searching SIMUI for paint routines with the same shape as the bottom bar's
(`vt+0x118` blit dispatch + a loop): `FUN_1004e63e` is the only other 6-blit routine with a loop.

## It has a SINGLE-BLIT FAST PATH the bottom bar lacks

```c
iVar5 = (**(code **)(**(int **)(param_1 + 0xcc) + 0x3c))();          // tile source's HEIGHT
if (iVar5 < *(int *)(param_1 + 0x10c) - *(int *)(param_1 + 0x104)) {  // shorter than the span?
    do {                                                              // ... then TILE
        ... vt[0x118](*(param_1 + 0xcc), uVar4) ...
    } while (local_14 < *(int *)(param_1 + 0x10c));
} else {
    ...
    (**(code **)(**(int **)(param_1 + 0x5c) + 0x118))                 // ... else ONE blit
              (*(undefined4 *)(param_1 + 0xcc), &local_18, piVar1, 0);
}
```

`vt+0x3c` on the raster class is `mov eax,[ecx+0x28]; ret` = **the surface HEIGHT**
(`vt+0x38` = `[ecx+0x24]` = width), read from the PE `[CONFIRMED @ GZGraphicD 0x10009e4e]`.

## The asymmetry, and why it matters

| | bottom bar `FUN_10026841` | side panel `FUN_1004e63e` |
|---|---|---|
| step | `*(+0xd8) - *(+0xd0)` = **source RECT width** | `src->vt[0x3c]` = **source SURFACE height** |
| fast path | **none - always tiles** | **yes - one blit if the source covers the span** |
| tiled child | `+0xac` (`this[0x2b]`) | `+0xcc` |
| consequence | widening the surface does nothing (run 17, measured) | **heightening the surface should collapse the loop** |

**The fix that FAILED on the bottom bar is the RIGHT fix here.** The vertical routine reads the
source surface's own height and explicitly takes a single-blit path when it is tall enough — so
`rz_hud_fit_child` applied to `+0xcc` in the HEIGHT axis should turn the loop into one blit, with no
field-write trickery needed.

## Object layout of the side panel window

Children at `+0xc0`, `+0xc4`, `+0xc8`, `+0xcc`, `+0x114`; **only `+0xcc` is tiled**, using rect
fields `+0x100..+0x10c` (span = `+0x10c - +0x104`). Same overall shape as the bottom bar: several
one-shot widgets plus one tiled filler.

## What is still needed to act on it

The mod has never captured the side panel's window object. The bottom bar's `this` was captured by
wrapping its producer (`FUN_100270e5`); the side panel needs the equivalent — the board notes
height-keyed tables `FUN_1004c3e9` / `FUN_1004cdcd`, and `FUN_1004e63e` sits in the same
neighbourhood, so its producer is very likely nearby.

`[UNCERTAIN]` — that `FUN_1004e63e` paints the in-city side panel specifically. It has the right
shape and the right address neighbourhood, but nothing yet ties it to that window at runtime. The
cheap confirmation is the same one used for the bar: wrap the producer, capture `this`, and log its
rect - if it is a tall narrow rect at a screen edge, that settles it.

## Bottom line for the owner's question

**Yes — worth doing, and the vertical case looks strictly easier than the horizontal one.** The side
panel's paint routine is written to avoid tiling when it can; the bottom bar's is not.

---

# 2026-09-02 to 2026-09-07 — KIDFIX, ARTGUARD, sc3io, minimised input, the DPI correction

Committed in `83d679a`. Primary records: `verify/resize_sidekidfix/RESULTS.md`,
`verify/resize_sidekidfix/RESULTS_ARTGUARD.md`, and the `re/tools/sc3io.py` docstring.

## KIDFIX — child windows were translated twice (`SC3RESIZE_KIDFIX`, default 1)

The cluster step translated every painter window by the resize delta, children included. A child's
rect is parent-relative, so moving the parent already moves it, and the second translation pushed
it off the client. Measured at virtual client 2048x1081 (`dx,dy = 1248,481`): side-panel page
children at `[3200 962 3236 1404]` with `KIDFIX=0`, `[1952 481 1988 923]` with `KIDFIX=1`. The
root/child classifier was correct on all 10 windows. Kept on because the write is plain arithmetic
error. **It did not fix the missing side panel**, which was the pre-registered discriminating
prediction.

## ARTGUARD — the side panel vanished after a tool click plus a resize (`SC3RESIZE_ARTGUARD`, default 1)

**Trigger, isolated by sequence:** maximize alone, panel present. Tool clicks alone, panel present.
Tool clicks then maximize, panel gone, and it stays gone after restore.

**Cause:** `rz_fix_hud_parents` widens every ancestor of a relocated window to the client height so
the input router's hit-test passes. The panel becomes an ancestor only once a tool click creates
its page children. It blits a fixed 96x442 surface (`this+0x58`), and the walk stretched it to
96x600.

**Why that paints nothing** `[CONFIRMED @ SIMUI]`:
- `vt+0x164` = `FUN_1006d438` rebuilds the blit source rect `+0x24..+0x30` from the local rect as
  `(0,0,w,h)`. The paint is `dev->vt+0x118(surface, this+0x24, this+0x90, 0)` in `FUN_1006d2d0`.
- `vt+0x170` = `FUN_1006d56c` keeps a surface only if the local rect matches its size exactly, and
  releases it (`+0x58 = 0`) on an empty rect. The paint skips a null surface silently.
- Paint gates are `+0xA0 & 1`, the `+0x60` dirty byte and `+0x58` null. No clip, no empty-rect test.

**Evidence chain:** the mod's own `PARENT>` log line shows the correct rect in and a client-height
rect out. Poking the four rects back to 96x442 in the broken state brought the panel, its art,
its ten buttons and the open flyout back. `side_paint_probe.py --diff` across the maximize found
one non-positional change: `panel+0x30: 442 -> 600`. Matched A/B with one flag: present with
`ARTGUARD=1`, absent with `=0`. Tool clicks at maximized size still work with the guard on.

**The fix:** the walk still traverses a window that owns a surface at `+0x58` (or is one of the
mod's managed HUD windows) but does not widen it.

**Corrected comment:** the parent widen is an input fix only. `vt+0xe4` = `FUN_1006de62` is a
hit-test, called only from the input walks `FUN_1006ccda` / `FUN_1006d1af`. The paint walk calls
every child's `vt+0x148` unconditionally. So a window outside its parent's rect still paints but
gets no mouse input.

**Constraint for UI scaling:** the panel's `SetRect` override `vt+0xc8` = `FUN_1004e20b` replaces
the requested width with the width of the raster at `+0xC0` and clamps the height up to the sum of
three decoration rasters `[CONFIRMED @ SIMUI 0x1004e20b]`. The panel cannot be widened through
`SetRect` while that raster is the shipped 96-wide one.

## sc3io — the one capture path and the one input path

`re/tools/sc3io.py` replaces about 20 scripts that each captured or clicked their own way.
- **Never moves the cursor and never takes focus.** Input is `PostMessageW` to the game's HWND.
  The window is raised with `SWP_NOACTIVATE` for capture only.
- **One capture method, no fallback:** desktop-DC `BitBlt` of the window's screen rect, the only
  method measured to see the DirectDraw layer. If the gate cannot trust a grab (occluded,
  minimised, off-screen), it raises and writes nothing.
- `sc3io_audit.py` is the regression check for cursor, focus and second-capture code in any tool.
  `sc3io_selftest.py` poisons the banned APIs and runs the live invariants. `sc3io_cli.py` serves
  PowerShell drivers (exit 2 = not grabbable, fatal).
- `vdd.py` + `launch_offscreen.py` run the game on a Parsec virtual display, so capture needs no
  real monitor.

## The DPI correction — posted input coordinates are PHYSICAL

The game is DPI-unaware: it renders at a virtual client size (800x600) and Windows scales it to
physical (1000x750 at 125%). The earlier tooling assumed posted mouse coordinates were virtual.
**They are physical**, the same space as a grab. Windows scales the `lParam` down into the
window's virtual space. Measured inside the engine (GZWIND window manager `mgr+0x170/+0x174`):
posting x=765 arrived as 612 (x0.8), posting x=956 arrived as 765. A pixel read off a grab is
directly clickable. `GetDpiForWindow` returned 96 in a state where the true factor was 1.25, so
derive the factor from the physical client and the engine's stored rect `win+0x38..+0x44`.

The wrong model put clicks ~20% off, which earlier read as "the map takes no clicks" and "input
fails when minimised". Re-measured on a 100%-scaled virtual display, map clicks resolve the correct
tile at native and maximized size.

## Input reaches the game while minimised

Measured 2026-09-07 across visible, buried under a topmost window, `SW_MINIMIZE`,
`SW_SHOWMINNOACTIVE` and off-screen: the WndProc receives every posted message and the window
manager dispatches it at the same coordinate in all five states. A posted click on a side-panel
tool button switched the tool while the window was minimised (15 rows of the panel subtree
changed). Only capture needs the window on screen. Tools: `input_reaches_game.py`,
`minput_probe.py`, with OS-level controls `minput_os_control.py` / `minput_cloak_control.py`.

**Keyboard limit (tooling, not the mod):** the city view's arrow handler reads the physical key
state, and modifiers come from `GetKeyState`, so posted keys never scroll and never carry
Ctrl/Shift/Alt. `key_state_spoof.py` hooks the key-state leaf `GZWIND FUN_10025790` to scroll
under automation. Full chain in the local note `verify/offscreen/KEY_BINDINGS_RUNTIME.md`.
