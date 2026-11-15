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
