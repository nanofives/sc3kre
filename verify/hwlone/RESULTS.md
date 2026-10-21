# hwlone: an unconnected highway looks like stock again (owner bug 2026-10-21, img1 / img2)

## Cause

The LAN release (main 664a685) has the hwcore proof package `highway_core` installed
(`mods\netmod\tables\highway_core.txt`: `hwyt 21100 21101`). That line turns on the proof rule `hwyt_run`
(`re/harness/src/sc3netmod_hwy.c`), which writes a ramp-down piece 21100 / 21101 into the free cell past EVERY
highway end. It was written for the hwcore in-game proof (`verify/hwcore/RESULTS.md`) and was never meant for play.
No shape block (hwt, hwcap, hwave, hwx, hwdx, hwdd) is involved.

Reproduced in `Simcity_stock_hwlone` (the owner's tree, DLLs built from main 664a685), lab city:

| drag | log (`sc3netmod.log`) |
|---|---|
| one piece at (50,24) | `hwy: edit: highway end at (49,23) -> proof piece 21101.1 in (48,23)` and 3 more: (51,23), (48,24), (51,24) |
| run (60,18)-(60,32) | proof pieces in (59,17), (60,17), (59,33), (60,33) |

Same drags in the same tree with no sc3netmod (mods_launch + sc3resize only): the same stock cells
(15053 / 15054 for the piece, 11235 / 11237 caps + 73 for the run) and nothing past the ends.

## Fix

`sc3netmod_hwy.c`: the proof rule runs only with `SC3NETMOD_HWYT=1` (was: on whenever a `hwyt` line is installed,
off with `=0`). With the rule off, any 21100 / 21101 already in a city are "kept by no block" and the next highway
pass removes them with a 3x3 retile, the load pass included. `examples/highway_core/README.md` says so.

Nothing else changes: the shape blocks never used 21100 / 21101 (no other source or table names them).

## In game (fix DLL, owner's tables unchanged, highway_core still installed)

| step | result |
|---|---|
| load the city saved by the owner build with the 8 ramps | `hwy: load: (59,17) piece 21100.2 kept by no block -> removed (land), 3x3 retile` x8, `load pass ... 0 written, 8 reverted`; cells = the stock run's cells |
| new run (56,40)-(68,40) along x, one piece at (66,31) | stock 15053 / 15054 / 15051 cells, no `hwy: edit` line |
| save + reload | `save: 4 variant tile(s)` (the lab's own 4), `load pass ... 0 written, 0 reverted`, cells unchanged |
| same game started with `SC3NETMOD_HWYT=1`, same two drags | 8 proof pieces written (the opt-in works) |
| variable set to `0` inside the running game (Frida, SetEnvironmentVariableA), the piece and the run dragged again | `hwy: edit: (48,23) piece 21101.1 kept by no block -> removed (land), 3x3 retile` x4 per drag, `0 written, 4 reverted` twice; cells = stock |

Pictures: `MAIN\verify\hwlone\owner_shots\hwlone_sheet.png` (1 owner build, 2 stock, 3 fix after reload of the
ramp city, 4 fix new drags); singles `hwlone_01..05_*.png`; edit-pass removal `hwlone_06_optin_HWYT1_ramps.png` ->
`hwlone_07_HWYT_off_edit_pass_removed.png`.

## Release note

With this DLL `highway_core` can stay installed: it does nothing, and it removes the ramps from cities already
saved with them. Measured 2026-10-21 in this tree with `tables\highway_core.txt` moved aside (= uninstalled), loading
the city saved by the owner build:

| step | result |
|---|---|
| load | `load: variant section 12 entries, 4 to restore, 8 not installed (stay base)`: the 8 ramps load as stock 15099 (Protected highway slope); `load pass ... 0 written, 0 reverted` |
| drag the piece and the run again | the stock tiler joins the caps into the 15099 cells (15053 / 15054 -> 15051, 11235 / 11237 -> 73): a slope stub at every old ramp, for good |

So uninstall `highway_core` only once every city saved with ramps has been loaded and saved with the fixed DLL;
otherwise keep it installed. Pictures: `hwlone_08_uninstalled_ramp_city_loads_15099.png`,
`hwlone_09_uninstalled_redrag_joins_15099.png`. The release tree has no netpack ledger (`netpack uninstall` there
says "not installed"); the stage source `Simcity_stock_avint` has one.

Not tested: the other camera rotations (the rule is off, nothing is written in any rotation).
