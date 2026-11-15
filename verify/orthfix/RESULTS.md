# orthfix: the yellow orthogonal cases of the xsect sweep (2026-11-14)

Round `re/sessions/ROUND_2026-11-14b_junctions.md`, stream `orthfix`. Baseline: `verify/xsect/` (main 5f87c4f mods).
Mods: child/orthfix (from main bada3bc), tree `dev/orthfix/tree` with boulevard 0.4.0, avenue_ends (+22400),
boulevard_junctions (+22401..22420). Sandbox `xsect_sandbox_clear.sc3`, same driver (`verify/orthfix/sweep.py`, a copy
of xsect's with a `final` read-back command).

## Verdict

| case | before (xsect) | now | how |
|---|---|---|---|
| 67 B x rail | refused: the column beside the rail stays stock 11204/29/11204, 1-row crossing band two-way | **converts** (one run of 13 columns through the rail, 39 cells written, rail 44 intact) | BVXING |
| 71 B x highway | refused, same with 15098 | **converts** (one run through both 15098 rows, highway 15051 intact) | BVXING |
| 62 avenue into a road | refused: `no avlt piece ... outline CAIA modes CTOI` | **converts**: `ends: U-turn / U-turn with a road`, end cell 22400.3 + U-turn 21701.1 | avlt 22400 |
| 26 A x B corner, 37 B x B corner | refused: `an end on a corner` | **converts**: one paved corner box, square kerbed outer corner, every lane turns (owner 2026-11-14: "Square, as shown") | BVCORNER, boxes 22401..22420 |
| 63 four roads | refused: `road more than 3 wide` | **converts** to two one-way avenues side by side, kerbs back to back (owner picked option A of `owner_shots/63_options.png`) | BVQUAD |

Looks: the crossing cells of 67 / 71 keep the stock crossing art (yellow centre line on the three crossing cells), as
the avenue cases 66 / 70 do with AVL's twins. 62 ends in the paved box cell of avenue_ends 22001 (same outline, art
copied), the avenue carries the white dashes up to it.

## Regression, run1 (default config: BVXING on, 22400 installed, BVCORNER off)

`py -3.12 verify/orthfix/compare.py verify/orthfix/run1`: 77 cases built (78-80 are the on-ramp cases ramp.py drives,
not rebuilt), **68 identical** in build and final cells, 9 listed as changed:

- 62, 67, 71: the fixes above (build and final).
- 46: one cell (96,93) holds the DB end cap 21026.0 at the moment 46 is read, not in xsect's read; final cells are
  identical. Case 45 next to it had 3 builds with no reply in the xsect run, so the DB cell landed later there.
- 64: build identical; final differs (28 cells, the diagonal boulevard re-tiled as a diagonal avenue). The re-tile is
  case 76's build re-deciding 64's band through DAV (`dav: edit: band axis 0 from (63,117) kept: 6 touching road
  cell(s)`), and the xsect log has the same line at its case 76. xsect's final read was taken before it built 74-77, so
  its final cells for 64 predate that edit. DAV, not this stream (diagfix's stream 4).
- 74-77: build identical; xsect has no final read for them (built after its read).

Every case green before is still green. Pictures: `owner_shots/ba_<case>.png`, `owner_shots/ba_sheet_run1_*.png`
(before = xsect zoom 4, after = run1 zoom 4).

## Switches

`SC3NETMOD_BVXING=0` (crossings as before), `SC3NETMOD_BVCORNER=1` (corner candidate on). Start-log lines:
`bv: boulevard over a rail / power line / under a highway (orthfix BVXING) on, 12 twin(s)`,
`bv: boulevard ending in a corner box (orthfix BVCORNER) on`, `bv: four parallel roads as two avenues side by side (orthfix BVQUAD) on`.

## Regression, run4 (default config: BVXING, 22400, BVQUAD, BVCORNER all on; child/orthfix 668b298)

77 cases: **65 identical**, 12 listed as changed: the six fixes (26, 37, 62, 63, 67, 71) and the same five explained
in run1 (46 read timing, 64 DAV re-tile by case 76, 74-77 no xsect final read). Every B case (08-11, 23-25, 35-45),
every merge (57-65) and every other green case is identical in build and final cells. Pictures:
`owner_shots/ba_sheet_run4_1.png`, `_2.png` (64's "after" shows the DAV re-tile, not this stream).
run2 (corners as a candidate) and run3 (stopped when the owner approved the corners) are superseded by run4.

Switches: `SC3NETMOD_BVXING=0`, `SC3NETMOD_BVQUAD=0`, `SC3NETMOD_BVCORNER=0`.
Ship set: `dev/orthfix/ship/` (boulevard 0.4.0, boulevard_junctions with art 22401..22420, avenue_ends with art 22400;
install commands in `SHIP.md`).

## run10: BVBEND default on (child/orthfix c045eca on main 380dd35)

`SC3NETMOD_BVBEND=0` turns it off. 41 (DA) / 45 (DB): BV ends staggered before the band, DAV's / DBV's bend sets hold
the overlap, both draw orders give the same pieces (`owner_shots/ba_sheet_bend_41_45.png`, `bendon1/raw/R41_BxDA_L_rev_z4.png`,
`R45_BxDB_L_rev_z4.png`). run10 vs run9: 68 identical, 9 changed: 15 19 34 38 40 48 (diagfix 7-8), 41 45 (bend sets),
39 (see below). vs diagfix m10: 69 identical, the 8 listed are my own fixes absent from m10's tree (26 37 62 67 71),
42 / 44 (same as run9) and 53 (no m10 build read).

39 regressed: DAVBBEND reads the T as a boulevard end and writes 22370..22378 over the 22470..22487 opening box
(`owner_shots/ba_39_davbbend_regression.png`). Same in m10, so on main, not from BVBEND. Fix is in DAV's test.

## run11: DAVBBEND guard (child/orthfix ce64b18 on main c65b8f5, with c045eca)

vs run10: 74 identical; 39 back to the opening box (identical to run9); 42 / 44 = diagfix 9's boxes (identical to m10).
41 keeps its bend in both draw orders (`guard1/raw/R41_BxDA_L_rev_z4.png`). 39 with the diagonal drawn first
(`guard1/raw/R39_BxDA_T1_rev_z4.png`) stays the stock ladder + stock junction: DAV's bend-1 refusal (the boulevard is
not one-way yet in the main pass, the post-AVL pass checks avl_dir only), not from the guard. Picture `owner_shots/ba_39_guard.png`.
