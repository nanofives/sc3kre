# STATUS diagfix (child of "SC3 Simtropolis feedback triage"), 2026-11-14

## goal
Round 2026-11-14b (`re/sessions/ROUND_2026-11-14b_junctions.md`), stream `diagfix`: fix the red / yellow xsect cases
that have a diagonal avenue (DA) or diagonal boulevard (DB) in them. Files: `sc3netmod_dav.c`, `sc3netmod_dbv.c`.
Milestones: 1 rail / highway cut (68 69 72 73, then 80), 2 diagonal x diagonal, 3 orthogonal band meeting a
diagonal, 4 the two DA bands re-tiled on every later edit (40, 41).

## verdict
- **Milestone 1 DONE, commit b54c02e on child/diagfix** (regression m1 clean, see verify/diagfix/RESULTS.md). Cause: a DA / DB drawn across a rail line or under a highway holds the game's shared
  crossing pieces on those rows (69 road x rail, 15098 highway over road). `rb_read` reports them as ROAD, so they are
  full band cells, and the DAV / DBV write loop put 20505 / 20500 / 20950 / 20951 over them through the piece writer
  FUN_10008919: the occupant became road-only and the rail or highway lost the cell. Fix DAVXNET: such a cell
  (base 69 / 67 / 11258 / 15098 / 16006 / 16007, or Protected for ROAD by FUN_1001a7f7 as BV asks) stays a band
  cell for masks and neighbours but is never written. Same as the stock diagonal road (74 / 75): crossing at grade,
  under the highway.

## built
- `sc3netmod_dav.c`: `dav_xnet()` + skip in the write loop, log line `dav: <who>: band axis A from (x,z): N rail /
  highway crossing cell(s) kept (DAVXNET)`, stats line. `sc3netmod_dbv.c`: same skip + log line. Off:
  `SC3NETMOD_DAVXNET=0`.
- `verify/diagfix/regress.py`: the xsect sweep re-run into `verify/diagfix/<run>/`, diff + before|after sheets.

## proven game-side vs static only
Game-side (dev/diagfix tree, xsect_sandbox_clear.sc3): 68 69 72 73 built, rail row keeps 44 + 69.1 crossings,
highway rows keep 15051 + 15098; pictures `verify/diagfix/try1/raw/`.

- Case 80: stock limit (no on-ramp beside any diagonal road), accepted by the orchestrator.
- **Milestones 2-4 COMMITTED** on child/diagfix: 16a9f81 (DBVCAPCLEAN + DAVDBVWIN), 17ed8de (DAVXAVL + dbvlanes art-copy
  fix), 44a7e03 (DAVBVBEND). Regression m3: no green case changed. Detail: verify/diagfix/RESULTS.md.
- Art fix 21917/21918/21919: my tree only; stage\src waits for the orchestrator (fix_dbv_art.py).
- ORTHFIX_ASKS.md handed to the orchestrator.
- **Family a) DA part COMMITTED 4cd3469** (merged main 7d1df99): DAVBEND135 + DAVBENDSTUB, pieces 22430..22441
  (axis 0 + axis-1 mirror), regression m5 clean. In game: verify/diagfix/bend3 (15), bend2 (b15), bend4 (m15).
- **Case 19 + DBVBROW COMMITTED a4d15cd**: DBVBEND135 kinds 18/19 (22442..22457, axis 0 + axis-1 mirror), DBVBROW
  (case 42, orthfix item 3). Regression m8: no green case changed. Item 1 (case 39) needs no DAV change (DAVBVBEND).
- Ids: 22430..22469, 22362..22399, 22488..22498 granted. Used 22430..22457; free: 22458..22469, 22362..22399, 22488..22498.
- Next: 34 (avenue into a DB end), 41 (boulevard into a DA end; BV writes those cells, spec to orthfix first), 48
  (corner box), then the 38/40/42/44 boxes (ask for ids; paint from verify/orthfix/mockdiag.py).
- Art lives in dev/diagfix/packs_src (KEEP file) + dev/diagfix/tree packs; stage\src untouched.

- **diagfix 7 (3d4350e) + 8 (36d1c3f) merged into main 380dd35**: bend sets 34 / 41 (DAVBBEND) / 45 (DBVBBEND), 48 corner,
  38 / 40 boulevard x DA boxes. orthfix switches BVBEND on against them.
- **diagfix 9 (ae206a0)**: 42 / 44 boulevard x DB boxes (DBVJBV, kinds 23-25, 22700..22720). Regression m10: only 42 / 44
  changed against m9.
- Ids: 22370..22399 used (41, 45), 22600..22661 (48, 38/40), 22700..22720 (42/44). Free: 22662..22699, 22721..22798.
- Next: families c) 49 / 53 and d) 50 / 52 / 54 / 55: crossing templates inside DBV (like DAV's davx), generated from
  one scene over 8 symmetries (4 turns x the x/z swap); DAV already yields DBV-claimed cells (bend 3).

- **diagfix 10 (153f4e0 WIP + 86c4a69, on main d4bfea9)**: c) / d) boxes 49 50 52 53 54 55 as DBV crossing templates
  (DBVX, verify/diagfix/dbvx_build.py, pieces 22721..22785), DAVX_MAX 64 -> 128 (main drops 4 of the 40 box templates
  without it). Regressions m11 / m12 clean (45 as before). Reverse draw order: all but 49 (DB drawn first) match.
- Open: 49 drawn DB first (band judged before the last drag lands); axis-1 mirrors of 45 (needs ids); BENDAVM on
  xsect-length axis-1 DB (geometry limit). Ids left: 22662..22699, 22786..22798.

- **diagfix 11 (6cf215f)**: 45 axis-1 mirror `bendbvm` (22662..22673), DBVXDBG log, pack versions 0.8.0 / 0.3.0.
  Final regression m13 clean (= m12), both draw orders checked (39/41/45 via orthfix order_cmp; 49..55 rev_cases).
  49 DB-first passed in m13, failed in two earlier runs: timing-sensitive, open.
- **Ship set ready: dev/diagfix/packs_src/SHIP.md** (diagonal_avenue 0.8.0, diagonal_boulevard 0.3.0).

## blocked on
Nothing.

## files owned
- `re/harness/src/sc3netmod_dav.c`, `re/harness/src/sc3netmod_dbv.c`, `re/tools/netmod/dbvlanes.py` (child/diagfix)
- art: `dev/diagfix/tree/mods/netmod/packs/diagonal_boulevard/art/2191{7,8,9}` (tree copy only; stage\src untouched)
- `verify/diagfix/**`, `re/sessions/STATUS_diagfix.md`

## game-harness need
dev/diagfix tree game (its own PID, SC3MODS_MULTI). Harness claim `diagfix`.

## asks of other sessions
None.
