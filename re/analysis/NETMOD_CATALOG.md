# NETMOD_CATALOG.md — the network piece catalog (netmod stage 0, `netcat`)

Built 2026-10-12 by the `netcat` child session. Owner goal: a suite to add road/rail/highway/bridge texture
variants and new network interactions. Stage 0 is the explorer: point at any network element and see
everything that defines it. Read-only over the game files. Nothing here writes under `Apps\`.

```
py -3 re/tools/netmod/netcat.py show 29 [--frames] [--all-rules] [--json]
py -3 re/tools/netmod/netcat.py from-clipboard          # after "Copiar ID" in the game's ? dialog
py -3 re/tools/netmod/netcat.py show --query block.txt  # a pasted "SC3 query id v1" block
py -3 re/tools/netmod/netcat.py list [--net HWAY] [--kind 5] [--name bridge]
py -3 re/tools/netmod/netcat.py export 29 --png DIR     # every frame of the piece as PNG
py -3 re/tools/netmod/netcat.py build                   # re/netcat_out/catalog.json + catalog.csv
py -3 re/tools/netmod/netcat.py html                    # re/netcat_out/html/index.html
py -3 re/tools/netmod/netcat.py tables                  # SIMNTWRK hardcoded tables, decoded
py -3 re/tools/netmod/netcat.py selftest                # 36 checks, all pass on the stock install
```

`re/netcat_out/` is covered by `/re/*` in `.gitignore`. It holds decoded game art (PNG) and must never be
committed or published (publish policy: tools and notes only). Game root: `$SC3_GAME_ROOT`, else found by
walking up, else the main checkout of the repo (a worktree has no game files).

Package `re/tools/netmod/`: `paths` (file locations), `rules` (TilingRules, line-aware), `names`
(Occupant.ini from SYS.PAK), `exemplars` (piece exemplars, agent types, localized names), `sprites`
(CSATTRIB frame tables, container slots, PNG), `pe_tables` (SIMNTWRK.DLL bytes), `trblkatt` (traffic
attributes), `query` (the Copiar ID block), `catalog` (the join), `htmlcat`, `netcat` (CLI).

## 1. What defines a piece: the chain, all on disk

| hop | source | key | status |
|---|---|---|---|
| which networks hold the id | `TilingRules\<NET>_GRND_Set.txt`, `DIAG_Set.txt` | raw id | loader `FUN_10016d87` binds file to global; `netcat selftest` re-derives the binding from the call sites `0x10017288..0x10017312` |
| piece class (one of 22) | classifier `FUN_1001a5f2` over the six Set lists | id | reproduced offline (`pe_tables.classify`); the six predicates at vtable `0x1002c7bc +0x11c..+0x130` read ROAD HWAY RAIL SUBW PIPE POWR, verified from the PE |
| exemplar | `Apps\Res\Occupant\OccupantAttribs.IXF`, TKB1 | `{0xE223741F, 0xA317745F, id}` | **NEW 2026-10-12**: 390 records here, 5 more in `OccupantAttribs_2.IXF` (group `0x0000057E`, the "Bridge Destroyed" pieces). Key is the one `FUN_1000c80b` loads `[CONFIRMED @ SIMNTWRK 0x1000c80b]` |
| agent type | exemplar prop `0x65` | type id | names and parents in `CitySim.ini` `[AgentTypes]` / `[AgentTypeHierarchy]` (SYS.PAK); costs in `SC3BudgetLayer.ini`. Road 29 = 16000 Road, the `object.type_id` the Copiar ID block shows |
| localized name | exemplar prop `0x6D` | `{0x2026960B, 0xA1096A4F, id}` | `Text\<lang>\SC3StringsBuildings.IXF`: 29 = "Carretera" (ENGLISH folder = Spanish text), "Road" (English-UK) |
| frame table | exemplar prop `0x67` `{0x6300, 0x6400, n}` -> `Sprites\CSATTRIB*.IXF` | `(0x6300, n)` | `BIN\r` v1, 20 frames (40 for layered bridge pieces, `layer_flags & 0xff` = 2) |
| pixels | `Sprites\00000005_Roads.DAT`, `0000000B_Utilities.DAT`, `00000008_Other.DAT` | frame `(group, instance)` | type 0 pixel + type 1 anchor record |
| rules | every `TilingRules\*.txt` | `id` or `id*256+state` | file + line + rule number per reference |
| traffic paths | `SSimData\<lang>\TRBLKATT.IXF` | `{0x625C6226, 0x825C6289, id*0x100+state}` | **parsed** 2026-10-12, section 5 |
| hardcoded | `SIMNTWRK.DLL` tables and code constants | id or `id<<8|state` | section 4 |

`[UNCERTAIN]` the runtime route from a placed piece to its pixels was never watched live. The data join
is exact (every exemplar's `0x67` names a CSATTRIB record; road 29's frames are the Roads.DAT records the
2026-08-19 recolour test turned red), but no breakpoint has seen SIMSPR read it for a network piece.

Frame index layout, measured over all 380 pieces with a table (`selftest`): within each layer of
`ZoomCount x RotCount` frames, frame `i` is zoom `(i % 20) // 4`, rotation slot `i % 4`, layer `i // 20`.
Road 29: zoom 0..4 widths 8, 16, 32, 64, 128. Unlike buildings, network pieces have their own zoom-4 art
(buildings reuse zoom 3). `[UNCERTAIN]` whether the rotation slot is the camera view or the piece state.

## 2. Coverage, measured

| | count |
|---|---:|
| distinct ids in the six Set files + DIAG | 420 (ROAD 109, HWAY 191, RAIL 38, SUBW 38, PIPE 32, POWR 26, DIAG 14: map counts match) |
| Set ids with an exemplar | 375 |
| Set ids with NO exemplar | 45: `1 220 233 235 244 250 319 320 11600 11601 11609 11610 15025 15075 15091 16010 16027 17000 17001 18025 18026 18031-18048 18054 18055 18076-18079` |
| exemplars in no Set | 20: `21 22 40 41 42 345 346 9274 9275 11215 11216 11602 11608 11636 11637` + `11595-11599` |
| pieces with art (CSATTRIB table) | 380; 40 have none |
| pieces whose exemplar points at ANOTHER piece's art | 10: 15045/15046 -> 39, 15047/15048 -> 43, 16060 -> 58, 16065 -> 333, 18084-18087 -> 15150-15153 |
| art container | Roads.DAT 288 pieces, Utilities.DAT 89, Other.DAT 3 |
| Roads.DAT + Roads_2.DAT sprite objects | 296 (map: 296) |
| pieces never produced by any rule RESULT | 172 (bridges, ramps, tunnels, crossings: placed by code or by the Bridges records) |
| pieces with no TrBlkAtt record | 84 (power lines, pipes, most subway) |
| pieces named by a hardcoded table/constant | 112 |

Class kinds over the 420: 2 (HWAY) 173, 1 (ROAD) 101, 4 (SUBW) 38, 3 (RAIL) 34, 9 (PIPE) 31, 10 (POWR) 22,
15 (HWAY 15130..15141) 8, 14 (ROAD+HWAY 15130..15141) 4, 6/13/7 two each, 11/5/12 one each.

**Where the art is not Roads.DAT.** 89 pieces draw from `0000000B_Utilities.DAT`, so the 2026-08-19
whole-Roads.DAT recolour left them unchanged: every power line (14..28, 92, 10033..10040, 11262/11263,
16061..16064, 18080..18083), the newer rail pieces (11651, 18000-18006 "Train House"/"Railroad", rail
tunnels 18019/18024), pipe and subway pieces 18007-18023, Harbour Bridge 18057-18070, bridge ramps
18050-18053, highway tunnels 18027-18030/18088-18091 and highway pieces 15150-15153.

**"Elevated rail".** No network, agent type or exemplar is named elevated: `CitySim.ini [AgentTypes]`
lists Rail, Rail Endcaps, Rail bridge (+incline, stanchion), Rail neighbor, SubToRail2K, Rail over road
(16014), Rail under highway (17208), and nothing else rail-shaped. The "elevated rail line" the
2026-08-19 test saw stay grey drew from outside Roads.DAT; the straight rail pieces (44, 46, 47 ...) are
IN Roads.DAT and were recoloured. The high-tension power line (agent 12103, pieces 14-28) is a grey line
of pylons whose art is in Utilities.DAT. `[UNCERTAIN]` which one the test saw: no screenshot was kept.
Settle with one in-game look at that Berlin frame, or `netcat from-clipboard` on it.

## 3. Rules: every reference, with file and line

`rules.Rules` indexes each appearance: Set membership, rule conditions and RESULTs (rule number,
selector, dir, state), Convert / Complex_Convert pairs (both ends), Protected, Bridges list positions,
Collapse groups, and the dead files (tagged `DEAD`, never edited by the game). `show` prints every RESULT
line (where the tiler produces the piece) and groups conditions/converts per file; `--all-rules` prints
everything. Road 29: RESULT in `ROAD_GRND_SimpleRules.txt` lines 77 and 105 (the capability map's T2
lines); RESULTs: 18 ROAD Simple, 2 ROAD Complex, 2 ROAD final, 4 POWR Complex (power line over road).

Checked encodings (selftest): every `*_Convert.txt` / `*_Complex_Convert.txt` value is
`ownSetId * 256 + state` with state 0..3 (12 files, 0 exceptions).

### Bridges record format (decoded 2026-10-12)

Loader `FUN_10017f98` -> `FUN_100196ce` pushes every token after line 1 into one int vector per network
(ROAD `DAT_100323b0`, HWAY `b4`, RAIL `b8`, POWR `bc`); line 1 is read and discarded
`[CONFIRMED @ SIMNTWRK 0x100196ce]`. The builder parses records out of the vector at placement time:

```
[len, axis, minLen, nA, A..., nB, B..., nC, C..., nD, D..., nE, E...]      len counts itself
```

| field | meaning (road/rail/power builder `FUN_1000122a`) |
|---|---|
| `axis` | 0 = bridge runs along x, 1 = along z. HWAY (`FUN_10002693`) uses 0..3: two passes, one per lane, key 0/2 (x run) or 3/1 (z run) |
| `minLen` | first record with `axis` matching and `minLen <= L` wins, file order `[CONFIRMED @ 0x10001468..0x100014b6]`. ROAD ships 18, 10, 6, 1 per axis: the longest bridge type that fits. The HWAY builder never reads it |
| A, E | end ramps: A[0] at position -1, E[0] at L, height + 7 (axis 1) / + 5 (axis 0), + 1 for power |
| B, D | pads: `r = L - k*nC`, B[0] repeated `r >> 1`, D[0] repeated `r - (r >> 1)` |
| C | the span, repeated `k = L // nC` times, in order |

Values are `id<<8 | state`, passed unchanged to the placer `FUN_10008919`. Shipped ROAD records, by `minLen`: 18 = suspension (A/E 16067/16070, span 11300-11304 or 16049-16053),
10 = layered/drawbridge (81-83, 88, 11268-11275), 6 = Harbour (18057-18070), 1 = plain (87/88, 11265/11271).
RAIL: one record per axis (59/60 ends, 90/91 + 16002/16003 span). POWR: 10033/10040 ends, 16061-16064
over water. HWAY: four lane records, 16042-16047, 16054/16055.

Cost = world `vt+0x54(0x3e82)`
(HWAY `0x3e84`) x L. Lists A, B, D, E have 5-slot stack buffers and C has 20, copied with no bounds
check: a longer list in a mod overflows the stack. `netcat tables` prints all 16 shipped records decoded.

### Collapse.txt

Line 1 = token count (259); then 19 groups `[n, ids x (n-1)]` (n counts itself, as in Bridges). Group
0x12 is forced by `FUN_1001da5f` for 0x2bd8/0x3b02. What a group means to the engine is not decoded.

## 4. Hardcoded in SIMNTWRK.DLL (`netcat tables`)

Read from the PE on every run (stock SHA-256 `693f6572...6f61`; a different DLL fails the selftest).

- **Crossing matrix** `0x100318ac`, u32[6][6] of `id<<8|state`, index `col + row*6`, lookup
  `f ? M[N][E] : M[E][N]` (`FUN_100167d4`). E from the existing piece: 0x1d road -> 1, 0x2bc4 -> 1,
  0x2c rail -> 2, 0x0e/0x0f/0x5c power -> 3, 0x49 highway -> 4, 0x3acb -> 5 (compiled as a sub/dec chain
  at `0x100168c2`). N = the new piece's netType. Shipped cells: road x rail = 69, road x power = 67,
  rail x power = 71, road x highway = 11258 / 15098, rail x highway = 16006 / 16007, power x highway =
  15036 / 15037. This is the lever for a new crossing type.
- **Slope tables** `0x1003193c` s8[8][4] corner-delta patterns, results `0x1003195c..0x10031a3c` u32[8]
  per network (ROAD 11201/11202/31/32, RAIL 16008/16009/46/47, SUBW 11614-11617, PIPE 11647-11650,
  POWR two tables, HWAY two tables 14094/15099-15105). `FUN_1001a2c0`.
- **Ramp tables** `0x10031fd8..0x10032028`, six u32[4] indexed by direction (-x 0, -z 1, +x 2, +z 3; the
  far end uses `(d+2)&3`): ROAD 63/64 (Road Tunnel Entrance), RAIL 18019/18024 (Railroad Tunnel), and four
  HWAY tables read by `FUN_1001ca1a` ("onramp" in the capability map) holding the Highway Tunnel pieces
  18027-18030 and 18088-18091.
- **Legacy import tables** `0x100313c0`, `0x100316d4`, `0x1003178c`, `0x10031844`, `0x10031878`
  (`FUN_1001272e`): legacy tilemap code -> piece, state, slope signature.
- **Id lists** `0x10031120` and `0x10031f94`, 16 entries each, the same 16 raw ids (83, 18058, 18068,
  16049, 16042, 11275, 91, 87, 11300, 18057, 18067, 16043, 90, 11265, 16061, 16062).
- **Code constants** in `FUN_1000122a` (bridge fallback 0x1d/0x2c/0x5c), `FUN_10009d20` / `FUN_1000abde`
  (highway diagonals 0x49, 0x2bfa, 0x3acb, 0x3afa, 0x3b07-0x3b0a), `FUN_1001da5f` (0x3acc, 0x2bd7, 0x2bd8,
  0x3b02), `FUN_1000de17` (road wear 0x1d <-> 0x3ac0-0x3ac2, 0x23 <-> 0x235b). Each one is looked up in
  the function bytes; a missing immediate is reported in the output, not hidden.
- `FUN_10008a4a`'s 0x24/0x25/0x2e/0x2d are NOT piece ids (a message argument, per the disassembly).

## 5. TrBlkAtt: per (piece, state) traffic paths

`SSimData\<lang>\TRBLKATT.IXF`, 862 records per language, 7 language folders = 6,034. Parsed to the exact
byte by `trblkatt.parse` on all 6,034 (selftest). Deserializers in STRTSIM: `FUN_10016aa5`
(TrBlockAttrib), `FUN_1000cf69` (pedestrian graph), `FUN_1002066a` (vehicle graph); class names from the
Loki demo `libStrtSim.so` are `[LINUX-HINT]` (`cSSStrtSimTrBlockAttrib`, factory `0x225c563d`).

```
"BIN\r"  s32 alt[4] (each >> 8; stored [0],[3],[2],[1])  u8 flag
"BIN\r"  u32 nPed  { u32 idx, s32 v0 v1 v2, u32 nEdge { s8 to(1-based, -1 exit), u8 e1, u32 key, u32 e3 } }
"BIN\r"  u32 nVeh  { u32 idx, s8 b0, s32 x3,   u32 nEdge { s8 to, u8 e1, u32 key, u32 e3 } }
```

Edge `key` loads `{0xA20BF670, 0xC20BF6C3, key}` from `SSimData\PPATHATT.IXF` (pedestrian) or
`{0xC25C74F2, 0xA25C7520, key}` from `SSimData\<lang>\VPATHATT.IXF` (vehicle). `alt` is read by
`FUN_1001c510` and subtracted from the occupant altitude. Road 29 state 0: 4 pedestrian nodes, 8 edges,
exit codes 0 and 16; 4 vehicle nodes, exits 0 and 16. Crossing 69: vehicle exits 0, 8, 16, 24; its
pedestrian exits are 0/16 in states 0 and 2 and 8/24 in states 1 and 3. Road 29 has records for states 0
and 1 only. `[UNCERTAIN]` what `e1`, `b0`, `v1` and the flag mean beyond the code paths named here.

A NEW piece id needs these records (or it has no traffic paths): `SSimData\*\TRBLKATT.IXF` has no
loose-file override known, and the game reads the folder of its language.

**English-UK differs.** The six folders DUTCH, ENGLISH, FRENCH, GERMAN, ITALIAN, SWEDISH are
byte-identical; English-UK differs in 792 of 862 records (road 29: an edge target at byte 218 is 3 in
ENGLISH and -1 in English-UK).

## 6. catalog.json schema (schema_version 1)

Top level: `schema`, `schema_version`, `generated`, `game_root`, `simntwrk_sha256`, `simntwrk_is_stock`,
`networks` (per tag: name, nettype, set_size, save_instance), `bridges` (per network: declared, tokens,
records `{line, len, a=axis, b=minLen, lists[5] of [line, value], ok}`), `collapse_groups`, `tables`
(the section 4 dumps), `pieces` (one per Set id, sorted).

Piece record:

| field | content |
|---|---|
| `id`, `hex` | piece id |
| `sets`, `set_lines` | networks (+ DIAG) and the line of the id in each Set file |
| `save_instance` | save network instance(s): 1 ROAD/RAIL/POWR/HWAY, 2 PIPE, 3 SUBW (QUERY_ID.md 4.3) |
| `class_kind`, `class_kind_why`, `class_vtables` | classifier result, factory size/vt1/vt2, and the `object.class` string the Copiar ID block prints |
| `exemplar_key`, `trblkatt_keys` | the GZ keys the engine loads |
| `occupant_ini` | `{name, line, text}` from SYS.PAK Occupant.ini, or null |
| `exemplar` | `{file, group, size, name, agent_type, agent_chain[{type,name,citysim_line}], footprint, sprite_key, lname_key, raw{prop: value}}` or null |
| `names_localized` | `{ENGLISH, English-UK}` |
| `budget` | `{value, comment, line, section}` from SC3BudgetLayer.ini for the agent type |
| `art` | `{csattrib{file,type,instance,hdr}, via, shared_from, objects[{container,group,object}], frames[{frame, group, instance, flag, u1, u2, container, slot, anchor_slot, w, h, format}]}` |
| `rules` | every reference `{file, line, stage, net, status, role, rule, selector, dir, state, text, extra}` |
| `rule_summary` | counts per stage + role |
| `hardcoded` | `[{where, rva, what}]` |
| `trblkatt` | `{lang, states, sizes, decoded{state: summary}, same_in_all_langs}` or null |

`catalog.csv` is a flat one-row-per-piece view (`catalog.CSV_COLS`). Consumers should read the JSON.

## 7. Open questions this stage found (candidates for UNCERTAINTIES.md)

1. Runtime piece -> pixels route not watched live (section 1).
2. CSATTRIB rotation slot = camera view or piece state.
3. Bridge span list at `0x10031120` holds raw ids (0x53 = 83 ...) but `0x100023c1` compares it with a full
   file token `id<<8|state`, so the `vt+0x15c(x, z, 1)` call there cannot match a shipped token. Read
   from the disassembly; what `[ebp+0x14]` points at was not re-traced.
4. `FUN_1001d761` reads the ramp partner at index `k+1`; for k = 3 that is the next table's slot 0, and
   past `0x10032028` it is a string at `0x10032038`.
5. Crossing matrix: nothing in `FUN_100167d4` stops netType 5/6 (N = 6 overruns the matrix).
6. 45 Set ids have no exemplar and 40 no art (incl. 18031-18048 "Highway Bridge" in Occupant.ini): what
   the factory's exemplar load does for them.
7. Exemplar props `0x136/0x137/0x138` carry values equal to the dead `*_Exits.txt` second column
   (`0x01040104` for road 29): meaning unknown.
8. "Elevated rail" (section 2).
9. English-UK TrBlkAtt differs (section 5): which is newer, and what the edits change in traffic.
