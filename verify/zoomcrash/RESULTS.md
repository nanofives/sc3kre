# RESULTS: CITYZOOM step kills the game silently (task zoomcrash, 2026-10-25)

Worktree `Simcity_wt_zoomcrash` (branch `child/zoomcrash` from main 54bf548). Test tree `Simcity_stock_zoomcrash`, all 7 mods
+ version.dll built from the worktree, Europolis, posted input only (no cursor, keyboard or foreground), HUD scale Auto.
Pictures: `MAIN\verify\zoomcrash\owner_shots\`. Raw logs and traces: `verify\zoomcrash\runs\` (local, not committed).

## Cause

The bug is a stack imbalance in sc3resize's zoom wrapper. It has nothing to do with the client size or the odd height.

1. ZOOMCENTER replaces iso view vtable slots +0x60 / +0x64 (SIMSPR 0x100633f0 / f4) with `zc_wrap0` / `zc_wrap1`. When
   CITYZOOM takes a step (`cz_zoom` returns 1) the wrapper skips the original and returned with a bare `ret`.
2. The originals FUN_1001d2d6 (zoom in) and FUN_1001d365 (zoom out) end in `ret 4` (bytes `5b 5f 5e c2 04 00`)
   [CONFIRMED @ SIMSPR 0x1001d362]. The caller, ZoomIn FUN_10042d8a, pushes one argument
   (`ff 75 08 8b 01 ff 50 60` = push [ebp+8]; call [eax+0x60]) [CONFIRMED @ SIMSPR 0x10042e13].
   So every CITYZOOM step left 4 bytes on the stack.
3. Frida trace (`runs/r6_stalk.txt`): at SIMSPR+0x42e1b, after the call, ESP = 0x1afcc0 on the stock path (zoom 3 -> 4)
   and 0x1afcbc after the skipped x1 -> x2 step, with the stray argument (1) at [esp].
4. FUN_10042d8a's epilogue is `pop esi; pop ebx; ... leave; ret 4` [CONFIRMED @ SIMSPR 0x10042f17]. With ESP 4 low, it
   returns ESI = 1 and EBX = the caller's old ESI. EBP and the return address stay correct, so the bad registers travel up.
5. On the minimap-button path, the frame above is sc3undo's thiscall helper: `mov ebx, esp` ... `call [ebp+0xc]` /
   `mov esp, ebx` / `pop edi` (sc3undo.dll +0x6611 .. +0x6630). After `mov esp, ebx`, ESP holds a value that is not on
   the stack. The next pop faults, and the kernel cannot push an exception frame on that ESP, so it ends the process with
   0xC0000005. No VEH, no Frida exception handler, no ExitProcess / TerminateProcess call and no WER event. The last
   block Stalker logged before the kill is sc3undo.dll+0x662b.

Measured: exit code 0xC0000005 on every unfixed run (`zoomcrash_run.py` prints it). Of 6 unfixed runs with the minimap
button, 5 crashed on the x1 -> x2 step (2560x1351 4/4, 3808x1984 1/1). In one run the second click never reached the zoom
slot, so no step was taken.

Why it looked size-dependent: the earlier "3840x1984 works" came from the cityzoom child's 2026-10-22 test, which pressed
the '+' key (RESULTS cityzoom row 2), not the minimap button, so its call chain did not include the frame that restores
ESP from EBX. The uiaudit 3840 log never took a zoom step. 1920x1080 allows no x2 (cz_max = 1), so cz_zoom returns 0,
the game's own method runs and nothing is skipped.

## Fix

`re/harness/src/sc3resize.c`: `zin_done` / `zout_done` end in `ret 4` (the original's return), with the evidence in the
comment above `zc_wrap0`. No other change. The off switch is unchanged: with `[view] zoomextra=0` / `SC3RESIZE_CITYZOOM=0`
cz_zoom returns 0 and the wrapper jumps to the original as before.

## Tests (fixed build, minimap zoom buttons by posted clicks, `re/tools/zoomcrash_run.py`)

| client | steps taken | scroll at x2 | crashes |
|---|---|---|---|
| 2560x1351 (owner's maximized class) | x1->x2 4x, x2->x1 4x, plus game zooms 3<->4 | 3 right-drags | 0 |
| 2561x1351 | x1->x2 2x, x2->x1 2x | 2 | 0 |
| 2560x1350 | x1->x2 2x, x2->x1 2x | 2 | 0 |
| 3808x1984 (3840 request, capped by the screen) | x1->x2 3x, x2->x3 1x, x3->x2 1x, x2->x1 3x | 2 | 0 |
| 2560x1440 | x1->x2 2x, x2->x1 2x | 2 | 0 |
| 2400x1299 (odd height) | x1->x2 2x, x2->x1 2x | 2 | 0 |
| 1920x1080 (no x2) | none, game zoom only | 2 | 0 |
| 2560x1351, `SC3RESIZE_CITYZOOM=0` | none (off switch) | none | 0 |

Pictures: `01_x2_2560x1351_after_step.png`, `02_x2_2560x1351_after_scroll.png`, `03_x3_3808x1984.png`,
`04_x2_2560x1350.png`, `05_x2_2561x1351.png`. The view renders at the step and after scrolling, and the HUD is intact.

### Both callers: minimap buttons and the +/- keys (orchestrator request)

Posted numpad +/- keys (VK_ADD / VK_SUBTRACT, no focus) reach the zoom step. Measured on the UNFIXED build first, at
2560x1351: 2 key steps in and 2 out, no crash (`runs/u2`). That is the luck described above: the key path reaches the
same 4-byte imbalance, but no frame above it restores ESP from EBX. The fixed build, alternating buttons and keys:

Script per size (28 items): buttons in, in, key -, key +, 2 right-drags, button out, key +, button in, key -, button out,
key +, 1 right-drag, key -, button in, button out. An input at x1 that zooms out goes to the game's zoom 3, so not every
input is a CITYZOOM step. Steps counted from the log.

| client | CITYZOOM steps (in / out) | scroll at x2 | crashes |
|---|---|---|---|
| 2560x1351 | x1->x2 3 / x2->x1 3 | 3 | 0 |
| 2561x1351 | x1->x2 3 / x2->x1 3 | 3 | 0 (a first run on a loaded PC drew 3 frames/s, took no steps, and did not crash) |
| 2560x1350 | x1->x2 4 / x2->x1 4 | 3 | 0 |
| 3808x1984 | x1->x2 5, x2->x3 1 / x3->x2 1, x2->x1 5 | 3 | 0 |

The one `VEH FAULT` line in every log (fixed, unfixed and earlier runs alike) is code 0xC0000096 at SC3U.exe+0x84122
about 200 ms after start. That is the game's own startup probe and has nothing to do with zooming.

The mouse wheel at zoom 4 was not driven (posted wheel messages do not zoom, cartrips3 R2). It goes through the same
wrapper, so the fix covers it, but this is unverified: needs owner check.

## Audit: every stub / hook in the 7 mods for the same bug class

The question for each hook that returns on its own (a skip or early-out path, or a C function that replaces the
original): does it pop the same stack bytes as the code it stands in for?

### Runtime audit (`re/tools/hook_audit.py`, all 7 mods + version.dll, Europolis loaded, after zoom steps)

Every loaded game module (and DDRAW / USER32 / GDI32 / KERNEL32 / msvcrt) is diffed against its disk file relocated to
the runtime base. Every rel32 jmp / call into mod code and every pointer slot (vtable, IAT, function pointer) that held a
code pointer on disk and now points into a mod is an install point. The original's `ret N` comes from a disassembly of
the disk code (IAT: the live export, following the kernel32 -> kernelbase stubs). The hook's `ret N` and tail jumps come
from a recursive-descent walk of the mod code, which follows `jmp [g_orig]` through memory, so chains through other mods'
hooks are walked too.

| build | install points | distinct hook entries | ok | own call/ret patches | CHECK | MISMATCH |
|---|---|---|---|---|---|---|
| unfixed (main 54bf548) | 319 | 154 | 309 | 5 | 3 | **2: SIMSPR+0x633f0 / +0x633f4 (zc_wrap0 / 1): ours `ret`, original `ret 4`** |
| fixed (this branch) | 319 | 154 | 311 | 5 | 3 | **0** |

Per mod (fixed build): sc3netmod 167 (97 IAT file-API wrappers, 45 call-site retargets, 18 slots, 7 jmps), sc3perf 47,
sc3undo 38 (vtable slots), sc3resize 38, sc3bigcity 13, VERSION.dll 9 (the loader's export proxies), sc3simrun 6,
sc3overscroll 1. The unfixed run flags exactly the bug found here and nothing else, so the audit detects this class.

The 3 CHECK rows are indirect call sites, where the callee is not known statically. I checked them by hand:
- SC3U.exe+0x25a99 `call [edx+0x100]` -> sc3simrun freeze_thunk (skip `ret 4`). The caller pushes one argument
  (`push eax` at 0x00425a96) and the street car Tick STRTSIM FUN_1001d2c0 ends in `ret 4`. The caller reads its locals
  through ESP (`mov eax, [esp+0x28]` at 0x00425a92, in the same loop), so every Tick it calls must pop exactly that one
  argument, or the stock game would break. Match.
- SIMDSTR+0x1e2e5 / +0x1e2f4 `call [eax+0xa8]` / `[eax+0xac]` -> sc3bigcity dstr_width_256 / dstr_height_256 (`ret`).
  No arguments are pushed before either call (ecx = esi only). The stubs make the same virtual call and return. Match.
The 5 call/ret patches (sc3simrun anim_stub x3 replacing `fldz; fstp [ebp-8]`, sc3bigcity spr_rec_release / realize)
are `call` + plain `ret` pairs that keep the stack as it was. Match.

Limit: the runtime audit sees what is installed at the moment of the dump. Hooks installed on demand (when a dialog
opens, for example) or a replaced vtable pointer inside a heap object are not seen. The static pass below covers every
naked stub in the source regardless.

### Static pass: every `__declspec(naked)` stub in the source

Stubs that only jump back into the original (no own `ret`) cannot have this bug and are listed by name only. Original
`ret` forms below are from the anchored files, by disassembly.

| mod | stub | stands in for | original | ours | verdict |
|---|---|---|---|---|---|
| sc3resize | zc_wrap0 / zc_wrap1 skip path | SIMSPR FUN_1001d2d6 / FUN_1001d365 (iso vt+0x60/+0x64) | `ret 4` | was `ret`, now `ret 4` | **FIXED** |
| sc3resize | dirtclip_stub skip | SIMSPR FUN_1000d0c5 entry | `ret 8` | `ret 8` | ok |
| sc3simrun | freeze_thunk skip | `call [edx+0x100]` at SC3U 0x00425a99 (agent Tick) | `ret 4` | `ret 4` | ok |
| sc3simrun | tick_entry skip / swap | STRTSIM FUN_1001f44a entry | `ret 4` | `ret 4` | ok |
| sc3simrun | anim_stub | 5-byte `fldz; fstp` replaced by a call | (call/ret pair) | `ret` | ok |
| sc3bigcity | dims_hook | SIMINIT+0xc09c body (`... c2 04 00` in its expect bytes) | `ret 4` | `ret 4` | ok |
| sc3bigcity | dstr_width_256 / dstr_height_256 | `call [eax+0xa8/0xac]`, no stack args | `ret` | `ret` | ok |
| sc3bigcity | spr_rec_release / realize | in-line code replaced by a call | (call/ret pair) | `ret` | ok |
| sc3bigcity | spr_apply_journal (C, `__fastcall`, no stack args) | SIMSPR FUN_10008dd4 | `ret` | `ret` | ok |
| sc3perf | ftol_fast | msvcrt `_ftol` (Apps and SysWOW64 copies) | `ret` | `ret` | ok |
| sc3perf | fast_ceil (falls back to the real ceil) | SimTransit IAT `ceil` (cdecl) | `ret` | `ret` | ok |
| sc3perf | list_count_fast | SIMCITY FUN_10001db0 (`... c3` in its expect bytes) | `ret` | `ret` | ok |
| sc3netmod | id_base_thunk | `call FUN_1001a93d` sites (SIMNTWRK) | `ret 4` | `ret 4` | ok |
| sc3netmod | get5c_hook | SIMNTWRK FUN_1000c2fc | `ret 4` | `ret 4` | ok |
| sc3netmod | get30_hook | SIMNTWRK FUN_1000cc83 | `ret` | `ret` | ok |
| sc3netmod | pred_wrap0..15 | predicate vt+0xc, 15 SIMNTWRK functions (FUN_1001ab26 .. FUN_1001b2e0) | `ret 4` (all 15) | `ret 4` | ok |
| sc3netmod | load_rec_thunk | `call FUN_1000d6b3` (SIMNTWRK) | `ret 0xc` | `ret 0xc` | ok |
| sc3netmod (bridge) | nb_a93d_thunk | FUN_1001a93d | `ret 4` | `ret 4` | ok |
| sc3netmod (bridge) | nb_bc7_thunk / nb_aaba_thunk | FUN_10009bc7 / FUN_1000aaba | `ret 8` | `ret 8` | ok |
| sc3netmod (lanes) | ld_stub -> ld_select (C `__fastcall`, 6 stack args) | SimTransit FUN_1000755e entry | `ret 0x18` | `ret 0x18` | ok |

Jump-back only (no own return): sc3resize lcenter_stub, tip_stub1/2, zc_zoom_stub, zc_rot_stub, zc_wrap2/3; sc3perf
spr_sleep_stub, smooth_dtor_stub, mt_706a_stub, mt_9242_stub, lf_2120_stub, list_find_both_ends, day_stub; sc3netmod
save_rec_thunk, save_begin_hook, save_end_hook, load_begin_hook, ramp_class_thunk, nb_collapse_wrap, nb_xcross_thunk,
rb_tramp; sc3overscroll translate_hook, translate_hook_all; sc3bigcity depth_hook, size_hook; sc3simrun coord_thunk,
strip_entry. sc3undo has no naked stubs.

A related shape to watch: rz_thiscall / rz_thiscall_ret (sc3resize) and sc3undo's helper at +0x6600 restore ESP from
EBX after the call. That keeps them safe from a wrong argument count in their own call, but it makes them the place where
a callee that clobbers EBX turns into a silent kill. That is how this bug surfaced. They are correct as written.

## Tools added (worktree `re/tools/`)

- `hook_audit.py`: the runtime hook audit above. `--pid` to attach, `--save` / `--load` a dump for offline analysis.
  Run it after any new hook: `MISMATCH` = fix, `CHECK` = verify the indirect call site by hand.

- `exit_catch.py`: Frida, logs every exception plus calls to ExitProcess, TerminateProcess, NtTerminateProcess,
  RaiseFailFastException and the msvcrt exits, with backtraces, written synchronously. A silent kill that shows none of
  these points to a fault the kernel could not deliver (bad ESP).
- `zoom_stalk.py`: Frida Stalker from the zoom slot or from SIMSPR+0x42e1b, one line per basic block (pc, esp, ebp),
  flushed per line. Stalker loses the thread at any exception (OutputDebugString included), so start it after one.
- `zoomcrash_run.py`: launch through version.dll (SC3MODS_DIR / MULTI), size the client with SetWindowPos
  (SWP_NOACTIVATE | SWP_NOZORDER), posted minimap zoom clicks (native offsets from the bottom-right: in (134,53),
  out (28,53), times the HUD factor), posted numpad +/- (`key:addx1`), right-drag scrolls, frame dumps, `audit:`
  (runs hook_audit.py), one `[N/M] item PASS|FAIL` line per step, `--pid` to drive a game already started.
