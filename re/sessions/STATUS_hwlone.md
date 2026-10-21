# STATUS hwlone (child of "SC3: owner hand-test bugs 10-21 (highways + avenues)")

## goal
Owner bug 1+2 (img1, img2): a 1-cell highway and an unconnected highway run show a raised deck block with ramps at
the ends. Expected: an unconnected highway looks and behaves exactly as stock.

## state
2026-10-21: DONE. Cause found, fixed, checked in game (load cleanup, new drags, save + reload). Game stopped.

## design
Cause: release tree has the hwcore proof package `highway_core` installed; its `hwyt` line turns on `hwyt_run`
(sc3netmod_hwy.c), which writes ramp-down pieces 21100 / 21101 past every highway end. Fix: proof rule opt-in only
(`SC3NETMOD_HWYT=1`); existing ramps are removed by the next pass / load as "kept by no block". Detail:
`Simcity_wt_hwlone\verify\hwlone\RESULTS.md`.

## built (files, uncommitted, in Simcity_wt_hwlone)
- re/harness/src/sc3netmod_hwy.c (2 hunks, marked task hwlone)
- re/tools/netmod/examples/highway_core/README.md (the "Off" line)
- verify/hwlone/RESULTS.md (new)

## proven in game vs offline only
In game: repro (owner build), stock (no sc3netmod), fix: saved ramps removed on load AND on an edit pass (HWYT=1
then cleared in-process), new drags stock, save + reload clean. Uninstall check (my tree, table moved aside, then
put back): a ramp city loads the ramps as stock 15099 and a re-drag joins the caps into them = permanent slope
stubs, so keep highway_core installed until old ramp cities are re-saved with the fix. Not tested: other rotations.

## blocked on
(nothing)

## files owned
- Simcity_wt_hwlone: re/harness/src/sc3netmod_hwy.c, re/tools/netmod/examples/highway_core/README.md,
  verify/hwlone/RESULTS.md
- MAIN: re/sessions/STATUS_hwlone.md, verify/hwlone/owner_shots/hwlone_sheet.png + hwlone_01..05_*.png (game shots)

## instance
`Simcity_stock_hwlone\re\harness\inst_hwlone` (owner build), `inst_hwlonestock` (sc3resize only),
`inst_hwlonefix` (fix DLL). PIDs 45660, 28488, 63688, 21400, 59624, 50384, all stopped. Tree's tables restored (highway_core.txt back). Two early launches died during load
(they started within 15 s of sibling launches).

## needs owner
Look at hwlone_sheet.png.

## asks of other streams
(none)
