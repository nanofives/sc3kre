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

**English-UK: known limitation (owner decision 2026-10-19).** English-UK stays mismatched; there is no job to make it
fully right-hand. What differs in an English-UK game:
- Right-hand (the same as in English): every piece the avenue rework adds. That is the converted one-way halves
  (21700), their U-turn ends and corner bends (21701, 21726), the road lanes of the one-way crossings and slopes
  (21710..21725, `uk_keep`), and the siblings' pieces, which follow the same rule (section 6: `"mirror_uk": false`).
  Each half runs the same way as in English.
- Left-hand (stock English-UK, mirrored): everything else. That is every two-lane road and its bends, T and X
  junctions, every avenue that does not convert (it stays stock two-way), the highways and ramps, and the rail /
  highway lanes on a one-way crossing.
- What a player sees: on a converted avenue, traffic keeps to the right; on the roads, unconverted avenues and
  highways of the same city, it keeps to the left. A car swaps sides where it passes between the two, in a junction
  box or at a crossing. The lanes still meet there (avcore's selftest and avjunc's seam checks run in English-UK
  too), so cars are not meant to stop or leave the road. That has only been checked offline.
- Routing in English-UK stays [UNCERTAIN] (the paragraph above). No English-UK game has run with these pieces.

Boulevards (bvlanes): each outer cell is a one-way half as above; the middle cell carries its side's third lane at z 14
(beside row 0) and z 241 (beside row 2) in the state-0 frame of the middle piece, running with the outer row beside it
(PLAN.md 9.2). bvlanes owns those numbers; the outer-cell edges follow this section.

## 3. avcore's pieces [published: all 18 in examples/avenue_lanes]

| id | base | what | saved as |
|---|---|---|---|
| 21700 | 11204 | straight one-way half (section 2), art = 11204's, state = the half's 11204 state | 11204, same state |
| 21701 | 11203 | avenue end U-turn quarter: one cell of the 2-cell U (see below); also a corner's OUTER bend (the same left turn), art = 11203's | 11203, same state |
| 21726 | 11203 | avenue corner INNER bend (see Corners below): a right turn, art = 11203's | 11203, same state |
| 21710..21725 | 69, 67, 11258, 15098, 31, 32, 11201, 11202 (k = 0..7 in that order) | a stock crossing / slope piece on a half, one-way: two ids per base (21710 + 2k = lanes toward the piece's x+ / z+ end at its own state 0, + 1 = the other way; `avlc` lines carry the side); the other network's lanes (rail, highway) and the pedestrians as stock; road lanes `uk_keep` (right-hand in English-UK too, the other lanes mirrored there as stock); matrix: the stock turns of the other network kept, the road's replaced by the one-way turn | the base, same state |

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

Corners (2026-10-19): a stock avenue corner is a 2 x 2 block past a band's last row: the end row holds the inner bend
(11203) and a half of the other axis (11204), the next row that half's partner (11204) and the outer bend (11203),
diagonal to the inner one and at the SAME 11203 state. The other axis's band begins beside the block, on the inner bend's
side. Measured with `py -3.12 -m netmod.avcorner_scan [--groups]` over the 15 shipped cities: 169 clean corner ends in 8
patterns (the table `AVL_CST` in sc3netmod_avl.c, `CORNER_PATTERNS` in avlanes.py), plus 214 ends where the outer cell
is a T 39 / X 43 (a road on the corner's outside; not handled, the band stays stock). One-way: inner bend -> 21726 (at
state 0 traffic enters across z+ and leaves across x-; median lane (175,255) -> (0,80) on r 175 = 23601 in English,
stock 1024's copy in English-UK; curb lane (80,255) -> (0,175) on r 80 = stock 768 in English, 23602's copy in
English-UK), outer bend -> 21701 (the U-turn quarter is the same left turn), the two halves -> 21700. No new curve, no
new art. Every lane keeps its side through the block (the inner bend's median lane takes the wide arc, the outer bend's
the tight one).

Corner with a road on its outside (2026-10-19, orchestrator: T + one road 110 ends, X 30 ends; "T next to T" and the
rest stay stock): the outer cell may hold a piece DECLARED with `avlj` (avjunc's box piece) instead of the bend. It
fits when its letters say I on the side the incoming half flows in from and O on the side the outgoing half leaves by.
In the outer cell's own frame at the corner's 11203 state that is always W = I, S = O (the U-turn quarter's own turn);
by world side per pattern: `py -3.12 -m netmod.avlanes corner-letters`. A declared outer cell is the declaring
stream's: avcore neither writes nor claims it, and joins the two bands through it as through a bend (all or nothing).
Before the box exists, `avl_corner_ok` (section 5) answers whether the group would convert with it.

Curve shapes: avcore 23600..23699. 23600 straight inner (255,80)->(0,80); 23601 English (175,255)->(0,80) on r 175
(for English-UK's U-turn outer lane); 23602 U-turn inner (0,175)->(80,255) on r 80; 23603 English (0,175)->(255,175)
(for English-UK's straight outer lane); 23604..23607 the slope pieces' missing same-direction lanes (31 / 32 share
23604 / 23605 by rotation, 11201 / 11202 share 23606 / 23607); 23608..23620 free.

lanekit: a vehicle lane may carry `"uk_keep": true`: `mirror_spec` leaves it as written, so in a spec with the default
`mirror_uk` only that lane stays right-hand in English-UK (avcore's crossings: the road lanes; the rail / highway lanes
keep the stock English-UK mirror so they meet their stock neighbours). Siblings may use any avcore curve key by number; they
write their own curves in their own ranges.

## 4. The band rule (sc3netmod_avl.c) [published]

An avenue band = the two halves running side by side along an axis. avcore converts a band only when ALL of it can
be one-way; otherwise it leaves the whole band stock two-way (owner decision).

- **Band cells avcore may write:** stock 11204 (-> 21700), the crossings and slopes of section 3, the 11203 pair of
  an end (-> 21701), and a corner block (inner bend -> 21726, outer bend -> 21701, its two halves -> 21700). Only stock pieces (id < 20000) and avcore's own pieces; never a cell another block claims
  (`dbv_claimed`, `hwave_claimed`, any other variant).
- **A band ends** (both halves at the same row) at one of:
  1. its stock end: the 11203 pair, which becomes the U-turn;
  1b. a corner block (section 3, Corners): acceptable when the band beyond it converts. That band is decided with this
     one, recursively, with its corner end taken as given; a loop of bands closes on itself (a band already being
     decided up the chain counts as acceptable). So bands joined by corners convert all or nothing, and an accepted or
     refused band processes the band beyond each corner in the same run, even outside the pass box;
  2. a cell on each half holding a piece DECLARED one-way by a sibling (`avlj` line, section 5), whose edge facing the
     band carries the band's direction (traffic of the half that flows into the piece = `I`, out of it = `O`);
  3. the map edge.
  Anything else (a stock T 39 / X 43 on a half, a plain road continuing a half, an undeclared variant) refuses the band.
- **Write / revert:** the game's piece writer FUN_10008919 per cell, as AVX / DAV. An avcore piece in a band that no
  longer qualifies gets its base back at the same state (the stock piece it replaced) before the writes; a rect retile
  would keep a Protected base (measured: rail crossing 69 stayed the one-way variant). Runs on every
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

C side for siblings (all blocks are #included into sc3netmod.c, so these are plain static functions; no per-sibling
pointers):

    int avl_dir(int x, int z);       /* -1: (x, z) is not a cell of a converted band; else the half's travel side 0..3
                                        (N E S W). Answers for straight halves AND crossing / slope variants, and
                                        for a corner block's two halves; -1 on U-turn cells and corner bends. Valid as soon as avl_run returns (the map is updated while each
                                        band is decided, before the writes). */
    int avl_claimed(int x, int z);   /* 1: avcore holds the cell (a band cell, its U-turn or a corner block cell): do
                                        not write it */
    int avl_own(WORD id);            /* 1: id is one of avcore's pieces */
    int avl_corner_ok(int x, int z);
                                     /* pure predicate for the stream that declares corner OUTER pieces: would the
                                        corner group through the outer cell (x, z) of a stock corner block (inner bend
                                        11203 / 21726, two halves) convert if (x, z) held a fitting avlj piece, whatever
                                        stands there now (stock T 39 / X 43 or the piece)? Nothing written, no cache. 0
                                        when AVL is off or (x, z) is not such an outer cell (a corner whose outer cell is
                                        a bend: use avl_band_ok on a band cell). */
    int avl_band_ok(int x, int z, int away);
                                     /* pure predicate, call it BEFORE you write: would the avenue band through (x, z)
                                        (any cell of it, either half, stock or ours), running away from you toward
                                        world side `away` (0 N 1 E 2 S 3 W), convert if the end on your side counted
                                        as a declared avlj join? Current road grid, the pass rules, nothing written;
                                        the same answer whatever stands at your end now. 0 when AVL is off, (x, z) is
                                        not a band cell or `away` does not run along the band. Program rule: a piece
                                        whose attached avenue would not convert stays in its pre-rework stock state. */
    int avl_post_set(int slot, AvlPostFn f);   /* the post-AVL phase, below */

Post-AVL phase: `rb_pass` / `rb_load_pass` call `avl_pass` = avl_run, then the slots:
`AVL_POST_DAV` (avdiag's diagonal put-back) and `AVL_POST_BV` (bvlanes, if it needs one) after every avl_run, may ask
for a re-run; `AVL_POST_AVX` (avjunc's avx_post) ONCE at the end, on avl's final band map.

    typedef int (*AvlPostFn)(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int *rbox);

Set your slot once (e.g. from your table-line handler: `avl_post_set(AVL_POST_AVX, avx_post_hook);`). A re-run hook that
put something back returns 1 with rbox = the box to re-decide (x0 z0 x1 z1); the phase runs avl_run over the union of
the asked boxes and the re-run hooks again, at most 4 re-runs per pass; avx_post's return value is ignored. A second
avl_run on a smaller box in the same pass is safe: it re-walks every band through that box whole. Declarations (`avlj`): up to 4096 for all packages together;
an `avlj` line may name a ROAD or a HWAY variant (hwave's ground row).

In game (lab, 2026-10-19): two parallel road drags (x 50 / 51, z 20..36) -> `avl: edit: band along z from (50,21)
rows 0..14 -> one-way (ends: U-turn / U-turn)`, 34 cells (21700.1 / 21700.3, 21701 at 3 / 0 and 2 / 1); save
`34 variant tile(s) written as base`; reload `load: all 34 variant tiles restored`; a game without sc3netmod loads
stock 11203 / 11204 at the same states. Art: avenue_markings' white dashes (`avenue_markings.py build` into the
package folder).

## 6. Rules for every stream's lanes [published]

- Right-hand everywhere: every lane spec sets `"mirror_uk": false` so English-UK gets the same lanes (the stock
  mirrored copy would disagree with the single turn matrix all languages share).
- Turn matrices explicit and one-way where the lanes are one-way; high half = transpose of low.
- No `path` keys in lane specs (section 2): curves by end points in each language. lanekit.compile_spec then (a)
  prefers the spec's OWN new curves among curves with the same end points (bvlanes' change, adopted here) and (b) keeps
  only curves whose end heights match the nodes (avcore: Paths.find matches x / z only, so a flat curve could be picked
  for a slope lane; it was, for half of avcore's slope lanes, before this fix).
- Check every edge your piece shares with a one-way half against section 2 offline before the game: avcore's
  `re/tools/netmod/avlanes.py` [published] has `edge_nodes(state, side)` (the two nodes a one-way half at `state` puts on
  `side`, in travel order) and `check(a, state_a, b, state_b, side, lang=...)` (every exit of one piece meets an entry
  of the other at the same position and direction; a / b = a piece id or a lanes.json path; run it for ENGLISH and
  English-UK). `py -3.12 -m netmod.avlanes selftest` checks avcore's own pieces (PASSED in both languages).
- Curve sort id: new curves follow the stock rule (2026-10-19). A curve record's trailing u32 is the path's sort id:
  STRTSIM SerialReadBinary 0x1001e673 stores it at +0x34 as file value + 1 (Linux oracle accessor `SortId`); a car
  taking a path whose sort id differs from its current one copies it to vehicle +0x150 and sends it to the anim
  occupant manager (DAT_10033218 vt+0x6c, property 0x80) at STRTSIM 0x1001b030, 0x10018820 and 0x1001bc70. What it
  controls downstream is [UNCERTAIN]: the consumer behind that call (SC3U.exe vtable 0x004d1088, slot +0x6c) is not
  traced. Stock: all 192 flat ground curves carry 0, all 408 deck curves 2. `hwlanes.extra_for` writes the same: 0 when
  every point is at y 0, else 2 (ramps / mixed heights stay 2 until measured); curve_set, curve_records and inject agree
  (`py -3.12 -m netmod.hwlanes selftest`, also run by avlanes selftest). Until 2026-10-19 hwlanes wrote 2 on every new
  curve. It was briefly the lead for a game hang; that hang was retracted (next item), so this is a stock-matching
  rule, not a fix.
- Lab trap (avjunc 2026-10-19): installing Frida hooks (hwtraffic_probe, a segment tracer) while the game is PAUSED and
  letting the probe's `--start` unpause it, with one-way pieces on screen at zoom 4, deadlocked SC3 every time; it was
  first misread as "a car on a radius-80 left turn (23602) hangs the game". Without a probe: the U-turn end at Seoul
  (51, 62..63) 5 min, a junction ring 7 min, no hang. Attach probes after the sim is running. avcore
  2026-10-19: a Frida attach made while paused and DETACHED before the keys unpaused the game deadlocked too (same
  stacks); unpausing first and attaching after was clean for 6 game months. Why that sequence deadlocks is [UNCERTAIN].
- Report tool, not a rule: `py -3.12 -m netmod.avlanes tightleft <package dir> [...]` lists every car lane whose curve,
  as driven, has a left bend of radius <= 80 (cut at 88 for the curve files' rounding), English and English-UK, with
  the curve key, height and stock / new. Stock itself drives such bends (English 11225, 1999, 18004, 15045 at r 42..65;
  every English-UK road corner on 768..771 at r 80), and so does avcore's U-turn inner lane (23602).
