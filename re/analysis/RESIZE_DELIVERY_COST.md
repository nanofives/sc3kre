# RESIZE_DELIVERY_COST.md — costing the shipped resize routine (2026-08-27, desk work, no lease)

**Verdict up front: do NOT hand-assemble the routine as a SIMSPR code cave. Ship it as a slim mod DLL
on the vehicle the camera workstream just proved.** The cave is buildable and slack is not the
constraint, but it is roughly 4x the largest cave this project has shipped, for no capability the DLL
route lacks.

Costed against `verify/resize_minimal/RESULTS.md` run 6 — the 9-step sequence that PASSES.

---

## Branch A — hand-assembled SIMSPR code cave

### Slack: MEASURED, and it is NOT the constraint
`SIMSPR.DLL.shipped` `.text` has exactly **one** zero run >= 64 bytes: **2,918 bytes at
`0x1006149A`**, ending at `0x10062000`. Already occupied: `resize_rectfix` (33-byte cave) and
`bridge_stash` (30-byte cave at `0x100614c0`). **Free from ~`0x100614e0`: ~2,848 bytes.**

### Size estimate, per step
| step | work | est. bytes |
|---|---|---|
| poll + guards | bridge from the `.data` stash slot (PI), `iso = bridge+0x18`, `B = iso+0x4ec`, `R = iso+0x74`, derive w/h, compare, early-out | ~40 |
| 1 | extent: 2 computed writes + 4 mirror writes | ~40 |
| 2 | `FUN_100059fb` (cdecl, 5 args, 2 stack locals) | ~30 |
| 3 | `FUN_1000e2c0` (thiscall, 2) | ~15 |
| 4 | `FUN_1000ee29` (thiscall, 3) | ~18 |
| 5-6 | `FUN_10009efb` replay x2 (thiscall, **8 args each**, 6 read from the object) | ~45 each = 90 |
| 7 | `FUN_10018cdf` (thiscall, 5; 2 read from the bridge) | ~30 |
| 8 | `FUN_1000fa36` (thiscall, 2) | ~15 |
| — | prologue/epilogue, register save/restore | ~20 |
| | **total** | **~300 (say 300-350)** |

Comfortably inside the slack. All five SIMSPR-internal targets (`059fb`, `e2c0`, `ee29`, `18cdf`,
`fa36`) are reachable by **rel32 direct call** — position-independent for free. `FUN_10009efb` lives in
GZGraphicD but is called **through the object's own vtable slot `+0x0c`**, so no import and no base
derivation is needed.

### ⭐ Good news that removes a whole sub-project: the 8-arg tuple is RECONSTRUCTIBLE
The harness replays `FUN_10009efb` from a table it built by hooking the function — a pure-DLL cave has
no such table, which looked like it would need a second recording cave. **It does not.**

`FUN_10009efb` writes its params straight to fields `[CONFIRMED @ 0x10009efb]`:
`p1->+0x24, p2->+0x28, p3->+0x0c, p4->+0x10, p5->+0x14, p6->+0x18, p7->+0x3c, p8->+0x40 (byte)`.
And nothing downstream overwrites them: `vt+0x1dc` = `FUN_1001420d` writes **only** `this+0x44`
(the 0x100-byte sub-object) `[CONFIRMED @ 0x1001420d]`, and `vt+0x1e0` = `FUN_100142a2` contains **no
writes** to any of those six fields `[CONFIRMED @ 0x100142a2]`. Both slots resolve identically on the
raster (`+0x1E894`) and blit-dest (`+0x1F328`) vtables.

**So the cave reads `p3..p8` back off the raster and substitutes only the new w/h.** No second cave.

⚠️ **One `[UNCERTAIN]` that MUST be settled before building.** A harness dump printed
`fmt(+0x0c) = 7` while the recorded tuple for that raster carried `p3 = 4`. If `+0x0c` really can hold
a value different from the `p3` last passed, reconstruction is unsafe. **Cheapest resolution: one added
log line comparing `R+0x0c/0x10/0x14/0x18/0x3c/0x40` against the recorded tuple, on a run that is
happening anyway.** Do not build on the reconstruction until that matches.

### ⚠️ The real blocker is NOT bytes — it is the per-frame hook point
**No SIMSPR hook site has been identified** for running the poll each frame on the render thread. The
harness sidesteps this entirely by driving from `WM_EXITSIZEMOVE` on the message thread. Finding a
safe, re-entrancy-tolerant per-frame site is **unstarted desk work** and is a prerequisite for the cave.

### Effort, honestly
8 thiscall invocations plus ~10 field writes, hand-assembled and capstone-verified. The largest cave
this project has shipped is `close_button_quit` at **77 bytes**, and that still needed a
position-independence hardening pass, a re-witness, and an owner hand-test to close. This is **~4x the
size with far more argument marshalling**. Realistic: several assemble/verify iterations plus **2-4
validation leases**, and a WndProc-adjacent crash risk on every one.

---

## Branch B — slim mod DLL (RECOMMENDED)

**The vehicle now exists and its offline gate has PASSED**, from the camera workstream on the same day:
- `re/harness/src/sc3slider.c` -> `re/harness/bin/sc3slider.dll` (130,560 B) — build gate PASSED
- `re/harness/src/slider_launch.c` -> `slider_launch.exe` (121,344 B, PE32 x86) — build gate PASSED
- `re/analysis/SLIDER_DELIVERY.md`; `inject()` copied verbatim from the proven `sc3launch.c` path
- ⭐ **`D-001`'s foreclosure was proxy-specific, not all injection** (`5d65295`) — the route is open

**The resize routine already exists as working C** (`rz_minimal_resize`, validated across 6 runs).
Shipping it = carving it into a slim DLL exactly as `sc3slider.c` was carved from `sc3probe.c`.

What Branch B removes outright:
- no hand-assembly, no capstone verification, no position-independence puzzles
- no slack ceiling
- **no tuple reconstruction needed** — the DLL can keep the recording hook, so the `[UNCERTAIN]` above
  stops being on the critical path
- ⭐ **the GZGraphicD `wmsize_setrect` cave becomes optional** — a DLL can subclass the WndProc in C

Shared with Branch A (not avoided): the **per-frame hook point** still has to be found, though a DLL
may drive it from a subclassed WndProc as the harness already does.

Cost carried: the vehicle owes **one** game-launch validation lease (already queued for the slider).
**Resize would ride the same vehicle, so that validation serves both** — it is not a new cost.

---

## Recommendation
1. **Ship Branch B.** Carve `rz_minimal_resize` + the poll into a slim mod DLL beside `sc3slider.c`.
2. **Keep `wmsize_setrect` as a patch anyway** — it is built, 44 bytes, and useful to anyone running
   stock. Not required by Branch B.
3. **Do not start the cave** unless the owner requires a patch-only, no-extra-EXE distribution. If that
   requirement appears, settle the `+0x0c` `[UNCERTAIN]` and find the per-frame hook site *first* —
   both are cheap, and both gate the expensive part.

**Nothing here was measured in a run. Slack, field offsets and vtable slots are read from the shipped
binaries; the size table is an ESTIMATE and is labelled as one.**
