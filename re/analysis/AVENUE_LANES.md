# AVENUE_LANES.md - one-way avenue halves: the avcore base (task avcore, 2026-10-19)

Owner: avenues are 2 lanes each way (3 on boulevards), one direction per half, right-hand traffic everywhere (English-UK
included), an avenue the mod cannot convert whole stays stock two-way. Plan and inventory: `verify/avlanes/PLAN.md`;
routing check M1: `verify/avlanes/RESULTS.md`. This file is the contract between avcore and the sibling streams
(avjunc, avdiag, avmisc, bvlanes). It is owned by avcore: ask for changes (send_to_session, cc the orchestrator).

Status of each part: **[published]** = fixed, build on it; **[coming]** = avcore is building it, the interface below is
what it will be.

## 1. Direction rule [published]

Stock 11204 state s = which half (measured on 26,752 shipped cells, 100%): the half's median lies on world side s
(N E S W = 0 1 2 3; N = -z, E = +x, S = +z, W = -x). Right-hand traffic = the median on the driver's left:

    travel direction of a half at state s = world side (s + 3) % 4
    state 0 -> W (-x), 1 -> N (-z), 2 -> E (+x), 3 -> S (+z)

The same rule holds for every piece that carries an avenue half in a one-way band, whatever its own state convention:
a sibling piece states the direction of each avenue edge explicitly (section 5), it is never inferred from its state.

## 2. Lane positions of a one-way half [published]

Frame = the half at state 0 (a band along x, this cell is the z+ half, median on its N edge z = 0, traffic -x):

| lane | entry node | exit node | curve |
|---|---|---|---|
| inner (median side) | (255, 0, 80) | (0, 0, 80) | found by end points: new 23600 in English etc., stock 512's reversed copy in English-UK |
| outer (curb side) | (255, 0, 175) | (0, 0, 175) | found by end points: stock 256 in English etc., new 23603's copy in English-UK |

Coordinates are lanekit's (x, y, z) in 0..255 cell units. **Lane specs carry no `path` keys**: lanekit then searches
each language's own curve library by end points. That matters because English-UK's VPathAtt holds every curve REVERSED
under the same key (lanekit MIRROR_LANGS): with right-hand lanes in every language (`"mirror_uk": false`), a fixed key
would make UK cars drive the curve backwards. Where a language has no curve with the right end points, add a new shape
in your range; a shape whose English geometry is the REVERSE of the lane gives English-UK the forward copy (hwlanes
writes UK copies reversed). avcore's 23601 and 23603 exist only for that. Other states by lanekit's rotation (`lanekit.rotate`: the
shipped rule; one state step maps sides x- -> z- -> x+ -> z+ -> x-, measured on 11203's records). So at any state the
inner lane runs 80 units from the median edge and the outer lane 175, both in the half's direction. Both nodes sit at
the stock slots 80 / 175, so where a one-way half meets a piece, the arrival node is found by position as for stock
roads (72-unit buckets, NET_LANES.md 2.3): **a sibling piece's avenue edge must put its two nodes at exactly these
positions, with the same direction**, or cars that reach it vanish (verify/hwcars: the hwdx hand-offs).

Turn matrix (props 310) of a straight one-way half at state 0: low half x+ => x- only, high half its transpose x- => x+
(the tiler counts a side as an arm if either half has a bit there; every stock mask has high = transpose(low)). The
router reads the low half in this install (layer +0x54 = 1, NET_LANES.md 1.3); sc3netmod LANEDENSITY enforces it on
every variant (default mode). Packed: `0x00040100`.
**English-UK routing [UNCERTAIN]:** lanekit notes the high half serves English-UK's lanes. If the router reads the high
half in an English-UK install, UK trips would route left-hand on these pieces while their cars drive right-hand. Not
tested (no English-UK install here). Making high = low would drop the downstream side as a tiler arm.

Boulevards (bvlanes): each outer cell is a one-way half as above; the middle cell carries its side's third lane at z 14
(beside row 0) and z 241 (beside row 2) in the state-0 frame of the middle piece, running with the outer row beside it
(PLAN.md 9.2). bvlanes owns those numbers; the outer-cell edges follow this section.

## 3. avcore's pieces [published: 21700 / 21701 lanes in examples/avenue_lanes; crossings / slopes coming]

| id | base | what | saved as |
|---|---|---|---|
| 21700 | 11204 | straight one-way half (section 2), art = 11204's, state = the half's 11204 state | 11204, same state |
| 21701 | 11203 | avenue end U-turn quarter: one cell of the 2-cell U (see below), art = 11203's | 11203, same state |
| 21710..21725 | 69, 67, 11258, 15098, 31, 32, 11201, 11202 | a stock crossing / slope piece on a half, one-way: two ids per base (21710 + 2k = lanes running toward the piece's x+ / z+ end at its own state 0, + 1 = the other way); the other network's lanes (rail, power, highway) unchanged | the base, same state |

End U-turn: a stock avenue end is a pair of 11203 bends. Measured on the 15 shipped cities: 9 clean ends, all in
one of four patterns (band along z, ending to the N: x- cell 11203.3, x+ cell 11203.0; to the S: x- 11203.2, x+
11203.1; band along x, ending to the E: z- cell 11203.0, z+ cell 11203.1; to the W: z- 11203.3, z+ 11203.2). Any other
pair of 11203 next to a band is a bend that turns a half into a road (2 such cells), not an end: the band rule refuses
it. Right-hand traffic always turns the same way through an end, so one piece covers both cells of every pattern: at
state 0, traffic enters across x- and leaves across z+; outer lane (0, 0, 80) -> (175, 0, 255) on a radius-175 quarter
circle about (0, 255), inner lane (0, 0, 175) -> (80, 0, 255) on radius 80. Curves: outer = stock 1024 (11203's own) in English etc., new 23601's UK copy in English-UK; inner = new
23602 in English etc., stock 768's reversed copy in English-UK. Clean
ends are rare in the shipped cities: most avenues there end in a road junction, so they convert only once avjunc's
pieces are declared (section 5).

Curve shapes: avcore 23600..23699. 23600 straight inner (255,80)->(0,80); 23601 English (175,255)->(0,80) on r 175
(for English-UK's U-turn outer lane); 23602 U-turn inner (0,175)->(80,255) on r 80; 23603 English (0,175)->(255,175)
(for English-UK's straight outer lane); 23604..23620 reserved for the slope / crossing pieces. Siblings may use any avcore curve key by number; they
write their own curves in their own ranges.

## 4. The band rule (sc3netmod_avl.c) [published]

An avenue band = the two halves running side by side along an axis. avcore converts a band only when ALL of it can
be one-way; otherwise it leaves the whole band stock two-way (owner decision).

- **Band cells avcore may write:** stock 11204 (-> 21700), the crossings and slopes of section 3, and the 11203 pair of
  an end (-> 21701). Only stock pieces (id < 20000) and avcore's own pieces; never a cell another block claims
  (`dbv_claimed`, `hwave_claimed`, any other variant).
- **A band ends** (both halves at the same row) at one of:
  1. its stock end: the 11203 pair, which becomes the U-turn;
  2. a cell on each half holding a piece DECLARED one-way by a sibling (`avlj` line, section 5), whose edge facing the
     band carries the band's direction (traffic of the half that flows into the piece = `I`, out of it = `O`);
  3. the map edge.
  Anything else (a stock T 39 / X 43 on a half, a plain road continuing a half, an undeclared variant) refuses the band.
- **Write / revert:** the game's piece writer FUN_10008919 per cell, as AVX / DAV. An avcore piece in a band that no
  longer qualifies goes back to stock with the rect retile FUN_100151f1 before the writes (AVX's order). Runs on every
  ROAD retile pass and on the city-load pass, AFTER every other road block (DBV, DAV, AVX, BV, RBT9, the hwave road
  pass), so siblings' pieces are already in place when a band end is checked.
- **Save:** every avcore piece saves as its base at its own state (no state change), so a game without the mod loads
  the stock avenue. Load: the load pass converts old cities.
- **Routing:** LANEDENSITY (default mode) enforces the variants' one-way matrices; nothing to add per piece.
- Off: `SC3NETMOD_AVL=0`. Stats line `stats: avl ...` every 10 s.

## 5. How a sibling piece joins a one-way band [published]

A sibling's block writes its own pieces as today. To let avcore end a band on a piece, the sibling's package declares
the piece's avenue edges (netpack manifest key `avenue_lines`, raw lines, like `highway_lines`; the lines must name ROAD variants of the same
package):

    avlj <piece> <N><E><S><W>

one letter per side at the piece's state 0: `I` = a one-way half's traffic ENTERS the piece across this side, `O` = it
LEAVES across this side, `.` = no avenue half on this side. avcore turns the pattern by the cell's state. Example: a box
cell on the x- half of a band along z, where that half runs -z (north) and meets the box at the box's S side, has
`I` on its S side at that state. The piece's lanes on an `I` / `O` side must be exactly section 2's nodes in that
direction. avcore checks the letters; it never looks inside the piece.

C side for siblings (all blocks are #included into sc3netmod.c, so these are plain static functions):

    int avl_dir(int x, int z);      /* -1: (x, z) is not a cell of a converted band; else the half's travel side 0..3 (N E S W) */
    int avl_claimed(int x, int z);  /* 1: avcore holds the cell (do not write it) */

Both answer from the last pass's result (the band map avcore keeps for the whole map, rebuilt per pass over the pass box).
avcore runs LAST in every ROAD retile pass and in the load pass, so a sibling block cannot call these for cells of the
same pass; use them to leave converted cells alone on the next pass, and rely on the `avlj` letters for the ends.

In game (lab, 2026-10-19): two parallel road drags (x 50 / 51, z 20..36) -> `avl: edit: band along z from (50,21)
rows 0..14 -> one-way (ends: U-turn / U-turn)`, 34 cells (21700.1 / 21700.3, 21701 at 3 / 0 and 2 / 1); save
`34 variant tile(s) written as base`; reload `load: all 34 variant tiles restored`; a game without sc3netmod loads
stock 11203 / 11204 at the same states. Art: avenue_markings' white dashes (`avenue_markings.py build` into the
package folder).

## 6. Rules for every stream's lanes [published]

- Right-hand everywhere: every lane spec sets `"mirror_uk": false` so English-UK gets the same lanes (the stock
  mirrored copy would disagree with the single turn matrix all languages share).
- Turn matrices explicit and one-way where the lanes are one-way; high half = transpose of low.
- No `path` keys in lane specs (section 2): curves by end points in each language.
- Check every edge your piece shares with a one-way half against section 2 offline before the game: avcore's
  `re/tools/netmod/avlanes.py` [published] has `edge_nodes(state, side)` (the two nodes a one-way half at `state` puts on
  `side`, in travel order) and `check(a, state_a, b, state_b, side, lang=...)` (every exit of one piece meets an entry
  of the other at the same position and direction; a / b = a piece id or a lanes.json path; run it for ENGLISH and
  English-UK). `py -3.12 -m netmod.avlanes selftest` checks avcore's own pieces (PASSED in both languages).
