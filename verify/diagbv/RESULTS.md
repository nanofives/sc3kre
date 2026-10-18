# diagbv: the diagonal 3-wide boulevard (2026-10-17 / 18)

Owner request (via the orchestrator, wave 2): "make it diagonal too": three diagonal road drags joined side by side
become one boulevard, the straight boulevard's cross-section turned 45 degrees, with its ends, its bends into the
straight boulevard and single straight roads crossing it. Light test per owner rule: one lab game, pictures, a save
and reload.

Setup: test tree `Simcity_stock_diagbv` (hard links of the stock tree), instance `re/harness/inst_diagbv`
(sc3netmod.dll from this worktree, 245,248 bytes, + sc3resize), packages `diagonal_avenue` 0.5.0, `boulevard` 0.2.0,
`avenue_markings` and `diagonal_boulevard` 0.1.0 installed as overlay. Lab city: copies of `lab.sc3` (flat patches at
alt 82). Screenshots in the instance's `shots/` and `MAIN\verify\diagbv\owner_shots\` (not committed).

## Design

- **Band:** rows of four cells d0..d3; strips A (p 0..1), B (1..2), C (2..3) with p = x - z. Stock tiles it as a
  ladder 11203 / 43 / 43 / 11203 (offline tiler).
- **Cross-section:** `boulevard_paint.Boulevard.section` evaluated as is with T = 256 p and a sampler that reads stock
  35 instead of 29 (`diagbv_paint.diagonal()` swaps the sampler and its centre-line cache). Measured: 35's profile
  across its strip in p_rel * 256 is 29's lane profile within a few units (sidewalk, curb, lanes, centre line). The
  section is not copied, so a change of the straight boulevard's look carries over.
- **Symmetry:** only the section's north half is used; the south half is it turned half a circle about (1.5, 0), which
  is exactly how stock places staircase C against A. So d3 = d0 turned, d2 = d1 turned, a top end = the bottom end
  turned. Sampler frame offset: staircase k at (p_rel, q) is staircase 0 at (p_rel, q - k), so a sliding carriageway
  meets the diagonal avenue's B staircase pixel-exactly.
- **Ends, fitted to the cells the drags leave** (`diagbv.py fit`: every road cell holds road, no road drawn in a cell
  the drags leave empty, the art equals the neighbour's own pieces where the claim stops):

| end | continuation past the last full row | claims | shape |
|---|---|---|---|
| narrow-C / narrow-A | the diagonal avenue on strips 0..2 / 1..3 | 2 / 0 rows | the ending carriageway slides one strip in, linear over 3 cells along (`AvenueNarrow.params`) |
| taper-1 (+ stub) | the middle road | 2 | both outer curbs linear, staggered by the oblique cut; centre line straight |
| taper-2 / taper-0 on the long side | an outer road | 1-2 | far curb 2 strips, slope 1/2 (1/3 with the drags' last cells); yellow line jogs to the nose |
| taper-0 on the short side | an outer road | 2 | the C carriageway can only close inside its last cell: a rounded end, then a 45 degree taper |
| cap-square / cap-part / cap-x4z3 / cap-x4z4 | nothing / the drags' last cells | 0-3 | straight curb along the cell edges the drags leave, corners rounded (r 0.35 cell) |
| stem | a row road across the band's end | 0 | junction keeping the road's far curb |
| bend-x / bend-z | three straight roads | 0 | band pieces up to the joint line, the straight boulevard's pieces after it |

  Why the short-side taper is abrupt: past the last full row the strip p 2..3 only has cells in teeth (the d2 cells'
  corners); with only staircase A going on, C must be gone at the d3 cells' bottom edge.
- **Junctions:** straight single road along x on a band row (crossing, T from either side) or along z through four rows;
  median noses parallel to the road; crosswalks = stock 43's two white lines across the band along the road edges and
  across the road at the band's outer edges.
- **Pieces:** 114 (20950..21063): every stamp cell is compared with the band's art at that place, with the pieces so far
  and with them turned (sample of zoom 3 / 4, views 0 / 1, trees, base); equal = shared. Bases: outer cells 35, the
  rest 43 (save = base). Art tables: outer band cell 35 (stock frame size), full cells with trees 11204, full without
  43, partial 35 (ground drawn under: no cyan). Lanes: copy_base, the inner band cell its own spec (35 state 2's half).

## Rule (`diagbv.py bands()`, `sc3netmod_dbv.c dbv_band()`)

Canonical frame = axis 0 as is, axis 1 the map turned back one state. Chain: rows (z, a) with ROAD at a..a+3, each the
next row's left - 1, anchored by 3 clean rows besides junction and end rows. Ends classified from the rows past the
first / last row (the top end turned). Stamps per kind in the manifest (`auto_diagonal_boulevards`: `dbvb`, `dbvs`
lines), turned for the other side. Isolated: every road 8-touching the band or its stamps is an arm, the road an end
goes on into, or the straight roads past a bend.

**Order and claims:** DBV runs first in RBT's two hooks and publishes the cells of each band it accepts.
- `sc3netmod_dav.c` / `diagave.py` (task diagbv lines): a row whose three cells are all claimed is not an avenue row;
  an end that runs into claimed cells is a bend of kind 3 (virtual rows past it); claimed cells are not "road beside",
  not "touches road", not written, not reverted. On axis 1 DBV's claim boundary runs along a real column, so DAV keeps
  partly claimed rows in its chain and writes only their unclaimed cells.
- `sc3netmod_bv.c` / `boulevard.py`: a column with claimed cells is not a boulevard column; an end whose cells beyond
  are all claimed is a bend (no end region, no nose); claimed cells are not "touches road".

Shapes refused (logged "left to the stock tiler"): ends of other shapes, two diagonals two cells apart (ends with a
gap), a column road ending the band, avenue / boulevard crossings.

## Offline

| check | result |
|---|---|
| `diagbv.py fit` | 12 end scenes fit (coverage, no spill, neighbour art past the claim) |
| `diagbv.py check` (70 footprints: both axes, both step phases, both gestures, every end, junction and bend, DAV and BV shapes) | 0 off; no cell in two blocks; DAV converts the avenue past every narrowing (both axes), BV the straight boulevard past every bend; DAV and BV shapes never taken by DBV |
| `diagave.py combos` | unchanged (24 / 48 drag and 4 / 32 junction footprints without a band, as before) |
| 4-cell band vs DAV's 3-cell rule | DAV never anchors on 4-wide rows (none is clean); DBV never on DAV bands (no 4-wide clean rows) |

## Game (pid 70260, then 5172 after reload)

| step | result (sc3netmod.log) |
|---|---|
| load | `dbv: ... band pieces outer 20950, inner 20951`, `dbv: diagonal boulevards on`, 0 exceptions |
| drags (102,92)-(110,100), (103,92)-(111,100), (104,92)-(112,100) | after the second DAV made an avenue, after the third `dbv: edit: diagonal boulevard axis 0, 8 row(s) ... 35 cell(s), 35 written`: square cap (turned) on top, cap-part at the bottom (`g1_z3`, `g1_z4`) |
| row road (100..115, 96) across it | `39 cell(s), 37 written`: 20953..20956 on the road row, noses 20952 / 20957, arms 29 (`g2_z3`, `g2_z4`) |
| other diagonal: drags (24,45)-(12,57), (24,44)-(12,56), (24,43)-(17,50) | the second drag stopped short in game, so a taper: `axis 1, 7 row(s) ... 33 cell(s), 33 written`, cap-part (turned) and taper-2 (`g3_z3`, `g3_taper_z4`) |
| save | `save: 68 variant tile(s) written as base` (72 cells minus 4 arms of stock 29) |
| twin on the save (`diagbv.py plan lab2_saved.sc3`) vs the live grid | 72 / 72 equal |
| reload | `load: all 68 variant tiles restored`; both DBV load passes `0 written` |
| demolish (112,99), (112,100), three straight roads x 109..111, z 99..105 | DBV keeps the band to row 98 (bend-z), then `bv: edit: boulevard axis 1, columns 99..105, 21 cell(s)`: no end region at the joint, cap at 105 (`g4_bend_z3`, `g4_bend_z4`); `g5_view1_z3` view 1 |
| save | `save: 82 variant tile(s) written as base` |

0 exceptions in both logs (`sc3netmod_run1.log`, `_run2.log`). Owner sheet: `MAIN\verify\diagbv\owner_shots\diagbv_sheet.png`;
mockup: `diagbv_mockup.png`. The blue square in panels 1, 4, 6 is the road tool's cursor highlight.

TrBlkAtt: 276 records per language for this package (copy_base copies each base record per state); with the other
three packages installed the index holds 1,261 slots (grows by itself).

## Not seen in game this round

Narrowing into the diagonal avenue (twin only, both axes), the junctions along z, T junctions, stems, the staggered
caps, the bend along x, bulldozing a junction cell. The rule writes about 20-35 cells after each nearby edit (the
stock retile re-places them first), as DAV and BV do.
