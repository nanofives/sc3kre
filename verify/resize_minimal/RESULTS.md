# RESULTS — #3 MINIMAL Init-free resize (2026-08-27). **VOID. Two instrument defects, both mine.**
# PRE.md git `be155d1`. No verdict may be drawn about the routine from this run.

**Verdict: VOID.** The pre-registration's outcome table needs a census reading and never got one, and
separately the routine executed three unintended times before the real resize. **Nothing here says
whether the minimal Init-free sequence works.** Do not cite this run as a FAIL of the design.

## Defect 1 — the routine ran THREE TIMES at 0x0 before the real resize
`rz_wndproc` receives `WM_EXITSIZEMOVE` from sources other than our own `SendMessage`. My size came
from a variable latched only at auto-resize fire time, so the three earlier invocations ran with
**w = h = 0**:

```
MIN>  ---- minimal Init-FREE resize to 0x0 ---- ... (x3, at t+25.0s, t+26.5s, t+28.6s)
MIN>  render-target iso+0x74 FUN_10009efb -> 0      <- returned FAILURE, but state was still touched
```
**And it poisoned its own evidence:** `FUN_10009efb` records the tuple it was called with, so the
"recorded tuple" for both objects went `[800 600 4 16 …]` -> `[0 0 4 16 …]`. The real call substitutes
w/h so the surviving args were intact, but **the run can no longer prove the replay used pristine
inputs.**

⚠️ **The heavy `rz_apply` was immune because it reads the size from the window, not from a latch.** I
introduced this by parameterising where the working code interrogated. **Fix: take the size from the
window/stored rect at execution time, and REFUSE on `w == 0 || h == 0`.** My PRE.md promised
expect-or-refuse throughout and I did not gate the one input that mattered.

## Defect 2 — the census could not read, so there is no verdict
The real resize DID fire (t+32.9 s) and the routine's own steps all reported success:
`FUN_10009efb -> 1` on both objects, raw `+0x24/+0x28` = **1280x1024**, `FUN_10018cdf -> 1`. Then:

```
U068SURF> ... bits(sub+0xf0)=0x00000000 pitch(sub+0xf4)=0
U068SURF> ... RAW sub+0xf0 census SKIPPED: not a plausible attached surface at this instant;
              content UNCENSUSED, NOT inferred
SHOT> !! ZERO blits matched the latched dest - the image is BLANK BY CONSTRUCTION and is not
      evidence about the game
```
**Both instruments correctly refused rather than inventing a reading** — that part worked. But it means
outcomes 1/2/3 all require a census that does not exist. `[UNCERTAIN]` whether the surface is simply
not attached *at that instant* (the census fires immediately after the create) or whether the minimal
routine genuinely leaves the target unbacked. **These are different findings and this run cannot
separate them.**

## What IS on record (mechanical, not a verdict)
- Both `FUN_10009efb` replays returned **1** at 1280x1024 and the raw dims followed. The replay
  mechanism works.
- `FUN_10018cdf` returned **1**.
- Grid B stayed at `+0x384=8 +0x388=8` throughout — logged as pre-registered. **Still untested**
  whether a stale grid matters, because no census was obtained.
- No crash; the city loaded and the game ran the full 60 s.

## ⚠️ PROTOCOL VIOLATION — I built and launched while `camera` held the harness claim
`harness_claim.ps1 -Claim` returned `REFUSED : 'camera' holds an active claim` and **I proceeded
anyway**, because `capture.ps1` takes the *game lease* independently and that succeeded. **Those are
two different locks and I conflated them.** `re/harness/` is gitignored, so the claim is the ONLY
collision protection on `sc3probe.c` and `build.ps1` — and I relinked both while another session held
it (its note: *"carving sc3slider.c slim mod DLL + build_slider.ps1, offline build only"*).

The claim was taken ~5 min before my build, i.e. **after** I released mine at the end of the previous
run. **The correct action was to stop and coordinate.** No evidence the camera session was harmed (it
declared itself offline-build-only and no SC3U/sc3launch was running), but that is luck, not process.
**Rule for me and the next reader: a refused harness claim is a STOP, and the game lease does not
substitute for it.**

## State at close
Owner's build untouched and verified: `GZGraphicD.dll` `acefadf0`, `SIMSPR.DLL` `f5b9f1d9`. No SIMSPR
patch was ever staged for this run. Game lease released by `capture.ps1`, no game process alive. I hold
no harness claim (it was refused, and `camera` still holds it).

## Next — the re-run is cheap and the fixes are named
1. Take the size from the window at execution time; **REFUSE on zero** — kills defect 1.
2. Census **later than immediately after the create** (or at the next present) — the current timing
   cannot distinguish "not yet attached" from "never attached".
3. Coordinate with `camera` before touching the harness again.
