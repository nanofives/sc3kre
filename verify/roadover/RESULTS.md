# roadover results (2026-10-28)

Spec and RVAs: `re/analysis/ROADOVER.md`. Tree `dev\roadover\tree` (from release sc3mods-2026-10-28e), mods from
`dev\roadover\inst`, city Berlin, sim paused. Driving: posted input only (`re/tools/roadover_drive.py`), camera through
rb_lab / nramp_cam, pictures by `SC3RESIZE_FRAMEDUMP`. Cells and funds: `re/tools/roadover_probe.py`. Pictures:
`MAIN\verify\roadover\owner_shots\` (not committed).

Test line: x 139, z 144 -> 150. Cells 144..146 bare land, then three zoned buildings: (139,147) type 4100 zone 2 1x1,
(139..140,148..149) type 3900 zone 2 2x2, (139,150) type 4500 zone 3 1x1 = 6 tiles.

| case | result | evidence |
|---|---|---|
| S stock refuses (`-Stock`, no mod mapped but the inert loader) | **met.** Road / highway / rail / power predicates (`0x1001ad60`, `0x1001ae36`, `0x1001ade7`, `0x1001adaf`, the stock functions in their slots) return 0 on all three houses and on the civic building (141,145). Road returns 1 on the road piece (138,147). So the red drag is the stock rule, not a mod regression | `roadover_probe.py pred` output in the session log |
| A road over the zoned houses | **met.** Preview blue, label $100 = road 70 + bulldozing 30 (6 tiles x $5). Release: 3 buildings removed, road on all 7 cells, funds 117,006 -> 116,906 | `A_road_over_zoned_houses.png`, log `ROADOVER> road build over 3 zoned building(s) (3 removed), 7 cell point(s): built, network 70 + bulldozing 30; funds 117006 -> 116906` |
| A undo | **met.** sc3undo entry "road: 34 inserted, 30 removed, 4 zone cells, $100". Undo: the three houses back with the same types and rects, $100 refunded, funds 117,006 | `A4_undo.png`, `sc3undo.log` `UNDO> entry 1 (road): 68 op(s), 0 failed, $100 refunded` |
| R rail over the same houses | **met.** Same $100, 3 removed, rail pieces 44 on x 139 (ends 18000). Undone and refunded | `D_rail_over_zoned_houses.png` |
| B refused: civic building (type 14312, zone 22, 3x3 at 141..143, 144..146), road z 145 x 140 -> 143 | **met.** Civic cells red, building stays. The bare cell (140,145) is blue and builds, as the game does for any drag with some red cells | `B_civic_refused.png` |
| C switch off (`SC3RESIZE_PLOPOVER=0`, the checkbox off) | **met.** Predicates return 0 on the houses, preview red over them like the owner's picture, houses untouched | `C_switch_off_red.png` |
| P power line over the houses (picked from the HUD power flyout, posted clicks) | **met.** Preview blue, label $110 = line 35 + bulldozing 75. The power tool's drag ended one cell further (z 151), so it also took the 3x3 zone-3 building at 139..141, 151..153: 4 removed, charged once each (5 + 20 + 5 + 45). Funds 117,006 -> 116,896, undo restored all 4 and refunded $110 | `P1_power_preview.png`, log `ROADOVER> power line build over 4 zoned building(s) (4 removed)` |
| charge once per building | **met.** The 2x2 under 2 drag cells is charged $20 once (road case: 5 + 20 + 5 = 30). The 3x3 under 1 power-line cell is charged its full $45 once, what the bulldozer charges for it | logs above |
| E still refused for another reason: funds $80 < road 70 + bulldozing 30 | **met.** Label $100 in the game's red "can't afford" colour. On release the build hook refused (`ROADOVER> road build over 3 zoned building(s) refused: funds 80 < 70 + bulldozing 30`), nothing removed, nothing built, funds still $80. The game's own "no funds" message did not appear: its tool+0x39 flag did not stop Apply this time, the hook's own funds test did | `E1_funds_short.png` |
| sc3netmod coexistence | **met after a fix.** First build: in 2 launches sc3netmod skipped its CROSS wrap of the 3 predicates, in 1 ROADOVER stood down. Fixed (ROADOVER waits for sc3netmod and chains). Then `CROSS: wrapped FUN_1001ad60 / 1ade7 / 1ae36` at 234 ms and `ROADOVER> sc3netmod is loaded: it wrapped ... chaining` at 249 ms, in 3 launches out of 3 | `sc3netmod.log`, `sc3resize.log` |

Game behaviour seen on the way, the same with ROADOVER passing through (no zoned building on the drag, or PLOPOVER
off): a drag with red cells builds its blue cells and charges the price of the whole drag. Measured $40 for 1 built cell
of a 4-cell drag, $70 for 3 built cells of a 7-cell drag. Whether `-Stock` does the same was not run: posted drags
cannot be aimed in the stock window on this PC (2000x1500 physical client, white frame).

Power lines in stock (orchestrator question): the stock power predicate `0x1001adaf` accepts only flora and existing
power-line pieces. Called in the `-Stock` process it returned 0 on all three zoned houses and the civic building (case
S). So stock refuses a power line over a building. It never crossed one without demolishing. Power over bare zoned lots
is untouched (no occupant, no predicate call). Power stays in ROADOVER. Dropping it means removing the 4th entry of `pvt` / `tvt` /
`pfn` / `tfn` in ro_install and netType 3 in ro_build.

After the orchestrator's point (2), the collection counts only cells the selection layer marks 0x23 (valid), the same
test the stock build uses before building a point. A building under a cell refused for another reason (slope, water,
another occupant, a whole-drag refusal) is neither charged nor demolished. The funds case is above. The slope and
water cases were not run in game.

Not run: a highway built over zoned houses in game. It is hooked and its predicate was measured accepting the houses.
The highway on the test line was refused by the road at x 138 / the civic building beside it, as stock refuses them. A road built beside the road at x 138 became
sc3netmod avenue 11204 (cells read back), whose pieces did not draw in this dev tree. That is why the road picture shows
the houses gone but no road, and the rail picture was added.
