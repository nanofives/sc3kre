# Graficas window: the 16 series, how they are kept, and what has no graph (child graphaxis 2026-10-30)

Owner request (2026-10-30): "Add graphs for information that is missing." This is the plan. Nothing here is built yet,
the owner picks first. Static reads (worker pass over the per-module exports plus a raw PE read), with the runtime
values measured on Berlin in `verify/graphaxis` where noted.

## 1. How the window gets its series

- Page window class: 0x84 bytes, ctor SIMUI `0x1002f9b7`. It broadcasts `{0x02DC6D7F, 0x605}` through city vt+0x1d4 with
  a sink at this+0x64 (IID 0x5e8). Each sim layer answers with `sink->+0xc(series)`. `FUN_1002f8c7` pushes
  `{BYTE on = 0; series *}` into the vector at this+0x68..+0x6c [CONFIRMED @ SIMUI 0x1002f8fd].
- Renderer SIMUI `0x1002ed75`. It plots `value * 100.0 / scale` (`_DAT_100a40b4` = 100.0f). Range group = page child 2,
  IID 0xa1336cc0 vt+0x30: 3 = 12 months (vt+0x28), 4 = 10 years (vt+0x34), 5 = 10 decades (vt+0x40) [CONFIRMED].
- Layout: checkboxes at page-local (20 + 120 col, 210 + 24 row), 3 per row (`0x1002e012`, `0x1002e380`). Line-end labels
  are a 4 px column at x 262..266 (`0x1002e19e`). The page sits at (38, 40) in the 424x440 Ver datos dialog (measured).

## 2. The series class (one copy statically linked in every sim module)

`operator_new(0xf0)`, ctor SIMMISC `0x10033556`, interface at obj+8 (vtable SIMMISC `0x10041b78`), IID `0xE3012FC7`.
Interface slots: +0x14 checkbox id ptr, +0x18 label id ptr, +0x1c colour, +0x20 scale, +0x28/+0x34/+0x40 copy the
12 / 10 / 10 arrays (newest first), +0x2c/+0x38 averages, +0x4c name, +0x50(i) labels, +0x54/+0x58 set the control ids,
+0x5c set colour, +0x60 set scale, +0x64 auto flag, +0x68(min, factor) auto settings, +0x6c/+0x74/+0x7c push a month /
year / decade, +0x70/+0x78/+0x80 set a whole array, +0x84 load, +0x88 save. Storage obj+0x78 (12 months), +0xa0 (10
years), +0xc8 (10 decades).

**Scale (+0x20)** [CONFIRMED @ SIMMISC 0x10033885, 0x10033baa, 0x10033856]: fixed mode = the constant set by +0x60, and
pushed values are clamped to it. Auto mode = `max(min, round(min(factor * max_of_all_32_values, 2^32)))`, factor =
`0x1003c648` = 1.1. Recomputed before a push that exceeds round(scale / factor), on array set and on load.

**Roll-up** (same in every record function): every month a push (+0x6c). In month 1 the 12-month average goes into the
yearly ring. When year % 10 == 0 the 10-year average goes into the decade ring. "100 anos" shows 10 decade averages.

**Save:** each layer writes its own series inside its own save record (+0x88 / +0x84, 12 + 10 + 10 dwords + scale,
`0x10033e90`). There is no spare history slot.

## 3. The 16 series

| # | ES label | Owner, builder (field) | Monthly record | Value pushed | Scale |
|---|---|---|---|---|---|
| 1 | Tamano de la Ciudad | SIMMISC world `0x10026795` (+0x28) | `0x100285bb` | R + C + I layer vt+0x28 | auto, min 100000 |
| 2 | Poblacion (Nat'l Pop) | same (+0x40) | `0x100285bb` | +0xa0: prev * 0xf4283 / 1e6 + RNG (range 0x1395) | auto, min 10000 |
| 3 | Comercio | same (+0x58) | `0x100285bb` | layer(+0x24) vt+0x28 | auto, min 10000 |
| 4 | Industria | same (+0x70) | `0x100285bb` | layer(+0x20) vt+0x28 | auto, min 10000 |
| 5 | Desempleo | same (+0x88) | `0x100285bb` | 0 if W <= J, 100 if J = 0, else (W - J) * 100 / (2W) | fixed 100 |
| 6 | Fondos | SIMMISC budget `0x100067c7` (+0x44), id 0x630536cb | `0x10007d88` | (max(treasury, -100000) + 100000) / 1000 | auto, min 200 |
| 7 | Aprobacion | SIMMISC aura `0x10002226` (+0x88) | `0x10002bcb` | signed byte +0xa4 + 0x7f | fixed 260 |
| 8 | Residentes | SIMRCI res `0x100214e0` (+0x690) | `0x10024347` | res vt+0x78 (population) | auto, min 10000 |
| 9 | Educacion | same (+0x698) | `0x10024347` | vt+0x88(0, 0x59) EQ, ages 0..89 | fixed 150 |
| 10 | Salud | same (+0x694) | `0x10024347` | vt+0x90(0, 0x59) LE, ages 0..89 | fixed 89 |
| 11 | Valor del Terreno | SIMRCI `0x1001c854` (+0xb0) | `0x1001d69b` | byte +0xc0 | fixed 260 |
| 12 | Polucion | SIMECO `0x10005844` (+0xf4) | `0x10007b5d` | (water * 100 / MaxWater + air * 100 / MaxAir) >> 1, max 100 | fixed 100 |
| 13 | Crimen | SIMSERV `0x10006aca` (+0xa8) | `0x100079d1` | byte +0xc4 | fixed 260 |
| 14 | Energia % | SIMUTIL `0x10003904` (+0x2c8) | `0x100051b8` | dword +0x78 | auto, min 10 [UNCERTAIN meaning] |
| 15 | Agua % | SIMUTIL `0x1000d262` (+0x3c) | `0x1000e8c4` | A * 100 / B (B at +0xb0, B - A at +0xb8) | fixed 100 |
| 16 | Trafico | SIMTRANSIT `0x10003eee` (+0xac) | `0x100093e9` | sum of cell density bytes / (vt+0xc8 + vt+0xc4) | fixed 220 |

Measured on Berlin (GRAPHAXIS log): Tamano 1,233,885 with scale 1,378,689; Fondos 221 (= 121,000) with scale 930;
Energia 18 with scale 59; Aprobacion 195 / 260; Comercio 118,738 / 133,101; Educacion 105 / 150; Salud 87 / 89.

Tracker names to fix (not changed here): SIMMISC `0x10026795` / `0x100285bb` are the world-layer series, not a finance
graph. SIMRCI `0x100214e0` is the Residents / Education / Health series. SIMSERV `0x10006aca` owns Crime.

## 4. Data that changes over time and has no graph

| Data | Where | History the game already keeps | Shown today |
|---|---|---|---|
| Income / expenses per category | SIMMISC budget `0x10007d88`: 7 x 12 monthly int64 buckets | 12 months, current year | Budget window |
| Tax rates R / C / I | budget GetTaxRate `0x1000520b` | none | Budget window |
| Debt / borrowed | `0x1000521f`, limit `0x100092aa` | none | Budget / loans |
| RCI demand | SIMRCI valve `0x1002efe8` | none | RCI bar (live) |
| Population by wealth | SIMRCI census `0x10025759` (+0x628..+0x640) [UNCERTAIN channel] | none | none |
| Workforce % / workforce EQ / LE | `0x100251a8`, `0x100251f6`, `0x10025292` | none | Cuadros |
| School / hospital load vs capacity | res layer +0x664..+0x680 | none | advisors |
| Jobs vs workforce | inputs J, W of `0x100285bb` | only Desempleo | none |
| Air vs water pollution | SIMECO +0xec / +0xf0 | only the averaged Polucion | maps |
| Garbage ledger, landfill capacity | SIMECO +0x154..+0x18b, rings +0x1a8..+0x3e8 | 12-month ring [save UNCERTAIN] | Cuadros (split) |
| Power by plant type, supply vs served | SIMUTIL +0xcc (12 x 10), +0x70 / +0x74 | 12-month ring (by plant) | Cuadros |
| Water demand / unmet | SIMUTIL water +0xb0 / +0xb8 | only Agua % | none |
| Neighbour deal income | SIMMISC `0x10006277` | none | budget |
| Transit ridership, commute time | no counter found [UNCERTAIN] | none | none |

## 5. Cost of a new series

- In the window: build a series with the game's own class (`operator_new(0xf0)` + SIMMISC `0x10033556`), answer the
  `0x605` broadcast with it (hook a handler such as SIMMISC `0x1002848f`), push from a hook on an existing monthly record
  function. The page lays checkboxes 3 per row from y 210: 16 series use 6 rows and the 6th row sits at y 330 + 18 of a
  396 px page, with the range radios at the right. Room for 1 more row (3 series) is likely; more needs a layout change
  [UNCERTAIN until tried].
- History: the 12-month view can be seeded from rings the game keeps (budget buckets, garbage rings, power by plant).
  10-year and 100-year views of a new series must be recorded by the mod and kept in a side file next to the `.sc3`
  (city name + date check after load). Writing into a stock save record would break the stock game's load.

## 6. Recommended first

1. Ingresos vs gastos (2 lines). 12 months free from the budget buckets. Low cost.
2. Energia y agua: oferta vs demanda (power +0x70 / +0x74, water +0xb0 / +0xb8). Low cost.
3. Demanda R / C / I. Needs the valve getter. Medium.
4. Polucion aire vs agua: two fields the game averages away. Very low cost.
5. Basura: producida vs al vertedero, capacidad restante. Ties in with the landfill stream. Low to medium.
6. Empleos vs poblacion activa: the inputs of Desempleo. Low cost.

## 7. Built 2026-10-30 (owner pick 1-4): GRAPHNEW, `re/harness/src/sc3resize_graphs.c`

Five graphs, one checkbox each, 11 lines, made of the game's own series class. Code comment block = the full evidence.

| Checkbox | Lines | Source (read after SIMMISC `0x10007d88`, closed month `ci`) |
|---|---|---|
| Ingresos/Gastos | Ingresos, Gastos | budget int64 rings `+off+ci*8`. Income: taxes `+0x90/+0x118/+0x1a0`, fares `+0x3a0`, ordinances `+0x2d0`, neighbour deals `+0x470`, business deals `+0x4e8`, disaster relief `+0x338`. Expenses: ordinances `+0x268`, neighbour deals `+0x408`, bonds dword `+0x558+ci*4`, departments: map `+0x60` nodes `+0x30+ci*8` (yearly total node `+0x90`, SIMMISC `0x10008d54`) |
| Energia of./dem. | oferta, demanda | city vt+0x150 = power layer + 0x14. Supply `+0x70`. Demand = sum of the demand bytes `+0x2dc` (w `+0x28`, h `+0x34`+1). Measured on Berlin: the byte sum equals the served `+0x74` of the next tick (served lags one month), so it is the same unit, and it also counts unpowered tiles |
| Agua of./dem. | oferta, demanda | city vt+0x154 = plumbing layer. Supply int64 `+0xb0`, delivered int64 `+0xb8`. Unmet water demand is not stored, so "demanda" is what was delivered |
| Demanda RCI | R, C, I | city vt+0x1b8(0x80f1e6d3), QI 0x40a42f1c, vt+0x14(3000/5000/8000), valve vt+0x30/+0x38/+0x3c. Shown as the HUD bar: -1000..1000. Berlin: all three valves max 2000 min -2000 |
| Contam. aire/agua | aire, agua | city vt+0x16c = SIMECO + 0x1c, vt+0x78 / +0x7c, as % of vt+0x84 / +0x88 (11000) |

Calendar: city vt+0x1e4(&month, &day, &year), month already the new one. Yearly push when the closed month is December,
decade push when (year + 1) % 10 == 0 (same rule as the game's records).

History file `<city>.sc3.graphs` (1,512 bytes): header {magic, ver 1, closed-month key, 11}, then per line {id, scale,
12 + 10 + 10 dwords}. Written after SIMCITY `0x1000429d` (city save) returns success, once the city file on disk carries
the save's time. Read the first time the graphs look at a city in a session and whenever the date jumps, used only when
its key equals the city's. City vt+0x1c (`0x10003b8b`) is NOT the load path: a detour on it never fired on a load.

Corrections to earlier notes (worker pass 2026-10-30):
- POWER_GRID.md `+0x78` is the spare-capacity % (what Energia % plots), not unmet demand. `+0x2d8` is the Energia
  series, not a message dispatcher.
- Section 4 above: unmet water / power demand are not stored as totals. The budget has 9 income/expense groups, not 7.
- `0x1002f8fd` (page vt+0x20) takes 2 arguments (`ret 8`), Ghidra shows one.

Autosaves (2026-10-31): sc3resize export `sc3resize_graphs_write(path)` writes the snapshot of the last save; sc3autosave
block GRAPHS calls it for its temp file and moves / deletes `.graphs` with each autosave file. The reader tries the
city's file, then `<stem> (auto 5 min|10 min|1 h).sc3`, because UNAUTO renames a loaded autosave to `<city>.sc3`.

## 8. graphtabs (2026-11-02): tabs, 9 more graphs, history seeded at load

Owner: "Demand graphs are not working, they show nothing, shows flat / energy demand/offer either / put tabs to show
different types of graphs, add more graphs according to available data".

**Why the new graphs looked flat.** The owner's MARIANO-PC log (2026-11-01, Big One): `history starts empty`, Graficas
opened before a month closed. With no `.graphs` file every new line was 12 months of its fill value (0, or "no demand"
for R/C/I). The values pushed were right (LIVING-PC Berlin: power supply 195,168 vs demand ~158,000, R/C/I moving).

**Seeding at load** (a line not found in the history file):

| Lines | 12 months from | Evidence |
|---|---|---|
| Ingresos, Gastos | budget rings, slot `(ci - k) % 12`. Slots after `ci` hold last year's months: the year-end fold zeroes only the yearly accumulators | [CONFIRMED @ SIMMISC 0x10007d88], saved by `0x10007519` |
| Energia consumo | power ring base+0xcc, 12 rows x 10 plant types, newest row base+0x2ac (rolling, not the calendar month) | [CONFIRMED @ SIMUTIL 0x10004c1f], saved by `0x100045ec` |
| Energia oferta | consumo and the stock Energia % series (base+**0x2d8**, spare % = (S - D) * 100 / S): S = D * 100 / (100 - spare) when spare > 0, else D. Newest month exact | [CONFIRMED @ SIMUTIL 0x100051b8] |
| Basura (5 lines) | SIMECO int64 month rings, slot = closed month | [CONFIRMED @ SIMECO 0x10007b5d], saved by `0x10006abb` |

Every other line, and the 10 / 100 year views, start at today's value (the 12-month mean for a seeded line). No ring
exists in the game for R/C/I demand, water, pollution split, taxes, debt, jobs, schools, hospitals or abandoned tiles.

Correction: the worker read put the Energia series at power +0x2c8. Its builder `0x10003904` runs with this = base+0x10;
the record `0x100051b8` reads base+0x2d8 (measured: a read at +0x2c8 found nothing).

**New graphs** (lines 11..30; lines 0..10 keep their ids, so 10-30 `.graphs` files still load):

| Graph | Lines | Source |
|---|---|---|
| Energia of./dem. | + consumo | newest row of the power ring. Demand is now iface vt+0x5c (base+0x2ec, running sum of the demand bytes) |
| Agua of./entreg. | "demanda" renamed "entregada" | it always was delivered (+0xb8); unmet water is not stored |
| Impuestos | R, C, I (%) | budget byte +0x8c + i * 0x88 (vt+0x4c(i)). i = R/C/I [UNCERTAIN order]. Berlin reads 2 / 3 / 3 |
| Deuda (bonos) | 1 | int64 budget+0x590 (vt+0x60) |
| Empleos/Trab. | jobs, workers | Desempleo's inputs [CONFIRMED @ SIMMISC 0x100285bb]: valve 7000 vt+0x2c; trunc(valve 3000 vt+0x28 * res vt+0x7c float). Berlin: 425,561 jobs, 794,278 x 0.647 = 513,898 workers |
| Escuelas / Universidades / Hospitales | users vs capacity | res iface (city vt+0x17c, vtable SIMRCI 0x1004c99c): vt+0x50 / +0x64, vt+0x58 / +0x68, vt+0x48 / +0x60. Berlin: 155,982 / 120,000 pupils, 50,140 / 39,000 patients |
| Basura | made, landfill, recycled, incinerated, exported | SIMECO rings +0x1a8, +0x3e8, +0x388, +0x328, +0x268 |
| Sin energia | unpowered tiles | power iface vt+0x60 |
| Abandonados | abandoned tiles | city vt+0x14c (vtable SIMRCI 0x1004d1e0, checked at run time) vt+0x54. Berlin: 0..54 per month |

The budget is reached as city vt+0x15c (vtable SIMMISC 0x1003c550) when no month has closed yet.

**Tabs.** A radio row under the chart (the range group's recipe, SIMUI `0x1002e6cb`, here `mp_group`): Ciudad, Economia,
Servicios, Redes, Ambiente. Each checkbox id belongs to one tab (`k_tab`); only the current tab's checkboxes show, from
page (20, 230), 3 per row, and only its checked graphs draw (off-tab series get an id no window has, stock ones get
their id back before the page closes). Traps found in the lab:
- The page's control handler `0x1002df5b` re-renders after a radio pick only when that group's selection is 3..5 (the
  range radios) [CONFIRMED @ SIMUI 0x1002df5b]. A tab pick changed the radio and nothing else; the next click then hit
  the old tab's checkbox. Detour on `0x1002df5b`: our group id -> render.
- A hidden checkbox (vt+0xfc) still took clicks at its cell (a click on Redes' first cell toggled Salud, hidden there
  from Servicios). Off-tab checkboxes are also moved to y 4000.
- Moves write the LOCAL rect only; the page rebuilds derived rects (vt+0x168, vt+0x14c) after placing a tab.
- `SC3RESIZE_GRAPHTABS=0`: the one-grid page; groups 6..14 then sit below the page's bottom edge.
- Lab: `graphaxis_lab.py` waited on the first GRAPHAXIS dialog line, which now comes before DLGSCALE's: wait on DLGSCALE
  first. A Save from the lab needs an un-linked city copy (`GraphTest.sc3`); the linked Berlin never saved.

## 9. graphs2 (2026-11-02): drawn tabs on both pages, Cuadros tabs, bar charts (education, health, water, transport)

Owner: line-graph tabs drawn as real tabs in one aligned row; the Cuadros radios become tabs too; Education tab with
capacity vs students (schools, universities, what exists for libraries and museums); Health tab with patients vs
capacity; water sources and processing in one tab; transportation methods used. Code: `sc3resize_vdtabs.c` (tab
widgets), `sc3resize_vdbars.c` (Cuadros hooks, bars, trip counter), GRAPHNEW hooks in `sc3resize_graphs.c`.

**Tabs.** GZWIND has no tab class (19 classes in `FUN_1000121d`; `FUN_1001a420`, once tagged "layout_tabs", draws a
scrolling item list) [CONFIRMED @ GZWIND 0x1000121d, 0x1001a420]. A tab = shape-class polygons (0x4303E5B6, **style
0x31** = filled + outlined, fill vt+0x14, line vt+0x18, as SIMUI 0x10046590 / 0x10051c53; **0x11 only strokes**) +
a caption-only text button over them (factory +0x2c, iface vt+0x58(NULL) drops the art, style bit 0x10 skips the
bevel, click = message 3 / p3 1 / id to the page's control handler) [CONFIRMED @ GZWIND 0x10008935, 0x10008adf,
0x10008fdb]. Tabs hang under a rule on the chart's bottom edge; the selected one is the Cuadros panel colour
(factory colour 0x62E56A2B), taller, rule broken under it. The button's auto-size (style 0x6a4 bit 0x20) does not
measure the caption (54..67 px for every caption): widths come from a per-character table of font 0xf.

**Cuadros page.** Director vtable SIMUI 0x100a4080: build `0x1001f3df` (+0xc), close `0x10020ffd` (+0x10); control
handler `0x1001f30d` (vtable 0x100a4008 +0xc, ret 0x14); refresh `0x1001f3b3` (vtable 0x100a3fe8 +0xc, message
0xC2A3FD82) [CONFIRMED by PE read + decompilation]. Children: bar chart 2 (14,10) 356x189, pie 3, panel 4, labels
0xb/0xc, legend 0xd..0x1c, radio group 5 (6 Educacion, 7 Electricidad, 8 Basura, 9 Salud, 10 Poblacion), fill
`0x100245c7`. The mod patches the 4 vtable slots (sc3dataview's prologue detour on the fill keeps working), parks the
radio group, and adds 7 tabs (5 stock + Agua + Transporte).

**Values shown** (all live, measured on Berlin 2026-11-02, `verify/graphs2/RESULTS.md`):

| Tab | Value | Read | Evidence |
|---|---|---|---|
| Educacion | school pupils / places | res layer (city+0xe4, vt SIMRCI 0x1004c99c) +0x66c / +0x670 | SIMRCI 0x10024347 (0x10024b46, 0x10024614) |
| | college students / places | +0x674 / +0x678 | 0x10024b74, 0x10024637 |
| | library places, museum places | +0x67c, +0x680 | 0x1002464c, 0x10024661 |
| | libraries / museums built | places / PopServed (globals SIMRCI 0x1005741c, 0x1005745c) | getters 0x10007f28, 0x1000907f |
| | residents of the age band served | res vt+0x78 x res vt+0x80(lo, hi), band bytes 0x10057420/21, 0x10057460/61 | 0x100251b5 |
| | teachers, professors, strikes | +0x684, +0x688, +0x650 / +0x651 | 0x10024606, 0x10024629 |
| Salud | patients / beds, doctors, strike | +0x664 / +0x668, +0x68c, +0x652 | 0x10024833, 0x1002485d, 0x10024572 |
| Agua | supply, delivered (int64) | plumbing P (city vt+0x154) +0xb0, +0xb8 | SIMUTIL 0x1000e8c4 |
| | per source: count, output, capacity | list *(*(P+0x74)), node +0x18 cap u16, +0x1a output u16, +0x20 type (2 tower, 3 pump, 5 desal), lock *(P+0x14) | 0x1000e0b5, 0x1000f771 |
| | buildings left dry, of consumers | P+0xc4, P+0xc0 (= 100 when none is dry) | 0x1000e8c4 |
| | water pollution (stock average) | SIMECO po (city vt+0x16c) vt+0x7c of vt+0x88 | 0x10008249 |
| | pollution produced / treated, last month | po+0xe8 / po+0xec | rollover 0x10007a9e |
| | treatment plants, capacity | list po+0x98 (sentinel), item vt+0x34 x 30; aging po+0xb8; lock = the object AT po+0x74 | SIMECO 0x1000a032, 0x10008249; SIMUTIL 0x10002563 |
| Transporte | trips using each network, per month | counted by the mod (below) | SimTransit 0x100072b6..0x10007554 |
| | failure ratio, last month | float T+0xb8, T = SimTransit 0x1001fdb8 | 0x100093e9 |

Checks that passed at run time: the per-source outputs add up to P+0xb0 exactly (Berlin 2067-03: 165,354 + 12,842 +
6,140 = 184,336); highway share of trips that used a network 4.9%, inside the 4.2-7.1% hwtrips range.

**Not stored by the game** (said in the tab or here, no proxy drawn): library / museum users (their seats go into the
per-age EQ arrays mixed with schools); students / patients are demand (every resident of the band; population x
pollution rate), not enrolment; unmet water demand; water held by towers; sewage volume; trip counts per mode.

**Traps.** (1) The [Library] INI section is read by the first library built (`FUN_1000793d`, guard `DAT_100585b4`):
with none built, the globals hold the file's defaults (PopServed 60000, ages 6..18), not the INI's (41000, 25..100).
(2) SIMECO's lock is an embedded object at po+0x74 (its first dword is the vtable); SIMUTIL's plumbing lock is a
pointer at P+0x14. Taking *(po+0x74) as the object faulted. (3) Bars reuse window ids in draw order, so a full-frame
shape must have its own id made before everything else, or it covers labels made earlier with lower ids. (4) The lab
game starts paused: `key=P4` before waiting for a month.

**TRIPMODES.** route_trip's pop `call 0x10009eed` at SimTransit 0x100072f8 -> a stub (sc3cartrips' recipe, signature at
0x100072f3, locked 8-byte write) that ORs each node's network into a per-thread mask (TLS) and, on the origin pop
(type 0x80) of a trip with the deposit flag [ebp+0x14], counts the trip once per network it used. Node types: road 1,
3; highway 2; bus 0x41, 0x42, 0x43, 0x50; rail 4, 0x14; subway 8, 0x18. Month = GRAPHNEW's budget record. Berlin:
1,276..1,612 trips per month, roads 62%, highways 3.5%, rail 5%, subway 7%, bus 0%, no network 30% (only the origin lot was
popped: route_trip tests arrival on the start node before expanding; what those trips are is [UNCERTAIN]). sc3cartrips patches the same call; the second to arrive refuses.

Off switches: `SC3RESIZE_VDTABS=0` (stock radios on both pages, no bars), `SC3RESIZE_VDBARS=0` (tabs, no bars),
`SC3RESIZE_TRIPMODES=0`, `SC3RESIZE_VDBARS_LOCK=0` (read the lists without the layers' locks). Log:
`SC3RESIZE_VDTABS_LOG=1`.
