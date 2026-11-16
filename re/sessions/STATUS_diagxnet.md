# STATUS diagxnet (round 2026-11-15b, cases 68 69 72 73)

## goal
Diagonal level crossing (DA 2+2 + median, DB 3+3) with the rail running through, and a diagonal underpass (highway deck
over the DA / DB lanes), placed by the DAVXNET block instead of the stock 69 / 15098 / 11258 it keeps today.
Ids 30000..30199.

## milestone 1: how the game makes these cells (static + stock data, 2026-11-15)

**Pieces.** Crossing matrix SIMNTWRK `0x100318ac` (u32[6][6], id<<8|state), read by `FUN_100167d4`
[CONFIRMED @ SIMNTWRK 0x100167d4]: road x rail = 69, road x highway = 11258 (highway piece 73's axis) and 15098 (highway
15051's axis). The state comes from the EXISTING piece's orientation (`vt+0xa0 -> +0x1c`): it swaps row / column of
the lookup. Result: 69 state 0 = road along x, rail along z; state 1 = turned (case 68: rail along x, 69.1 x 3).
11258 / 15098 only ever at states 0 and 2 = the two one-way deck halves (case 72: row 140 15098.2, row 141 15098.0).

**Sets / Protected.** 69 is in ROAD_GRND_Set + RAIL_GRND_Set and ROAD_GRND_Protected + RAIL_GRND_Protected; 15098 in
ROAD + HWAY Sets and ROAD_GRND_Protected; 11258 in ROAD + HWAY Protected. A netpack variant joins every Set and
Protected list that holds its base, and its Convert rows (`netpack_bridges.inherit_edits`, NETBRIDGE.md): so a variant
of 69 has the ROAD+RAIL class (the rail line is not cut), a variant of 15098 the ROAD+HWAY class, and the stock re-tiler
keeps both (Protected).

**Save.** A variant is saved as its base id at its own state, the variant id rides in section 0x4E56 (NETVARIANT.md
4). Without the mod the cell loads as the stock crossing. rb_save_id keeps the state, and 69 has a lane record for
state 0 only, 15098 for states 0 and 2. So **each variant is written at the stock crossing's own state** (69: 0/1 by
the rail's axis; 15098 / 11258: 0/2 by the deck half). No odd-state highway pieces, so no lit twins.

**Traffic and trains.**
- Road trips step by the 4-neighbour network flag grid (NET_LANES.md 3.2): only the ROAD class matters. Kept.
- Highway trips: SimTransit router `FUN_1000755e` reads the turn matrix prop 310 (low half) on highway nodes. 15098's
  310 = `0x20842180` holds the highway's one-way x turn plus the road's z turns. **The variant keeps the base's
  exemplar byte copy (prop 310 unchanged), the lanes spec must not override `connects`.**
- Rail trips: RAIL class (Set) + prop 311 for the tiler, both inherited from 69 unchanged.
- Animated vehicles (STRTSIM, TrBlkAtt): a new id needs its own records or cars / trains vanish on it. Record = the
  band cell's car lanes (its 35 halves, as diagfix's box pieces: `diagave.parts_spec`) + the base's other lanes:
  69's two train lanes (y 79) / 15098's four highway lanes (y 1024) at the matching state. Lanes carry a per-lane class,
  so one record mixes car and train (69 already does).

**What a new id must satisfy.** variant of 69 / 15098 / 11258 (inherits class, Protected, Convert, save), written at
the stock state, prop 310 / 311 as the base, lanes = band car lanes + base train / highway lanes, art = band scene with
the rail / deck composited (deck from the base's own frames at the same state, so walls light as stock).

**Id plan (42 of 30000..30199).** Per band cell role and mirror class (axis 0 vs axis 1 relative to the rail / deck):
rail DA 3 x 2 = 6, rail DB 4 x 2 = 8 (a quarter turn covers the other rail axis: 69 turns with its state); underpass
DA 3 x 2 mirrors x 2 bases = 12, DB 4 x 2 x 2 = 16 (state 2 vs 0 is the same cell set turned half a circle, so one id
per role serves both deck rows). No new curve shapes expected (lanes reuse stock curves).

**Code plan.** In the DAVXNET block (dav.c / dbv.c write loops): instead of skipping a kept crossing cell, look up
`davxn <base> <base state> <band piece> <band state> <piece>` (the band piece / state = what DAV / DBV would write
there, so mirrors and both rail axes are table lines) and write the variant at the base's state; no line = stock kept
as today. My variants count as kept crossings already (g_base = 69 / 15098 / 11258). Revert: a variant no band keeps
gets its base written back at its state (a stock retile keeps a Protected cell). Off: `SC3NETMOD_DAVXN=0` (one switch
per look: `SC3NETMOD_DAVXNRAIL`, `SC3NETMOD_DAVXNHWY`).

**Open (to check in game).** What the cell turns into when the band or the rail / highway is bulldozed (stock 69's
Convert rows are inherited, never traced: NETVARIANT.md 3).

## HANDOFF (2026-11-15 ~21:35, LIVING-PC reboot coordinator asked for a safe point)

Done: milestone 1 reported to the orchestrator. Milestone 2 (offline mocks) half done, nothing sent to the owner yet,
no game run, no code or worktree edits (dev/diagxnet/wt is still clean at 4b761ac).

Files (MAIN\verify\diagxnet\, untracked like verify/diagfix's scripts):
- `xm.py`: shared setup (this worktree's painter on sys.path, SC3_GAME_ROOT = stage\release, stage\src pack art
  index, renderer patches copied from verify/diagfix/mock_a.py, DiagBEl copied from verify/diagfix/mock_c.py, sheet()).
- `railx.py`: look 1, the rail crossing scene `RailX(Placed(DiagEl(18)) | Placed(DiagBEl(36)), m=123)`; carriageway =
  band pixels + stock 69 (state 1) track panels at the panel lz runs measured per (zoom, view) (`track_rows`; the stock
  frames place the tracks differently per view, 44 matches 69 per view); sidewalk / kerb / median / outside the band =
  stock rail 44 at STATE 0 (44.0 = rail along x, 69.1 = rail along x, from the xsect 68 grid); white stop lines on the
  approach side of each carriageway (right-hand: high p = x - z carriageway drives +q). `py -3.12 railx.py OUT.png da|db --v N`.
- `mock_railx_da_v2.png` (looks right in z4 v0, z4 v1, z3 v2: tracks run through the lanes, ballast across the median
  and sidewalks, stop lines), `mock_railx_db_v2.png` (rendered, NOT looked at yet). v1 = wrong (44 at state 1).
- `scratch/`: stock frame dumps (15098 / 15051 / 69 / 44) used to study the deck.

Next, in order:
1. Look at `mock_railx_db_v2.png` (crop the crossing, as done for DA) and fix what is off.
2. Look 2, the underpass (`underx.py`, not written): per cell, keep stock 15098 (11258 for 73-axis highways) layer 0
   and layer 1 (deck top) except the pixels where 15098 differs from solid 15051 (73 for 11258) = the open face; there,
   ray-march (ray at height e sits at (u0 - e/32, v0 + e/32) in tile units, e in zoom-3 px): through open deck cells
   (all band cells under the deck) to the ground = band scene colour x shadow factor (measure vs stock 29 under
   15098's opening), or into a solid 15051 neighbour's end face = interior wall colour (sample stock 15098's inner
   light wall by height). Deck rows in case 72: z 140 (15098.2) and 141 (15098.0), band DiagEl(c = -108) i.e. cells
   (32..34,140), (33..35,141); case 73 DB cells (50..53,140), (51..54,141), DiagBEl(-90).
3. Owner sheet: rail DA + DB, underpass DA + DB, before | after, send to the orchestrator for the owner call.
4. After the call: build script (ids 30000.., parts_spec lanes = band 35 halves + 69 train / 15098 highway lanes,
   connects NOT overridden, art relabelled to the stock state), `davxn` table lines + DAVXNET code (plan above), new
   package, in-game check (train crosses, highway traffic), 80-case regression both orders, ship dir + SHIP.md.

## milestone 2: offline mocks (2026-11-15, after the reboot) - WAITING ON THE OWNER CALL
Sheet: `verify/diagxnet/owner_shots/mock_sheet_v1.png` (68 69 72 73, today | mock, zoom 4 views 0 and 1).
- Rail (railx.py v3): tracks through the lanes (69's panels), ballast across the median and sidewalks (44), white stop
  line on each carriageway's approach side. DB fixed after the reboot (needs diagbv_paint.paint_cell's sampler swap).
  Sampler checked: painting stock 44 through it gives stock 44 pixel for pixel (anchors matched).
- Underpass (underx.py v3): stock deck, slab and outer walls kept; the view ray is marched down from the slab (the eye
  sees the first solid): ONE opening shaped like the band, abutment walls along the band's edges (drawn with the solid
  twin's end-face texture), road under the deck shaded x0.72. Known nit: tan slivers between wall pillars in view 3
  (the twin-pixel lookup misses there and falls back to the end face), to fix in the build.

## milestone 3: build (owner 2026-11-15 "Yes, build them", stop lines "Keep them"; outside lines approved)
- Package `re/tools/netmod/examples/diagonal_xnet` 0.1.0: 70 variants 30000..30069 (rail on 69: DA 3+3, DB 4+4; underpass
  on 15098 and 11258: DA 6+6, DB 8+8 each), 96 `davxn` lines. Art from `xnet_paint.py` (rail painted on the 69 frame: no
  1 px rim; underpass wall hits take the cell's own solid-twin pixel first: no slivers), lanes = band 35 halves + 69
  train / base deck lanes, no `connects` (base turn matrix kept). Build: `py -3.12 -m netmod.xnet_build <pack>` from
  re/tools (~10 min). Installed in dev/diagxnet/tree (its mods/netmod is now a copy of stage/src's; the linked release
  copy moved to dev/diagxnet/netmod_from_release).
- Code: `sc3netmod_davxn.c` (DAVXN), hooks in the DAVXNET block of dav.c / dbv.c, 4 lines in DAV's revert scan, stats,
  rbt.c dispatch; netpack `crossing_lines` + schema. Switches SC3NETMOD_DAVXNRAIL / SC3NETMOD_DAVXNHWY.
- Unverified in game until the regression: 11258 (highway along z) deck states (2 on the low column, 0 on the high one,
  predicted from the art) and rail along z (69.0) use: verify/diagxnet/xnet_lab.py builds those in free slots.

## milestone 4: FIXED (2026-11-16) - verify/diagxnet/RESULTS.md
- Sweep order (x1, 80 cases): only 68 69 72 73 80 changed, to the new pieces; no other case changed.
- Reverse orders: 39 41 45 53 identical, 50 52 54 55 / 49 as recorded for the staged build. 68..73 band first: rail /
  highway cut = stock limit (same with plain diagonal road 35), not a regression.
- All 10 extra orientations place variants (11258 states confirmed 2 low x / 0 high x). Train crosses 30000..30002.
  Sacramento: highway density constant through the underpass over 7 game years. Save + reload keeps all 9 cells.
  SC3NETMOD_DAVXNHWY=0 reverts the underpass on load.
- Ship: dev/diagxnet/ship/diagonal_xnet + dev/diagxnet/ship/SHIP.md (KEEP file in dev/diagxnet).

## milestone 5: DAVXHEAL (owner 2026-11-16 "Fix it") - committed child/diagxnet 5caeb96 (on main 5df3524)
- Cause: the rail / highway drag skips diagonal cells; FUN_100167d4 only takes straight road as the existing piece.
- Fix: after every rail / highway pass, a run interrupted by 1..4 diagonal cells gets the stock crossing, then DBV + DAV
  give the DAVXN variants. Plain diagonal roads fixed too. Off SC3NETMOD_DAVXHEAL=0. Call line in rb_pass (approved).
- Checks: verify/diagxnet/RESULTS.md section DAVXHEAL. Tree now holds every current pack (orthfix 11-15b set, diagfix 12
  diagonal_boulevard); its old netmod is in dev/diagxnet/netmod_backup_1116. No pack change for this fix.

## milestone 6: underpass wall wedge (owner review 2026-11-16, case 72 view 0) - diagonal_xnet 0.1.1
- Cause: the game draws 2-layer pieces' layer 0, then plain highway cells (15051 / 73), then every layer 1. The highway
  cell beside the band drew its end face over our layer-0 wall (measured: offline model of that order = the game shot).
- Fix: xnet_paint.paint_under_cell puts this cell's own deck / slab / wall pixels in layer 1 too (deck judged at e = 32,
  else 1 px seams). All 56 underpass ids rebuilt, rail ids byte-identical. In game 72 73 H1..H6 x 4 views clean (w3).
- verify/diagxnet/RESULTS.md section "Underpass wall wedge"; ship dir dev/diagxnet/ship/diagonal_xnet = 0.1.1
  (0.1.0 kept in dev/diagxnet/ship_prev_0.1.0); tree has 0.1.1 installed.

## built
package + code, all checks done (milestone 4)

## proven game-side vs static only
static only (decomp + stock data files + lanekit dumps)

## blocked on
nothing

## files owned
child/diagxnet worktree (uncommitted):
- re/harness/src/sc3netmod_davxn.c (NEW, ignored path: `git add -f`)
- re/harness/src/sc3netmod_dav.c (DAVXNET block + 4 revert-scan lines + stats), sc3netmod_dbv.c (DAVXNET block),
  sc3netmod_rbt.c (2 lines: prototype + `davxn` dispatch)
- re/tools/netmod/netpack.py (`crossing_lines`), re/tools/netmod/netpack.schema.json
- re/tools/netmod/xnet_paint.py, re/tools/netmod/xnet_build.py (NEW)
- re/tools/netmod/examples/diagonal_xnet/manifest.json, README.md, xn_30000..30069.lanes.json (NEW; art/ ignored)
MAIN (untracked unless noted): verify/diagxnet/RESULTS.md (tracked path), verify/diagxnet/*.py, owner_shots/,
x1 x2 x3 c1 runs; re/sessions/STATUS_diagxnet.md. Art: dev/diagxnet/ship/diagonal_xnet (+ SHIP.md).

## game-harness need
dev/diagxnet/tree only

## asks of other sessions
none
