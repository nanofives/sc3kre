# CodeView symbols for SC3U.exe (retail CD 2.0.949)

2026-11-05. SC3U.exe was 100% stripped in every release we had (GOG, Steam). A Simtropolis reply pointed out that
the retail CD's SafeDisc-encrypted `SC3U.ICD` keeps the full CodeView debug info. A SafeDisc-decrypted copy is on
debugging.games (`/_files/Windows/[WIN] SimCity 3000 Unlimited (US) (2.0.949) [2000-04-19].7z`). It covers the
**main exe only**, not the DLLs.

Local copies (gitignored, never publish, these are EA's symbols): `original/retail_2.0.949/`.

| file | SHA-256 (first 16) | bytes |
|---|---|---:|
| `sc3u_949.7z` (archive as downloaded) | `d452f20a2acb5ce8` | 2,926,329 |
| `SC3U.ICD` (retail, encrypted) | `08e580f152b924fa` | 5,302,849 |
| `sc3u.exe` (decrypted, CodeView left in the overlay) | `d8ec8983f29cdcd9` | 5,302,849 |

## Same build as the anchor

`re/tools/` has no PE differ for this; it was a one-off pefile section compare. Against `original/SC3U.exe`:

- Same 5 sections, same VAs and sizes. `.data`, `.rsrc`, `.reloc` byte-identical.
- `.text`: 10 bytes differ in 3 runs: `0x00406516..17` and `0x00406549..4d` (both inside `cSC3App::DoCDCheck`,
  `0x004064ee`) and `0x004ceffd..ff`.
- `.rdata`: 26 bytes differ, 13 two-byte runs spaced 0x14 apart from `0x004f1b5e`.
- The anchor still has the 3 debug-directory entries (MISC, FPO, CODEVIEW) pointing at file offset `0x11a000`,
  where its file ends. The retail exe has the data there.

So every CodeView address is valid for `original/SC3U.exe` and for the GOG 2.0.949 exe (anchor + 8 bytes).

## What is in it

CODEVIEW entry: `NB11`, 0x3e1a84 bytes at file offset `0x12cf90`, 817 subsection directory entries. Read with
Microsoft `cvdump` (github.com/microsoft/microsoft-pdb, `cvdump/cvdump.exe`):

| | count |
|---|---:|
| S_PUB32 publics (decorated C++) | 10,339 (`.text` 7,505, `.rdata` 1,214, `.data` 1,620) |
| S_GPROC32 / S_LPROC32 with locals, registers, line numbers | 1,602 / 112 |
| types | 40,901 |
| classes / structs with a definition | 2,272 |
| data members with offsets | 8,429 |
| vtable slots (primary vtables) | 10,583 |

Full procedure records exist only for `sc3app` (the game app, `D:\SC3Projects\SC3Gold\SC3App\source\*.CPP`). The
framework libraries linked into the exe (GZWin, Rizzo, RizzoWin32, Network, GZWWW, GZResource, Gonzo, SimLib,
GonzoWin32, NetworkWin32, GZVideoPlay) have publics only. Code symbols by source project:
sc3app 1,714, GZWin 1,221, Rizzo 1,087, Network 690, GZWWW 654, GZResource 496, RizzoWin32 493, Gonzo 237,
SimLib 236, NetworkWin32 141, GonzoWin32 114, the rest import thunks.

Types include 108 `cISC3*` interfaces (`cISC3City` 157 slots, `cISC3App`, the advisors, the budget, building,
zone, power, pollution, crime, fire, police, weather and world layers, the occupant manager, `cISC3WinMain`) and
the `cIGZ*` framework interfaces. **Only interfaces the exe itself references are there.** There is no
`cISC3TrafficLayer`, no transit and no network layer.

## Tools

```
cvdump.exe original/retail_2.0.949/sc3u.exe > original/retail_2.0.949/cvdump_sc3u.txt
py -3.12 re/tools/cv_symbols.py      # -> cv_functions/cv_data/cv_vtables/cv_members/cv_classes.tsv, CV_CLASSES.md
pwsh re/scripts/ghidra_headless.ps1 -Script ApplyCvSymbols.java -Write -Args "<cv_functions.tsv> <cv_data.tsv> <log>"
pwsh re/scripts/ghidra_headless.ps1 -Export
py -3.12 re/tools/cv_tracker.py      # -> tracker_batches/exe_edits.tsv, exe_adds.tsv, dll_edits.tsv
py -3.12 re/scripts/tracker.py batch|add <tsv> [--legacy-names] [--skip-rejected] --apply
```

- `cv_symbols.py` undecorates with DbgHelp `UnDecorateSymbolName` (Microsoft's own undecorator) and checks the
  type-derived vtables against the exe's real ones (below).
- `ApplyCvSymbols.java` mutates the program, hence the new `-Write` switch on `ghidra_headless.ps1` (without it
  `-Script` stays read-only).
- `tracker.py add` is new: inserts rows that do not exist yet, in address order inside the module, and verifies
  every old record is byte-identical afterwards.

## Vtables: how slots are derived, and how far to trust them

A class's primary vtable = the vtable of its base at offset 0, plus its own `INTRO` virtuals at their `vfptr offset`.

**Overloaded virtuals.** VC6 writes ONE `vfptr offset` for a whole overload group (raw NB11 bytes: methodlist
`0x29df` holds the three `cISC3City::Init` entries, each with `vbaseoff = 0x1c`). This is not a cvdump display bug.
In all 307 such methodlists, every entry carries the same offset. The group fills the k slots **ending** at that
offset, in methodlist order. `cISC3City`: `Init(cIGZDBSegment*)` +0x14, `Init(cISC2Importer*)` +0x18,
`Init(cISC3NewCityInfo&)` +0x1c, `Save` +0x20.

**Measured against the exe.** For every class with a primary vtable (`??_7X@@6B@`) in `.rdata`, each derived slot
was compared with the function the real vtable points at:

| result | slots |
|---|---:|
| method name agrees | 2,170 |
| overload group order agrees (argument lists compared) | 266 of 266 |
| real slot is `__purecall` (abstract class) | 1,294 |
| method name differs | 90 |

The 90 differences sit in 10 multiple-inheritance or nested classes: cWinBMPViewGVExtra 24, cWinBMPView 24,
cGZFileSystem 13, cGZApp 10, cSC3Newscast 5, cGZDBSegmentIndexedFile 5, cGZDBRecordIndexedFile 4,
cGZAnimationPlayer2 2, plus 1 each in cRZNetManager, cRZCookieManager, cGZRegistry. Single-inheritance
interface chains (all `cISC3*`) had none.

**Holes.** 26 classes have one or more slots that CodeView does not describe at all. They all come from
`cGZWin` +0x194 = `cGZWin::SetSize(cRZPoint const&)` (real vtable). CodeView lists that overload as `VIRTUAL`
(override) with no offset, although no base declares it. `CV_CLASSES.md` prints such slots as "(not in CodeView)".

`CV_CLASSES.md` (local) shows, per class: bases, size, every slot (offset, method, introducing class,
attribute, signature, and the exe implementation when the class has a vtable in the exe), then the data members.

## What was applied (2026-11-05)

**Ghidra, project `SC3` (backup before the run: `ghidra/_bak_precv_20261105/`):**

| | functions |
|---|---:|
| named + signature applied through the Microsoft demangler | 6,435 |
| named from the undecorated name (C names, static procs, demangler refusals) | 188 |
| created (no function existed) and named | 501 |
| left alone: thunks | 271 |
| left alone: address inside another function (`0x00432785`, `0x0046a4a8`, `0x0046b207`, `0x0047604d`, `0x0047e565`, `0x004869f5`) | 6 |

Data labels: 1,295 (vftables, statics, globals). Skipped: 1,670 `??_C@` string literals and `__imp_` IAT slots.

**Export:** `re/ghidra_export/` now has 12,300 functions (was 11,799), 0 decompile failures, 287 still `FUN_`.
File names and the header line use the **qualified** name since this change (`004064ee_cSC3App__DoCDCheck.c`).
The pre-CV export is kept as `re/ghidra_export_pre_cv/`. `query.ps1 -Xref FUN_<addr>` translates to the current
name. `symbols.csv` `isLibrary` is now `true` for most exe functions, because CV names are IMPORTED symbols.
Nothing reads that column.

**Tracker:**

| | rows |
|---|---:|
| SC3U.exe rows tagged `[CV-SYMBOL 2026-11-05]` | 6,616 (C0 -> C1: 5,895) |
| SC3U.exe rows added (functions Ghidra lacked), C1 | 300 |
| DLL rows tagged `[CV-COPY 2026-11-05]` | 9,265 (C0 -> C1: 7,858) |
| skipped: rows that already fail a gate (C2 without subsystem/new_name, C3/C4 without evidence) | 18 |

C0 38,087 -> 24,334, C1 5,074 -> 19,127, rows 50,621 -> 50,921. Subsystem `src:<project>` where it was empty.
`new_name` untouched (the `sc3_<subsystem>_<verb>_<noun>` rule stands). Skipped rows: SC3U.exe `0x00405092`,
`0x004064ee`, `0x0040b761`, `0x0040cb70`, `0x0040cc08`, `0x0040ed1c`, `0x004218b0`, `0x00422c4e`, `0x0042e409`,
`0x0042f629`; GZResourceD.dll `0x1000b88a`, `0x100168cb`; SIMGEOM.DLL `0x1001fa0c`; SIMSPR.DLL `0x1001ddb8`,
`0x1001de0c`, `0x10050cdf`, `0x10050d09`, `0x10057826`.

**DLL copies (`[CV-COPY]`)**: masked-instruction hash from `re/match_linux/win_*.tsv` equal to exactly one
CV-named exe function. Gates: the hash occurs once in the exe, at most once inside the DLL, in no more than
1.25 x as many copies as modules (generic shapes), the exe body is at least 16 bytes, and the exe address is not
an ICF fold of differently named functions. Rejected by the gates: 29,026 (hash repeats in exe), 1,138 (< 16 B),
952 (exe copy has no CV name), 176 (repeats inside the DLL), 56 (generic shape), 53 (ICF fold), 11 (no row).
The DLL Ghidra projects were NOT renamed. The names live in the tracker notes only.

## Interface pass: DLL vtable slots named from the interface each vtable implements (2026-11-05)

The DLLs have no symbols, but their classes implement interfaces whose vtable layout CodeView gives exactly. A
vtable layout is the binary contract, so a DLL vtable that implements `cISC3City` has `cISC3City`'s methods in
its slots. What was missing is which DLL vtable implements which interface. Four steps, all tools in `re/tools/`,
all outputs in the local `original/retail_2.0.949/iface/`:

1. **`qi_scan.py`: every vtable, by emulating QueryInterface.** Every GZCOM vtable starts with QueryInterface.
   Each candidate (a data dword whose next two dwords are also code pointers) is run under unicorn as
   `QueryInterface(id, &out)` against a fake object, for every candidate id (immediates in the body and its
   base-class chain, plus every id seen anywhere). Result per vtable: the ids its subobject answers, and where
   `*ppv` points for the others. Traps fixed on the way: MSVC puts the "ask the base class" branch AFTER the
   first `ret 8`, so the immediate scan must not stop at `ret`; candidates run with bogus arguments write into the
   image and the fake vtable, and a unicorn write hook reports a store without blocking it, so the image is
   restored after any such run (without that, 3,181 of 3,420 exe targets came back unusable).
   Exe check against CodeView's `vftable` labels: **205 of 211 QueryInterface vtables found, 0 false positives**
   (missed: 4 `cSC3OccupantManagerAnim` QIs that do not emulate cleanly, 2 that return false for id 1).
   All modules: 2,221 vtables (2,016 in DLLs) in 31 s.
2. **`iface_ids.py`: interface ids from the exe.** For each exe class, CodeView gives every base subobject's
   absolute offset (`cSC3App`: `cIGZSystemService` +0, `cIGZApp` +0x18, `cISC3App` +0x30). An id answered at
   offset x can only be an interface at x. Intersect over classes, eliminate, repeat. MSVC's `{for `X'}` vtable
   labels are NOT usable for this: under multiple inheritance they do not name the owning base (reading them named
   `0x66` cIGZSystemService, the SDK's `0x6c` contradicts it; by offset `0x66` = `cIGZApp`).
   **53 ids, 7 of 7 that overlap the SDK headers agree, 0 conflicts.**
3. **`iface_linux.py`: more ids from the Loki Linux demo's named QueryInterface functions** (`re/match_linux/lin_*.tsv`).
   Rule: `cSC3X::QueryInterface` introduces `cISC3X`; when exactly one plausible constant is left in its body, that
   constant is the id. A plausible constant is >= 0x01000000 (the first run re-derived 7 of 8 known ids WRONG
   from addresses inside the Linux image such as `0x5092e0`) and is served by a vtable in the twin Windows DLL.
   Held-out on the known ids: **8 of 8 re-derived correctly** (50 not reachable by the rule). **17 new ids**, every
   one served by its twin DLL (`cISC3ResidentialLayer` `0x4106c508` in SIMRCI, `cISC3OccupantManager`
   `0xa1478afe` in SIMGEOM, `cISC3WinCityView` `0xa1634f05` and `cISC3CitySpriteManager` `0x416cc7f3` in SIMSPR, ...).
   Plus `0xfa1` = `cISC3City` from the exe consumer `cSC3App::CreateCity` `0x00407b5e`
   (`GetClassObject(0xa1a166cc, 0xfa1, &out)` stored to `cSC3App+0x48 mpCity`, a `cISC3City *`), and by ancestor
   elimination **`0x81c0cb7c` = `cISC3QueryInfo`** (U-044 closed). 85 ids in total (`iid_final.tsv`).
4. **`iface_name.py`: name the slots.** A vtable's interface = the most-derived named interface its subobject
   answers (all its named ids must lie on that interface's CodeView chain). Named only if the vtable has at least
   as many code slots as the interface. If the subobject also answers unnamed ids, the named interface is a correct
   prefix (single inheritance), and that is recorded.

| | count |
|---|---:|
| DLL vtables named (126 of them as a prefix of a more derived, unnamed interface) | 871 |
| not named: no named id answered | 1,104 |
| not named: interface only forward-declared in CodeView (no method list) | 20 |
| not named: named ids not on one chain | 21 |
| slots named / distinct DLL functions / interfaces | 20,338 / 5,855 / 49 |

**Check against names sessions gave the same functions (C2+):** 306 contain the method name exactly, 23 share most
words, 128 are worded differently. Sampled, the different ones mostly say the same thing from the body's side
(`sc3_rci_get_serviceid_80f1e6d3` = `cISC3CityLayer::GetLayerType`, `sc3_ntwrk_hud_message_proc` =
`cIGZWinProc::DoWinMsg`, `sc3_gzstream_write_u32` = `SetFieldUint32`). `cSC3City` (SIMCITY `0x10013260`, walked by
hand from the SDK headers in the catalogue): 48 C2+ slots compared, e.g. +0x138 `BuildingLayer` ... +0x16c
`PollutionLayer` all equal the C3 names, and the overload pair +0x12c `CreateOccupant(cISC3OccupantAttrib*)` /
+0x130 `CreateOccupant(cGZResourceKey&)` equals the C3 `_attrib` / `_reskey` split.

**Applied:** tracker rows tagged `[CV-IFACE 2026-11-05] <Interface>::<Method> slot +0x.. (<signature>)`, C0 -> C1
(subsystem `iface:<Interface>` where empty): 5,036 in the first run, **721 more** after a correction, **141 more** after
the SDK-id follow-up below (5,898 in all). 9 rows skipped (they already fail a gate). The correction: the first run
looked rows up by the DLL FILE's spelling (`GZWIND.DLL`), the tracker spells `GZWinD.dll` / `GZWWWD.dll` /
`SIMVARIABLES.DLL`, so 721 existing rows were reported as "no tracker row" and left untagged. Matched
case-insensitively, **89** slot targets really have no row (`iface/missing_functions.tsv`); `ApplyDllNames.java`
creates them in Ghidra.

**Limits.** The layers that matter most for mods (`cISC3ZoneLayer`, `cISC3PowerLayer`, `cISC3PollutionLayer`,
traffic, transit, network) are only forward references in the exe's types, so CodeView gives no method list for
them. Their slots stay with the SDK-header walks in `GZCOM_INTERFACE_CATALOGUE.md`. A slot function shared by
several vtables (one trivial body for many getters) lists every slot it fills.

### Follow-up the same day: SDK-declared interfaces, more ids

`iface_linux.py` now also accepts interfaces only the SDK headers declare (`iface/sdk_classes.txt`, extracted from a
clone outside the tree). That needed one more guard: a class answers an interface's id only if it derives from it,
so an id that an UNRELATED class also answers is a shared base, not `cISC3X`. Without the guard the first run named
`0x81c0cb7b` `cISC3CrimeLayer` although the pollution layer answers it too, and `0x81c0cb7c` `cISC3PollutionLayer`
(it is `cISC3QueryInfo`). With it: held-out **10 of 10** correct, 0 wrong, **43 ids** from Linux names, every one served
by its twin DLL. 112 ids in total. The slot pass then named 130 more functions (141 rows).

**Placement check against the catalogue.** Two independent methods: the catalogue's arity fingerprint scan (s18) and
this pass's emulated QueryInterface. Where both give an answer they agree on **11 of 11** classes, at the same
vtable (budget, residential, city, sprite cell map, occupant manager, base advisor, ordinance, disaster, cell
cursor, weather, dirt bag).

## Newly located SDK interfaces walked with `walk_vtable_class.py` (2026-11-05)

s18c could not place `cISC3AuraLayer`, `cISC3LandValueLayer` and others: their inherited cell-map slots are adjustor
thunks with no `ret`, so there is no arity to fingerprint. The interface id locates them instead. 17 interfaces were
walked in report mode (vtable from the id, names from the header by slot position, the walker's strict arity check
and blocking collision audit): **0 arity mismatches; every measurable slot agrees** (aura and land value 1/1 measurable,
fire 11/11, ordinance 12/12, petitioner manager 9/9, dirt generator 8/8, the advisors 1..7 each).

The walker's own `--apply` was NOT used: it rewrites the whole tracker with `csv.DictWriter` (the churn CLAUDE.md
warns about), replaces existing notes (it would have wiped the `[CV-COPY]`/`[CV-IFACE]` notes) and sets C1 on rows
that may be higher. Its `--batch-out` rows went through `tracker.py batch` instead: note appended, new_name only where
empty, C0 -> C1 only. **92 rows** `[SDK-WALK 2026-11-05]`. 7 rows dropped: 3 functions (SIMADV `0x10006c6d`,
`0x10010f8c`, `0x1001d21a`) are one body filling slots of several advisor interfaces, so no single method name fits.

## Name audit against the original names (2026-11-05)

520 rows where a session's `sc3_*` name did not obviously match the CodeView name were sent to the worker account in 4
chunks (read-only: each body read and classified). 322 CONSISTENT, 135 VAGUE, 53 WRONG, 10 UNSURE.

- **WRONG -> renamed: 42** (`[NAME-AUDIT 2026-11-05] renamed from <old>: <reason> (original: <name>)`, confidence
  unchanged). Examples: SC3U.exe `0x00406eb8` and `0x0048440b` (resource manager, not a string manager), SIMCITY
  `0x100095ce` (`cRZDate::DayOfMonth`, returned the day, not the month), SIMCITY `0x1000addd` (`cRZRandom::Seed`, not
  a timer), six `cSC3CompressibleINIFile::EnumEntries`/`InitFileType` copies named as factory registration. 6 skipped
  (name changed since the clash table), 1 skipped (proposed name failed NAME_OK).
- **VAGUE: not renamed.** The names are not wrong, the original name already sits in the notes and as a Ghidra label,
  and renaming working names breaks references in docs and memory. Proposals kept in the local
  `original/retail_2.0.949/audit/vague_proposals.tsv`.

## For mod work: `re/tools/vtname.py`

```
py -3.12 re/tools/vtname.py cIGZWin 0xc8 0xe4            # slot -> method + signature
py -3.12 re/tools/vtname.py --pe SIMCITY.DLL 0x10013260 0x14c   # real vtable: target, tracker name, interface method
py -3.12 re/tools/vtname.py --scan re/harness/src/sc3resize.c --as cIGZWin   # every vt+0x.. in a file, candidates
```

The CodeView `cIGZWin` layout confirms what the UI mods worked out by hand in `sc3resize.c`: `vt+0xc8` "SetRect" =
`SetArea(long,long,long,long)`, `vt+0x98`/`+0x9c` = `GetL`/`GetT` (`mov eax,[ecx+0x80/0x84]`), `vt+0xd8` = 
`ScreenToWindowCoordinates`, `vt+0xdc` = `WindowToScreenCoordinates`, `vt+0xe4` = `IsPointInWindowScreenCoordinates`,
`vt+0x144` = `GZPaint`, and the paint walk's per-child `vt+0x148` = `Plot`. The mod sources were NOT edited: a
`vt+0xNN` is only meaningful with the object it is called on (`sc3resize.c`'s `vt+0x68` is not a window, although
`cIGZWin` +0x68 exists), and child worktrees edit the same files.

## Rules of evidence

- `[CV-SYMBOL]` = the original name and signature from the retail build's own debug info, at the exact address.
  It is a name witness, not a behaviour witness. It moves a row to C1 (named, body not read). C2 still needs the
  decompilation read, C3 a runtime or second witness, as before.
- `[CV-COPY]` = same body shape as a CV-named exe function. Hint quality, like the 2026-10-05 framework copies.
  A masked hash ignores constants, so two template instances that differ only in an ID can share it.
- `[CV-IFACE]` = the function sits in slot k of a vtable whose QueryInterface answers interface I's id, and slot k
  of I is that method (CodeView layout). A name witness for the slot, not for the body. C1.
- `[SDK-WALK]` = vtable located by its interface id, slot named from the SDK header by position, arity checked where
  measurable (the note says which). C1.
- `[NAME-AUDIT]` = a session name replaced because the body and the original name contradict it. Old name in the note.
- CV names beat `[LINUX-HINT]` and `[iOS-HINT]` names for the exe.
- `functions.csv` is published with the repo. The CV notes put about 16,000 original symbol names into it. Pushing
  that is the owner's call.
