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
monitor**. The headless harness reconstructs frames from the raster composite (which is proven full and
correct); it cannot see the real present to a screen. **Needs an owner hand-test on a real display.**
An earlier informal hand-test (`verify/resize_handtest`) showed maximize works with no black viewport
and no crash, but pre-dates the current fixes.

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
- WndProc subclass makes a real `WM_SIZE` publish the true client size (why the on-disk
  `wmsize_setrect` GZGraphicD patch is OPTIONAL under this mod).

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

**Done (headless-verified):** the 9-step routine (both directions), the crash fix (all 4 walkers), the
display-mode patches, the load-readiness gate, on-screen fill at 2048x1152 (raster+composite census),
shippable DLL+loader with offline gates passed.

**Open:**
- ⏳ **`D-004` — the real-monitor flip.** Only an owner hand-test on a physical foreground display can
  confirm the final DirectDraw present. Everything upstream is proven.
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
