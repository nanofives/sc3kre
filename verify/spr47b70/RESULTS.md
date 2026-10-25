# spr47b70: VEH FAULT READ 0 at SIMSPR.DLL+0x47B70 (child spr47b70, 2026-10-25)

Verdict: **a stock bug, not a mod.** The city view init loads one sprite and never checks the result. That load fails
whenever anything else has the file open, because GZResourceD opens files exclusively. Fixed in sc3resize, block
`SHAREREAD` (off: `SC3RESIZE_SHAREREAD=0`).

## Cause

| step | evidence |
|---|---|
| SIMSPR `FUN_10044471` (`sc3spr_view_register_cursors`, city-view init, main thread) builds the path `<app>\Res\UI\Shared\cursors\anchor point cursor.BMP` and calls `(image manager)->vt+0xc` with out = `this+0x1fc` | `[CONFIRMED @ 0x10047ADB..0x10047B5F]`, strings at `0x10072148` / `0x10072130` |
| the target is GZResourceD `FUN_10007603` (`sc3_gzres_load_imagefile`, `ret 0x14`) | runtime, `re/tools/spr47b70_probe.py` -> `fn=GZResourceD.dll+0x7603` (`logs/probe1.txt`) |
| it opens the file via `FUN_1000a89b` mode 1 -> file open (vt `0x1001e128` +0xc = `FUN_1001816f`) with `(1, 2, 0)`: GENERIC_READ, OPEN_EXISTING, **dwShareMode 0** | `[CONFIRMED @ 0x1001819B..0x100181EA]`, `[CONFIRMED @ 0x1000A975]` |
| on a failed open it returns 0 and leaves `*out` = 0. The init then runs `mov ecx,[edi]` / `mov esi,[ecx]` = the fault at +0x47B70 | `[CONFIRMED @ 0x10047B62..0x10047B70]` |
| the BMP is one file object behind **52 hard links**: MAIN\Apps (the owner's install), Simcity_release and every Simcity_stock_* tree | `fsutil hardlink list` |

So a game builds its city view while any other process (another game in any linked tree, an indexer, a tool) has the
file open. The exclusive open fails and the game dies with no dialog.

Field logs: `MAIN\verify\uiaudit\fix_A\sc3resize_crash_terrain3840.log` and
`MAIN\verify\verdatos\logs\B_tex256_e1024_load_crash_SIMSPR47B70_sc3resize.log`. Both show the same registers as the
repro (eax=001AE500/001AF100, ecx=esi=0, `[esp]`=0xFF), the same stack (SC3U+0x40917 > SIMSPR) and the main thread.
Which process held the file in those two runs is `[UNCERTAIN]`. Many children ran games from hard-linked trees that
day, and no handle log exists.

## Repro (file held open by `hold_file.py`, my tree's copy only: its hard link was broken first)

| arm | holder | result |
|---|---|---|
| stock `SC3MODS_OFF=1` (Frida probe) | exclusive | load returns 0, out 0, process gone, **1 of 1** (`logs/repro_stock_locked.txt`) |
| all mods, before the fix | exclusive | VEH FAULT SIMSPR+0x47B70 READ 0, field signature, **1 of 1** (`logs/repro_mods_locked_sc3resize.log`) |
| C: all mods, `SC3RESIZE_SHAREREAD=0` | exclusive | VEH FAULT SIMSPR+0x47B70, **1 of 1** (`logs/C_excl_off_sc3resize.log`) |
| A: all mods, fix on | exclusive | **5 of 5 alive** (+1 earlier run). Each logs `SHAREREAD> ### the anchor marker sprite failed to load 21 times`, and the view comes up without the marker (`logs/loop_A.txt`) |
| B: all mods, fix on | FILE_SHARE_READ (= another patched game reading) | alive, sprite loaded on the first try, marker drawn 400 of 400 passes (`B_marker_drawn.png`) |
| D: all mods, fix on | none | 2 of 2 alive, no retry line (`logs/loop_D.txt`) |

Natural rate without a holder: not measured. A collision needs two openers within one open-to-close of a 3 KB read.

Draw guard: the right-drag marker draw (`FUN_10043daf`, SIMSPR 0x1004407F) is the only other reader of `this+0x1fc`.
`re/tools/spr47b70_markerdraw.py` sets the drag flag `+0x1e6` from the view tick, with no mouse involved. With a null
sprite (arm A game): 60 marker passes, sprite drawn 0 times, no fault. With the sprite loaded (arm B): drawn 400 of 400.
Posted right-drags do not enter the drag mode (it reads the physical button), so a real right-drag with a missing
sprite stays on the owner-check list. It needs a held file to happen at all.

## Fix: sc3resize `SHAREREAD` (worktree `child/spr47b70`)

1. GZResourceD file-open slot `0x1001e134` (vt `0x1001e128` +0xc) wrapped with an atomic CAS on `.rdata`. A
   read-only open (no write bit) also gets FILE_SHARE_READ. Writes keep the caller's mode. Two readers coexist, so
   patched games no longer collide with each other.
2. SIMSPR+0x47B62: a null sprite is retried 20 times, 5 ms apart, with the game's own call and arguments. If it is
   still null, both vt calls are skipped (jump to +0x47B84), and the view comes up without the anchor marker.
3. SIMSPR+0x4407C: the marker draw is skipped when `this+0x1fc` is null (jump to +0x440A2, still calls the matching
   end call).

Install checks: the shipped bytes (memcmp), no branch lands inside either patched range (capstone scan of all SIMSPR
code), no other mod touches these bytes or that `.rdata` page, and protection is never restored (onramp rule).
A stock game in another tree can still hold the file exclusively for a moment. Part 2 covers that case.

## Round 2 (orchestrator checks, final build: SHAREREAD + sc3netmod OVPIN)

| check | result |
|---|---|
| held file, exclusive, fix on (`final_A.txt`) | alive, view up without the marker (21 failed tries logged) |
| held file, shared read, fix on (`final_B.txt`) | alive, sprite loaded on the first try, city starts |
| held file, exclusive, `SC3RESIZE_SHAREREAD=0` (`final_C.txt`) | VEH FAULT SIMSPR+0x47B70 after 5 s, as before |
| two games from two hard-linked trees, started together, 3 rounds (`pairs.txt`) | 3 of 3 pairs alive. The two view inits landed 2 to 4 s apart in every round, so this shows the two trees coexist but does not force the 1 ms overlap. The held-file arms test that case |
| save (options flyout > floppy), quit with save, reload (`save_trace.txt`, `save_*.png`, `load_saved.png`) | city file rewritten twice (19:42:31, 19:44:25). SC3.cfg / SC3Net.cfg / SC3U.ini written at exit. 0 failed opens over the whole session. The reload shows the saved date (3/22/2088), no fault |
| write opens untouched | every write open in the trace keeps the caller's own share mode: the save's temp file read+write share 1 through the wrapper (`sc3resize.dll+0x230b` on the stack), SC3U.ini read+write share 0 |
| sc3netmod OVPIN on vs `SC3NETMOD_OVPIN=0` (`netmod_ovpin_on.log` / `_off.log`) | 160 import slots hooked in both. No module was skipped in any run, so the skip path was not exercised |

Void batch, kept on record: a first round-2 batch ran with no mods loaded (a `$TREE`/`$Tree` name clash in
`run_arm.ps1`, PowerShell names are case-insensitive), and its held-file holders outlived their arms (the cleanup still
matched the old `excl.py` name). Its pair rounds therefore ran stock, with the file held, and crashed 3 of 6 games at
SIMSPR+0x47B70 (the game's own `Apps\SC3U_stkdmp.txt`, 19:29:19 / :33 / :52). That is the known held-file case, not a
new cause. Both runner bugs are fixed. `pair.ps1` now kills any leftover holder first. A one-game stock trace
(`filetrace_stock.txt`) shows the game opens the BMP once, for 1 ms. `who_holds.py` (Restart Manager) found no other
holder over 60 s with the trees idle (5,569 tries).

## sc3netmod first-chance faults (asked)

The 7 faults are in `verdatos\logs\B_tex256_e1024_2560_3840_sc3resize.log`, not in the crash run. They are READs of
`0x78000000` (the base of `Apps\MSVCRT.DLL`) at KERNEL32+0x1CA9E, inside `IsBadReadPtr`. The caller is sc3netmod
`ov_hook_all` -> `iat_patch(m, ...)` (`IsBadReadPtr(dos)`) over a `K32EnumProcessModules` list, run from its
LoadLibrary hook (MaxisAddOn+0x37A8 on the stack). A listed module whose image is not readable at that moment faults,
`IsBadReadPtr` catches it and returns TRUE, and the module is skipped. So they are handled. Residual risk: the module
was not pinned across the import-table walk, the same pattern sc3perf fixed on 2026-10-22 (memory
project-mod-startup-races). **Fixed in round 2: sc3netmod `OVPIN`** (`SC3NETMOD_OVPIN=0` = old walk). `ov_hook_all`
takes a reference on every listed module (`GetModuleHandleExA` FROM_ADDRESS) before its `g_ovlock` section and
releases them after it. A module whose handle can't be taken is skipped and logged (first 8). The loader calls stay
outside `g_ovlock` on purpose, because the file hooks take that lock on threads that may hold the loader lock.

Also seen, unrelated and pre-existing: a handled `IsBadReadPtr` fault at KERNEL32+0x2CF80 from sc3resize itself
(D r2 here, and `Simcity_stock_lanedensity2` on 2026-10-15). The game continues.

## Files

- `re/harness/src/sc3resize.c`: SHAREREAD block (after TIPCURSOR) + its call in `rz_watcher`
- `re/harness/src/sc3netmod.c`: OVPIN in `ov_hook_all` + its switch in `overlay_init`
- `re/tools/spr47b70_filetrace.py`: Frida trace of one file's opens/closes, or of every write open (`--writes`)
- `verify/spr47b70/pair.ps1`, `who_holds.py`
- second test tree `Simcity_stock_spr47b70b`: hard links of my tree (the BMP is shared by these two trees only), own instance folder
- `re/tools/spr47b70_probe.py`: read-only Frida probe of the load (do not use it with the fix on: it hooks +0x47B62)
- `re/tools/spr47b70_markerdraw.py`: drives the marker draw without a mouse
- `functions.csv`: GZResourceD `0x1001816f` `sc3_gzres_open_file`, `0x10007603` `sc3_gzres_load_imagefile` (C2)
- `verify/spr47b70/`: this file, `run_arm.ps1`, `loop.ps1`, `hold_file.py`, `logs/`, `B_marker_drawn.png`, `A_after_rdrag.png`
