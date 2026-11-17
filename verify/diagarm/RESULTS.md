# diagarm: diagonal junctions broken in the showcase city (2026-11-17)

Workspace dev/diagarm (main d7d1ddb + every pack of the 2026-11-17 release). Code: `re/harness/src/sc3netmod_dbv.c`
only, block **DBVSHORT** (off: `SC3NETMOD_DBVSHORT=0`). No pack, art or table change.

## 1. Why the 17 junctions broke in the showcase city

Two causes. Every one of the 17 has the first. 8 of them also have the second.

**a) Road cells lost during play (all 17).** Offline network read of the showcase saves (`network_layer.read_networks`):
the built save `showcase.sc3` holds 7,232 road cells; then 7,220 (`showcase_g1`), 7,083 / 7,069 / 7,060 (the
`showcase_zoned` autosaves), 7,056 (`showcase_zoned`), 7,048 (`showcase_shoot`), with no edits between them. Every
one of the 17 lost 1 to 4 of its own cells (C3 (78,42), C9 (107,115), D8 cross (136,85) (140,91), ...), and so did
almost every other block, orthogonal ones too, plus the cloverleaf loops of ISSUES 5. A band with a missing cell is no
longer a band, so DAV / DBV leave it to the stock tiler (load log of the damaged city: `dav: load: band axis 0 from
(79,43) with 3 junction cell(s), 0 crossing(s) left to the stock tiler: no split into two lone staircases`).
Proof that this alone explains 12 30 41 42 44 68: the undamaged built save loaded in dev/diagarm reads them fully
converted with the 4-row arms (`rb_built/`), and the same blocks rebuilt at their own coordinates with the street
grid on the clean sandbox convert too (`b1/`, `b2/`).
Cause (found by the roadloss child, 2026-11-17): the showcase's offline zoning tool (`verify/showcase/zone.py` via
`city_write.zone_set`) mirrored the zones in x and zoned road cells, and the stock zone developer bulldozed those
cells in play. Not a game or mod bug, and not fire (my first guess). So in the showcase city only the arm-length
class below is real.
Offline reader used for the counts: `verify/diagarm/savecells.py` (road cells per save, `--diff` gone/new between
saves, `--at X,Z` base piece id per save), on `re/tools/network_layer.read_networks`.

## 2. Shortest arm per family, released build (clean sandbox, `s43/`, against the 6-row stage `final1117/s1`)

| family | 4 rows | 3 rows |
|---|---|---|
| R / A / B x DA (12-15, 27-30, 38-41) | converts (27 28 29 38 40: one end cap is the stock 18004, not 21803) | 15 28 30 32 39 41 mixed |
| DA x DA (46-48) | 1-2 cells stock | converts |
| R / A x DB (16-19, 31-34) | 19 34 whole band stock (the stock look), rest converts | 17 19 34 stock |
| B x DB (42-45) | 43 stock, 45 mixed | 42 43 44 stock, 45 mixed |
| DA / DB x DB (49-55) | all mixed (6..19 stock cells; 6-row baseline 4..6) | all mixed |
| ends, merges, rail, highway (59 60 64 65 68 69 72 73) | converts | converts |

"Mixed" = mod pieces on one band, the stock 43 / 39 ladder on the other, meeting with no box: broken pieces
(`s43/sheet_a.jpg`, `sheet_b.jpg`).

## 3. Fix: DBVSHORT (`sc3netmod_dbv.c`)

1. `dbv_band`: one clean row is enough when the band's shape is known anyway: a crossing template matched, or neither
   end is ragged.
2. Discovery hands chains with fewer than 3 clean rows to the rule too (`dbv_chain_tried`), if they have at least
   one clean row on the unmasked map. That condition keeps a solid block of roads out: in xsect 63, four straight
   roads side by side, an earlier version had carved boulevard pieces out of the block after DBVTOUCH masked it.
   Chains of 2-3 rows (the axis-1 stems) are accepted only through a template, and are refused without a log line.
3. When no template matches strictly, a relaxed pass skips the window cells more than 1 cell from the template's
   writes (the arms' run-on and what lies past a short arm, e.g. the street grid 2 rows on) and counts their
   mismatches. Of the matching templates, only the ones with the fewest mismatches are kept (a T's box fits a short
   L too: 52, T 3 misses 4, corner 5 misses 2). Strict matches are unchanged. The matched windows' rows are now marked
   after the choice. Log: `crossing template N matched with its window cut to the box (short arm, K run-on cell(s)
   missing, DBVSHORT)`; stats line `short-arm template matches=`. Offline twin: `xsim2.py`.

## 4. Results

Clean sandbox (`f8/`, `f7/`):

| case | release | diagarm |
|---|---|---|
| 19 34 43 45 at 4 rows | stock / mixed | converted, both draw orders cell-identical |
| 17 19 42 44 45 at 3 rows | stock / mixed | converted (42 44 checked in both orders) |
| 34 at 3 rows | stock | converted (`f1/`) |
| 50 52 54 55 at 4 rows | 19 stock cells | 6 = the 6-row baseline (the stem's far end, as at 6 rows), both orders identical |
| 49 51 53 at 3 rows | 22 / 5 / 20 | 5 / 5 / 4 = baseline |

Showcase city (the undamaged built save, `rb_before/` fix off, `rb_after3/` fix on):

| case | before | after |
|---|---|---|
| 12 30 41 42 44 68 | converted | converted (unchanged; in the played city they broke from lost cells only) |
| 45 B into DB end | 18 stock | 0 stock (paved bend box). See the note on old saves below |
| 50 / 52 / 54 / 55 | 19 / 19 / 19 / 19 stock | 6 / 6 / 6 / 6 (boxes drawn) |
| 49 / 51 / 53 | 13 / 12 / 12 | 13 / 12 / 12: still mixed (open) |
| 38 40 47 | 1-2 stock cells | unchanged |

Note on old saves: a save made under the old rule keeps BV's boulevard pieces in 45's bend cells. On the first load
DBV sees them and does not take the bend, and BV's load revert then retiles the junction to the stock look (clean).
Saved and loaded again, it converts (checked: `rb_after/` first load, `rb_after2/` second load).

Pictures (phone-sized, zoom 4, one view each, rotations kept to none): `owner_shots/city_<xsect>_<case>.jpg` (45 50
52 54 55 fixed; 49 51 53 open) and `owner_shots/sandbox_xsect<case>_<arm>.jpg` (19 34 43 45 at 4 rows, 17 42 44 at 3).

## 5. Regression

- Full 80-case sweep, fresh sandbox, sweep order, final read-back against the released stage `final1117/s1` (`m3/`,
  `cmp_stage.txt`): **77 identical**. 31 / 32 / 33 differ by 27 / 26 / 15 cells, exactly shortarm's merged change
  (my base includes avenue_dbv_t 0.2.0; shortarm reported the same numbers against the same baseline).
- Short-arm layouts in reverse draw order (`f6/`, `f7/`): 19 34 43 45 50 52 54 55 at 4 rows: 0 cells differ from
  the forward build. 42 44 at 3 rows: converted in reverse. 49 50 at 6 rows reversed: as the release.
- Shipped city: Berlin (16 diagonal bands) loaded with the fix on and off, every road cell read: 19,220 cells, 0
  differ (`berlin/`).
- The earlier m1 run (before the clean-row condition in point 2) changed 63. m3 has it identical again.

## 6. Open

- 49 (DA x DB cross) at 4 rows, 51 (T2) and 53 (cross) in the showcase's layout: one core cell off every template.
  In 49 the diagonal avenue's 4-row arm ends exactly at the box (no arm past it). These need new template variants
  (dbvx_build). They look as they did before (mixed).
- T / corner DB stems of 3 rows (50 52 54 55): 1 full row in the turned frame, so no chain to try. Trying 1-row
  chains would send every straight z-road to the template matcher. Mixed, as before.
- DA family at 3 rows (15 28 30 32 39 41: DAV's own 3-clean-row anchor, `DAV_MIN_ROWS`) and the 18004 end cap at 4
  rows: not touched.
- Cause a) is the zoning tool's (roadloss child), not this branch's.

## Files

- Code: `re/harness/src/sc3netmod_dbv.c` (branch child/diagarm).
- Tools (MAIN/verify/diagarm, untracked like the other verify tools): `savecells.py` (offline save reader), `readback.py`, `armlab.py`, `shots.py`,
  `cityshots.py`, `sheet.py`, `pairs.py`, `mapread.py`, `xsim.py`, `xsim2.py`, `run.py` / `cmp_stage.py` (copies of
  shortarm's), `holes.py` (the game's remove call does not remove mod pieces: dropped).
