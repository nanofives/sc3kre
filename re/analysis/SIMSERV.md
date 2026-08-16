# SIMSERV.DLL — GZCOM city-services director (S9)

_RE pass: read-only over `re/ghidra_export_simserv/functions/` (1344 decompiled bodies).
All addresses are Ghidra VAs in this module's `0x10000000` image. `[CONFIRMED @ 0xADDR]`
= present in the decompilation; `[UNCERTAIN]` = inference, with the missing witness named._

## 1. Purpose

SIMSERV.DLL is the **city-services simulation module**, not a fire-only module. Its GZCOM
director registers **seven** classes that together implement the paired
generation/response subsystems for **fire, crime, and public safety**: four grid *layers*
(`SC3FireLayer`, a `FlammabilityLayer`, a police/dispatch layer keyed by `SC3Police.INI`,
a crime layer keyed by `SC3Crime.INI`) and three *building exemplars* (`FireStation`,
`PoliceStation`, and a jail/prison exemplar keyed on `InmateCapacity`/`MonthlyUpkeep`).
The identity is grounded in the module's own INI-path and section strings —
`\Sys\SC3FireLayer.INI`, `FlammabilityLayer`, `\Sys\SC3Police.INI`, `\Sys\SC3Crime.INI`,
`FireStation`, `PoliceStation` — each consumed by a per-subsystem tuning loader that reads
named keys from `SC3Tune.INI` / `SYS.PAK` and stores them in module-static tunables. The
fire subsystem is the most fully realized in code (radial coverage stamping, a time-sliced
fire-spread scan, ordinance-modulated flammability); police/crime share the same tuning
scaffold but their sim bodies were not read in this pass.

## 2. Director + registrations

**Entry chain (the standard GZCOM recipe holds exactly):**

| Step | RVA | Note |
|---|---|---|
| PE export `GZDllGetGZCOMDirector` | `0x100135fd` | guarded one-shot; returns `&DAT_100249c0` (the static director) `[CONFIRMED @ 0x100135fd]` |
| duplicate accessor (same body) | `0x100103fb` | `[CONFIRMED @ 0x100103fb]` |
| director ctor | `0x10010426` | sets vtables `PTR_FUN_1001f790` / `PTR_LAB_1001f764`, then 7× register `[CONFIRMED @ 0x10010426]` |
| `register_class(this,clsid,factory,0)` | `0x10013983` | inserts `{clsid,factory,0}` into the map at **director+0x14** via `FUN_10013c2a` `[CONFIRMED @ 0x10013983]` |

**Seven registered classes** `[CONFIRMED @ 0x10010426:20-26]`. Each factory does
`operator_new(size)` + ctor and returns `object + N` (a sub-interface pointer). Class
identity is attached from the tuning loader whose name-string anchor sits in the **same
contiguous address block** as the ctor — a co-location inference, marked `[UNCERTAIN]`
where the GZCLSID itself carries no name.

| GZCLSID | factory RVA | ctor RVA | `operator_new` | returns | class (evidence) |
|---|---|---|---|---|---|
| `0x20a7ae7f` | `0x100104e3` | `0x10005f9a` | `0xe0` (224) | obj+0x1c | Crime layer — `[UNCERTAIN]`, co-located with `SC3Crime.INI` loader `0x100062af` |
| `0x61448030` | `0x10010521` | `0x1000c3e6` | `0x54` (84) | obj+0x10 | `FlammabilityLayer` — `[UNCERTAIN]`, co-located with `FlammabilityLayer` loader `0x1000c126` |
| `0x00abf2ec` | `0x1001055c` | `0x1000d7b8` | `0xf0` (240) | obj+0x1c | Police layer — `[UNCERTAIN]`, co-located with `SC3Police.INI` loader `0x1000dab0` |
| `0xa0f42214` | `0x1001059a` | `0x10009b53` | `0xe0` (224) | obj+0x1c | `SC3FireLayer` — `[UNCERTAIN]`, co-located with `SC3FireLayer.INI` loader `0x10009df5` |
| `0x40fc7753` | `0x100105d8` | `0x10001020` | `0x40` (64) | obj+0x08 | `FireStation` exemplar — reads `[FireStation]` `[CONFIRMED @ 0x10001020]` |
| `0x210d4d78` | `0x10010613` | `0x10004426` | `0x40` (64) | obj+0x08 | `PoliceStation` exemplar — reads `[PoliceStation]` `[CONFIRMED @ 0x10004426]` |
| `0x22ee7a5b` | `0x1001064e` | `0x1000357e` | `0x3c` (60) | obj+0x08 | jail/prison exemplar — reads `InmateCapacity`/`MonthlyUpkeep` `[CONFIRMED @ 0x1000357e]` |

Class-name strings literally present in the module: `SC3FireLayer.INI`
`[CONFIRMED @ 0x10009df5:39]`, `FlammabilityLayer` `[CONFIRMED @ 0x1000c126:54]`,
`SC3Police.INI` `[CONFIRMED @ 0x1000dab0:42]`, `SC3Crime.INI`
`[CONFIRMED @ 0x100062af:55]`, `FireStation` `[CONFIRMED @ 0x10001020:73]`,
`PoliceStation` `[CONFIRMED @ 0x10004426:73]`. No `SC3PoliceLayer`/`SC3CrimeLayer`
literal exists — those layers are keyed by INI filename + section `TuningParameters`.

## 3. Key subsystems (fire, read to C2)

The fire subsystem operates on a base grid layer reached at **`object - 0x1c`** (the
factory-returned pointer is `ctor+0x1c`, so the sim methods subtract it back to the C++
base). Grid access is through a vtable: `+0x0c`=width, `+0x10`=height, `+0x34`=read cell,
`+0x3c`=write cell, `+0x90`=lock/unlock pair (`+4` lock, `+8` unlock).

- **`0x1000b36a` — radial coverage/effect brush.** `(this=grid, coord[4] bbox, radius,
  effectCenter, effectEdge)`. Clamps a square bbox to grid dims, then for every cell whose
  Euclidean distance (`sqrt`→`floor`, rounded with `_DAT_1001e3c8`) ≤ radius, linearly
  interpolates the effect from `effectCenter` at r=0 to `effectEdge` at r=radius, adds it to
  the current cell, **divides by 0x10 (16)**, and clamps to `[0, 0xff]`. `[CONFIRMED @ 0x1000b36a]`
- **`0x1000adf5` — coverage recompute / repaint.** Iterates the station list (`this+0x18`),
  summing capacity into `this+0x98` and toggling flag `this+0x9c`; then iterates
  `this+0x14` and the active-fire list (`this+0x48`), calling `0x1000b36a` for each with
  `DispatchRadius`/`DispatchEffect`. `[CONFIRMED @ 0x1000adf5]`
- **`0x1000a9c6` — add fire / place agent.** Walks two lists to compare counts; allocates a
  `0x2c`-byte agent (`operator_new`, vtables `PTR_FUN_1001f0ec`/`…1f0bc`/`…1ef74`), writes a
  message struct `{0x207edc0e, 0x57e, 0x32cc}` and dispatches it via the agent's vtable
  `+0x1c`; resolves a graphic via layer `+0x40` vtable `+0x13c`/`+0x48`; queries IID
  `0xc14f8955`; posts notification `(1,0x23,0,0,0)` to the service from `0x100175f8`; then
  stamps coverage with `+DispatchEffect`. `[CONFIRMED @ 0x1000a9c6]`
- **`0x1000abda` — remove fire.** Finds the `this+0x48` list node matching `(x,y)`,
  releases its agent/graphic (IID `0xc14f8955`), unlinks it, and un-stamps coverage with
  **negated** `DispatchEffect` (`-DAT_100243c3`). `[CONFIRMED @ 0x1000abda]`
- **`0x1000b61d` — fire-spread scan init.** Binds a layer (`param_1` vtable `+0x178` base,
  `+0x14c` sub-object), sets stride from `UpdatePeriod` (forced to 1 if 0), computes
  **cells-per-tick = width·height / (UpdatePeriod·16)** into `this+0x18`, and seeds the scan
  cursor from tables `DAT_100243d0`/`DAT_100243d4`. `[CONFIRMED @ 0x1000b61d]`
- **`0x1000b6f7` — fire-spread tick (per active cell).** For an un-ignited cell: draws a
  random via `FUN_100134fc(...,10000)`, and if below the ignition value ignites (sets
  `+0xc4`, posts message `0x032a40a4` to the scheduler `0x1001325b`). For a burning cell:
  increments duration `+0xc8`, extinguishes once `duration > MaxStrikeDuration`
  (`DAT_100243c8`) or heat `+0xb8 ≥ 100`. Spreads across a 4×4 (`0x10`) neighbor block,
  scaling heat by `StrikeEfficiency` (`·DAT_100243c6/100`), accumulating burn stats at
  `+0xcc/+0xd0/+0xd4`, stepping the cursor by `0x10` per cell and wrapping rows via the
  16-entry `DAT_100243d0/DAT_100243d4` phase tables. `[CONFIRMED @ 0x1000b6f7]`
- **`0x1000c608` — per-tile flammability.** Reads a building's base flammability
  (`this+0x30` vtable `+0x7c`→`+0x80`→`+0x70`), then applies ordinances via the service at
  `this+0x28`: `+LeafBurningBanOrdEffect` if ordinance `0x22bf1e35` active,
  `+SmokeDetectorsOrdEffect` if `0x62bf1daa` active, `-NoWaterEffect` if the tile fails the
  water check (`this+0x2c` vtable `+0x48`). Final flammability =
  `base − base·effect/100` when `effect < 100`, clamped to `0xff`. `[CONFIRMED @ 0x1000c608]`
- **`0x1000af08` — fire-station shortfall/priority score.** Returns `10000` if flag
  `+0xa8` set; else if the station has coverage (`FUN_1000b936(+0x18)≠0`), funding
  `+0x9c < MinAcceptableFunding` (`DAT_100243c4`), and local flammability
  `> MaxAcceptableFlam` (`DAT_100243c5`), returns `(MinAcceptableFunding − funding)²`;
  otherwise `0`. `[CONFIRMED @ 0x1000af08]`

**GZCOM service singletons (guarded one-shot getters):**
- `0x1001755e` → resource/IO service (`DAT_10024ac4`); vtable `+0x50` opens a named
  stream (`\Sys\…INI`, `\Sys\SYS.PAK`), `+0x34` yields the sub-service returned by
  `0x100175f8`. `[CONFIRMED @ 0x1001755e]`
- `0x1001325b` → message/scheduler service (`DAT_10024a14`); vtable `+0x10` posts a
  message record. `[CONFIRMED @ 0x1001325b]`

## 4. Data / tunables (all raw values)

**Fire layer** — `\Sys\SC3FireLayer.INI` §`TuningParameters`, loader `0x10009df5`:

| key | global | note |
|---|---|---|
| `UpdatePeriod` | `DAT_100243c0` | **defaults to `0x1e` (30)** if parsed 0 `[CONFIRMED @ 0x10009df5:66-68]` |
| `DispatchRadius` | `DAT_100243c2` | `[CONFIRMED @ 0x10009df5:88]` |
| `DispatchEffect` | `DAT_100243c3` | `[CONFIRMED @ 0x10009df5:108]` |
| `MinAcceptableFunding` | `DAT_100243c4` | `[CONFIRMED @ 0x10009df5:128]` |
| `MaxAcceptableFlam` | `DAT_100243c5` | `[CONFIRMED @ 0x10009df5:148]` |
| `StrikeEfficiency` | `DAT_100243c6` | `[CONFIRMED @ 0x10009df5:168]` |
| `MaxStrikeDuration` | `DAT_100243c8` | `[CONFIRMED @ 0x10009df5:182]` |

**Flammability** — `\Sys\SC3Tune.INI` + `\Sys\SYS.PAK` §`FlammabilityLayer`, loader `0x1000c126`:
`LeafBurningBanOrdEffect`→`DAT_100244dc`, `SmokeDetectorsOrdEffect`→`DAT_100244dd`,
`NoWaterEffect`→`DAT_100244de` `[CONFIRMED @ 0x1000c126:68,88,108]`.

**Fire station exemplar** — §`FireStation`, loader `0x10001020`:
`OptimalCoverageRadius`, `OptimalMaxCoverage`, `OptimalMinCoverage`, `OptimalMonthlyUpkeep`,
`MaxEfficiency`, `MysticalE` `[CONFIRMED @ 0x10001020]`.

**Police station exemplar** — §`PoliceStation`, loader `0x10004426`: same six keys **plus**
`OppressionThreshold` `[CONFIRMED @ 0x10004426]`.

**Prison exemplar** — §`<DAT_10024284>` (section name is an unnamed rdata string), loader
`0x1000357e`: `InmateCapacity`→`DAT_1002426c`, `MonthlyUpkeep`→`DAT_10024270`; one-shot
guarded by `DAT_1002494c`; object field `+0x38` (`param_1[0xe]`) initialized to
`MonthlyUpkeep` `[CONFIRMED @ 0x1000357e]`.

**Police layer** — `\Sys\SC3Police.INI` §`TuningParameters`, loader `0x1000dab0`:
`UpdatePeriod`, `DailyJailReleaseRate`, `ConvictionRate`, `NoJailPenalty`, `DispatchRadius`,
`DispatchEffect`, `MaxJailOvercrowding`, `MinAcceptableFunding`, `MaxAcceptableCrime`,
`StrikeEfficiency`, `MaxStrikeDuration` `[CONFIRMED @ 0x1000dab0]`.

**Crime layer** — `\Sys\SC3Crime.INI` §`TuningParameters`, loader `0x100062af`:
`AgentIDModifiers`, `UpdatePeriod`, `PoliceFactor`, `YouthCurfewOrdEffect`,
`GamblingOrdEffect`, `JrSportsOrdEffect`, `NeighborhoodWatchOrdEffect`,
`ConservationCorpsOrdEffect` `[CONFIRMED @ 0x100062af]`.

**Tables / magic constants:**
- `DAT_100243d0` / `DAT_100243d4` — a 16-entry table of `(x,y)` step pairs, indexed by a
  0..0xf phase byte, driving the time-sliced grid scan `[CONFIRMED @ 0x1000b6f7:101-103, 0x1000b61d:32-34]`.
- `_DAT_1001e3c8` — `double` rounding bias added before `floor()` in the distance calc `[CONFIRMED @ 0x1000b36a:71]`.
- `0x2c` — fire-agent object size `[CONFIRMED @ 0x1000a9c6:75]`.

## 5. Cross-module edges

All are late-bound through GZCOM (GZCLSID/IID literals or service vtables); none is a
static import.

| id (raw) | kind | site | meaning (mechanical) |
|---|---|---|---|
| `0xc14f8955` | IID (QueryInterface) | `0x1000a9c6`, `0x1000abda` | interface queried on the fire sprite/agent object |
| `0x207edc0e` | message/type id | `0x1000a9c6` | header of the `{id,0x57e,0x32cc}` record dispatched to the agent (`+0x1c`) |
| `0x032a40a4` | message id | `0x1000b6f7` | posted to scheduler `0x1001325b` (`+0x10`) on ignition |
| `0x23` (35) | notification id | `0x1000a9c6` | `(1,0x23,0,0,0)` to sub-service from `0x100175f8` |
| `0x22bf1e35` | ordinance GZCLSID | `0x1000c608` | "leaf-burning ban" ordinance queried on ordinance service (`this+0x28` `+0x0c`) |
| `0x62bf1daa` | ordinance GZCLSID | `0x1000c608` | "smoke detectors" ordinance, same service |

The resource service (`0x1001755e`) reads `\Sys\*.INI` and `\Sys\SYS.PAK` — the shared
tuning/resource module. The scheduler service (`0x1001325b`) is the sim message bus.
`0x57e`/`0x32cc` in the agent record are unlabeled ids (sprite/exemplar) — raw values only.

## 6. Classification (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x100135fd,gzcom-director,C2,sc3_serv_get_gzcom_director,"PE export; guarded one-shot returns &DAT_100249c0 @0x100135fd"
0x100103fb,gzcom-director,C2,sc3_serv_get_director_dup,"identical body to 0x100135fd @0x100103fb"
0x10010426,gzcom-director,C2,sc3_serv_director_ctor,"sets director vtables + 7x register_class @0x10010426"
0x10013983,gzcom-director,C2,sc3_serv_register_class,"inserts {clsid,factory,0} into map at director+0x14 @0x10013983"
0x100104e3,gzcom-factory,C2,sc3_crime_factory_layer,"operator_new(0xe0)+ctor 0x10005f9a, returns obj+0x1c; clsid 0x20a7ae7f"
0x10010521,gzcom-factory,C2,sc3_flam_factory_layer,"operator_new(0x54)+ctor 0x1000c3e6, returns obj+0x10; clsid 0x61448030"
0x1001055c,gzcom-factory,C2,sc3_police_factory_layer,"operator_new(0xf0)+ctor 0x1000d7b8, returns obj+0x1c; clsid 0x00abf2ec"
0x1001059a,gzcom-factory,C2,sc3_fire_factory_layer,"operator_new(0xe0)+ctor 0x10009b53, returns obj+0x1c; clsid 0xa0f42214"
0x100105d8,gzcom-factory,C2,sc3_fire_factory_station,"operator_new(0x40)+ctor 0x10001020, returns obj+0x08; clsid 0x40fc7753"
0x10010613,gzcom-factory,C2,sc3_police_factory_station,"operator_new(0x40)+ctor 0x10004426, returns obj+0x08; clsid 0x210d4d78"
0x1001064e,gzcom-factory,C2,sc3_police_factory_jail,"operator_new(0x3c)+ctor 0x1000357e, returns obj+0x08; clsid 0x22ee7a5b"
0x10005f9a,crime-layer,C2,sc3_crime_layer_ctor,"0xe0 layer ctor, list-node init; co-located with SC3Crime loader @0x10005f9a"
0x1000c3e6,flammability-layer,C2,sc3_flam_layer_ctor,"0x54 ctor, dual vtable set; co-located with FlammabilityLayer loader @0x1000c3e6"
0x1000d7b8,police-layer,C2,sc3_police_layer_ctor,"0xf0 layer ctor, 4 list heads + FUN_100134cb/13eb5; co-located with SC3Police loader @0x1000d7b8"
0x10009b53,fire-layer,C2,sc3_fire_layer_ctor,"0xe0 layer ctor, list heads + FUN_100134cb/13eb5; co-located with SC3FireLayer loader @0x10009b53"
0x10001020,fire-station,C2,sc3_fire_load_station_exemplar,"reads [FireStation]: Optimal{Coverage,Max,Min,Upkeep},MaxEfficiency,MysticalE @0x10001020"
0x10004426,police-station,C2,sc3_police_load_station_exemplar,"reads [PoliceStation]: same six + OppressionThreshold @0x10004426"
0x1000357e,police-jail,C2,sc3_police_load_jail_exemplar,"reads InmateCapacity->DAT_1002426c, MonthlyUpkeep->DAT_10024270; guard DAT_1002494c @0x1000357e"
0x10009df5,fire-layer,C2,sc3_fire_load_tuning,"SC3FireLayer.INI [TuningParameters] -> DAT_100243c0..c8; UpdatePeriod default 0x1e @0x10009df5"
0x1000c126,flammability-layer,C2,sc3_flam_load_tuning,"SC3Tune.INI/SYS.PAK [FlammabilityLayer] -> DAT_100244dc..de @0x1000c126"
0x1000dab0,police-layer,C2,sc3_police_load_tuning,"SC3Police.INI [TuningParameters], 11 keys incl DailyJailReleaseRate/ConvictionRate @0x1000dab0"
0x100062af,crime-layer,C2,sc3_crime_load_tuning,"SC3Crime.INI [TuningParameters], 8 keys incl PoliceFactor/ordinance effects @0x100062af"
0x1000b36a,fire-coverage,C2,sc3_fire_stamp_coverage_radial,"radial brush: dist<=radius, lerp center..edge, /0x10, clamp 0..0xff @0x1000b36a"
0x1000adf5,fire-coverage,C2,sc3_fire_recompute_coverage,"sums stations at +0x98, restamps fires+coverage via 0x1000b36a @0x1000adf5"
0x1000a9c6,fire-agent,C2,sc3_fire_add_fire,"alloc 0x2c agent, msg {0x207edc0e,0x57e,0x32cc}, IID 0xc14f8955, notify 0x23, stamp +effect @0x1000a9c6"
0x1000abda,fire-agent,C2,sc3_fire_remove_fire,"find list node by (x,y), release IID 0xc14f8955, unstamp -DispatchEffect @0x1000abda"
0x1000b61d,fire-spread,C2,sc3_fire_scan_init,"cells/tick = w*h/(UpdatePeriod*16); seed cursor from DAT_100243d0/d4 @0x1000b61d"
0x1000b6f7,fire-spread,C2,sc3_fire_spread_tick,"ignite via rand<val -> msg 0x032a40a4; extinguish at MaxStrikeDuration/heat>=100; StrikeEfficiency scale @0x1000b6f7"
0x1000c608,flammability-layer,C2,sc3_flam_compute_tile,"base flam +/- ordinances 0x22bf1e35/0x62bf1daa/water; flam-base*eff/100 clamp 0xff @0x1000c608"
0x1000af08,fire-station,C2,sc3_fire_station_priority,"10000 if flag; else (MinAcceptableFunding-funding)^2 when under-funded & over-flam @0x1000af08"
0x1001755e,gzcom-service,C2,sc3_serv_get_resource_service,"guarded singleton DAT_10024ac4; +0x50 opens named stream @0x1001755e"
0x100175f8,gzcom-service,C2,sc3_serv_get_notify_service,"resource-service +0x34 sub-service; target of (1,0x23,..) @0x100175f8"
0x1001325b,gzcom-service,C2,sc3_serv_get_message_bus,"guarded singleton DAT_10024a14; +0x10 posts message @0x1001325b"
```

## 7. OPEN (undetermined + missing evidence)

- **GZCLSID→class-name binding is inference.** The four layer classes are attached to
  their names only by address co-location with a name-anchored tuning loader; the loaders
  themselves have **no direct-call xref inside SIMSERV** (they are virtual methods reached
  through the `PTR_FUN_*` vtables). Missing witness: the vtable dumps for
  `PTR_FUN_1001ec2c` / `…1ee74` / `…1f4e8` / `…1f2c8` (director-side layer vtables) to prove
  which vtable slot points at which loader. Needs live-Ghidra vtable read or the `.rdata`
  export of those `PTR_` tables.
- **Police and crime sim bodies unread.** Only their tuning loaders were read; the dispatch
  / jail-population / crime-generation update methods (the consumers of `SC3Police.INI` /
  `SC3Crime.INI` tunables) were not located in this pass. Missing: an xref sweep on the
  police/crime `DAT_` globals (parallel to the fire `DAT_100243c0..c8` sweep already done).
- **Numeric tunable values not recovered.** The shipped values of every key live in
  `SC3Tune.INI` / `SC3FireLayer.INI` / `SC3Police.INI` / `SC3Crime.INI` / `SYS.PAK`, parsed
  at runtime — they are **not** constants in the binary (only the parse targets are).
  Missing: those game data files (candidate: `re/data/ixf_text.csv` for the labels, and the
  `\Sys\*` files themselves for the numbers).
- **`0x57e` / `0x32cc`** in the fire-agent message record and the prison section-name string
  `DAT_10024284` are unlabeled; reported as raw values. Missing: the rdata string at
  `0x10024284` and a consumer of `0x57e`/`0x32cc` (likely a sprite/exemplar id in another
  module).
- **Service GZCLSIDs not captured.** `0x1001755e` / `0x1001325b` return cached singletons;
  the GZCLSID/IID used to obtain them lives in the un-read init helpers `FUN_10017589` /
  `FUN_1001330b`. Missing: read those two helpers to name the external services.
- **`FUN_1000b936`** (used as a boolean "has coverage/stations" in `0x1000af08` /
  `0x1000b6f7`) was not read; treated mechanically as a nonzero-count test.
