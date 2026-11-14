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
| 26 A x B corner, 37 B x B corner | refused: `an end on a corner` | candidate built (BVCORNER, opt-in), pictures next | owner call |
| 63 four roads | refused: `road more than 3 wide` | options sheet `owner_shots/63_options.png` (A two avenues, B wide boulevard, C stock) | owner call |

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
`bv: boulevard ending in a corner box (orthfix BVCORNER) off (candidate, ...)`.
