# DATAVIEW_PLAN: custom data views for data the game holds but never shows

Owner request 2026-10-30: "Add custom data views of things that are not shown today. Let's plan it."
Child `dataview`, round `re/sessions/ROUND_1030.md`. This is a plan, nothing is built. Static evidence only, nothing
measured in game yet.

Tags: `[CONFIRMED @ module 0xRVA]` = read in the decomp or the PE. `[GZ-HINT]` = name from the GZCOM header catalogue.
`[iOS-HINT]` = named iOS twin. `[SIZE-FIT]` = save section size scales with N, meaning not read. `[UNCERTAIN]` = open.

## 1. How Ver datos draws a map, and the hook a mod needs

### 1.1 Stock panels (SIMUI)

The dialog init `SIMUI 0x10044257` runs `0x10044430`, which builds 10 map panels via `0x1004458c` and then two
more pages (`0x1001f19b`, `0x1002f982`, by position the graphs/charts pages `[UNCERTAIN]`). Each panel init asks the
layer registry (iid 0x59a) for layer objects by id with `reg->vt+0x58(id)`, gives each a palette
(`inner->vt+0x18(reg->vt+0x48(paletteHash))`) and adds it to its map view with `view.iface(+0xa4)->vt+0x98(inner)`.
Every panel adds base terrain 0x2711 (SIMDIRT `0x1001127d`) first. `[CONFIRMED @ SIMUI init bodies below]`

| panel | init (SIMUI) | layer ids | registered by |
|---|---|---|---|
| Aura | `0x10047fcb` | 0x271c | SIMMISC `0x10004bf9` |
| Zonas | `0x100483e0` | 0x271b | SIMRCI `0x1003449b` |
| Densidad | `0x10049180` | 0x2724 | SIMRCI `0x100308dc` |
| Criminalidad (+ police coverage) | `0x10048c58` | 0x271d, 0x271e | SIMSERV `0x100091d4`, `0x1000ff83` |
| Incendios (+ fire coverage) | `0x100499aa` | 0x272c, 0x272d | SIMSERV `0x1000ce83`, `0x1000be18` |
| Valor del terreno | `0x10049ed2` | 0x2726 | SIMRCI `0x1001f5e5` |
| Energía | `0x10049595` | 0x2722 | SIMUTIL `0x10005ef3` |
| Agua | `0x1004b10e` | 0x2720 | SIMUTIL `0x10010456` |
| Tráfico y transporte | `0x1004acf9` | 0x2715 | SimTransit `0x1000b033` |
| Contaminación: aire / agua / basuras radios | `0x1004a2e7` | 0x2731 / 0x2732 / 0x2733 | SIMECO `0x1000c54a` |

There is no health, education, noise, desirability, age or trip map. The radio handler `SIMUI 0x10047ca0` hides
0x2731..3 (iface+0x8c) and shows the picked one (iface+0x84). That is the stock model for "several layers, one
panel".

### 1.2 The layer interface (iid 0x5dd), the only thing a new map needs

- Base class in SIMUTIL (QI `0x1001cbfa`, vtables `0x10020848`, `0x10022ae0`, `0x10024130`). Fields: +4 refcount,
  +8 id, +0xc palette, +0x10/+0x14 cell grid W/H, +0x18 byte.
- Render `+0x38` (`0x1001ccd6`) runs the per-texel loop `+0x4c` (`SIMUTIL 0x1001cd0f`): for each texel it maps to a
  cell `(cx, (H-1)-cy)` and calls **`+0x48 GetCellColour(cx, cy, &colour)`**. A true return paints the texel through
  `tex->vt+0xb8`. `[CONFIRMED @ SIMUTIL 0x1001cd0f]`
- Gradient layers read a value and index the palette. Example, air pollution `SIMECO 0x1000e3a3`: value =
  `grid->vt+0x58(cx,cy)`, clamped to `DAT_1002025c`, then `palette->vt+0x1c((palette->vt+0x14() - 1) * v / max, out)`.
  `[CONFIRMED @ SIMECO 0x1000e3a3]`. A new layer can reuse a stock palette by hash (e.g. 0xa30e2116, the
  traffic/pollution ramp) and gets the stock look for free.
- So **a new map layer = one heap object with a copy of SIMUTIL vt `0x10024130` (its +0x48 is a stub returning 0)
  and our own +0x48 reading any per-cell array.** SetId (+0x14) to an unused id (0x2740+), SetSize (+0x28) to the
  city cells, add it to a panel's view with `iface+0x98`, toggle with `+0x84`/`+0x8c`, set `view+0xdc = 1` to
  re-render. `[UNCERTAIN, untested]` but every step is a stock call the panels already make.
- Our mods need no change for this: VERDATOS clones the view and its wrappers share the inner layer (+8), VDRADIO
  copies the shown byte +0xc by that shared inner, `vd_tex` reads the cell count from inner+0x10. A layer built as
  above is drawn sharp in the scaled dialog automatically.

### 1.3 A layer the game builds and never shows: 0x2735 = RADIATION `[CONFIRMED 2026-10-30]`

**Resolved (built and measured, verify/dataview/RESULTS.md):** the factory hands the layer its owner, whose +0x1c is the
city's `cISC3PollutionLayer` (vt SIMECO `0x1001b984`); slot +0x54 is `IsRadioactive` (`0x10008db8`, bit 31 of the
pollution cell value). Set by `SetIsRadioactive` (slot 37, `0x10008f65`) from SIMDSTR `0x10007815` and SIMUTIL
`0x10009295`. Craterville: 0 cells (115 landfill cells, so it is not the landfill bit). The original note follows.

SIMECO's registration `0x1000c54a` registers **four** layers, 0x2731, 0x2732, 0x2733 **and 0x2735**. The factory
`0x1000e0e7` builds 0x2735 (vt `0x1001c060`) like the other three. Kind map `0x1000e0a0`: 1->0x2731, 2->0x2732,
3->0x2733, 5->0x2735, kind 4 has no layer. No SIMUI panel adds 0x2735 (grep over every module export: only SIMECO
and unrelated SIMNTWRK/GZWWWD constants). Its GetCellColour `SIMECO 0x1000e4cc` is a **yes/no mask**: it calls
`grid->vt+0x54(cell)` and, when true, paints one fixed colour `0x100187de(0xff,100,0)` (orange). Which per-cell flag
`vt+0x54` tests is `[UNCERTAIN]`. The pollution grid keeps an "active landfill" bit 0x8000 per cell
(catalogue §29c), which is the first thing to compare against. Showing it costs one `iface+0x98` call on the
pollution panel, no data RE.

## 2. Inventory: data held but not shown

Sources: three read-only sweeps over `CITY_SAVE.md`, `GZCOM_INTERFACE_CATALOGUE.md`, `CAR_TRIPS.md`,
`HIGHWAY_TRIPS.md`, `POWER_GRID.md`, `SIMUTIL_SIMTRANSIT.md`, the SIM* notes, `sc3perf.c`, plus the decomp checks
above. Runtime access: city object `*(*(SC3U 0x4fa86c)+0x48)`, subsystem pointers at city `+0x84..+0xfc`
(Power +0xb8, Plumbing +0xbc, Budget +0xc4, Pollution +0xd4, Crime +0xd8, Residential +0xe4, LandValue +0xf0,
Neighbors +0xf4, Weather +0xf8), traffic layer singleton `SimTransit DAT_1001fdb8`. `[CONFIRMED, sim_status.py,
catalogue §13c, sc3perf.c:946]`

Effort: S = one child-day once the layer kit (step 0) exists, M = 2-3 days, L = needs new RE first.

| # | data | where it lives | evidence | how to show | effort | risk | player gains |
|---|---|---|---|---|---|---|---|
| A | **Trip success per lot** (untried / ok / failed) | SimTransit layer 1-bit grids `+0x7c` tried, `+0x80` ok, writer `0x10006a72`, reader `0x10006965` returns 2/0/1 | CONFIRMED (sc3perf replaces the writer), iOS twin `GetTripSuccess` | new layer on Tráfico panel: green ok, red failed, clear untried | S after step 0 | low, read-only, data already used by sc3perf | sees which lots fail their commute, the hidden reason zones stall or abandon |
| B | **Layer 0x2735** (built, never shown) | SIMECO vt `0x1001c060`, +0x48 `0x1000e4cc` | CONFIRMED object, flag UNCERTAIN | 4th radio / toggle on Contaminación | S (cheapest item) | low; meaning must be measured before naming it | whatever Maxis cut, likely landfill / garbage-blocked cells |
| C | **Separate traffic grids**: road live, highway, subway, and the month snapshot vs live | SimTransit `+0x6c` road, `+0x70` highway, `+0x74` subway, snapshots `+0x60/+0x64/+0x68` | CONFIRMED (sc3perf `mt_congestion`); `transit_layer.py` names `+0x64/+0x70` "rail", conflict to settle | radios on Tráfico panel | S | low | tells highway and subway load apart from streets |
| D | **Garbage ledger + landfill capacity** | Pollution layer (city +0xd4) int64 totals `+0x154..+0x18b`: produced, imported, exported, recycled, incinerated, to-energy, landfilled; LastMonth slots 53-59; landfill capacity total/available, incinerator capacity | ledger CONFIRMED (catalogue §15b), capacities GZ-HINT | number list in the pollution panel (radio Basuras) or a text block | M (needs text drawing in the dialog; NATIVETEXT exists in sc3resize) | low | "how many years of landfill left", imports/exports per month. Overlaps stream **landfill** |
| E | **Power per plant**: current output, base capacity, build date, decline age, max life, overwork counter | plant object `+0x08` output, `+0x0c` base, `+0x14` built, `+0x20` DeclineAge, `+0x1c` MaxLifeSpan, `+0x10` overwork; derate `SIMUTIL 0x100069fb` | CONFIRMED (U-011) | label at each plant on the Energía map ("72% · 18 años") or a list | M (plant enumeration path not traced) | medium, needs plant list walk | know which plant is declining before it fails |
| F | **Per-tile power demand** | power layer `+0x2dc` demand byte per tile | CONFIRMED (POWER_GRID.md) | gradient radio on Energía | S | low | where the load is, sizing new plants |
| G | **Hidden demand variables** 3001 (parks/civic), 5001 / 8001 (connections, airport 12310, seaport 12330), 7000 | Valve layer SIMRCI `0x80f1e6d3`; 3000/5000/8000 clamp ±2000 at `0x1000e842` / `0x100159a5`, 5001/8001 unclamped | ids CONFIRMED (SC3ValveLayer.ini + clamps), 7000 meaning UNCERTAIN | extra bars next to the RCI meter or numbers in a panel | M | low read, UI placement work | sees what ports, airports and connections add to C/I demand. Overlaps stream **portsre** |
| H | **Health / education capacity vs demand, strikes** | ResidentialLayer (city +0xe4) patients `+0x664` / capacity `+0x668`, students `+0x66c/+0x670`, college `+0x674/+0x678`, library/museum `+0x67c/+0x680`, teachers/profs/doctors `+0x684..+0x68c`, strike flags `+0x650..+0x652` | CONFIRMED (catalogue §10) | numbers or bars in a panel, or graph series | S-M | low | "do I need another school/hospital" in numbers. Overlaps stream **graphaxis** part 2 (graph series) |
| I | **Building age map** | occupant record build date (year, day) in the save | CONFIRMED on disk, runtime offset in the occupant object not traced | gradient layer by age | M-L | medium | spots old districts; plant age is item E |
| J | **Neighbour connections per side + pending deal offers + deal age** | SIMMISC neighbours (city +0xf4), save `0x10015378`; deal age `rec+0x38` `0x10018cd5` | CONFIRMED in save (`neighbor_layer.py`), runtime offsets partly | list in Mapa de vecinos | M | low | why a deal is offered, which edge links exist |
| K | **"Why isn't this lot growing"** status | R/C/I evaluators `SIMRCI 0x10028f12`, `0x1000fd53`, `0x10017fc0` return 0..0x10; computed on the fly | CONFIRMED values, labels UNCERTAIN | colour per status on Zonas | L (each status must be decoded) | medium-high | the most useful view a player could have, but the most RE |
| L | Water bit planes | water layer `+0x40/+0x68/+0x6c/+0x70`, 1 bit/cell | shape CONFIRMED, meaning UNCERTAIN | radios on Agua | L | medium | maybe "pipe reach vs served"; must decode first |
| M | Fire burn stats, station shortfall, jail overcrowding | SIMSERV `+0xcc..+0xd4`, `0x1000af08`, `0x1000f3bd` | CONFIRMED readers | numbers | S-M | low | small |
| N | Weather layer | SIMMISC vt `0x10041000`, city +0xf8, 32 methods | GZ-HINT, unread | unknown | L | unknown | unknown |

### Not possible as "real" data (the game does not have it)

- **Health / education coverage per cell**: schools, colleges and hospitals have no radius key
  (`0x10009eed`, `0x10004c2a`, `0x10006416` vs SIMSERV `0x10001020` with radius). Coverage is city-wide capacity,
  item H. A distance map would show something the sim does not use.
- **Noise**: `NoiseFactor=0` in SC3Aura.ini, no grid, no loader read found.
- **Water pressure / pipe capacity**: not modelled (bit planes only).
- **Commute time**: not a quantity. Trips carry a summed cost against a budget and a success bit
  (`PUBLIC_TRANSIT.md` §3). Path length is measurable only by hooking `route_trip 0x100070d0` (ld_paths does it).
- **Desirability per zone type**: one land value map and one aura map are kept, both already shown.
- **Per-wealth demand**: no such valve variables.

## 3. Build plan

**Step 0, the layer kit (needed by A, B, C, F, and later I, K, L).** A new mod DLL `sc3dataview` (keeps `sc3resize.c`
untouched; VERDATOS/VDRADIO already handle extra wrappers):
1. Hook the init of the target panel(s) in SIMUI (post-call) or the message 0x42f0da12 registration, add our
   layer(s) with `iface+0x98`, hidden.
2. Our layer: vtable copied from SIMUTIL `0x10024130`, own +0x48 reading the data on the game thread inside render
   (no Frida, no extra thread), stock palette by hash.
3. Toggle: first version = a key that cycles the extra layers of the open panel (posted-message testable, no real
   mouse). Second version = real radio buttons like the pollution panel, which is SIMUI window work
   (`project-simui-window-model`).
4. Off switch `SC3DATAVIEW=0`, plus per-layer switches.
Risk: a crash inside the dialog render. Prove it first with item B (stock object, zero data code).

## 4. Recommendation: first 4

1. **B, layer 0x2735**: one call, proves the kit end to end, and reveals a layer Maxis cut.
2. **A, trip success map**: the strongest hidden-data view, data CONFIRMED and already used by sc3perf.
3. **C, separate road / highway / subway traffic**: same panel and kit as A, almost free after A.
4. **H, health/education capacity vs demand**: numbers the player has to guess today. Agree with graphaxis who
   draws it (graph series or panel numbers) so it is not built twice.

Next tier: D (garbage ledger, after the landfill stream settles the landfill model), E/F (power), G (after portsre).
K stays as research: high value, but each status code has to be decoded first.

## 5. Verification per item (light, per `feedback-light-testing`)

One in-game check per item in `dev\dataview\tree`, frame-dump pictures of the panel into
`MAIN\verify\dataview\owner_shots\`. For A and C, compare against a city where sc3perf's trip counters show known
failures. For B, compare its mask against the zone raster's landfill cells (slot 17) and the 0x8000 bit.
