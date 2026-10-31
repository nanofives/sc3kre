# avdiagbreak: diagonal avenue sections break when a road is placed elsewhere (2026-10-30)

Owner report 2026-10-30: "Diagonal sections of 3-lane road sometimes break when placing roads elsewhere."
Branch child/avdiagbreak (from main 6640f27), tree `dev\avdiagbreak\tree`, city Roadless Paradise (192 x 192).

## Verdict

Cause found and fixed. The edit pass of sc3netmod's DAV block reads a window, the retile pass's work box + 24 cells
(`dav_run`, sc3netmod_dav.c). When the window's edge cuts a diagonal band, DAV judges only the part inside the window.
That part fails the band rules:
- fewer than `DAV_MIN_ROWS` (3) clean rows: the `continue` at the `brun < DAV_MIN_ROWS` test, or
- `ok = 0` before the border test of the "touches road" loop.

So the pass never set `border`, and no whole-map pass ran. The revert loop then read the band's pieces in the window
as "no longer in a band" and stock-retiled them (manager `VT(mgr, 0xb0)`, mask 3). The game's retile of one cell
re-tiles the whole connected run, past the window, which is the same trap as hwtdel's 15149 net.

"Sometimes" = position only: the edit's window edge must cross a band. That happens for a road 22 to 26 cells from a
band end, or level with part of a long band. Unconnected roads trigger it too. Piece id, drag direction and save/load
play no part.

## Reproduction (in game, PID 2220, build 6640f27 unchanged)

| step | result |
|---|---|
| two joined diagonal drags from (60,60), 12 rows (`avdb_lab.py avenue 60,60 12`) | `dav: edit: band axis 0, 12 row(s) from (60,60), 36 cell(s) ... 36 written` |
| unconnected road (95,80)-(95,85), 22 cells east of the band's last row (x 71..73, z 71) | window (71,56)-(119,109). `dav: edit: (72,70) avenue piece 20505 no longer in a band -> stock retile`, then the same for (72,71) 20502 and (73,71) 21803 |
| cell diff of (56,56)-(78,76) | **21 cells changed**: rows 64..71 went to stock 43 / 11203 / 39 / 11202, 8 rows of them outside the read window |

Pictures (MAIN `verify\avdiagbreak\owner_shots\`): `before_far_road_breaks_band.png`, `after_far_road_band_intact.png`,
sheet `avdiagbreak_before_after.png`.

## Fix: CUT guard, `re/harness/src/sc3netmod_cut.c` (off switch `SC3NETMOD_CUTGUARD=0`)

Used by DAV's revert loop (`dav_pass` only; `dav_run` and the whole-map pass are unchanged). BV / DBV have the same
pattern and are task avslow's (orchestrator 2026-10-30), so their files are not touched here:
1. `cut_hold`: before reverting, the 8-connected component of block pieces (not kept by this pass) through each stale
   piece is walked. If one reaches the window's border ring (inside the map), the window cut a run: nothing is reverted
   and the pass sets `border`, so the caller's existing whole-map pass decides with the whole band in view.
2. When `border` is already set (a kept band reached the border, the whole-map pass comes anyway), the windowed pass
   reverts nothing. The whole-map pass reverts what is really stale.
3. `cut_reput`: after any revert, cells this pass wrote that the reverts' run-wide stock retile changed get their
   piece back (DAV writes before reverting).

The whole-map pass is DAV's existing mechanism (`a band reached the read border - whole-map pass`). The guard only
routes the cut-and-failed case into it.

## After (PIDs 22836, 16328, 22744; final build PID 22632: far road, same result)

| case | log | cells changed in (36,34)-(100,90) |
|---|---|---|
| far road (95,80)-(95,85) | `dav: edit: (72,70) piece 20505 belongs to a run the read window (71,56)-(119,109) cuts: not reverted, whole-map pass` + `a band reached the read border - whole-map pass` | 6, the road's own cells |
| road north (60,37)-(66,37), window (36,13)-(90,61) cuts the band's first 2 rows | same, piece 21803 at (60,60) | 7, the road's own cells |
| side road (56,66)-(65,66) joins the band | `band axis 0, 12 row(s) ... 3 junction cell(s), 2 arm cell(s) ... 25 written` (median opening 21817 / 21819 / 20506) | 13, road + junction, as before |
| road touching the band end diagonally (74,72)-(80,72), inside the window | 36 x `no longer in a band -> stock retile` (rule "touches road"), window pass 112.5 ms | 37: whole band to stock, same as before the fix (by design) |

DAV pass time (a temporary timer, removed from the final build): no DAV run over 50 ms in the cut cases, whole-map pass
included (192 x 192 map, one band).
The 6 to 20 s between DAV's two runs of one edit (rb_pass, then AVL's post phase `dav_post`) is spent outside DAV
(avx / bv / r9 / hwave / sle / avl), on a shared PC with 3 other SC3 games and 3 test runs going. That is avslow's area.

## Proven in game vs static only

- DAV: in game (cases above).
- DBV and BV: not changed here. Same revert-without-border pattern (`clean < DBV_MIN_CLEAN` `continue` /
  `dbv_band` failure; `bv_parts` failure). The owner's "3-lane" is the boulevard, so the reported breaks are DBV:
  task avslow owns that fix. Second witness (this far-road repro on a diagonal boulevard) pending its DBV change.
- `cut_reput`: built, not exercised in game (needs a revert next to a kept band in one window).

## Owner calls / notes

- A road that touches a diagonal avenue without being a supported junction (here: diagonally at its end) turns the
  **whole** band back to the stock ladder. That is the existing rule (task diagave: "isolated: no other road touches the
  band"), not this bug, but the owner may read it as the same "break". Keeping the rows away from the contact would be a
  rule change. Owner call.
- Not in scope (STATUS asks): the 20505 outer cells at state 2 draw cyan triangles at zoom 3, in both shots.

## Tools

- `re/tools/netmod/avdb_lab.py`: `stair` / `avenue` (diagonal drags as staircase cell lists through manager vt+0xf0,
  nb_drive.py's game-thread build), `road`, `remove`, `snap` (piece.state per cell), `diff`, `grid`.
- `re/tools/netmod/avdb_case.sh` (gitignored helper): snapshot, one edit, new log lines, cell diff.
- Snapshots: MAIN `verify\avdiagbreak\data\*.json` (s0..s2 = the repro, g*/f* = after).

## Round 2 (2026-10-31, on main 91bf829 with avslow's BVGROW / DBVGROW)

### Second witness: boulevards (Roadless Paradise, final build)

| case | log | cells changed |
|---|---|---|
| diagonal boulevard, three joined drags from (60,60), 12 rows (`avdb_lab.py dboulevard 60,60 12`) | `dbv: edit: diagonal boulevard axis 0, 9 row(s) ... 36 cell(s), 36 written` | 44 (build) |
| far road (91,80)-(91,85) beside a road at x 90, window (66..115) cuts the band's last rows | `dbv: edit: the window cuts a diagonal boulevard (side x-) - window grown to (2,56)-(115,109)` | 12: only x 90 / 91 (they became a straight one-way avenue 21700 / 21701), 36 DBV cells untouched |
| straight boulevard x 95..97, z 76..96 | `bv: edit: boulevard axis 1, columns 76..96 ... 63 written` | 63 |
| road (73,52)-(78,52), window z1 = 76 holds only the boulevard's first row | `bv: edit: a boulevard reached the read border (side z+) - window grown to (49,28)-(102,140)` | 6, the road |

Picture: MAIN `verify\avdiagbreak\owner_shots\after_dbv_far_road_intact.png`.

### DAVGROW (`SC3NETMOD_DAVGROW=0` = off)

DAVCUT used to send a cut window to DAV's whole-map pass. On Europolis 1024 that pass costs 300-400 ms, and it runs
twice per edit (rb_pass, then AVL's post phase `dav_post`). Now `dav_run` grows the window on the cut sides (64 cells,
then doubling, the whole map last), the same loop as avslow's `dbv_run`:
- `dav_pass` reports the sides from both detectors: a band that reaches the border (the old `border` test, now per
  side) and DAVCUT's stale components (`cut_hold` walks all of them and records the sides they reach).
- In a cut window the cut band is not written. The wider pass decides it.

Europolis 1024, lab copy `dev\avdiagbreak\tree\Cities\avdb_e1024.sc3`: a 3-row band at (1006,704) (`avenue 1006,704 3`,
in the free strip z 703..707 between roads), then bulldoze + re-place one road cell at (1012,728). The window
(988,704)-(1023,754) cuts the band's top. `SC3NETMOD_PTIME_MIN=0`.

| | ptime of the edit | DAV in rb_pass | DAV in AVL post | window |
|---|---|---|---|---|
| DAVGROW=0 | **818.07 ms**, **621.23 ms** | 406.33, 300.80 | 389.44, 314.53 | whole map, twice |
| DAVGROW on | **5.41 ms**, **5.55 ms** | 1.48, 1.47 | 1.47, 1.53 | grown z- once to (988,640)-(1023,754) |

The band cells are the same after (`data\e1024_after.json`: 21803 / 20501 / 20505 / 20500 / 20502 as built). Typical
unrelated edits on this map in the same games: 3-16 ms. Roadless Paradise cases on the DAVGROW build: far road (x-),
north road (z+), accepted-but-cut band (5 rows inside, z+): each grows once, only the road's cells change. The side-road
median opening converts as before.

Lab note: on Europolis 1024 under load, Frida job replies sometimes time out (300 s) although the edit ran. The ptime
log is the record.
