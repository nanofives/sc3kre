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

## Rules of evidence

- `[CV-SYMBOL]` = the original name and signature from the retail build's own debug info, at the exact address.
  It is a name witness, not a behaviour witness. It moves a row to C1 (named, body not read). C2 still needs the
  decompilation read, C3 a runtime or second witness, as before.
- `[CV-COPY]` = same body shape as a CV-named exe function. Hint quality, like the 2026-10-05 framework copies.
  A masked hash ignores constants, so two template instances that differ only in an ID can share it.
- CV names beat `[LINUX-HINT]` and `[iOS-HINT]` names for the exe.
- `functions.csv` is published with the repo. The CV notes put about 16,000 original symbol names into it. Pushing
  that is the owner's call.
