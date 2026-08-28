# PRE-REGISTRATION — reproduce the v3 crash at MIN ZOOM and CATCH the fault (before the lease)

**Goal.** The headroom census (zoom 3) contradicted the 16384-overflow story. Reproduce the crash at
**min zoom** (the untested worst case) and, instead of a silent death, **catch the exception** to name
its code, address (module+RVA), and which of the 9 steps was executing.

**Instrument (sc3resize crash-hunt build).**
- `SC3RESIZE_MINZOOM=1`: force zoom 0 (via iso `vt+0x38` = SIMSPR+0x6752) before the resize.
- per-step breadcrumb `g_rz_step` (1..9) set before each step.
- `__try/__except` around `rz_do_resize`, filter captures exception code + address; on fault logs
  `*** FAULT CAUGHT *** code=... at MODULE+0xRVA ... executing STEP n`.
- Drive an external `SetWindowPos` to **2048x1152** (over the size that crashed in v3).

**Outcomes.**
| # | reading | meaning |
|---|---|---|
| 1 | `FAULT CAUGHT`, step + module+RVA logged | ⭐ **the real fault is localized** — report the step and address; that names the true cause (overflow vs AV vs which callee) |
| 2 | no fault, resize completes, frame correct at 2048x1152 min zoom | the v3 crash was **NOT** reproduced by size+zoom alone — it was something else (timing? the auto-maximize path?); report and reconsider |
| 3 | process dies with NO `FAULT CAUGHT` line | the fault is **outside** `rz_do_resize` (e.g. later, in the game's own next paint) or not an SEH-catchable exception; report where the log stops |
| 4 | `MINZOOM setzoom slot mismatch` | zoom not forced; the run tests zoom 3 again — note it and do not claim min-zoom coverage |

**Pre-registered reads regardless:** the `MINZOOM` before/after zoom values; the `extent AFTER` cell
plausibility; and the last `g_rz_step` reached.

⚠️ After a caught fault the engine state is half-resized; the process may still die later. The ONE
diagnostic (code/addr/step) is the deliverable — do not interpret anything after the catch.

## Install
Owner build stays live (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`). Mod patches nothing on disk;
`resize_rectfix` (step 9's on-disk companion) is irrelevant here since the DLL does step 9 itself.
