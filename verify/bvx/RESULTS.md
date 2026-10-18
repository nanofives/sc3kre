# bvx: boulevard junctions with avenues and with other boulevards (2026-10-17 / 18)

Owner ask (avenue program, wave 2, via the orchestrator): straight junctions of the 3-wide boulevard with avenues
and with other boulevards, in the language of the avenue junctions: one paved box, crosswalks across every arm,
every median ending in a concrete nose with its trees, white dashed lane lines up to the crosswalk, curbs continuous.
Light test per owner rule: one lab game, pictures, save and reload.

Setup: worktree `Simcity_wt_bvx` (branch child/bvx from round/avenues), test tree `Simcity_stock_bvx`, instance
`re/harness/inst_bvx`, sc3netmod.dll built from this branch (230,912 bytes). Packages installed (overlay): boulevard,
avenue_junctions, avenue_markings, boulevard_junctions. Pictures (not committed): `MAIN\verify\bvx\owner_shots\`.

## Stock today (offline tiler)

Each kind tiles as a patch of 43 / 39 / 11203 tiles with the boulevard's 11204 / 29 / 11204 around it (left column of
`bvx_mockup.png`). Before this change the BV block refused every run with an avenue or boulevard beside it ("road
beside the boulevard is not a straight single road"), so the whole boulevard stayed stock, not only the junction.

## Design

- Where it lives: inside the BV block's run rule, because a junction is part of a boulevard run (the run must go on
  through it, and its neighbours get the median noses). New file `sc3netmod_bvx.c` (#included after
  `sc3netmod_bv.c`), called from `bv_run1` at lines marked `task bvx`; twin `bvx.py`, called from `boulevard.runs()`.
- Junction span: consecutive run columns with road beside the run. 1 wide stays the boulevard's road junction
  (unchanged). 2 (avenue) or 3 (boulevard) wide, each side road over the whole span or empty, every arm straight and
  clean for 2 cells = a wide span. At the run's very end with nothing beyond and arms on both sides = T (the
  boulevard ends there, end type 4 in C, `tee` in the twin). Refused: one side only at an end (a corner), road 4+
  wide beside the run, an arm shorter than 2 or with road beside it. Staggered single roads keep the old per-column
  rule (regression below).
- Box cells: each cell's piece from its REAL edge pattern N E S W (I box, A arm, C closed), so the two runs that cross
  in a boulevard x boulevard box (one along x, one along z) write the same piece and state. The canonical set under
  rotation is 6 patterns: AIIA 20900 (corner of two arms), IACI 20901 and IICA 20902 (corner of an arm and the closed
  side, two mirror images), IIAI 20903 (one arm), IICI 20904 (one closed side), IIII 20905 (3x3 middle).
- Arms: an avenue arm's two cells beside the box get 11204 with the median nose (20910 nose E, 20911 nose W, placed
  in the cell's 11204 state, art = `avx.arm_frame`: white dashes). A boulevard arm's first column comes from that
  boulevard's own run (OUTER / NOSE, so its median nose and trees are the boulevard's).
- Art: `bvx.Box` = avenue_junctions' box (29's curb on a closed side, 43's corner where two arms meet, 43's own
  crosswalk lines within 40 units of an arm edge) with one change: the plain asphalt is a per-pixel palette of 43's own
  plain asphalt (lane units 72..184, all views). avx's mirror about the cell middle repeats a dark ring per cell, which
  reads as a quilt on a 2x3 or 3x3 box (first mockup). Mean luma kept at 43's (93; diagave_paint's road palette is 107).
- Package: new `examples/boulevard_junctions` (ids 20900..20905, 20910, 20911), manifest key
  `auto_boulevard_junctions` (the shape of `auto_avenue_junctions`, compiled by the same `compile_avx`), table lines
  `bvxb <piece> <NESW>` / `bvxa <piece> <1|3>`. Off switch `SC3NETMOD_BVX=0`.

## Offline

| Check | Result |
|---|---|
| `bvx.py check --tiler`: 5 kinds (BxA, AvT, BvT, BxB, BbT) x 4 rotations through `boulevard.runs()` | 20 / 20 convert; each rotation equals rotation 0 turned (MIDDLE / NOSE2 compared mod 2, IIII any state); 0 clashes between the two runs of a BxB / BbT box |
| AVX (`avx.find`) on the road sets and on the stock tiles | no junction in any of the 20 drawings |
| RBT twin (`rb_auto.check`) on the stock tiles | no block |
| bigrbt twin (`Simcity_wt_bigrbt` `bigrbt.check`, read-only) | no block in any of the 20 drawings (a boulevard side has 3 arm cells: its own refusal) |
| `runs()` regression, 36 road sets (crossing + T, staggered T's, tapers, avenue narrowing, 4-wide, 30 random) | only runs that were refused before change: one previously refused avenue crossing now converts, the others are still refused with a more precise reason |
| boulevard round-2 avenue layout | 39 cells wanted, as before |
| `netpack.py validate` + JSON schema | ok |

## Game (pid 43176, then 38800 after reload)

| Step | Result (sc3netmod.log) |
|---|---|
| table read | 6 `bvx: ... box piece` lines, 2 `avenue arm piece` lines, no `###` errors |
| patch 1: boulevard x 101..115 rows 96..98, avenue x 105 / 106 (z 91..103), avenue x 111 / 112 (z 91..95) | grid: box 20900.0 20900.1 / 20903.1 20903.3 / 20900.3 20900.2 at 105..106 with noses 20910.1 20911.3 above and 20911.1 20910.3 below; T box 20900.0 20900.1 / 20903.1 20903.3 / 20902.0 20901.0 at 111..112; boulevard noses 20702 next to both boxes. Equal to the twin |
| patch 2: boulevard x 11..23 rows 49..51, boulevard x 16..18 (z 44..56) | `axis 0, columns 11..23 ... 39 cell(s)` and `axis 1, columns 44..56 ... 39 cell(s), 39 written`; 3x3 box 20900 / 20903 / 20905 corners, sides, middle; both runs agree |
| demolish z 52..56 (x 16..18): boulevard T | `axis 1, columns 44..51 ... 24 cell(s)`; far row 20902.0 20904.0 20901.0 (closed S) |
| demolish x 107 (rows 96..98): boulevard 101..106 ends on the avenue | `columns 101..106 ... 22 cell(s)`: 20900.0 20901.3 / 20903.1 20904.3 / 20900.3 20902.3 + noses; the cut-off part 108..115 stays a boulevard with its avenue T (`columns 108..115, 26 cell(s)`) |
| screenshots | zoom 3 view 0 / 1, zoom 4 views 0, 1, 2: `bvx_sheet.png` |
| save (menu 0x10009002) | `save: 102 variant tile(s) written as base` |
| twin on the save (`bvx.junction_wants(road_of_save(lab2_saved.sc3))`) vs live grid | 102 / 102 equal, 0 mismatches (27 bvx cells) |
| reload (`lab3.sc3` = the save) | `load: all 102 variant tiles restored`; AVX and all four BV load passes `0 written` |

0 exceptions in both logs (`inst_bvx/sc3netmod_run1.log`, `_run2.log`). Both games stopped by PID. One zoom 4 view 1
frame came out half drawn right after a failed camera call (`rb_lab cam`); retaken after a fresh camera call, clean.

## TrBlkAtt

boulevard_junctions takes 23 slots per language: 20900 / 20903 / 20905 copy 43's record (1 each), 20901 / 20902 /
20904 carry a T 39 state 1 spec (4 each), 20910 / 20911 copy 11204's records (4 each). With the four packages
installed the index holds 932 records per language (862 stock).

## Open

- Owner call: box asphalt as a per-pixel 43 palette (uniform, a little grainy at zoom 4) or avx's mirror (quilt). If
  the palette is kept, `avx.Box` could take the same one-line change so all boxes match.
- The boulevard's front median trees stand up to the crosswalk (the same open point as avx's nose cells).
- Not handled (stay stock): a boulevard ending on a single road (a 1-wide span at a run end: two more patterns,
  ACIA and ICIA), an avenue or boulevard meeting the boulevard at a corner (L), junctions closer than one clean column.
- Lanes are copied / T 39 specs per box cell, cosmetic; not traced with cars (the lab city has no population).
