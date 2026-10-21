# avramp results: avenue dragged to a highway end (owner bug 7, 2026-10-21)

Owner report 7 (img9, `MAIN\verify\ownerbugs_1021\owner_shots\img9.png`): "avenues are not connecting to the ramp of
the highway". Branch child/avramp from main 664a685. Test tree `Simcity_stock_avramp` (= the release the owner ran,
`mods\netmod` overlay included), instance `re\harness\inst_avramp`, lab city copies. Pictures:
`MAIN\verify\avramp\owner_shots\avramp_sheet.png`, single frames `avramp_*.png` there.

**No code change.** The orchestrator's call (2026-10-21): the cause is hwcore's proof rule, which hwlone makes opt-in
(main afca244), so hwave stays as it is. A proof-row case written into sc3netmod_hwave.c first was reverted.

## 1. Cause
- The release installs `highway_core` (hwcore's PROOF package). Its `hwyt` rule (`sc3netmod_hwy.c` hwyt_run, end of
  every highway pass) writes a ramp-down piece 21100 / 21101 into the free cell past every highway end. That ramp is the
  "ramp of the highway" in img9.
- Highway first, avenue dragged to its end afterwards: the road tool stops at the cell before the ramp. Grid (lab,
  x 68/69): z26 caps 11235.0 / 11237.0, z27 proof 21101.0 / 21100.0, z28 the avenue U-turn row 21701.3 / 21701.0,
  z29+ 21700. HWAVE wants the U-turn row right past the cap row, and the cell past the cap holds highway, not road, so
  it never tries (no log line).
- Avenue first, highway after: the cell past the cap is taken, hwyt writes nothing, the transition builds.

## 2. Checks with the proof rule off (main 664a685 build, `SC3NETMOD_HWYT=0`, highway_core left installed)
| case | result |
|---|---|
| (a) owner's order: highway (69,16)->(69,26), then roads (68,40)->(68,27), (69,40)->(69,27) | `hwave: road: highway end at (68,26) turn 0 -> transition to the avenue, 4 cell(s) written`; z26 21601.0 / 21600.0, z27 21851.0 / 21850.0, z28+ 21700 |
| (a) other z direction: highway (51,38)->(51,30), roads (50,14)->(50,28), (51,14)->(51,28) | `highway end at (51,29) turn 2 -> transition`; z29 21600.2 / 21601.2, z28 21850.2 / 21851.2 |
| (b) x axis, highway first: highway (115,85)->(106,85), roads (94,85)->(104,85), (104,84)->(94,84) | transition at x105 turn 1: 21601.1 / 21600.1, x104 21851.1 / 21850.1 |
| (b) x axis, avenue first: roads (94,95)->(103,95), (94,96)->(103,96), highway (115,96)->(104,96) | `hwave: edit: highway end at (104,95) turn 1 -> transition` |
| save + reload (4 transitions) | save 112 variant tiles as base; reload `all 112 variant tiles restored`, grids identical; shot rotated (view 1) |
| (c) the img9 repro save (made WITH proof pieces, release DLL), loaded with the rule off | `hwy: load: (x,z) piece 21100/21101 kept by no block -> removed (land), 3x3 retile` x 10 (all proof pieces in the save), the stock caps stay, the avenue's U-turn row stays one cell off: **not joined on load** (z26 cap, z27 empty, z28 21701) |
| (c) then one more drag of each avenue half into the gap: (68,31)->(68,27), (69,31)->(69,27) | after the first half the stock retile shows a road end; after the second `hwave: road: highway end at (68,26) turn 0 -> transition`, 4 cells |

So: with the rule off, the owner's order builds the transition in every direction and order tried. A city saved with
proof pieces loses them on load and the avenue needs one more drag of both halves (each from inside the avenue to
the cell next to the cap) to join.

## 3. Notes
- Lanes: the ground row is avmisc's one-way 21850 / 21851 on avcore's converted band (`avl: ... -> one-way (ends: join or
  edge / U-turn)`), unchanged pieces. Router walk not re-run.
- Camera tool: `rb_lab.py cam` twice in a row, or with a rotation change, failed with "system error" several times;
  once the game then stopped responding (PID 68652, killed). One `cam` call per move is safer.
- Two boot crashes (0xC0000005 after ~0.5 s) while three sibling games were starting; the next launch was fine.
