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
