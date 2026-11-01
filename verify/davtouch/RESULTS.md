# davtouch: a road touching a diagonal avenue keeps the avenue (2026-10-31)

Owner call 2026-10-31: "A road touching a diagonal avenue should keep the avenue." Branch child/davtouch (from main
7ee5ed9), tree `dev\davtouch\tree`, city Roadless Paradise. Every case below was built with the real Road tool (posted
drags through `re/tools/roadover_drive.py`, no cursor), not the lab build call.

## Verdict

Cause: `dav_pass` (sc3netmod_dav.c) sets `ok = 0` for any road touching the band in a shape it has no junction for,
and the revert loop then stock-retiles every avenue piece of the band. The game's mask-3 retile re-tiles the whole run,
so all 26 cells of an 8-row avenue went back to the 43 / 11203 ladder. `dbv_band` (sc3netmod_dbv.c) refuses a
diagonal boulevard the same way.

Fix: DAVTOUCH (`SC3NETMOD_DAVTOUCH=0` = off) and DBVTOUCH (`SC3NETMOD_DBVTOUCH=0` = off), each in its own block:
1. A one-cell stub beside a band row is a junction arm (the same median opening / row junction a 2-cell side road
   gets). The stub cell gets the stock dead end 11225, open side toward the band.
2. Any other touching road: the band is judged again with the touching road's cells masked out of the read buffer
   (read as no road), up to 8 times, each time masking the cells the refusal names. The band converts. The touching
   road's cells keep the pieces the stock tiler gave them, so the road stops at the curb. The mask lives only while that
   band is judged and written.
3. DAV only: the drag-end extension past a band's last row now takes only cells the drags' staircases reach (below the
   band cell of the row before, or after one along the row). A road touching the end cell at a corner used to be read
   as part of the drags' end and broke the staircase split.

## Before (main 7ee5ed9 build, PID 16560)

Avenue: two joined drags (60,60)-(68,68) and (61,60)-(69,68), 26 cells. Boulevard: three joined drags from (40,75),
8 rows, 35 cells.

| case (road tool) | DAV result | DBV result |
|---|---|---|
| straight row road at a mid row, (57,63)-(62,63) | junction (median opening) | junction |
| column road from N into a mid row, (66,56)-(66,63) | junction (median opening) | not run |
| row road crossing the band, (55,64)-(75,64) | junction | not run |
| 1-cell stub beside a mid row, (62,63) / boulevard (43,79) | **whole band stock** (26 cells) | **whole band stock**: "road below the band is not a straight single road" |
| column road from S, 2 rows from the end, (62,63)-(62,70) | **whole band stock**: "a column road meets one carriageway near the avenue's end" | not run |
| column going on from the end cell, (69,69)-(69,75) | **whole band stock** | band kept, end row stock (avrbtfix RAGGED) |
| row road touching the end cell at a corner, (70,69)-(75,69) | **whole band stock** | band kept, end row stock (RAGGED) |
| perpendicular diagonal touching the side, (72,57)-(66,63) | **whole band stock** | not run |
| row road beside the end row, (55,60)-(59,60) / boulevard (34,75)-(39,75) | **whole band stock**: "road beside the avenue is not a straight arm" | **whole band stock**: "top end: ... not an end this package knows" |

## After (PIDs 23332, 11080, 21060, 448)

| case | log | cells changed |
|---|---|---|
| 1-cell stub W (62,63) | band 26 cells, 3 junction cells, 1 arm cell, 19 written | 4: stub 11225.3 + opening 21817 / 21819 / 20506 |
| 1-cell stub E (67,64) | 3 junction cells, 1 arm cell | 4: stub 11225.1 + opening |
| column from S near the end | `kept: 2 touching road cell(s) left to the stock tiler (DAVTOUCH, 2 tries)` | 8, the road's own cells |
| column on from the end cell | `kept: 1 ... (DAVTOUCH, 1 tries)`, band 27 cells | 10: the road's first cell (69,69) joins the band as its last cell (21804), 3 end cells get other end pieces, 6 road cells stock |
| corner at the end (build with item 3) | nothing written, band unchanged | 6, the road's own cells |
| perpendicular diagonal | `kept: 2 ... (DAVTOUCH, 2 tries)` | 13, the road's own cells |
| row road beside the end row | `kept: 1 ... (DAVTOUCH, 1 tries)` | 5, the road's own cells |
| side road, column from N, crossing (regression) | as before | as before |
| boulevard 1-cell stub (43,79) | `diagonal boulevard ... 36 cell(s), 27 written` | 7: stub 11225 + jrow-A stamp |
| boulevard road beside the end row | `kept: 1 ... (DBVTOUCH, 1 tries)` | 6, the road's own cells |
| boulevard perpendicular diagonal (42,84)-(45,81) | `kept: 2 ... (DBVTOUCH, 2 tries)` | 7, the road's own cells |
| boulevard corner at the end | unchanged: RAGGED end, band kept, end row stock | as before |

Every case was undone with the bulldozer and the band came back cell for cell (`0 cell(s) differ` against the base
snapshot).

Save and reload: the city autosaved with the avenue stub junction, the avenue end-row road and the boulevard stub +
angled diagonal in place, then loaded in a new game. Load log: `dav: load: band ... kept`, `dbv: load: ... kept`,
0 cells written. Snapshot of both bands against the one taken before the save: 0 cells differ.

## Shipped cities (owner look call)

Bands that a touching road used to block now convert when a city loads. Berlin, Germany, same build, switches on vs off:

| | diagonal avenues converted | diagonal boulevards converted |
|---|---|---|
| `SC3NETMOD_DAVTOUCH=0 SC3NETMOD_DBVTOUCH=0` | 0 | 0 |
| on | 2: from (95,101), 13 touching cells masked; from (227,152), 10 masked | 2: canonical (136,-171), 3 masked; (169,-161), 8 masked |

The other Berlin bands still stay stock for reasons that are not touches (a straight avenue they bend into stays
two-way, no staircase split). No picture: my Berlin camera shots did not frame the band.

## Owner look calls

1. Where no junction shape exists (the cases with "kept" above), the touching road stops at the avenue's curb. Traffic
   most likely does not pass there, because the avenue pieces carry their own one-way lanes and the touching cell's
   stock piece is not joined to them. Not measured. A near-carriageway T at end rows would need new art.
2. The brief said "leave the cell it meets to the stock tiler". I kept every band cell as avenue, since a stock ladder
   piece inside the band reads as a hole. The one exception is the column going on from the band's end cell: the cell
   it meets (69,69) is past the band's last row, so it is part of the drag's end and stays in the band.
3. Shipped cities: Berlin gains 2 diagonal avenues and 2 diagonal boulevards on load (table above).
4. Boulevard corner touches keep the existing RAGGED rule (avrbtfix, owner 2026-10-21): the band is kept, its last row
   goes stock.

## Pictures (MAIN `verify\davtouch\owner_shots\`)

- `davtouch_avenue_before_after.png`: stub, column from S, road on from the end cell, corner, angled diagonal, road
  beside the end row. Top row the old build, bottom row this one (zoom 2, rotation 0).
- `davtouch_avenue_kept_junctions.png`: side road and crossing as before, stub W and stub E as new junctions.
- `davtouch_boulevard_before_after.png`: stub before / after, road beside the end row and angled diagonal after.
- `after_reload_dav_z3.png`, `after_reload_dbv_z3.png`: the reloaded city at zoom 3.

The cyan diamond on some after shots is the Road tool's own cell highlight under the parked cursor, not art.

## Notes

- Twice today every SC3U.exe on the PC (mine and other sessions') vanished at once with no fault line and no WER event
  (20:31 and ~21:20). Not this code: the second time it was idle between cases, and the first time was on the old build.
- Lab tools: `dev\davtouch\shots\case.sh` (one Road tool edit + log + diff), `undo.sh` (bulldozer clicks, then the
  game-thread remove for cells a posted click missed), `sheets.py` (owner sheets). Not committed.
