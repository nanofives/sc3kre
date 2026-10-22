# onramp: "the ramp preview disappears after placing a ramp" (owner, LAN build 2cedb34), 2026-10-21

Verdict: **stock behaviour.** No mod causes it. Owner asked for the fix (2026-10-22): **RAMPCAP in sc3netmod, below.**

## Cause
The stock add-point cap (`NET_RAMPS.md` 1.2). `FUN_10004754` (SIMNTWRK, adds a cell to the tool selection and
highlights it) adds only while `DAT_100322a4 < 0x200`, and increments it on every add `[CONFIRMED @ 0x10004754]`.
Only the drag path builder `FUN_1000488d` resets it. The On-ramp hover `FUN_10009d20` adds points on every mouse
move, so after enough moves it adds nothing: no light-blue strip, cost $0, and the build `FUN_1000abde` finds no
points and places nothing. Selecting the Road tool resets the counter. That is the owner's "change the selector and
come back".

## A/B (test tree Simcity_stock_hwlight, lab.sc3 copies, fresh launch each)
Highway 48,28 -> 68,28 (cells z 27..28), road 58,20 -> 58,36 crossing it. On-ramp tool, ramp at 59..61 z 29, then
hover 55..57 z 29, then mouse sweeps over valid spots. Counter read through Frida (SIMNTWRK + 0x322a4).

| step | A: sc3resize only | B: resize, bigcity, overscroll, simrun, perf, netmod, undo |
|---|---|---|
| tool selected | 1 | 1 |
| 3 moves on spot 1, preview + $225 | 30 | 30 |
| ramp 1 placed (15130 / 15134 / 15138) | 64 | 64 |
| hover spot 2, preview + $225 | 91 | 91 |
| +40 moves | 451 | 451 |
| +15 moves | 512 (cap): no preview, $0, click places nothing | 512, same |
| Demolish tool, then On-ramp again | 512, still no preview | not run |
| Road tool (no drag), then On-ramp again | 1 -> 30, preview back | not run |

TMPL (the template block that wraps this hover and resets the counter in template mode) is not installed in this
build ("tmpl: no templates in the tables"), so the hover is the stock function in both arms.

Frames: `owner_shots/onramp_ab_sheet.png` (plus the five single frames beside it).

## Fix: RAMPCAP (sc3netmod, `re/harness/src/sc3netmod_tmpl.c`, 2026-10-22)
`tmpl_install` now wraps the On-ramp selection hover (slot 0x1002c1bc, `FUN_10009d20`) first, whether or not any
template is loaded. `tm_hover` sets `DAT_100322a4 = 0` before each hover, then runs the stock hover (or the template
hover in template mode, which already did the reset). The hover erases the selection's point vector before it adds, so
one hover adds at most a few points and the cap never fills. Opt-out: `SC3NETMOD_RAMPCAP=0`. Log line:
`rampcap: On-ramp hover 0x1002c1bc wrapped, ...`. The slot belongs to the On-ramp tool's own selection object
(`FUN_1000f79c`), so no other tool is affected. `FUN_10009d20` returns with `ret 0x10`, which matches the wrapper's 4
stack args.

In-game check (full release set, sc3netmod from this worktree, fresh lab copy):

| step | result |
|---|---|
| ramp 1, then 100 mouse moves, hover spot 2 | counter 3, preview + $225, ramp 2 placed |
| 100 more moves, hover spot 3 | counter 3, preview + $225, ramp 3 placed (3 in a row) |
| paused: ramp 4, undo, redo (sc3undo) | `APPLY> on-ramp: 46 inserted, 44 removed`, `UNDO> 90 op(s), 0 failed, $225 refunded`, `REDO> 90 op(s), 0 failed` |
| save, quit, load the save | the 54..62 x 25..30 grid is identical to the one before the save; 80 moves later the counter is 1 |
| 5 launches of the final DLL | 5 of 5 reached the city |

Startup crashes (investigated 2026-10-22, see the next section): not caused by RAMPCAP. They are races between the
mods at startup, and they exist in the LAN build too.

Frames: `owner_shots/onramp_fix_sheet.png` (before at the cap, after 100 and 200 moves, 3 ramps, undo, redo).

## Startup crashes: races between mods (2026-10-22)
56 launches of the full release set tonight, 6 died at startup with 0xC0000005 within about 0.5 s. sc3resize's own
crash logger (`rz_veh`, `VEH FAULT` lines in sc3resize.log) caught 4 of them. The first 2 have no logs left. Every
run also logs one handled `0xC0000096` at `SC3U.exe+0x84122` at about 25 ms. That is the game's own startup probe
and it is harmless.

| run | fault | cause | status |
|---|---|---|---|
| final_7 | READ 0x7800003C at sc3perf+0x8110 = first instruction of `rc_scan_module` (reads `base + 0x3c`) | LAYER_REFCOUNT reads the PE header of a module the Toolhelp snapshot listed, but that module was freed before the read. `Apps\MSVCRT.DLL` is the only Apps DLL whose preferred base is 0x78000000 | fixed: `rc_watcher` and `exec_ranges` hold a reference (`GetModuleHandleExA` FROM_ADDRESS, then `FreeLibrary`) while reading; a module already gone is skipped and logged |
| pinb_10 | WRITE SIMTRANSIT+0x7159 at sc3perf+0x9FBE (`patch_trclear`, right after its 2 `VirtualProtect` calls) | sc3netmod LANEDENSITY patches SimTransit +0x755e (same 4 KB page) from its own thread at the same moment (193 ms vs 207 ms), and its `write_code` restored the old protection between sc3perf's `VirtualProtect` and its write | fixed: sc3netmod `write_code` leaves the page RWX, as sc3perf already does (sc3perf.c comment, 2026-10-09) |
| both_5 | WRITE SIMSPR+0x43A5E at sc3overscroll+0x473F (`patch_camfeel`) | same race on SIMSPR page 0x10043000: sc3simrun `patch_scroll_anim` writes +0x43de7 / +0x43f60 / +0x44003 from its own thread and restores protection after each write | fixed by the no-restore rule (below) |
| both_9 | WRITE SIMSPR+0x43F60 at sc3simrun+0x18AC (`patch_scroll_anim`) | the same page, the other direction (sc3overscroll's restore) | fixed by the no-restore rule (below) |

Restore sites still in the release mods: sc3resize 24, sc3simrun 9, sc3overscroll 4, sc3undo 3 (sc3perf and
sc3bigcity 0). Any two of them on one page, written from two threads at once, can crash the start. The suggested
fix is the sc3perf convention everywhere: no restore. Launch tallies: before the two fixes 4 of 36 crashed. After
the sc3perf pin 1 of 10 crashed (pinb_10). With both fixes 2 of 10 crashed, both on the still-open SIMSPR race.

### No-restore rule applied to every release mod (2026-10-22)
All 42 protection restores after a patch write are gone: sc3resize 25, sc3simrun 9, sc3overscroll 5, sc3undo 3
(plus sc3netmod `write_code`). Each is now a `(void)0` with the comment `no restore (task onramp)`. The 13 unlocks
that asked for `PAGE_READWRITE` now ask for `PAGE_EXECUTE_READWRITE`, so a page left unlocked can never lose
execute rights if it holds code. sc3perf and sc3bigcity already followed the rule. Not changed: sc3netmod_lanes.c
`sc3netmod_ld_set` (the A/B toggle used by test tools, with all other threads suspended).

| build | launches | startup crashes |
|---|---:|---:|
| release set as on 2cedb34 (+ RAMPCAP) | 36 | 4 + 2 without logs |
| + sc3perf module pin | 10 | 1 (protection race, SimTransit) |
| + sc3netmod no restore | 10 | 2 (protection race, SIMSPR) |
| + no restore in resize / simrun / overscroll / undo | **30** | **0** |

In those 30 runs the pin fired once: `LAYER_REFCOUNT> SIMADV.DLL at 0x03E80000 was freed after the module snapshot -
skipped` (nr2_1). SIMADV was loaded again and patched at 184 ms. Before the pin, that read would have been an
unmapped read like final_7. The log lines that report refused or mismatched patches match a pre-change run (both_1),
apart from sc3resize vs sc3overscroll swapping which one applies the shared GZGraphicD windowed / FIX16 bytes first.
The runs alternate between both orders, and the bytes end up the same either way. Smoke test on the final build:
highway, road, 2 ramps, counter 3 after 80 moves, undo / redo of a ramp (99 op(s) each way, 0 failed), windowed,
60 fps. Per-run logs: `Simcity_stock_hwlight\re\harness\inst_onramp\runs\` (not committed).
e\harness\inst_onramp
uns\` (not committed).
