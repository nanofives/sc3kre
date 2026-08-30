# PRE-REGISTRATION — VEH crash logger for the zoom-after-resize crash

Instrument only, no behavior change. Committed before the run.

## Why

After the render fix (step 11, `verify/resize_setdataview/`), zooming in after a resize crashes the
game. It is uninstrumented: our `__try/__except` wraps only the resize routine (not the game's zoom
path), and SC3U's top-level handler swallows the fault so Windows logs no WER. Only a process-wide
handler can capture it. Methodology: "build the fault-catcher first" (the §4 resize-crash approach).

## The change (`re/harness/src/sc3resize.c`)

`AddVectoredExceptionHandler(1, rz_veh)` at load. `rz_veh` logs, for any hardware fault (AV
`0xC0000005`, illegal/priv instr, div0, stack overflow, in-page):
- `*** VEH FAULT *** code=... at MODULE+0xRVA (base ...)` (faulting instruction, resolved via
  `rz_modstr`),
- `VEH access=READ/WRITE/EXEC addr=0x...` (the address touched),
- `VEH regs eax..esp`,
- `VEH [esp]=0x... -> MODULE+0xRVA` (top-of-stack return, to name the caller).
Returns `EXCEPTION_CONTINUE_SEARCH` — the game's own handling is unchanged (it will still exit). No
other code changes. Filtered to hardware codes to avoid first-chance C++/debug noise.

## Expected outcome

Not a pass/fail test - a localizer. Reproduce the zoom crash and the log should show a `*** VEH FAULT ***`
line naming the faulting `MODULE+RVA` + access address. That address is the input to the actual fix
(most likely another grid-B clamp or a grid resize on the zoom path `FUN_10006752`). If the crash occurs
with NO `VEH FAULT` logged, the fault is not a hardware exception we filter for (revisit the filter).

## Protocol

Harness claimed `handtest`. Owner launches, resizes ONCE, then ZOOMS IN to reproduce the crash, and
sends the log. Prior log archived `re/harness/sc3resize_handtest.step11a.log`. Install (`SIMSPR
f5b9f1d9`, `GZGraphicD acefadf0`) verified before/after; no on-disk change.

## STATUS

Built + string-verified (`VEH crash logger installed`, `VEH FAULT`, `VEH access=`, `VEH regs` present;
render fix step 11 retained; PE32; install intact). Pre-registered. Awaiting the owner reproduction.
