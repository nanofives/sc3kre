# RESULTS - mods stay inert unless the sc3kre loader loads them (child/lateguard, 2026-10-27)

Verdict: an UNPATCHED anchor `SC3U.exe` with all 8 DLLs in `Apps` now starts as the stock game (main menu drawn, alive
at 60 s), where main 7c0dfcd's DLLs crash it 0.7 s after start. A patched exe still loads the 7 mods before GZGraphicD and
plays Frankfurt. The test-harness path (`SC3MODS_DIR`) still works, and the same run with a second copy of every mod in
`Apps` (a config that used to crash) is now harmless.

## Who maps the Apps DLLs

The game's own GZCOM component scan [CONFIRMED @ 0x0040b00f, 0x0048a575, 0x0048a675]:

- `FUN_0040b00f`: when no `Components` list is configured, lists `"*.dll"` (string 0x004f5198) in the app folder,
  skips `CLCD16.DLL`, `CLCD32.DLL`, `DPLAYERX.DLL`, `DRVMGT.DLL`, and hands each path to the COM director
  (`FUN_004708c4()` vtable +0x14).
- `FUN_0048a575`: `LoadLibraryA(path)`, then `GetProcAddress(h, "GZDllGetGZCOMDirector")`. If that export is missing
  or its director refuses, `FUN_0048a675` runs.
- `FUN_0048a675`: `FreeLibrary(h)`.

So every `sc3*.dll` gets its DLL_PROCESS_ATTACH from the game and is unmapped right after. Measured with a
LoadLibraryExW/FreeLibrary hook in the runs below: the scan maps and frees `sc3bigcity`, `sc3mods`, `sc3netmod`,
`sc3overscroll`, `sc3perf`, `sc3resize`, `sc3simrun`, `sc3undo`, in that (alphabetical) order, in the same 0.1 s
log tick as GZGraphicD. A mod that hooks the game in DllMain and starts a thread therefore leaves hooks and a thread pointing
into freed memory. With a patched exe the mods are already loaded from the same path, so the scan's LoadLibrary only
bumps the refcount and DllMain does not run a second time.

## What changed

- `re/harness/src/sc3mods_guard.h` (new). `sc3mods_guard(inst, name)` is the first statement of each mod's
  DLL_PROCESS_ATTACH. It returns 1 (initialise) if:
  1. `GetModuleHandleA("sc3mods.dll")` or `GetModuleHandleA("version.dll")` exports `sc3mods_loading` and it returns
     nonzero, or
  2. `SC3MODS_ANYLOAD=1` is in the environment.

  Otherwise it writes one line, `[pid N] <mod> not loaded by sc3mods, inert ...`, to `<mod>.log` beside the DLL
  (CREATE_ALWAYS, so one line per run) and DllMain returns TRUE with nothing else done: no hooks, patches, threads,
  critical sections or ini reads. The only calls are kernel32 functions already bound under the loader lock.
- `sc3mods.c` / `.def`: export `sc3mods_loading()`. It is true only on the thread inside `load_mods`' LoadLibrary
  loop (`g_loading_tid`), cleared after the loop. A late (dynamic) load of `sc3mods.dll` still loads nothing (7c0dfcd).
- `sc3modldr.c` / `.def` (the retired version.dll proxy): same export, so a rebuilt proxy still starts the mods.
  Compile-checked only (build_mod.ps1 no longer has a target for it).
- `mods_launch.c`: sets `SC3MODS_ANYLOAD=1` for the game, because the `version.dll` binaries already in old trees have
  no `sc3mods_loading` export. Compile-checked.
- Guard added to all 8 mods: sc3resize, sc3bigcity, sc3overscroll, sc3simrun, sc3perf, sc3netmod, sc3undo, and
  sc3cartrips (not in the default list, but it would sit in Apps the same way).

Why this mechanism and not another:

- A thread-scoped flag exported by the loader is the only signal that is true for "our loader is loading me right
  now" and false for the game's scan, which loads the very same file path on the same main thread. A process-wide
  env var set by the loader would stay visible to the scan unless cleared, and a cleared one is what the export does
  with less to get wrong.
- `lpReserved` cannot tell them apart: every mod load is a dynamic LoadLibrary (NULL), from our loader or the scan.
- "GZGraphicD not loaded yet" was considered and rejected. It holds only while the scan's order puts GZ* first,
  which is NTFS name order. FindFirstFile on FAT32/exFAT returns directory order, and a `Components` list can set
  any order.

## Proof

Trees: `Simcity_stock_lateguard` and `Simcity_stock_lateguard_p`, made with `link_tree.py` from `Simcity_release`
(shipped stock GZGraphicD/SIMSPR, SHA prefixes 48201f47 / eec71500). In both, `Apps\SC3U.exe` is a real copy of
`original\SC3U.exe` (anchor 49DD55E1...), not a hard link, and the game-written configs are de-linked. The 8 DLLs in
`Apps` were built from this branch (`re/harness/inst_lateguard`). Driver: `verify/lateguard/stock_run.py` (posted
input only, no cursor, no focus, own PID killed at the end). Logs and grabs are under `verify/lateguard/data/`
(local, gitignored).

Windowed rule: the stock game opens fullscreen. For the unpatched runs, `stock_run.py` spawns the game under Frida
and, when LoadLibraryExW returns GZGraphicD, writes the same three things sc3bigcity's `patch_windowed` +
`patch_surfacefmt` do (flag +0x6cdac, nop at +0x117d6, FIX16 cave at +0x19349). No mod DLL is involved. The patched
runs start plainly and sc3resize does windowed itself (`SC3RESIZE_WINMEM=0`).

| # | exe | DLLs in Apps | env | result |
|---|---|---|---|---|
| A | anchor (unpatched) | 8, guarded (this branch) | none, `-intro:off` | alive at 60 s, main menu drawn (`unpatched_guarded2/grab.png`), no sc3 module mapped at 30 s or at 60 s, each of the 7 mods wrote exactly 1 "inert" line, sc3mods.log 2 lines ("dynamic load ... no mods loaded") |
| B (control) | anchor (unpatched) | 8, main 7c0dfcd (unguarded) | none, `-intro:off` | **dead 0.7 s after resume** (0.2 s after the scan mapped sc3bigcity), c0000005 at 11:15:33 in `SC3U_stkdmp.txt`, the dumper died before writing the fault address. sc3bigcity.log shows it initialised (QFS24, WINDOWED) during the scan. Only sc3bigcity and sc3mods were mapped before the process died |
| C | patched (E5B6330C..., `sc3mods_patch.ps1`) | 8, guarded | none, Frankfurt, `-intro:off` | `sc3mods.log`: "static import, process init ... GZGraphicD loaded now? no", 7 loaded. sc3resize: `DPI>` per-monitor v2 at 1.8 ms, `EARLY: loader notification registered (status 0x00000000)`, `EARLY: GZGraphicD mapped ... patching before its DllMain`. READY lines from bigcity/overscroll/simrun/netmod. 0 inert lines. Frankfurt rendered (Pob 480,675, 10/13/2054), sc3perf overlay 60 fps (`patched_apps/grab.png`). Alive at 60 s |
| D | patched | 8, guarded | `SC3MODS_DIR=re\harness\inst_lateguard`, `SC3MODS_MULTI=1`, Frankfurt | sc3mods: mutex renamed, 7 mods loaded from the instance folder before GZGraphicD, READY lines in the instance logs. The 7 duplicate copies in `Apps` each wrote 1 inert line. Frankfurt rendered (`patched_dir/grab.png`), alive at 60 s |

An earlier run of A ended at 4.6 s. EIP was the test's own Frida cave + 3: Frida frees `Memory.alloc` memory when the
JS handle is collected. The fix was to keep a reference. The mods were already inert in that run (one line each).

Not shown: the sim running. Both patched runs left Frankfurt paused (cities load paused) and no unpause was posted.
importldr's evidence for the mods while the sim runs still stands, and this change does not touch any code after
DllMain's guard.

Defender (real-time protection, behaviour monitor and on-access On, signature 1.461.224.0): `Get-MpThreatDetection`
showed 23 detections before the builds and runs and 23 after. The newest is still 2026-10-27 08:42, `version.dll` in
`Simcity_release`. The compile-check `version.dll` (sc3modldr) existed in the scratchpad for under a minute and was
deleted. No exclusions were added.

## Every way a mod gets loaded (step 2)

| path | how | after this change |
|---|---|---|
| Player install: patched `SC3U.exe` imports `Apps\sc3mods.dll` | `load_mods` LoadLibrary loop, flag set | works (run C) |
| Test harness: patched exe + `SC3MODS_DIR` / `SC3MODS_LIST` / `SC3MODS_MULTI` (`zoomband_run.py`, `zoomcrash_run.py`, `vdscroll_bench.py`, `spr47b70_probe.py --spawn`) | same loop | works (run D), and a second copy in Apps no longer crashes |
| `-multi` parallel games | same loop plus mutex rename | works (run D used `SC3MODS_MULTI=1`) |
| `SC3MODS_OFF=1` stock arms | loader loads nothing | unchanged. Any copy in Apps is inert instead of crashing |
| `mods_launch.exe` + old `version.dll` (sc3modldr) in the tree, used by 14 tools in `re/tools` (closex_drive, dismiss_tips, hudclick_launch, hudperf_bench, leftclick_run_arm, link_tree notes, nb_drive, np_arm, nv_run, pt_run, sc3io notes, startup_loop, undo_drive, zoomcenter_run_arm) | old proxy without the export | needs `mods_launch.exe` rebuilt from this branch (it sets `SC3MODS_ANYLOAD=1`). An OLD `mods_launch.exe` with NEW mods gives inert mods, one line each. Not run here (Defender flags `mods_launch.exe`, importldr retired it) |
| A rebuilt `version.dll` from `sc3modldr.c` | export present | works by the flag. Compile-checked only |
| Retired injectors (`sc3launch.c`, `resize_launch.c`, `bigcity_launch.c`, `overscroll_launch.c`, `slider_launch.c`, untracked in MAIN `re/harness/src`) and any Frida `Module.load` | CreateRemoteThread(LoadLibraryA) or similar | inert unless the game is started with `SC3MODS_ANYLOAD=1`. No current tool does either: a grep of `re/tools` found no `Module.load` / `LoadLibrary` of a mod |
| `sc3probe.dll`, `sc3startsize.dll`, `ptrshape` | not mods in Apps, no guard added | unchanged |

## Open risks

- `SC3MODS_ANYLOAD=1` turns the guard off for the whole process, including the scan. Use it only with a single
  copy of each mod and no late-loading loader. With old `version.dll` + `mods_launch` that holds (the proxy loads the
  mods first, so the scan only bumps refcounts).
- Mods built before this branch have no guard. A player who keeps an old `sc3*.dll` in Apps beside an unpatched exe
  still crashes. The 10-27c release must ship all 7 mods and `sc3mods.dll` from this branch together.
- The inert line overwrites `<mod>.log` beside the DLL. In run D that is the Apps copy's log, not the log of the copy
  that ran. Intended (one line per run), but a tester reading `Apps\sc3resize.log` after a `SC3MODS_DIR` run sees
  "inert" and must look in the instance folder.
- Unpatched windowed mode in these runs came from the Frida test patch, not from the game. A real stock unpatched
  start is fullscreen, which is the stock game's normal behaviour.

## Files

- `re/harness/src/sc3mods_guard.h` (new, force-added)
- `re/harness/src/{sc3mods.c,sc3mods.def,sc3modldr.c,sc3modldr.def,mods_launch.c}`
- `re/harness/src/{sc3resize,sc3bigcity,sc3overscroll,sc3simrun,sc3perf,sc3netmod,sc3undo,sc3cartrips}.c`
- `verify/lateguard/RESULTS.md`, `verify/lateguard/stock_run.py`, `verify/lateguard/batch_ab.sh` (driver scripts force-added)
