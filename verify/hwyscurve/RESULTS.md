# hwyscurve results (2026-10-29): highway S-curve over a one-cell offset

Owner request 2026-10-29: "i need this S curve for highways" (`MAIN\verify\hwyscurve\owner_report.png`). Tree
`dev\hwyscurve\tree` (release sc3mods-2026-10-29, main 584ab1f), mods from `dev\hwyscurve\inst`. Pictures:
`MAIN\verify\hwyscurve\owner_shots\` (not committed). Code: `re/harness/src/sc3netmod_hwsc.c` (block HWSC, off with
`SC3NETMOD_HWSC=0`), `re/tools/netmod/hwsc_build.py`, package `re/tools/netmod/examples/highway_scurve`.

## 1. The stock case

Lab: Roadless Paradise (flat land at height 82), highway drags with `hw_lab.py hway`, cells read with `rb_lab.py cells`.
sc3netmod wrote 0 cells in these passes (`hwy: ... cells written=0`), so every result below is the stock tiler's.

| layout | cells | stock result |
|---|---|---|
| owner's: band 1 rows z 89/90 to x 104, band 2 rows z 90/91 from x 103 (overlap 2) | (104,89), (103,90), (104,90), (103,91) | 15149.0, the owner's picture |
| overlap 3: rows z 155/156 to x 101, rows 156/157 from x 99 | (101,155), (99..101,156), (99,157) | 15149.0 |
| overlap 1: rows z 79/80 to x 103, rows 80/81 from x 105 | column x 104 | 11223.0 / 11224.0 / 11223.2, a stock one-column diagonal (left alone) |
| full width: rows z 83/84 and 85/86 side by side, overlap x 102..104 | 4 cells | 15149 + stray 73 pieces (another shape, out of scope by orchestrator call) |

The picture is the one-cell (half-band) shift. Cause (offline `netrules explain hwsc_lab.sc3 X Z --net HWAY`, verdict
"agrees with the save" on all 4 owner cells): no HWAY Simple or Complex rule matches the neighbour masks 0xdf, 0x7f,
0x36, 0xc9, so the final-pass fallbacks HWAY_GRND_final.txt #15 / #9 / #6 write 15149.0. The shared middle row would
carry band 1's -x carriageway and band 2's +x one in the same cells.

## 2. What was built

- Geometry: the whole two-cell deck shifts one cell sideways over the overlap as a straight, two opposite arcs and a
  straight: L 2 -> R 1.25 cells, 53.1 deg; L 3 -> R 2.5, 36.9 deg; L 4 -> R 4.25, 28.1 deg. Footprint = the overlap
  columns x 3 rows, all cells the player built and paid for (no land taken, no question, no charge).
- Pieces 28200..28253 (one per footprint cell; S and mirrored Z, L 2..4: 6 + 9 + 12 per hand), lit twins
  28300..28353 (written at odd turns, walls shaded like stock), base 15051, frame table 15127 + ground_under. Art
  painted at install time from the stock highway frames by hwpaint (nothing from the game in git).
- Lanes: hwlanes from the same scene, curve shapes 28400..28495, 4 lanes in and 4 out at each end on the stock lane
  positions (z 110 / 194 and 61 / 145 of the cell), every cut lane continues into the next cell (offline check),
  nearest two nodes on one border 84 units (the stock pair spacing; the street sim buckets by 72). 8 corner cells the
  deck only grazes carry no lane and an empty turn matrix.
- Saves: each cell saves as what the stock tiler leaves there (15149.0 on the shared row and at the two band ends,
  the plain straight elsewhere), so a game without the mod loads the stock layout. With the mod the variant section
  restores the S.
- Rule (sc3netmod_hwsc.c header): footprint all highway (15149 / axis straight / HWSC piece) on flat ground, lead-ins
  the plain stock straights at stock states, no highway beside it (third row past each end, rows outside), nothing
  claimed by another block. Every pass including the city load, so an existing city's staircase is healed on load.

## 3. In game (dev\hwyscurve\tree, all mods, sim running, posted input only)

| case | result | evidence |
|---|---|---|
| owner's layout (S2, along x) and the overlap-3 staircase, loaded from the lab save | **met.** The load pass built both: `hwsc: load: S-curve S2 at (103,89) turn 0: 6 cells written`, `S3 at (99,155) turn 0: 9 cells written`. The full-width case next to it stayed stock | `after_owner_case_lab_z3.png` (before: `before_overlap2_owner_case.png`) |
| edit pass, along z, S3 (two drags) | **met.** Built on the drag's own retile: `hwsc: edit: S-curve S3 at (50,43) turn 1: 9 cells written`, cells hold the lit twins 28306..28314 at state 1, walls shaded like the stock highway | `after_zaxis_S3_lab.png` |
| edit pass, along z, mirrored Z4 (overlap 4) | **met.** `S-curve Z4 at (50,81) turn 1: 12 cells written` | `after_zaxis_Z4_lab.png` |
| router (SimTransit step rules over the turn matrices, `hwave_probe.py --walk`) | **met, 8 of 8 walks**: both directions of S2 (x), S3 (x), S3 (z), Z4 (z) leave the S on the far band's right carriageway, e.g. `(100,89) x+ ... (103,89) 28200 -> (104,89) 28203 z+ -> (104,90) 28204 -> (105,90) 15051.2 ...` | session log |
| cars cross the S (Seoul copy, pop 504k) | **met.** Bypass on the busy highway at z 75/76: a band on rows 76/77 over x 92..99, row 75 bulldozed at x 94..95 -> S2 at x 92..93 and Z4 at x 96..99, both built on the edit pass. Animated cars, 70 frames: a +x car through S2, the bypass and Z4 back onto row 75 (frames 17..31), a -x car the other way (50..66); cars found by differencing against the median frame on each cell | `seoul_bypass_car_plus_x.gif`, `seoul_bypass_car_minus_x.gif`, `seoul_bypass_overview_z3.png`, `seoul_bypass_z4.png` |
| save + reload | **met.** The save holds the stock layout cell for cell (15149 on the shared rows and band ends, 15051 elsewhere, read offline). Reload with the mod: `load: all 3185 variant tiles restored`, `hwsc S-curves built=0, kept=2` | `seoul_bypass_after_reload.png` |
| layout broken | **seen once (by accident).** A demolish click that took a whole column out of a built Z4 left no HWSC piece behind: the stock tiler's caps and straights came back | session log |

Not run: `SC3NETMOD_HWSC=0` in game, a game without the mod loading the save (the saved tiles were read offline and
are the stock ones), sloped ground and ramps next to the footprint (refused by the rule, offline reading only).

Lab traps: an elevated deck is drawn 4 altitude units up, so demolish clicks need `--alt <ground + 4>` or they hit
the neighbour cell; after a click the neighbouring art changes, so check the cells after every click.
`nb_drive.py remove` reported each removal but the cells read back unchanged (not chased). A drag of a highway with a
one-cell sideways offset builds a straight band (the tool keeps the first axis): the owner's layout takes two drags.
