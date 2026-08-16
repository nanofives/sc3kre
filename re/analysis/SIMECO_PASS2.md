# SIMECO.DLL — second pass

## 1. Promoted rows (C1 → C2)

All 10 bodies were read, mechanically described, and their callees identified. All 10 reach C2. None were too degraded to promote.

```csv
rva,subsystem,confidence,new_name,evidence
0x100162e9,resource-mgr,C2,sc3_eco_get_resource_mgr,"guarded one-time singleton getter: if (DAT_10020949 & 1)==0 set bit0, FUN_10016314(&DAT_10020948) [construct], FUN_10018ff6(&DAT_10016337) [_onexit cleanup]; returns pointer DAT_10020950. Callers do (*(ret+0x50))() to open a named resource [CONFIRMED @ 0x100162e9; 0x100046bb:54-55]"
0x1001589f,ini,C2,sc3_eco_ini_ctor,"config-object ctor: base ctor FUN_1000f034(this); std::string member ctor FUN_10002e57(this+0x64); reader member ctor FUN_10012d9a(this+0x78); zero this+0xb4/+0xb8/+0xbc; install vtable PTR_FUN_1001ca64 [CONFIRMED @ 0x1001589f]"
0x1000f121,ini,C2,sc3_eco_ini_set_file,"set primary config-file path: if flag this+0x19 set, call virtual (*this+0xc)() [release prior]; then FUN_10002fe4(this+4, param_1) [assign path string]. this+4 is the file the resolver looks up [CONFIRMED @ 0x1000f121; 0x100046bb:56-58]"
0x10015981,ini,C2,sc3_eco_ini_set_pak,"set archive to overlay + reset resolution: this+0xb4 = 0 [force re-resolve]; FUN_10002fe4(this+0x64, param_1) [assign archive path, e.g. SYS.PAK] [CONFIRMED @ 0x10015981; 0x100046bb:61-63]"
0x1001599c,ini,C2,sc3_eco_ini_read_key,"read section.key -> value string. FUN_10016012(this) [lazy resolve]; switch this+0xb4: 0 -> return 0; 1 -> tail FUN_1000fe22(this,key,section,out) [plain-file read]; 2 -> seek PAK entry (reader+0x30 with handle this+0xc0), build search key by concatenating separators DAT_100206ec + section + DAT_100206e8, count via reader+0x38, loop FUN_10015f67 per entry, match section header (FUN_1000ec0e/FUN_10010cc9), then key match via FUN_1000e7a8, copy value into param_3+4 (FUN_1000258c), return 1. Returns found flag [CONFIRMED @ 0x1001599c]"
0x10015c93,ini,C2,sc3_eco_ini_iterate_section,"iterate a section, invoking callback per entry. FUN_10016012(this); switch this+0xb4: 0 -> return 0; 1 -> tail FUN_100100bf; 2 -> seek PAK entry, build search key (FUN_1000a964/FUN_100162c3 + DAT_100206e8), loop entries, on section match call (*param_2)(&entry_val,&entry_key,param_3) [the callback, e.g. FUN_1000564a], break when key/section change (local_3c==local_40 || local_28==local_2c). Returns 1 on success [CONFIRMED @ 0x10015c93]"
0x10012ad7,util,C2,sc3_eco_parse_int_auto_radix,"string->unsigned int with auto radix. if s[0]=='0' && (s[1]=='x'|'X') -> strtoul(s,0,0x10); else scan chars: any in 'a'..'f' ((0x60<c)&&(c<0x67)) or 'A'..'F' ((0x40<c)&&(c<0x47)) -> radix 0x10, else 10; strtoul(s,0,radix). Result returned in EAX (decomp shows void; caller uses return, e.g. 0x100046bb:91) [CONFIRMED @ 0x10012ad7]"
0x10016427,ixf-text,C2,sc3_eco_reskey_ctor,"resource/text-key ctor: this+4=0 [lazy text ptr]; this+8=0x2026960b [fixed resource TYPE id]; this+0xc=param_2 [group]; this+0x10=param_1 [instance]; vtable *this=PTR_FUN_1001cac8; FUN_10016666(this). Confirmed call form FUN_10016427(buf, instance, group) -> key triple {type 0x2026960b, group, instance} [CONFIRMED @ 0x10016427; 0x1000c95c:234]"
0x1001645f,ixf-text,C2,sc3_eco_reskey_get_string,"getter for the cached text at param_1+4: if *(param_1+4)==0 -> build empty std::string in param_2 (FUN_100024d7, vtable PTR_LAB_1001b130); else FUN_10011274(param_2, *(param_1+4)) [copy cached string]. Returns param_2 [CONFIRMED @ 0x1001645f]"
0x1000a80b,util,C2,sc3_eco_agentmap_subscript,"std::map::operator[] on DAT_10020818: FUN_1000b526 [lower_bound] on key *param_1; if at end (==*this) or key < node key (node[4]) -> insert node via FUN_1000acc8 (FUN_1001087a builds the value); return node+5 (byte 0x14, the value slot). Modifier record lives at node+0x14 [CONFIRMED @ 0x1000a80b; 0x1000c95c:267-274]"
```

Note on renames vs the doc's provisional names: `sc3_eco_ini_open_file` → `sc3_eco_ini_set_file` and `sc3_eco_ini_overlay_pak` → `sc3_eco_ini_set_pak` (neither opens/overlays at call time; each just stores a path — resolution is deferred to `FUN_10016012`). `sc3_eco_str_to_int` → `sc3_eco_parse_int_auto_radix` (the radix auto-detect is the whole point). `sc3_eco_text_key_ctor`/`sc3_eco_text_fetch` → `_reskey_ctor`/`_reskey_get_string`, and `sc3_eco_agentmap_at` → `_agentmap_subscript` (it inserts-if-absent, i.e. `operator[]`, not a pure lookup).

---

## 2. OPEN-list resolutions

### Item 1 — Float `.rdata` constants → **STILL OPEN (values), roles now confirmed**
The six symbols are referenced but never carry a literal value in any decompiled body (Ghidra leaves `.rdata` float loads symbolic). Confirmed by grep across all 1212 functions. Their **usage** is now pinned, which narrows what each must be:

| symbol | confirmed use | RVA of witness |
|---|---|---|
| `_DAT_1001b5a8` | added as `+ (float)_DAT_1001b5a8` immediately before every `SUB84`/`ftol` float→int truncation across the module — a rounding bias | 0x10008249:268,330; 0x1000c95c:278,280,526; 0x10001a22:98,191,243; 0x10016be1:49; 0x10016f06:21; 0x10017054:21 |
| `_DAT_1001bdec` | `_DAT_10020274 = (float)GarbageScalingFactor * _DAT_1001bdec` (scales the INI value) | 0x100046bb:516 |
| `_DAT_1001bdf0` | tick: `fVar3 = _DAT_1001bdf0` seed and `if (local_18 != _DAT_1001bdf0)` sentinel | 0x10008249:251; 0x10007fd4:85 |
| `_DAT_1001bdf8` | tick decay step: `if (_DAT_1001bdf8 < fVar3) fVar3 -= _DAT_1001bdf8` | 0x10008249:265-266 |
| `_DAT_1001bf30` | advisor cat 0: quadratic coeff `x*x*_DAT_1001bf30 + bias` | 0x1000c95c:277,280 |
| `_DAT_1001bf38` | advisor cat 2: `ceil(param_3 * _DAT_1001bf38 / total)` — a percentage scale | 0x1000c95c:481 |

**Blocker:** the byte values live in `.rdata`; no `globals.csv`/`symbols.csv` in `re/ghidra_export_simeco/`. **Tool that breaks it:** `pe_read.py` (or Ghidra `DumpDataAt`) reading 4 bytes as `float` at each RVA (`0x1001b5a8, 0x1001bdec, 0x1001bdf0, 0x1001bdf8, 0x1001bf30, 0x1001bf38`; note the extra `_DAT_1001be8c` at 0x1000a739:10, same "×coeff + bias" shape, worth dumping too). Also worth resolving vtable-slot targets while there.

### Item 2 — Owning simulator GZCLSID + message ids `0xe3079ef9`/`0xe3079f00` → **STILL OPEN**
The two ids are literals loaded into `param_1` immediately before the notifier subscribe calls, so their **subscription slots are now confirmed**: `0xe3079ef9` → notifier(`this+0xf4`) vtable **+0x54**, `0xe3079f00` → vtable **+0x58**, preceded by three plain `+0x50` subscribes and followed by one `+0x5c` [CONFIRMED @ 0x10005844:183-190]. The **names/semantics** and the simulator's GZCLSID are set by whoever *publishes* them — not present anywhere in SIMECO. **Blocker:** cross-module. **Tool:** grep `re/ghidra_export/` (SIMCITY.DLL/SIMMISC.DLL exports) for `0xe3079ef9`/`0xe3079f00`, and the ASCII clsid table in `SYS.PAK`/`CitySim.ini`.

### Item 3 — Ordinance id → in-game name → **STILL OPEN**
Unchanged. The 12 ids are confirmed query keys inside SIMECO; the human names come from the ordinance module/IXF. **Tool:** grep the ordinance module export for the 12 ids in §5, or the IXF ordinance-name table.

### Item 4 — Sub-layer identities at `this+0x3c/0x58/0x10c/0x128/0xf4/0x13c` → **PARTIALLY RESOLVED**
The ctor `FUN_10004379` splits these into two kinds:
- **Embedded sub-objects** (vtable written inline at construction) — identities are these `.rdata` vtable RVAs:
  - `this+0x58` (idx 0x16) and `this+0x74` (idx 0x1d): both `PTR_FUN_1001bb80` (same class) [CONFIRMED @ 0x10004379:45,52]
  - `this+0x128` (idx 0x4a): `PTR_FUN_1001bb38` [:119]
  - `this+0x144` (idx 0x51): `PTR_FUN_1001baf0` [:124]
  - `this+0x498` (idx 0x126): built by `FUN_1000a3ba`, vtable slot at idx 0x125 = `PTR_FUN_1001bae8` [:129-130]
- **Pointer slots** — zero in the ctor, filled during init as external service pointers: `this+0x3c` (idx 0xf) and `this+0x10c` (idx 0x43) are both `= 0` in the ctor [:33,111] and receive owner-service pointers in `FUN_10005844`. So `this+0x3c`/`0x10c` are **not** owned sub-layers; they are cached references to sim services.
- `this+0xf4` = the notifier (a `0xf0`-byte object, see §3 of the doc); `this+0x13c` = the optional object (item 5).

**Remaining blocker:** the class names / owning ctors behind `PTR_FUN_1001bb80`, `PTR_FUN_1001bb38`, `PTR_FUN_1001baf0`, `PTR_FUN_1001bae8` need the vtable slot targets. **Tool:** `VtableDump.java` on those four RVAs (each slot → a `FUN_*`, then read the ctor/first method for a name string).

### Item 5 — The `0x44`-byte optional object at `this+0x13c` → **PARTIALLY RESOLVED**
Its ctor `FUN_1000a32e` (22 bytes) was read: base ctor `FUN_10017f8d(this)`, byte flag `this+0x31 = 0`, vtable `*this = PTR_LAB_1001bdfc`; returns this [CONFIRMED @ 0x1000a32e]. Build path in init [CONFIRMED @ 0x10005844:191-208]: gated on `(*(this+0x1c vtable+0x1b8))()` non-null **and** its `(*vtable[0])()` returning true; then `operator_new(0x44)` → `FUN_1000a32e`; stored at `this+0x13c`; then `(*obj+4)()` [init], `cVar1 = (*obj+0xc)()` [query]; if true it runs `(*obj+0x50)()`, `(*obj+0x54)()` and then a large zero-init of `this+0x148..0x188`, `this+0x42c..0x468`, and a 12-iteration strided clear from `this+0x1ec` (accumulator/history table). **Purpose (abduction/disaster hook) still not confirmed.** **Blocker:** the meaning of vtable slots `+4/+0xc/+0x50/+0x54` on `PTR_LAB_1001bdfc`, and the base ctor `FUN_10017f8d`. **Tool:** `VtableDump.java` on `PTR_LAB_1001bdfc`, then read those four slot functions + `FUN_10017f8d`.

### Item 6 — `FUN_1000c95c` categories 1 and 2 → **RESOLVED (and the premise corrected)**
The premise ("cats 1/2 push flag `0x20000`, text ids `0x2a..0x2c`, air-vs-water") was wrong. `0x2a..0x2c` are **category-0** land-value bands. The real dispatch on `param_5` [CONFIRMED @ 0x1000c95c]:

- **cat 0** (`param_5==0`, line 225): combined air+water land-value impact; bands `param_2/5, ×1, ×5, ×10, ×0x32` where `param_2 = DAT_1002025c + DAT_10020260`; text ids `0x29..0x2f`; sets `*param_6=1` on worst band (line 421).
- **cat 1** (`param_5==1`, the `piVar3==1` branch, lines 524-587): **only** when tile type `== 0x11` and the global service `FUN_10012167` vtable+0x94(0) is non-null. Reads a single value from `this+0x1c` vtable **+0xa4**, scales it by `_DAT_10020274` (**GarbageScalingFactor**), text ids `0x10c` (label) / `0x10d` (value). → a **garbage / solid-waste tonnage** readout.
- **cat 2** (`param_5==2`, the `piVar3!=1` branch, lines 447-522): same gate; reads **two** values from `this+0x1c` vtable **+0xa4** (total) and **+0xa8** (served), computes `ceil((total - min(served,total)) * _DAT_1001bf38 / total)` — a **shortfall percentage**; text ids `0x10e` / `0x10f`.
- **cat 3** (`param_5==3`, line 604): **air**, bands on `DAT_1002025c` (`>>3, >>2, >>1, (<<2)/5`), reads grid via `local_14[7]` vtable+0x58, text ids `0x187..0x18d`.
- **cat 4** (`param_5==4`, line 772): **water**, bands on `DAT_10020260` (same shifts), grid via `local_14[7]` vtable+0x5c, text ids `0x18e..0x194` (note `399=0x18f`, `400=0x190`).

So cats 1/2 are **not** pollutant bands at all — they are two service-capacity readouts on the `this+0x1c` sub-object, gated on tile type `0x11`. The only residual `[UNCERTAIN]` is *which* service `this+0x1c` is (resolved by item 4's VtableDump).

---

## 3. New findings

1. **INI backend is a lazy PAK-overlay resolver.** New function `FUN_10016012` (`sc3_eco_ini_resolve_source`, 535 bytes) is called at the top of both `read_key` and `iterate_section`. State field `this+0xb4`: `0` = unresolved, `1` = plain file on disk, `2` = file found *inside* the archive (with entry handle cached at `this+0xc0`). It points the reader (`this+0x78`) at the archive path (`this+0x64`, e.g. `SYS.PAK`), opens via reader vtable+0xc(1,2,1), enumerates entries, and matches the primary file name (`this+4`, e.g. `SC3Pollution.INI`) [CONFIRMED @ 0x10016012:32,70,99]. This is the concrete mechanism behind the doc's "opens SC3Pollution.INI then overlays SYS.PAK."
2. **Config object layout** (from ctor + accessors): `+0` vtable `PTR_FUN_1001ca64`; `+4` primary path std::string; `+0x19` path-set flag; `+0x64` archive path std::string; `+0x78` archive-reader object (methods `+0xc` open, `+0x24`, `+0x30` seek-entry, `+0x38` read/count, `+0x70` set-source); `+0xb4` state; `+0xc0` entry handle.
3. **IXF text-key triple confirmed:** `{type = 0x2026960b, group, instance}` — the fixed **type** id `0x2026960b` (new constant, not previously recorded) is baked into every key by `FUN_10016427`; the group `0x82e0074c` and per-string instance are the varying pair [CONFIRMED @ 0x10016427:8; 0x1000c95c:234].
4. **Message subscription slots pinned:** msg `0xe3079ef9` → notifier vtable+0x54, msg `0xe3079f00` → +0x58 [CONFIRMED @ 0x10005844:186-189].
5. **Advisor text-id map extended** (beyond the doc's §3): cat 1 = `0x10c/0x10d`, cat 2 = `0x10e/0x10f`, plus the init-string branch uses group `0x029541f4` instance `0x1d9` and stores the notifier name into `this+0xf8` via `FUN_10002fe4` [CONFIRMED @ 0x10005844:151-165].
6. **Agent-modifier map node layout:** value at node+0x14; the 5-field `%d %d %d %d %d` record is read back as `short@+0`, `short@+2`, `byte@+4`, `byte@+5` [CONFIRMED @ 0x1000c95c:267-274] — matches the clamp ranges in `FUN_1000564a` (signed-16 for the first fields, unsigned-8 for the last two).
7. **Extra rounding-bias witnesses** (`_DAT_1001b5a8`) appear in `FUN_10016f06`/`FUN_10017054` (`(float)local_c / *(this+0x6c) + bias`) and `FUN_1000a739` (`*(param_1+0x148) * _DAT_1001be8c + bias`) — `this+0x6c` and `this+0x148` are per-object scale divisors worth a later pass.

---

## 4. Revised OPEN (replaces §7 wholesale)

- **Float `.rdata` constant values** `_DAT_1001b5a8` (rounding bias, all `SUB84`/`ftol` sites), `_DAT_1001bdec` (GarbageScalingFactor multiplier), `_DAT_1001bdf0` (tick seed/sentinel), `_DAT_1001bdf8` (tick decay step), `_DAT_1001bf30` (advisor cat-0 quadratic coeff), `_DAT_1001bf38` (advisor cat-2 percentage scale), and `_DAT_1001be8c` (scale coeff in `FUN_1000a739`). Roles confirmed; byte values need `pe_read.py`/Ghidra `.rdata` dump at those RVAs (no `globals.csv` in the export).
- **Message ids** `0xe3079ef9` (notifier slot +0x54) / `0xe3079f00` (+0x58) and the **owning simulator GZCLSID** — subscription wiring confirmed; names/semantics live in the publishing module (SIMCITY.DLL / SIMMISC.DLL) or the `SYS.PAK`/`CitySim.ini` clsid table.
- **Ordinance id → in-game name** — the 12 ids are confirmed query keys; human names come from the ordinance module / IXF.
- **Embedded sub-layer class identities** — vtable RVAs now known: `PTR_FUN_1001bb80` (`this+0x58` & `this+0x74`), `PTR_FUN_1001bb38` (`this+0x128`), `PTR_FUN_1001baf0` (`this+0x144`), `PTR_FUN_1001bae8` (`this+0x498`, via `FUN_1000a3ba`). Slot targets/class names need `VtableDump.java`. Note `this+0x3c` and `this+0x10c` are **cached service pointers**, not owned sub-layers.
- **The `0x44`-byte optional object** (`this+0x13c`, ctor `FUN_1000a32e`, vtable `PTR_LAB_1001bdfc`, flag `+0x31`) — build gate and method-call sequence (`+4/+0xc/+0x50/+0x54`) confirmed; purpose needs `VtableDump.java` on `PTR_LAB_1001bdfc` + base ctor `FUN_10017f8d`.
- **`FUN_1000c95c` cat-1/cat-2 service identity** — mechanics fully resolved (cat 1 = garbage tonnage via `this+0x1c`+0xa4 × GarbageScalingFactor, ids `0x10c/0x10d`; cat 2 = shortfall % via `+0xa4`/`+0xa8`, ids `0x10e/0x10f`, gated on tile type `0x11` + `FUN_10012167`+0x94). Only which concrete service `this+0x1c` is remains — resolved by the sub-layer VtableDump above.
- **INI key/value delimiter strings** `DAT_100206ec` / `DAT_100206e8` (used to build the section-scan search key in `read_key`/`iterate_section`) — raw C-strings in `.rdata`, contents not in the export; minor, dump with the float constants.
(raw JSON: C:\Users\maria\AppData\Local\Temp\fleet-delegate-5e8f70d8b29645a08cc617b8d1de12fd.json)
