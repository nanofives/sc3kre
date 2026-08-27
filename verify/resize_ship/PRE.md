# PRE-REGISTRATION — `sc3resize` slim mod DLL, offline gates + the validation run
# (committed BEFORE any lease)

## What was built (Branch B of `re/analysis/RESIZE_DELIVERY_COST.md`)
- `re/harness/src/sc3resize.c` -> `re/harness/bin/sc3resize.dll`
- `re/harness/src/resize_launch.c` -> `re/harness/bin/resize_launch.exe`
- `re/harness/build_resize.ps1`

A carve of the validated minimal Init-FREE resize routine (`verify/resize_minimal/`, run 6 PASS)
into a shippable DLL, on the vehicle the camera workstream proved (`SLIDER_DELIVERY.md`,
`D-001` foreclosure is proxy-specific). Logging and detour-installer blocks are **verbatim** from
`sc3slider.c`, which took them verbatim from `sc3probe.c`.

## OFFLINE GATES — all PASSED before any lease was requested
| gate | result |
|---|---|
| builds clean, no warnings | **PASS** |
| `sc3resize.dll` is PE32 x86 with the DLL flag | **PASS** (machine `0x014C`, magic `0x10B`) |
| `resize_launch.exe` is PE32 x86 console | **PASS** |
| imports are KERNEL32 + USER32 only | **PASS** (no CRT DLL dependency, `/MT`) |
| both hook prologues decodable, >= 5 stealable bytes, no rel32 | **PASS** — both are `mov eax, imm32`, exactly 5 bytes |
| loader injects `sc3resize.dll` by name from its own directory | **PASS** |

⭐ **One bug was caught by verification before it ever ran.** The bridge-capture handler read ECX
from the pushad frame at `f[2]`, derived by reasoning about PUSHAD order. The authoritative layout
in `sc3probe.c:8650-8658` is **`f[7] = ECX`** (`f[0]` eflags, `f[1..8]` edi..eax, `f[9]` return
address, `f[10..]` args). **Fixed to `f[7]` and the source now cites sc3probe rather than
re-deriving.** At `f[2]` the mod would have captured ESI as the bridge and dereferenced garbage.

## What is NOT yet established — this needs the lease
**Nothing in this mod has been run.** The routine it carries is validated, but *this binary*, this
injection path, and this per-frame poll are not.

| # | reading | verdict |
|---|---|---|
| 1 | log shows bridge captured, poll armed, and on resize the full sequence runs with content extent matching the new client size | ⭐ **PASS** |
| 2 | injects and logs but the bridge is never captured | **FAIL** — hook site or `f[7]` wrong; do not blame the routine |
| 3 | bridge captured but the poll never fires | **FAIL** — the `0x18c58` heartbeat is not per-frame in a shipped context |
| 4 | sequence runs but the frame is wrong (terrain-only, black, or old extent) | **FAIL**, and the step-by-step log localises which of the 8 steps regressed |
| 5 | crash or hang | **FAIL.** A hang at `FUN_10018cdf` specifically would mean the grid-B step did not take |

**Pass bar carries the lesson from runs 2 and 5:** extent alone is not enough and "not uniform" is
not enough. Content must match the client size **and** be comparable in colour richness to a
known-good frame.

## Known gaps, recorded before the run
- ⚠️ **The WndProc subclass is UNTESTED.** It replaces the GZGraphicD `wmsize_setrect` patch under
  this mod. If it does not work, `wmsize_setrect` remains available as the fallback.
- ⚠️ **`rz_enum` picks the first visible window of this process.** That is a heuristic, not an
  identity check; the harness uses `find_game_window`. If the wrong window is picked the poll reads
  the wrong client rect. **Not yet hardened.**
- Downward resize (`U-069`) untested, as ever.
- No claim about the DirectDraw primary (`D-004`).
- The mod does **not** supply step 9 (the present rect); that is the separate `resize_rectfix`
  patch and must be staged for a complete result.

## Install state
Owner's build untouched: `SIMSPR.DLL` `f5b9f1d9`, `GZGraphicD.dll` `acefadf0`. **The mod is a DLL —
it patches nothing on disk.** Harness claim taken as `resize` for the build and released after.

---

# AMENDMENT — the validation run's METHOD and its honest limits (before the lease)

**This run does NOT go through `capture.ps1` or the probe.** The mod is a standalone DLL with no
census, no blit-mirror and no `-shot`. So the instrument is different from every previous run in this
workstream, and the outcome table must be read accordingly.

**Method:** acquire the lease manually -> `resize_launch.exe -kill 75` (its own injector) -> wait for
the city -> resize the game window **externally** from PowerShell (`SetWindowPos`), which is a *real*
`WM_SIZE` from outside the process -> screenshot the window -> read `sc3resize.log`.

⚠️ **Externally driving the resize is a BETTER test of the shipped path than the harness was** (the
harness posted its own `WM_EXITSIZEMOVE`), but the screenshot is a **new, unvalidated instrument**.
Prior work (`D-004`) records that this environment cannot be assumed to have a usable foreground
display. **If the screenshot comes back black or blank, that is a fact about the screenshot, NOT about
the mod** — exactly the `capture.ps1` silent-failure trap this board already paid for twice.

## What this run CAN and CANNOT decide
| pre-registered outcome | decidable here? |
|---|---|
| 2 — injects but no bridge captured | **YES**, from the log |
| 3 — bridge captured but poll never fires | **YES**, from the log |
| 5 — crash or hang | **YES** (a hang at `FUN_10018cdf` = the grid-B step did not take) |
| 4 — sequence runs but values are wrong | **PARTLY** — the log carries extent before/after, the cell-size plausibility gate, both `FUN_10009efb` returns and dims, `FUN_10018cdf`'s return, `FUN_1000fa36` |
| 1 — full PASS incl. content richness | **NO, not by census.** Only by screenshot, which is unvalidated |

**So the honest ceiling for this run is: WIRING VALIDATED, pixels pending.** A full pixel verdict needs
either a census added to the mod (dev-only, gated) or a probe-side re-run. **Do not report a screenshot
as a census.** If the wiring passes and the screenshot is unusable, the correct verdict is *"wiring
validated, pixel verdict still owed"* — not a PASS and not a FAIL.

`resize_rectfix` (step 9) is **already live** in the owner's four-recipe SIMSPR `f5b9f1d9`, so the
sequence is complete without staging anything.
