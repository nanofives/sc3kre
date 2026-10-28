# relocate results (2026-10-28)

Spec and RVAs: `re/analysis/RELOCATE.md`. Tree `dev\relocate\tree`, mods from `dev\relocate\inst`, city Berlin.
Driving: posted input only (sc3io), camera through `netmod/nramp_cam.py`, pictures by `SC3RESIZE_FRAMEDUMP`.
Pictures: `MAIN\verify\relocate\owner_shots\` (not committed). Log lines from `inst\sc3resize.log`.

| case | result | evidence |
|---|---|---|
| A1 reward: Statue (type 14150, 1x1) at (161,126) moved to (157,122) | **PASS.** Button in the "?", tool with the statue's footprint, placed, original gone (probe: no occupant at 161,126; new 14150 at 157,122, zone 22). Free on that earlier build. | `A1_reward_*.png`, log `moved building (original) cells [161 126 161 126] removed`, `MOVE placement (kind 0) at (157, 122): placed` |
| A2 landmark: Brandenburg Gate (type 18010, 3x3) at (144,142) moved to (150,132) | **PASS.** Same sequence, old spot clean grass, gate among the trees by the Kongresshalle. | `A2_landmark_*.png` |
| B Police Station over an industrial block | **PASS.** 7 zoned buildings removed (one 2x2 partly outside the footprint removed whole), station placed, funds 119,728 -> 119,178 = $550 = $500 price + $50 bulldozing (per-tile $5 x footprints). A second placement removed 4 (one a 3x3 zone-11 tower) for $560. | `B_*.png`, log `zoned building under the footprint ... removed` x7, `building placement ... placed, price 550` |
| refused: Police Station over the first Police Station | **PASS.** Red cursor, no placement, nothing demolished, funds unchanged. | `C_refused_police_over_police.png` |
| refused: the gate's move tool over a road and the Berlin Wall | **PASS.** Red 3x3 cursor, every check "refused". | `C_refused_landmark_over_road_and_wall.png` |
| Escape after Mover (Mayor's House 10110) | **PASS.** Tool gone, house still at (225,184) (probe). | `D_mayor_after_mover_then_escape_unchanged.png` |
| layout | The Mayor's House dialog has the game's own "Sustituir" at the bottom left. First build overlapped it. Fixed: Mover goes one row up when its rect hits a control. | `D_mayor_dialog_mover_above_sustituir.png` |
| switches off (`SC3RESIZE_RELOCATE=0`, `SC3RESIZE_PLOPOVER=0`) | **PASS.** One "off" log line, no Mover, Copiar ID still there. | `E_switches_off_no_mover.png` |

## Cost policy (owner call 2026-10-28: bulldozing + levelling as the game charges them, plus 50% of the price)

A1/A2 above ran on the earlier free build. These ran on the final build, sim paused:

| move | logged parts | cursor label | funds |
|---|---|---|---|
| Mayor's House (10110, 2x2) onto 3 zoned houses | price 0, 50% 0, bulldoze 50 (original 20 + clearing 0 + zoned 30), levelling 0, total 50 | $50 | 117,006 -> 116,956 |
| Defense Contractor (11001, 5x5), in place (no other 5x5 spot in view) | price 25,000, 50% 12,500, bulldoze 125 (original 125), levelling 0, total 12,625 | $12,625 | 117,006 -> 104,381 |
| Prison (19004, business deal), in place | price 0, bulldoze 125, total 125 | | 104,381 -> 104,256 |

The cursor label equals what is withdrawn in every case. Levelling stayed 0 in these three (flat sites). The
levelling part is the remainder of the check's own total, so it is the game's number, but no sloped site was run.
Pictures: `F_mayor_cost_*.png`, `G_defense_contractor_*.png`.

Game prices read from the budget (vt+0x54): Lighthouse 5,000, National Park 10,000, Golf Course 25,000, Defense
Contractor 25,000, Medical Research / R&D / Stadium 75,000, Theme Park 125,000, Spaceport 250,000, Skating Rink 1,500.
All other rewards, every business deal and every landmark tried are 0.

## Business deal restart

Prison moved (in place): budget advisor deal list before = after: 19004 active, $250/month, monthly deal total $650.
Only the occupant pointer changed. The game ran on afterwards. Static read in `re/analysis/RELOCATE.md` section 3.

## Earlier notes

Stock costs measured with the stock CanPlace (`free 0`, price + clearing): Statue $5 on a cell with one tree (probe:
flora there), so its price is $0. Brandenburg Gate $40 and $45 at the four valid spots tried, price and tree clearing
not separated. Police Station $500 on cleared ground.

Bug found and fixed on the way: starting the tool inside the button click let the click's own button-up reach the new
tool, which ran Apply without a button-down and faulted (SIMGEOM `0x10021a84`, null tool+0x10). The tool now starts
250 ms later from a thread timer.

Not tested: right-click cancel, a sloped site (levelling charge),
the shoreline / plumbing / subway tool kinds, an undo (sc3undo) of a move or of a placement over zoned buildings, the
Rewards / Landmarks menus after a move (static: rewards keep no "built" state, landmarks end at placed=1).
