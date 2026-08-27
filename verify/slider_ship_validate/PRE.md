# PRE-REGISTRATION — standalone slider ship validation (loader + slim DLL + INI)

Written and committed BEFORE the lease. Owner: `camera`. Queued as a rider on the next SC3 game
lease (run queue: `BOARD.md`). Camera is priority 4 — this does NOT take a lease of its own; it slots
in when a sibling frees the lease, or the owner runs it by hand on a real display.

## Scope — what this run does and does NOT prove

Already settled, NOT re-tested here:
- The scroll-speed **arithmetic** (value → camera movement) is **C3** (`verify/scroll_patch_test`
  S1/S2/S3, and the within-process A/B/A). `pref_patch_rdata`/`pref_patch_live` write the exact bytes
  already proven to move the camera.
- The slider **UI** (a "Camera Scroll Speed" slider appears in Preferences and drags) was witnessed
  via the harness `-pref` (dragged 21.25→128.0, shots `pref1_202726.png`/`pref3_005306.png`,
  `CAMERA_MODDING.md`). The slim DLL's `pref_*` functions are copied VERBATIM from that same code.

This run validates ONLY the **shippable wiring delta** — the parts that are new or first-run-standalone:
1. `slider_launch.exe` injects `sc3slider.dll` (standalone loader, not the harness `sc3launch`).
2. The slim `DllMain` + `slider_watcher` install the GZGraphicD `0x10018c58` heartbeat **without the
   harness env/gzlog plumbing** (the standalone-heartbeat path — coded for this, never run standalone).
3. `slider.ini` is read on boot and written back on a drag (brand-new code, never run).
4. The GZ window/vtable lookups still resolve in the slim standalone context.

## Fixture & install

- Fixture: `Cities/Europolis.sc3` (non-Farmsville, known-good in-city render; boots to a live view so
  the `live=ok` leg is exercisable).
- Install: **STOCK both modules** — restore `Apps/SIMSPR.DLL.shipped` (sha `eec71500…`) and
  `Apps/GZGraphicD.dll.shipped` before the run. This matches the ship assumption (an unmodified game)
  and makes any observed scroll change the slider's, not a residual patch. Verify stock before:
  `SIMSPR` scroll `32.0`×5 `@0x10067690`, divisor `fe` `@0x10043a5e`, dead zone `12.0` `@0x100676a4`.
- Artifacts (dev layout): `re/harness/bin/slider_launch.exe`, `re/harness/bin/sc3slider.dll`, and a
  test `re/harness/bin/slider.ini` containing `[camera]` / `scroll_speed=64` (double shipped 32, and
  distinct from the owner's live 8, so the boot value is unambiguous in the log).
- Launch: `re/harness/bin/slider_launch.exe -- "Cities\Europolis.sc3"` (the loader finds
  `SC3U.exe` at `<root>\Apps`). NOT `capture.ps1`/`sc3launch`. Log: `sc3slider.log` beside the DLL
  (or `SC3SLIDER_LOG`).

## Leg A — boot + heartbeat wiring (from `sc3slider.log`, reaches only the MENU)

A sibling holding a headless lease can carry this leg: it needs only that the game reach the main
menu, no Preferences interaction.

- **CONFIRMS**, the log contains, in order:
  1. `### sc3slider loaded - Camera Scroll Speed slider, boot value 64.000` (DllMain + INI read).
  2. `### PREF: boot value 64.000 applied to SIMSPR .rdata (ok)` (boot apply once SIMSPR maps).
  3. `### PREF: heartbeat installed at GZGraphicD(base 0x........)+0x18c58 - slider armed, scroll
     speed 64.000`. The logged base may be `0x10000000` OR a relocated base — **either is a PASS**
     (position-independent target = base + `0x18c58`); a relocated base that still installs is the
     stronger witness.
- **FALSIFIES:** `loaded` line absent (injection/DllMain failed) · `.rdata` apply logs `skip`
  (SIMSPR not found / write refused) · `FAILED to install the heartbeat` (undecodable prologue or
  relocation) · any `C0000005`.
- **Plausible-but-wrong:** `slider_launch` prints `injected ...` but no `sc3slider loaded` line ever
  appears → the DLL loaded but DllMain did not run/log → report as an init failure, do not gloss.

## Leg B — slider appears, drags, persists (needs Preferences OPEN, real display)

The slim DLL has no UI automation, so opening Preferences is manual (owner hand-test) or via a
harness-driven session that can navigate the menu. Decisive for the GZ-resolution unknown.

- **CONFIRMS:**
  1. On opening Preferences: `### PREF: slider id=0x02F95B12 ... -> add OK` and
     `### PREF: label id=0x02F95B13 "Camera Scroll Speed" ... -> add OK`, and the slider + caption are
     **visible** in the window (screenshot).
  2. Dragging the slider logs `### PREF: scroll speed <- N (slider M) rdata=ok live=ok` and the arrow/
     edge scroll speed **visibly changes** with it.
  3. After quitting, `slider.ini` `scroll_speed` == the last value the slider was left at (write-back).
  4. Relaunching reads that value: `### sc3slider loaded ... boot value <persisted>` (round-trip).
- **FALSIFIES:** `no widget factory` · `factory has no vt+0x50` · `CreateSlider returned null` ·
  `add FAILED` · `add OK` logs but no slider visible.
- **Plausible-but-wrong (THE real unknown):** Leg A passes (`heartbeat installed`) but on opening
  Preferences NO `add OK`/`add FAILED` line appears at all → the heartbeat tick is not reaching
  `pref_tick`, or the tree walk finds no Preferences window in the slim context → report as the
  standalone-wiring gap this run existed to find; do NOT dress it as "slider just didn't show."

## Post-run (MANDATORY — BOARD standing rule)

Re-stage the owner's live build and verify, then delete/neutralise the test `slider.ini`:
```powershell
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL.shipped --recipe scroll_speed=8 --recipe drag_divisor=4 --recipe drag_deadzone=2 --recipe resize_rectfix --out SIMSPR.DLL.4
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL.shipped --diff SIMSPR.DLL.4   # gate: 13 runs / 45 bytes
Copy-Item SIMSPR.DLL.4 Apps\SIMSPR.DLL -Force
py -3.12 re/tools/pe_patch.py Apps\GZGraphicD.dll.shipped --recipe resizable_frame --recipe close_button_quit --out GZGraphicD.dll.rf
py -3.12 re/tools/pe_patch.py Apps\GZGraphicD.dll.shipped --diff GZGraphicD.dll.rf   # gate: 69 bytes / 7 runs
Copy-Item GZGraphicD.dll.rf Apps\GZGraphicD.dll -Force
```
Verify live: `SIMSPR` scroll `8.0`×5, dead zone `2.0`; `GZGraphicD` `@0x10018570` = `cd`. The slider
mod is runtime-only and on-disk stock, so no slider artifact needs removing from `Apps\`.
