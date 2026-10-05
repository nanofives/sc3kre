# TOOLING_ADOPTION.md - cross-project + external tooling, evaluated for SC3 (2026-10-05)

Source of the candidate list: a survey of the sibling RE projects (TD5RE, Mashed, SimGolf, SAMP) and a
web sweep for throughput tools. Each item below was MEASURED here before being adopted or rejected.

## 1. Cheap ports from sibling projects

### 1a. SimGolf `FixParams.java` - REJECTED (measured)
Commits decompiler-inferred params for DEFAULT-signature functions, switching to `__thiscall` on `in_ECX`.
- SC3's Ghidra 12.1.2 analysis already does the thiscall half: the SIMRCI export has 1,013 `__thiscall`,
  705 `__fastcall`, **0** `in_ECX` bodies (of 4,040). Dry run: `default=672 in_ECX=0`.
- A/B export of SIMRCI (read-only session, FixParams chained before ExportAllDecomp, DB untouched):
  **269/4,040 files changed, none an improvement.** The changes rename `param_1` -> `this` and RENUMBER every
  later param (breaks every note that cites `param_N`), drop typed array access (`param_1[0xe]` becomes
  `*(int *)((int)this + 0x38)`), and introduce `in_EAX` artefacts.
- Side finding: SimGolf's original `dry` mode still mutates (sets the convention and commits params).

### 1b. Mashed `rw_string_anchor_scan.py` - REJECTED (no anchor population)
The scan names functions from strings that carry their own API name. SC3 retail has almost none:
- `Class::Method`-shaped strings across SC3U.exe + all 30 modules: **23** (e.g. `OccManAnim::MoveOccupant: Failed`).
- No `__FILE__` paths, no assert text.
- MSVC RTTI type names (`.?AV...@@`): **6-9 per binary, 208 total, all CRT exception classes.** The game code
  was built without RTTI. Consequence for later items: class recovery (OOAnalyzer) must work from
  vtables/ctors only, and the RTTI route to class names does not exist.

### 1c. Gated tracker writer - ADOPTED as `re/scripts/tracker.py`
Mashed enforces confidence gates through its `re-classify` skill. SC3 already had safe *batch* writers
(`walk_vtable_class.py`, `merge_worker_module.py` filter on module + check blast radius); the gap was hand
edits, done as inline python, which caused both recorded tracker incidents.
- `get` / `find` / `set`, `--module` REQUIRED, dry-run unless `--apply`, gates: NAME_OK, C2 needs
  subsystem+name, C3/C4 need `[CONFIRMED @ ...]` or a `verify/` path, lowering needs `--demote`.
- **Splices instead of rewriting.** `functions.csv` is mixed-format (QUOTE_ALL + unquoted rows + a bare-LF
  last record): a `csv.DictWriter` round-trip differs at byte 848,767 and grows the file 303 bytes. Every
  whole-file writer churns untouched rows. tracker.py re-serialises only edited records and verifies the
  changed-record count equals the intended count (restores the backup otherwise). Selftest: `tracker.py selftest`.
- **Found and fixed while building it:** 3 C2 rows filed under module `GZWIND.DLL` (no size) beside the
  canonical `GZWinD.dll` rows, which still read C0 (`0x1000337d`, `0x1001efdf`, `0x1001f603`). Merged into
  the canonical rows, orphans removed: 50,682 -> 50,679 rows, diff = 6 out / 3 in. tracker.py now blocks
  if a module exists in two spellings.

## 2. External type archives - `0xC0000054/sc4-ghidra-symbols` (+ `sc3k-gzcom-dll`)

`sc3k-gzcom-dll` was **already adopted** before this sweep (`GZCOM_INTERFACE_CATALOGUE.md`,
`walk_vtable_class.py --headers`). Nothing new there. `sc4-ghidra-symbols` (cloned to
`Proyectos/re-references/`, Apache-2.0, last commit 2026-10-02) was inventoried with a headless dump:

| archive | types | verdict for SC3 |
|---|---:|---|
| `SimCity4.gdt` | 1,976 (854 structs, 126 `vftable_cIGZ*`) | **Not applied.** 23 interfaces overlap the SC3 SDK headers, which are already used and are the closer witness (same product). SC3 slot order is permuted even against SC3 headers (catalogue §25d), so SC4 order is weaker still. |
| `Gimex.gdt` | 114 (`GIMEX_open/read/info/...`, `GINFO`, `GSTREAM`, FSH `Shape*`) | **Hint only** for `GIMEX.DLL` (504 C0 / 24 C1). SC3's GIMEX exports only `GZDllGetGZCOMDirector`, so there are no named entry points to attach prototypes to. |
| `DirectX7.gdt` | 56,797 | **Adopted as a lookup table**, not applied: `re/analysis/DIRECTX7_VTABLE_SLOTS.csv` = 647 rows `interface,offset,slot,method` over every IDirectDraw*/IDirect3D* vtable. Cross-check: `IDirectDrawSurface7` slot 22 (`+0x58`) = `GetSurfaceDesc`, matching the resize crash record. GZGraphicD has 1,041 untyped indirect calls; typing them needs per-field analysis, the table makes each one a lookup. |
| FidDbs (`libcmt` VC2003, `stlport` VC7, `lua5`, `libpng`, `zlib`) | - | **None apply.** SC3 links the CRT dynamically (`MSVCRT.dll`, `MSVCP60.dll`, `MSVCIRT.dll` in every module) and no binary contains zlib, libpng, Lua or STLport strings. |

**New lead for item 5:** `GIMEX.DLL` statically contains **IJG libjpeg** (its full error-message table:
"Wrong JPEG library version: library is %d...", "Corrupt JPEG data: bad Huffman code", ...). libjpeg is open
source, so a VC6-built libjpeg FidDb should name a large share of GIMEX's 504 C0 rows mechanically.

## 3. Time Travel Debugging - ADOPTED as `re/tools/ttd.py` (query side validated; record side needs one UAC)

Ported from SimGolf `re/tools/ttd_record.py` + `ttd_query.py` and TD5RE `ttd_mcp_workflow.md`. WinDbg, cdb
and `ttd.exe` are already installed (Store app; aliases in `%LOCALAPPDATA%\Microsoft\WindowsApps`).

- **record** attaches to a game started by the normal launchers, so the game lease stays with its owner.
  Needs admin: one UAC prompt per record. Refuses to reuse a tag (traces are evidence). `--ring-mb` bounds size.
- **query** (no admin, any session, parallel): `modules`, `writers`, `readers`, `execs`, `raw`.
  `writers` prints position, writer IP as `module!rva`, address, old -> new value.
- **SC3-specific:** all 30 DLLs link at `0x10000000`, so the loader relocates all but one. `--module X --rva Y`
  resolves the module base inside the trace and translates. RVA output is limited to SC3's own modules
  (`original/modules` + the exe); anything else prints as `name+offset`.

Validated 2026-10-05 against SimGolf's indexed trace `log/ttd/stories_load/golf_clean01.run` (1.09 GB):
- `execs --addr 0x40afa0` = **2**, matching SimGolf's recorded note (both `FUN_0040afa0(1)` calls are in the trace).
- `writers --addr 0x55b028` = 2 writes, both at `golf_clean!0x004aa6f3`, `0x0 -> 0x0`. Each query ~1.8 s once indexed.
- `modules` shows relocation in action (`jgld` at `0x03ac0000`).
- One bug caught in testing: the first version translated every non-SC3U module from `0x10000000`
  (printed `0x100aa6f3` for an exe address). Fixed by restricting RVA space to known SC3 modules.

**First recording to make** (needs Mariano at the machine for the UAC prompt): bigger-cities item 3 / the
pause question - attach at city load, record the unpause, then `writers --module <clock module> --rva` on the
clock suspend-depth field `+0x140` to list every writer with old -> new values.

## 4. Linux named build - FOUND (free Loki DEMO), matching NOT YET RUN

Nothing in this repo had the binary: the SDK headers (`GZCOM_INTERFACE_CATALOGUE.md`) were derived from the
Loki Linux build, but the build itself was never obtained. The **freely redistributable Loki demo** is on
archive.org's Loki demos ISO: `https://archive.org/download/loki-demos/loki-demos.iso/sc3u_demo.tar.gz`.
Stored at `original/loki_demo/` (gitignored), SHA-256 anchors in `original/loki_demo/ANCHORS.txt`.

- One x86 ELF per SC3 module (`lib/libSimRCI.so`, `libSimNtwrk.so`, ... `libGZWinD.so`) plus `sc3u_demo.x86`:
  a 1:1 module map onto `Apps\*.dll`.
- `.symtab` is stripped, but **`.dynsym` names 47,156 defined functions** (GCC 2.95 mangling, full arg types),
  e.g. `Apply__19cSC3AgDeveloperRuleRC14sIGZRectUint32Uiii`. Per module: SIMUI 3,607, SIMSPR 2,770, SIMRCI 2,327,
  STRTSIM 2,110, SIMADV 1,806, SIMDSTR 1,795 ... exe 13,347. Comparable to the 50,679-row Windows tracker.
- `ghidra_headless.ps1 -Linux <lib.so> -Import|-Export` added (project `SC3linux_<stem>`, export
  `re/ghidra_export_linux_<stem>`). `-Import` runs pre-script `SetGnuV2Demangler.java`: GCC 2.95 mangling is
  only understood by the DEPRECATED demangler (`demangler_gnu_v2_24 -s gnu`); Ghidra's default AUTO left every
  name mangled. With it, names arrive as `cSC3BuildingLibrary::SetFundingPercentage` with argument types.
- libSimRCI.so: 5,243 functions, of which **1,165 are separate 4-byte copies of `__i686.get_pc_thunk.bx`**
  (GCC PIC helper). They are dropped before matching, otherwise every Linux callee set contains them.
- **Caveats:** it is the DEMO (scope may be trimmed vs Unlimited; verify per module), GCC 2.95 vs MSVC codegen,
  and Linux platform layers (SDL/OpenAL) differ from DirectDraw. Names stay `[LINUX-HINT]` until an SC3U-side
  witness confirms, same rule as the iOS and SDK oracles.

### Matcher - `re/tools/linux_match.py` (first module: SIMRCI)
Features from `re/scripts/FuncFeatures.java` (strings, 32-bit constants >= 0x10000 that are not addresses,
callees), vtables from `read_vtables.py` logic (Windows, split at constructor-loaded starts) and
`re/scripts/DumpElfVtables.java` (Linux, after relocation; GCC slots 0-1 are offset/typeinfo). Outputs in
`re/match_linux/` (gitignored).
1. **Anchors:** a string/constant unique on both sides, mutual best, no tie. SIMRCI: **32**. Mostly GZCOM
   `QueryInterface` IIDs and layer-type ids. Spot check against existing names: `findBestLandUse` <->
   `sc3_inddev_pick_building`, `EndOfMonth` <-> `sc3_res_simulate_population`, QI <-> `sc3_*_query_interface_*`.
2. **Vtable alignment:** a Windows and Linux vtable of equal length whose matched slots agree position for
   position -> pair every remaining slot. Windows 182 vtables, Linux 264.
3. **Callee propagation:** a matched pair with exactly one unmatched callee each -> pair them. Iterate 2+3.

Measured precision (10 random 50/50 anchor splits, withheld half must be re-derived):
| propagation | final pairs | held-out agree | held-out DISAGREE |
|---|---:|---:|---:|
| none (anchors + vtables) | 70 | 8 | 0 |
| **callees (default)** | **80** | **8** | **0** |
| callees + callers | 86 | 8 | **4** |
Caller propagation is wrong across compilers (inlining differs), so it is off. **Coverage is the limit, not
precision: 80 of 3,899 SIMRCI functions (2.1%).** Every vtable alignment needs at least one seeded slot, and
the retail build has few unique strings/constants.

### Class-name join attempt (2026-10-05) - 80 -> 102 pairs, precision held
A literal class-name join is not available: Windows has no class names (RTTI off, item 1b) and the catalogue
documents only a handful of vtables, by INTERFACE name (`cISC3ZoneLayer`), not the concrete `cSC3*` classes Linux
names. What was built instead, all in `linux_match.py`:
- Confirmed the premise: an anchored class's vtables line up slot for slot (`cSC3BuildingMuseum` 5<->5:
  QueryInterface AddRef Release AsISC3Building AsISC3Occupant; `cSC3CityCellMapSized<short>` 18<->18).
- **Set anchors:** the whole set of constants (or strings) as one key. QueryInterface bodies share single IIDs
  with their bases, but the IID set is usually unique. Anchors 32 -> 39.
- **Tie rejection** in vtable alignment (inherited slots, e.g. one QueryInterface shared by
  `cSC3OccTestDefault` / `cSC3SimRoadFilter` / `cSC3SimTransportFilter`, made the old aligner take the first).
- **Linux `PTR_*_virtual_table` labels skipped** (pointers to vtables, not vtables).
- **Offset placement** of a Linux vtable inside a merged Windows run (>= 2 agreeing slots): added 0 on SIMRCI.
  The one inspected case was correct to refuse: `AddRule` is a shared base implementation at slot 3 of one
  Windows class and slot 7 of `cSC3LandfillZoneDeveloper`.
- Library-call set anchors: added 0 (only 105 Windows SIMRCI functions call any import; see below).
Result: **102 pairs (2.6%)**, held-out 4/4 agree, 0 disagree. Remaining Windows vtables: 9 fully matched,
66 seeded but not alignable (46 because the Linux home has another length, i.e. a different class sharing a base
slot; 19 ties), 107 with no seeded slot at all.

### The lever found: framework code is IMPORTED on Linux, STATIC on Windows
On Linux, GZ/RZ framework functions arrive by name from other libraries: callees include
`cRZRefCount::AddRef/Release` (43/38 callers), `RandomUint32Uniform` (37), `ConvertToUint32` (34),
`pthread_mutex_lock` (332). On Windows the same code is statically linked into every DLL as anonymous internal
functions. So once the Windows copies of the framework (`cRZRefCount`, `cRZString`, random, critical sections, ...)
are named ONCE, every call to them becomes a shared, identifying callee token on both sides. Plan:
1. import `sc3u_demo.x86` and the GZ libs (where the framework is defined, by name);
2. name the Windows framework copies inside each DLL (they are byte-similar copies across all 30 DLLs, so one
   matched copy names the rest by hash);
3. re-run with "callee-name set" anchors. Expected to beat BSim, which remains the fallback (same ISA, GCC 2.95 vs
   MSVC 6, unmeasured).
No tracker writes from this yet: names stay `[LINUX-HINT]`.

## 5. Matching compiler - toolchain IDENTIFIED, NOT obtainable yet (parked)

Correction to the first survey (which said SC3 = SimGolf's cl 12.00.8168). Rich header by product id:
- SC3U.exe: C++ (`0x0b`) build **8447** x122 objects, C (`0x0a`) 8447 x11, only one 8168 object. SIMRCI: C++ 8447 x75.
- SimGolf golf_clean.exe: C/C++ 8168 (152 + 109); 8447 appears there only as the linker.
- cl **12.00.8447 = VC6 SP4**. (richprint `comp_id.txt` labels only the 8447 *linker*, as "SP5 imp/exp".)
- The game DLLs are timestamped **2000-04-19**, so SP5 (2001; its cl reports 12.00.8804) is ruled out.

What was tried (2026-10-05):
- archive.org `vs6sp5` (MD5 971e5b17...): ships cl/c1/c1xx/link/cvtres but **no c2.dll**. With SimGolf's c2.dll:
  `fatal error C1900: Il mismatch between 'P1' version '19991026' and 'P2' version '19970710'`. Removed.
- archive.org `X05-86592` (SP4, **Aug 2000 re-press**, raw 2448-byte-sector MDF converted to ISO): its
  c1/c1xx are dated **2000-05-16** (after the game build, same sizes as SP5's) and it has **no c2.dll** either.
- The Processor Pack (`vcpp5`, Dec 2000) has a c2.dll but post-dates the build. Not used.
- The original Jan-2000 SP4 pressing (front end matching the 19991026 IL, plus its back end) was not found.

Machine note: a global `CL=/MP12` environment variable is set; clear it for VC6 builds (`D4002`).
Defender note: unpacking a whole VS6 service pack writes old copies of `regsvr32.exe`/`hh.exe`/`makecab.exe`, which
ASR rule `C0033C00-D16D-4114-A5A0-DC9B3A7D2CEB` blocks (5 notifications on 2026-10-05). List first, then extract by name.

**libjpeg FidDb, measured:** SimGolf's `re/fid/simgolf_vc6.fidb` (VC6 8168 CRT + SimGolf's prebuilt IJG
`JPEG.lib`) dry-applied to GIMEX.DLL with SimGolf's `ApplyFid.java`: **2 names of 504 C0** (`_jpeg_std_error`
at `0x100117b5`, `_DllMain@12` at `0x10017242`; `re/fid/GIMEX.DLL.fid_dry.tsv`). libjpeg is confirmed present, but
GIMEX's copy is a different build. The FID route needs the matching compiler, so it stays parked with item 5.

## 6. Headless Ghidra MCP - ADOPTED as opt-in, NO Ghidra upgrade needed

The web sweep suggested ReVa / bethington ghidra-mcp, which target Ghidra 12.1.3. Not needed: TD5RE already runs
`mrphrazer/ghidra-headless-mcp` (pyghidra, 212 tools, read-only by default). Cloned to `tools/ghidra-headless-mcp`
(gitignored; commit b9c491a), driven by Simcity's own Ghidra 12.1.2 and the py 3.12 pyghidra 3.0.2 already installed.
- Smoke test: initialize -> 212 tools -> `project.program.open_existing` SC3_SIMRCI read-only ->
  `decomp.function 0x10002573` returns the same C as the text export. ~13 s cold start.
- **Lock hazard, measured:** while a server session holds a project open (even read-only), `ghidra_headless.ps1
  -Count` on that project did not error, it **hung 13+ minutes**. So the server is NOT registered for every
  Simcity session. Opt-in: `claude --mcp-config tools/ghidra-mcp.json`, and `program.close` when done.
- `ghidra_headless.ps1` now fails fast on a held lock (tested: held -> error in 0.9 s; free -> normal run,
  SIMRCI `TOTAL_FUNCTIONS=4040`). A stale lock file from a crashed run does not block it.
- Use it for interactive questions (xrefs, types, one-off decompiles with retyping in-memory). Bulk work stays on
  the text export + headless scripts, which never lock out other sessions.

### Framework lever + all modules (2026-10-05, afternoon)
**Imports.** All 29 Linux binaries imported and dumped (`re/scripts/linux_import_all.ps1`, resumable, 3 parallel):
21 minutes once Ghidra's `Decompiler Switch Analysis` was turned off in `SetGnuV2Demangler.java`. With it on,
`sc3u_demo.x86` stalled 31+ minutes in that analyzer (decompilers respawning at ~0 CPU, no completion); with it
off the same import took 6 minutes. The matcher does not use jump tables. Windows features for 30 modules: 4 minutes.

**Framework copies (no Linux needed).** `FuncFeatures.java` now emits a masked instruction hash (7th column).
2,045 hashes occur in >= 3 Windows modules and cover **23,697 Windows functions**; in the tracker that is 22,142
rows, of which **18,500 are C0 = 47% of all C0**. The real unreviewed backlog is far smaller than 39,169.
`re/tools/framework_names.py` also writes, without applying anything:
- `framework_inherit.tsv`: **823** unnamed C0/C1 copies whose other copies carry exactly one C2+ name.
- `framework_clashes.tsv`: **76** identical bodies (322 rows) that sessions named differently, 51 of them > 64 bytes,
  e.g. one 3,457-byte body is `sc3_dstr_resample_field_2d` in SIMDSTR and `sc3_gfx_resample_image` in SIMUI.

**Naming the framework from Linux.** `SC3U.exe` vs `sc3u_demo.x86`: 1,213 pairs (10.6%), held-out 83/90.
Quality gates on hash -> name: drop "generic shapes" (copies > 1.25 x modules: one 32-byte destructor had 195 copies
in 23 modules) and GCC-only names (SGI STL internals, `__builtin_*`; MSVC 6 ships Dinkumware's STL). Result:
~290-334 named bodies (oscillates between iterations), e.g. `cRZCOMDllDirector::*` once in every module, `cGZWin::*`
(81), `cRZVariant::*` (54), `cRZFile::*` (22). Spot check against existing tracker names on the same bodies: 12/15
agree (`cGZWin::SetArea` = `sc3_gzwin_set_area`, `cRZDate::DateString` = `sc3_transit_format_date`, ...).
Bug found on the way: import names need normalising (`<EXTERNAL>::x` on Linux, `MSVCRT.DLL::x` on Windows), else
the builds share zero `FW:` tokens.

**All modules** (`re/tools/linux_match_all.py`, iterates match <-> framework naming; `match_summary.tsv`):
| | pairs | coverage | held-out |
|---|---:|---:|---:|
| first full run (GZ DLLs vs their own `.so`) | 3,659 | 5.6% | 269/301 = 89.4% |
| **GZ DLLs matched against `sc3u_demo.x86`** | **4,080** | **6.2%** | **270/306 = 88.2%** |
On Linux the framework lives in the exe; the GZ `.so` files are ~800-function stubs. GZWinD 22 -> 133 pairs,
GZResourceD 21 -> 162. Framework names lifted SIMRCI only 102 -> 112.
Weak modules by held-out: SIMADV 9/16, AUDIO 6/11, SIMTRANSIT 8/12, SC3U 83/90. Clean: SIMMISC 22/22, SIMDIRT 15/15,
SIMSPR 26/27, SIMUTIL 8/8, SIMVARIABLES 8/8.

**Verdict.** ~88% is hint quality, not tracker quality. Use the pairs as `[LINUX-HINT]` to pick and orient work.
Promote a name only with an SC3U-side witness. The 823 inherit proposals and 76 clashes are tracker decisions
for the owner, independent of Linux.

### Applied to the tracker (2026-10-05, evening) - via `tracker.py batch` (new: one splice, gates, blast radius)
**Inherited names: 708 rows -> C1.** From the 823 proposals, 115 rows were dropped first: 11 hashes occur more
than once inside a single module, i.e. template instantiations sharing one tiny body (`sc3_pollution_set_all_cells`
had 31 copies in 5 modules), where one name would be wrong for most copies. Each applied row's note:
`[FRAMEWORK-COPY 2026-10-05] masked-instruction hash ... identical to <module> <rva> (<conf> <name>); named by
identical copy, body not read here.` Blast radius verified = 708. C0 39,169 -> 38,582. `--legacy-names` let 22 rows
reuse pre-convention names that already exist at C2+ (`sc3spr_*`, `sc3ui_*`).

**Clash renames: 205 rows across 65 bodies** (`re/match_linux/clash_decisions.tsv`, applied list `apply_clashes.tsv`):
- 10 bodies left alone (template shapes: >1 named copy in one module, different names may be right).
- 44 by rule, in order: highest confidence, module-NEUTRAL name over a caller-context one (`sc3_util_move_file`
  over `sc3_dstr_move_file`), unsuffixed over `_gzwind`-style disambiguators, most rows, NAME_OK, GZ/SC3U home.
- 6 obvious neutral names (e.g. `sc3_citycellmap_in_bounds_rect/point`, the CityCellMap template both layers share;
  `sc3_gz_director_base_ctor`, identical in 4 modules).
- 15 by reading one body each (subagent, read-only, mechanical justification per name). Several old names were not
  just inconsistent but WRONG: the body named `sc3_*_ini_locate_section` in six modules has no INI parsing, it reads a
  binary index of u32-length-prefixed names + u32 -> `sc3_io_lookup_name_in_file_index`.
- 1 left manual: the 37-byte helper ctor (`sc3_scenario_helper_ctor` | `sc3_strtsim_helper12_ctor`).
Every renamed row keeps `[RENAMED 2026-10-05] was <old>; ... canonical by <reason>` in notes. Confidence unchanged.
Blast radius verified = 205.

**Notes updated:** 223 mentions of the 203 old names replaced in 53 docs under `re/analysis/` and the root `*.md`
(whole-name matches only; every old name mapped to exactly one new name and none is still used by another row).
This file keeps the old names on purpose as examples. Diffs are name-only (equal lines in/out, CRLF untouched).

**Correction, same evening: 4 of the 205 renames were wrong and are reverted.** Resolving the last manual clash (the
37-byte "helper ctor") showed its body has 23 copies in 7 modules, 10 inside STRTSIM alone, each installing
different vtables: a generic ctor SHAPE, not one function. The template-shape filter used for the clashes counted
only NAMED copies per module, so shapes with one named copy per module slipped through. Re-checked against ALL
copies: 6 decided bodies are shapes. Kept: `sc3_util_vector40_insert` and `sc3_util_deque_growmap_b` (the names
describe the shape, true for every copy) and the helper ctor (both names kept, `[NOT-A-CLASH]` note on both rows).
Reverted (tracker `revert_clashes.tsv` + 3 doc lines restored only where they reproduce the committed text):
`sc3_ntwrk_scalar_deleting_dtor` (had become `sc3_valvelayer_scalar_deleting_dtor`, a 28-byte shape with 1,000+
copies), `sc3_cogamecmd_ctor` and `sc3ui_smallobj_ctor_5a6` (had become `sc3_gz_reskey_init_empty`),
`sc3ui_ctor_clsid_3370d1a5` (had become `sc3_ntwrk_predicate_ctor`). The 708 inherited names re-checked the same
way: 0 affected. Net clash renames: **201 rows**. `tracker.py batch --legacy-from <backup>` was added so a revert can
restore a pre-convention name that now exists only in the backup.
Rule for next time: a hash is a candidate for "one function" only if it has at most ONE copy in EVERY module.
