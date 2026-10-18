# roundabout4: results (2026-10-14)

PRE: `verify/roundabout4/PRE.md` (e881699, before the first launch), addendum 1 (64e4205, after GR, before arms A, T,
S, O). Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_roundabout4` (stock GZGraphicD / SIMSPR / SIMNTWRK,
package roundabout 4.0.0 in overlay mode), instances `re\harness\inst_rb4` (sc3resize + sc3netmod from this branch)
and `inst_rb4_nomod` (sc3resize only). PIDs 19432, 20188, 2612, 11368, 8872, 21228, 16188, 4612, 19880, 7188, 10884,
15584, 9372, 10892, 1740, 20632, 16916, 20888, 5992, 21064, 9332, 10880, 20732, 20544, 5284: all mine, each started with
`mods_launch.exe -multi` and stopped with `taskkill /PID` except 10892 and 1740 (exited by themselves, below). Frames,
logs, saves and probe files stay in the instance folders (`shots\`, `city\`, `seq2\`, `T*.json`). Owner pictures:
`MAIN\verify\roundabout4\owner_shots\` (6 PNG + captions.md, not in git).

## Changes after PRE (each reported, none silent)

1. **20401 frame geometry (addendum 1).** With 39's full frames the terrain under the piece was missing in part of
   the cell in 15 of 48 views. 20401 now carries stock 11203's frame sizes and anchors (`frame_like`, `art.from`
   11203). Same art; 12 rim pixels dropped in one frame.
2. **GR metric (addendum 1).** Pixel equality with stock grass was ill-posed (empty cells differ between sessions);
   replaced by hole pixels and green fraction, measured before the addendum was written (reported as observations).
3. **BK procedure.** The two-number table reverts 20401 blocks on load (below), so the "before" frames were taken
   on a save made in that state and reloaded.
4. **T sites and camera.** Direct camera calls left the street sim without visible movers (roundabout1's trap);
   T was redone with the camera moved by minimap and zoom clicks only, and on Berlin (57,167) as well as Moscow.

## Static

| check | outcome |
|---|---|
| `netpack.py validate examples/roundabout` | OK, 4.0.0, variants 20400 (art from 39) and 20401 (art from 11203), `auto roundabout: piece 20400 ... arm-less quarter 20401`, no warning |
| `netpack.py selftest` | 0 failures (the run before PRE had 1, U1, from files another child wrote into MAIN during it) |
| `netpaint.py seams` 20400 | 1320 / 1320; 20400's 20 frames byte-identical before / after the netpaint changes |
| installed frame tables | 20400 flags 0x80, 20401 0xC0 |
| `rb_auto.py scan` (16 shipped cities) | 7 blocks, per-cell pieces as in PRE arm A |

## In game

| arm | outcome | verdict |
|---|---|---|
| L | `rbt: ... piece 20400, at least 3 arm(s), arm-less quarter 20401`, `hooked ... arm-less quarter 20401`, `### READY ... load=patched`; 0 `### rbt` lines in any log | met |
| GR as worded | first build (39 frames): black 0.0 of G in all 48 views, equal-to-stock 0.00..0.58 | **not met as worded** (addendum 1) |
| GR holes, first build | 15 of 48 views with back-buffer pixels in the closed cell outside the curb (up to 811 px); stock 0 (3 px in one view) | defect found |
| GR holes, rebuilt (11203 geometry) | 0 in 47 of 48 views; E zoom 4 rot 2: 3 px, the same 3 px as stock | met (observation) |
| GR green, rebuilt | green-dominant fraction of G 0.81..1.0 in 47 of 48 views (stock 0.77..1.0 where comparable); W zoom 2 rot 3: 0.0, as stock: the map-edge skirt covers that block in the W rotation-3 views | met (observation) |
| A | Berlin `3 qualify, 3 converted`: (29,86) `20400.3 20401.0 / 20400.2 20400.1`, (57,167) `20400.3 20400.0 / 20401.2 20400.1`, (145,102) `20401.3 20400.0 / 20400.2 20400.1`; Moscow `3 qualify, 3 converted`: (30,54) closed (30,55) 20401.2, (92,141) closed (92,141) 20401.3, (122,130) all 20400; Craterville (132,148) all 20400. 0 other cells differ from the save in every 10x10 box | met |
| B-W (56,8) | `20401.3 20400.0 / 20400.2 20400.1`, log `-> roundabout, 3 arm(s): 20401 20400 / 20400 20400` | met |
| B-N (56,20) | `20400.3 20401.0 / 20400.2 20400.1` (first attempt: camera call failed, its strokes built nothing, 20 passes = the strokes of the other cases; rerun) | met |
| B-E (56,32) | `20400.3 20400.0 / 20400.2 20401.1` | met |
| B-S (68,20) | `20400.3 20400.0 / 20401.2 20400.1` | met |
| B-G (68,32) | 3 arms `... / 20400.2 20401.1`; E added: all 20400, `4 arm(s)`; E exit demolished: `20401.1` again, `3 arm(s)`; S exit demolished: `39.3 39.0 / 11203.2 11203.1`, no 20400 / 20401 | met |
| lab save | `save: 16 variant tile(s) written as base` | as expected |
| BK | two-number table: `arm-less quarter 0 (none ...)`; on the 4.0.0 lab save the load pass reverted all four blocks (`(a)`: 20401 is not a known piece for that table), `0 qualify, 4 reverted`; that state saved (`no variant tiles`) and reloaded: `4 qualify, 4 converted`, all quarters 20400 | **not met as worded** (reverts first); behaviour now documented |
| V | 48 views x 3 games (mod, stock, BK), camera origins equal in all but 1 (mod2 W z2 r0). Closed side: edge line, gutter and sidewalk continuous between the two neighbouring quarters, no stub, no dashes, no splitter, terrain outside (owner shots 01-04) | owner to judge |
| T Moscow | camera by UI clicks, sim running, 480 s: (30,54) 0 movers in or near the block; (92,141) 5 failed moves at (90,144) only. Control (all quarters 20400, same method) at (30,54), 240 s: 0. The 4-arm (122,130) in the same build: 6,875 samples, 151 moves in 120 s | no traffic at the 3-arm blocks, arm and control alike |
| T Berlin (57,167) | arm (20401 at (57,168)) 480 s: 1,138 samples; control (all 20400) 480 s: 1,048. Same moves in both: N arm both ways, (58,167) -> (58,168) 5 / 6, (58,168) code 24 failed 5 / 6; **0 moves leaving or entering the closed quarter (57,168) in either**; 0 ring moves against the order in either; min distance from the centre 164.4 / 164.1. Codes seen: 0, 8, 16, 24 only, so no pedestrian move was counted | closed mouth unused: met; ring direction held: met; pedestrians: not measured |
| S | `netvariant.py scan`: 0 raw variant tiles, 12 entries, (30,55) and (92,141) saved as 11203 -> 20401, the other 10 as 39 -> 20400 (the `save:` log line was not captured: another game of mine held the instance log) | met |
| S0 | no-mod game: the 12 cells read the shipped tiles (11203 at (30,55) and (92,141)), 0 other differences | met |
| S1 | own log: `variant section 12 entries, 12 to restore`, `all 12 variant tiles restored`, `3 qualify, 0 converted, 0 reverted`; grids equal to the save with 20401 on the two cells | met |
| O | 6 PNG + captions.md | done |

## Incidents

- PID 7188 (Moscow, first T): "Not Responding" after picture camera calls followed by un-pause; stopped. Same trap as
  roundabout1 RESULTS 3 (camera calls and a running sim).
- PIDs 10892 (Moscow) and 1740 (Berlin), both with 20401 placed, exited by themselves some minutes after a 480 s probe
  ended, with no crash dump and no log line. Not reproduced: PID 9332 (Berlin, 20401 placed) ran 25 minutes with the
  sim running, a probe attached and detached, and stayed up. Cause not established `[UNCERTAIN]`.
- With several games in one instance folder only the first holds `sc3netmod.log`; later games need `SC3NETMOD_LOG`.

## Answers to the brief

- **Second piece**: 20401, base 39, same behaviour as 20400 (variant of T 39), placed by RBT on the arm-less quarter
  only. Rotation is the cell's own state, so the closed mouth always faces the missing arm (all 4 sides in the lab,
  3 sides in shipped cities).
- **Terrain under the piece** (NO-GUESSING point): the frame table bit 0x40 makes SIMSPR fetch and draw the cell's
  terrain under the occupant [CONFIRMED @ SIMSPR 0x100192aa, 0x1001a303]; 11203 ships it, 39 does not. With 39's
  frame geometry it still left holes; with 11203's it does not (measured). Why geometry matters was not traced.
- **Lanes**: ring only + outer sidewalk (11203 state 0's lane and walk). No entry or exit at the closed mouth, and in
  game no move used it (arm and control).
- **Rule, load, revert, saves**: unchanged behaviour; 20401 counts as either stock tile; saved as 11203; a save opens
  without the mod with the stock tiles; with roundabout3's two-number table a 4.0.0 save reverts to stock first.

Functions read for this task: SIMSPR `FUN_100192aa`, `FUN_1001a303`, `FUN_10019610`, `FUN_1001924c`, `FUN_1000dc17`
(head). SIMNTWRK code paths used are those of roundabout3.
