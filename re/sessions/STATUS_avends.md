# STATUS avends (round 2026-11-09, groups B, C, A, E: the remaining two-way avenue ends)

## goal
The refused avenue ends left on the owner's newest Big One (`dev/avends/tree/Cities/BigOne_owner.sc3`) convert to
one-way halves where a correct one-way layout exists; the rest stay two-way with the reason logged
(brief `ROUND_2026-11-09_avends.md`).

## verdict + deciding code (milestone 1: cause per group, 2026-11-09)
Evidence: load of the owner save in my tree (own PID 5688, log kept as `dev/avends/inst/sc3netmod_run1.log`):
`stats: avl bands converted=34, refused=16`. Live cells read by `np_drive.py cells`, saved tiles by
`network_layer.py --tiles`, saved variants by `netvariant.py scan`, AVX's twin `avjunc_rule.find_c` on the save.
Box drops located with a debug line (env `SC3NETMOD_AVXDBG=1`, added in `sc3netmod_avx.c avx_validate`, logs only).

The 16 refusal lines = 11 ends. Not mine: the D4 chain (604,119) / (606,131) / (608,133) / (608,135): (608,134) still
holds hwt 21227 in this save (owner re-drag pending).

| group | refused end (log) | layout | first failing check |
|---|---|---|---|
| C | none left | ramp T's beside 11258 at (555,64) / (558,64) | already converted by D1 on this save: `(556,64) rows 0..1`, `(560,64) rows 0..4 -> one-way`, live boxes 20831 / 20850 / 20806 |
| B1 | (547,61) z fwd end (547,63) 39.2 + (548,63) 39.0; (549,64) x back end (548,64) 39.1 + (548,65) 11204.0 | z avenue 547/548 T's into x avenue z 64/65 from the N; x avenue's W end is a road X at 545 (box 545), one row 546 between | AVX drops the T box: `avx: dbg drop: box at (547,64) cell (547,64) side W mode T vs (546,64) 21775.2 mode O` |
| B2 | (567,23) z fwd end (567,31) 11204.1 + (568,31) 39.2 ("cells beside the inner bend are not 11204 halves"); (570,31) x back end (569,31) 39.3 + (569,32) 43.0 ("no 11203 inner bend"); (581,33) via its corner | avpaint's own corner + T (converted 2026-10-28), but the newest save has (568,32) 29.0 where the linked half 39 stood; (568,31) 39.2 keeps an S arm into it, the 29 has no N arm | AVL `avl_corner_at`: the half beside the inner bend is not 11204 / a linked T |
| A1 | (562,11) x back end (561,11) 11204.2 + (561,12) 39.3 | U-turn pair (560,11) 11203.3 / (560,12) 11203.2, road 29.1 from the S into (561,12) on the last row | AVL: end row not a U-turn pair; AVX twin: `piece 11203 in the segment` (the walk reaches the U-turn) |
| A2 | (484,18) x fwd end (485,18) 11203.0 + (485,19) 39.1 | U-turn pair whose z+ cell is the bend + an E arm into diagonal road 35.0 (486,19) | AVL: end row not a U-turn pair (39 not 11203); AVX twin: `piece 35 in the segment` |
| E | (613,176) z fwd end and (613,193) z back end, both (613,192) 11204.1 + (614,192) 39.2 | flat row 192 between slope rows 191 (31.2) and 193 (31.0); (614,192) T into a dead end 11225.1 at (615,192) | AVX: 11225 not in AVX_STOCK (arms -1), so no outside arm, no box; AVL ends on the stock T |
| (584,108) | (585,108) x back end (584,108) 39.2 + (584,109) 43.0; (584,110) z back end (584,109) 43.0 + (585,109) 11204.0; (598,110) via the corner | z avenue 584/585 (S) jogs to 583/584 (N) at rows 107..109 where the x avenue z 108/109 T's in from the E and diagonal avenue 20950/20951 arrives at row 106 | see design: no clean one-way layout |

B1 detail: the save's variant list holds AVX two-way LINK noses 21775 / 21776 at (546,64) / (546,65) (saved as 11204).
AVX's z walk from the stem (547,62) makes the 4-cell box first; the x walk's equal box loses the tie (`keep the bigger`).
The z box looks W for a crossing-avenue span: `avx_make` needs a straight pair within 3 cells, `avx_pair` excludes link
noses, the next cells are box 545 and an empty cell, so no span: W edge = road arm 'T' against the nose's one-way 'O'.
Measured: a copy of the save without the 21 saved variants in 540..552 x 58..68 (`BigOne_strip547.sc3`, own PID 5372)
builds the box from existing pieces (20807 / 20808 / 20809, link noses 21772 / 21773 on row 63, noses 20800, 20803 at
546) and converts `(547,61) rows 0..0` and `(550,64) rows 0..3`; refused 16 -> 14. The twin reads saved bases only, so it
keeps the box: twin and game disagree on reloaded cities.

## design (agreed 2026-11-09: order B1, B2, E, A1, A2, then F = the (584,108) jog, design first)
Ids: piece ids **22000..22099** (the brief's 20900..20999 is taken in the installed tables: boulevard_junctions
20900..20905 / 20910..20949, diagonal_boulevard 20950..). Curve shapes **26500..26999** (first free block above 25508
outside avdiamond's 25500..25999 grant and the wall-lighting twin ids 26000..26209).

## built
- B1 (AVX block AVTEE, `SC3NETMOD_AVTEE=0`): a crossing-avenue span is also found on a row of our link noses.
- B2 (AVL block AVCT29, `SC3NETMOD_AVCT29=0`): a corner + T reads a plain 29 in the linked-half spot; piece 22000
  (package avenue_ends, base 29).
- E (AVX block AVSTUB, `SC3NETMOD_AVSTUB=0`): the road dead end 11225 is a road arm (one side, S at state 0).
- A1 / A2 (AVX + AVL block AVUEND, `SC3NETMOD_AVUEND=0`): AVX walks stop before a U-turn pair (avcore's block); AVL end
  kinds 9 "join + U-turn" and 10 "U-turn with a road" (piece 22001, base 39).
- Debug only (`SC3NETMOD_AVXDBG=1`): AVX logs validation drops and piece puts that do not take.
- Twin: `avjunc_rule.city_layer_saved` (saved variant list), `link_row`, `STUB_MASK`, `uturn_stop`; tools `avends_diff.py`, `avends_seams.py`,
  `avends_build.py`. Results: `verify/avends/RESULTS.md` (worktree).

## proven game-side vs static only
Owner save, all groups: converted 34 -> 43, refused 16 -> 7 (B1 + B2 -> 39 / 11, E -> 41 / 9, A -> 43 / 7); routed
trips 0 steps against on every converted half; save + reload identical per group; no-mod load = saved bases; each
switch off gives the previous result back. Shipped cities in game: the 6 new boxes live, except Sacramento (168,139),
where the game's piece writer refuses the put (an existing AVX limitation, 3 non-avends cells there too). Static:
English-UK. Still two-way on the owner save: the D4 chain (4 bands, owner re-drag pending) and the (584,108) knot (3).

## blocked on
Nothing. F built (owner go 2026-11-09): F2a DBVBENDT, F2b BVSHORT, F3 BVNT (pieces 22002..22013), plus AVLKEEPMAP (AVL's
band map was cleared by load-time re-runs; needed for F). Owner save: converted 50, refused 4 (only the D4 chain).

## files owned (worktree dev/avends/wt unless MAIN)
- `re/harness/src/sc3netmod_avx.c` (B1 AVTEE; debug drop lines under `SC3NETMOD_AVXDBG=1`, logs only)
- `re/harness/src/sc3netmod_avl.c` (B2 AVCT29, A AVUEND, F AVLKEEPMAP)
- `re/harness/src/sc3netmod_dbv.c` (F2a DBVBENDT), `re/harness/src/sc3netmod_bv.c` (F2b BVSHORT, F3 BVNT, debug
  `SC3NETMOD_BVDBG=1`), `re/harness/src/sc3netmod_bvx.c` (F3 box skip), `re/harness/src/sc3netmod.c` (`bvn` line)
- `re/tools/netmod/diagbv.py` (F2a twin), `re/tools/netmod/netpack.py` + `netpack.schema.json` (`bvn` lines)
- `re/tools/netmod/avends_dbvdiff.py`, `re/tools/netmod/avends_fbuild.py` (new)
- `re/tools/netmod/examples/avenue_ends/bvn_22002..22013.lanes.json` (new, 12 files)
- `re/tools/netmod/avjunc_rule.py` (AVTEE twin, table_info, city_layer_saved)
- `re/tools/netmod/avends_build.py`, `re/tools/netmod/avends_diff.py`, `re/tools/netmod/avends_seams.py` (new)
- `re/tools/netmod/examples/avenue_ends/manifest.json`, `.../ct_22000.lanes.json`, `.../ct_22001.lanes.json` (new)
- `re/tools/netmod/examples/avenue_ends/avends_pieces.json` (new, ignored by the examples rule: needs `git add -f`, as
  avdiamond_pieces.json)
- `verify/avends/RESULTS.md` (new)
- MAIN `re/sessions/STATUS_avends.md`
- not in git: package art `examples/avenue_ends/art/22000..22013` (worktree only until release), pictures
  `MAIN/verify/avends/owner_shots/*.png`, lab saves in `dev/avends/tree/Cities/` (BigOne_strip547, BigOne_b12_saved, BigOne_e_saved, BigOne_a_saved)
- release step: `netpack.py install avenue_ends --tree stage/src` (art from the worktree)

## game-harness need
My tree only (dev/avends). Own PIDs so far: 5688, 19404, 5372, 17616, 16944, 2972, 9140, 4456, 3560, 16656, 3536.

## asks of other sessions
None.
