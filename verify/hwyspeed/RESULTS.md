# hwyspeed results (2026-11-18)

Request (Simtropolis, Spamoidutout): "vehicles going faster on highways". Analysis: `re/analysis/VEHICLE_SPEED.md`.
Tree: `dev\hwyspeed\tree` (LAN 2026-11-18 stage), city Sacramento, CA, windowed 800x600, sim running, posted input and
Frida reads only. Probe: `re/tools/hwyspeed_probe.py` (hooks STRTSIM `0x1001b900`, the per-frame car move).

## Verdict

- **Stock already drives straight highways faster**: lane speed e3 95,999 / 110,000 against road 64,000 (TrBlkAtt,
  per lane edge). Measured 0.827 / 0.947 cells/s against 0.525 on roads = x1.58 / x1.80. Highway curves and junction
  pieces are stored at road speed (64,000).
- **The trip sim has no speed**, only a per-step cost checked against a length budget (`HIGHWAY_TRIPS.md`). Nothing
  there was changed.
- **Built: sc3simrun HWYSPEED, ON by default since the owner's call (2026-11-18, x1.5).** Animated cars on highway and
  ramp lanes (e3 above 66,000) x 1.5. Looks only: no trip, traffic density or routing change. Row "Faster highway
  cars" / "Autos rápidos en autopista" on the Turn mods on/off page. Highway curves and junction pieces stay stock.

## M1. Stock speeds (data/m1_stock_z3.json, zoom 3 on the straight highway at cells 150-158 x 133-134, 60 s, 113 cars)

| e3 | ticks | cars | cells/s achieved | % of nominal |
|---|---|---|---|---|
| 47,700 | 3,136 | 3 | 0.411 | 99.2 |
| 64,000 (road, highway curves) | 69,442 | 41 | 0.525 | 94.4 |
| 65,000 | 828 | 4 | 0.561 | 99.5 |
| 70,000 | 402 | 3 | 0.604 | 99.4 |
| 75,000 (ramps) | 1,150 | 8 | 0.628 | 96.4 |
| 80,000 | 826 | 9 | 0.683 | 98.3 |
| 96,000 (highway) | 11,256 | 24 | 0.827 | 99.2 |
| 110,000 (highway) | 5,749 | 15 | 0.947 | 99.1 |

dt per frame 16,666..16,760 (microseconds at 61 fps). Two other movers at e3-equivalent 240,100 / 480,200 (2.1 / 4.1
cells/s) do not come from lane edges and are not scaled by HWYSPEED (their speed is the same in A and B below).

## M2. Lane table sweep (data/sweep66.txt)

14 TrBlkAtt files (7 languages, base tree and netmod overlay): 80,304 vehicle edges above 66,000, **all node class 0
(cars)**, 0 train, 0 subway. Pieces: HWAY 676 (stock 68, highway_diagonal_cloverleaf 222, hwt_trumpet 108,
highway_dd_cloverleaf 108, highway_scurve 108, hwx_cloverleaf 48, highway_avenue 14), ROAD+HWAY 91 (diagonal_xnet 56,
boulevard 16, highway_avenue 10, avenue_lanes 4, avenue_diamond 3, stock 2), RAIL+HWAY 2, POWR+HWAY 2. No ROAD-only,
avenue-only, boulevard-only, roundabout, RAIL-only or SUBW piece has a lane above 66,000. Inside the ROAD+HWAY
crossings, the lanes above 66,000 are 95,999 at y = 1024 (elevated highway) and 74,999 at y 0..512 (ramps). All
1,672 road lanes there are 64,000.

## M3. A/B in one game (data/ab1_z3.json, same view as M1, SC3SIMRUN_HWYSPEED=1, factor set through the export, 10 s settle, 60 s blocks)

| block | factor | highway lanes cells/s | ramps | road 64,000 | car-ahead distance < 28 | car pairs < 16 (any lane) | jumps |
|---|---|---|---|---|---|---|---|
| A1 | 1.00 | 0.827 / 0.946 | 0.630 (75,000) | 0.477 | 0 of 17,948 | 0 (240 scans) | 33 of 105,400 |
| B1 | 1.50 | 1.237 / 1.419 | 0.921 (112,500) | 0.460 | 0 of 25,488 | 0 | 16 of 104,647 |
| A2 | 1.00 | 0.826 / 0.946 | 0.677 (80,000) | 0.545 | 0 of 7,064 | 0 | 11 of 95,424 |
| B2 | 1.50 | 1.234 / 1.413 | 1.024 (120,000) | 0.542 | 0 of 7,882 | 0 | 34 of 114,462 |

- Highway lanes x1.50 in both B blocks (1.237 / 0.827 = 1.50, 1.419 / 0.946 = 1.50). Road lanes, 47,700 lanes and the
  non-lane movers (240,100: 2.069 / 2.081 / 2.068 / 2.079) unchanged.
- Following clamp on highway lanes: capped on 2.3-2.9% of frames at x1.5, against 1.5-1.7% at x1.0. Achieved speed
  98.7-99.0% of nominal. **No car came within 28 units (centre to centre) of its car ahead, and no two cars on any
  lanes came within 16 units, in any block.** So cars entering or leaving a highway at x1.5 queue as at x1.0, with no
  overlap.
- "Jumps" (displacement above 3 steps + 8 units between two updates of the same car object): 800..9,000 units
  (3..35 cells), mostly on road lanes, at the same rate in A and B. The probe keys cars by object pointer and cannot
  tell a reused object from a moved car `[UNCERTAIN]`. They do not grow with the factor.
- Road 64,000 differs between blocks (0.46-0.55) because of road queues in view (clamped 15-18% of frames in blocks 1-2,
  3-4% in 3-4), not because of the factor.
- Logs: `### HWYSPEED: on, factor_pct=100 threshold=66000, 2 of 2 slots armed`. No VEH fault after arming (the one
  `0xC0000096` at SC3U+0x84122 at 59 ms is the game's own startup probe, before arming at 338 ms).

## Pictures (owner_shots/)

- `hwyspeed_before_after.gif` (784 KB, 480x614, 4 s loop at 15 fps from 60 fps in-process frame bursts): top x1.0
  (stock), bottom x1.5, same view, zoom 4, straight highway at cells ~180-192 x 51-52 with a road at the top left.
- `gif_spot_zoom4.png`: the GIF's view, one frame.

## M4. Shipped default + mods page row (owner call 2026-11-18, branch on main 4a394cc)

Default `[hwyspeed] enabled=1 factor_pct=150`; `SC3SIMRUN_HWYSPEED=0` (what the row writes) turns it off. Row in the
Features column of the Turn mods on/off page (sc3resize `k_mt_rows`, key `resize.mt_hwyspeed`, env
`SC3SIMRUN_HWYSPEED`, default-on row type like Siren fix). Text in 7 languages, `sc3lang.py check`: 348 keys in each
table, 0 missing, 0 unknown, 0 format mismatches, 0 outside cp1252.

Layout: 16 feature rows. At stylemix's 18 px the "Recalcular agua salada" city checkbox would land at local y 438, on
Volver (436). At 17 px with the old 8 px gap it sat at 422 and Volver's box clipped the bottom of its text (seen in
game). Now 17 px rows + a 4 px gap under them: checkbox at 418, clear of Volver (`owner_shots/mods_page_row_es.jpg`).

| step (dev tree, Sacramento, windowed, posted clicks only) | result |
|---|---|
| start, no ini, no env | `### HWYSPEED: on, factor_pct=150 threshold=66000, 2 of 2 slots armed` |
| Preferencias > Opciones de mods > Activar mods | row "Autos rápidos en autopista" last in Funciones, ticked |
| untick, OK | `MODTOGGLE> SC3SIMRUN_HWYSPEED off at the next start`, `sc3mods.ini` = `[env] SC3SIMRUN_HWYSPEED=0` |
| restart | sc3mods.log `[env] SC3SIMRUN_HWYSPEED=0 (sc3mods.ini)`, sc3simrun `### HWYSPEED: off (stock lane speeds ...)` |
| page again | row unticked (read from the ini); tick, OK: `SC3SIMRUN_HWYSPEED on at the next start`, key removed |

Caption widths: only Spanish seen in game (26 characters, about 38 px left in the 208 px column). The others are
19-26 characters (de 25, nl 26, sv 26 are 2-3 longer than their longest shipped feature caption, still no longer than
the Spanish one) `[not seen in game]`.

## Not done

- Highway curves and junction pieces at 64,000 still run at road speed (owner: stay stock).
- Trip-choice options (lower highway step cost, destination-aware routing): not built.
