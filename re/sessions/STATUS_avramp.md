# STATUS avramp (owner bug 7: avenue not joining a highway ramp), 2026-10-21

## goal
Owner report 7 (img9). DONE: cause found, verified fixed by hwlone's proof-rule opt-in (no hwave change, orchestrator
call). Protocol: re/sessions/CHILD_PROTOCOL_2026-10-21_ownerbugs.md.

## design
- Cause: highway_core's proof rule (hwyt) writes a ramp-down 21100/21101 past every highway end; an avenue dragged to
  that end afterwards stops at the ramp's foot, one row further than HWAVE looks.
- Fix = hwlone (main afca244, rule opt-in). My proof-row change to sc3netmod_hwave.c was REVERTED (file = HEAD).

## built (files, uncommitted)
- verify/avramp/RESULTS.md only

## proven in game vs offline only
- rule off (SC3NETMOD_HWYT=0 on the 664a685 build): highway-first builds in z (turns 0, 2) and x (turn 1), avenue-first
  in x, save + reload 112/112. img9 repro save: proof pieces removed on load, avenue NOT joined on load, joins after one
  more drag of both halves.

## blocked on
-

## files owned (worktree Simcity_wt_avramp)
- verify/avramp/RESULTS.md
- owner pictures (orchestrator's call): MAIN\verify\avramp\owner_shots\avramp_sheet.png + avramp_*.png

## ids taken
- none

## instance
Simcity_stock_avramp\re\harness\inst_avramp, all my PIDs stopped (last 11144). Saves: repro_saved.sc3 (bug layout,
proof pieces), t3_saved.sc3 (4 transitions, rule off). sc3netmod.dll there = 664a685 build.

## needs owner
- old cities with the bug layout need one more avenue drag after updating (or a load-time join, if wanted).

## asks of other streams
-
