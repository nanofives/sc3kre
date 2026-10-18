# Highway program integration (round/highways, 2026-10-18)

`round/highways` = main (d960b2c) + child/hwcore (1c60417) + child/hwt (35e5dea) + child/hwx (ff71859) +
child/hwdd (68609a9) + child/hwdx (5e6bc5f).

## Merges
Every conflict was two blocks adding lines at the same spot in `sc3netmod.c` (include) and `sc3netmod_rbt.c`
(prototypes, `hw?` table-line routing, `<block>_run(hp)` in `rb_hwy()`, stats). Resolved by keeping both sides
(scratch resolver that refuses any conflict line without a `task` tag). No logic clash: the blocks own disjoint
shapes (hwx = X with four continuing arms, hwt = T and the stub X, hwdd = diagonal x diagonal).
Combined DLL builds (292,864 bytes). `netpack validate`: 0 errors on all four packages; warnings are the expected
"no rule RESULT places" (pieces placed by the DLL), Collapse groups full (INHERIT maps at removal) and, on
highway_dd_cloverleaf only, lane-vs-matrix warnings under review by hwcore.

## Combined game check
Tree `Simcity_stock_highways` (hard links), packages hwt_trumpet + hwx_cloverleaf + highway_dd_cloverleaf (not the
proof package highway_core), DLL from this branch, lab city.
- Load: 175 variants, no `###` errors, `hwdd: on`.
- Straight X dragged (44..72 x 28, 58 x 14..42): `hwt` refused both anchors ("far arm continues: a full X (hwx)"),
  `hwx: cloverleaf at (58,28): 96 cells written`.
- T (through 95..115 x 86, stem 105 x 99..88): `hwt: full T at anchor (105,86) turn 2 from the stem's end caps:
  50 cells written`.
- Diagonal x diagonal (121,9)-(141,29) and (141,9)-(121,29): `hwdd: built cloverleaf at frame (131,19)`, 108 cells.
- Save: 254 variant tiles written as base (= 96 + 50 + 108). Reload: 254 restored, every block `kept`, load pass
  0 written / 0 reverted, 0 exceptions.
Shots (not committed): `Simcity_stock_highways\re\harness\inst_highways\c_x1.png`, `c_t1.png`, `c_dd1.png`,
`c_reload_x_r1.png`.

## Four-package check (after hwdx)
- First run with all four packages: `### hwy: ... too many pieces` then `### hwdx: piece 21526 is not declared (hwyp) -
  HWDX off`. The base held 256 declared pieces; the four packages declare 347 (hwt 54, hwx 31, hwdd 90, hwdx 172).
  Only visible with every package installed. Fixed in hwcore 1c60417: 4096 pieces, id-indexed lookup, duplicate
  declarations logged.
- Re-run (fresh lab, DLL from 4f5f7f3): 347 variants, `hwdd: on`, `hwdx: on (120 classes)`. Diagonal x straight
  (42..74 x 28 and (42,14)-(68,40)): `hwdx: new crossing O (56,28) case A, quadrants A1 A2 O1 O2`, 154 cells. T: 50
  cells. Diagonal x diagonal: 108 cells. Save: 312 tiles as base. Reload: 312 restored, hwt / hwdd / hwdx kept, load
  pass 0 written / 0 reverted, no exceptions. (The cloverleaf X shared the first run: no free flat window left.)
- hwdd's lane-vs-matrix warnings: by design (hwcore review): hwdd's matrices come from its router-flow table so the
  second highway does not switch carriageways under the crossing; all 16 movements reach offline; animated cars follow
  the drawn lanes. Collapse "group full" warnings: harmless with the DLL (INHERIT maps variants at removal).

## Open
- Not measured anywhere: cars on the ramps (the lab city has no population).
- Known limitation: without the mod, ramp cells on open land load as stock ramp / slope pieces.
