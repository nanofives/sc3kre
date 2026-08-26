# RESULTS — U-068 rect-fix SHIPS as a patched SIMSPR.DLL code cave (2026-08-26)

**Verdict: PASS on every pre-registered criterion.** A patched `SIMSPR.DLL`, loaded off disk with no
injected push, performs the U-068 post-resize present-rect push itself, from a code cave in `.text` slack.
The pre-registered flips both landed: the harness `U068PUSH> BEFORE` count read **1** (stock was **0**), and
**shot B — post-resize, before any harness push, full-present suppressed — renders the full city** where on
stock SIMSPR it was black. No access violation: the cave executes cleanly from the mapped-but-past-
VirtualSize `.text` tail.

## Provenance
- Patched DLL `Apps\SIMSPR.DLL` = `pe_patch.py --recipe resize_rectfix` on shipped (`eec71500…`),
  sha256 **`3841214dfcfa9019f186da9a2886a02b9e846aad9e6af22bdf166d52c826b28d`**, 512000 bytes (length
  preserved). Independently `--diff`-verified 36 bytes / 5 runs before the run. Cave `0x1006149a` (37B over
  zero slack), hook `0x10005f55` (`e8 b4 57 00 00` → `e8 40 b5 05 00`). Both verified live on disk pre-launch.
- Probe `sc3probe.dll` sha256 `da6f20809aae3bc454689cbc336f288c44303e9553dcea4b5554eacb1199e192`
  (**unchanged** from the confirmed rect-push run — no relink, so this is a strict single-variable A/B: the
  only change from `verify/u068_rectpush_test` is the patched DLL).
- Europolis, `-nocom -windowed -fix16 -fitclient -nointro -quiet`, env `SC3PROBE_RESIZE=1
  RESIZETO=1280x1024 RESIZEAT=22 U068SURF=1 U068SRC=1 U068SHOT=1 RESIZE_PUSHRECT=1`, `-AtSec 100`. Own game
  lease (`resizeship`), released `-DirtyOk` (install left on the owner's gentle build). Log
  `re/harness/capture.log`.
- `RESIZE_PUSHRECT=1` kept ONLY to keep the three-shot instrument, the `BEFORE` count log, and the shot-B
  full-present suppression; the harness phase-C push fires AFTER shot B and after the `BEFORE` log, so
  neither reflects it. The variable under test is the patched DLL.

## The measurements

### The cave executed during the forced Init — `U068PUSH> BEFORE count = 1` `[CONFIRMED @ capture.log:1079]`
```
U068PUSH> iso+0x4d0 BEFORE: begin=0x0ED3C388 end=0x0ED3C398 count=1  iso+0x7c=0 items(+0x524)=0
U068PUSH> iso+0x4d0 AFTER push {0,0,1280,1024} via FUN_10010586: ... count=2 (end advanced +0x10 ...)
```
On stock SIMSPR the confirmed run logged this SAME line as `count=0` (`u068_rectpush_test/RESULTS.md`). Here
it reads **1** — the code cave ran inside the harness's forced Init `FUN_10005b42` and its `push_back` took,
before the harness phase-C push (which then made it 2). This is the direct witness that the patch, not the
probe, filled the list. The construction Init also runs the cave, but the ctor's own push is erased by that
Init and the cave re-adds exactly one, so pre-resize state is count 1 (unchanged) — confirmed by shot A.

### Shot B flips BLACK → CITY — the shipping witness
- **Shot A** (`shot_01.bmp`, 1024x768, pre-resize control): full Europolis, 98.3% non-zero. Instrument sound.
- **Shot B** (`shot_02.bmp`, 1280x1024, post-resize, BEFORE phase-C push, full-present suppressed): **the
  full Europolis city at 1280x1024**, 98.6% non-zero, viewed directly (`.happy-share/…/
  resize_shot_B_postresize_prepush.png`). On stock SIMSPR this exact shot was BLACK (a 113 KB highly-
  compressible PNG). The patched DLL renders the resized view through the game's OWN per-frame loop
  (`FUN_1000e058` over the cave-pushed rect), with no injected push.
- **Shot C** (`shot_03.bmp`, 1280x1024, post phase-C push): full city, 98.6%.

### No fault — cave executes from past-VirtualSize `.text`
The game ran the full duration and was killed on schedule; no `0xC0000005`, no `FAULTED` (the only
"exception" token in the log is inside the U068SURF arming description). The owner's requested execution
witness: the trampoline at `0x1006149a` (past `.text` VirtualSize `0x6049a`, inside the RX page based at
`0x10061000`) ran without an unmapped-page or bad-trampoline fault.

## Attribution
Single-variable against `u068_rectpush_test` (same probe, same env, same city/camera/window): the only
change is the patched DLL, and the only behavioural deltas are `BEFORE` count `0→1` and shot B `black→city`.
So the code cave IS what restores the post-resize present — measured, not inferred.

## Honest caveats (all expected, none an item-1 regression)
1. **HUD does not reflow** — toolbar/status/minimap laid out for 1024x768, stray magenta widget bottom-
   right. Separate item-2 defect (`FUN_100270e5`, no branch above width 800). The center llama is the game's
   own loading overlay.
2. **This is still the harness driving the resize** (forcing Init). Whether a REAL shipped resize reaches
   Init is item 3 — and the answer already established is NO (fixed frame, WM_SIZE → GZGraphicD vt+0x30, not
   iso Init). So this run proves the FIX ships and executes correctly; it does not by itself make a hand-
   resize reach the fix. #3 is the remaining design work (owner-scoped, static).
3. **Upward resize only, 1024→1280.** Downward (`U-069`) unexercised. The cave pushes `{0,0,iso+0x5c,
   iso+0x60}` = the new dims Init stored, so it is dimension-correct for a downward resize too, but that is
   untested.

## Bonus #3 evidence captured this run
- `RZ> window vt+0x30 = 0x030185F5 (GZGraphicD.dll+0x185F5)` `[capture.log:120]` — resolves the previously
  `[UNCERTAIN]` WM_SIZE handler target to **GZGraphicD FUN_100185f5**.
- `RZ> window … style_flags(+0x10)=0x0000001B` `[capture.log:119]` — confirms the fixed-frame mask 0x1B.
- `RZ> captured SetMode tuple: … w=1024 h=768 …` `[capture.log:70]` — the device SetMode path (0x10015e3d).

## State left behind
Owner's three-recipe gentle build re-staged and verified LAST (scroll 8.0 ×5, drag `fc`, dead zone 2.0;
`--diff` 8 runs / 9 bytes; sha `e63ec800…`). Lease released `-DirtyOk`. Probe unchanged; no harness claim
taken (no relink). Patched build kept at `verify/resize_rectfix_ship/SIMSPR.DLL.resizefix` (game-derived,
not committed). Recipe `resize_rectfix` committed in `re/tools/pe_patch.py` (`73f6208`).
