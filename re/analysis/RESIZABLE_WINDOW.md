# RESIZABLE_WINDOW.md — consolidated handoff (2026-08-29)

Single authoritative summary of the resizable-window / arbitrary-resolution mod for
**SimCity 3000 Unlimited**. Supersedes the scattered `verify/resize_*` records for orientation; those
remain the primary evidence (each has a committed `PRE.md` + `RESULTS.md`).

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

## 6. What is DONE vs OPEN

> ⛔⛔ **UPDATED 2026-08-29 — `D-004` WAS HAND-TESTED AND IT FAILED. THE MOD IS NOT COMPLETE
> END-TO-END.** Owner ran it on a real 2048x1152 display and maximized by hand: the city **stayed drawn
> in the top-left at the pre-resize size** and did not fill the window. Cursor/input did follow the full
> window. The log shows the routine completing all 9 steps three times with both surfaces re-created at
> 2048x1081 and **zero faults**. Full record: `verify/resize_handtest/RESULTS.md`.
>
> **Read the "on-screen fill at 2048x1152" claim below as *renders into its own surfaces at that size*,
> NOT *displays at that size*.** The `verify/resize_census` result was a **nondiagnostic proxy** — it
> measured `iso+0x74` / `iso+0x4ec`, which were full on the failing run too.

**Done (headless-verified):** the 9-step routine (both directions), the crash fix (all 4 walkers), the
display-mode patches, the load-readiness gate, surface-level fill at 2048x1152 (raster+composite
census — see the correction above), shippable DLL+loader with offline gates passed.

**Done (real-display verified, 2026-08-29 hand-test):** the crash fix holds under hand-driven
maximize/restore churn (zero `FAULT CAUGHT`); the readiness gate fires on a real city load; the WndProc
subclass publishes the **true** client size (`WM_SIZE 2048x1081`); all 4 clamps install against a
relocated `SIMSPR` base.

**Open:**
- ⛔ **DEFECT A — resize does not repaint the newly exposed area.** Black except moving traffic; camera
  motion makes terrain and zones appear. Step 7 `FUN_10018cdf -> 1` and step 9's full present-rect push
  both happen, so the redraw path is not being triggered for the new region. `[UNCERTAIN]`, not
  diagnosed. **Blocks shipping.**
- ⛔ **DEFECT B — the resize drops buildings and roads** (CORRECTED from "never render"; owner:
  launch is fine, resize breaks it). At every camera position after a resize, buildings and roads are
  gone; terrain and zones return on camera motion. `patch_windowed`/`FIX16` exonerated (live at launch,
  city fine). Lead: step 8 `FUN_1000fa36` re-registers *partially* (terrain+zones, not buildings/roads).
  `[UNCERTAIN]`, worker reading the decomp. **Blocks shipping.**
- Input picking now disagrees with the blit: the view fills the window but navigation works only in the
  top-left 800x600 (the inverse of the pre-fix behaviour). Not investigated.
- ✅ ~~**`D-004` — the real-monitor flip: FAILED**~~ **CONFIRMED 2026-08-29** by the stored-RECT fix.
  Retained below for the reasoning that got there:
- ⛔ **`D-004` — the real-monitor flip: FAILED, and now localized.** *(historical — superseded above)* Everything from `WM_SIZE` through
  `iso+0x4ec` is witnessed correct on a real display; the monitor still shows the old image top-left.
  **The gap is downstream of `iso+0x4ec`** — the component that copies that surface to the DirectDraw
  primary and flips it, which the 9-step routine never touches and never resizes.
  `[UNCERTAIN]` the specific object and call are **not identified**; this is localization by
  elimination, not a confirmed cause. ⛔ Do not score a future run against `PRE.md`'s old table, which
  reads this exact visual as "the render target is NOT resized" — the log proves it **was**.
- Camera can scroll to empty corners at large sizes (cosmetic; the census saw low fill when scrolled) —
  not investigated, likely a default camera-origin/clamp question, not a resize defect.
- The DLL has only been driven via `resize_launch.exe` + external `SetWindowPos`; a real user drag-resize
  goes through the same `WM_SIZE`, but has not been hand-exercised.

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
