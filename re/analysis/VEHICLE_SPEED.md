# Vehicle speed per network: animated cars and the trip sim (task hwyspeed, 2026-11-18)

Simtropolis request (Spamoidutout, 2026-11-17): "vehicles going faster on highways". This note says where speed lives
in each layer, what the stock data already does, and what the HWYSPEED switch changes. Measurements:
`verify/hwyspeed/RESULTS.md`. Probe: `re/tools/hwyspeed_probe.py`. Fix: sc3simrun HWYSPEED block.

## 1. Two layers, and only one of them has a speed

| layer | what moves | speed? | where |
|---|---|---|---|
| animated cars (STRTSIM street sim) | the sprites on screen | yes, per lane edge | sections 2-4 |
| trips (SimTransit route_trip) | nothing visible: a walk that deposits traffic density | no. Per-step cost only, checked against a length budget | section 5 |

The two are independent: cars never deposit traffic density, and density comes only from trips
(`STRTSIM.md` section 8, `NET_LANES.md` verdict table). So a faster animated car changes nothing in the simulation.

## 2. How a car moves (STRTSIM)

Per-frame chain (from `STRTSIM.md` section 8): SC3U heartbeat -> STRTSIM `sc3_vehicle_update_tick` `0x1001d2c0` ->
behaviour `vt+0x14c` = `0x10019ab0`, which calls the action handler for the car's current action code from table
`0x10033158` (filled by `0x1001d060`: code 0 `0x1001b340` MoveNStages, code 1 `0x1001b200`, code 2 `0x1001b900`).

- **MoveToPoint update `0x1001b900`** (action code 2): `+0x148 = 0`, then
  `fild qword [dt]; fmul dword [esi+0x10c]` at `0x1001b940` / `0x1001b944`, and the product goes to MoveDist
  `0x1001b680` as the distance to move this frame `[CONFIRMED @ 0x1001b900 disassembly]`.
  `[LINUX-HINT]` cSSVehicle::MoveToPointUpdateFn, same body (`(float)param_1 * *(float *)(this + 0x10c)`).
- **dt** is the heartbeat's real-time delta. Measured: 16,666..16,760 per frame at 61 fps = microseconds
  (`verify/hwyspeed/data/m1_stock_z3.json`, `dt_sum / ticks`). It does not follow game speed (`STRTSIM.md` section 8:
  cars move at the same rate paused and at every speed).
- **MoveDist `0x1001b680`**: if the car has a car ahead (`+0x104`), the gap is that car's `vt+0x14(+0x110, +0x118)`
  minus 0x1c (28 units). A gap of 0 or less stops the car this frame, else the distance is capped to the gap
  `[CONFIRMED @ 0x1001b691..0x1001b6f0]`. It adds the distance actually moved to `+0x148`. Position: `+0x0c` x,
  `+0x10` y, `+0x14` z, cell = value >> 8 (256 units per cell).
- **`+0x10c` (the car's speed)** is written from the current lane path's speed getter, path `vt+0x3c`, by:
  MoveAlongPath `0x1001b110` (action code 1), its twin `0x10019d50` (code 5), and appear-on-path `0x1001bc70`
  (`param_1[0x3d]`, param_1 = car + 0x18) `[CONFIRMED]`. `0x10007f9f` writes `+0xf4` of car + 0x18 (= car `+0x10c`)
  from the edge directly at placement `[CONFIRMED]`. `0x10001eca` writes the constant `0x1002a244` (0.000106) and
  `0x1001a440` / `0x1001b970` write arguments: those are other movers `[UNCERTAIN which]`.
- **Path speed getter `0x1001ddc8`** = `fld dword [ecx+0x24]; ret` `[CONFIRMED]`. It sits in exactly two vtables:
  forward path `0x1002cf40` (slot address `0x1002cf7c`, ctor `0x1001db50`) and backward path `0x1002cfa8`
  (slot `0x1002cfe4`, ctor `0x1001dd6e`). A scan of STRTSIM for the address finds no other reference. Both ctors copy
  `+0x24` from the lane edge `+0x18` (`*(param_5 + 0x18)`).
- **Edge speed**: the TrBlkAtt vehicle-graph deserializer `0x1002066a` reads the edge's 4th u32 (`e3`) and stores
  `e3 * 2.22222e-09` (float `0x3118b5b5` at `0x1002d264`) at edge `+0x18` `[CONFIRMED]`. Format: `NET_LANES.md` 2.1.
- **Car class speed**: cSSVehicleAttrib::MaxSpeed (`[LINUX-HINT]`, attrib `+0x18`) is read in the Windows build only
  by `0x1000539f` (boat init, `[LINUX-HINT]` cSSBoat::Init). Road vehicles take the lane's speed whatever their class.
  Trains were not traced `[UNCERTAIN]`. Rail and subway lanes are at most 64,000, so HWYSPEED does not touch them either way.

So, for a car: **cells per second = e3 x 2.22222e-09 x 1,000,000 / 256**, less the following clamp.
Road (e3 64,000) = 0.556 cells/s nominal.

## 3. Stock lane speeds (TrBlkAtt e3)

Survey of `Apps\Res\SSimData\ENGLISH\TRBLKATT.IXF`, every vehicle edge, by the network Set file the piece is in:

| network | node class | e3 (edges) |
|---|---|---|
| ROAD | car | 64,000 (1,060), 39,999 (16, pieces 15040/15041), 37,999 (8, 15042) |
| RAIL | train | 64,000 (368), 55,000 (64) |
| SUBW | subway | 64,000 (328) |
| HWAY | car | 110,000 (136), 95,999 (368), 94,000 (56), 79,999 (40), 74,999 (52), 70,000 (64), 65,000 (16), 64,000 (876), 60,000 (64), 49,999 (48) |
| ROAD+HWAY (crossings, on-ramps) | car | 64,000 road lanes, 95,999 highway lanes, 65,000 on-ramps 15138-15141 |

Per highway piece (state 0):

| piece kind | e3 | x road |
|---|---|---|
| straight highway 73, 15051, diagonal 11223/11224/15052/15106, tunnels 18027-18030 / 18088-18091, signs 15146-15148 | two lanes: 110,000 (node x = 61) and 95,999 (node x = 145), state 0 of piece 73 | 1.72 / 1.50 |
| highway bridges 16042-16045, rail crossing 16006/16007, 18031-18044 | 95,999 | 1.50 |
| 14094, 15099, 15150/15151, 18084/18085, interchange 15107/15109/15111/15113 | 94,000 / 95,999 | 1.47 / 1.50 |
| interchange ramps 15112/15114/15120/15122 | 79,999 | 1.25 |
| interchange / on-ramp curves 15119-15133 | 74,999 | 1.17 |
| grade change 15102/15103, bridge slope 16046/16054 | 70,000 | 1.09 |
| on-ramps 15134-15141 | 65,000 | 1.02 |
| **highway curves and junction pieces 14020-14023, 15001-15096, 15108/15110, 15152/15153, 16020-16034, 18086/18087** | **64,000** | **1.00** |
| bridge slope 15104/15105, 16047/16055 | 60,000 | 0.94 |
| highway ends 11235/11237, 14999, 15053/15054, 15059 | 49,999 | 0.78 |

So **stock already drives straight highways 1.50x / 1.72x faster than roads.** Curves and junction pieces drop to
road speed.

The netmod pieces follow the same scheme: the highway program packages (hwx, hwt, hwdx, hwdd, scurve) use 110,000 /
95,999 / 94,000 on main lanes and 74,999 on loops and ramps; avenues, boulevards and roundabouts use 64,000.
All 14 TrBlkAtt files (7 languages, base and overlay): **every lane above 66,000 is in a HWAY piece or a crossing of a
highway, and none is a train or subway lane** (`verify/hwyspeed/data/sweep66.txt`: 80,304 edges above 66,000, all
node class 0). Inside ROAD+HWAY crossings the lanes above 66,000 are the elevated highway lanes (95,999 at y = 1024)
and ramp lanes (74,999, y 0..512). Every road lane in them is 64,000.

## 4. Measured (Sacramento, zoom 3, sim running, 60 s, 113 cars)

| e3 | cells/s achieved | x road |
|---|---|---|
| 64,000 road (and highway curves) | 0.525 | 1.00 |
| 74,999 ramps | 0.628 | 1.20 |
| 95,999 highway | 0.827 | 1.58 |
| 110,000 highway | 0.947 | 1.80 |

Achieved = 94-99% of nominal (the following clamp). Two other movers on the same handler run at e3-equivalents
240,100 and 480,200 (2.1 and 4.1 cells/s). They do not take their speed from a lane edge `[UNCERTAIN which vehicles]`.

## 5. The trip sim has no speed

`HIGHWAY_TRIPS.md`: route_trip `FUN_100070d0` is a first-arrival walk. STTraffic.INI step costs (road 4 + d/25,
highway 2 + d/100) are only summed and compared against a 1,024-unit budget at `FUN_1000755e`'s entry. They never
rank one neighbour over another, and highway cost 2 -> 0 gave no measurable change in highway share. There is no
travel time or commute time per network in the trip layer. A "faster" highway there could only mean (a) a lower step
cost = longer reach before a trip fails, measured as no clear effect, or (b) a destination-aware routing rewrite where
cost ranks choices. Both change trip outcomes and need the orchestrator's OK. Neither is built.

## 6. What "faster on highways" can mean

| option | layer | what the player sees | what it changes in the sim | size |
|---|---|---|---|---|
| A. HWYSPEED (built, on by default, owner 2026-11-18) | animated cars | cars on highway lanes and ramps x factor (default 1.5): 0.83 / 0.95 -> 1.24 / 1.42 cells/s | nothing | 2 vtable slots in sc3simrun |
| A2. also highway curves | animated cars | no slow-down on the 64,000 curve and junction pieces | nothing | lane data: rewrite those records' e3 (lanekit) or identify the piece at path take. Not built |
| B. lower highway step cost | trips | nothing directly | longer trip reach on highways. Measured: no clear share change | INI value (netpack `ini`) |
| C. destination-aware routing | trips | more cars on highways (density, the traffic overlay) | trip choice, highway share, congestion | route_trip rewrite. Large |

## 7. HWYSPEED (sc3simrun)

Both path-speed vtable slots (`0x1002cf7c`, `0x1002cfe4`) point at `hws_speed`, which returns `path+0x24 x factor`
when the stored speed is above `threshold x 2.22222e-09`, else the stock value. Arming checks the e3 constant
(`0x3118b5b5` at `0x1002d264`), the getter bytes (`d9 41 24 c3`) and that both slots hold the getter. Otherwise it
logs and does nothing.

- Config: `simrun.ini` `[hwyspeed] enabled=1 factor_pct=150 threshold=66000`. Env `SC3SIMRUN_HWYSPEED=1/0`,
  `SC3SIMRUN_HWYSPEED_PCT=n` (25..400). On by default (owner 2026-11-18). Mods page row "Faster highway cars"
  (sc3resize MODTOGGLE, writes `[env] SC3SIMRUN_HWYSPEED=0` when unticked).
- Off: the vtables are not touched.
- Run time: export `sc3simrun_hwyspeed(pct)` (returns the old pct, pct < 0 only reads). A car picks a new factor up
  when it takes its next lane path (one per piece crossed).
- Not covered: highway curves and junction pieces stored at 64,000 (option A2, owner: stay stock), and the two
  non-lane movers.
