# STATUS orthfix (child of "SC3 Simtropolis feedback triage"), 2026-11-14

Round brief: `re/sessions/ROUND_2026-11-14b_junctions.md`. Cases (all yellow, "refused by design" in
`verify/xsect/RESULTS.md`): 26 A x B corner, 37 B x B corner, 62 avenue narrowing into a road, 63 four roads side by
side, 67 B x rail, 71 B x highway. Workspace `dev/orthfix/{wt,tree,inst}`, branch `child/orthfix` from main bada3bc.
Ids granted: pieces 20769..20789 (BV crossing twins), 22400..22429 (avlt + corner boxes).

## goal
Turn each refused case into a converted junction, or bring a new look to the owner as a candidate.

## verdict (per case)
| case | cause (log line, code) | fix | state |
|---|---|---|---|
| 67 B x rail | BV run stops at the Protected crossing column (`bv_full` excludes `bv_prot`); the end reads "3 roads going on" = `an end where the roads going on are not one road or an avenue`; the ragged fallback leaves the column beside the rail stock 11204/29/11204, then AVL leaves the 1-row crossing band two-way | BVXING (`sc3netmod_bv.c`): the run walks through 1..4 crossing columns (same Protected base 69 / 67 / 11258 / 15098 x 3, road along the run) when a full boulevard column follows; the columns beside it end their median in a nose; crossing cells get BV twins 20769..20780 (outer = AVL's 21710.. lanes, middle = two-way 14 / 241 lanes), base art | MERGED main 51a4f76 (child/orthfix 328523e); sweep run1 OK |
| 71 B x highway | same, crossing piece 15098 (2 columns) | same block | MERGED main 51a4f76; sweep run1 OK |
| 62 A into R | AVL AVUEND: `U-turn with a road: no avlt piece for (33,123) 39.3 outline CAIA modes CTOI` (avends' 22001 is the mirror case) | avlt piece 22400 (avenue_ends, outline ACAI modes ICTO at state 0, base 39), lanes by avends_build, box art copied from 22001 (same outline, so no new look) | MERGED main 51a4f76; converts in run1 (`ends: U-turn / U-turn with a road`); look accepted as existing |
| 26 A x B corner, 37 B x B corner | `bv_run1`: `an end on a corner (road on one side only)` | BVCORNER: a corner end is a T box whose far side is closed; bvlanes corner kinds BcB / BcAn / BcAs (every lane turns), 20 box pieces 22401..22420, art by bvx Box (square curbed outer corner = NEW LOOK) | child/orthfix d0fdd59 (tooling) + bv.c in 328523e; OPT-IN `SC3NETMOD_BVCORNER=1`; in game both convert (corner1), pictures `verify/orthfix/owner_shots/ba_26_AxB_L.png`, `ba_37_BxB_L.png`; full sweep with it on = run2 |
| 63 four roads | `bvx_spans`: `road more than 3 wide beside the boulevard` | no pick: options sheet `verify/orthfix/owner_shots/63_options.png` (A two avenues side by side, B one wide boulevard with a 2-cell median = new art, C stay stock) | OWNER CALL 2026-11-14: option A (two avenues side by side), default on. Block BVQUAD in `sc3netmod_bv.c` (SC3NETMOD_BVQUAD=0 off), coded, not built yet |

## built
- `re/harness/src/sc3netmod_bv.c`: BVXING (`bvr` lines, `bv_xcol`, `bv_xspan`, kind 8 columns, twins written at the
  crossing's state, twin revert = base written back since a Protected cell survives a retile, bvs_map skipped for
  twins), BVCORNER (opt-in). `sc3netmod.c`: `bvr` added to the line filter.
- `re/tools/netmod/boulevard.py`: crossing twins (`XING`, `xing_specs`), manifest 0.4.0 with `boulevard_slope_lines`
  bvr lines; runs() corner ends (`CORNER`, env BV_CORNER=0 off). `bvx.py`: NEWPAT ICCI, shapes BcB / BcAn / BcAs.
  `bvlanes.py`: corner scenes, corner turn rule (a corner's only turn takes every lane), pool + 22401..22429, orthfix
  ids' curves allocated last. `avends_build.py`: ids 22400..22419 accepted. `netpack.py` / schema: `bvr` lines.
- Rebuild check: `bvlanes.py build boulevard boulevard_junctions diagonal_boulevard` reproduces every existing spec
  byte for byte (all three packages must be passed, else the avx32 shapes renumber); only `bvlanes_boxes.json`
  changes (225 -> 309 lines, 0 removed). avends_build reproduces 22000/22001 except one appended shape 26503 in
  ct_22000's curve list.

## proven game-side vs static only
- Game-side (try1, sandbox, 4 cases): 67 and 71 convert, pictures `verify/orthfix/try1/raw/`.
- Static only so far: 62, corners, 63 options.

## blocked on
Nothing. Owner call pending: corner look (26 / 37).

## ship set
`dev/orthfix/ship/` (SHIP.md: boulevard 0.4.0 + avenue_ends with 22400, install commands). No corner art.

## files owned
Code (committed on child/orthfix when the group passes the sweep): the files under "built", plus
`re/tools/netmod/examples/boulevard/{manifest.json,bvr_2076*..2078*.lanes.json}`,
`examples/avenue_ends/{avends_pieces.json,manifest.json,ct_22000.lanes.json,ct_22400.lanes.json}`,
`examples/boulevard_junctions/{manifest.json,bvlanes_boxes.json,bvl_22401..22420.lanes.json}`.
Art (gitignored, must reach `stage/src` by `netpack.py install`): `dev/orthfix/packs/avenue_ends/art/22400` (copy of
22001), `dev/orthfix/packs/boulevard_junctions/art/22401..22420` (bvx.py build --only). The crossing twins have no art.
Records: `verify/orthfix/` (sweep.py copy with `final`, compare.py, mock63.py, runs, owner_shots).

## game-harness need
My own game only (`sc3dev run orthfix`), PIDs recorded in `dev/orthfix/last_pid`.

## asks of other sessions
None (no change to dav.c / dbv.c).

## side effects to know
- My tree got `stage/src`'s ledger + packs (it had none). Reinstalling through today's netpack also rewrote
  OccupantAttribs_Korea.IXF and the sprite DATs (renumbered), and printing the install report crashes in
  `_print_report` on a growable entry (`%d` given a list) after the files are written: a netpack bug outside this
  stream, not fixed here.

## update 2026-11-14 late
- Owner calls: corners "Square, as shown" -> BVCORNER default on; 63 option A -> BVQUAD (default on).
- child/orthfix 668b298 (BVQUAD + BVCORNER default), d0fdd59 (corner tooling), 328523e (merged as main 51a4f76).
- run4 default-config regression: 65 identical, only the six fixes + the explained five changed.
- Ship set `dev/orthfix/ship/` now has boulevard_junctions too.
- Next (queued by the orchestrator): diagfix asks 38/39/40/42/44 (BV arm into a diagonal band), after diagfix's
  DAVBVBEND merges. Assessment: needs a boulevard end / opening cut along the diagonal, i.e. new pieces.

## update 2026-11-15 (diagfix asks 38/39/40/42/44)
- Orchestrator: full look (new art) wanted. Offline mockups done, no game: `verify/orthfix/owner_shots/mockdiag_options.png`
  (1 boulevard ends on a DA, 2 DA leaves the boulevard's side, 3 boulevard crosses a DA), script `verify/orthfix/mockdiag.py`
  (diagave_paint.Crossing + a BoulevardEl element; plain cells use shipped art). Sent to the orchestrator for the owner.
- Box cells (9 per shape) are DAV/DBV's; mine = boulevard cells cut along the box's diagonal edge (about 6 pieces with
  the axis mirror). Asked for ids 22470..22481. Waiting: owner look call, ids, and the go after diagfix's DAVBVBEND merges.
- Ids 22470..22481 GRANTED 2026-11-15 for the boulevard cut pieces. Idle until the owner call + go after DAVBVBEND.

## update 2026-11-15 BVDIAG rule part
- child/orthfix 6788440 (on main ba48e8d): BVDIAG (SC3NETMOD_BVDIAG=0 off). 38 / 39 / 40 convert up to the diagonal;
  41 (bend) unchanged; 42 / 44 convert with 8-cell arms (sweep's 6-cell stems too short once DBV claims touching cells).
- run5 (77 cases) vs xsect and vs diagfix m3: no green case changed. Sheet `owner_shots/ba_sheet_bvdiag_38_40.png`.
- Box-cell spec for diagfix: `verify/orthfix/BOXCELLS.md`; reference frames `dev/orthfix/mockdiag_frames/`.
- Waiting: owner's yes on the mockups, then art (39 opening cells = mine, 22470..22481) + nose move.
- 2026-11-15: main acd1938 (BVDIAG + DAVBEND135) merged into child/orthfix. 39 box = mine, all 9 cells; ids 22470..22487 (18 = 9 cells x 2 axes, never past 22498). 38/40/42/44 boxes = diagfix, painted from verify/orthfix/mockdiag.py (keep it stable). DBVTOUCH in 42 = diagfix. Still no art until the owner says yes.
- 2026-11-15: fdb94d9 (2-column stems on a diagonal end, DBV pieces always diagonal: 42 / 43 / 44 convert and keep);
  72f1c68 BVBEND (41 staircase end before the band's overlap, opt-in SC3NETMOD_BVBEND=1 until diagfix's bend sets for
  DA (41) and DB (45) exist; with today's DAV / DBV the bend is refused and the diagonal falls back to the stock ladder).
  run8 (main 60311b0 + orthfix): vs run7 76 identical, 42 changed by DBVBROW only. Merged main 60311b0.
- 2026-11-15: bfa6f2f BVOBOX, the 39 opening box (owner "Yes, all three"): package boulevard_diagonal 22470..22487
  (art + right-hand lanes from verify/orthfix's mockup scene, shapes 29000..29085), built by
  re/tools/netmod/bvdiag_build.py; mirror set checked on a one-off build (verify/orthfix/mirror_case.py). run9 vs run8:
  76 identical, 39 converts. Pictures owner_shots/ba_sheet_obox_39.png, obox_mirror_z4.png. Ship set + SHIP.md updated.
- 2026-11-15: c045eca BVBEND default on (SC3NETMOD_BVBEND=0 off), on main 380dd35 (diagfix's bend sets DAVBBEND
  22370..22387, DBVBBEND 22388..22399). 41 / 45 checked in game in both draw orders: same pieces
  (`owner_shots/ba_sheet_bend_41_45.png`, `bendon1/raw/R41_*`, `R45_*`). run10 vs run9: 9 changed = diagfix 7-8
  (15 19 34 38 39 40 48) + 41 45. vs diagfix m10: 39 / 41 / 45 identical.
- REGRESSION, not mine: 39 lost the owner-approved opening box. DAV's DAVBBEND (sc3netmod_dav.c ~848) matches 39's T
  (boulevard through, DA stem from its side) as a boulevard ENDING into the DA, writes 22370..22378 on the box and
  splits BV's run. Same in diagfix m10, independent of BVBEND. Proposed guard (diagfix's file, needs an ok):
  `!RD(BX(-1), BZ(0))` in the DAVBBEND test (the boulevard must not go on past the band's first row; (161,68) in 39,
  empty (17,86) in 41). Picture `owner_shots/ba_39_davbbend_regression.png`.
- 2026-11-15: merged main c65b8f5 (87b3b05), ce64b18 DAVBBEND guard in sc3netmod_dav.c (orchestrator's ok): the cell past
  the band's first row must be no road, read through DAVTOUCH's masks (dav_road_unmasked; plain RD saw the masked
  boulevard as empty). run11 vs run10: 74 identical, 39 back to the box (= run9), 42 / 44 = diagfix 9 (= m10). 41 bend
  kept both orders. Open: 39 drawn diagonal first stays the stock ladder (DAV post-AVL STRAIGHT_OK checks avl_dir only,
  not BV's one-way pieces), pre-existing, not changed. Picture owner_shots/ba_39_guard.png.
- 2026-11-15: e7fbe55 DAVBVOUTER (on main 8d2397f, orchestrator's ok): 39 drawn diagonal first now gets the box. Cause:
  AVL maps only its own bands, so BV's outer piece at the bend-into cell had avl_dir -1 when the diagonal came first;
  dav_bv_oneway needs avl_dir too, and a post-only accept was reverted by the next edit's main pass. Both STRAIGHT_OK
  branches accept g_bv_p[0] (SC3NETMOD_DAVBVOUTER=0 off). 39 / 41 / 45 reverse = sweep order (verify/orthfix/post3,
  order_cmp.py). run12 vs run11: 77 identical (build + final read; its xsect before|after shots were stopped, same cells as run11).

## round 2026-11-15b (owner review of the final sheets, brief re/sessions/ROUND_2026-11-15b_owner_review.md)
- Workspace refreshed: child/orthfix fast-forwarded to main 4b761ac; dev/orthfix/tree rebuilt from stage/release
  (old tree kept as dev/orthfix/tree_old1114) + stage/src ledger and packs; all mods rebuilt.
- 67 / 71 (BVXART): new `re/tools/netmod/bvxing_paint.py` paints the crossing twins' own art. 67 = RailXing (the
  boulevard's 3 + 3 lanes and white dashes across the crossing column, median as paint between two yellow lines, one
  stop bar per carriageway on its approach side, 69's rail band read along the rails so it runs unbroken over all three
  rows). 71 = Underpass (ray cast over a box model fitted to stock 15098 / 11258: deck top at 32, open-face deck edge
  6 deep, side walls along the road; the walls between boulevard rows removed, what the ray meets next drawn instead:
  the boulevard ground or the far outer wall; the deck alone as layer 1 like the stock's). Ids 30200..30208 (art twins
  of 69 / 15098 / 11258: A, B, middle), boulevard pack 0.5.0, table lines `bvq` (sc3netmod_bv.c prefers them,
  SC3NETMOD_BVXART=0 off; sc3netmod.c line filter; netpack.py + schema accept bvq). Offline mock sent:
  verify/orthfix/owner_shots/mock_67_71_art.png.
- 66 / 70 answer: yes, inconsistent next to the new 67 / 71 (two stock 2-lane crossings with yellow lines / two
  tunnels with a wall between). Owner call, unchanged.
- 29 / 31 / 32 / 33 cause: the avenue's end against a 45-degree band: one half ends on a plain band edge piece (not
  connected), the other meets DAV/DBV's single-road T and its first cell is a stock T 39 (the "stock box"). Needs an
  avenue T box with avlj joins in the band (diagfix's cells). Asked the orchestrator.
- 43 cause: DBV refuses the band ("road above the band is not a straight single road"), BV then refuses on the stock
  drags. Needs DBV to accept a band starting at a boulevard's side (DAVBVBEND's twin, diagfix). My side coded:
  bvdiag_build.py sets C / D (DB opening box, ids 30209..30232, needs 72 curve shapes, asked for 60 more), bv_obox
  generalised to a 4-wide band (BVOBOXDB, `bvo 2|3` lines, SC3NETMOD_BVOBOXDB=0 off).
- 2026-11-16 (orchestrator: owner approved 67 / 71, wants 66 / 70 the same; shapes 29200..29299 granted; orthfix builds
  43's DBV part and the 29-33 boxes itself):
  - 66 / 70 AVXART: avenue art twins 30233..30238 (bvxing_paint Section(rows=2), Underpass rows=2), `avlq` lines in the
    boulevard pack's avenue_lines, sc3netmod_avl.c prefers them (SC3NETMOD_AVXART=0 off). In game: art2.
  - 43: DBVBVBEND (sc3netmod_dbv.c, marked orthfix block, SC3NETMOD_DBVBVBEND=0 off): new end kind DK_BVOPEN, the
    band's last 3 rows inside a straight boulevard that goes on both sides -> those rows left to BV (MARK 16|2);
    BVOBOXDB (bv.c): bv_obox takes a 4-wide band and the `bvo 2|3` sets; boulevard_diagonal 0.2.0 (bvdiag_build.py
    sets C / D). In game (art3): box written, DBV 9 rows, reverse order identical.
  - 29 / 31 / 32 / 33: no C code. DAV / DBV crossing templates built by verify/orthfix/avtbox_build.py (29, DA, reuses
    diagfix's box_build / corner_build) and verify/orthfix/avdbx_build.py (31-33, DB, reuses diagfix's dbvx_build), each
    with `avlj` end-column lines; packages avenue_diagonal_t (30239..30260) and avenue_dbv_t (30261..30355); netpack +
    schema accept davx / dbvx lines in avenue_lines. In game (art3, SWEEP_ARM=10): every arm 21700 one-way, no 11204 /
    39 left; reverse orders identical at the junction.
  - run13 (BVXART only) vs final1115: 75 same, 67 / 71 changed only. run14 (everything) running.

### files owned (round 2026-11-15b)
re/harness/src/sc3netmod.c (bvq filter), sc3netmod_bv.c (BVXART, BVOBOXDB), sc3netmod_avl.c (AVXART),
sc3netmod_dbv.c (orthfix DBVBVBEND block only), re/tools/netmod/bvxing_paint.py (new), boulevard.py, bvdiag_build.py,
netpack.py, netpack.schema.json; verify/orthfix/{avtbox_build.py, avdbx_build.py, compare.py, run_sweep.sh, RESULTS.md,
art1..3, run13, run14, owner_shots/{mock_67_71_art, ba_67_71_art, ba_66_70_art, mock_43_obox_db, ba_43_29_33}.png}.
Package dirs (art gitignored, ship from here): dev/orthfix/packs/{boulevard_x (boulevard 0.5.0), bvdiag_x
(boulevard_diagonal 0.2.0), avtbox (avenue_diagonal_t 0.1.0), avdbx (avenue_dbv_t 0.1.0)}.
- 2026-11-16: run14 vs run13: 73 same, 29 43 66 70 changed (intended). Short arms (6): 31 / 32 / 33 identical to the
  stage look (templates need ~10-cell arms), nothing broken. 70 seam fixed (EDGE 16), a small median nub remains.
  Committed child/orthfix eb956f2 (one commit for the round). Ship set dev/orthfix/ship/SHIP.md (boulevard 0.5.0,
  boulevard_diagonal 0.2.0, avenue_diagonal_t 0.1.0, avenue_dbv_t 0.1.0). verify/orthfix/{avtbox_build,avdbx_build}.py
  live in MAIN's verify/ (not on the branch).
