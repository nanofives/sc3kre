# roundabout3: results (2026-10-14)

PRE: `verify/roundabout3/PRE.md` (4a04f22, before the first launch), addenda 1-4 (5018765, 6eab2ff, 12c7844, 48fa144),
each committed before the frames or run it predicts. Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_roundabout3`
(stock GZGraphicD / SIMSPR / SIMNTWRK), instances `re\harness\inst_rb3` (sc3resize + sc3netmod from this branch) and
`inst_rb3_nomod` (sc3resize only). PIDs 2920, 5096, 8720, 11644, 9828, 3400, 15840, 556, 9208, 11568, 12028, 16180:
all mine, all stopped with taskkill /PID. Logs, saves, grids and frames stay in those folders (`shots\V0` = the 36
lab views). Owner pictures: `MAIN\verify\roundabout3\owner_shots\` (5 PNG + captions.md, not in git).

## Changes after PRE (each reported, none silent)

1. **Rule (c), before PRE.** First draft: "no road on the corner beside a road exit". `rb_auto.py scan` on the shipped
   cities showed it refuses single diagonal roads (piece 35) and roads that bend right after the exit; PRE was written
   with the 2x2-of-road form.
2. **White line (addendum 1).** V0 not met as worded (below). Cause found in `netpaint.py`, fixed (dash phase).
3. **Metric G (addendum 2).** Wrong metric for the question (single radius); G' pre-registered before use.
4. **Zoom-3 band (addendum 3).** `give_way.r_z3 = [208, 222]` after the zoom-3 frames still showed 1-px dots.
5. **Load-time revert (addendum 4).** Arm added before its run.

## Static

| check | outcome |
|---|---|
| `netpack.py validate examples/roundabout` | OK, `auto roundabout: piece 20400, >= 3 arm(s)`; no template, no Protected or Collapse edit |
| `netpack.py selftest` | 0 failures |
| `netpaint.py seams` (after both art changes) | 1320 / 1320 |
| no arrows | marking pixels inside the ring (r 136..208, under every zoom's give-way band), 20 frames: 3.0.0 **0**, 2.0.0 306 (z3 60, z4 246) |
| `rb_auto.py scan`, 16 shipped cities | 7 qualify: Berlin (29,86) (57,167) (145,102), Craterville (132,148), Moscow (30,54) (92,141) (122,130) |

## In game

| arm | outcome | verdict |
|---|---|---|
| L | `rbt: ... piece 20400, at least 3 arm(s)`, `hooked the retile pass FUN_1001547b (entry) and the city load (manager vt+0x1c)`, `tmpl: no templates`, `### READY ... load=patched`; 0 `### rbt` lines in any run | met |
| TH | load (`rbt: city load`), the load-pass message and every tool retile on the same thread id in each run (e.g. 1708 / 1708 / 1708 in the lab) | met (gate passed) |
| A | Moscow `3 qualify, 3 converted` at (30,54) (122,130) (92,141) (twice); Berlin 3 at (29,86) (145,102) (57,167); Craterville 1 at (132,148). Every block 20400 in states 3,0 / 2,1 at the right cells; 0 other cells differ from the save in 10x10 boxes. full-map pass on a 256 map: 8 to 12 ms (log times) | met |
| B1 | stock tiles after each stroke as simulated (39.3 11203.0 / 11203.2 11203.1, then 39.3 39.0 / 11203.2 11203.1); converts on the 3rd arm, 20400 after the 4th | met |
| B2 | 3 arms: converts | met |
| B3 / B4 | 2 arms W,N 39.3 39.0 / 11203.2 11203.1; 1 arm 39.3 11203.0 / 11203.2 11203.1; no conversion | met |
| B5 | converts at 3 arms, stays at 4, reverts when the 2-wide N road is complete: 39.3 39.0 / 39.2 39.1, exit 39.2, corner 11203.1, 11204.1 / 11204.3, ends 11203.3 / 11203.0 = the simulator's grid | met |
| B6 | two 2x2 side by side: 39.3 11204.2 11204.2 11203.0 / 39.2 11204.0 11204.0 39.1, no conversion | met |
| B7 | converted 3-arm block, second road beside its N arm: back to 39.3 39.0 / 11203.2 39.1 | met |
| B8 | converted 3-arm block, E arm's first cell demolished: 39.3 39.0 / 11203.2 11203.1 | met |
| B9 | converted block, second 2x2 on its E exit: block 39.3 39.0 / 39.2 39.1, second 39.3 11203.0 / 11203.2 11203.1 | met |
| B10 | one block cell demolished: 3 cells left, none 20400 | met |
| B, extra | lab: 2-wide road beside the N arm -> stock (4-way pinwheel 39.x with crosswalks); its 3 cells demolished one by one: converts again when the 2x2 of road outside the exit is broken (2nd demolish) | observation |
| T | Moscow (122,130), 480 s: ring moves 178 counter-clockwise, **0 against**; into the ring 118 (all 4 arms: 28 / 41 / 25 / 24), out 100, 0 failed; 81,488 vehicle samples, **0** closer than 129.5 to the centre, min 173.1 | met |
| S | `save: 12 variant tile(s) written as base`; `netvariant.py scan`: 0 raw variant tiles, 12 entries; (30,55) and (92,141) saved as 11203, the other 10 as 39 | met |
| S0 | saved Moscow without sc3netmod: the 12 cells read the shipped tiles (39.x and the two 11203), 0 other differences in 10x10 boxes | met |
| S1 | with the mod: `12 to restore`, `all 12 variant tiles restored`, load pass `3 qualify, 0 converted, 0 reverted`, grids equal to S | met |
| addendum 4 | saved Moscow with a `rbt 20400 4` table: `all 12 restored`, `(30,54) ... no longer qualifies (d (arms)) -> stock retile`, same for (92,141), `1 qualify, 0 converted, 2 reverted`; the two blocks read the shipped tiles, (122,130) stays 20400, 0 other differences | met |
| V0 | lab 4-arm block, roundabout vs stock frames pixel-aligned (same camera origins in both games), outline = pixels within 1.5 px of the block's outer edge: W = **0** in all 12 views. Brighter than stock by > 60: 22 sidewalk-grey pixels per zoom-4 view (e.g. 160,176,184 vs 136,152,152), none at zooms 2-3 | **not met as worded** (no line on the block edge) |
| V cause | pixel provenance of the 20400 frame (zoom 4, slot 0): the thin white line along the ring's edge at each entry is the give-way marking (35 white px) plus the arm's own edge line (30). Dash phase `r_o * (th mod 2pi)` moves about 38 units across the 7-unit band (one 40-unit period): 90% of the entry span's angles have an "on" pixel, in 2 runs. Fixed phase: 58%, 5 dashes | cause shown |
| G | before: z4 48 runs, z3 20; after (`af_*`): z4 20 runs (16..24 met), z3 18 (not more than before: not met) | mixed |
| G' | before: z4 paint 0.378 (>= 0.35 met), runs 40 (<= 12 not met). After `af_*`: z4 0.310 (met), runs 28 (16..24 not met); z3 18 runs vs 18 (not met) | mixed |
| addendum 3 | `af2_*` (zoom-3 band 14 units): z4 identical to `af_*` (G 0.256 / 20, G' 0.310 / 28); z3 G' paint 0.306 > 0.213 and 22 runs (16..24); W 0 in all 12 views; seams 1320 / 1320 | met |
| O | 5 owner pictures + captions.md | done |

Run counts on screen pixels are not a reliable measure of the dashes: a 1-px diagonal line breaks into many runs when
sampled finely, which is why G and G' "runs" missed both ways. The paint fraction and the pictures (owner shots 01, 02)
are the evidence that matters: zoom 4 now shows separate dashes on all four entries in every rotation.

Deviations: nramp_cam's zoom or rotation call returned "system error" 5 times over the session; each time the view was
re-taken (its state is printed per call). The B3 site was first tried at (144,120), where the terrain is not at
altitude 82: the strokes landed on other cells (rows show slope piece 32); B3 and B5-B10 were re-run at flat sites
picked from the save's height map. The sequence pictures (owner shot 05) are at zoom 3 and show the active tool's
cursor at the last mouse position.

## Answers to the brief

- **Cost**: free. The road is already paid for; the conversion writes 4 pieces with `FUN_10008919`, no budget call.
- **Protected / Collapse**: the roundabout piece is in neither. Every stock retile that reaches the block re-places it as
  stock road; RBT then converts it again when it still qualifies. That is the revert path in play; the load pass uses
  the rect retile `FUN_100151f1` for saved roundabouts that no longer qualify.
- **"Touches an avenue / another 2x2"**, from the measured tiles: an avenue on a closed side or along a side turns block
  cells into 11204 (rule a, b); an avenue or a second 2x2 at an exit makes the exit, the corner beside it and the two
  cells beyond all road (rule c); B5, B6, B9 grids above.
- **Mirrored pinwheel**: never converts (one piece, one chirality).

Functions read for this task: SIMNTWRK `FUN_1001547b` (signature, ret 0xc, box write), `FUN_100151f1`, `FUN_100130e9`
(entry, `this` = manager), `FUN_10008919`, `FUN_100165d8`, `FUN_10007791`, `FUN_1001a93d`, `FUN_1001a056`,
`FUN_10023c14`; manager vtable 0x1002c7bc slots +0x1c / +0x14c / +0xb0 read from the PE.
