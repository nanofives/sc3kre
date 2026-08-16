# STRTSIM.DLL — SC3StrtSimLayer (street / vehicle-traffic sim)

**Module:** `Apps\STRTSIM.DLL`, 233,472 bytes, GZCOM director plugin.
**Export decomp:** `re/ghidra_export_strtsim/functions/` (1,652 `.c` files).
**Load base in export:** `0x10000000` (addresses below are export/Ghidra VAs; RVA = addr − 0x10000000).
**Version resource:** `SimCity 3000`, `SC3U.EXE`, `2.0.949`, `Copyright © 1999 Maxis, Inc.` [CONFIRMED @ 0x10034148/0x1003424c].

## 1. Purpose

STRTSIM.DLL is the GZCOM plugin that hosts **SC3StrtSimLayer**, the module’s single
heavyweight layer object (a `0x27e0`-byte / 10,208-byte instance). Grounded in its
strings and code, it drives the on-street **vehicle / traffic** subsystem: it loads a
per-layer tuning file `\Sys\SC3StrtSimLayer.INI` out of `\Sys\SYS.PAK`
[CONFIRMED @ 0x10014796:44-52], reads the tunable `MaxMarinaToBoatDistance` and the
tunable group `MiscStrtSimTunables` [CONFIRMED @ 0x10006066:64-66], and reads four
vehicle-roster keys — `KeyVehiclesForLowMemoryMachines`,
`EmergencyVehiclesForLowMemoryMachines`, `KeyVehiclesForHighMemoryMachines`,
`EmergencyVehiclesForHighMemoryMachines` — selecting the Low- or High-memory set from a
machine-tier byte [CONFIRMED @ 0x10014796:53-75]. It maintains two vehicle-GZCLSID
rosters (“key” = ordinary traffic vehicles, “emergency” vehicles), pre-caches those
vehicle resources on a background alertable thread, and picks emergency vehicles at
random from the roster. It also parses a text table of per-country calendars / seasonal
“modes” with packed dates (holiday scheduling) [CONFIRMED @ 0x10009b35]. Day-of-week and
`%2u/%2u/%2u` date-format strings live in the module [CONFIRMED @ 0x10032820-0x100328ac].

## 2. Director + registrations

Standard GZCOM recipe, fully recovered:

```
GZDllGetGZCOMDirector  0x10024389   guarded singleton, returns &DAT_10032c08
   -> director ctor    0x10006643   FUN_1002438e(base ctor) then 13x register_class
   -> register_class   0x10024716   inserts {clsid, factory, 0} into map at director+0x14
```

- `GZDllGetGZCOMDirector` [CONFIRMED @ 0x10024389]: one-shot guard `DAT_10032c4c & 1`,
  calls director ctor `FUN_10006643(&DAT_10032c08)`, registers an atexit handler
  `LAB_10006baf`, returns `&DAT_10032c08` (the static director).
- Base director ctor `FUN_1002438e` [CONFIRMED @ 0x1002438e]: installs vtables
  `PTR_LAB_1002d3d8`/`PTR_FUN_1002d364`, zero-inits fields, builds the class map holder.
- Director ctor `FUN_10006643` [CONFIRMED @ 0x10006643]: sets vtables
  `PTR_FUN_1002a978` / `PTR_LAB_1002a94c`, then makes **13** `register_class` calls.

### Registered classes (13)

Each factory does `operator_new(size)` + a ctor. `FUN_100067a1` returns `object+0x14`
(a sub-interface base), matching the recipe’s “may return object+N” trap; the rest return
the object head.

| # | GZCLSID | factory RVA | alloc size | ctor / init | notes |
|---|---|---|---|---|---|
| 1 | `0x22498f2c` | `0x1000676c` | `0x27e0` (10208) | `FUN_1001245b` | **SC3StrtSimLayer** — the main layer |
| 2 | `0x21fd6eef` | `0x100067a1` | `0x2c` (44) | `FUN_1000959b`, returns obj+0x14 | sub-interface object (2 vtables) |
| 3 | `0x025c6d8b` | `0x100067dc` | `0xc` (12) | `FUN_10006a18` | small helper object |
| 4 | `0x820c0620` | `0x10006872` | `0xc` | `FUN_10006a87` | small helper object |
| 5 | `0x625c758f` | `0x100068a4` | `0xc` | `FUN_10006aac` | small helper object |
| 6 | `0xc22b517c` | `0x100068d6` | `0xc` | `FUN_10006ad1` | small helper object |
| 7 | `0x622b7f03` | `0x10006908` | `0xc` | `FUN_10006af6` | small helper object |
| 8 | `0xc22b54d7` | `0x1000693a` | `0xc` | `FUN_10006b1b` | small helper object |
| 9 | `0xc25c2bb0` | `0x1000696c` | `0xc` | `FUN_10006b40` | small helper object |
| 10 | `0x225c563d` | `0x1000699e` | `0x8` (8) | inline: vtable `PTR_LAB_1002a9c0`, [1]=0 | smallest object |
| 11 | `0x225c61e8` | `0x100069b8` | `0xc` | `FUN_10006b65` | small helper object |
| 12 | `0x42cefd0b` | `0x1000680e` | `0xc` | `FUN_10006a3d` | small helper object |
| 13 | `0x42dfcc92` | `0x10006840` | `0xc` | `FUN_10006a62` | small helper object |

All [CONFIRMED @ 0x10006643:20-32]; sizes/ctors [CONFIRMED @ each factory RVA].

Class-name **string** anchor: `\Sys\SC3StrtSimLayer.INI` [CONFIRMED @ 0x10032494] is the
only `*StrtSim*` name in the module (matches MODULE_MAP.md). It names the layer’s config
loader, not a vtable. [UNCERTAIN] which GZCLSID above is the *class id* of SC3StrtSimLayer
vs its sub-interfaces — the ids are only present as these dwords, resolvable by matching
against the SYS.PAK/CitySim.ini id registry (not in this module).

## 3. Key subsystems

**`sc3_strtsim_layer_ctor` `FUN_1001245b` @ 0x1001245b [C2].** SC3StrtSimLayer ctor.
Installs three vtables (`PTR_LAB_1002c6b0/688/674`, later overwritten with
`PTR_FUN_1002c600` / `PTR_LAB_1002c5d8` / `PTR_LAB_1002c5c4`) [CONFIRMED @ :19-21,:77-79].
Zero-inits the large instance, seeds flags: `+0x32=1`, `+0x33=1` (two enabled bytes)
[CONFIRMED @ :32-33], `[0x9f2]=5` [CONFIRMED @ :67]; builds a small self-linked list node
via `FUN_10002ea6(0xc)` whose `+0`/`+4` both point back at itself (empty circular list)
[CONFIRMED @ :70-74]; constructs four sub-objects via `FUN_1001594b` at `+0xcc/+0xd8/
+0xe4/+0xf0` [CONFIRMED @ :47-53]; final loop zeroes `0x992` (2450) dwords from `+0x160`
[CONFIRMED @ :112-116]. Callee `FUN_10002ea6` (allocator), `FUN_10021847`, `FUN_1001594b`.

**`sc3_strtsim_layer_init` `FUN_10014796` @ 0x10014796 [C2].** Layer init (no direct
caller in the module → reached through a vtable slot). Opens `\Sys\SC3StrtSimLayer.INI`
from `\Sys\SYS.PAK` via the resource service (`FUN_10026443` obj, method `+0x50` = key
builder) [CONFIRMED @ :42-52]. Reads machine tier: `if (*(short*)(iVar4+2) < 0x31)`
selects the **Low**-memory vehicle keys, else the **High**-memory keys
[CONFIRMED @ :54-75], registering INI callbacks `FUN_10011cd0` (key vehicles) and
`FUN_10011cab` (emergency vehicles) via `FUN_100269a6`. Then runs the module’s ten
table-init routines (`FUN_1000c3c9,1001d060,10002336,10007434,1000f9ac,100056f4,
1000ea6f,10008314,10006066,10010182`) [CONFIRMED @ :79-88]. Allocates a `0x1d00` object
`FUN_10013397(0x1d00)` → `DAT_10033064` and calls its `+4` init [CONFIRMED @ :89-92].
Finally resolves six service handles through `DAT_10033048` method `+0x14` with IID
`0x80199683` from GZCLSID pairs and caches them:
`0x21fd6eef/0x21fd8e4c`→`DAT_1003304c`, `0x625c6cc7/0xa25c6d40`→`DAT_10033050`,
`0x22cefd99/0x62cefddb`→`DAT_10033054`+`DAT_10033058`,
`0x62dfccec/0x62dfcd34`→`DAT_1003305c`+`DAT_10033060` [CONFIRMED @ :93-118].

**`sc3_strtsim_load_misc_tunables` `FUN_10006066` @ 0x10006066 [C2].** Re-opens
`SC3StrtSimLayer.INI` + `SYS.PAK`, queries a service (clsid `0x625c6cc7/0xa25c6d40`,
sub-key `0x400` then `0x401`) storing to `DAT_10032bf8`/`DAT_10032bfc`
[CONFIRMED @ :45-52], then reads tunable group `MiscStrtSimTunables` / key
`MaxMarinaToBoatDistance` [CONFIRMED @ :64-66]; on success squares the value:
`DAT_10032454 = iVar4 * iVar4` [CONFIRMED @ :76-77] (max marina→boat distance stored as a
squared distance). Callee `FUN_10024f79` (string→int).

**`sc3_strtsim_parse_country_schedule` `FUN_10009b35` @ 0x10009b35 [C2].** Text-table
parser. Reads `NumCountries:%d` [CONFIRMED @ :58-60]; per country reads `Country:%s`
(or the default token `:holidays` @ 0x100324c4 when not in country mode)
[CONFIRMED @ :83,:101]; then `NumModes: %d` [CONFIRMED @ :109]. Allocates
`NumModes * 0x14` bytes [CONFIRMED @ :110]; each mode row is `%d %d %d %d`
[CONFIRMED @ :118] with field `+8` scaled by float `_DAT_1002b638` [CONFIRMED @ :120].
The first row’s date is packed: when `local_18 >= 0xf69b5` (1,010,101), it is split
`/1000000`, `%1000000/10000`, `%10000/100`, `%100` and re-packed as
`((a<<8|b)<<8|c)<<8|d` [CONFIRMED @ :128-133] → a byte-packed Y/M/D date; later rows are
cumulative deltas [CONFIRMED @ :140]. Each mode owns a sub-array of `count<<4`
(0x10-byte) records, each parsed `%d %d %d %d` with a running cumulative first field
[CONFIRMED @ :146-175]. Result handed to `FUN_1000a1c5`. This is the seasonal /
holiday-calendar table used to schedule traffic behaviour by country.

**`sc3_strtsim_ini_add_key_vehicle` `FUN_10011cd0` @ 0x10011cd0 [C2]** and
**`sc3_strtsim_ini_add_emergency_vehicle` `FUN_10011cab` @ 0x10011cab [C2].** INI
enumeration callbacks. Each takes the INI value string (vtable `+0x14`), converts it to a
numeric GZCLSID via `FUN_10024f79`, and pushes it into a vector — key vehicles →
`DAT_10032fb0`, emergency vehicles → `DAT_10032fc0` (via `FUN_10003f6f`)
[CONFIRMED @ both :8-11].

**`sc3_strtsim_pick_random_emergency_vehicle` `FUN_10013124` @ 0x10013124 [C2].**
Count = `(DAT_10032fc4 - DAT_10032fc0) >> 2`; if 0 returns 0, else draws a random index
`FUN_10021878(this+0x78, count)` and returns `DAT_10032fc0[idx]` (a vehicle GZCLSID)
[CONFIRMED @ :9-18].

**`sc3_strtsim_preload_key_vehicles` `FUN_10011cf5` @ 0x10011cf5 [C2].** Background worker
loop over the key-vehicle roster `DAT_10032fb0..DAT_10032fb4`. Guarded by state
`DAT_10033068` (must equal 2, else resets `DAT_10033068=0`,`DAT_1003306c=1` and exits)
[CONFIRMED @ :25-29]. Per vehicle: enters critical section `0x10032f70`
(`FUN_1002544d`), looks the id up in cache map `DAT_10033020`; on miss, creates the object
via service `DAT_10033048` method `+0x14` (IID `0x80199683`, clsid `0xc25c2bf7/0x025c2c45`)
and inserts it [CONFIRMED @ :30-40]; leaves the critical section and sleeps
`FUN_1002517f(20000)` = `SleepEx(20ms, alertable)` [CONFIRMED @ :41-43]. A resource
pre-cache pass that yields the CPU between items.

**`sc3_strtsim_resolve_vehicle_class` `FUN_1001346f` @ 0x1001346f [C2].** Cache-or-create
for a vehicle class: probes map `DAT_10032fe0` by key `*(param_1+8)`; on miss creates via
`DAT_10033048` method `+0x14` (IID `0x80199683`) and inserts, on hit returns the cached
`+0x14` interface, then AddRefs it (`(**)(*obj+4)`) [CONFIRMED @ :11-23].

**`sc3_strtsim_init_msgid_table` `FUN_10002336` @ 0x10002336 [C2].** Builds a
handler/descriptor table (`DAT_10032a24…`) of function pointers
(`FUN_100014ca/10002814/10002c80/10001f02/10002a19/1000161c` + `LAB_*`)
[CONFIRMED @ :34-57] and derives ids by hashing the message constants
`0x4e2000-0x4e2003`, `0x4e2100-0x4e2103`, `0x4e2200-0x4e2203` through `FUN_1001346f`-style
map lookup `FUN_1001346f`… actually via `FUN_1001346f`’s sibling using clsid
`0xc25c74f2/0xa25c7520`, storing results to `DAT_100329b4`/`DAT_10032a90`
[CONFIRMED @ :60-79]. The `0x4e2xxx` values are the module’s message/notification ids
(raw; exact meaning not in this module).

**Table-init family** `FUN_1000c3c9` @ 0x1000c3c9, `FUN_1001d060` @ 0x1001d060,
`FUN_10007434` @ 0x10007434, `FUN_1000f9ac` @ 0x1000f9ac, `FUN_100056f4` @ 0x100056f4,
`FUN_1000ea6f` @ 0x1000ea6f, `FUN_10008314` @ 0x10008314 **[C2].** Each is a guarded
one-shot that zero-fills a static struct then plants vtable/handler function pointers
(e.g. `FUN_1000c3c9` guards on `DAT_10032dec`, plants `LAB_1000b423`,`LAB_1000bc13`,
`FUN_1000ad77`, then binds a service object via `FUN_1000104a` → method `+0x7c` → `0xfa2`
[CONFIRMED @ 0x1000c3c9:14-28]). These register the module’s serialization/message
handler descriptor tables. `FUN_1001d060` installs the largest table (≈18 handler slots
`LAB_1001b320…LAB_1001ac10`) and binds resource `0xfa2` [CONFIRMED @ 0x1001d060].

**`sc3_strtsim_resolve_clsid_table` `FUN_10010182` @ 0x10010182 [C2].** Loops over a
4-entry clsid table `DAT_1002c318` (stride 4, len 0x10), each queried via `FUN_100264e9`
service method `+0x14` (base clsid `0x625c6cc7/0xa25c6d40`, IID `0x80199683`), caching
handles into `DAT_10032ee0` (0 on failure) [CONFIRMED @ :17-32].

## 4. Data / tunables

Raw values, all [CONFIRMED]:

- **Config files:** `\Sys\SC3StrtSimLayer.INI` @ 0x10032494, `\Sys\SYS.PAK` @ 0x10032484.
- **Tunable group:** `MiscStrtSimTunables` @ 0x10032458; **key:** `MaxMarinaToBoatDistance`
  @ 0x1003246c (stored **squared** into `DAT_10032454` @ 0x10006066:77).
- **Vehicle rosters (INI keys):** `KeyVehiclesForLowMemoryMachines` @ 0x10032638,
  `EmergencyVehiclesForLowMemoryMachines` @ 0x10032610,
  `KeyVehiclesForHighMemoryMachines` @ 0x100325ec,
  `EmergencyVehiclesForHighMemoryMachines` @ 0x100325c4. Tier switch:
  `*(short*)(iVar4+2) < 0x31` (49) → Low set [CONFIRMED @ 0x10014796:54].
- **Roster vectors:** key vehicles `DAT_10032fb0`/`DAT_10032fb4`, emergency vehicles
  `DAT_10032fc0`/`DAT_10032fc4`; vehicle-class cache map `DAT_10032fe0`; preload cache map
  `DAT_10033020`; preload state `DAT_10033068`(==2 to run)/`DAT_1003306c`.
- **Schedule parser format strings:** `NumCountries:%d` @ 0x100324f8, `NumCountries:`
  @ 0x10032508, `Country:%s` @ 0x100324ec, `NumModes: %d` @ 0x100324dc, `:holidays`
  @ 0x100324c4, records `%d %d %d %d` @ 0x100324d0 (also `%d %d`, `%d %d %d`,
  `%d %d %d %d %d`, `%d %d %d %d %d %d` @ 0x1003243c-0x10032760). Date pack threshold
  `0xf69b5` (1010101); mode-field scale `_DAT_1002b638` (float).
- **Message ids:** `0x4e2000..0x4e2003`, `0x4e2100..0x4e2103`, `0x4e2200..0x4e2203`
  @ 0x10002336.
- **Calendar strings:** weekday names @ 0x10032820-0x1003285c; date formats `%2u/%2u/%2u`
  / `%2u.%2u.%2u` / `%2u-%2u-%2u` @ 0x10032894-0x100328ac.
- **Resource/type tags:** `gamecmd`, `cogamecmd`, `sc3agenttype`, `sc3typehierarchy`,
  `dbsegment`, `cores` @ 0x10032714-0x10032760.
- **Unlabelled table** @ 0x10032660: 63-byte ASCII `"$$$$%%%%%%%%&&&&&&&&''''''''$$$$,,,,--------........////////,,,,"`
  — [UNCERTAIN] purpose; report raw.
- **INI writer templates:** `\n[%s]\n`, `%s = %s\n`, `[%s]\n` @ 0x1003277c-0x10032794.

## 5. Cross-module edges

The layer never links other DLLs statically; it reaches the engine through two GZCOM
service singletons and creates objects by GZCLSID:

- **Service singletons:** `FUN_100264e9` @ 0x100264e9 (lazy `DAT_100333d0`) and
  `FUN_10026443` @ 0x10026443 (lazy `DAT_100333cc`); the cached factory handle
  `DAT_10033048` is fetched from `FUN_100264e9` [CONFIRMED @ 0x10014796:41].
- **IID used for every create/query:** `0x80199683` (method slot `+0x14`); path/key builder
  is method slot `+0x50` on the `FUN_10026443` service.
- **External GZCLSIDs referenced (create/query targets):** `0x21fd6eef/0x21fd8e4c`,
  `0x625c6cc7/0xa25c6d40`, `0x22cefd99/0x62cefddb`, `0x62dfccec/0x62dfcd34`
  (init handles), `0xc25c2bf7/0x025c2c45` (preloaded vehicle service),
  `0xc25c74f2/0xa25c7520` (msg-id hashing). Plus the 13 ids this module *registers*
  (section 2). [UNCERTAIN] which owning module each external id resolves to — not
  determinable inside this DLL.
- **Vehicle class objects** are created on demand and AddRef’d
  (`FUN_1001346f`/`FUN_10011cf5`), i.e. STRTSIM consumes vehicle/exemplar classes owned by
  the resource/exemplar subsystem.

## 6. Classification table (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x10024389,gzcom-director,C2,sc3_strtsim_get_gzcom_director,"PE export; guarded singleton returns &DAT_10032c08, calls ctor FUN_10006643 @0x10024389"
0x10006643,gzcom-director,C2,sc3_strtsim_director_ctor,"registers 13 classes via FUN_10024716; installs PTR_FUN_1002a978 @0x10006643"
0x1002438e,gzcom-director,C2,sc3_strtsim_director_base_ctor,"base ctor, vtables PTR_LAB_1002d3d8/PTR_FUN_1002d364, builds class map @0x1002438e"
0x10024716,gzcom-director,C2,sc3_strtsim_register_class,"thiscall; writes {clsid,factory,0} into map at this+0x14 @0x10024716"
0x1000676c,gzcom-factory,C2,sc3_strtsim_factory_layer,"new(0x27e0)+FUN_1001245b; clsid 0x22498f2c @0x1000676c"
0x100067a1,gzcom-factory,C2,sc3_strtsim_factory_subiface,"new(0x2c)+FUN_1000959b, returns obj+0x14; clsid 0x21fd6eef @0x100067a1"
0x100067dc,gzcom-factory,C2,sc3_strtsim_factory_c025c6d8b,"new(0xc)+FUN_10006a18; clsid 0x025c6d8b @0x100067dc"
0x1000680e,gzcom-factory,C2,sc3_strtsim_factory_c42cefd0b,"new(0xc)+FUN_10006a3d; clsid 0x42cefd0b @0x1000680e"
0x10006840,gzcom-factory,C2,sc3_strtsim_factory_c42dfcc92,"new(0xc)+FUN_10006a62; clsid 0x42dfcc92 @0x10006840"
0x10006872,gzcom-factory,C2,sc3_strtsim_factory_c820c0620,"new(0xc)+FUN_10006a87; clsid 0x820c0620 @0x10006872"
0x100068a4,gzcom-factory,C2,sc3_strtsim_factory_c625c758f,"new(0xc)+FUN_10006aac; clsid 0x625c758f @0x100068a4"
0x100068d6,gzcom-factory,C2,sc3_strtsim_factory_cc22b517c,"new(0xc)+FUN_10006ad1; clsid 0xc22b517c @0x100068d6"
0x10006908,gzcom-factory,C2,sc3_strtsim_factory_c622b7f03,"new(0xc)+FUN_10006af6; clsid 0x622b7f03 @0x10006908"
0x1000693a,gzcom-factory,C2,sc3_strtsim_factory_cc22b54d7,"new(0xc)+FUN_10006b1b; clsid 0xc22b54d7 @0x1000693a"
0x1000696c,gzcom-factory,C2,sc3_strtsim_factory_cc25c2bb0,"new(0xc)+FUN_10006b40; clsid 0xc25c2bb0 @0x1000696c"
0x1000699e,gzcom-factory,C2,sc3_strtsim_factory_c225c563d,"new(8) inline vtable PTR_LAB_1002a9c0; clsid 0x225c563d @0x1000699e"
0x100069b8,gzcom-factory,C2,sc3_strtsim_factory_c225c61e8,"new(0xc)+FUN_10006b65; clsid 0x225c61e8 @0x100069b8"
0x1001245b,strtsim-layer,C2,sc3_strtsim_layer_ctor,"SC3StrtSimLayer ctor; 0x27e0 obj; vtable PTR_FUN_1002c600; flags +0x32/+0x33=1 @0x1001245b"
0x1000959b,gzcom-factory,C2,sc3_strtsim_subiface_ctor,"two-vtable sub-interface object, PTR_FUN_1002b5c8 @0x1000959b"
0x10006a18,gzcom-factory,C2,sc3_strtsim_helper12_ctor,"vtable PTR_LAB_1002a9d0, FUN_10024ae3 @0x10006a18"
0x10014796,strtsim-layer,C2,sc3_strtsim_layer_init,"loads SC3StrtSimLayer.INI, mem-tier vehicle roster select, 10 table-inits, 6 service handles @0x10014796"
0x10006066,tunables,C2,sc3_strtsim_load_misc_tunables,"reads MiscStrtSimTunables/MaxMarinaToBoatDistance, stores squared to DAT_10032454 @0x10006066"
0x10009b35,schedule,C2,sc3_strtsim_parse_country_schedule,"NumCountries/Country/NumModes parser, packed Y/M/D dates, per-mode subarrays @0x10009b35"
0x10011cd0,vehicles,C2,sc3_strtsim_ini_add_key_vehicle,"INI callback: value->clsid via FUN_10024f79, push to DAT_10032fb0 @0x10011cd0"
0x10011cab,vehicles,C2,sc3_strtsim_ini_add_emergency_vehicle,"INI callback: value->clsid, push to DAT_10032fc0 @0x10011cab"
0x10011bfc,vehicles,C2,sc3_strtsim_clear_key_vehicles,"vector clear of DAT_10032fb0 @0x10011bfc"
0x10011bb9,vehicles,C2,sc3_strtsim_clear_emergency_vehicles,"vector clear of DAT_10032fc0 @0x10011bb9"
0x10013124,vehicles,C2,sc3_strtsim_pick_random_emergency_vehicle,"random index over (fc4-fc0)>>2, returns DAT_10032fc0[idx] @0x10013124"
0x10011cf5,vehicles,C2,sc3_strtsim_preload_key_vehicles,"bg thread; state DAT_10033068==2; create-and-cache each roster clsid; SleepEx 20ms @0x10011cf5"
0x1001346f,vehicles,C2,sc3_strtsim_resolve_vehicle_class,"map DAT_10032fe0 cache-or-create via svc +0x14 IID 0x80199683, AddRef @0x1001346f"
0x10002336,messaging,C2,sc3_strtsim_init_msgid_table,"handler table DAT_10032a24; hashes msg ids 0x4e2xxx into DAT_100329b4/DAT_10032a90 @0x10002336"
0x1001d060,messaging,C2,sc3_strtsim_init_handler_table_big,"guarded; ~18 handler slots, binds resource 0xfa2 @0x1001d060"
0x1000c3c9,messaging,C2,sc3_strtsim_init_handler_table_a,"guarded DAT_10032dec; plants handlers, binds svc method +0x7c/0xfa2 @0x1000c3c9"
0x1000f9ac,messaging,C2,sc3_strtsim_init_handler_table_b,"guarded zero-fill + 3 fn ptrs DAT_10032ebc @0x1000f9ac"
0x1000ea6f,messaging,C2,sc3_strtsim_init_handler_table_c,"handler table DAT_10032e44, LAB_1000e619 @0x1000ea6f"
0x10008314,messaging,C2,sc3_strtsim_init_handler_table_d,"handler table DAT_10032cac, LAB_1000e619 @0x10008314"
0x10007434,messaging,C2,sc3_strtsim_init_handler_table_e,"zero-fill + LAB_100073a4/LAB_10006ec2 DAT_10032c64 @0x10007434"
0x100056f4,messaging,C1,sc3_strtsim_init_handler_table_f,"plants FUN_10004db0 into DAT_10032bac @0x100056f4"
0x10010182,gzcom-services,C2,sc3_strtsim_resolve_clsid_table,"4-entry clsid table DAT_1002c318 -> handles DAT_10032ee0 via svc +0x14 @0x10010182"
0x100264e9,gzcom-services,C2,sc3_strtsim_get_class_factory,"lazy singleton DAT_100333d0 (create-by-clsid service) @0x100264e9"
0x10026443,gzcom-services,C2,sc3_strtsim_get_resource_service,"lazy singleton DAT_100333cc; method +0x50 builds key from path @0x10026443"
0x10024f79,util,C2,sc3_strtsim_parse_uint_auto_radix,"strtoul with 0x/hex-digit auto radix detect @0x10024f79"
0x1002517f,util,C2,sc3_strtsim_sleep_ms,"SleepEx(arg/1000, alertable) @0x1002517f"
```

## 7. OPEN

- **Which registered GZCLSID is SC3StrtSimLayer’s own class id** vs its sub-interfaces:
  the 13 ids in §2 appear only as raw dwords. Missing evidence: the SYS.PAK / CitySim.ini
  id→name registry (parsed at runtime, not in this module) or a cross-module witness.
- **The 12 small `0xc`-byte helper ctors** (`FUN_10006a3d/62/87/aac/ad1/af6/b1b/b40/b65`):
  not individually read here. Missing evidence: read each ctor + its vtable
  (`PTR_LAB_1002a9d0…`) to classify (likely message-target / iterator shims).
- **Meaning of message ids `0x4e2000-0x4e2203`** and the `0xfa2` resource bound by the
  handler-table inits. Missing evidence: the message-id→name map / GZ message router
  (another module).
- **Byte-packed date semantics** in `FUN_10009b35` are mechanically derived but the field
  ordering (which byte is year/month/day) is not proven against a real
  `SC3StrtSimLayer.INI` schedule. Missing evidence: a sample INI/PAK schedule block.
- **63-byte table @ 0x10032660** (`"$$$$%%%%…////,,,,"`): purpose undetermined; reported
  raw. Missing evidence: an xref reading it as an index/LUT (not located in functions read).
- **The layer’s per-frame tick / simulate method** (vtable `PTR_FUN_1002c600` slots) was
  not resolved to a concrete function here. Missing evidence: decode the vtable at
  `0x1002c600` and read its slot targets.
- **External GZCLSID → owning module** mapping (§5). Missing evidence: cross-module
  director registration tables (SIMTRANSIT / SIMGEOM / resource modules).
