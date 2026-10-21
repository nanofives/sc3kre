# STATUS hwtee (child of owner hand-test bugs 2026-10-21): DONE

## goal
Owner bug 3 (img3): two highways connected like a T, no T interchange offered. Expected: the hwt trumpet (with the
hwask question) forms for that layout.

## design
Cause: owner's through highway ends 6 cells right of the stem (end cap at T frame dx 7, the capped-twin case hwt
accepts). The release's highway_core proof rule put a ramp 21100/21101 at dx 8, hwcap_end read it as other highway,
hwt refused with the unlogged reason "through highway". hwlone's opt-in fix (child/hwlone a6ba6e4) removes the cause.
My change: hwt_check reordered (meeting cells first, silent; then stem; then the through highway's length) and logs
the refusals that have a through highway present. Detail: worktree verify/hwtee/RESULTS.md.

## built (files, uncommitted)
- Simcity_wt_hwtee: re/harness/src/sc3netmod_hwt.c (task hwtee: hwt_check order + 3 logged reasons)
- Simcity_wt_hwtee: verify/hwtee/RESULTS.md (new)

## proven in game vs offline only
In game with hwlone's sc3netmod_hwy.c on top (= main after both merges): owner layout asks and builds in turn 0
(stem toward the through) and turn 1 (stem dragged outward), short end clean (stock cap + capped twin 21255, no 15149);
5-cell case refused with the new log line; save 104 tiles + reload kept=2. Round 2 (on main afca244's hwy.c, identical):
city saved WITH proof ramps by the release-like DLL loads clean (6 ramps removed, stock caps), re-dragging the stem asks
and builds the same clean T. Repro on the release build: dx 6 and dx 7
no question, dx 8 asks. Offline: nothing (hwt_twin.py unchanged, decisions unchanged).

## blocked on
nothing

## files owned
- Simcity_wt_hwtee: re/harness/src/sc3netmod_hwt.c, verify/hwtee/RESULTS.md
- MAIN: re/sessions/STATUS_hwtee.md, verify/hwtee/owner_shots/hwtee_sheet.png + hwtee_*.png (game shots)
- I did not edit sc3netmod_hwy.c (main afca244 has hwlone's change).

## instance (folder, last PID)
Simcity_stock_hwtee\re\harness\inst_hwtee (PIDs 14088 crashed at load, 48840, 34168 hung, 3808, 37308, 73020, 57208,
3320 crashed at load, 52968, 71384: all stopped). sc3netmod.dll there is the combined build (worktree + hwlone hwy.c). Saved city c1_saved.sc3 (2 Ts).
Defender quarantined my own mods_launch.exe build twice; the instance runs a copy of inst_hwlone's.

## needs owner
- hwtee_sheet.png.
- Design call: a through highway ending 5 or fewer cells right of the stem (or 1 left) gets no T. A mirrored trumpet
  would be a new package.

## asks of other streams
- none (hwlone merged on main afca244)
