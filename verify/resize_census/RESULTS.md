# RESULTS — in-mod pixel census (2026-08-28). ⭐⭐⭐ OUTCOME 1: NOT CLIPPED. The frame FILLS the window.
# PRE git `5ddc2f1`. Europolis, load zoom, gate on, 2048x1152. No fault.

| surface | size | non-zero | bbox | beyond 800x600 | verdict |
|---|---|---|---|---|---|
| render target `iso+0x74` | 2048x1152 | **100.0%** (2359296/2359296) | r0..1151 c0..2047 (**full**) | **1,879,296** | FILLS BEYOND |
| blit-dest `iso+0x4ec` | 2048x1152 | **99.7%** (2352028/2359296) | r0..1151 c0..2047 (**full**) | **1,879,296** | FILLS BEYOND |
| (settle) render target | 2048x1081 | 99.9% | r0..1079 c0..2047 (full) | 1,731,840 | FILLS BEYOND |
| (settle) blit-dest | 2048x1081 | 99.6% | full | 1,731,840 | FILLS BEYOND |

## Verdict: on-screen correctness SETTLED — the frame is not clipped
**Both the rasterization surface AND the composite surface hold a full 2048x1152 image**, ~99.7-100%
non-zero, bounding box spanning the entire window, with **~1.88M non-zero pixels in the area BEYOND the
old 800x600.** A clip to the top-left would show `beyond = 0` and a bbox of ~800x600; it shows the
opposite. Read RAW (no `vf1c` lock), so the measurement did not tear its own subject.

⭐ **This retires the earlier "clipped 800x600" screenshot as a `PrintWindow`/D-004 capture artifact,
NOT the engine's frame** — exactly the caution logged when that screenshot was taken ("the log is the
witness, not the image"). The engine composites a full-size frame; `PrintWindow` simply failed to
capture it.

## What remains genuinely open (and it is small)
- The **`iso+0x4ec` blit-dest is what feeds the DirectDraw present**, so a full blit-dest is strong
  evidence the presented frame is full-size. The one hop this cannot see is the final DirectDraw
  primary **flip to the physical monitor** — `D-004`, which by construction needs a real foreground
  display, not a headless census. **No in-process instrument can close that last hop.**
- Downward resize `U-069` still untested.

## Where the workstream stands
Resize routine: robust at 2048x1152 across zoom and timing. Frame: **fills the window on both the
raster and composite surfaces.** Crash: not reproducible + guarded by the load-readiness gate. Delivery:
`sc3resize.dll` + `resize_launch.exe`, offline-gated. The only thing a headless environment cannot
verify is the final flip to a real monitor (D-004) — an owner hand-test on a real display would close it.

## State
No fault, no orphan. Owner build verified `f5b9f1d9` / `acefadf0`. Mod patches nothing on disk. Lease +
claim released.
