# POST_P1.md — P1 is exited. What the next gate should be.

**Status: ⭐ ADOPTED 2026-08-17 (owner's call).** T1 → T2 → T3 are now the binding roadmap after
P1 and are recorded as such in `ROADMAP.md`, which also marks the old P2 – P5 annotate-first phases
superseded. This file remains the analysis behind that decision. Measured 2026-08-17.

**T1 is ACTIVE and is blocked on one thing: nobody has put a file we wrote in front of the game.**
`verify/city_load_test/` is built and waiting; the harness session (the only one running the game)
has been asked.

## P1 exit: all five criteria hold, verified now rather than quoted

| # | criterion | state |
|---|---|---|
| 1 | every `FUN_*` in all 31 binaries enumerated | ✅ **0 unenumerated `FUN_` bodies**, 50,621 rows |
| 2 | ≥ C2 across the toolkit-necessary set | ✅ **562 / 562 = 100%** |
| 3 | UI / audio / tooling / framework "enumerated, unclassified" | ✅ by design |
| 4 | subsystem map committed | ✅ `re/analysis/SUBSYSTEMS.md` |
| 5 | end-state decision taken | ✅ modding / format toolkit, 2026-08-17 |

**P1 is exited.** Every number above was re-measured for this document, because the export moved
three times in the last day and this project has been bitten by quoted figures.

### The number that looks alarming and is not

`functions.csv` is **39,845 C0 of 50,621 rows — 78% unread.** Under the retired gate that would be
a catastrophe. Under the toolkit end-state it is **the design**: criterion 3 says UI, audio, tooling
and framework modules stay enumerated-and-unclassified, and criterion 2 replaced "read everything"
with "read what touches a shipped byte". 562 functions did that job. Anyone quoting 78% as debt is
measuring against a gate that was retired for good reasons (`GATE_RESCOPE.md`).

## What the toolkit actually has, and what it does not

| format | read | write | evidence |
|---|---|---|---|
| QFS / RefPack | ✅ | ✅ **byte-identical** | compressor transcribed from GZResourceD `FUN_1001694d`. `qfs_encode.py --selftest`: **60/60 city payloads** and **63,931/63,931 sprite streams**. The sprite streams had only ever been DECOMPRESSED before 2026-08-17 |
| city save family | ✅ 59/59 | ✅ **byte-identical**, 5 layers | `city_roundtrip.py`; plus an editing API, `city_write.py` |
| sprites | ✅ | ✅ **byte-identical** | `sprite_encode.py --selftest` = **62,552/62,552**, reproduced in one command 2026-08-17 |
| `.IXF` container | ✅ | ✅ **byte-identical, exposed** | `ixf_parse.py` `layout()`/`build()`/`roundtrip()`; `--selftest` = **657/657** containers across the whole install, 8 extensions, selected by MAGIC not extension |
| `SYS.PAK` | ✅ 51 ini files | ❌ none | `syspak_parse.py` is read-only |
| FEZC / GVF (iOS) | ✅ | ❌ none | cross-reference only, not a modding target |

**And one claim that is not evidence-backed at all: no file this project wrote has ever been loaded
by the game.** Everything above is a structural result. `verify/city_load_test/` holds a four-file
ladder built to settle it, and it needs someone running the game.

## The three gates, in dependency order (ADOPTED)

### T1 — PROVE THE WRITE PATH (the falsifiable one)

**Exit: the game loads a file this project wrote, and shows the edit.** Run
`verify/city_load_test/` in order T0 → T1 → T2 → T3 and record each result. The README commits to
what each outcome means *before* the run.

Why first: every other toolkit claim inherits from this one. If T3 fails, the editing API needs a
checksum or derived-state fix and T2/T3 below change shape. **Cost: minutes, by whoever runs the
game.** It is the cheapest high-information step available and it is currently blocked on nobody
having tried it.

### T2 — EXPOSE THE FORMATS AS A LIBRARY

**Exit, measurable:** every format with a proven write path has (a) a documented read and write
entry point in `re/tools/`, outside any test harness, and (b) a `--selftest` that round-trips the
shipped corpus and reports `N/N`.

Concretely: promote the `.IXF` container writer out of `city_roundtrip.py` into `ixf_parse.py`
(or a new `ixf_write.py`), and give `qfs_encode`, `sprite_encode` and `city_write` a consistent
surface. This is packaging, not discovery — the hard parts are done.

### T3 — DEMONSTRATE A MOD END TO END

**Exit: one change, made with these tools, visible in the running game.** The evidence says the
content is data-driven (`U-006`: no per-building classes in code; `SC3Tune.INI` and `SYS.PAK` drive
the taxonomy), so the highest-value target is a tunable or an asset, not a save edit.

`[UNCERTAIN]` whether `SYS.PAK` needs a writer for this — depends on whether the game reads loose
files that shadow the archive, which has not been tested.

## What is deliberately NOT proposed

- **Reading more functions.** Criterion 2 defines what the toolkit needs and it is met. The next
  function read should be one a *specific* toolkit task demands, not a coverage number.
- **The old P2–P5 phases.** They were written for annotate-first with a possible source port. The
  port is closed. Folding them into T1–T3 is the honest bookkeeping.
- **Chasing `0x16`.** It is the most interesting open question in the format
  (`CITY_SAVE.md`), but it blocks nothing: `city_write.py` refuses to write it and every shipped
  file round-trips with it intact.

## Open items that should NOT gate the next phase

62 rows in `UNCERTAINTIES.md`, ~19 open. The ones touching the toolkit:

- **`U-029`** — the `u16` permutation's purpose, the `3000/5000/8000` keys, the `this+0x3c`
  23-vs-92-byte mismatch. Does not block writing: the permutation round-trips untouched.
- **`U-039`** — unreferenced tail bytes in 7 `.SNR` files. Preserved verbatim; blocks nothing.
- **`0x16`** — no producer found, no name. See above.

None of these prevents T1, T2 or T3. Recording that explicitly so they are not treated as blockers.

## Recommendation

**T1 now**, because it is minutes of work, it is the only claim in the project resting on nothing,
and its outcome changes what T2 and T3 should look like. T2 next as pure packaging. T3 last, since
it is the one with a genuine unknown in it (`SYS.PAK` write, or loose-file shadowing).

---

## T1, first empirical attempt (gzcom session, 2026-08-17) — a precondition cleared, T1 itself still open

**T1 is NOT met. What follows removed one risk and produced one methodological result; it did not put a
written file in front of the game's loader.**

### What was done

1. `Cities\` snapshotted hash-for-hash first: 59 files, 24.3 MB.
2. `re/tools/city_write.py Cities --selftest` re-run unmodified as a precondition: **59/59 byte-identical**.
3. A shipped save copied to a scratchpad (never edited in place) and given the narrowest documented edit:
   `Berlin, Germany.sc3`, N=256, tile **(0,135)** zone slot **2 → 0** (unzoned).
4. Verified through their loader: exactly **1 tile** differs across the whole 256×256 raster.
   File size **781807 → 781808**, i.e. **+1 byte** — the writer re-compresses QFS rather than patching in
   place, so the container length fields were recomputed. That is a stronger statement about the writer than
   the no-edit round-trip gives.
5. Placed in `Cities\` as `ZZ_T1_TEST.sc3` — a **new** filename, nothing shipped overwritten.
6. Ran `harness_run.ps1 -Scenario windowed-nointro`.

### The result, and the trap it walked into

The first run **FAILED** (`no render evidence`). A control run with the file removed **PASSED**, same switches,
same `-Kill 30`, back to back. That pairing reads as "the game rejects our written file", and it is **wrong**.

Repeating with the file present: **3/3 PASS**. The initial FAIL was a transient of the U-032/U-034 family.

`harness_run.ps1`'s own docstring says *"a single run is not evidence. Every scenario is repeated and its runs
are classified by verdict, so a transient shows up as a mixed batch instead of a false conclusion."* That rule
is what stopped a false negative from being reported here, on the first occasion it was tested by a different
session. Worth keeping.

### What this does and does not establish

**Does:** the game starts and renders normally with a `city_write.py` output present in `Cities\` (3/3), so
there is no startup-time or enumeration-time rejection of the file. And placing/removing such an artifact is
safe and fully reversible — `Cities\` verified byte-for-byte identical afterwards, `original\SC3U.exe` still
matches the anchor.

**Does not:** prove the game can LOAD it. Reaching the load dialog needs a UI click, and no harness scenario
does that — `sc3launch` has no `-city` switch and `windowed-movie` is explicitly marked INTERACTIVE for the
same reason. The 3/3 runs reached the main menu and no further, so the loader was never invoked on the file.

### What T1 actually needs

One of:

- **An interactive run.** A human launches `-nocom -windowed -origin -fix16 -fitclient -nointro`, clicks Load
  City, picks `ZZ_T1_TEST`, and reports whether it loads and whether tile (0,135) is unzoned. The file recipe
  above is deterministic, so this is a five-minute check for whoever is at the machine.
- **Or automation of the load path.** Either synthetic input to the dialog, or a trace-table entry on the
  city-load/parse functions so an unattended run can show the loader accepting or rejecting the file. The
  second is the better investment and belongs with whoever owns `re/harness/`.

Until one of those happens, T1 remains what the city-save session called it: the only claim in the project
resting on nothing.
