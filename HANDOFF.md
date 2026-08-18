# HANDOFF.md — SimCity 3000 RE (state @ 2026-08-18)

> # 🟡 T3 IS BUILT AND BLOCKED ON ONE OBSERVATION NOBODY HERE CAN MAKE (2026-08-18)
>
> **The install is CLEAN** — `Apps\Sys\SYS.PAK` is the shipped `172c02d9…`, 272,507 B, no
> `SYS.PAK.original`, 0 loose `.ini`. **Nothing is staged.** Verified at the end of the session.
>
> **T3's remaining work is not analysis. It is four archives, two protocols and two fill-in
> templates, all committed, waiting on somebody who can run the game.** The session that built
> them could not. Do not rebuild any of it; read `verify/tunable_mod_test/README.md` and run it.
>
> | ready to stage | value | length | diff vs shipped |
> |---|---|---|---|
> | `tunable_mod_test/SYS.PAK.m1_samelen` | `MaxAirPolluteForUI=00008` | 272,507 (**+0**) | **2 runs, 3 bytes** |
> | `tunable_mod_test/SYS.PAK.m2_shorter` | `=8` | 272,503 (−4) | 9,324 runs |
> | `credits_discriminator/SYS.PAK.c1_9999` | `ScrollRate…=9999` | 272,507 (**+0**) | **1 run, 4 bytes** |
> | `credits_discriminator/SYS.PAK.c2_90000` | `=90000` | 272,508 (+1) | 1,867 runs |
>
> **Why the marker changed.** The failed 2026-08-17 attempt used a tunable chosen for
> plausibility. This one is chosen for traceability: `SC3Pollution.ini MaxAirPolluteForUI` →
> `DAT_1002025c` (loader `0x100046bb:414`) → the six-way band in `0x1000c95c` → IXF group
> `0x82e0074c` instances 392-397. Six code branches, six shipped strings, in order. Setting it
> to 8 collapses the thresholds to 1/2/4/6, so a polluted tile reads **Hazardous**. The
> observable is a **word on a panel**, not a speed judged by eye.
>
> **De-risked offline so the run cannot waste itself:** `DAT_1002025c` has exactly ONE writer
> (10 occurrences in the SIMECO export, 1 write, 9 reads), so "overwritten after load" is
> impossible; `Apps\Sys\` has no loose `SC3Pollution.INI`, so editing inside the archive was the
> only thing that could work; and a **second** panel line ("Pollution Generated", `0x1000c95c:283`
> uses `air max + water max`) will also move — recorded as an AMENDMENT in the README so nobody
> reads it as a failure. The **water** line is the control. `[UNCERTAIN]` and the reason a run is
> still needed: click → broadcast is not statically provable, since `0xC2DCC228` is compared in 13
> modules and assigned nowhere.
>
> ## 🔴 THE CREDITS STORY IN THE BANNER BELOW IS WRONG — corrected here
>
> The 2026-08-17 record says "that tunable does not drive the credit scroll". **The code does not
> say that.** `0x004293fd` scrolls `ftol(elapsed × [0x4c])` px per frame with a sub-pixel carry,
> ceiled at `[0x4e]` = 4 (ctor `0x004286d7`; `MaxPixelsToScrollPerFrame` is absent from the
> shipped INI). But 4 px/frame at ~60 fps is **14,400 px/min**, so neither 1500 nor 4242 was
> clamped and 4242 should have run **~2.83x faster**. A worker analysis that claimed the clamp
> explained the null was checked and **refuted by that arithmetic** — do not re-adopt it.
>
> **H2 ("the config read fails silently") is now structurally REFUTED, without the game**
> (`U-051`): the mode field can never stay 0 (`FUN_004872e8` falls through to 1
> unconditionally), the member match `_strupr`s both sides, the section string is stored in the
> archive as **exactly 17 bytes** with no CR or padding (measured), and `FUN_00486f55` shares the
> whole mechanism and is boot-critical. So **H1 is the only surviving reading and the null was an
> observational problem** — a human judging 2.83x by eye with no reference. That is an inference,
> not a measurement; `verify/credits_discriminator/` measures it, and its observable is a
> **stopwatch duration**, not a speed.
>
> **The standing lesson, and it now has two independent confirmations:** never use a judged rate
> as a marker.
>
> ## What changed in the repo
>
> - `re/tools/syspak_mod.py` — the editing layer, promoted out of a one-off test script.
>   `--get / --set / --diff / --selftest` (17 checks). Section-aware; refuses silent no-ops;
>   `--pad` keeps an edit same-length, which is safe because `FUN_10012ad7` is a radix chooser
>   that never uses radix 8. Verified byte-identical against the script it replaced.
> - `.gitignore` now allowlists `verify/*/RESULTS.md`. Until 2026-08-18 the public repo held every
>   protocol and **not one outcome**, while `ROADMAP.md` and `HANDOFF.md` cited two RESULTS files
>   as the evidence for T1 and the SYS.PAK writer. Two of those files belong to the launch-harness
>   session — exception recorded in `SESSIONS.md` with a one-line revert.
> - `ROADMAP.md` T2: the stale "SYS.PAK still has no writer" line is corrected; it has one, it
>   round-trips 51 members byte-identically, and it is the only writer in that table validated
>   game-side.
>
> **If nobody can ever run the game here, say so and close T3 as "cannot be tested in this
> environment"** with the artifacts as the deliverable — the same call the roadmap already made
> available for T1. Leaving it open forever is the worse outcome.

## ⭐ WHERE THE PROJECT IS

**End-state: a MODDING / FORMAT TOOLKIT.** Decided 2026-08-17; the source-port option is
**closed** (`ROADMAP.md`, P1 gate).

> # ✅ THE INSTALL IS RESTORED, AND BOTH TESTS WERE RUN (2026-08-17, late)
>
> The harness session ran both staged tests and restored `Apps\Sys\SYS.PAK` to the shipped
> archive (sha `172c02d9…`, verified). **Nothing is staged in the install any more.**
>
> **T1 — the game LOADS files this project wrote.** All four rungs of
> `verify/city_load_test/` load, including T2 (our QFS compressor's output) and T3 (a one-tile
> zone edit). Full record: `verify/city_load_test/RESULTS.md`. The central toolkit claim is no
> longer structural-only.
>
> **T3 — the SYS.PAK writer is validated GAME-SIDE.** The game opens our written archive and
> boots on it (`FILETRACE` confirms `CreateFileA` + a normal menu render, and every boot
> resource comes from PAK members). Record: `verify/loose_file_test/ARM3_RESULTS.md`.
>
> **My pre-registered prediction was WRONG and was falsified properly.** I predicted the credits
> would scroll ~3x from `ScrollRateInPixelsPerMinute=4242`; they scrolled normally. That would
> have implicated the writer, except a full byte diff shows our archive differs from shipped by
> **exactly 4 contiguous bytes** — the `1500`→`4242` digits — so the game read it exactly as it
> would a hex-edited shipped archive. The premise was wrong, not the writer: that tunable does
> not drive the credit scroll. **This is the model outcome — a falsified prediction settled by
> measurement rather than argued away.**
>
> Still open from those runs, all small and all recorded in the two RESULTS files: T3's tile
> (28,0) was never visually confirmed as Landfill; that run hard-crashed ~35 s after load during
> the probe's own framebuffer sampling (best reading: instrumentation, NOT proven); and a
> name-collision crash was found — **do not place a written city beside another with the same
> internal name** (actionable for toolkit users).

> # 🔴 SUPERSEDED — the install WAS modified while the tests were staged
>
> `Apps\Sys\SYS.PAK` is **not the shipped archive**. It is one this project's writer produced,
> staged as a live test (roadmap gate T3, "arm 3"):
>
> ```
> Apps\Sys\SYS.PAK           ours      sha256 c224e8bf…   272,507 bytes
> Apps\Sys\SYS.PAK.original  shipped   sha256 172c02d9…   272,507 bytes
> ```
>
> Same length; the only difference is one value inside `SC3Tune.ini`
> (`ScrollRateInPixelsPerMinute` 1500 → 4242), verified by re-parsing both. **RESTORE WITH:**
>
> ```
> del  "Apps\Sys\SYS.PAK"
> move "Apps\Sys\SYS.PAK.original" "Apps\Sys\SYS.PAK"
> ```
>
> `verify/city_load_test/` also holds four `.sc3` files staged for gate T1, but those are **not**
> in the game folder and affect nothing. Manifests, predictions and undo steps for every staged
> test live in `verify/*/README.md` and the `*_MANIFEST.txt` beside them.
>
> **Nothing was overwritten and nothing is lost**: the shipped archive is byte-unchanged next to
> the modified one, and every extracted file is recoverable from it.

> ## ⚠️ THREE SESSIONS SHARE THIS WORKING COPY — read `SESSIONS.md` before writing a tracker
>
> It records who owns which files and seven agreed rules. The two that cost real time today:
> **commit by path, never `git add -A`** (three of another session's commits swept up this
> session's in-flight files), and **any count over the exports must state its filter and be
> cross-checked** (three loose-filter errors in one day, each plausible and each caught only by a
> disagreement between two methods).

## ⭐⭐ P1 IS EXITED. THE ROADMAP IS NOW T1 → T2 → T3 (adopted 2026-08-17)

All five P1 criteria hold, each re-measured on the day: 0 unenumerated `FUN_` bodies across 30
binaries, **562/562 = 100%** of the toolkit-necessary set at ≥ C2, UI/framework
enumerated-unclassified by design, subsystem map committed, end-state decided. The old
annotate-first phases **P2 – P5 are superseded**. Analysis: `re/analysis/POST_P1.md`.

### ⭐ THE ONE SENTENCE THAT MATTERS

**Every shipped format now has a byte-identical writer, every one is verified against itself, and
NOT ONE has ever been verified against the game.** The format work is done and internally
rigorous; the entire external-validation surface is two runs nobody has performed.

| format | writer selftest | command |
|---|---|---|
| `.IXF` container | **657/657** containers, whole install, 8 extensions | `ixf_parse.py . --selftest` |
| city save family | **59/59** no-edit identity, 5 layers | `city_write.py Cities --selftest` |
| QFS / RefPack | **60/60** city + **63,931/63,931** sprite streams | `qfs_encode.py . --selftest` |
| sprite blocks | **62,552/62,552** | `sprite_encode.py Apps/Res --selftest` |
| `SYS.PAK` | **byte-identical, 51 members** | `syspak_parse.py <pak> --selftest` |

**T1 — PROVE THE WRITE PATH. ◀ ACTIVE and blocked on a human, not on analysis.**
Exit: *the game loads a file this project wrote, and shows the edit.* Built and waiting:
`verify/city_load_test/`, four `.sc3` files (untouched copy → byte-identical rewrite →
same-content-different-bytes → one tile changed), each isolating one variable, with every
outcome's meaning committed to in the README **before** the run. The harness session has been
asked three times and has not answered. **If nobody will run the game, say so and close T1 as
"cannot be tested here" rather than leaving it open forever.**

**T2 — EXPOSE THE FORMATS AS A LIBRARY. ✅ MET 2026-08-17.** See the table above. The stated debt
is paid: the `.IXF` writer moved out of `city_roundtrip.py` into `ixf_parse.py`, and the harness
now delegates to it. Promoting it paid for itself immediately — the harness copy carried a
`size + 4` rule generalised from 13 city files that failed **472 of 478** localized-text
containers.

**T3 — DEMONSTRATE A MOD END TO END. Scoping ANSWERED, both routes BUILT, one observation left.**
`[CONFIRMED @0x004872e8]` **the archive WINS over loose files**: the resolver checks `SYS.PAK`
exists, opens it **read-only** (verified by a live vtable dump: `PTR_FUN_004d87ec` slot 3 =
`FUN_0047b437`, and the call passes `GENERIC_READ / OPEN_EXISTING / FILE_SHARE_READ`), scans its
directory for the member, and only falls back to a loose file when the archive is missing or
lacks that entry.

- **Route A — rewrite the archive.** ✅ Built: `syspak_parse.py` `build()` / `replace_member()`.
  Staged live in the install right now (see the banner above).
- **Route B — use the loader's own fallback.** Extract all 51 members to `Apps\Sys\` and move the
  archive aside. No new format work; it is the shipped code path.

What remains is **not a format problem**: one change, made with these tools, observed running.

> **`functions.csv` is 78% C0 and that is the DESIGN, not debt.** Criterion 3 keeps whole module
> families unclassified deliberately, and criterion 2 replaced "read everything" with "read what
> touches a shipped byte" — 562 functions did that. Do not re-derive the 78% as a backlog against
> a gate that was retired for good reasons (`GATE_RESCOPE.md`).

**⭐⭐ P1 CRITERION 2 IS MET (2026-08-17): 562 / 562 = 100% of the toolkit-necessary set at
≥ C2.** Re-scoped on the owner's call that morning (from ≥C1 across all core-sim functions), closed
at 530/530, RE-OPENED at 530/562 when a concurrent session's vtable carve grew the set, and closed
again. 333 functions read in 22 delegated clusters plus 4 read by hand, every batch verified
against the binary before merging.

The set is derived from the binary, not chosen: pinned GZCOM stream-slot users, section-TYPE
literal writers, functions naming a class id that occurs as a section `group`, and `.INI`
loaders. 562 of 14,671 core-sim functions = 3.8%, **recall 50/50 = 100%** against the unrelated
`find_section_producers.py`, and threshold-insensitive across a 6x range of its one threshold.
Re-measure, never quote: `py -3.12 re/scripts/scope_toolkit.py [--validate|--todo <MODULE>]`.
Analysis and the four options considered: `re/analysis/GATE_RESCOPE.md`.

**Criterion 1 is MET again too (38,092 rows), so the whole P1 gate now holds.** It went stale
mid-session when the exports were regenerated; `enumerate_functions.py` added the **129** missing
`FUN_` rows (SIMRCI 90, SIMMISC 39) and a direct check finds **0 unenumerated `FUN_` bodies across
all 30 binaries**. Criterion 2 was unaffected — none of the 129 is a toolkit-set member.

> ⚠️ **I first reported that gap as 271 and it was wrong.** My check matched `'_FUN_' in
> filename`, which also matches `thunk_FUN_*`; 142 were thunks, which the criterion excludes.
> `enumerate_functions.py --dry-run` said 129, my grep said 271, and **the loose instrument was
> mine.** The earlier commit message carries the 271 figure uncorrected — this is the correction.

⚠️ **"Met" means met AT THAT MEASUREMENT, and it has already been proved twice today.** The set is
derived from the export and moved **513 → 530 → 562** in one day as exports were regenerated and a
vtable carve landed. Criterion 2 was closed at 530/530, re-opened at 530/562, and closed again. A
re-export can add members, so **re-run `scope_toolkit.py` rather than quoting 562**.
Why C2 rather than C1: 1,473 of the old count were
`classify_families.py` regex labels with nothing read, and only **839** core-sim functions had
ever actually been read. The set shrank 19x and the bar went up a notch.

The work list feeds the existing delegation path directly:
```
py -3.12 re\scripts\scope_toolkit.py --todo SIMRCI > slice.txt
pwsh -NoProfile -File re\scripts\delegate_cluster.ps1 -Module SIMRCI -RvaFile slice.txt
```
`-RvaFile` is new; the size heuristic is no longer the only selector, and the gate no longer asks
for the sub-100-byte tail that heuristic was down to.

**The loop that closed the gate, and the one to reuse:** `scope_toolkit.py --todo <M>` →
`delegate_cluster.ps1 -RvaFile` → `verify_worker_rows.py` → merge **only at zero flags** →
hand-read every flag. 22 clusters, 333 functions. Three batches were held back on flags and
re-read or hand-checked rather than merged, and that is the part that matters: one batch had
placeholder names (`sc3_dstr_classA_shutdown`) and came back correct on the re-read.

**`verify_worker_rows.py` is new and it is not optional.** `merge_worker_module.py` scrubs leaks
and caps C3+, but checks no claim. The verifier resolves every cited constant against the body
(as integer values, across hex / decimal / `FUN_` symbols / **C character escapes**), requires a
serialisation name to be backed by a stream slot or an INI string, and rejects hedging words.
Calibrate before trusting it: on the already-merged `SIMRCI_CLUSTER3.md` it flags 4 of 25.

> ⚠️ **THREE SESSIONS SHARE THIS WORKING COPY. Read `SESSIONS.md` before writing a tracker.**
> It records who owns what and seven rules agreed between them. The C3 rows the gzcom session
> wrote were **audited and are sound** — two `VtableDump` runs confirmed the slot mappings
> exactly, so no downgrade. `functions.csv` grew 36,790 → 50,621 rows during the day from that
> session's carve and enumeration, with 0 rows lost and 0 downgraded (checked at every merge).

**⭐ DONE 2026-08-17 — the city-save WRITER round-trips shipped `.sc3` files BYTE-IDENTICALLY,
59/59 at every layer.** The toolkit branch's first deliverable, and it passed the sprite bar.

```
py -3.12 re/tools/city_roundtrip.py "Cities"
L0 container 59/59 · L1 record 59/59 · L2 archive 59/59 · L3 QFS 59/59 · L4 whole file 59/59
```

Every layer is re-emitted **from parsed structure**, nothing copied through, and L4 recomputes
both length fields from the bytes it emitted. Full write-up: `formats/CITY_SAVE.md` ("THE WRITER")
and `formats/QFS.md`.

**The expected blocker was not one. The QFS COMPRESSOR is in the game** — GZResourceD
`FUN_1001694d` via `FUN_100168cb` `[CONFIRMED]`, transcribed in `re/tools/qfs_encode.py`, and it
reproduces all 59 shipped streams exactly. It selects matches by **net gain**
(`matchLen - tokenCost`), not by length, and the shipped files used its `quick = 1` mode
(`quick = 0` compresses 4.7% better and is therefore provably not what shipped).

> **The method lesson is the transferable part.** A probe of the shipped streams measured the
> encoder taking the longest available match only 82.0% of the time and the nearest such offset
> 67.8% — which looks precisely like an unreproducible heuristic, and "byte-identical QFS is
> unattainable, here is the weaker bar" was one step from being written down. It was wrong: the
> probe had no cost model. What broke it was a question rather than a measurement — *the game
> writes `.sc3` files, so where is its compressor?* **Before concluding a behaviour cannot be
> reproduced, check whether the code that produces it shipped.**

**Scope limit, stated plainly:** section payload bytes are re-emitted verbatim, so this is an
**edit-and-rewrite** pipeline (parse, change bytes at a decoded offset, emit a valid file), not
authoring a city from scratch — that would mean reimplementing the layer savers.

**The city save is READ-solved.** Container, 24-byte header, QFS, section archive, per-section
frame, **all 44 section groups traced to their serialisers**, map dimension `N` readable, zone
layer decoded to per-tile developer slots with R/C/I/Landfill named. Tools: `re/tools/city_parse.py`,
`re/tools/city_sections.py`, `re/scripts/find_section_producers.py`.

### Method lessons from 2026-08-16/17 — these cost real time, read them

1. **Silent tool failures were the dominant time sink — four in one session.** Every one
   produced plausible output with no error: a regex needing 8 hex digits when Ghidra strips
   leading zeros; an assumed store order; a call-listing regex that skipped slot-0 calls
   entirely; a classifier counting a function's own name as a call. **Every one was caught by a
   disagreement between two methods, never by re-reading the code.** Cross-check tools against
   readers, and hand-sample output.
2. **Don't reason backwards from a discrepancy to a cause.** Four inferences about one ~138-byte
   gap were all wrong (`vt+0x98` non-scalar; blocks as 4-byte elements; saver/loader asymmetry;
   the alignment contradiction). Each made the arithmetic close and each was falsified by
   reading. Measure the cause.
3. **Re-read the function, not the summary of it.** `CITY_SAVE.md`'s grammar was derived from
   the saver twice and the loader once and was still missing two writes.
4. **A validation harness can go circular.** After the classifier's first merge it began scoring
   its own rows and "improved" from 12/13 to 626/627. Ground truth must exclude your own output.
5. **A coverage number that only ever rises is not measuring anything.** The classifier reverted
   85 of its own rows on re-run; core-sim went 24.9% → 24.0% and that was correct.
6. **2026-08-17 added FOUR more silent zero-match regexes, plus more since, so treat this as the
   default failure mode rather than an anomaly.** (a) `\.ini` matched nothing because Ghidra renames dots to underscores
   (`s_Sys_SC3ComLayer_ini_...`) — reported 0 INI loaders across 11 modules; (b) a gate-cost line
   compared two different denominators and printed 9,388 where an independent count said 7,263;
   (c) writing a regex through a bash heredoc turned `\b` into literal BACKSPACE bytes, and
   `print(pattern)` rendered them invisibly, so the pattern LOOKED right while matching nothing;
   (d) the row verifier had no case for **C character escapes**, so a correct claim citing `0x16`
   — present in the body as `'\x16'` — was reported as a fabricated constant. **(d) is the one to
   remember: when a checker accuses a claim, check the checker first.** Edit regex code with a
   real editor, and give every checker a `--selftest` against strings whose answers you know.
7. **A rule confirmed on one family is not a rule about the format.** The `.IXF` string-payload
   extent was generalised from 110 records across 13 city `.SNR` files and round-tripped **59/59**
   of them — then failed **472 of 478** localized-text containers, every one off by exactly four
   bytes. 59/59 was a real number that licensed a wrong generalisation. Widen the corpus before
   believing a rule, and select it by MAGIC rather than by extension: the same container ships as
   `.IXF`, `.DAT`, `.SC3`, `.SCT`, `.SNR`, `.ST3`, `.BLD` and `.CFG`.
8. **Stop writing code through shell heredocs.** Five separate escaping failures this session,
   including one that put literal `0x08` and `0x16` BYTES into `HANDOFF.md` — in the sentence
   documenting that exact bug — and one that produced a regex requiring invisible control
   characters, which `print()` rendered as if it were correct. Use a real editor for code.
9. **When two methods disagree, one of them is yours.** Every count dispute today resolved
   against the looser instrument, and about half the time that was mine: `'_FUN_' in filename`
   also matches `thunk_FUN_*` (271 vs 129), `'&' + var` matched `&local_84` as a substring
   (6 hits vs 0), and a checker with no two's-complement path called a correct GZCOM IID
   citation fabricated.

## 🔴 What landed 2026-08-16 (still current unless corrected above)

1. **The city-save section offset base is `0`, not `+0x0C`.** The `[CONFIRMED, 59/59]` claim for
   `+0x0C` was circular and is **FALSIFIED**. The body header is **8 bytes**; what was read as
   header fields at `+0x08`/`+0x0c`/`+0x10` is the first section's own content. Proof: the
   SIMCITY object frame `{u16 version, u8 flags, u8 extra, u32 0xDEADBEEF}` lands exactly on a
   section start for **2,330 of 3,451 sections at base 0** — and 2,330 is the **total** number of
   `0xDEADBEEF` occurrences in all 59 bodies. At base 12 only 319 line up.
   **Every byte-level observation previously recorded at base 12 is off by 12** and the ones in
   `CITY_SAVE.md` have been re-measured. `re/tools/city_parse.py` is fixed; 59/59 still parse.
2. **The archive DOES frame sections** — frame class `SIMCITY.DLL` `0x10010315` (read) /
   `0x10010531` (write) / `0x1001066c` (dtor) / `0x100106ab` (accessor), vtable
   `PTR_FUN_10013fc0`. It is **opt-in per class**; `SC3ZoneLayer` does not use it.
   Also found: `SIMCITY.DLL FUN_1000351e` is the **city load driver** — layer array at
   `citySim+0x94..+0x98`, each layer's load is **vtable slot `+0x1c`**, called `(citySim, archive)`.
3. ~~**Zone grammar: attempt 7 failed. Do not attempt an eighth.**~~ **SUPERSEDED 2026-08-17 —
   the zone section is now decoded.** The grammar starts at `N*N` and parses in 59/59; all eight
   earlier sweeps failed for one reason, they required it to consume to the section end and it
   never does. The `3·N²` reading was also wrong: only the first `N*N` is a raster, the rest is
   a `u16`-per-tile permutation written by a sub-object at `this+0x268` (slot 1 writes, slot 0
   reads), and the loader's second arm is a **failure fallback** that recomputes a histogram,
   not a format variant. `N` is readable from the SIMGEOM tile-grid section. See `CITY_SAVE.md`
   and `U-029`; open items there are semantic (the permutation's purpose, the `3000/5000/8000`
   keys, a `this+0x3c` 23-vs-92-byte mismatch).
4. **Group `0x21737de5` is named**: the SIMDIRT terrain layer, saver `0x10004d90`, loader
   `0x10004a00`, payload delimited by literal `DirtBag_Start` / `DirtBag_End`. It is the **first
   section of every city file**. Its grammar is chunk-keyed, not the `vt+0x38`/`vt+0x88` mirror
   pair — so the mirror-pair test does **not** find every serialiser.
5. **C0 clusters merged** for the five modules that had never had one: SIMSPR, GZWinD, GZWWWD,
   SIMDIRT, AUDIO (`re/analysis/<M>_CLUSTER1.md`, 124 rows). (tracker figures superseded — see the gate table below).
6. **⭐ THE P1 GATE IS RE-SCOPED** (owner call, 2026-08-16). *"100% of `FUN_*` at ≥ C1"* is
   **retired** — do not measure against it. The gate is now: everything **enumerated** (met,
   31,991 rows) + **≥ C1 across the eleven core-sim modules** + subsystem map (met) + the
   end-state decision (**still open**). UI / audio / tooling / framework modules stay
   "enumerated, unclassified" **by design**.

   **The core-sim set (11 modules), and the only progress number that counts:**

   | module | backlog | ≥C1 | % |
   |---|---|---|---|
   | SIMDSTR | 1,191 | 221 | 18.6% |
   | SIMRCI | 1,536 | 315 | 20.5% |
   | SIMUTIL | 763 | 177 | 23.2% |
   | SIMSERV | 713 | 168 | 23.6% |
   | SIMVARIABLES | 350 | 83 | 23.7% |
   | SIMCITY | 587 | 140 | 23.9% |
   | SIMECO | 659 | 167 | 25.3% |
   | SimTransit | 619 | 164 | 26.5% |
   | SIMGEOM | 1,148 | 310 | 27.0% |
   | SIMNTWRK | 809 | 222 | 27.4% |
   | SIMMISC | 1,200 | 332 | 27.7% |
   | **TOTAL** | **9,575** | **2,299** | **24.0%** |

   The set is **levelled** (18.6%–27.7%), so "attack the worst" is not a useful selector. Pick by
   value, not by percentage.

   **7,276 to go.** Stop quoting the all-binaries 17.0%; it is dominated by 20,670 functions the
   gate does not ask for. SIMCITY / SIMNTWRK / SIMVARIABLES were added to the set on the owner's
   call 2026-08-16 — the original eight were listed before SIMCITY was identified as the tick
   driver.

   > **8.6% → 24.0% of that came from `re/scripts/classify_families.py`, not from reading.**
   > 4,009 rows merged at **C1 only** — a regex did not read anything, and C2 in this project
   > means the decompilation was read. Do not raise those rows to C2 without reading them.
   > Every merged row carries a `[classify_families]` prefix in `notes`, so they are trivially
   > separable from human/worker work.

   > ### The tail now has a tool: `re/scripts/classify_families.py`
   >
   > Bulk-classifies small functions by structural family. **`--validate` first, always** — it
   > scores the classifier against functions humans and workers already labelled, per family,
   > and that number is the only reason to trust the rest of the output. Measured precision:
   > `vtable_install` 100% (8/8), `lazy_singleton` 100% (4/4), `ctor_or_dtor` 92% (12/13, and
   > the single miss was hand-checked — `sc3_cal_today` really is a constructor, the harness
   > just does not recognise a domain name).
   >
   > **Run across all 31 binaries with `--all-modules`** (2026-08-16): 4,009 rows at C1,
   > all-binaries coverage 9.3% → **17.0%**. The gate is still measured over the core-sim set
   > only, so those extra rows do not inflate it — they are free coverage for whoever opens a
   > UI or framework module later.
   >
   > ⚠️ **The core-sim number went DOWN in that run, 24.9% → 24.0%, and that is correct.**
   > Widening the validation set exposed two more pattern bugs, and re-running **reverted 85
   > rows it had previously written**. The tool now re-examines its own output on every run and
   > actively resets verdicts that no longer hold, rather than freezing a bad label in place.
   > A coverage number that only ever rises is not measuring anything.
   >
   > **The biggest single family is `deleting_dtor` — 475 functions.** It is the MSVC scalar
   > deleting destructor, `dtor(this); if ((flags & 1) != 0) operator_delete(this);`, and the
   > `& 1` guard is the compiler's own signature, so this is an identification rather than a
   > heuristic. It came with a free result: in **all 11 modules the guarded call resolves to
   > exactly ONE target, 100% share** — that target is the module's `operator delete`, an
   > 11-byte `free(param_1)`. All 11 are now named at **C2** (`sc3_<module>_operator_delete`).
   > The 1-target/100% convergence is also the strongest available check on the family: a
   > sloppy pattern would have produced scattered targets.
   >
   > **`forwarder` (35%) and `vcall_wrapper` (0%) are deliberately NOT merged.** They are
   > structurally true and semantically empty: `sc3_powerplant_tick` genuinely is a forwarder,
   > and calling it one tells a reader nothing. Those 990 functions stay C0 so somebody picks
   > them up properly later. Merging them would have bought ~10 more points of "coverage" and
   > destroyed the signal about what still needs reading.
   >
   > **Three bugs in this tool were caught by sampling its output, not by reading the code**, and
   > all three produced plausible-looking numbers while being wrong:
   > 1. the function's own name in the signature line counted as a call, so the zero-call branch
   >    never ran and getters/setters/stubs scored a flat zero;
   > 2. `puStack_c = &LAB_...` (the SEH handler, present in every EH function) was read as a
   >    vtable install;
   > 3. `stub` was tested before the vtable check, so 45 vtable installers were filed as empty.
   >
   > If you extend it: run `--validate`, then hand-read ten random hits per new family.
   >
   > ⚠️ **The size heuristic behind `delegate_cluster.ps1` is nearly exhausted in these two
   > modules, and the "~360 runs" estimate is misleading.** Measured after cluster 3:
   >
   > | | SIMRCI (1,429 C0 left) | SIMMISC (1,102 C0 left) |
   > |---|---|---|
   > | ≥ 500 bytes | ~46 | ~25 |
   > | ≥ 200 bytes | ~212 | ~120 |
   > | **under 100 bytes** | **~70%** | **~74%** |
   >
   > Cluster 1 read 1447-814 byte functions, cluster 2 ~800-700, cluster 3 ~700-500. By cluster
   > 5 a run is deep-reading 300-byte helpers, and the last ~70% are sub-100-byte accessors and
   > forwarding stubs. **Grinding those 25-at-a-time is the wrong tool.** What they need is a
   > bulk classifier that groups by vtable slot / single-caller / size signature and labels whole
   > families at once. Design that before spending another 300 cluster runs.

7. **⭐ END-STATE DECIDED (owner call, 2026-08-17): a MODDING / FORMAT TOOLKIT.** The
   source-port option is **closed**, not deferred — 31,991 functions across 31 interdependent
   binaries with the sim spread over eleven of them. `ROADMAP.md` carries the full rationale.
   **P1 gate criterion 5 is now MET.**

   Consequence for RE work: annotate-first still holds, but the *purpose* narrows to **what a
   toolkit needs**. Deprioritise anything that only matters to a reimplementation (per-tick sim
   math, render internals, UI behaviour) unless it blocks a format. The core-sim ≥C1 target
   (24.0%) should be re-scoped against this — a toolkit likely does not need all 9,575.

   **First deliverable, and it is falsifiable: a city-save WRITER that round-trips a shipped
   `.sc3` byte-identically.** Reading 59/59 is not the same as writing one the game accepts.
   The bar to match is the sprite work: 62,552/62,552 byte-identical re-encode.
---

> ⚠️ **EVERYTHING BELOW THIS LINE IS THE 2026-08-15 SNAPSHOT AND IS PARTLY SUPERSEDED.**
> Kept for the parts that are still the best record (module recipe, pinned classes, sim models,
> cross-RE rule, tooling). Do **not** trust these specifically:
> * the **`3.2% classified`** figure and any per-module percentage — see the gate table above;
> * **"C1 tier is EMPTY"** — it is now the largest tier (4,015 rows, mostly `classify_families`);
> * anything about the **city save** — the container section base was `+0x0C` and is **0**, and
>   the zone section is decoded; `CITY_SAVE.md` is the only current source;
> * **"the grammar is confirmed from BOTH the saver and the loader"** — true only up to block C;
> * the **next-moves list** at the foot — superseded by the toolkit decision in `ROADMAP.md`.
# HANDOFF.md — SimCity 3000 RE (state @ 2026-08-15)

Snapshot for a fresh orchestrator session. Everything below is on disk; boot from the docs,
not from any prior transcript.

## Where we are
- **Phase:** P0 DONE. **P1 (surface map) ACTIVE.** End-goal: understand + annotate first
  (source-port-vs-toolkit decision deferred to the P1 exit gate). See `ROADMAP.md`.
- **🔴 THE STRUCTURAL FACT:** the simulation is **not** in `SC3U.exe`. That binary is the GZCOM
  shell. The game is **29 GZCOM director DLLs** in `Apps\` (6.2 MB). All are imported and
  exported. See `re/analysis/MODULE_MAP.md` + `MODULE_INVENTORY.md`.
- **Tracker `functions.csv`** now has a **`module` column** (first field).
  ⚠️ **THE DENOMINATOR WAS WRONG UNTIL 2026-08-16.** The tracker enumerated only `SC3U.exe`, so
  every percentage measured ~18% of the binaries. `re/scripts/enumerate_functions.py` fixed it.
  **Real backlog: 31,991 `FUN_*` across all 31 binaries. Classified: 1,034 = 3.2%.**
  (C1 tier is EMPTY — everything anyone has read is ≥ C2.)
  Note the raw export count of 56,754 is **misleading**: 22,495 of those files are `Unwind_*`
  exception fragments, plus 1,118 `Catch_*`, 516 thunks, 662 library-named. Do not quote it.
  Per-module coverage: SIMCITY 10.2% · SIMDSTR 5.7% · SIMGEOM 5.1% · SIMUI 4.3% · SIMMISC 3.8% ·
  SIMRCI 3.1% · SIMBABLD 1.9%. See the P1 exit-gate assessment in `ROADMAP.md`.

## The GZCOM module recipe (holds for every module)
```
GZDllGetGZCOMDirector  (PE export)
  → guarded static director ctor
  → N × register_class(director, GZCLSID, factory, 0)     # inserts into a map at director+0x14
  → factory: operator_new(size) + ctor                    # may return object+N (sub-interface)
```
Registration counts: SIMUI 40 · SIMSPR 40 · SIMRCI 37 · SIMMISC 36 · SIMUTIL 15 · SIMGEOM 14 ·
SimTransit 5 · SIMBABLD 2.

> **GZResourceD's DB was also mutated 2026-08-16**: 3 stream-primitive functions carved (`0x1000c157/69/ad`); export 1,458 -> 1,461, +3 / 0 removed / 1,461 ok / 0 fail.
>
> ⭐ **THE GZCOM STREAM WRITE PRIMITIVES ARE PINNED** (`re/analysis/formats/CITY_SAVE.md`) and they apply to EVERY serialiser in the project, not just the city save: stream `vt+0x64` and `vt+0x84` = `Write(ptr,len)` raw block, `vt+0x68` = write u8, `vt+0x88` = write u32, all forwarding to `vt+0xac`. The stream is IID `0x199627`, QI'd in 18 of the 31 modules; its QueryInterface is GZResourceD `0x1000b88a` and returns `this` at offset 0.
>
> **SIMRCI's Ghidra DB was MUTATED 2026-08-16** and re-exported. `MakeFunctions.java` force-created
> 4 functions Ghidra's auto-analysis had left uncarved: `0x1000e837`, `0x1001599d`, `0x1002115d`
> (8-byte `CALL <ini loader>; RET 4` stubs) and `0x10030369` (the SC3ZoneLayer base-class write
> thunk, slot 10 of `PTR_FUN_1004d274`). **`re/ghidra_export_simrci/` is now 3,267 files (was
> 3,263)**, verified as +4 added / 0 removed / 3,267 ok / 0 fail.
> Lesson: after any `MakeFunctions` run, **re-export that module** — workers grep the text export,
> and a stale export makes a newly-carved function look absent, which reads as "this vtable slot
> leads nowhere" rather than "the export is out of date".

**Trap:** factory stubs are reached only via the registration table (a DATA ref), so Ghidra often
leaves them as bare `LAB_*` with **no exported body**. Recovered 12 in SIMUI + **51 across 17
modules** with `re/scripts/MakeFunctions.java`. Detect with `re/scripts/find_stub_gaps.py`, but
**only trust the registration-signature filter** — a blanket `LAB_*` sweep matches basic-block
labels inside functions and will corrupt the databases.

## Classes pinned (real GZCLSIDs — NOT the `0x41F836xx` ids in CitySim.ini)
`SC3PowerLayer` `0x20afdf44` · `SC3WaterLayer` `0x82bf0042` · `SC3ValveLayer` `0x60a42f32` ·
`SC3ZoneLayer` `0x409ff3ba` · `TrafficLayer` `0x029ca806` · `SC3BuildingLayer` `0xe150e7bb` ·
`SC3BudgetLayer` `0xc11bcc75` · `SC3WorldLayer` `0xe11bddf6` · sprite manager `0xa411112f` ·
**9 power plants** (`0x?14a10??` cluster, Coal `0x814a0fbd` … WasteToEnergy `0x2302193a`).

## Sim models reversed
- **Power** (`POWER_GRID.md`): masked **bitmap dilation flood-fill**, 32 tiles/dword, **cap 600**
  (`0x258` @`0x10004ee2`), over a conductive mask raster + a byte-per-tile demand raster.
  Plant output = `cap − (age − declineAge)·cap/(maxLife − declineAge)`, 0 past maxLife.
- **RCI/zoning** (`SIMRCI.md`): valve effect tables are module-global; 23-slot zone-developer table.
- **Traffic** (`SIMUTIL_SIMTRANSIT.md`): trip/cell-cost commute model, 4 per-zone destination tables.
- **Budget/ordinances/aura/neighbor deals** (`SIMMISC.md`): bonds, the tax "transmogrifier"
  coefficients, the 40-byte ordinance record with prerequisite links.
- **Buildings** (`SIMGEOM.md`): occupant property schema, ids `0x65`–`0x7c`.

## Data formats cracked (all with parsers or full specs)
| format | where | tool |
|---|---|---|
| `SYS.PAK` | 51 ini files | `re/tools/syspak_parse.py` |
| **`.IXF` GZ segment** | localized text, building exports, **all 40 sprite archives** | `re/tools/ixf_parse.py` |
| **QFS / RefPack** | sprite pixel data | `re/tools/qfs.py` — **C4, 63,691/63,691 streams round-trip** |
| **plain-bitmap sprite** | 1,139 effect/UI records | `re/tools/sprite_render.py` — **C4**, 8bpp 5-bit coverage mask |
| **span sprite** | 62,552 records = the main art | `sprite_render.py` + `sprite_encode.py` — **C4, 62,552/62,552 re-encode BYTE-IDENTICAL** |
| **sprite anchor** (type-1) | 62,387 records | `sprite_render.parse_anchor` — **C4**, 4×i16 `{spanL,spanT,spanR,spanB}`, witnessed by `.SII` |
| ⭐ **city save family** | `.sc3`/`.sct`/`.snr`/`.st3` — **59/59 files** | `re/tools/city_parse.py` — IXF container + 24-byte header + **QFS payload**, 59/59 decode, 21.9 MB -> 92.7 MB. See `formats/CITY_SAVE.md` |
| FEZC / GVF | iOS assets | `fez_extract.py`, `gvf_dump.py` |

The sprite block's producer is **`GZGraphicD.dll`'s image class** (GZCLSID `0xa487535d`,
IID `0x0487534f`), not SIMSPR: encoder `0x100017de`, consumer `0x10001700`. See `formats/QFS.md`
and `formats/SPRITE_SII.md`.

`.IXF`: magic `0x80C381D7`, 20-byte index `{group, instance, type, offset, size}`, end = key
triple zero, tombstone = `offset`/`size` == `-1`. Reader (GZResourceD `0x1000ca78`) **and** two
writers (SIMBABLD `0x1204f2e7`, SIMSPR `0x100583cf`) all agree.
Extraction: **537 files, 71,924 text records** → `re/data/ixf_text.csv`; sprites: **40 archives,
127,971 records** (63,691 type-0 + 62,387 type-1) → `re/data/sprite_records.csv`.
⚠️ A previous figure of "72 archives / 253,838 records" was **double-counted** (exactly 2x over the
36 `.DAT` files, missing the 4 `.IXF`); corrected 2026-08-15 by the full `qfs.py` sweep.

## Public repo

Tools + notes are published to **https://github.com/nanofives/sc3kre** (public, MIT for our code).
The repo is a **subset** of this working tree, not a mirror: `re/tools/*.py`,
`re/scripts/*.{py,ps1,java}`, `re/analysis/**/*.md`, the root trackers and `functions.csv` — 61
files, ~1.4 MB. **No game binaries, no `re/ghidra_export*`, no `re/data/`, no extracted assets.**
`.gitignore` is deny-by-default (`/*` then an explicit allowlist), with a per-directory deny for
each `re/analysis` subdirectory so a NEW subdir fails safe.

> ⚠️ Do NOT "fix" that `.gitignore` into the tidier `!/re/analysis/**/*.md` form. It was tried and
> it **leaks**: git's `**/` directory re-include exposes the subdirectory's non-md contents, which
> let `re/analysis/formats/gvf_keys.csv` (961 KB of extracted iOS game data) become tracked.
> Verify any change with `git check-ignore -v` and `git ls-files`, never by eye.

> ⚠️ `re/scripts/delegate_module.ps1` no longer hardcodes the worker path (it was scrubbed for
> publication). It **throws unless `$env:REPO_FLEET_DELEGATE` is set** — point it at your
> read-only delegation helper, i.e. the workspace's
> `.claude\skills\repo-fleet\scripts\delegate.ps1` (path is machine-local; see the workspace
> `CLAUDE.md`, which is deliberately not in this repo).

**Not backed up anywhere:** `re/data/` (63,691 rendered sprites), `re/ghidra_export*/` (31 dirs)
and the Ghidra projects are local-only and unversioned.

## Tooling added this session
```
re\scripts\ghidra_headless.ps1 -Module <NAME.DLL> -Import|-Export   # per-module projects
re\scripts\delegate_module.ps1           # fan one module analysis at a read-only worker
re\scripts\merge_worker_module.py        # land a worker's markdown + merge its rows
re\scripts\DumpDisasm.java               # raw instruction listing (when decomp fails)
re\tools\qfs.py                          # QFS/RefPack decompressor
re\tools\sprite_render.py                # sprite -> PNG (both pixel classes + anchors)
re\scripts\import_all_modules.ps1        # bulk import, resumable
re\scripts\recover_all_stubs.ps1         # + find_stub_gaps.py + MakeFunctions.java
re\scripts\VtableProbe.java              # method -> vtable slot -> installing ctor
re\scripts\VtableDump.java               # dump a vtable's slots  (vtables are DATA, ungreppable)
re\tools\ixf_parse.py                    # .IXF/.DAT index + text extraction
re\tools\pe_read.py                      # read .rdata constants straight out of a PE, no Ghidra
```

## The cross-RE rule (hard-won, two results)
**iOS algorithms and magic constants transfer; iOS struct layouts do NOT.**
Confirmed: the `Bit1_SelectionGrow` cap of 600 is literally in SIMUTIL. Refuted: **0 of 5**
`goPowerPlant` field offsets match the PC build. Use iOS to predict *what code does and which
constants to look for* — never *where fields sit*. See `SIM_LAYERS_XREF.md`.

## Uncertainties
Resolved this session: **U-005** (modules), **U-007** (GZCOM resource key), **U-008** (`.IXF` text,
C4 round-trip), **U-009** (power vs water), **U-010** (ValveLayer id), **U-011** (plant field map),
**U-012** (power flood-fill). **Falsified: U-006** — no `0x41F836xx` GZCLSID exists in *any*
shipped binary; building types are pure data. Do not re-attempt.
Open: **U-001** (HTML consumer; lead `0x004a3f0c`), **U-002** (FEZC field0), plus the per-module
open lists at the foot of each analysis doc.

## Next moves (ranked)

> **DONE 2026-08-15:** the whole sprite pipeline. `re/tools/qfs.py` (QFS, 63,691/63,691 streams)
> and `re/tools/sprite_render.py` (both pixel classes) turn all 63,691 records into PNGs.
> Building property ids `0x65`–`0x7c` are in `re/analysis/SIMGEOM_PROPERTIES.md`.

> **ALSO DONE 2026-08-15:** all 7 previously unanalysed sim modules now have a first-pass
> analysis doc — `SIMNTWRK.md` `SIMDSTR.md` `SIMADV.md` `SIMSERV.md` `SIMECO.md` `STRTSIM.md`
> `SCENARIO.md` — via `re/scripts/delegate_module.ps1` + `re/scripts/merge_worker_module.py`.
> Findings are C1/C2 only (workers cannot verify, so C3+ claims are capped on merge).
> Spot-checked against the binary: SIMNTWRK's 2 GZCLSIDs + TilingRules strings, SIMECO's
> pollution-layer factory (`new(0x4d0)`, returns `+0x1c`, CLSID `0xc0a81498`) — all correct.

> **ALSO DONE 2026-08-15 (later):** pass 2 on SCENARIO / SIMADV / SIMECO / SIMDSTR via
> `re/scripts/delegate_pass2.ps1` → `re/analysis/<MODULE>_PASS2.md` (a SUPPLEMENT; the pass-1
> doc is not overwritten). **C1 108 → 46.** And **U-023 + U-024 are resolved** — the sprite
> block's producer is `GZGraphicD.dll`'s image class, and every header field is now named.
> Backups: `re/scripts/backup.ps1` mirrors ~1.2 GB to `D:\Backups\Simcity-RE`.

1. **Remaining C1 (46)**: SC3U 26, SIMUI 13, SIMUTIL 4, GZResourceD/SIMNTWRK/STRTSIM 1 each.
   SC3U and SIMUI are the two big un-passed surfaces.
2. **U-023** — the class behind IID `0x0487534f` (sprite-block consumer). Names the last
   unexplained span-sprite header fields. Needs `VtableProbe.java`, not grep.
3. **SIMGEOM `0x76`–`0x7a`** — 5 of the 7 resource-variant slots have no proven consumer, and
   the purpose-bit names (1/2/4) are still unknown. See `SIMGEOM_PROPERTIES.md` OPEN list.
4. **The `.SII` text mirrors** (10 files beside the sprite `.DAT`s) may name sprite records —
   a cheap cross-check now that the images exist.
4. **Queued live-Ghidra data xrefs** (text export cannot resolve these): config-loader vtable slot
   indices per layer; the scale float `_DAT_1003c644`; the writers of the power mask/demand
   rasters; SIMSPR's post-QFS pixel path.

---



---

## READY-TO-PASTE KICKOFF PROMPT (new orchestrator session, in the Simcity folder)

> You are the parent orchestrator for the SimCity 3000 RE project. Read first, in order:
> `HANDOFF.md` (the head — "WHERE THE PROJECT IS" — is current; everything under the
> ⚠️ banner is a 2026-08-15 snapshot and partly dead), `ROADMAP.md` (the P1 gate and the
> **END-STATE DECIDED** block), `re/analysis/formats/CITY_SAVE.md`, and `U-029` in
> `UNCERTAINTIES.md`. Boot from those, not from any transcript.
>
> **STATE.** End-state is a **modding / format toolkit**; the source-port option is **closed**
> (owner call 2026-08-17). P1's gate is met except criterion 2 — ≥C1 across the eleven core-sim
> modules, **2,299 / 9,575 = 24.0%** — and that criterion should itself be re-examined now that
> the end-state is a toolkit, since a toolkit likely does not need all 9,575.
>
> **THIS SESSION'S GOAL: the first toolkit deliverable — a city-save WRITER that round-trips a
> shipped `.sc3` BYTE-IDENTICALLY.** Reading 59/59 is not writing. The bar to match is the sprite
> work (62,552/62,552 byte-identical re-encode). Until that passes, "the city save is solved"
> means solved for reading. Start by re-emitting an unmodified file through
> container → 24-byte header → QFS → section archive → per-section frame, and diff. Expect QFS
> re-compression to be the hard part; `re/tools/qfs.py` decompresses but a byte-identical
> *compressor* has never been demonstrated. If it cannot be bit-exact, say so early and define
> the weaker bar (game accepts the file) explicitly rather than sliding into it.
>
> **WHAT IS ALREADY DONE — do not redo it.** City save: container, header, QFS, section archive,
> per-section frame, **all 44 section groups traced to their serialisers**, map dimension `N`
> readable from the SIMGEOM tile-grid section, zone layer decoded to per-tile developer slot
> indices with **Residential / Commercial / Industrial / Landfill named from their `SC3Tune.INI`
> sections**. Tools: `re/tools/city_parse.py`, `re/tools/city_sections.py`,
> `re/scripts/find_section_producers.py`. Also settled: the `+0x188`/`+0x18c` conflict was
> multiple inheritance (both readings correct), and the loader's second arm is a **failure
> fallback**, not a format variant.
>
> **DEAD ENDS — do not reopen without new evidence.** The eight zone-grammar sweeps (the grammar
> is at `N*N`; they all failed because they required it to consume to the section end). The
> `3·N²` three-plane reading (only the first `N*N` is a raster). The `+0x0C` section base (it is
> **0**). `U-006` (no `0x41F836xx` GZCLSID exists in any shipped binary). "Dimensions are in
> SC3WorldLayer" (they are not; they are in the tile-grid section).
>
> **METHOD RULES — these cost the most time in the last session, all five are in `HANDOFF.md`.**
> (1) **Silent tool failures were the dominant time sink — four in one session**, every one
> plausible-looking with no error, every one caught by a *disagreement between two methods* and
> never by re-reading code. Cross-check tools against readers and hand-sample output.
> (2) **Never reason backwards from a discrepancy to a cause** — four inferences about one
> 138-byte gap were all wrong. Measure the cause. (3) **Re-read the function, not the summary of
> it** — `CITY_SAVE.md`'s grammar was derived three times and still missed two writes.
> (4) A validation harness can go **circular** once it scores its own output. (5) A coverage
> number that only ever rises is not measuring anything.
>
> **PROJECT RULES.** You are the single writer of `functions.csv` / `STUBS.md` /
> `UNCERTAINTIES.md` / `DEFERRED.md`. Delegate read-only analysis to the account2 worker
> (`re/scripts/delegate_cluster.ps1 -Module <M> -Top 25`, then
> `re/scripts/merge_worker_module.py <out> <M> --suffix CLUSTER<N> --merge`); **set
> `$env:REPO_FLEET_DELEGATE`** or those scripts throw. Keep Ghidra runs and all writes local. Do
> not report worker $ cost. **VERIFY worker claims against the binary before merging** — several
> were wrong. `re/scripts/classify_families.py` bulk-labels the small-function tail at **C1
> only**; run `--validate` first and never promote its rows to C2 without reading them.
>
> **PUBLIC REPO.** `github.com/nanofives/sc3kre` is public: tools and notes only, never assets.
> `.gitignore` is deny-by-default and its `re/analysis` rule must stay per-directory (the
> `**/*.md` form leaks). Grep every diff for `C:\Users\`, the worker account name and the owner's
> email before committing. ⚠️ **Known unresolved:** the local Windows username is already in the
> repo's *history* from a delegation footer; scrubbed going forward, a history rewrite is the
> owner's call.
>
> **OPEN ITEMS, ranked.** (1) the save writer above; (2) `U-029` semantics — what the `u16`
> per-tile permutation is for, what the `c1` keys `3000/5000/8000` index, and a `this+0x3c`
> 23-byte-vs-92-byte mismatch; (3) re-scope core-sim ≥C1 against the toolkit decision;
> (4) **windowed mode — ROOT CAUSE now found** (`LAUNCH_CONTROL.md` §16-§21, `U-039`): windowed
> surfaces are created 32bpp while the engine renders 16bpp, so 16bpp output never lands in the
> presented surfaces (black client). One defect also explains U-024 and U-025. Two fixes landed
> in the harness (`-nokeysrc` clears a 100%-failing `DDBLT_KEYSRCOVERRIDE`; U-033 path bug), but
> both are in `re/harness/src`, which is gitignored. Cheap confirmation pending: set the desktop
> to 16bpp and launch windowed. LAUNCH_CONTROL.md is uncommitted (§16-§21 added this session).
>
> **ASK ME** rather than deciding: whether to exclude `re/harness` (1.2 GB of regenerable
> framebuffer BMPs) from `backup.ps1`, and whether to rewrite the public repo's history.
>
> Commit at boundaries; keep `.happy/project-info.json` current; confirm before large delegation
> runs.