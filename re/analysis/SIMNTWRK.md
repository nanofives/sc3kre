# SIMNTWRK.DLL — network / transport-graph tiling module

GZCOM director module. Ghidra full export: `re/ghidra_export_simntwrk/`
(1353 functions, decomp ok=1353 fail=0). image_base = `0x10000000`.
sha256 = `693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61`.

All addresses are SIMNTWRK.DLL virtual addresses (image base 0x10000000).

---

## 1. Purpose

SIMNTWRK.DLL is the **network-tile ruleset engine** for the game's built line
networks: roads, rails, highways, subways, power lines and pipes. Its strings are
exclusively the names of per-network tiling-rule tables under a `TilingRules\`
folder [CONFIRMED @ 0x100312xx string block], one family per network prefix:

```
ROAD_ HWAY_ RAIL_ SUBW_ PIPE_ POWR_   (+ DIAG_)   all "_GRND_" (ground level)
```

with these stages per family: `Set`, `SimpleRules`/`SIMPLERULES`,
`ComplexRules`/`COMPLEXRULES`, `Protected`, `Convert`, `Complex_Convert`,
`Bridges`, `final`, plus a shared `Collapse.txt` and `DIAG_Set.txt`
[CONFIRMED @ 0x10031a5c–0x10031efc]. The module reads these text tables at init,
parses them into integer records and inserts them into 18 rule containers plus a
bank of ~50 per-case handler objects that a network-piece factory
(`FUN_1000bdcd`, 22 cases) instantiates on demand. This is the tile
auto-connection / auto-orientation logic ("when a road tile has neighbours in
directions X,Y, draw tile N; when converted to a bridge, use tile M").

"Ntwrk" here means the in-city transport/utility **graph**, not internet
networking. There are no socket imports (imports are WINMM, KERNEL32, Ole32,
MSVCP60/MSVCIRT/MSVCRT only). See OPEN for the one anomalous `CAsyncSocket` RTTI symbol.

---

## 2. Director + registrations

PE export → guarded singleton → base ctor → 2× register_class, matching the GZCOM recipe.

- **`GZDllGetGZCOMDirector`** `[CONFIRMED @ 0x1001e4e4]` — guarded static director:
  `if ((DAT_1003222c & 1)==0){ DAT_1003222c|=1; FUN_100010d1(&DAT_100321e8); atexit(&LAB_100011cd);} return &DAT_100321e8;`
  The director object is the static `DAT_100321e8`.

- **Director ctor `FUN_100010d1`** `[CONFIRMED @ 0x100010d1]`:
  calls base ctor `FUN_1001e4e9`, installs vtables `PTR_FUN_100291d4` /
  `PTR_LAB_100291a8`, then registers exactly **2 classes**:
  ```
  FUN_1001e866(dir, 0x2171c021, FUN_10001138, 0);
  FUN_1001e866(dir, 0xe223741f, FUN_1000116a, 0);
  ```

- **register_class `FUN_1001e866`** `[CONFIRMED @ 0x1001e866]` — packs
  `{clsid, factory, arg}` and inserts into the map at `director+0x14` via
  `FUN_1001eb49`. Matches the "map at director+0x14" recipe.

- **Base director ctor `FUN_1001e4e9`** `[CONFIRMED @ 0x1001e4e9]` — sets vtables
  `PTR_FUN_1002ca94`/`PTR_LAB_1002ca68`, zeroes fields, builds the class map at
  `param_1+0x14` (a sub-object constructed by `FUN_1001e983` at `param_1+5`).

### GZCLSID → factory table `[CONFIRMED]`

| GZCLSID | factory RVA | alloc size | object ctor | ctor vtable | notes |
|---|---|---:|---|---|---|
| `0x2171c021` | `FUN_10001138` @ 0x10001138 | `0x6c` (108 B) | `FUN_1001a12e` @ 0x1001a12e | `PTR_FUN_1002c7bc` | 4-vtable object; embeds a sub-object at `+0x14` built by `FUN_1000aa2e`; byte flag at `+0x1a`. |
| `0xe223741f` | `FUN_1000116a` @ 0x1000116a | `0x150` (336 B) | `FUN_1000daec` @ 0x1000daec | `PTR_LAB_1002bd04` | large object; sub-object at `+1` built by `FUN_100248f6`; fields `+0x50..+0x53` zeroed; extra vtables at `+6`,`+7`. |

Both factories are the classic `operator_new(size)` + ctor pattern
[CONFIRMED @ 0x10001138, 0x1000116a]. Neither factory string-names its class —
there are **no `SC3*Layer` name strings in this module** (unlike SIMRCI/SIMMISC),
so the two classes are identified only by GZCLSID and size here.

Note: the value `0xE223741F` (the second GZCLSID) is also written as a literal tag
into every parsed Set-file record (see §3/§4), i.e. the network-piece records are
GZCOM-typed against this class `[CONFIRMED @ 0x10016d87 → FUN_1001746e local_18[0] = -0x1ddc8be1 = 0xE223741F]`.

---

## 3. Key subsystems

### 3.1 Tiling-rules init — `FUN_10010dff` `[CONFIRMED @ 0x10010dff]`
The module's ruleset bootstrap. Mechanically:
1. `operator_new(0x14)` a driver object (vtable `PTR_LAB_1002c75c`) and register it via `FUN_1001b4ff`/vcall `+0x10`.
2. Allocate **18 rule containers** into globals `DAT_10032300 … DAT_10032344`, each `operator_new(0x10)` + `FUN_10022866` (vtable `PTR_FUN_1002cd84`). These are the 6 networks × 3 stages (Simple/Complex/final) target maps.
3. Run the three file loaders in order, aborting if any returns 0:
   `FUN_10016d87()` (Set) → `FUN_10017f98()` (Convert/Protected/Bridges/Collapse) → `FUN_100175ed()` (Simple/Complex/final).
4. On success allocate **~50 tiny 8-byte handler objects** into globals `DAT_100323c0 … DAT_10032464`, each `operator_new(8)` + `FUN_1001a98b`, each stamped with a **distinct vtable** (`PTR_LAB_1002c748`, `…c734`, `…c720`, … stepping down by 0x14). These are the per-rule-case dispatch handlers.
5. Allocate one `operator_new(0x18)` object `DAT_10032468 = FUN_1001f201(_,0xffffffff)` and call `FUN_1000d165()`.

### 3.2 Set-file loader — `FUN_10016d87` `[CONFIRMED @ 0x10016d87]`
Builds 7 paths `"TilingRules\" + {ROAD,HWAY,RAIL,SUBW,PIPE,POWR,DIAG}_GRND_Set.txt`
(path join by `FUN_1001bc00`), constructs 7 Set-parser objects
(`operator_new(0x3c)` + `FUN_100203a7`), then parses each via `FUN_1001746e`
into globals `DAT_10032348 … DAT_10032360` (7 record-vectors). Uses a
**131072-byte (0x20000) stack read buffer** `aiStackY_20178[32768]`.

### 3.3 Simple/Complex/final loader — `FUN_100175ed` `[CONFIRMED @ 0x100175ed]`
Builds **18 paths** = 6 networks × {`SimpleRules`,`ComplexRules`,`final`}
(exact string casing varies per network: `ROAD_GRND_SimpleRules.txt`,
`RAIL_GRND_SIMPLERULES.txt`, etc.), parses each with `FUN_1002294e` into the 18
containers `DAT_10032300 … DAT_10032344`.

### 3.4 Convert/Protected/Bridges loader — `FUN_10017f98` `[CONFIRMED @ 0x10017f98]`
Loads the remaining ~21 tables: per network `Convert`, `Complex_Convert`,
`Protected`, and (for ROAD/RAIL/HWAY/SUBW/POWR) `Bridges`, plus `Collapse.txt`
[CONFIRMED — string PTRs listed in the function body: `PTR_s_ROAD_GRND_Convert`,
`…Complex_Convert`, `…Bridges`, `…Protected`, `s_Collapse_txt`, for all 6 prefixes].
Same 0x20000-byte read buffer pattern.

### 3.5 Set-line parser — `FUN_1001746e` `[CONFIRMED @ 0x1001746e]`
Reads the file into the 0x20000 buffer via `FUN_10017596`, then `strtok`s on a
5-byte delimiter loaded from `DAT_10031f0c`/`DAT_10031f10`. For each token it:
strips a leading non-digit run, copies, strips the trailing non-digit tail
(`isdigit`), `atoi`s the leading integer, and if the first char is a digit pushes
the record `{0xE223741F, 0xA317745F, value}` (see §4) into the target vector via
`FUN_1001b456`. Finally zeroes the whole 0x1ffff buffer.

### 3.6 File-read helper — `FUN_10017596` `[CONFIRMED @ 0x10017596]`
Zeroes 0x1ffff bytes, then drives a file object via vtable: `[+0x54]()` (open/exists
check), `[+0xc](1,2,1)` (seek/mode), `[+0x3c](buf,&len)` (read), `[+0x14]()` (close).
The file abstraction is a GZCOM stream, not raw `ReadFile`.

### 3.7 Path join — `FUN_1001bc00` `[CONFIRMED @ 0x1001bc00]`
`std::string`-style concat of `param_2` (a `{ptr,len}` string, the `"TilingRules\"`
prefix) with C-string `param_3` (the leaf name); reserves `len1+len2+1` and appends
both ranges via `FUN_1000744b`.

### 3.8 Rules-file parser wrapper — `FUN_1002294e` `[CONFIRMED @ 0x1002294e]`
`operator_new(0x50)` + ctor `FUN_1002234d(_, pathStruct)` to build a rule-file
parser object, then inserts it (`FUN_10022aa6`) into the container at `this+4`.

### 3.9 Rule-parser ctor — `FUN_1002234d` `[CONFIRMED @ 0x1002234d]`
Zeroes an 0x50 object, installs vtable `PTR_FUN_1002cd80`, builds a string member
at `+0x3c` from the path (`FUN_10007071`), and nests a `0x3c` Set-parser
(`FUN_100203a7`) at `+0x4c`.

### 3.10 Set-parser ctor — `FUN_100203a7` `[CONFIRMED @ 0x100203a7]`
0x3c object, vtable `PTR_LAB_1002cbf0`, string member at `+4`, `+0x1c = 0xffffffff`,
**`+0x24 = 0x20000000`** (raw constant — capacity/flag, meaning undetermined),
container at `+0x28`.

### 3.11 Network-piece factory — `FUN_1000bdcd` `[CONFIRMED @ 0x1000bdcd]`
`switch((param_1 & 0xff) - 1)` with **22 cases (0..0x15)**. Each case
`operator_new(0x20)` (or `0x1c` for cases 8, 9, 0x12) + ctor
(`FUN_1000d2da` for 0x20, `FUN_1000d0fc` for 0x1c) and stamps a distinct pair of
vtables per case (`PTR_FUN_1002b724`/`PTR_LAB_1002b5dc` for case 0, stepping through
`…2b3cc`, `…2b220`, … down to `…29408`/`…292c0` for case 0x15). It then vcalls the
new object: `[0](param_2,param_3)` (init); on success `[0xc]()` then
`[0x104](param_1)`; on failure `[8]()`. This is the per-tile-type piece factory
selected by a 1-based network/piece type id in the low byte of `param_1`.

### 3.12 COM path/shortcut resolver — `FUN_10020b60` `[CONFIRMED @ 0x10020b60]`
If a filename's extension (last `.`) equals `DAT_1003209c`, it `LoadLibraryA("Ole32.dll")`,
`GetProcAddress` for `CoInitialize`/`CoUninitialize`/`CoCreateInstance`, creates a COM
object, calls `IPersistFile::Load`-style `[+0x14]`, then `[+0x4c](0,1)` and
`[+0xc](buf,0x105,…)` to extract a resolved path string (≤261 chars) into the
caller's buffer, then `CoUninitialize`/`FreeLibrary`. Mechanically this resolves a
shell-link / OLE-persisted file to a real path. `[UNCERTAIN]` exact extension in
`DAT_1003209c` and the CLSID used (both are raw data not in the export).

---

## 4. Data / tunables (raw)

- **Tiling-rule table folder / files** `[CONFIRMED @ 0x10031a5c–0x10031efc]`:
  prefix `TilingRules\` (`0x10031efc`). Per network prefix `{ROAD,HWAY,RAIL,SUBW,PIPE,POWR}_GRND_`
  and shared `DIAG_GRND_`/`Collapse.txt`, with suffixes:
  `Set`, `SimpleRules`/`SIMPLERULES`, `ComplexRules`/`COMPLEXRULES`, `Protected`,
  `Convert`, `Complex_Convert`, `Bridges`, `final`. (Casing is inconsistent across
  networks in the shipped strings, e.g. `ROAD_GRND_SimpleRules.txt` vs
  `RAIL_GRND_SIMPLERULES.txt` vs `Road_GRND_Protected.txt`.)

- **Set-record layout** = **12 bytes** (vector stride `0xc`) `[CONFIRMED @ 0x1001b456 (+0xc advance), 0x1001746e]`:
  `{ dword tag0 = 0xE223741F, dword tag1 = 0xA317745F, int value = atoi(token) }`.
  `0xE223741F` is the module's second GZCLSID; `0xA317745F` is a second fixed tag
  (meaning undetermined — likely a GZ type/IID). `value` is the parsed tile/piece id.

- **strtok delimiter**: 5 bytes at `DAT_10031f0c` (4) + `DAT_10031f10` (1)
  `[CONFIRMED @ 0x1001746e]`. Raw bytes not in the export → exact chars undetermined.

- **Parser capacity/flag constant** `0x20000000` written at Set-parser `+0x24`
  `[CONFIRMED @ 0x100203a7]`.

- **File read buffer size** `0x20000` (131072) bytes, zeroed as `0x1ffff`
  `[CONFIRMED @ 0x10016d87, 0x10017596, 0x10017f98]`.

- **Container counts**: 18 rule containers `DAT_10032300..0x10032344`; 7 Set
  vectors `DAT_10032348..0x10032360`; ~50 handler objects `DAT_100323c0..0x10032464`
  `[CONFIRMED @ 0x10010dff, 0x10016d87]`.

- **Text-substitution tokens** near `FUN_10020b60` `[CONFIRMED @ 0x100320b4–0x10032108]`:
  `%MAYOR% %YOURNAME% %CITYNAME% %YOURCITY% %POPULATION% %YEAR% %PARADENAME% %ANYNEIGHBOR%`.
  Present as data; no reader of them was located in the functions read.
  `[UNCERTAIN]` which function consumes them.

- **Guard dword** `DAT_1003222c` (director singleton flag) `[CONFIRMED @ 0x1001e4e4]`.

---

## 5. Cross-module edges

- **Ole32.dll (COM)**, loaded dynamically `[CONFIRMED @ 0x10020b60]`:
  `CoInitialize`/`CoUninitialize`/`CoCreateInstance` + an `IPersistFile`-shaped
  interface for path/shortcut resolution. This is Windows COM, not a SimCity GZCOM
  service.
- **WINMM.dll** — `timeGetTime` imported `[CONFIRMED @ strings 0x10030262]` (timing).
- **GZCOM framework**: the module is itself a GZCOM director; it exposes 2 classes
  by GZCLSID (`0x2171c021`, `0xe223741f`) to the shell for the rest of the game to
  instantiate. No outbound GZCLSID/IID `CoCreateInstance`-style calls into other
  SimCity modules were seen in the functions read (the init path only reads local
  `TilingRules\*.txt` files through a GZCOM stream abstraction whose provider is
  passed in, not created here). `[UNCERTAIN]` which module supplies the file-stream
  object used by `FUN_10017596`.

---

## 6. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1001e4e4,gzcom-director,C2,sc3_ntwrk_get_gzcom_director,"PE export; guarded singleton DAT_1003222c; ctor FUN_100010d1; returns &DAT_100321e8 [CONFIRMED]"
0x100010d1,gzcom-director,C2,sc3_ntwrk_director_ctor,"installs vtables; registers 2 classes 0x2171c021/0xe223741f via FUN_1001e866 [CONFIRMED]"
0x1001e4e9,gzcom-director,C2,sc3_ntwrk_director_base_ctor,"sets director vtables; builds class map at +0x14 [CONFIRMED]"
0x1001e866,gzcom-director,C2,sc3_ntwrk_register_class,"packs {clsid,factory,arg}; inserts into map at this+0x14 [CONFIRMED]"
0x10001138,gzcom-factory,C2,sc3_ntwrk_factory_cls2171c021,"operator_new(0x6c)+FUN_1001a12e [CONFIRMED]"
0x1000116a,gzcom-factory,C2,sc3_ntwrk_factory_clse223741f,"operator_new(0x150)+FUN_1000daec [CONFIRMED]"
0x1001a12e,gzcom-class,C2,sc3_ntwrk_cls6c_ctor,"0x6c obj; vtable PTR_FUN_1002c7bc; subobj at +0x14 via FUN_1000aa2e [CONFIRMED]"
0x1000daec,gzcom-class,C2,sc3_ntwrk_cls150_ctor,"0x150 obj; vtable PTR_LAB_1002bd04; subobj at +1 via FUN_100248f6 [CONFIRMED]"
0x10010dff,tiling-init,C2,sc3_ntwrk_tiling_init,"allocs 18 rule containers + ~50 handlers; runs 3 loaders in sequence [CONFIRMED]"
0x10016d87,tiling-load,C2,sc3_ntwrk_load_set_tables,"builds 7 TilingRules\\*_GRND_Set.txt paths; parses into DAT_10032348..60 [CONFIRMED]"
0x100175ed,tiling-load,C2,sc3_ntwrk_load_simple_complex_final,"18 paths = 6 nets x {Simple,Complex,final}; FUN_1002294e into DAT_10032300..44 [CONFIRMED]"
0x10017f98,tiling-load,C2,sc3_ntwrk_load_convert_protect_bridge,"loads Convert/Complex_Convert/Protected/Bridges/Collapse tables [CONFIRMED]"
0x1001746e,tiling-parse,C2,sc3_ntwrk_parse_set_line,"strtok+isdigit+atoi; pushes 12B record {0xE223741F,0xA317745F,val} [CONFIRMED]"
0x10017596,file-io,C2,sc3_ntwrk_read_file_to_buffer,"zeroes 0x1ffff; vtable [0x54]/[0xc]/[0x3c]/[0x14] read into 0x20000 buf [CONFIRMED]"
0x1001bc00,util-string,C2,sc3_ntwrk_path_join,"concat {ptr,len} prefix + cstr leaf; reserve len1+len2+1 [CONFIRMED]"
0x1002294e,tiling-parse,C2,sc3_ntwrk_add_rule_file,"operator_new(0x50)+FUN_1002234d; insert into container at this+4 [CONFIRMED]"
0x1002234d,tiling-parse,C2,sc3_ntwrk_rulefile_parser_ctor,"0x50 obj; vtable PTR_FUN_1002cd80; path member +0x3c; nested 0x3c parser +0x4c [CONFIRMED]"
0x100203a7,tiling-parse,C2,sc3_ntwrk_set_parser_ctor,"0x3c obj; vtable PTR_LAB_1002cbf0; +0x24=0x20000000 [CONFIRMED]"
0x10022866,tiling-init,C2,sc3_ntwrk_rule_container_ctor,"0x10 obj; zeroes +1..+3; vtable PTR_FUN_1002cd84 [CONFIRMED]"
0x1001b456,util-vector,C2,sc3_ntwrk_vec_push_record,"std::vector push of 12B record; advances +0xc or grows via FUN_1001b670 [CONFIRMED]"
0x1000bdcd,piece-factory,C2,sc3_ntwrk_make_piece,"switch (type&0xff)-1 22 cases; new 0x20/0x1c + per-case vtables; vcalls [0]/[0xc]/[0x104] [CONFIRMED]"
0x1000d2da,piece-ctor,C2,sc3_ntwrk_piece_ctor_20,"chains FUN_1000d0fc; +7=0; vtables PTR_FUN_1002badc/PTR_LAB_1002b994 [CONFIRMED]"
0x10020b60,com-pathresolve,C2,sc3_ntwrk_resolve_ole_path,"ext==DAT_1003209c; dynamic Ole32; CoCreateInstance+IPersistFile Load; extract path<=261 [CONFIRMED]"
0x1000119f,gzcom-dtor,C1,sc3_ntwrk_scalar_deleting_dtor,"calls FUN_100011bb then conditional FUN_10026665(free) on (param&1) [CONFIRMED]"
```

(24 rows at C2, 1 at C1. All are decompilation-grounded; none claimed above C2 —
C3+ needs runtime or a second witness not available read-only.)

---

## 7. OPEN — undetermined, with the missing evidence

1. **Class identities of the 2 registered GZCLSIDs** (`0x2171c021` = 0x6c object,
   `0xe223741f` = 0x150 object). No name string in the module. *Needs:* the
   ASCII GZCLSID→name table in `SYS.PAK`/`CitySim.ini`, or an `[iOS-HINT]` match
   against `re/ghidra_export_ios/` (candidates: a `goNetwork*` / `goTilingLayer`
   class — not yet checked). The 0x150 object is the likely SC3 network layer;
   unconfirmed.
2. **Meaning of the record tags `0xE223741F` and `0xA317745F`** written into every
   Set record. `0xE223741F` is provably the 2nd GZCLSID; `0xA317745F` is an
   unresolved fixed dword. *Needs:* GZCOM IID registry / a consumer that reads the
   record's tag fields (reader not located).
3. **strtok delimiter bytes** at `DAT_10031f0c`/`DAT_10031f10` (5 bytes). Raw data
   not in the export. *Needs:* a data-section dump / live Ghidra read of 0x10031f0c.
4. **`FUN_10020b60` extension `DAT_1003209c` and the COM CLSID** used. *Needs:*
   data-section read; likely `.lnk` + `IShellLink`/`IPersistFile` but unconfirmed.
5. **`%MAYOR%`/`%CITYNAME%`/… token consumer.** Tokens exist as data at
   0x100320b4–0x10032108 but no substitution routine was found among functions read.
   *Needs:* xref search on those string addresses across the module.
6. **`CAsyncSocket` RTTI anomaly.** symbols.csv has
   `0x10023824 ??_GCAsyncSocket@@UAEPAXI@Z` (MFC async socket scalar-deleting dtor)
   and namespace `CAsyncSocket`. But the module imports **no** WinSock (no
   ws2_32/wsock32; imports are WINMM/KERNEL32/Ole32/MSVCP60/MSVCIRT/MSVCRT). This
   is either a FidDb mislabel or vestigial code. *Needs:* read `FUN_10023824` and
   its callers to confirm whether any socket vtable is actually reachable; check
   imports table directly. Treat "SIMNTWRK = internet networking" as **falsified**
   until such evidence appears — all live strings/logic are transport-graph tiling.
7. **How the 18 rule stages combine at runtime** (the actual tile-selection
   algorithm reading Set + Simple/Complex + Convert/Protected/Bridges). Only the
   *loading* path is mapped; the *evaluation* path (readers of DAT_10032300..) was
   not traced. *Needs:* xref sweep on `DAT_10032300..0x10032464` consumers and the
   ~50 handler vtables, plus the large unread functions (`FUN_10002693` 6819 B,
   `FUN_1000488d` 5827 B, `FUN_1000122a` 5225 B, `FUN_1000abde` 4375 B).
