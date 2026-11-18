# STATUS dbvx49 (child, round 2026-11-17b)

## goal
Junctions 49 (DA x DB cross), 51 (DA x DB T2), 53 (DB x DB cross) get their junction boxes at 3, 4 and 6-row arms,
both draw orders, sandbox + showcase layout. Off switch for any C change.

## verdict + deciding code (2026-11-17)
Fixed except 49 at 3 rows' 1-row avenue stub (4 stock cells, open). Full record: `verify/dbvx49/RESULTS.md`.
Causes: (a) 49 / 53 template windows cut from 6-row arms (one cell off at 4 rows, anchor off the chain at 3 rows);
(b) `dbv_end_kind` cap tests read 9-wide rows, a street 2 rows past an axis-1 end made it RAGGED (showcase 51 / 53);
(c) ends inside a template's rows were skipped (`jxrow`), 49 at 4 rows lost its cap; (d) the box splits the diagonal
avenue, its stub past the box is under `DAV_MIN_ROWS`.

## built
- `sc3netmod_dbv.c`: DBVCAPNEAR (`SC3NETMOD_DBVCAPNEAR=0`), DBVXENDCAP (`SC3NETMOD_DBVXENDCAP=0`), debug
  `SC3NETMOD_DBVCAPDBG=1`.
- `sc3netmod_dav.c`: DAVSHORTBOX (`SC3NETMOD_DAVSHORTBOX=0`).
- package diagonal_boulevard 0.3.1: 8 short-arm template variants (ids 23..30), no new art. Full pack with art for
  stage/src: `dev/dbvx49/packs/diagonal_boulevard`. Installed in dev/dbvx49/tree only.

## proven game-side vs static only
- game, sandbox (b0 before / a7 after, both orders cell-identical): 49 at 3 / 4 rows box 0 -> 7, 53 at 3 / 4 rows box
  0 -> 8, 49 at 4 rows stock 13 -> 6, 49 / 53 / 51 at 6 rows unchanged except 53's top-left cap (6 cells).
- game, showcase: 49 / 51 / 53 stock 13 / 12 / 12 -> 6 / 6 / 6, boxes drawn in 49 / 53.
- game, Berlin: 19,220 cells, 0 differ fix on / off.
- game, side effects (pictures owner_shots/side_*): far-end caps on 50 52 54 55 (4 rows, showcase), 54 / 55 / 53 at 6
  rows, showcase 42 / 44, sweep 51.
- sweep 80 cases: s1 (build before the Berlin fix): only 51 53 54 55 differ from diagarm's m3 (released code), all
  explained by end caps; 31 32 33 differ from final1117/s1 in m3 as well (baseline drift). s2 on the final build:
  identical to s1 (73 of 80 identical to final1117/s1, the 7 others as above).
- static: `verify/dbvx49/shortx.py` emulation, variants change no template choice on other diagonal cases.

## blocked on
-

## files owned
- dev/dbvx49/wt: `re/harness/src/sc3netmod_dbv.c`, `re/harness/src/sc3netmod_dav.c`,
  `re/tools/netmod/examples/diagonal_boulevard/manifest.json`
- `dev/dbvx49/packs/diagonal_boulevard` (full pack with art, for stage/src)
- `verify/dbvx49/*` (untracked tools, runs, owner_shots, RESULTS.md), `re/sessions/STATUS_dbvx49.md`

## game-harness need
dev/dbvx49 tree only.

## asks of other sessions
- orchestrator: install diagonal_boulevard 0.3.1 from `dev/dbvx49/packs/diagonal_boulevard` into stage/src; owner
  call on the side-effect caps (section 5 of RESULTS.md).
