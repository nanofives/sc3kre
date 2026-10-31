# Seaports and airports: how they work and what they change (portsre, 2026-10-30)

Owner request (2026-10-30): "how the seaport and airport logic works, to better understand their impact on the game".
Research only, no mod. Plain-language Spanish version for the owner: `verify/portsre/EXPLICACION.md`.

Evidence marks: `[CONFIRMED @ addr module]` = SC3U x86 decompilation, `[LIVE]` = read from a running game
(`verify/portsre/berlin_valves.txt`), `[DATA file]` = extracted game config (`re/data/syspak/`), `[iOS-HINT]` /
`[LINUX-HINT]` = named oracles (not authority), `[UNCERTAIN]` = open.

Ids used throughout: zone slot 14 = Airport, 15 = Seaport (`formats/CITY_SAVE.md`). Agent type 12310 = Airport,
12330 = Seaport, both children of 12002 Transportation `[DATA CitySim.ini:72-73, 346-347]`.

## Summary

- **Demand.** Commercial and industrial demand each have a ceiling set by how much of a "connection capacity"
  valve is used (5001 commercial, 8001 industrial). Ceiling = 2000 x (1 - used%). Every developed airport building
  cell adds 500 commercial / 100 industrial capacity, every seaport cell 250 industrial / 100 commercial. Neighbour
  road/rail/highway/subway connections add 7,000-25,000 each. Proven live in Berlin: commercial demand pinned at 860 =
  2000 x (1 - 57%) for 26 months (section 1).
- **Growth.** Zoning has no port-specific rule and costs $500 / $250 a cell. A port cell grows only with power,
  water service and transport within 6 cells. Seaports grow only around piers, and piers need 5 cells of open water
  beside the zone edge. Bigger zone = more pieces, never bigger pieces (section 2).
- **Side effects.** Airport: air pollution 100 per building with a 25-cell halo, residential land value -7. Seaport:
  water pollution 100 with a 10-cell halo, residential land value -7. Both produce garbage (section 3).
- **Traffic.** Airport cells are commercial trip destinations and seaport cells industrial ones. Planes (max 3 per
  runway group) and ships (max 1 per pier group) are animation (section 4).
- **Advisors / rewards.** Warnings fire above 75% capacity used. The Spaceport reward needs more than 50 airport
  buildings. A seaport enables garbage deals with neighbours that have no land route. No plane crash disaster exists,
  and there is no upkeep (section 5).

## 1. Demand: the airport and seaport raise the commercial and industrial demand CAPS

### 1.1 The valve model

RCI demand lives in "valves" (`cISC3Valve`, SIMRCI vtable `0x1004cc14`). Field map, every slot read from the PE and
its body `[CONFIRMED @ SIMRCI 0x10042dbe..0x10042e62]`:

| field | meaning | accessor (vtable slot) |
|---|---|---|
| `+0x08` | valve id | `+0x20` get / `+0x24` set |
| `+0x0c` / `+0x10` | last month's SUPPLY / DEMAND | `+0x28` / `+0x2c` |
| `+0x14` / `+0x18` | this month's supply / demand accumulators | `+0x40` AddToSupply / `+0x44` AddToDemand |
| `+0x1c` / `+0x20` | initial supply / demand (accumulators restart from these) | `+0x58` / `+0x5c` |
| `+0x24` / `+0x28` | max / min of the value | `+0x50` / `+0x54` (each clamps against the other) |
| `+0x2c` | the value (what the RCI bars show for 3000/5000/8000) | `+0x30` |
| `+0x34` / `+0x38` | economy / tax modifiers (float) | `+0x60..+0x6c` |
| `+0x3c` | CAP, byte, clamped to 100 | `+0x70` get / `+0x74` set |

Month end, valve `+0x78` `[CONFIRMED @ SIMRCI 0x10042e62]`: supply/demand := accumulators, accumulators := initial
values, then `+0x8c` recomputes the value `[CONFIRMED @ SIMRCI 0x10042e89]`:

```
raw     = clamp(demand - supply, min, max) + (economy/tax term, ftol)      ; clamp again to [min, max]
ceiling = max - cap * max / 100
value   = max(min(raw, ceiling), min)
if smoothing flag (+0x31): value moves toward that target by at most 7 * (max - min) / 100 per month
```

The 7% step is visible live: industrial 224 -> 504 -> 784 -> 1064 -> 1344, +280 a month = 7% of 4000 `[LIVE]`.
Same shape as iOS `goValve::EndOfMonth` 0x002b33b8 / `SetDemandCap` 0x002b30c0 `[iOS-HINT]`.

### 1.2 Who sets the cap

Two monthly functions, one per zone class `[CONFIRMED @ SIMRCI 0x1000ee50, 0x10016061]`:

```
cap% = 0                          if connection demand == 0
     = 100                        if connection supply < connection demand
     = 100 * demand / supply      otherwise (integer division)
```

- Commercial `0x1000ee50` (called by `0x1000efcd`, vtable `0x1004c290`): reads valve **5001**, sets the cap of **5000**.
- Industrial `0x10016061` (called by `0x1001625b`, vtable `0x1004c4e4`): reads valve **8001**, sets the cap of **8000**,
  then applies two ordinance cuts to industrial demand (`DAT_1005767c` / `DAT_10057678`, = `WaterConservationOrdEffect=3`
  / `PowerConservationOrdEffect=3` of `SC3IndLayer.ini`, ordinances `0x82b9999b` / `0x02bf1dfa`).
- Which valve object each function reads was proven live: `com 5000 <- 5001`, `ind 8000 <- 8001` `[LIVE]`.
  Same pair in iOS `goCommercialLayer::Simulate` 0x002b9060 / `goIndustrialLayer::EndOfMonth` 0x002b91a0 `[iOS-HINT]`.
- Valves 5000/5001 are created in `0x1000e842`: 5000 range [-2000, 2000], 5001 unbounded with initial supply
  `DAT_100574f8` = `InitialConnectionSupply=25000` `[CONFIRMED @ SIMRCI 0x1000e842; DATA SC3ComLayer.ini]`.
  Industrial `0x100159a5`: 8000 [-2000, 2000], 8001 initial supply `InitialConnectionSupply=70000` `[DATA SC3IndLayer.ini]`.
- Residential has the same mechanism on 3000 from 3001 (parks, landmarks, rewards supply 3001): live cap 43 =
  100*790880/1804750 `[LIVE]`. Not port-related, listed so the three bars read the same way.

So the cap is a **usage ratio**, not a population threshold. Every developed commercial building consumes 5001 and
every industrial building consumes 8001. The more of that "connection capacity" is used, the lower the ceiling of
the demand bar. At 100% used, the ceiling is 0: commercial (or industrial) demand cannot be positive.

### 1.3 Who supplies 5001 / 8001

`SC3ValveLayer.ini` `[DATA]`, format `valve:supply:demand` (record `+0xc` supply short, `+0xe` demand short):

| source | 5001 (commercial capacity) | 8001 (industrial capacity) | other |
|---|---:|---:|---|
| initial (always) | 25000 | 70000 | |
| Airport, per building cell (12310) | **+500** | +100 | demands 7000 x5 |
| Seaport, per building cell (12330) | +100 | **+250** | demands 7000 x5 |
| Spaceport, per cell (12350) | +30000 | +30000 | +30000 on 3001 |
| road neighbour connection | +12000 | +12000 | |
| rail neighbour connection | | +25000 | |
| highway neighbour connection | +10000 | +7000 | |
| subway neighbour connection | +25000 | | |
| commercial building, per cell | demands 18 (low) / 61-64 (medium) / 128-130 (high) | | |
| industrial building, per cell | | demands 17-20 (low) / 61-67 (medium) / 129-130 (high), 11 farms | |

How the rows are applied:

- **Per building, times its footprint.** `0x1002f5af` takes the occupant (`GZIID_cISC3Occupant 0xc14f8955`),
  multiplies vt`+0xd8` by vt`+0xd4` (the footprint, `QUERY_ID.md`), and calls AddToSupply / AddToDemand with
  `effect * footprint` for each row of the building's agent type `[CONFIRMED @ SIMRCI 0x1002f5af]`. The effect list for a
  type is cached by `0x1002f4ed` from the `AgentValveEffects` table `DAT_10058720` `[CONFIRMED @ SIMRCI 0x1002f4ed]`.
  Live in Berlin each month: 321 one-cell airport buildings adding (5001 +500, 8001 +100), 13 four-cell ones adding
  (+2000, +400), 174 one-cell seaport buildings (+100, +250), 19 four-cell ones (+400, +1000) `[LIVE]`.
- A building with a zone interface (`0xe0faadc7`) whose vt`+0x4c` is not 1 is skipped `[CONFIRMED @ 0x1002f5af]`
  (meaning of state 1 `[UNCERTAIN]`). Empty zoned cells have no occupant, so **zoning alone adds nothing**: only the
  port buildings that have grown count.
- **Neighbour connections.** Valve-layer month end walks `ConnectionValveEffects` (`DAT_10058710`) for index 0..3 =
  road, rail, highway, subway and multiplies each row by a count read from the neighbours layer (vt `+0xdc`, `+0xd8`,
  `+0xec`, `+0xf0`) `[CONFIRMED @ SIMRCI 0x1002efe8; layer identity GZCOM_INTERFACE_CATALOGUE.md 16a]`.
  Index-to-type follows the ini comments `[DATA]`; the count = number of connections of that type is the reading of
  the getter names in `16a` `[UNCERTAIN: getter bodies not read here]`.

### 1.4 Berlin, measured

`Berlin, Germany.sc3` (453 airport + 166 seaport zone cells), 26 months `[LIVE]`:

| valve | supply | demand | cap | value |
|---|---:|---:|---:|---:|
| 5001 commercial capacity | 1,078,500 | 613,363 | | |
| 5000 commercial demand | | | 57 | **860 = 2000 - 57%*2000, every month** |
| 8001 industrial capacity | 1,030,800 | 172,803 | | |
| 8000 industrial demand | | | 16-17 | 224..1344, below its ceiling 1660-1680 |

Port share of capacity, from the per-building counts above: airports 186,500 of 5001 (17%), seaports 25,000 (2%);
seaports 62,500 of 8001 (6%), airports 37,300 (4%). Berlin's commercial bar was pinned by the cap. Arithmetic on the
same numbers: without the airports, 5001 supply would be 892,000, cap 68, ceiling 640 instead of 860 (derived, not run).

### 1.5 Capacity scaling ("a bigger one")

Linear in developed footprint. One airport cell = 500 commercial capacity = enough for about 27 low-density or 4
high-density commercial cells (500/18, 500/130). One seaport cell = 250 industrial capacity = about 12 low-density
dirty or 2 high-density industrial cells (250/20, 250/130). One road neighbour connection (12000) equals 24 airport
cells of commercial capacity, one rail connection (25000) equals 100 seaport cells of industrial capacity (derived
from the `[DATA]` rows). There is no separate "has one" bonus: the first cell and the hundredth cell count the same.

## 2. Placement and development

Read with a delegated sub-agent (2026-10-30), spot-checked where marked. SIMRCI unless noted.

### 2.1 Placement: ordinary zoning, priced per cell

- Same CanZone / PlaceZone as every zone (`0x1003559f` / `0x1003591f`), no port-specific branch except the price
  `[CONFIRMED @ 0x1003559f]`. **No water-adjacency, minimum-size or slope rule at placement**, in line with
  `LAUNCH_CONTROL.md` 31.9.5/31.9.7, which withdrew the earlier "seaports need water" reading.
- Cost = unit price(category) x zonable cells (+ demolition): airport category 4 = `AirportZone=500`, seaport
  category 5 = `SeaportZone=250` per cell `[CONFIRMED @ 0x1003559f:191-201, SIMMISC 0x100053bb; DATA SC3BudgetLayer.ini]`.
  For scale: dense R/C/I zoning is 50 a cell, landfill 50.

### 2.2 The developers and their rules (`SC3ZoneLayer.ini` + parsers `0x10030c5b` / `0x10030d64`)

| zone | developer (ctor, vtable) | rules (class, Apply) | iOS name `[iOS-HINT]` |
|---|---|---|---|
| 14 Airport | `0x10004447`, `0x1004b234` | `0x81ffc3ce` Apply `0x1002b04c`; `0x2207d9ee` Apply `0x100032d1` | goRunwayDeveloperRule; goAirparkDeveloperRule |
| 15 Seaport | `0x1002c73f`, `0x1004ce20` | `0xc2d3fd7e` Apply `0x1002d27f`; `0xe2d3fd92` Apply `0x1002c12a` | goPierDeveloperRule; goDockyardDeveloperRule |

Dockyard tuning `SC3Tune [ZoneDeveloperRules] 0xe2d3fd92=1,7,5,35`: min dims 1, max 7 (clamped <= 10), 35% chance of
building list A `[CONFIRMED @ 0x1002bbf3]`; the iOS dockyard hard-codes the same 7 and 35 `[iOS-HINT 0x00363a68]`.
Transport distance 6 is set on every rule (`0x100046c5` -> `0x1000c23e`, `rule+0x30 = 6`) `[CONFIRMED]`.

### 2.3 What a cell needs to grow (UpdateCell)

Airport `0x10004784` (matches iOS `goAirportDeveloper::UpdateCell` 0x0035eb24), seaport `0x1002ca1f` (iOS 0x0036dc0c).
An empty zoned cell is refused, in this order, when `[CONFIRMED]`:

1. radioactive (pollution vt`+0x54`), return 10
2. not powered, return `0xe`
3. no transport within **6 cells** (zone vt`+0x6c(cell, 6)`, IsNearTransport `[iOS-HINT]`), return `0x10`
4. no water service (plumbing vt`+0x48`), return `0xf`
5. otherwise a buildable rect is grown and up to min(rules, 5) rules are tried at random (airport `0x10004966`,
   seaport `0x1002cc5b`); failure returns 9 (airport) / `0x11` (seaport).

So **both port zones need power, water service and a road/transport link within 6 cells** before anything appears.
What the reason codes show in the UI `[UNCERTAIN]`.

The seaport hands each rule a value from valve 8001 vt`+0x38` (`0x1002cc5b`, valve at `this+0x44` from `0x1002c941`).
Slot `+0x38` is `0x10042dda`, which returns `+0x24` = the valve MAX, and 8001's max is `0x7fffffff` (live). The
dockyard / airpark rules return 0 when that value is below 1 `[CONFIRMED @ 0x1002c12a, 0x100032d1]`, so for the
seaport this is a gate that **always passes**. The airport passes a fixed 2000. Neither port's growth depends on demand.

### 2.4 What gets built, and why bigger means more (not bigger buildings)

- Port layer (SIMGEOM, port interface vtable `0x1002a394`, slots match iOS `goPortLayer`): runway service bit `0x01`
  (`0x1001199a`), control-tower bit `0x02` (`0x100119d4`), pier service = bits `0x3c` non-zero (`0x10011a10`).
  AddPier `0x10011c71` marks +-8 cells sampled every 4 (counter, max 15 piers per sample); AddControlTower `0x10011bc4`
  marks +-4 `[CONFIRMED]`. Whether these radii are in cells or in coarser grid units `[UNCERTAIN]`.
- **Runway** `0x1002b04c`: rect at least 3x3 with one side >= 5; runway at most 10 cells, needs AddRunway `[CONFIRMED]`.
- **Airpark** `0x100032d1`: rect clamped to 10x10; tries the control tower first, else 55% a terminal strip, else a
  hangar, else a filler on a runway-served cell `[CONFIRMED]`.
- **Pier** `0x1002d27f`: along a zone edge, needs a run of >= 5 edge cells each with 5 cells of open, unoccupied
  water outward (terrain vt`+0x54`), run capped at 12; piers are 5 cells long `[CONFIRMED structure; terrain getters
  named only by iOS match]`. **This is where the seaport needs water**: without open water beside the zone, no pier,
  and the dockyard rule only builds on pier-served cells, so nothing else grows either.
- **Dockyard** `0x1002c12a`: only pier-served cells, rect clamped to 7x7, within transport distance 6 `[CONFIRMED]`.
- Size effect: a larger zone gives more seed rects, hence more runways, piers, towers, terminals and fillers. Every
  rule is capped (10x10, 7x7, 10-cell runway, 12-cell waterfront). No code picks a larger building type because the
  zone is larger. With section 1.3 this means: port effect = number of developed port building cells.

### 2.5 Decline

- Seaport, existing building `[CONFIRMED @ 0x1002ca1f]`: state 1 and no pier service -> re-placed with flag 2; state 2/4
  with water, power, transport, pier service and no radiation -> flag 1; state 2/4 missing any of these -> removed
  (building layer vt`+0x5c`) if removable. Whether flag 2 produces the "Abandoned Seaport" occupants 18092/18093
  `[UNCERTAIN]`.
- Airport: only the upgrade branch (flag 1) exists, **no abandon / remove branch in the airport developer**
  `[CONFIRMED @ 0x10004784]`. Other paths (disasters, generic building layer) not checked.

## 3. Environment: pollution, land value, desirability (aura), crime, water

All rows below are per building of the agent type, `[DATA re/data/syspak/<file>]`. A port zone holds many buildings
(Berlin: 334 airport and 193 seaport buildings, section 1.3), so each row is paid many times over.

### 3.1 Pollution `SC3Pollution.ini [AgentIDModifiers]`

| type | air amount : radius | water amount : radius | garbage |
|---|---|---|---:|
| Airport 12310 | **100 : 25** | 50 : 10 | 48 |
| Seaport 12330 | 50 : 15 | **100 : 10** | 32 |
| for scale: Train Station 12230 | 100 : 10 | 90 : 5 | 60 |
| for scale: Coal Power Plant 12111 | 5000 : 25 | 3000 : 12 | 50 |

Format `"%d:%d,%d:%d,%d"` (string at SIMECO `0x100204fc`), parsed by `0x1000564a` into two signed amounts, two byte
radii and one garbage value `[CONFIRMED @ SIMECO 0x1000564a]`. Which pair is air and which is water:

- The stamp `0x100095e7` adds pair 1 to grid `this+0x58`, pair 2 to grid `this+0x74`, field 5 to grid `this+0x128`
  (clamped >= 0) `[CONFIRMED @ SIMECO 0x100095e7]`.
- The pollution tick `0x10008249` reads grid `+0x58` into the value it hands to vt`+0x98` = the air setter
  `0x10008ffd` (writes bits 15..29 of the packed cell, read back by the air getter `0x10008ddd`, tested against
  `AirPollutedThreshold` by `0x10008e67`), and grid `+0x74` into vt`+0x9c` = the water setter `0x100090aa` (bits 0..14)
  `[CONFIRMED @ SIMECO 0x10008249:162-163,186-187,367-396]`. Traffic adds to the air value in the same tick
  (`TrafficAirFactor`, cut by the smog ordinance) `[CONFIRMED @ 0x10008249:252-254]`. Field 5 is garbage: getter
  `0x10008e3a` reads `+0x128 & 0x7fff` `[CONFIRMED]`. Same packing as iOS `GetAirValue` (`>>15`) / `GetWaterValue`
  (`&0x7fff`) `[iOS-HINT]`.
- Spread `[CONFIRMED @ SIMECO 0x100095e7]`: the amount is added to every cell of the building's own rectangle, then to
  each cell within `radius` of the rectangle with `amount * (radius - d + 1) / (radius + 1)`, `d` = longer axis
  distance + half the shorter one. On removal (`param_1 == 1`) the same values are subtracted.

So an airport is mainly an **air** polluter with a wide halo (25 cells), a seaport mainly a **water** polluter with a
10-cell halo. Both produce garbage.

### 3.2 Land value `SC3LandValue.ini`

`12310=-7:R,4:C,2:I` (Airport), `12330=-7:R,2:C,4:I` (Seaport) `[DATA SC3LandValue.ini:82-83]`. Signed deltas per
zone class: residential land value goes DOWN 7 near either port, commercial goes up 4 near an airport, industrial up 4
near a seaport. Radius of the effect is not in the row `[UNCERTAIN: land-value stamp not read]`. Air and water
pollution also lower land value through `AirPolluteFactor=400,-7000,250` / `WaterPolluteFactor=100,-9000,100`
(meaning of the three numbers `[UNCERTAIN]`).

### 3.3 Desirability / aura `SC3Aura.ini`

`12310=0,-2`, `12330=0,-2` `[DATA SC3Aura.ini:40-41]`. Same pair as dirty high-density industry `8500=0,-3` and the
bus station `4,-1`. Field order not decoded `[UNCERTAIN]`: across the table the first number is always >= 0 and the
second is signed, which reads as (radius, effect) but the parser was not read.

### 3.4 Crime `SC3Crime.ini`

`12310=3,4      Airport (zone)`, `12330=3,4      Seaport (zone)` `[DATA SC3Crime.ini:37-38]`. For comparison: bus
station `3,15`, train station `3,20`, military base `20,20`, high-density commercial `6,4`. Field meaning not decoded
`[UNCERTAIN]`. (A `buildingId -> {radius, signed effect}` loader exists at SIMSERV `0x1000689e`, `SIMSERV_CLUSTER1.md`,
but which of police / crime it serves is itself open there.)

### 3.5 Water use `SC3WaterLayer.ini`

`12310=8     Airport Puzzle Zone`, `12330=6     Seaport Puzzle Zone` `[DATA SC3WaterLayer.ini:68-69]`, against 2 for a
low-density home. Units / per-cell vs per-building `[UNCERTAIN]`.

## 4. Traffic, vehicles, neighbour links

Read with a delegated sub-agent (2026-10-30); the classifier was spot-checked.

### 4.1 Trips (SimTransit)

- `0x1000532c` (`cSTTrafficLayer::GetGenericBuildingType` `[LINUX-HINT]`) walks the agent-type chain: 3000 -> kind 0
  (residential); 5000, 10000, 18000, **0x3016 Airport**, 0x303e Spaceport -> kind 1 (commercial); 8000, **0x302a
  Seaport** -> kind 2 (industrial); 13000, 19000, 11000, 1001, 0x2f45, 0x2ee5 -> kind 3 `[CONFIRMED @ SimTransit 0x1000532c]`.
- `0x1000559e` stamps each occupant into the destination grid of its kind with the kind's radius
  (`STTraffic.ini` `TripMaxDistanceToRoadRes=4 / Com=3 / Ind=5`), and the trip arrival test `0x10008a94` stops on
  those cells (`CAR_TRIPS.md` 3.1) `[CONFIRMED @ SimTransit 0x1000559e]`.
- So **an airport cell is a commercial trip destination and a seaport cell an industrial one**, with the same
  radius as any C or I building. No port-specific weight was found. Whether port buildings also originate trips
  (issuer filter `0x100097b9`) `[UNCERTAIN]`.
- Development needs a transport occupant within 6 cells (2.3) but no code reads traffic or congestion for ports.

### 4.2 Planes and ships (STRTSIM, animation)

- Planes: one manager per runway group (tiles in the same row/column within +-12 cells, `0x10014171` / `0x10003317`).
  Attribute `AIRTRMGR.IXF` inst 1 = `3,4,75,77,78,79`: **at most 3 planes per runway group**, art ids 75/77/78/79.
  Runway at least 4 long (`0x10003376`). Initial parked planes `random(1, runwayLen/3)` (`0x10003a3b`). First arrival
  after 10,000,000 time units, then every 20,000,000..40,000,000 (`0x10003cc2`) `[CONFIRMED @ STRTSIM]`.
- Ships: one producer per pier group (+-10 cells, `0x10013d8c`), needs a seaport path of >= 10 cells
  (`0x1000fece`), **at most 1 ship per pier group at a time**, a new one every 120M..360M units (`0x1000fe62`,
  `0x10010211`). The ship art set (`VCLPROD.IXF` 1020..1023, vehicles 69/70/71) depends on two bits: a neighbour
  deal of type 4/5 exists, and a Military Base exists (`0x1000fcf0`) `[CONFIRMED @ STRTSIM; IXF decode by sub-agent]`.
- No reader of plane or ship counts in any sim layer was found: **they are visual only** as far as traced
  (exhaustive negative not claimed).

### 4.3 Neighbours

- Neighbour record (stride 0x54) has road / rail / water / power / highway / subway connection fields, no air or sea
  connection `[CONFIRMED offsets @ SIMMISC 0x1001698a..0x10016a6f]`. `[ConnectionValveEffects]` lists only road, rail,
  highway, subway.
- `ConnectionsExistForDeal` `0x10017b64`: deal types 4/5 need a Seaport (building count of 0x302a > 0) when the
  neighbour is not a land neighbour, or is a land neighbour with no road, rail or highway link; types 0/1 need a
  power link, 2/3 a water link `[CONFIRMED @ SIMMISC 0x10017b64]`. By the order of `NeighborDeals.ini`, 4/5 are the
  garbage deals `[UNCERTAIN: no name string tied to the enum]`. **So a seaport is what lets a city with no land
  route to a neighbour make that kind of deal.**

### 4.4 Noise

No noise layer, flight-path effect or airport noise stamp was found. `SC3Aura.ini` `NoiseFactor=0`. The airport's
nuisance is its air pollution halo (3.1) and the residential land-value -7 (3.2).

## 5. Advisors, petitioners, news, rewards, ordinances, budget, disasters

Read with a delegated sub-agent (2026-10-30); the cap byte and the spaceport test were spot-checked. SIMADV unless
noted. Text from `re/data/ixf_text.csv` (its `ENGLISH` column holds the Spanish strings, `English-UK` the English).

### 5.1 The "needs airport / seaport" warnings read the cap

The City Planner compares `COMMERCIAL_CAP_PROBLEM=75` / `INDUSTRIAL_CAP_PROBLEM=75` (`Advisor-CityPlanner.ini:15-16`,
loader `0x10007989`) against a byte from the Com / Ind layer (`0x100094e7`). That byte is SIMRCI `0x1000e7bc` /
`0x10015922` = `(this+0x18 / +0x1c)->vt+0x70` = valve slot `0x10025cb6` = **the cap byte `+0x3c` of valve 5000 / 8000**
`[CONFIRMED; same object offsets as the cap setters 0x1000ee50 / 0x10016061]`. So the advisors speak when more than
75% of the commercial or industrial connection capacity is in use. Berlin sat at 57 / 16-17, under both.

Advice `0x10009ea8`:

| id | when (cap > 75 for the class) | text (EN / ES) |
|---|---|---|
| 43 | commercial, airport count >= 1, neighbour test, flag `+0x1a9` | "Commerce Needs Airport Expansion" / "Comercio necesita ampliación de aeropuerto" |
| 132 | commercial, airport count >= 1, flag `+0x1a9` | "Commerce Needs Connections" / "Comercio necesita conexiones" |
| 131 | commercial, no airport, flag `+0x1a8` | "Connections Needed For Commercial To Grow" (body suggests building an airport) |
| 130 | industrial, no rail, no seaport | "Industry Needs Connections" |
| 229 | industrial, rail < neighbour count | "Industry Railing For More Rail Lines" |
| 134 | industrial, seaport >= 1, neighbour count != 4 | "Industry Needs Bigger Seaport" / "Industria necesita un puerto mayor" |
| 226 | seaport zone tiles > 5 and undeveloped-reason sum > 5 | "Seaport Not Developing" / "El puerto no se desarrolla" |
| 98 | (Transportation `0x10017002`) airport zone present, no airport building | "Airport Not Developing" / "Aeropuerto no se desarrolla" |

Meaning of the neighbour tests and of flags `+0x1a8/+0x1a9` `[UNCERTAIN]`.

### 5.2 Year unlock

Airport tool: `AIRPORT_AVAILABLE=1930` (`Advisor-Transportation.ini:12`, loader `0x10015f9c` -> `+0xb4`). From that
year, each check has a 10% chance (`rand(100) < 10`) to unlock: advisor message 135 "Airport Available" / "Disponible
aeropuerto", and the Root\Zoning\Airport button `0x10003006` is enabled `[CONFIRMED @ 0x1001725d; reload 0x10017528]`.
**The seaport has no year gate** (its button `0x10003005` is never posted by SIMADV).

### 5.3 Petitioners and news

- Petitioner 27 "Commercial Needs Airport" / "El comercio necesita aeropuerto": no airport and commercial cap > 75.
- Petitioner 20 "Don't Expand Airport" / "No a la ampliación del aeropuerto": advice 43 or 132 active and commercial cap < 40.
  `[CONFIRMED @ 0x1000a8d7]`
- Ticker lines tied to the advice above: "Commerce Needs Airports For Cash To Fly In", "Chamber Of Commerce Wants Airport
  Proposal To Take Off", "Sims Awed By Aeroplane". Headlines 665-667 (airport plans / expansion / new seaport,
  `SC3TickerData.ini:353-355`) exist, but no code that posts them was found.

### 5.4 Rewards, deals, ordinances

- **Spaceport reward**: population and year from its `REWARD_BUILDINGS` row (`;350000;2050;150;1`, column order
  inferred) **and airport building count > `AIRPORT_NEEDED_FOR_SPACEPORT=50`** (strict) `[CONFIRMED @ 0x1000a324:96-103]`.
  The count is BuildingLayer vt`+0x60(12310)`; whether it counts buildings or cells `[UNCERTAIN]`. Then petitioner 150
  "Spaceport Wanted".
- **Theme park reward**: airport count > 5 and the Tourist Promotion ordinance (`0x62f6e7cf`) on `[CONFIRMED @ 0x1000a324:145]`.
- **Aerospace Tax Incentive ordinance** (`0x22f6e7f4`) is offered (10% per check) once there is >= 1 airport and the
  year is past `AEROSPACE_AVAILABLE_YEAR=1960` `[CONFIRMED @ SIMMISC 0x1001a153, 0x1001a057]`.
- **Garbage deals** (deal types 4/5, see 4.3): without a seaport, a neighbour with no land route cannot take a trash
  deal. Advisor 4 "Need Seaport For Trash Deal", 3 "Need Connection For Trash Deal" (`0x10005052`), 112 "Need Seaport To
  Ship Trash" (`0x10010b87`); SIMMISC `0x10018cd5` cancels such deals when the seaport is gone `[CONFIRMED]`.

### 5.5 Budget

$500 per airport zone cell, $250 per seaport zone cell, once, when zoning (2.1). `SC3BudgetLayer.ini` has no upkeep
row and no monthly airport/seaport income or cost was found. Their money effect is indirect: commerce and industry
that can grow because the cap is raised pay taxes.

### 5.6 Disasters

**There is no plane crash and no ship or port disaster in SC3U.** `[PlaneCrashDisaster]` is an empty section
(`SC3DisasterLayer.ini:85-89`), no SC3U module carries a plane-crash string, and the Make Disaster menu lists Fire,
Tornado, Earthquake, Riot, UFO, Toxic cloud, Whirlpool, Locusts, Space Debris (`MenuItem.INI:79-88`). The iOS enum
`kGZDISASTERID_PlaneCrash` has no manager class `[iOS-HINT]`. `SSAeroplane::DisasterFightingRoutineUpdateFn` is the
**dispatched firefighting plane** ("Plane Dispatch", `MenuItem.INI:79`), not a crash. Its link to the airport was
not traced `[UNCERTAIN]`.

## 6. Mod opportunities noticed (not built)

1. **Tune the caps by data, no code**: `SC3ValveLayer.ini` rows 12310 / 12330 (per-cell capacity) and
   `[ConnectionValveEffects]`, `InitialConnectionSupply` in `SC3ComLayer.ini` / `SC3IndLayer.ini`. A netpack-style
   override of these rows would make ports matter more or less.
2. **Show the caps**: a Ver datos panel or tooltip with "commercial capacity used 57%, industrial 16%" (valves
   5001/8001 supply and demand, cap bytes). Today the player only sees the advisor at > 75%. Fits the `dataview` stream.
3. **Plane crash disaster**: the section and enum exist but are empty, so a mod would have to supply the whole event.
4. **Seaport year gate / airport unlock**: `AIRPORT_AVAILABLE` is data. A mod could gate the seaport the same way.
5. **More planes / ships**: cap 3 planes per runway group (`AIRTRMGR.IXF` inst 1 first token) and 1 ship per pier
   group (`VCLPROD.IXF` float) are data. Visual only.

## 7. Open items

- Valve 7000 (every port building demands 5 per cell): a second valve class (SimTransit reads it with iid
  `0x2657bb3`), not recomputed by `0x10042e89`; meaning `[UNCERTAIN]`.
- Neighbour connection count getters (neighbours layer vt `+0xd8/+0xdc/+0xec/+0xf0`) not read; Berlin's 842,000
  commercial-capacity remainder was not split by connection type.
- Crime, aura, water row field meanings (3.3-3.5); land-value radius.
- Building states 1/2/4 and the Abandoned Seaport occupants; reason codes 9..0x11 in the UI.
- BuildingLayer vt`+0x60` unit (buildings vs cells) for the spaceport 50 and the advisor counts.
- Whether ports originate trips.
