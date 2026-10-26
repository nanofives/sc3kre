# avxroad: avenue x road "not merging" (owner hand test 2026-10-26, LAN build sc3mods-2026-10-25d = main 9825dc4)

Owner: "this intersection on avenues are not merging properly" (MAIN `verify/avxroad/owner_shots/img1_avenue_x_road_not_merged.png`),
then "on berlin this road looks wrong" (`img2_berlin_avenue_48_183.png`, Query ID (48,183) = 11204 state 1).
Branch `child/avxroad` from main 7d3493b. Sheet: MAIN `verify/avxroad/owner_shots/avxroad_sheet.png`.

## Cause

- img1 is not a straight crossing. It is two roads meeting the avenue from opposite sides one position apart. The two
  yellow centre lines are parallel and 130 px apart, and the road is 129 px wide in that view (vertical extent at a
  fixed x), so the offset is 1 cell.
- **The stock tiler drops both T's in that layout.** Measured in a game with only sc3resize + sc3bigcity (no netmod, no
  overlay), lab avenue x 123..139 z 30/31: road N at x 128 gives `39.1` at (128,30). Road S at x 129 then turns (128,30)
  back to `11204.2` and never makes a T at (129,31). Each road ends as a `29` whose arm points into a straight half with
  no arm back, so the roads are not connected (same with AVX + AVL off).
- AVX then finds only straight pairs (no position with an outside arm), so no box forms, and AVL converts the stretch
  as plain band `21700`. That is img1 (`before_mod_offset1_T.png`).
- img2 (Berlin (48,183)) is the same family: in the shipped city the W road `29.0` at (47,183) points into the W half
  `11204.1` of a 2-row avenue stub, which has no arm back.
- Checked fine before the fix, in game: straight X (avenue first, road first), T from N, T from S, a 2-position offset
  (stock links it as a Z of T's, AVX makes two T boxes). A road crossing 2 cells from an avenue end stays stock 43 / 39
  with the band two-way (existing behaviour, not reported).

## Fix (code only, no new ids, switch `SC3NETMOD_AVXDROP=0`)

`sc3netmod_avx.c` `avx_drops` (task avxroad), run in `avx_run` after `avx_caps`, before `avx_find`. A straight half
(11204 or avcore's straight) whose outside neighbour is a plain road piece (29 / 39 / 43 / 11203) with an arm toward it
is re-read for this pass with that arm (the `virt` mechanism of task avx32). The two positions then form one box with a
road arm on each side, and every cell pattern it needs is already declared: 20815 `AAII ITOT` and 20817 `ICAI ICOT`
for the pair in img1, and 20814 / 20816 for the mirrored offset. Lanes follow the existing box rules: row flow one-way
by the half's direction (right-hand), median opening two-way, road arms two-way. The noses are the existing 20801 /
20802. A box the validation drops writes nothing, so the cells stay what they were. AVL never sees the re-read.
Neighbours that are another avenue's half, a rail crossing (69), a slope (31) or 15098 / 11258 are left alone. That is
64 of the 227 dangling arms in the shipped cities, and they are other shapes.

Twin: `re/tools/netmod/avjunc_rule.py` `dropped_tees` (called from `find`, `tees=True`). `avl_bands` now ignores the
re-read halves and stops at box cells, as the C AVL block does (without that, a re-read half that formed no box split
its band in the twin only).

## Proven in game (tree Simcity_stock_avxroad)

| case | result |
|---|---|
| offset 1, avenue first, N road then S road (axis x) | box 20815.3 / 20817.3 + 20817.1 / 20815.1, noses 20802 / 20801, both bands one-way (`after_offset1_T_view0.png`) |
| offset 1, roads first then the avenue across their ends, both offsets (N at c / S at c+1 and N at c+1 / S at c) | both boxed (20815 / 20817 and 20814 / 20816) |
| avenue along z, roads W then E and E then W, both offsets | both boxed (`after_reload_axisz_view0.png`) |
| save + reload | 106 variant tiles saved as base. Reload: load passes write 0 cells and the three test areas are identical, with the first DLL and again with the final one |
| save loaded without netmod | stock ids only (43 / 39 / 11204 / 11203). The pair loads as 43 + 39 per half and the roads stay joined (`nomod_load_offset1.png`) |
| final DLL, fresh edit | offset pair boxed (`after_offset1_T_view2_final.png`) |
| Berlin load | 54 re-read halves (stats line), equal to the twin's 54 for Berlin. (48,183) becomes box 21763 / 21750 with two-way noses (the stub's bands are too short to convert), view 1 `after_berlin_48_183_view1.png` |

Pictures were not compared against the owner's exact Berlin (theirs has their own edits), only against the shipped city.

## Offline (twin over the 16 shipped cities)

- 199 re-read halves (163 of them the img1 pair pattern), 106 new boxes, 24 boxes replaced by a bigger one (a stock T
  plus a dropped T become one 2-position box or an X), 0 boxes lost outright, 0 band cells lost (cells that left a band
  became box or nose cells), 152 more band cells converted. 13 re-read halves end up in no box and stay as stock.
- `avjunc_rule.py check`: mismatched edges 125 -> 101. The 23 `nose C|T 29` mismatches (a nose closed beside a road
  arm 29 = exactly these dangling roads) are gone. No new kind appears.

## Traffic: the roads are connected for trips (orchestrator ask)

`re/tools/netmod/avxroad_trips.py` (read-only Frida, hooks of hwtraffic_probe.py: route_trip FUN_100070d0 and the
per-node deposit FUN_10006edd of an arrived trip's path). A site is an avenue half and the road cell pointing into it
(51 sites in Berlin, from `avjunc_rule.dropped_tees` limited to cells inside a box). A trip CROSSES a site when its path
steps directly between the two cells. Two Berlin games run side by side, speed 4, 300 s each:

| game | trips routed | arrived | trips crossing a site | sites crossed |
|---|---|---|---|---|
| fix on | 205,928 | 204,766 | 4,603 | 45 of 51 |
| `SC3NETMOD_AVXDROP=0` (= LAN build) | 206,749 | 205,595 | 1,126 | 7 of 51 |

- The 7 sites crossed without the fix are places where the avenue half stayed STOCK 11204 (unconverted). The stock
  router does not use turn matrices there, and LANEDENSITY enforces matrices only on our variants. Where the half is
  avcore's one-way 21700 (img1's case), nothing crosses without the fix.
- The 6 sites never crossed with the fix: one is a 3-cell dead-end stub. The other 5 hold the box pieces (read in game:
  20844, 20814 x3, 20815), and each road side reaches the rest of the network another way, so no trip needed them in
  300 s. The same piece 20814 carries 555 crossings at (88,35).

## Berlin (48,183), img2 (orchestrator ask: what the blocks do to stock-city avenues on load)

Cells (shipped city, identical in the stock game and in the LAN build before the fix):

```
z\x     47      48      49      50
181      B    39.2 11203.0      .     <- the diagonal road (35) joins the W half (T), the E half ends in a curve
182      B 11204.1 11204.3      .
183   29.0 11204.1    39.2      .     <- W road (29.0) points into the W half, which has no arm back
184      B       B    39.2   29.0
```

- **On load, before the fix, no netmod block writes any of these cells.** AVX finds no box (the W road's arm dangles),
  AVL has no band (2 rows, both ends stock), RBT / RBT9 / hwy do not qualify there. Frames of the stock game (no netmod,
  no overlay), the LAN build and the fix at the owner's angle: `berlin_48_183_compare_view0.png` (view 1:
  `..._view1.png`). Stock and the LAN build look the same. So img2's stub, with the curve end cutting in beside the T,
  crosswalks on the two T's and the W road stopping at the curb, is the stock tiler's layout, not a mod artefact.
- The fix boxes row 183 (21763 / 21750, every arm two-way because the stub's bands are too short to convert) with
  two-way noses 20810 / 20811 on row 182. The W road now joins, and trips use it (site (48,183): 534 crossings in 300 s
  with the fix, 320 without, the half being stock). Three frames 6 s apart: traffic moves through it, nothing stuck.
- **Not changed:** row 181, the stock T where the DIAGONAL road (35) meets the W half, beside the 11203 curve ending the
  E half. AVX only takes straight roads (a 35 arm reads as unknown and refuses the box). Making that end a junction is
  diagonal-road work (DAV / avdiag), a separate task. The owner's own Berlin is not the shipped one (zones where the
  shipped city has buildings), so their exact cells there are not known.
- Old cities load cleanly with the fix: Berlin, London and Seoul each loaded and ran 60 s at speed 3, with no fault
  beyond the startup privileged-instruction probe at SC3U+0x84122 (also there with no netmod). Re-reads per city in game
  equal the twin: Berlin 54, London 36, Seoul 10. Berlin load writes: AVX run 3,032 cells (2,848 before), AVL 1,000
  (1,158), AVX post 651 (651).

## Trap found on the way

Several games in one tree share `Apps\`, and np_drive's `shot` drops `DUMP` there, so ANY of them may answer it. Two
multi-game frames came from the wrong game. Use `SC3RESIZE_FRAMEDUMP=<instance>\fd_` per game (and its `req` file);
every frame in owner_shots was re-taken that way, or with one game running.

## Not done / open

- Lane-following of individual cars through the new boxes not traced (routing proven above).
- Row 181 of Berlin (48,183): diagonal road ending at an avenue end, stays stock (see above).
- Behaviour change beyond img1: every shipped or player city with this stock pattern gets a junction on load, so those
  roads now connect to the avenue where stock left them unconnected.
