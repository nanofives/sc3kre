# diagfix: diagonal avenue / boulevard junction fixes (round 2026-11-14b)

Stream `diagfix` of `re/sessions/ROUND_2026-11-14b_junctions.md`. Inputs: the xsect sweep (`verify/xsect/`, 80 cases on
the flat sandbox, main bada3bc). Code: `sc3netmod_dav.c`, `sc3netmod_dbv.c` on branch child/diagfix. Every run here is
the whole sweep re-built on a fresh `xsect_sandbox_clear.sc3` in `dev/diagfix/tree` (`regress.py`, which drives
`verify/xsect/sweep.py` + `ramp.py` and writes into `verify/diagfix/<run>/`), then every slot re-read after the whole
run and diffed cell by cell (piece id + state) against `verify/xsect/final_cells.json`.

## Milestone 1: rail and highway cut by a diagonal band (68, 69, 72, 73, 80)

**Cause.** A diagonal avenue or boulevard drawn across a rail line or under a highway holds, on those rows, the game's
shared crossing pieces: 69 (road x rail, case 68 cells (141..143,123)) and 15098 (highway over road, case 72 cells
(32..34,140), (33..35,141)). `rb_read` (manager vt+0x14c ROAD predicate) reports them as road, so they are full band
cells, and the DAV write loop (`sc3netmod_dav.c`, `FUN_10008919` per cell) and the DBV write loop put 20505 / 20500 /
20950 / 20951 over them: the occupant became road-only and the rail or highway lost the cell. The stock diagonal road
(74, 75) keeps the crossing cells and runs into them.

**Fix DAVXNET** (`SC3NETMOD_DAVXNET=0` = off). `dav_xnet()`: a cell whose piece (or its variant base) is 69, 67, 11258,
15098, 16006, 16007, or Protected for ROAD (`FUN_1001a7f7(1, id)`, the test BV already uses) stays a band cell (masks,
the neighbours' pieces and the band's extent are as before) but neither DAV nor DBV writes it. Log lines
`dav: <who>: band axis A from (x,z): N rail / highway crossing cell(s) kept (DAVXNET)` and the `dbv:` twin; stats
`stats: dav/dbv rail / highway crossing cells kept=N`.

**Result (game, dev/diagfix tree).**

| case | before (xsect) | after |
|---|---|---|
| 68 DA x rail | rail row (141..143,123) = 20505.2 / 20500.0 / 20505.0, rail cut | 69.1 x 3, rail continuous, avenue meets the level crossing on both sides |
| 69 DB x rail | (159..162,123) = DB pieces, rail cut | 69.1 x 4 |
| 72 DA x highway | (32..34,140) / (33..35,141) DA pieces, highway cut | 15098.2 x 3 / 15098.0 x 3, avenue passes under |
| 73 DB x highway | same, 4 per row | 15098 x 4 per row |
| 80 DA beside on-ramp | no ramp (highway cut) | highway intact, still no ramp: **stock limit**. A plain diagonal road gets no on-ramp either (`ramp_dr.py`: r1 click one cell east of the road, r3 on it: nothing placed, same session where 78 / 79 placed theirs). The On-ramp tool needs a straight road end (78's road cell becomes 15046). |

Pictures: `m1/owner_shots/` (before | after per changed case, `sheet_before_after.png`).

Regression run `m1`: see "m1 regression" below.

### m1 regression (all 80 cases, fresh sandbox, commit b54c02e)

`m1/diff.txt`: final read-back (every slot re-read after the whole run) against `verify/xsect/final_cells.json`, and
each case's build-time read-back against xsect's. xsect's `final_cells.json` was read before cases 74..80 were built,
so for those the baseline is their build read-back.

- Changed: 68, 69, 72, 73 (the fix: 3 / 4 / 6 / 8 crossing cells kept), 80 (6 highway cells kept, no ramp = stock).
- 46: one build-time cell, (96,93) 21026.0, is a neighbour slot's DB cap read at another moment; the finals are equal.
- **64 (green before) is broken after the run, and this predates the round.** Building case 76 (road over rail at
  (105,135..147)) grows DAV's window to (17,111)-(129,171) for case 65's avenue, while DBV's window stayed
  (81,111)-(129,171). So DBV never claimed case 64's diagonal boulevard in that edit, and DAV took its first two
  staircases as a diagonal avenue: `dav: edit: band axis 0, 13 row(s) from (63,117), ... 28 written`. The xsect sweep
  log has the same line at the same build (`7619790 ms`). xsect's pictures and final read-back were taken before 76
  was built, so they never showed it. Fixed later in this round (milestone 4: DAV windows vs DBV claims).
- Every other case: same piece ids and states, final and build time.

Pictures: `m1/owner_shots/<case>_before_after.png`, `m1/owner_shots/sheet_before_after.png` (68 69 72 73 80 64).

## Milestones 2-4 (commits 16a9f81, 17ed8de, 44a7e03) + the art fix + family a) case 15

Regression `m3` (all 80 cases, fresh sandbox, every block below on, plus the DAVBEND135 bend set for axis 0 in my tree):
**no green case changed.** Changed cases and why (`m3/diff.txt`, `m3/verdicts.json`, sheet
`m3/owner_shots/sheet_before_after.png`, one before|after per case beside it):

| block | switch | cause (cells, log) | cases |
|---|---|---|---|
| DBVCAPCLEAN | `SC3NETMOD_DBVCAPCLEAN` | axis-1 frame = map turned one state: a 7-row drag is 4 canonical rows, both end rows took the 3 clean rows (`fewer than 3 clean rows (2 clean, end kinds top 103 bottom 103)`); a cap / ragged end row with nothing beside now counts | 50 52 54 55: DB arm converts; the T / corner itself still needs pieces (family d) |
| DAVDBVWIN | `SC3NETMOD_DAVDBVWIN` | DAV window grown to (17,111) past DBV's (81,111): DBV never claimed 64's DB, DAV wrote 28 DA cells over it when 76 was built | 64 stays green after 76 |
| DAVXAVL | `SC3NETMOD_DAVXAVL` | the DA x avenue template writes 11204 beside the box; DAV's post-AVL pass overwrote AVL's 21700 there every edit | 27 28 one-way end to end (were yellow) |
| DAVBVBEND | `SC3NETMOD_DAVBVBEND` | main pass refused 39's bend into a boulevard (avl_band_ok) and reverted 21 cells, post pass accepted (avl_dir) and rewrote them, every edit; BV flipped 41 | 39 stable (0 revert lines), 41 keeps its B arm |
| art fix | (data) | 21917 / 21918 / 21919 held 20950's art (dbvlanes split-id copy kept stale folders) | 16 17 18 clean; 31..33 / 42..44 lose the grass diamond, still need A/B x DB pieces or BV |
| DAVBEND135 | `SC3NETMOD_DAVBEND135` | owner chose "taper + bend": a road into a DA end at 135 deg; set 22430..22434 (axis 0), merge table end codes 2/3 | 15 in game: `bend1/raw/15_RxDA_L_z4.png` |

48 changed too (overlapping L: whichever band writes the shared corner cells last wins; identical DAV log lines in
both runs). Still red; family b)'s corner box replaces it.

Next (uncommitted in the worktree): DAVBENDSTUB (the stray one-cell stub inside the bend, owner yes 2026-11-15, piece
22435) and the axis-1 mirror set 22436..22441 (`mirror_set.py`: hflip of frame slot -k, same axis-space offsets,
state + 1, the merge table's own rule), then 19 / 34 / 41.

## Family a) DA part (commit 4cd3469) and DB part (commit a4d15cd)

| block | switch | case | pieces | in game |
|---|---|---|---|---|
| DAVBEND135 + DAVBENDSTUB | `SC3NETMOD_DAVBEND135` | 15 (road into a DA end), both ends + axis-1 mirror | 22430..22441 (diagonal_avenue) | `bend3/raw/15_*`, `bend2/raw/b15_*`, `bend4/raw/m15_*` |
| DBVBEND135 (kinds 18 / 19) | `SC3NETMOD_DBVBEND135` | 19 (road into a DB end), axis 0 + axis-1 mirror | 22442..22457 (diagonal_boulevard) | `b19b/raw/19_*`, `b7/raw/m19_*` |
| DBVBROW | `SC3NETMOD_DBVBROW` | 42 (orthfix BOXCELLS item 3): a boulevard row beside a DB is not a junction arm | none | `b9/cases/42_grid.txt` |

Traps found on the way: the game's piece writer ADDS the staircase partner cell when the bend's top piece is written
(it never exists during DAV's passes: DAVBENDSTUB re-reads after the write); mirrored frames must be flipped about the
tile centre (registration at offset 0: L' = w - W - L), and frame k of the mirror is the source's slot -k; an inner DB
piece with art source 11204 inherits 11204's tree layer (bend pieces use 35); bend detection must ask for a straight
road of 3+ cells with nothing beside it (a neighbour slot's diagonal touching 50's end matched a 2-cell test); DBVBROW
must follow the band's edge and count DBVTOUCH-masked cells.

Regressions m5 (DA bend) and m8 (DB bend + DBVBROW): no green case changed. Art: dev/diagfix/packs_src (KEEP).
Open: 34 (avenue into a DB end: offline mock not readable yet, `paint_34.py`), 41 (boulevard into a DA end: BV owns
those cells, spec to orthfix first), 48 (DA x DA corner box, mock approved), the 38/40/42/44 boxes (paint from
verify/orthfix/mockdiag.py; ids 22580.. to be scanned).

## Family a) rest + family b) (round 2026-11-15, uncommitted until the next regression)

| block | switch | case | pieces | state |
|---|---|---|---|---|
| DBVBEND135 kinds 20 / 21 (`bendav` / `bendavm`) | `SC3NETMOD_DBVBEND135` | 34 (avenue into a DB end), axis 0 + axis-1 mirror | 22458..22469, 22362..22369 | axis 0 in game OK (`b34b/raw/34_*`, rounded kerb kept by the owner); mirror: see below |
| DBVBEND135 BENDAVM path fix | (same) | m34l: the avenue's columns past row 3 were not path, the band was refused "touches road" and masked to a ragged end | none | to test |
| dbv refused-try log | (log only) | `dbv: band ... try N refused (why), masking the touching road` | none | in |
| DAV crossing templates (corner) | (data) | 48 (DA x DA corner box) | 22600..22609 (+ stub 22435 on the drags' overshoot) | in game OK after the overshoot fix (`b48b/raw/48_*`: the box closes with the outer kerb) |
| DAVBBEND (merge ends 8 / 9) | `SC3NETMOD_DAVBBEND` | 41 (boulevard into a DA end), both ends + axis-1 mirror; only when no BV piece holds the 9 cells (needs orthfix BVBEND=1) | 22370..22387 | to test (`mock/mock_41_v1.png`, `mock/mirror41.png`) |
| DBVBBEND (kind 22 `bendbv`) | `SC3NETMOD_DBVBBEND` | 45 (boulevard into a DB end), axis 0 (mirror needs 12 more ids) | 22388..22399 | to test (`mock/mock_45_v1.png`) |
| DAV crossing templates (boxes) | (data) | 38 (B crosses DA), 40 (B ends on DA), rotations + x-mirrors | 22610..22661 | built offline (`box_build.py`, `mock/box_38_40_v1.png`), not installed |

Traps: the 48 scene kept the drags' 1.06-cell overshoot in the ART too (the first avenue went on one row past the box,
cut square); footprint and art now differ (`CornerW.painting`). A 7-row axis-1 DB drag is only 4 full rows in DBV's
turned frame: bend + far cap leave 2 clean rows (needs 3), so m34 with the xsect drag length stays stock (a geometry
limit, not the bend). The DAV merge table was at its 64-line cap (now 128).

## diagfix 14 (round 2026-11-15b, owner bug in 52): the avenue arm cut off from the DA x DB corner box

Owner, from the bfill4 sheet and final1115 `sheet_final_3`: in 52 the diagonal avenue arm ends in a V, then grass, then
the box. Cause: `verify/diagfix/dbvx_build.py` fitted 52 as an L corner, but its drags run the first kind 3 rows on past
the other band (the avenue dragged to the boulevard's far edge), so the layout is a T with the boulevard as the stem.
The best-scoring L (ends 0 1) drew the avenue on the far side; its six arm cells beside the box were painted from a scene
with no avenue there, i.e. empty art, deduped into one piece (22735, written on 52's cells (30,101) (31,101) (30,102)
(31,102) (32,102) and (31,103)'s row). 55 (DB x DB L) had the same fault on 8 cells.

Fix: L cases also try the T scenes (after the L ones, so a tie keeps the L); 52 and 55 now fit `T stem 1 edge 1` with
no undrawn drag cell; 55 joins 52 in `ASYM` (a T is not x <-> z symmetric, its mirror gets its own templates); the
build stops if any written box cell paints nothing. Pack: 76 pieces 22721..22796 (the old 22735 is gone, later ids one
lower), 22 templates (was 18), template check 0 wrong.

Other empty-art pieces, all by design: 22435 / 22441 (the transparent stub box_build / corner_build write on drag
overshoot past a box: 15 29 40 48), 22607..22609 (past 48's corner), 22720 (past 44's band edge). 49 50 53 54 write none.

Regression m17 (fresh game, every pack incl. orthfix 11-15b; diagxnet's underpass 0.1.1 is wall art only): against m16
only 52 / 55 change (the arm cells now the avenue / boulevard) and 53 / 54 (ids one lower, same states). Orders
(m17b, fresh game): 39 41 45 identical; reversed 49 53 identical, 54 55 the known slot-edge cell, 50 / 52 differ only
at the boulevard's far end cap (the next slot's road; m13b / m14b / m16 effect, not the box). Before | after, 4 views:
`verify/diagfix/owner_shots/c52_before_after.jpg`, `c55_before_after.jpg` (local).

## diagfix 15 (round 2026-11-15b, owner review of c19_option: "almost perfect, minor glitch at the end of the avenue and the beginning of the 1 tile road")

19's look is now the owner's: the original cap-square end of the diagonal boulevard, opened only over the road's row
(`verify/diagfix/paint_19c.py` CapRoad), in place of the taper + bend. The glitch at the road (offline mock and in game):
the opened outer curb still rounded the corner with the end edge (a grass notch at the road's north kerb), the end edge's
kerb kept the diagonal strip's x sqrt 2 profile (its gutter line one step off the road's), and the road's south sidewalk
ended short of the cap's outer curb (an asphalt gap, then a gutter-line stub). Fixed in CapRoad: no rounding on the
opened side, the end kerb eases into road 29's profile over the last 1.5 cells, the cap's outer curb runs up to the
road's sidewalk and road 29's own pixels fill that inside corner.

Pieces: the DBV `bend135` stamp (kind 18, `verify/diagfix/add_bend19c.py`, the whole old 8-cell footprint so the mirror
covers the turned frame's partial rows) and its mirror `bend135m` (kind 19, add_bend19m.py), same ids 22442..22457, same
cells and states: only the art changes (pack art, gitignored), the manifest and tables are byte-for-byte as before.
Same detection, switch SC3NETMOD_DBVBEND135 (=0: the square end as before the bend). Regression m18 (fresh game, every
pack): 0 cells differ from m17 in all 80 cases (art only). In game before (staged 11-15) | after, 4 views, 19 and its
axis-1 mirror m19: `verify/diagfix/owner_shots/c19_before_after.jpg`, `cm19_before_after.jpg` (local).
