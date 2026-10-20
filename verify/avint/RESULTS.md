# avint: combined game check of round/avlanes (2026-10-20)

Branch round/avlanes at 939d9da (main f47edab + child/avcore + child/avjunc 06a9fc7 / 244dc22 + child/avmisc 1cc4aa3 +
child/avdiag 8c9eb39). Tested by avcore. Own hard-linked test tree `Simcity_stock_avint` (link_tree.py from MAIN's
install, 18,671 files), instance `re\harness\inst_avint` (sc3netmod.dll built from this worktree, 363,520 bytes, plus
sc3resize), and a second instance `inst_nomod` (sc3resize only) for the no-mod load. Harness claimed as avcore for the
run and released after. Packages installed at once (16): avenue_lanes, avenue_markings, avenue_junctions,
big_roundabout, boulevard, boulevard_junctions, diagonal_avenue, diagonal_boulevard, highway_core, highway_ask,
highway_avenue, highway_dd_cloverleaf, highway_diagonal_cloverleaf, hwt_trumpet, hwx_cloverleaf, roundabout (86 overlay
files). Own PIDs 29764, 42020, 70684, 43768, 56860, all closed.

Order kept for every game: load, unpause by sc3io keys (P, speed), attach Frida only after the sim runs (the sc3pause
guard in this tree confirmed "running" before each attach). The view was moved with minimap clicks and the zoom
buttons. `rb_lab cam` was only called with the zoom its capture click lands on, so the zoom job never changed the zoom.

## Seoul

| check | result |
|---|---|
| load counts (both fresh loads identical) | AVX load run: 149 junction boxes, 0 corner junctions, 1,011 cells; AVL: 124 bands converted, 57 refused, 1,494 cells (ends: 117 join / join, 3 + 2 with a U-turn end, 2 with a corner); AVX post: 184 cells; rbt / rbt9 / hwy: 0. No DAV / BV / DBV line: Seoul has no diagonal avenue, boulevard or diagonal boulevard. |
| piece census (whole map, after load) | 2,501 variant cells: avcore 1,490 (21700 x 1,432, 21701 x 11, crossings / slopes 21710..21723 x 46, 21726 x 1), avjunc 1,011 (boxes 20800..20899 x 885, crossings / one-way approaches 21750..21776 x 126); diagonal / boulevard / roundabout / highway-program pieces 0 |
| no hang, >= 3 game months | game 1: speed 4, 1/3/1999 -> 1/1/2004 (the year-end budget window paused the sim at the end), 18 / 18 watch samples responsive, plus 4 game months under hwtraffic_probe. Game 2: speed 2, 1/3/1999 -> 4/15/2000, responsive throughout |
| failed trips (hwtraffic_probe, game 1, speed 4, default LANEDENSITY mode) | month 1 (partial, 14 days) 2.44%; full months 2 / 3 / 4: 81 of 3,755 = 2.16%, 72 of 3,364 = 2.14%, 66 of 3,661 = 1.80%; mean of the full months 2.03%. The 1.95% baseline (verify/avlanes M1 arm B) ran with `SC3NETMOD_LANEDENSITY=all`; its arms ranged 1.59..2.36% per month. All three months lie inside that range |
| tracker pass (game 2, hwcars_tracks attached to the running game, box 30..80 x 40..90, 90 s, 219 vehicles) | `avl_tracks_an`: 4 visits against a 21700 half's direction, all by vehicles NOT on the road surface: 3 at (38,44) are subway trains (class 2, a different height, entering from cells with no surface road), 1 at (61,46) is a car at y 23808 that crosses on to cells with no surface road and on to (65,40) (the elevated highway over the avenue). Road cars on the one-way halves: 0 wrong-side visits. The check covers avcore's 21700 halves only; the siblings' one-way pieces are not checked by this tool |
| save (game 2) | `save: 2501 variant tile(s) written as base` (= the census) |
| reload with the mod | `load: all 2501 variant tiles restored`; AVL load pass 0 written; a whole-map census matches the pre-save census on every one of the 2,501 cells (0 differ). AVX writes the same 184 cells on the run and the post as on a fresh load |
| the same save without sc3netmod (inst_nomod, only sc3resize injected) | 0 variant ids on the map; every one of the 2,501 cells loads as its stock base at the same state (11204 x 2,113, 43 x 229, 39 x 101, 11203 x 12, slopes / crossings 31 / 32 / 15098 / 11258 / 69 / 11201 x 46) |

Tracker crash (game 1, not a mod fault): the first tracker pass used a whole-map box. About 2 minutes in, the game
process died with an access violation writing address 0 inside frida-agent.dll (+0x177B34), followed by a fault in
SC3U while it went down (`data/seoul1_tracker_crash.txt`, from sc3resize's VEH log). The tracker keeps every sample in
the 32-bit game process, and the whole-map box was the cause on the tool side; the 50 x 50 box in game 2 ran clean.
Use a small box with hwcars_tracks.

## London (load only)

| item | count |
|---|---|
| AVX load run | 375 junction boxes, 28 corner junctions, 2,543 cells; post 765 cells; stats: boxes seen 375, two-way arm 157, dropped 28 |
| AVL | 226 bands converted, 252 refused, 1,468 cells (ends among the first 200 logged: 166 join / join, 32 with one corner end, 2 corner / corner) |
| rbt9 | 1 roundabout qualified, 9 cells |
| corners on the map after load | 18 inner bends (21726). 8 of them have the outer bend 21701 (clean corners), 10 a corner junction on the outer cell: 21768 x 2, 21769 x 5, 21770 x 3 (X corners at (144,57), (157,102), (194,125), each 21770.0 with 21726.1 diagonal) |
| variant cells | 3,940 (avcore 1,406, avjunc boxes 2,223) |

The log's 28 corner junctions on the run against 10 on the map: AVX's stats count 28 dropped, so 18 were written back
to stock after AVL decided. Which rule drops them is avjunc's and was not read here.

## Owner shots (MAIN `verify\avint\owner_shots\`)

- `avint_seoul_overview.png`: Seoul, game 2 at 4/15/2000, zoom 2, one-way avenues and junction boxes.
- `avint_london_corner_area.png`: London at zoom 2 around the X corner (157,102). The corner's exact position in the
  picture is NOT established: rb_lab's pixel math, with the cell heights from the save (35 there), put the marks on
  a building, so it does not hold on raised terrain. Marked attempts are not shipped. A shot that shows a corner for
  certain: the lab sheets in `verify\avcore\owner_shots\` (avcore_corner_sheet.png, avcore_tcorner_lab.png).

## Data (`verify/avint/data/`)

`traffic_seoul.json` / `.txt` (hwtraffic_probe), `watch_seoul.txt` (hang watch), `tracks_seoul_an.txt` and
`grid_seoul.json` (tracker analysis and the piece grid of its box), `census_variants.json` (variant id counts: Seoul
before save, after reload, without the mod; London), `seoul_load_save.log`, `seoul_reload.log`, `london_load.log`,
`seoul1_tracker_crash.txt`.

## Not done / open

- Per-car checks of the siblings' one-way pieces (avjunc approaches 21772..21776, bvlanes, avdiag): the tracker
  analysis covers 21700 only.
- London: no per-car pass (load only, as asked).
- English-UK: not run (known limitation, AVENUE_LANES.md 2).
