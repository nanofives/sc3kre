# RESULTS — U-068 rect-push fix attempt (2026-08-26)

**Verdict: FIX CONFIRMED.** The pre-registered top-row outcome landed: `iso+0x4d0` count 0→1, the iso
render target became a live blit source the instant of the push (0 before, 34 after), and the screen
shows the full city. Single-variable A/B — shot B (black) and shot C (city) differ only by the rect push.

## Provenance
- Probe `sc3probe.dll` sha256 `da6f20809aae3bc454689cbc336f288c44303e9553dcea4b5554eacb1199e192` (276,480 b),
  built 2026-08-26 from the staged hunks (`SC3PROBE_RESIZE_PUSHRECT` gate).
- **Stock SIMSPR** restored for the measurement (verified scroll 32.0 ×5, drag `fe`, deadzone 12.0);
  re-staged to the owner's three-recipe build after (scroll 8.0 ×5, drag `fc`, deadzone 2.0; `--diff`
  gate 8 runs / 9 bytes).
- Europolis, `-nocom -windowed -fix16 -fitclient -nointro -quiet`, `SC3PROBE_RESIZE=1
  RESIZETO=1280x1024 RESIZEAT=22 U068SURF=1 U068SRC=1 U068SHOT=1 RESIZE_PUSHRECT=1`, `-AtSec 100`.
  Own game lease (`resizefix`), own harness claim. Log `re/harness/capture.log`.
- Three shots, one process, same city/camera: A pre-resize control, B post-resize unfixed
  (full-present suppressed), C after the push. BMPs `re/harness/shot_01..03.bmp` (game content, not
  retained/committed); PNGs shared for review in `.happy-share/…/u068_shotB…png` (black) and
  `…u068_shotC…png` (city).

## The measurements

### Shot A — pre-resize control (t+21.86 s, 1024x768) — VALID
Europolis fully rendered, `Pob 2,069,432`. Census `A_pre_resize_CONTROL`: iso sub `0x0F40C9F0` matched as
a blit source **43 / 1500** blits. Instrument sound.

### The push (phase C, t+27.131 s) — took cleanly `[CONFIRMED @ capture.log:960-965]`
```
U068PUSH> iso+0x4d0 BEFORE: begin=0x121C9728 end=0x121C9728 count=0  iso+0x7c=0 items(+0x524)=0
U068PUSH> iso+0x4d0 AFTER push {0,0,1280,1024} via FUN_10010586: begin=0x121C9728 end=0x121C9738
          count=1 (end advanced +0x10 - push_back took)
U068PUSH> FUN_1000e058 incremental present (iterates iso+0x4d0) -> 0   (void; return meaningless)
```
BEFORE confirms the mechanism live: the list was **empty** (count 0) and `iso+0x7c` had reverted to **0**
(the incremental-park state), exactly as the decompilation predicted. The push advanced `end` by one
16-byte element (count 0→1) — a real `push_back`, not an in-place overwrite.

### Shot B — post-resize, UNFIXED control (t+27.131 s, 1280x1024) — BLACK
Captured immediately BEFORE the push. The iso viewport is **black**; HUD/minimap present (laid out for
1024x768 — the separate item-2 reflow). The defect reproduced through the exact list path being fixed.

### Census — the transition is pinned to the push `[CONFIRMED @ capture.log:945-1034]`
The `B_post_resize` census window (opened 25324.9 ms, closed 32210.4 ms) spans the push at 27131 ms:
- **Before the push** (25324→27131, ~1.8 s): **zero** iso-sub matches — the black defect.
- **First match at 27131.280 ms** — 18 µs after the push, and BEFORE the explicit `FUN_1000e058` at
  27146.8 ms, so it is the **game's own frame loop** blitting the pushed rect, not the harness call.
- **34 matches total** through window close (32210 ms), a rate comparable to control A's 43 — the
  persistent rect is re-blitted every frame. **The fix self-sustains; it is not a one-frame flicker.**

### Shot C — post-push (t+28.93 s, 1280x1024) — FULL CITY
The iso viewport renders **the full Europolis city at 1280x1024**. Captured ~1.8 s after the push, well
within the sustained-blit window, so the frame loop was still presenting the persistent rect. Shot C's
mirror matched 377 blits into the composite (latched dest `0x0C02E370`).

## Attribution — a confirmed cause, not a confirmed path
B and C are the same process, same city/camera/window, same post-resize Init state. The **only**
difference is the one rect pushed into `iso+0x4d0`. B is black, C is the city. So the empty rect list
**was** what prevented the blit — measured, per the reopen rule, not inferred.

## Honest caveats
1. **The HUD does not composite over the city in shot C** — the status bar sits at its 1024x768 position
   mid-screen and the tool palette is overpainted by the full-screen iso present. This is the separate,
   already-root-caused **item-2 reflow** (`FUN_100270e5`, no branch above width 800), not an item-1
   regression. The pushed rect `{0,0,1280,1024}` mirrors the ctor's own full-device rect, so it is the
   correct iso rect; the HUD placement is item 2.
2. **This is the harness driving the resize.** The fix is proven under `SC3PROBE_RESIZE_PUSHRECT`; making
   a real, shipped resize reach this code (window style / client-size path) is **item 3**, a separate
   shipping-shape decision, not yet built.
3. **Upward resize only, 1024→1280.** Downward resize (`U-069`) is still unexercised.

## What a shipping fix needs (mechanism-level)
After Init re-runs on a resize, `push_back {0,0,new_w,new_h}` into `iso+0x4d0` via the engine's own
`FUN_10010586`, using the new device dims. The game's per-frame loop then presents it every frame with no
further help. (No forced `FUN_1000e058` call is needed — the loop picked up the rect on its own within
18 µs.)
