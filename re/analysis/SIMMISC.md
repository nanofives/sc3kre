# SIMMISC.md — SIMMISC.DLL: budget, world, ordinances, aura, neighbor deals

```
Apps\SIMMISC.DLL   331,776 bytes   image base 0x10000000   2,603 functions
export: re\ghidra_export_simmisc\
```

Four subsystems in one module. Director `GZDllGetGZCOMDirector` `0x1002fe99` → ctor `0x1002a204`
→ **36** registrations (SIMRCI recipe).

> **Subsystem-id correction:** the task prompt called budget "S7". Per `SUBSYSTEMS.md`, **S7 is
> Vehicles/Street-Sim** and **S10 is Budget & finance**. The tracker uses the canonical ids:
> budget + neighbor deals = **S10**, world = **S1**, ordinances = **S14**, aura = **S12**.

| class | GZCLSID | `new` | ctor |
|---|---|---:|---|
| **SC3BudgetLayer** | `0xc11bcc75` | 0x598 (1432) | `0x10005129` |
| **SC3WorldLayer** | `0xe11bddf6` | 0xc8 (200) | `0x1002653f` |
| NeighborDeals manager | `0x2910e84` | 0x204 (516) | `0x10014759` |
| Aura layer | `0xc259c02d` | 0xbc (188) | `0x10001058` |
| Ordinance manager | `0x41193c4b` | 0x78 (120) | `0x10019a2b` |

Plus ~28 small `0x03/0x43/0xc3-12xxxx` classes of 0x34–0x50 bytes — a typed-object taxonomy with
no string anchor, all `[UNCERTAIN]`.

**Which class is which, proved per-class** (the config-load vtable slot is *not* uniform, so
sole-opener + sole-caller was used instead): `\Sys\SC3BudgetLayer.INI` is opened only by
`0x100053bb`, called only by `0x10005303`, which has no direct caller (vtable dispatch) and sits
in the same address island as the factory-bound ctor `0x10005129`, whose last field write
(`param_1[0x154]`, offset 0x550) fits `operator_new(0x598)`. Same argument for World via
`0x10027be7` ← `0x10026714` ← ctor `0x1002653f`. `[UNCERTAIN]` the exact slot indices — the
vtables are `.rdata` and need a live-Ghidra xref.

## S10 — the budget model `[CONFIRMED @0x100053bb]`

### Bonds `[Bonds]`
| key | global | arithmetic |
|---|---|---|
| `MaxBonds` | `DAT_1004948c` | atoi |
| `MonthlyPaymentPer1K` | `DAT_10049490` | atoi |
| `MaxBondAmt` | `DAT_10049494` | **atoi × 1000** @`0x10005437` |
| `BondLifespan` | `DAT_10049498` | atoi |

The model is parameterised as `monthly = (principal / 1000) × MonthlyPaymentPer1K`, capped by
`MaxBonds` (count) and `MaxBondAmt` (currency, entered in thousands). `[UNCERTAIN]` the per-bond
repayment record and schedule loop — they live in the 1432-byte layer object's tick methods,
not in the loader.

### Taxation `[TuningParameters]` — "transmogrifiers" are scalars, not tables
`LVToResTaxTransmogrifier` → `DAT_1004949c`, `LVToCom…` → `DAT_100494a0`, `LVToInd…` →
`DAT_100494a4`, each `(float)atoi × _DAT_1003c644`. So a *transmogrifier* is a **single
land-value→tax conversion coefficient per RCI category** — no array, no index. `MinAverageLV` →
`DAT_100494a8`, clamped ≤ 255.

`TaxationDemandEffect` **is** the table (the tax→demand curve): map `DAT_10049db0` keyed by int,
element **27 dwords / 108 bytes**; each row parses 4 tokens — two floats (`atol × _DAT_1003c644`),
a byte clamped ≤ 22, and the int key. Remaining dwords of the slot are untouched by the loader
`[UNCERTAIN]`.

`[UNCERTAIN]` the numeric value of the scale float `_DAT_1003c644` — a `.rdata` literal not in the
text export.

### `[BuildingPlacementCosts]`
A list (cb `0x1000668d` → map `DAT_10049de0`, keyed by building id) plus **13 fixed action costs**
into `DAT_10049dc0` at indices 0–0xc: LowDensityZone, MedDensityZone, HighDensityZone,
LandfillZone, AirportZone, SeaportZone, Dezone, Demolish, LevelTerrain, RaiseTerrain, LowerTerrain,
DecorativeWater, DemolishRubbleTile — the build-UI tool costs.

## S14 — ordinances

**The ordinance record is 40 bytes** (`operator_new(0x28)`, `0x1001a637`), keyed into a map at
`manager+0x28`:

| off | field |
|---|---|
| `+0x00` | int ordinance id |
| `+0x04` | byte flag = 0 |
| `+0x05` | byte: 1 = leaf, 0 = has child |
| `+0x08` | int → child/prerequisite record, or 0 |
| `+0x0c` | embedded object + a string from GZ key `{group = token5, type 0xc29a6083}` — the ordinance's resource reference |
| `+0x24` | int (last token) |

Global triggers `[ORDINANCE_TRIGGERS]` → manager `+0x18`…`+0x24`:
`HOMELESS_SHELTER_PERCENT`, `EARTHQUAKE_PREP_BUILDINGS`, `TOURIST_PROMOTION_BUILDINGS`,
`AEROSPACE_AVAILABLE_YEAR`.

### How effects reach the other layers `[important]`
**SIMMISC does not hold the RCI or power effect magnitudes.** It owns *governance state* — which
ordinances exist, which are enabled, and the trigger thresholds. The magnitudes live with their
consumers: `OrdinanceEffects` is loaded by SIMRCI's `sc3_valve_load_tuning` (`SIMRCI.md`), and
`SavingDueToPowerConservationOrdinance` by SIMUTIL's `sc3_power_load_layer_tunables`
(`SIMUTIL_SIMTRANSIT.md`). Only budget/aura-local effects are in SIMMISC:
`TireRecyclingOrdEffect` → `DAT_10049dd0`, and `ParkingFineOrdEffect` / `AltDrivingOrdEffect` /
`NukeFreeOrdEffect` in the aura loader.

`0x10019b65` binds three sibling interfaces (`0xc106c4f5`, `0xa0ab89f0`, `0x411bddda`) and
registers the manager as a service (key `0xc37a5aaa`) — that is the enable/broadcast channel.
`[UNCERTAIN]` the exact monthly dispatch call; it goes through those COM interfaces.

## S12 — the aura layer `[CONFIRMED @0x1000133a]`
`\Sys\SC3Aura.INI [TuningParameters]` → byte globals `DAT_10049110`…`DAT_10049128`:
`UpdatePeriod` (forced ≥ 1), `OptimalPoliceCoverage` + its Optimal/Oppressive/Inadequate effects,
`CrimeFactor` (0 → −1), `FireCoverageFactor`, `AirPollutionFactor`, `WaterPollutionFactor`,
`StandingGarbageFactor`, `RadiationFactor`, `High/LowEQFactor` + thresholds, `High/LowLEFactor` +
thresholds. This is the pollution / crime / education / land-value driver.

## S10 — neighbor deals `[CONFIRMED @0x100159fb]`
`[DEAL_RATE_CONSTANTS]` POWER/WATER buy+sell rates, GARBAGE import/export rates,
`DEAL_RATE_VARIABLE`. `[BASE_DEAL_QUANTITIES]` BASE_POWER/WATER/GARBAGE (each stored twice —
value plus a running copy), `PercentPopForSell/Buy`, `Power/Water/GarbageUnitsPer1K`.
`[MINIMUM_DEAL_COSTS]` and `[DEAL_PENALTIES]` (`BASE_DEAL_PENALTY`, `DEAL_PENALTY_MULTIPLIER`).
Mechanically: monthly cash = quantity × rate, quantity from `UnitsPer1K × (population/1000)` gated
by the percent-pop keys, floored by the minimums, with a cancellation penalty.

## S1 — world layer `[CONFIRMED @0x10027be7]`
`Sys\SC3WorldLayer.ini [WorldLayer]`: `JobToResFactor` (byte, 0 → 1), `ExternalJobDemand`,
`ListOfWorldValveMapping`, and `EconomicPhases` → map `DAT_10049f70`, 4-dword record
`[key×1000, 0, int2, int3]`, default `[0,0,1,1]` when empty. The external-economy / job-demand
driver feeding RCI.

## "Cheesy funds cheat"
`0x10004fd8` (16 bytes) does exactly one thing: builds a named descriptor at `DAT_10049e08` with
the label `Cheesy funds cheat`. `DAT_10049e08` is referenced nowhere else, and `0x10004fd8` has no
caller (static-init / indirect registration). So SIMMISC registers only the **trigger label**;
the money-granting effect dispatches through the descriptor vtable `PTR_LAB_1003c434` elsewhere
`[UNCERTAIN]`. The master cheat gate `simon says` lives in `SC3U.exe` (`SUBSYSTEMS.md §2`).

## Open (needs live Ghidra — data xrefs)
1. Config-loader vtable slot indices for budget / world / ordinance.
2. Numeric value of the scale float `_DAT_1003c644`.
3. The per-bond repayment record inside the 1432-byte budget object.
4. The ~28 unnamed `0x03/0x43/0xc3-12xxxx` classes.
