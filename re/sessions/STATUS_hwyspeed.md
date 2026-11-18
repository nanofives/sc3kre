# STATUS hwyspeed (child of round 2026-11-18) - DONE, shipped default on (owner call), ready to commit

## goal
Simtropolis (Spamoidutout): "vehicles going faster on highways". Find where animated vehicles and the trip
simulation get their speed per network, measure, propose, implement. Owner 2026-11-18: ship as a mods page row,
ON by default, x1.5, curves and junction pieces stay stock.

## verdict + deciding RVA
- Animated cars move dt x lane speed per frame: STRTSIM `0x1001b940` (`fild dt; fmul [car+0x10c]`), dt = real-time
  microseconds. `+0x10c` comes from the lane path's speed getter `0x1001ddc8` (`fld [ecx+0x24]`), in two vtables only
  (slots `0x1002cf7c`, `0x1002cfe4`). path+0x24 = TrBlkAtt edge e3 x 2.22222e-09 (`0x1002066a`, `0x1002d264`).
  Car class max speed is read only by boats (`0x1000539f`). Following clamp: gap to the car ahead - 28 (`0x1001b6a3`).
- Stock data already makes straight highways faster: e3 95,999 / 110,000 vs road 64,000. Measured 0.827 / 0.947 vs
  0.525 cells/s = x1.58 / x1.80. Highway curves and junction pieces are 64,000 = road speed.
- Trip sim: no speed (per-step cost vs a length budget only, HIGHWAY_TRIPS.md). Not touched.

## built
- sc3simrun HWYSPEED: both getter slots -> `hws_speed`, lanes above e3 66,000 x 1.5. Default ON
  (`simrun.ini [hwyspeed] enabled=1 factor_pct=150 threshold=66000`), `SC3SIMRUN_HWYSPEED=0` turns it off, export
  `sc3simrun_hwyspeed(pct)` for run-time A/B.
- sc3resize MODTOGGLE row "Faster highway cars" / "Autos rápidos en autopista" (Features column, default-on type, env
  `SC3SIMRUN_HWYSPEED`). Feature rows 17 px apart (`MT_FEAT_DY`) and 4 px gap under them, so the SALTFIX city checkbox
  sits at local y 418, clear of Volver (436).
- `resize.mt_hwyspeed` in all 7 tables, `sc3lang.py check` clean.
Built in dev\hwyspeed (sc3simrun, sc3resize), compile clean.

## proven game-side vs static only
- Game-side: stock speeds (M1), A/B x1.0 / x1.5 in one game (M3: highway lanes exactly x1.50, roads unchanged,
  0 overlaps), GIF. Default on at start with no ini; row untick -> ini `[env] SC3SIMRUN_HWYSPEED=0` -> next start
  `HWYSPEED: off`; re-tick removes the key (M4). Picture `verify/hwyspeed/owner_shots/mods_page_row_es.jpg`.
- Static only: lane sweep (no train/subway lane above 66,000). Captions in de/fr/it/nl/sv not seen in game (all
  <= 26 characters, the Spanish 26 has about 38 px left).

## blocked on
Nothing.

## files owned
In the worktree `dev/hwyspeed/wt` (branch child/hwyspeed on main 4a394cc):
- re/harness/src/sc3simrun.c (HWYSPEED block, default on; harness .c may need `git add -f`)
- re/harness/src/sc3resize.c (row + MT_FEAT_DY 17 + 4 px gap)
- re/harness/lang/{de,en,es,fr,it,nl,sv}.txt (resize.mt_hwyspeed)
- re/tools/hwyspeed_probe.py (new)
Written in MAIN:
- re/analysis/VEHICLE_SPEED.md (new)
- verify/hwyspeed/RESULTS.md, verify/hwyspeed/owner_shots/{hwyspeed_before_after.gif, gif_spot_zoom4.png,
  mods_page_row_es.jpg}, verify/hwyspeed/data/{m1_stock_z3.json, ab1_z3.json, sweep66.txt, sac_cells.json, view_z3.png}
- re/sessions/STATUS_hwyspeed.md

## game-harness need
None left running. Every game PID I started (4972, 14856, 6780, 16008, 14644) was stopped by PID. BMP dumps deleted.

## asks of other sessions
None.
