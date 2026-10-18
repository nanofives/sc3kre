# hwdd milestone 1: diagonal highway x diagonal highway, stock aftermath and the plan (2026-10-18)

Owner picture: `MAIN\verify\hwdd\owner_shots\hwdd_plan.png` (drawn by `re/tools/netmod/hwdd.py plan`).
Stock shots: `MAIN\verify\hwdd\owner_shots\stock_dd_centre.png`, `stock_dd_corner.png` (zoom 3, rotation 0).

## Stock aftermath (measured in game)

Test tree `Simcity_stock_hwdd`, instance `inst_hwdd`, `lab2.sc3` (copy of `lab.sc3`), sc3resize only (no sc3netmod,
so highways are pure stock), pid 57820. Treasury set to $2,000,000 with `hw_lab.py funds 24675`. Drags with
`hw_lab.py hway ... --alt 82`, grids read with `hw_lab.py cells`.

A diagonal highway is a 3-cell band per row, the drag line through the middle cell:

| family | row cells (d0, d1, d2) | end caps |
|---|---|---|
| A, x - z constant | 11223.2 / 11224.0 / 11223.0 | 14999.0 (top end), 14999.2 (bottom end) |
| B, x + z constant | 15052.2 / 15106.0 / 15052.0 | (not read) |

Lanes (lanekit describe, world coordinates): right-hand traffic. A heading (x+, z+) keeps the x - z > c side, B heading
(x+, z-) keeps the x + z < c side. Lanes at 0.17 and 0.40 true cells from the centreline, band edge at 0.707.

The crossing depends on where the two centrelines meet (continuous coordinates, cell (x, z) = [x, x+1] x [z, z+1]):

| meeting point | drags | stock result |
|---|---|---|
| a cell corner | A x - z = 30, B x + z = 86, O = (58, 28) | 4x4 stub x 56..59, z 26..29: 2x2 15149 at x 57..58 / z 27..28, 73.2 / 73.0 on the z sides, 15051.2 / 15051.0 on the x sides, the stub's 4 corners stay plain band (11224.0, 15106.0) |
| a cell centre | A x - z = 118, B x + z = 149, O = (133.5, 15.5) | 3x3 stub x 132..134, z 14..16: one 15149 at (133, 15), 73.2 / 73.0, 15051.2 / 15051.0, corners plain band |

Both stubs never resolve (STOCK.md). Grids as read:

```
corner                                                  centre
  26  11223.2 11224.0 15051.2 15051.2 15106.0 15052.0     14  11223.2 11224.0 15051.2 15106.0 15052.0
  27        .    73.2 15149.0 15149.0    73.0       .     15        .    73.2 15149.0    73.0       .
  28        .    73.2 15149.0 15149.0    73.0       .     16  15052.2 15106.0 15051.0 11224.0 11223.0
  29  15052.2 15106.0 15051.0 15051.0 11224.0 11223.0          132..134 = stub
         55      56      57      58      59      60
```

Stock art (netart.stock_frames, zoom 4): A turned a quarter is B in 3 of 4 view frames, byte-identical (11223 frame
k = 15052 frame k-1 for k = 0, 2, 3; 11224 frames 0 / 2 = 15106 frames 1 / 3). Frame 1 of 11223 vs frame 0 of 15052
differs (7,512 px), 11224 frame 1 vs 15106 frame 0 differs (7,321 px). So a piece made on an A arm cannot be reused on
a B arm by a quarter turn.

## Design

Frame: P = ((z - z0) - (x - x0)) / sqrt2, Q = ((x - x0) + (z - z0)) / sqrt2 around O, true cell lengths. This is the
game's rotation-0 screen seen from above: A runs vertical, B horizontal.

- **Cloverleaf turned 45 degrees, with hwx's ramps.** Per quadrant one 270-degree loop (the left turn) and one outer
  ramp wrapped around it (the right turn). The ramp geometry is hwx's (`hwx.py ramps_q0`, orchestrator ask
  2026-10-18, refit the same day to the program's 0.62 ramp deck = hwpaint RAMP_W, stock 15127 fitted at 0.64): deck
  half width 0.31, loop radius 1.25, 0.19 ground between the loop and outer ramp decks (outer ramp radius 2.06 about
  the loop centre), outer ramp turns of radius 0.75, S tapers 0.5 (loop) / 0.62 (outer ramp). It is ported, not imported, and turned 45 degrees in
  the world ((u, w) -> (P, Q) = (-w, -u), a rotation because the plan frame is itself a mirror of (x, z)), so right
  turns stay right turns. Only the band offsets differ: the diagonal band edge is 0.707 from the median (hwx 1.0) and
  its outer lane 0.40 (hwx 0.57); the diagonal deck's edge is 0.63 from the median (hwpaint W_DIAG, hwcore measured
  on the stock bands; the band cells reach 0.707), so the ramp lines sit 0.25 outside 0.63 = 0.88 (hwx 1.25). The
  loop centres sit 2.13 from both centrelines, on the grid axes through O.
- Footprint: 11x11 cells (O on a centre) or 12x12 (O on a corner, the same box as hwx's), unchanged by the 0.62 refit.
- Movements (right-hand, screen compass): NE quadrant loop NB->WB, outer WB->NB; SE loop EB->NB, outer NB->EB; SW
  loop SB->EB, outer EB->SB; NW loop WB->SB, outer SB->WB. 4 through + 8 turning = every movement except U-turns.
- **A over B.** A crosses on a deck, B passes under: the X cells (band cells whose centre is closer than 1.6 cells,
  along the band, to the other centreline). The loops leave / join the carriageways 1.63..2.13 cells from O along
  the band (hwx: 2.0..2.5), so A's rise to H_HIGH and B's dip to H_LOW run over 0.8..1.6 from O, about the stock X
  arm slope (hwcore: no minimum slope length). Where a ramp joins, the carriageway's parapet and the ramp's facing
  parapet are open (hwpaint Deck gaps, spans computed from the geometry in hwdd_paint.joins).
- Ramps stay at the highway deck height everywhere: no ramp crosses a highway.
- Cells: centre parity writes 97 cells (9 crossing, 4 of them also holding a loop's deck, 32 highway + ramp, 56 ramp
  only), corner parity 108 (12 crossing, 8 of them with a loop's deck, 32 highway + ramp, 64 ramp). Every ramp lane passes cell to cell through
  edges (0 corner steps on all 8 ramps, `hwdd.py cells`).
- **Ids** (21360..21459): ramp-only cells one id in 4 states (the ramps are C4 symmetric); highway + ramp and crossing
  cells one id per half-turn pair (A over B, and the A / B art difference above). Centre 21360..21394 (35 ids),
  corner 21395..21432 (38), ramp-free flyover twins of the crossing cells that hold a loop's deck 21433..21438 (6);
  21439..21459 spare. [UNCERTAIN: assumes a variant's state turns its art and lanes like a stock piece's, frame =
  (state + view) & 3, as diagave_paint.Stock reads stock frames.]
- Free area: every written cell must hold nothing but trees (no building, zone or other network) and be flat at the
  bands' height. Cells inside the loops and between loop and outer ramp are not written.
- Superseded drafts (same day): loops of radius 1.9 with outer ramps straight along grid lines (13x13 / 14x14, 85
  ids); hwx's ramps at a 0.44 deck (11x11 / 12x12, 85 / 96 cells, 67 ids).

## Rule

After every highway retile and city load (net 4, on RBT's hooks via hwcore's `sc3netmod_hwy.c`):

1. Find an A band and a B band whose centrelines meet at O, with the stock stub between them (15149 plus 73 / 15051,
   either parity).
2. Each of the 4 arms runs as a clean band at least 2 rows past the outer ramps' joins (5.7 cells from O along the band).
3. Every cell the cloverleaf writes is free and flat (above). Then write the cloverleaf.
4. Fallback: arms long enough for the stub but the quadrants not free -> flyover only (the X cells: A over a deck, B
   under it, no ramps; X cells keep their id, the crossing cells holding a loop's deck take twins 21433..21438).
5. Refused, stock left as is: arms too short, slope, a third highway / road / avenue in the footprint, a T (one
   diagonal ends on the other), two crossings whose footprints overlap, diagonal x straight (stream hwdx's).
6. Revert: an edit that breaks the pattern takes the ramps out and restores what still qualifies (cloverleaf ->
   flyover -> stock). Saved ids are stock (rb_save_id), so a game without the mod loads the stock stub.

## Open

- Deck / underpass heights and slope length: hwcore's painter, kept alike with hwx's straight cloverleaf.
- One-lane ramp lanes on hwx's curves (radius 1.25 / 2.06 / 0.75) at 45 degrees: hwcore's ramp lanes.
