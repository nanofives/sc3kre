# hwdx: diagonal highway x straight highway (skewed cloverleaf)

Stream `hwdx` of the highway program (protocol `re/sessions/CHILD_PROTOCOL_2026-10-18_highways.md`, ids
21260..21359 + 21460..21559). Status: milestone 1 (plan) done, the design is picked (cloverleaf), the rule, cell
tables and offline twin are done. The mockup and build wait on hwcore's `hwpaint.py` / `sc3netmod_hwy.c`.

Tools (run from `re/tools`):
- `netmod/hwdx_plan.py` holds the geometry and draws the plan pictures (`cells`, `png OUT --plan clover|direct`).
- `netmod/hwdx.py` turns that geometry into what the block needs: `table --case A|B`, `ids`, `check`.

## 1. What stock leaves (measured in game 2026-10-18, reproduced by the offline tiler)

All four drags give one shape, turned or mirrored. Case frame: O is the cell corner where the medians cross.
Straight S is in rows j = -1 (runs +x) and j = 0 (runs -x). Diagonal D is the band i - j in {-1, 0, 1} (case A, x-z
family, 11223 / 11224) or i + j in {-2, -1, 0} (case B, x+z family, 15052 / 15106, the mirror image).

| cell (case A) | stock piece | cell | stock piece |
|---|---|---|---|
| (-3,-1) (-2,-1) | 15149 Highway Construction | (1,0) (2,0) | 15149 |
| (-1,-1) | 11224 (band middle) | (0,0) | 11224 |
| (0,-1) | 15051 (band outer cell left straight) | (-1,0) | 15051 |
| (-3,-2) | 73 (band cell beside S turned straight) | (2,1) | 73 |

The offline tiler (`tiler.retile(4, ...)`, cells seeded with 15051, Roadless Paradise) gives this cell for cell. It
does so in both drag orders and in all four orientations. Case A at r = 1 (straight along z, x+z diagonal) and case
B at r = 1 (straight along z, x-z diagonal) are the in-game drags C and A turned.

## 2. Design (owner's pick pending, orchestrator default 2026-10-18: clover)

- **Bridge:** S goes over: 1024 -> 1536 in the arm cells, 1792 over the band, like the stock X's z arms
  15150 / 15153. D goes under: 1024 -> 512 -> 256, like the stock X's 15107 / 15108. Core = 16 cells.
- **Ramps:** 8 one-lane ramps on decks at 1024, using hwx's numbers:
  - deck half-width 0.22;
  - ramp lines 0.25 outside a carriageway edge;
  - loop radius 1.25;
  - 0.19 of ground between neighbouring decks;
  - S-tapers of 0.6 into the outer lane, never on the cells where a deck changes height.
- **Acute quadrants:** a 225-degree loop sits at the corner (the 135-degree left turn), and the 135-degree right
  turn runs round it.
- **Obtuse quadrants:** a 315-degree loop (the 45-degree left turn), with the 45-degree right turn round it.
- **Size:** footprint 20 x 14 cells, 130 cells.
- **Pieces:** 112 classes (core 16, ramp-on-highway 30, ramp alone 66). Every class that touches highway comes in
  two flavours, because the stock uses different ids per axis and per diagonal family. That makes 158 ids of 200.
- **Rejected alternative:** direct flyovers for the 45-degree left turns (`hwdx_plan_direct.png`). That version is
  26 x 22 cells with 4 one-lane bridges, because both highways' halves touch and a left exit cannot climb over the
  other half.

## 3. Rule (`hwdx.detect` / `hwdx.place`, the block does the same on a net-4 pass)

- **Trigger:** the stock aftermath above, found from any 15149 cell under the 8 turns and mirrors. The design is
  point-symmetric about O, so r and r + 2 give the same placement.
- **Core:** all 16 cells must hold highway (straight, band or 15149). If not, leave the crossing as stock.
- **Per quadrant:**
  - its joining cells must hold plain highway;
  - its ramp-only cells must be free (no network; in game also no building or zone, trees cleared: hwcore's claim
    rule) and flat and dry.
  - A quadrant that fails drops its two ramps; the others still build. Each quadrant joins only its own two
    carriageways.
- **Refused:** slope or water in the core, diagonal x diagonal (hwdd), any T involving a diagonal, highway x avenue,
  two crossings closer than their footprints.
- **Open:** the arm check covers only the joining cells, not every mainline cell between the core and them.

## 4. Turn matrices: the core must not merge S and D

The router and the tiler see a piece only as entry side -> exit side. The stock diagonal staircase takes one x step
per row. Inside the S rows, an x step in the same direction as that row's traffic shares an entry side with S. The
matrix then merges the two carriageways.

Measured offline with every ramp removed, the stock-side core still connected 4 of the 8 turns (all four 45-degree
ones). The router would have used these core shortcuts instead of the obtuse quadrants' ramps.

The fix (`CORE_D_A`) changes only the turn sides inside the core. D takes its x steps only where they run against
S's traffic:
- D+ goes straight up through row -1 and steps twice in row 0;
- D- goes straight down through row 0 and steps twice in row -1.

The drawn diagonal and its lanes keep the true geometry. With the fix, the core alone connects exactly the 4 through
movements.

Stream hwdd (diagonal x diagonal) will meet the same problem.

## 5. Offline check (`py -3.12 -m netmod.hwdx check`, 2026-10-18)

- Four drags (cases A and B, straight along x and along z) x two drag orders. Each run: stock tiler -> detect finds
  exactly that crossing -> all four quadrants placed (130 cells) -> **12/12 movements** reachable over the turn
  sides.
- Core only (no ramps): exactly the 4 throughs, in both cases.
- 0 of 260 cells disagree with their piece's turn sides at the cell's state.
- A claimed cell inside A1 refuses A1 only; A2, O1 and O2 still build.

Not proven yet: anything in game (no variant built), lanes (TrBlkAtt), art, saves. Which way the engine turns a
state (`STATE_DIR`) gets checked at build time, as hwx does.
