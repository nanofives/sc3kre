# NETWORK_TYPES.md — the network type enum, and what a "new road type" would cost

Measured 2026-08-21. Question that prompted it: **can a new road type be added to the game?**

**Verdict: not without patching code.** The set of networks is a closed 6-member enum realised
as if/else cascades over immediates and hard-coded per-type globals, in three separate modules.
The *payload* of each network (tiling rules, costs, upkeep, art ids) is data-driven and editable.

The same finding explains a fact about the shipped game: **SC3000 has no street and no avenue.**
Exhaustive sweep of `strings.csv` across all 31 exports returns zero hits for
`avenue|street|monorail|elevated|lightrail|NetworkType` in any PC module. The only hits are in
`re/ghidra_export_ios/` (`street_sim/` path names, `SSVehicle::IncludeRoadsAndAvenues`), which
are iOS-only. `[CONFIRMED — negative]`

> ⚠️ That negative was produced with **raw `grep` run inside the export directories**, not the
> harness `Grep` tool, which cannot see `re/ghidra_export*/` at all and reports it as "0 matches"
> (`U-056`). Any re-check must use the same method.

## 1. netType → network, now named

`SIMNTWRK.md` listed the netType→name binding as **OPEN**, and `SIMNTWRK_CLUSTER2.md` recorded
"which physical network each netType denotes … is not string-labelled" as `[UNCERTAIN]`. **Both
are now closed**, by chaining two functions that had not been cross-read:

- `FUN_100175ed` binds each `DAT_100323xx` rule container to a **named `.txt` file**
  `[CONFIRMED @ 0x100175ed:119-332]`
- `FUN_1001547b` binds each **netType constant** to the same container
  `[CONFIRMED @ 0x1001547b:104-167]`

Compose the two and the enum falls out:

| netType | network | final / simple / complex container | handler | sub-layer | factory resource id |
|---:|---|---|---|---|---|
| **1** | **ROAD** | `10032300` / `10032318` / `10032330` | `DAT_100323c0` | `this+0x3c` | `16000` (`0x3e80`) |
| **2** | **RAIL** | `10032308` / `10032320` / `10032338` | `DAT_100323c8` | `this+0x3c` | `17000` (`0x4268`) |
| **3** | **POWER LINE** | `10032314` / `1003232c` / `10032344` | `DAT_100323d4` | `this+0x3c` | `0x42cc` (17100) |
| **4** | **HIGHWAY** | `10032304` / `1003231c` / `10032334` | `DAT_100323c4` | `this+0x3c` | `0x3e81` (16001) |
| **5** | **PIPE** | `10032310` / `10032328` / `10032340` | `DAT_100323d0` | `this+0x40` | `0x4394` (17300) |
| **6** | **SUBWAY** | `1003230c` / `10032324` / `1003233c` | `DAT_100323cc` | `this+0x44` | `0x43f8` (17400) |

Corroborated three independent ways:

1. `FUN_10007791` @ `0x10007791:9-13` — identical netType→handler chain (`1→c0, 2→c8, 3→d4,
   4→c4, 5→d0, 6→cc`).
2. `FUN_100151f1` flag-bit→handler agrees exactly (per `SIMNTWRK_CLUSTER2.md`).
3. The **factory resource ids** read out of the 7 layer-registration functions
   (`0x1000e537`, `0x1000ee4b`, `0x1000fc45`, `0x1000e9e7`, `0x100100bc`, `0x1000f2c7`,
   `0x1000f79c`) form a coherent block: `16000`/`16001` adjacent for the two road-family
   surface networks, `17000`/`17100`/`17300`/`17400` spaced for the rest.

The sub-layer split is a consistency check that holds: **pipe (`+0x40`) and subway (`+0x44`) are
exactly the two underground networks**, and the four surface networks share `+0x3c`.

netType is **not** a bitfield at this layer. The *selector byte* in `FUN_100151f1` is
(`bit0|bit1 → nets 4+1`, `&4 → 2`, `&0x20 → 3`, `&8 → 5`, `&0x10 → 6`), but netType itself is an
ordinal.

## 2. Why six is load-bearing

**There is no bound or count constant.** This is a checked negative, not an absence of looking.
Raw grep for `< 7`, `<= 6`, `- 1 < 6`, `& 0x7` across all 1,851 SIMNTWRK function bodies returns
exactly two hits, both at `0x1001ca1a:234,238`, and both are **terrain-slope thresholds** in the
highway-ramp builder, not type bounds. `[CONFIRMED — exhaustive negative]`

Everything that could have been a table is unrolled code instead:

- Every netType dispatch is an **if/else cascade on immediates**, across **11 functions**:
  `0x1001547b`, `0x10007791`, `0x100077e7`, `0x10008064`, `0x10008a4a`, `0x10014771`,
  `0x10014807`, `0x1001a2c0`, `0x1001a7f7`, `0x1001a85a`, `0x10022676`.
- The handler objects are built by **individually emitted** `operator_new(8)` +
  `FUN_1001a98b` blocks with a **literal distinct vtable each** — e.g.
  `DAT_100323c0 ← PTR_FUN_1002c748`, `DAT_100323c4 ← PTR_FUN_1002c734`,
  `DAT_100323d4 ← PTR_FUN_1002c6f8`, over `DAT_100323c0..0x10032464`
  `[CONFIRMED @ 0x10010dff:218-275]`. **Corrected 2026-08-23: there are exactly 42**, not "~50" —
  vtables `0x1002c414..0x1002c748` step `0x14`, and the block ends flush against the next class's
  vtable at `0x1002c75c`. They are stateless predicate functors (one `bool Test(subject)` at
  `+0xc`), not per-rule-case dispatchers. Full map: `NETWORK_RULE_ENGINE.md` §5.
- The 18 rule containers, 7 Set vectors, 12+12 Convert/Protected/Bridges vectors and 6 per-type
  allowed-piece vectors are each allocated by their own `operator_new(0xc)`
  `[CONFIRMED @ 0x10017f98:614-820]`.
- The rule **filenames are hard-coded string literals in straight-line code**: `FUN_10016d87`
  builds exactly **7** `_Set.txt` paths, `FUN_100175ed` exactly **18** (6 nets × {Simple,
  Complex, final}), `FUN_10017f98` the remaining ~21 from named string pointers. **No directory
  scan and no count read from a file** — so the loader cannot discover a 7th rule set even if the
  files were placed correctly.

The effective bound is the literal `6` embedded in the comparison chains.

### The edits a 7th network would need

1. The `1..6` cascades in **11 SIMNTWRK functions** (list above).
2. The **22-entry piece-constructor jump table** `switchdataD_1000c2a4` @ `0x1000c2a4`, driving
   `FUN_1000bdcd`'s `switch((param_1 & 0xff) - 1)`, cases `0x00..0x15`, each stamping two
   hard-coded vtable pointers `[CONFIRMED @ 0x1000bdcd:20-231]`. A 23rd piece class has no
   reachable code.
3. **The `*6` stride in the piece matrix `DAT_100318ac`**, indexed `(row + col*6)*4`
   `[CONFIRMED @ 0x100167d4]`. The network count is baked into an address computation.
4. The **12-value transit type-byte cascade** in SimTransit (§4).
5. **Three new predicate functions** (positive, negation, crossing) plus a **43rd vtable** — and
   the `.rdata` vtable block is **contiguous with the next class's vtable**, so there is no slack
   to extend it in place (`NETWORK_RULE_ENGINE.md` §5).

Plus the UI, which is equally closed: `MenuItem.INI` rows dispatch **fixed GZCOM command GUIDs**
(`0xC2B5DE77` Roads, `0x42B5DE98` Lay Rail, `0xC2B5DEA6` Lay Subway Rail, `0x42B5DE86` Highway)
that must already exist in a module. **You can retarget a button, not create a tool.**

## 3. The one crack: netType 8

`FUN_10014807` @ `0x10014807` dispatches `param_2` over `{1,2,3,4,5,6,8}` to vtable slots
`+0x78/+0x80/+0x8c/+0x7c/+0x88/+0x84/+0x90`. **Value 7 is absent; 8 maps to `+0x90`.**
`[CONFIRMED @ 0x10014807]`

What `8` denotes is **`[UNCERTAIN]`** — no string, no second witness found. This is the only site
where the enum is not closed at 6. Missing evidence: the vtable contents at slot `+0x90` on that
object, or the caller that supplies `param_2`. Filed as **U-071**.

## 4. The SimTransit type byte, decoded

`SIMTRANSIT_CLUSTER1.md` recorded the type→mode binding as `[UNCERTAIN]`. **Closed**, by pairing
the cost-global *use sites* in `FUN_1000755e` against the *definition sites* in the INI loader
`FUN_100015b1` (section `[TrafficLayer]` of `Sys\STTraffic.INI`). Every use site pairs
`DAT_1001f0b<n>` with `DAT_1001f0c<n+1>`, 10/10 consistent, which pins the enum:

| type byte | cost pair | meaning |
|---:|---|---|
| `1` | b0/c1 | **Road** |
| `2` | b2/c3 | **Highway** |
| `3` | b0/c1 | Road (secondary — see below) |
| `4` | b8/c9 | **Rail** |
| `8` | b9/ca | **Subway** |
| `0x14` | b5/c6, or b8/c9 if subtype==4 | **RailStation** |
| `0x18` | b7/c8, or b9/ca if subtype==8 | **SubwayStation** |
| `0x30` | b6/c7, or b9/ca if subtype∈{4,8} | **SubwayRailStation** |
| `0x41` `'A'` | b1/c2 | **Road+Bus** |
| `0x42` `'B'` | b3/c4 | **Highway+Bus** |
| `0x43` `'C'` | b1/c2 | Road+Bus (variant) |
| `0x50` `'P'` | b4/c5, or b2/c3 if subtype=='A' | **BusStop** |
| anything else | — | impassable (`+0x1d = 0`) |

All `[CONFIRMED @ 0x1000755e:378-520]`.

Bit semantics corroborated by `FUN_10008a94` @ `0x10008a94:26-48`: type `1`/`'A'` → connectivity
bit `0x400`, `2`/`'B'` → `0x800`, `4` → `0x1000`, `8` → `0x2000`. So the **low nibble is
`1 road / 2 highway / 4 rail / 8 subway`, `0x10` = station, `0x40` = bus-route overlay**.

`[UNCERTAIN]` whether type `3` is a distinct network or an alias of road: it uses the Road cost
pair at `0x1000755e:455` but has its own arm. Missing evidence: the writer that stamps `3` into
the type byte. Filed as **U-072**.

## 5. Data-driven vs hard-coded, per network

### Data-driven (loaded at runtime)

| what | source | witness |
|---|---|---|
| Tiling / auto-orient / bridge / convert / protected rules | `TilingRules\{ROAD,HWAY,RAIL,SUBW,PIPE,POWR}_GRND_*.txt` + `DIAG_Set.txt`, `Collapse.txt` | loaders `0x10016d87`, `0x100175ed`, `0x10017f98`; reader `0x10017596`; parsers `0x1001746e`, `0x10022676`. **Game-verified 2026-08-23**: files read from `Apps\Res\TilingRules\` and their contents parsed into engine records — `verify/tilingrules_read_test/RESULTS.md` |
| Per-network **protected** piece-id list | **`*_Protected.txt`** → 6 vectors `DAT_10032394..a8`, loaded by the COUNTED_LIST parser `FUN_100196ce` | `FUN_1001a7f7(netType, pieceId)`, linear scan. **Corrected 2026-08-23:** this is a *protected* test ("the tiler may not replace or remove this piece"), NOT an allowed-piece test, and it does **not** read `*_Set.txt` — the Set files load into `DAT_10032348..0x10032360`. `NETWORK_RULE_ENGINE.md` §6 |
| Per-mode trip cell cost + congestion divisor (10 modes) | `Sys\STTraffic.INI` `[TrafficLayer]` | `0x100015b1:50-610` |
| Impassability threshold, max density, mass-transit chance, per-zone max road distance | same INI | `0x100015b1:330-790` |
| Per-station `OptimalMonthlyUpkeep` | `Sys\SC3Tune.INI` | `0x1000d3a7`, `0x1000d625`, `0x1000d8e7`, `0x1000dbc7` |
| Vehicle rosters | `Sys\SC3StrtSimLayer.INI` → GZCLSID vectors | `0x10014796:53-75` |
| Placed-piece persistence | GZ property block `0x6355941d..0x63559422` | `0x1000ca2c` save / `0x1000c86f` load |

### Hard-coded (immediates / `.rdata`)

The existence and count of the 6 networks (§2); the 22 piece classes and vtables; ~50 rule
handlers; default piece ids per network (`0x1d` road, `0x2c` rail, `0x5c` power,
`[CONFIRMED @ 0x1000122a:689-716, 828-854]`); crossing ids `0x49, 0x2bfa, 0x3acb, 0x3afa,
0x3b07..0x3b0a` (`0x10009d20`); the `*6` matrix stride; the `.rdata` orientation tables
`DAT_10031fd8..0x10032028`; direction-bit table `DAT_10031380`; the transit type-byte values and
bit meanings; the 4 occupant type ids `0x2fb2/0x2fc6/0x3048/0x3049` → masks
`0x11/0x14/0x18/0x3c` (`0x10005983`).

Also hard-coded and worth knowing: **only 4 of the 6 networks can bridge.** `FUN_10017f98`
builds 4 `*_Bridges.txt` paths — ROAD, RAIL, HWAY, POWR. **SUBW and PIPE have no bridges file**
`[CONFIRMED @ 0x10017f98:210,256,300,410]`.

### Graphics
Piece **ids** are hard-coded; the **art** those ids resolve to comes through the resource service
and lives in the `.DAT` content. No `.dat`/exemplar key carrying a *network type* field was
located in any module — **`[UNCERTAIN]`**, missing evidence is a parsed `SYS.PAK` exemplar dump.

## 6. What is actually achievable, ranked by evidence

1. **Re-skin a network — game-verified.** `verify/sprite_mod_test/RESULTS.md`: sprite replacement
   on `Apps/Res/Sprites/00000005_Roads.DAT` (15,172,185 B, 6,676 pixel records) rendered the
   whole road network red, then with authored stripes, geometry unchanged. Control held: the
   elevated rail line was unaffected, so rail art is not in `Roads.DAT`.
2. **Retune per-network costs** — `STTraffic.INI` (`TripCellCostBaseRoad=4`, `Highway=2`,
   `MaxEfficiencyRoads=120`, `OptimalMonthlyFundingCostPerRoad=2` / `PerHighway=30`) via
   `syspak_mod.py --set`. Writer is C4 and the *mechanism* is game-verified, but
   **`[UNCERTAIN]`: no individual `STTraffic.INI` key has been shown to move traffic in-game.**
   The loaders prove the keys are read, not that a given key has a visible effect.
3. **Retile an existing network** — **gate passed, game-verified 2026-08-23.** The files are read
   loose from `Apps\Res\TilingRules\` at startup (48 of the 68; 13 are dead and 7 are lazy
   `Landfill*`), and their **contents are parsed into engine records**: cutting
   `ROAD_GRND_Set.txt` from 109 ids to 1 dropped the per-id append count `0x1001b456` from
   **448 to 340**, exactly the −108 predicted, with the per-file control `0x1001746e` unmoved at
   7 (`verify/tilingrules_read_test/RESULTS.md`). Still **untooled**, and the rule-opcode grammar
   for `*_SimpleRules` / `*_ComplexRules` is still undocumented. Whether the records change
   *rendered* behaviour is open, blocked on `U-068`.

   Correction from that run: `sc3_ntwrk_parse_set_line` @ `0x1001746e` is **misnamed** — it is
   called once per Set **file** (7 unrolled call sites in `FUN_10016d87`), and the `strtok` loop is
   inside it. The per-id record append is its callee `FUN_1001b456`, which has exactly one call
   site in the module.
4. **New piece id inside an existing network** — data-shaped at every hop (`*_GRND_Set.txt` id
   list → rule tables → `Occupant.ini` `[OccupantKeys]` row → `OccupantAttribs*.IXF` props
   `0x64`/`0x66`/`0x67` → `Roads.DAT` frame table + pixels). Every hop has a reader, but **two
   hops have no writer**: `syspak_mod.py` only sets existing keys (no add-key path, `--pad`
   refuses to lengthen), and `.IXF` record *insertion* is untested. Nobody has attempted it.

A true 7th network is an exe/DLL patch project (`re/tools/pe_patch.py` is the existing lever).
This is why SC4 needed a rewritten network layer rather than an extension of this one.

## 7. Supersedes

These notes are now **stale on the points listed** and should be read with this file:

- `SIMNTWRK.md` — netType→name binding marked OPEN. **Closed, §1.**
- `SIMNTWRK_CLUSTER2.md` — "which physical network each netType denotes … is not
  string-labelled". **Closed, §1.**
- `SIMTRANSIT_CLUSTER1.md` / `SIMTRANSIT_CLUSTER2.md` — type→mode naming `[UNCERTAIN]`.
  **Closed, §4.**

## 8. Tracker entries proposed, NOT applied

Written as a new file per the single-writer contract in `COORDINATION.md`; a concurrent harness
session was live at the time of writing. The parent orchestrator should merge:

- **U-071** — netType `8` at `0x10014807` (§3). **Filed 2026-08-22.**
- **U-072** — transit type byte `3`, distinct network or road alias (§4). **Filed 2026-08-22.**
- **U-073** — whether any exemplar property carries a network-type field (§5). **Filed 2026-08-22.**

(These were drafted as U-068/069/070; the rendering session took those ids first. Renumbered
before filing.)
- `functions.csv` — the netType→network names in §1 are promotable evidence for the 7 layer
  registration functions and the 11 dispatch sites.
