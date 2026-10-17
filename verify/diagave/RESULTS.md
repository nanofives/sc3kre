# diagave phase 0: stock diagonals, side-by-side diagonals, straight road across a diagonal (2026-10-17)

Owner question: can the netmod pipeline give **diagonal avenues**, with art for diagonal intersections and ordinary
roads crossing them? Phase 0 = learn what stock does before designing pieces. Light test per owner rule: one game run,
pictures, no pre-registration.

Setup: game run in the hard-linked stock tree `Simcity_stock_roundabout3` (SIMNTWRK / SIMSPR / SIMUI SHA-256 equal
to `original/modules/`), instance `re/harness/inst_diag` with **sc3resize only** (windowed + frame dump, no network
mod), `mods_launch.exe -multi`, pid 24080, lab city = `inst_rb3/roadless.sc3` copy. Drags with `rb_lab.py road
... --alt 82` (zoom 3, rotation 0), grids read live with `rb_lab.py cells`. Log: only the startup VEH entry at
3.9 ms that every sc3resize log carries. Offline: `re/tools/netmod/diag_probe.py` (this branch) on the 16 shipped
cities and on the lab save. Owner pictures: `MAIN\verify\diagave\owner_shots\diagave_phase0.png` (untracked).

## 1. Stock diagonal pieces in the shipped cities (`diag_probe.py scan`)

| Piece | Cells (16 cities) | What the neighbourhood grids show (`diag_probe.py sites`) |
|---|---|---|
| 35 | 8,322 | diagonal straight, a 4-connected staircase, two cells per row (states 0/2 on one axis, 1/3 on the other) |
| 18004, 1999 | 6, - | ends of a diagonal drag (18004 at the start cell, 1999 at the end cell, both seen live) |
| 14010-14013, 14014-14017 | 168 each, 172 each | always a 2x2 group: a straight road bending 45 deg into a diagonal (two hands) |
| 14000-14009 | 0 | never placed in a shipped city |
| 11207-11210 | 4 / 7 / 1 / 6 | a diagonal branching off a diagonal (Y) |
| 11211-11214, 14030/14031 | 151 / 71 / 166 / 123, 139 / 49 | a straight road merging into a diagonal |
| 11204 | 26,752 | the stock **avenue**: 2 cells wide (states 1 / 3 side by side), tree median, one two-way carriageway per cell |

Road pieces orthogonally next to a 35 that are outside the diagonal family: 39 x470, 29 x179, 11203 x137, 43 x45,
11204 x11 (rest under 7). So where a diagonal meets a straight road, stock uses ordinary T / 4-way / curve cells.
There is **no diagonal avenue** and **no X crossing piece for a straight road across a diagonal**.

## 2. Two diagonals drawn touching (the natural "avenue" gesture)

Drag A (102,92)-(110,100), then drag B (104,92)-(112,100), i.e. B two cells along x. Live grid after B:

```
  92  11225.3    39.3 11204.2 11203.0                                          (x 102..105)
  93          11203.2    39.3    43.0 11203.0
  94                  11203.2    43.0    43.0 11203.0
 ...  (same pattern each row)
  99                                  11203.2    43.0    39.1 11203.0         (x 109..112)
 100                                          11225.2       . 11225.2         (x 110, 112)
```

Picture: a ladder of 4-way crossings with curved edges (owner sheet panel 2). Not an avenue. With one empty cell
between the staircases (B shifted 3) the two roads stay clean 35 staircases (offline, panel 3).

**Simulator agreement:** `tiler.py` seeded with the drags' exact footprint (18004 start, 1999 end) and retiled with
`retile_rect` gives the same 34 band cells as the live grid, cell for cell. TILER_SIM.md's "diag" class is the drag
code that places the 35 / 18004 / 1999 seeds, not the rules: once the seed footprint is given, the rules are modelled.

## 3. Straight road across a single diagonal

Drag C (100,101)-(105,106), then a straight road (99,103)-(108,103). Live grid:

```
 101          11225.3 11203.0                                                 (x 100..101)
 102                     39.2 11203.0
 103  11225.3    29.0    39.1    39.1 14031.1 11214.1  29.0  29.0  29.0 11225.1   (x 99..108)
 104                                     35.2 14030.1
 105                                             35.2 11203.0
 106                                                  11225.2
```

The diagonal above the road is rebuilt from curves and a T, the crossing cells are T / merge pieces, below it two 35
cells survive (panel 4). The simulator gives the same 19 cells.

## 4. What this means for phase 1 (design reasoning, not measured)

- A touching pair of staircases is a band 4 cells wide per row (x = z+c .. z+c+3). Its fully covered strip is
  3/sqrt(2) = 2.1 cells wide across the diagonal, about the stock avenue's 2.0. The gesture already reserves the room.
- Every band row repeats (translation by (1,1)), and a 180 deg turn maps the outer cell of one side onto the other
  (stock already places 11203.2 / 11203.0 there) and likewise the two inner cells. So the straight diagonal avenue
  needs **2 new ids** (outer, inner), states covering both diagonal axes. Ends, the straight-to-diagonal joins, crossings
  with roads and avenue x avenue come on top.
- Neighbour sets in the band (E = x+1, S = z+1, as in the grids above): outer left = E, N, NW, NE, SE; inner left = all but SW; inner right =
  all but NE; outer right = W, S, NW, SE, SW. The inner sets also occur in other dense road blocks, so rules must also
  check neighbour ids (5x5 Complex stage) or use an RBT-style hook in the retile pass.
- The simulator predicts these retiles, so rule work for the band can be iterated offline (`diag_probe.py band`,
  `netrules preview`), with one in-game check per round.
- Lanes: the band is 4-connected, so road routing can step between the two carriageways through the inner cells
  unless the turn matrix forbids it (LANE_DENSITY.md section 2). Stock 11204 keeps its halves unlinked.

Not done: art, rules, lanes; rotations other than view 0 in game; zooms other than 3.
