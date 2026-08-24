# tilingrules_read_test — RESULTS

Run 2026-08-21 21:07. Probe `sc3probe.dll` 226,304 B, built from `sc3probe.c` with the
multi-module filetrace fix (README §3). Harness claimed via
`re/scripts/harness_claim.ps1 -Claim -Owner roads`.

```
pwsh re/harness/capture.ps1 -Name tiling_t0 \
  -Switches "-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace" \
  -GameArgs "-lFarmsville" -AtSec 45
```

Log: `re/harness/capture.log`, 212 FILETRACE lines.

## T0 — POSITIVE. The game reads `Apps\Res\TilingRules\`.

Per the outcome table committed in README §4, row 1: **files are read from this directory, the
surface is live.**

Hooks armed first, so the result is not a silent-failure artefact:

```
[    1.551 ms] --- FILETRACE: hooking ALL modules (CreateFileA / GetFileAttributesA /
               FindFirstFileA), re-armed every 100 ms; watching ... TilingRules / _GRND_ / .txt ---
```

Then, at ~1,735 ms, the rule load runs on one thread (`tid 6b9c`) as a tight contiguous burst
spanning 1,735-1,749 ms:

```
FILETRACE #55: GetFileAttributesA "...\Apps\Res\TilingRules\ROAD_GRND_Set.txt" -> exists
FILETRACE #56: CreateFileA        "...\Apps\Res\TilingRules\ROAD_GRND_Set.txt" -> ok
FILETRACE #57: GetFileAttributesA "...\Apps\Res\TilingRules\HWAY_GRND_Set.txt" -> exists
FILETRACE #58: CreateFileA        "...\Apps\Res\TilingRules\HWAY_GRND_Set.txt" -> ok
...
```

**48 distinct rule files opened, every one `-> ok`. Zero `FAIL`, zero `MISSING`.**

Three details that corroborate the static analysis rather than merely agreeing with it:

1. **The base directory is `Apps\Res\`.** This closes the `[UNCERTAIN]` in
   `re/analysis/NETWORK_TYPES.md` §5 and README §2 — the loader's caller-supplied base dir was
   the one thing static reading could not resolve.
2. **Exactly 48 files are opened, and SIMNTWRK's `strings.csv` contains exactly 48 rule-file
   literals.** The set of files read is precisely the set of hard-coded names, which is the
   dynamic confirmation of the "no directory scan, no manifest" finding
   (`NETWORK_TYPES.md` §2).
3. **The access pattern is `GetFileAttributesA` (exists) then `CreateFileA` (open), per file,
   direct from disk.** No `SYS.PAK` consultation appears anywhere in the burst. This is the
   opposite of the `loose_file_test` ARM3 result, and it is why that precedent does not apply
   here: these files were never in an archive to be shadowed by.

Load order matches `FUN_10016d87` then the Convert group, ROAD before HWAY before RAIL, as the
straight-line code emits them.

## Finding: a latent case-sensitivity bug in the shipped game

The game asks for **`Road_GRND_Protected.txt`** (mixed case `Road`). The file on disk is
**`ROAD_GRND_Protected.txt`** (upper). It opens `-> ok` **only because NTFS is
case-insensitive**. All five sibling networks use the consistent upper-case form
(`HWAY_`, `RAIL_`, `SUBW_`, `POWR_`, `PIPE_GRND_Protected.txt`).

This was visible statically — `SIMNTWRK`'s string table holds both a `Road_GRND` and a `ROAD_GRND`
prefix — but its consequence only shows up when the filesystem is asked.

**Consequence: on a case-sensitive filesystem this open fails**, and road protected-tile rules
load as empty while the other five networks load fine. Relevant to Wine/Proton with a
case-sensitive mount, and to any future port. Filed as **U-074** (defect confirmed, consequence
untested).

## What is NOT read at city load: 20 of the 68 files

| files | status |
|---|---|
| `{ROAD,RAIL,HWAY,SUBW,POWR,PIPE}_GRND_SlopeRULES.txt` (6) | **Not referenced in ANY module.** Dead. |
| `{ROAD,RAIL,SUBW}_Exits.txt` (3) | **Not referenced in ANY module.** Dead. |
| `networkIntesection.txt` (1, note the shipped typo) | **Not referenced in ANY module.** Dead. |
| `ROAD_GRND_FinalRules.txt` (1) | **Not referenced in ANY module.** Dead. Distinct from `ROAD_GRND_final.txt`, which *is* read. |
| `PIPE_GRND_Bridges.txt`, `SUBW_GRND_Bridges.txt` (2) | Dead, and **this independently confirms** `NETWORK_TYPES.md` §5: only 4 of 6 networks can bridge. The files ship, the loader never builds their paths. |
| `LandfillRules1..6.txt`, `LandfillStartRule.txt` (7) | **Live but lazy** — referenced by `SIMRCI`, not `SIMNTWRK`. Not expected at city load. |

Searches run with raw `grep` over `re/ghidra_export*/strings.csv` (the harness `Grep` tool cannot
see the exports, `U-056`).

So **13 of the 68 shipped files are dead weight**, and any tiling mod should ignore them. Editing
`ROAD_GRND_SlopeRULES.txt` or `ROAD_Exits.txt` would produce no effect and look like a failed
experiment.

## Interpretation limit — this does NOT yet prove edits take effect

Stated in README §5 before the run and it still holds. T0 proves the files are **opened and
parsed**. `NETWORK_TYPES.md` §5 documents substantial hard-coded `.rdata` piece and orientation
tables (`DAT_10031fd8..0x10032028`, `DAT_100318ac`) that could override text rules. **T1 (a
content edit) is required to prove behaviour, and has not been run.**

### Correction: the rules load at STARTUP, not at city load

The run was launched with `-lFarmsville`, but **the city never loaded** — there are zero `.sc3` /
`Cities` FILETRACE hits, and the captured frame
(`.happy-share/.../tiling_t0_210733.png`) is the **main menu**, in Spanish, after 44 s of
runtime.

The rule load happened anyway, complete, at 1,735-1,749 ms. So **all 48 files are read
unconditionally during module/layer init at startup, before and independent of any city**. An
earlier draft of this file attributed the burst to city setup; that was wrong and is corrected
here.

This does not weaken T0 - it strengthens the modding story, since edited rules are consumed at
boot with no city required. But it does mean:

- The `-l<value>` switch (`0x004077b5` +77, which routes through GZCOM service `0x441E5070`
  rather than a direct file open) **did not load a city in this configuration**. Cause not
  established. Recorded as a harness gap, and it **blocks T1**, which needs roads on screen.
- The claim "not expected at city load" for the `Landfill*` files is untested either way: no city
  was loaded, so nothing lazy was exercised.

Scope of this run: **startup only.** Anything loaded on demand during gameplay was outside it.

## T1 — INCONCLUSIVE. Not a negative: the observation channel was unavailable.

Attempted 2026-08-21, five launches. **The edit was made and read; the effect could not be
observed.** Neither committed outcome row in README §4 applies, because both require seeing the
map. Recording it as inconclusive rather than stretching it into a result.

### What was done

`Apps\Res\TilingRules` backed up whole to `verify/tilingrules_read_test/TilingRules.bak` (68/68
files; the backup is gitignored by `/verify/*/*`, so game content cannot reach the public repo).
`ROAD_GRND_Set.txt` replaced: the 110-id allowed-piece list (744 B, SHA-256 `9926948A…`) became
`{99999}` (7 B), a single id that matches no piece.

**Confirmed read in the modified state:**

```
FILETRACE #60: GetFileAttributesA "...\TilingRules\ROAD_GRND_Set.txt" -> exists
FILETRACE #61: CreateFileA        "...\TilingRules\ROAD_GRND_Set.txt" -> ok
```

Result: **no crash, no exception, no dump, and the city still loaded** (25 `Farmsville` accesses),
run held 49 s. So the road allowed-piece list is **not validated and not required for a successful
city load** — a real but weak datum. Whether road tiles render or connect differently is exactly
what could not be seen.

Restored from backup and verified: SHA-256 matches `9926948A…`, and all 68 files match the backup
byte-for-byte.

### Why it could not be concluded: the render defect, now localised

The blocker is a pre-existing documented defect, not this test's design. `HANDOFF.md` open item 4
and `LAUNCH_CONTROL.md` §16-§21 (`U-039`, `U-024`, `U-025`): windowed surfaces are created 32bpp
while the engine renders 16bpp.

This run **sharpens where it bites**, which is the useful part:

| state | frame produced? | engine counters |
|---|---|---|
| main menu, no city | **yes** - `SHOT #13` at 44,067 ms, a correct 2560x1440 composite | `Blt=0` |
| city loaded (Farmsville) | **no** - zero `SHOT` lines at 50 s, 75 s | `Blt=0`, `Flip=0`, `Lock=0` throughout |

Same switch set, same probe, sole difference the loaded city. So **the menu path reconstructs a
frame and the in-city path does not.**

**Not filed as a new uncertainty — it is already `U-068`.** Checked 2026-08-22: the rendering
session had independently diagnosed this to a single call. `U-068` /
`LAUNCH_CONTROL.md` §33.2 defect 6: the iso view's graphics device cannot create a backing store
after a DirectDraw teardown, `dev->vf0c(w,h)` at ~`0x10005b7c` returns **0**, `Init` ignores the
failure, so `iso+0x524` stays 0 and no terrain draws. Their note calls it "the ONLY thing between
the five verified in-city fixes and a rendered city".

So this run is **corroboration from an independent route**, not a new finding: a different
observable (blit-mirror shot reconstruction) fails exactly where their surface-level diagnosis
predicts. **T1 unblocks when `U-068` closes** — no separate work is needed on this side.

### City provenance — why these results are not exposed to the `Cities\` position hazard

`GAME_PROTOCOL.md` rule 6 (added 2026-08-23 by the bigger-cities session): the load-city dialog's
confirm id `0x02DFDD6A` selects a **position in the list, not a city**, so adding or removing any
`.sc3` silently re-points every other session's click at a different map. It cost another session
three runs.

**Neither T0 nor T1b used that path, and T1b is city-independent anyway.** Two independent reasons:

1. **The fixture was named, not clicked.** Every run here passed a **bare absolute `.sc3` path** as
   a game argument (below), so there is no list position to shift. Better still, the choice is
   *self-evidencing*: the filetrace logs the resolved path, e.g.
   `CreateFileA "…\Cities\Farmsville.sc3" -> ok`. That is a stronger provenance record than
   sampling map dimensions after the fact, because it names the file rather than inferring the map
   from its size.
2. **T1b measures a startup-time counter.** The `_Set.txt` parse runs at 1,735–1,749 ms during
   module init, **before and independent of any city** (see the correction above). The 448 → 340
   result would be identical with no city loaded at all. So the hazard cannot touch it.

**It does apply to the pending visual T1.** Costs, tile counts and "did the road connect" are all
map-dependent, and the failure mode there is worse than a crash: a wrong-city run still produces
numbers. So README §7's procedure now requires a dimension check and forbids leftover saves.

`Cities\` verified stock at the time of writing: **15 `.sc3`, all mtime 2000-04-18**, subdirectories
only the shipped `Scenarios/`, `StarterTowns/`, `Terrains/`. Note the counting trap — a
case-sensitive glob (bash, Python `glob`) returns **14**, because `TUTORIAL.SC3` is upper-case;
reproduced here.

### Harness finding: how a city actually auto-loads

Worth recording because it cost four launches and the documented switch did not do it.

| argument passed to SC3U | observed |
|---|---|
| `-lFarmsville` | **no file access at all.** No `Cities` open, no `FindFirstFileA`. The `-l` path did not reach a file. |
| `-lC:\…\Cities\Farmsville.sc3` | `CreateFileA "-lC:\…\Farmsville.sc3"` → **FAIL**. The `-l` prefix was **not stripped**; the whole token was used as a path. |
| `C:\…\Cities\Farmsville.sc3` (bare absolute path, no switch) | **`-> ok`, city loads.** First open at 1,383 ms, reload at 2,533 ms. |

**So: pass a bare absolute `.sc3` path. Do not use `-l`.** `LAUNCH_CONTROL.md` §397 lists
`-l<value>` as the way to "load a city directly at launch"; against this build, in this
configuration, it did not. Mechanism `[UNCERTAIN]` — the failing attempts carried a leading space
in `-GameArgs` (needed to stop PowerShell binding `-lC:` as a parameter), which may have shifted
tokenisation. What is certain is that the bare path works and is reproducible.

Also note for `capture.ps1` callers: the shot fires at ~44 s, so `-AtSec 40` kills the run before
it lands. Use 60+.

## T1b — non-visual observable. PREDICTION COMMITTED BEFORE THE RUN.

T1 was blocked because the only observable considered was visual. It does not have to be. The
parser itself is instrumentable: `-modlog "SIMNTWRK.DLL:<va>,<va>"` hooks functions in a
late-loading module and reports hit counts (`=== TRACER HIT COUNTS ===`).

**Question this settles:** is the rule file's *content* consumed into the engine, or is the file
merely opened? T0 proved only the open. This proves the parse.

### Instrumented

| VA | function | role |
|---|---|---|
| `0x1001746e` | `sc3_ntwrk_parse_set_line` | **the measurement.** `strtok` + `isdigit` + `atoi`, pushes a 12-byte record `{0xE223741F, 0xA317745F, value}` per parse |
| `0x10016d87` | `sc3_ntwrk_load_set_tables` | **the control.** Builds the 7 `_Set.txt` paths. Runs once regardless of file contents |

### Stock inputs, counted exactly

| file | ids | non-blank lines |
|---|---:|---:|
| DIAG_Set | 14 | 1 |
| HWAY_GRND_Set | 191 | 18 |
| PIPE_GRND_Set | 32 | 3 |
| POWR_GRND_Set | 26 | 2 |
| RAIL_GRND_Set | 38 | 3 |
| **ROAD_GRND_Set** | **109** | **10** |
| SUBW_GRND_Set | 38 | 4 |
| **total** | **448** | **41** |

### Committed predictions

The edit is `ROAD_GRND_Set.txt` → `{99999}`: **1 id, 1 line**.

| hypothesis | stock count | modified count | delta |
|---|---:|---:|---:|
| **H1** `parse_set_line` runs **per id** | 448 | 340 | **−108** |
| **H2** it runs **per line** (strtok loop inside) | 41 | 32 | **−9** |
| **H3** content is NOT consumed | any | **identical** | **0** |

Control `0x10016d87` must read **the same in both runs** under H1 and H2. If the control moves,
the runs are not comparable and the measurement is void.

**This is falsifiable in a way T1 was not:** H3 is a real possible outcome, and it would mean the
48 files are opened and their contents discarded — which would demote the tiling surface from
"live" to "read but inert". The experiment also incidentally decides H1 vs H2, i.e. whether the
parser is per-id or per-line, which the static analysis left ambiguous.

### Round 1 result: BOTH H1 AND H2 FALSIFIED. Instrument was wrong, not the theory.

Stock run measured **`0x1001746e` = 7 hits**, control `0x10016d87` = 1. Seven hits from **seven
distinct unrolled call sites** (`SIMNTWRK+0x1728D`, `+0x172A4`, `+0x172BB`, `+0x17300`, `+0x17317`,
…), all inside `FUN_10016d87`.

So `sc3_ntwrk_parse_set_line` is **called once per Set FILE** — seven files, seven calls. A
per-line loop would have shared a single call site. **The name is a misnomer**: reading the body
confirms it parses an entire file, with the `strtok` loop *inside* it. Corrected in
`re/analysis/NETWORK_TYPES.md`.

Consequence: this counter is **content-insensitive** — it reads 7 whatever the files contain, so
it cannot discriminate H3. Not a result about the game, a badly chosen instrument.

### Round 2: the correct per-id observable

`FUN_1001746e` body (`re/ghidra_export_simntwrk/functions/1001746e_FUN_1001746e.c`): after
`FUN_10017596` reads the file into a 0x20000 buffer, the `strtok` loop calls, for **each token
whose first character is a digit**:

```c
local_18[2] = atoi(pcVar2);
FUN_1001b456(param_3, local_18);   /* append the 12-byte record */
```

`local_18` is the `{0xE223741F, 0xA317745F, value}` record (`-0x1ddc8be1` = `0xE223741F`).

**`FUN_1001b456` has exactly ONE call site in the whole module** — this one. So it is a dedicated
per-id append, not a shared container helper. That makes it both precise and safe to hook (no log
flood).

| hooked | prediction stock | prediction modified | delta |
|---|---:|---:|---:|
| `0x1001b456` per-id append | **448** (= the exact id total) | **340** | **−108** |
| `0x1001746e` per-file parse (**control**) | **7** | **7** | **0** |

Committed before the round-2 runs. H3 survives only if the append count is identical across runs.

### Round 2 result: T1b PASSES. Predicted to the digit.

| run | `ROAD_GRND_Set.txt` | `0x1001b456` per-id appends | `0x1001746e` control |
|---|---|---:|---:|
| stock | 744 B, 109 ids | **448** | **7** |
| modified | 7 B, `{99999}`, 1 id | **340** | **7** |
| **delta** | −108 ids | **−108** | **0** |

**Predicted 448 → 340, control 7 → 7. Measured 448 → 340, control 7 → 7.** Exact, both numbers,
no fitting after the fact — the prediction is in the section above this one.

**H3 is falsified. The content of the tiling rule files is parsed into the engine's data
structures, and the number of records the engine builds is a direct function of what is in the
file.** Change 109 ids to 1 and the engine builds 108 fewer records.

The control is what makes this airtight: `0x1001746e` stayed at exactly 7 in both runs, so the
loader ran identically and only the *per-id* work changed. A confounded run would have moved both.

This is the first time this project has demonstrated that **an edit to a plain-text game file
changes what the engine builds in memory**, measured rather than inferred.

### What T1b does and does not establish

**Does:** the 48 files are not merely opened (T0) — their contents are tokenised, converted with
`atoi`, and appended as `{0xE223741F, 0xA317745F, value}` records into the per-network Set
vectors. The data path from text file to engine structure is confirmed end to end.

**Does not:** show that the resulting records change *rendered or simulated* behaviour. The
records land in the vectors that `FUN_1001a7f7(netType, pieceId)` linear-scans for compatibility,
but whether a road tile then looks or connects differently still needs the visual T1, still
blocked on `U-068`. Also unchanged: a 7-byte Set file causes **no crash and the city still
loads**, so the allowed-piece list is not validated.

So the ladder now reads: **T0 = files are read. T1b = contents are consumed. T1 = behaviour,
still open.**

### Method note worth keeping

The first instrument was wrong and the run said so cheaply. Hooking `0x1001746e` looked like the
obvious per-record counter given its name; it is per-file. **The fix came from reading the
function body and finding the callee inside the loop, then checking that callee had exactly one
call site in the module** so its count could not be diluted by other callers. Both checks are
cheap and both were necessary.

## Net effect on the modding picture

`NETWORK_TYPES.md` §6 item 3 was ranked highest-leverage but gated on this question. **The gate
is passed.** The tiling surface is 48 plain-text files, read loose from disk at city load, with no
archive, no compression, and no repack step. It is now **tooled** (`re/tools/tilingrules.py`, 68/68 byte-identical round-trip with a
writer) and its **rule-opcode grammar is documented** (`re/analysis/formats/TILINGRULES.md`,
and all three field encodings decoded in `re/analysis/NETWORK_RULE_ENGINE.md` §4). Both landed
the same day as this test, so the "untooled/undocumented" caveat above is superseded.

The verdict on the original question is unchanged: this is retuning an existing network, not
adding one. A 7th network still needs the four code patches in `NETWORK_TYPES.md` §2.

---

# T1 attempt, 2026-08-24: NO RESULT ABOUT TILING RULES. The capture path produced no frame.

**Verdict: none of §4's T1 rows applies.** Run 1 is the baseline *and* the instrument control, and
the control failed. Per the stop rule agreed before launch, run 2 was not performed and
`ROAD_GRND_Set.txt` was never edited. **Nothing is concluded about whether an edited rule changes
the map.**

## Game content: untouched, verified twice

| moment | `Apps\Res\TilingRules\ROAD_GRND_Set.txt` | file count |
|---|---|---|
| before | `9926948A…1358` | 68 |
| after | `9926948A…1358` | 68 |

`TilingRules.bak\ROAD_GRND_Set.txt` also `9926948A…1358`, 68 files. Step 0 was already satisfied on
this machine. The install was `stock (matches original/)` at release, harness claim and game lease
both taken as `roads` and both released.

## What run 1 did

The §7 baseline invocation, unmodified, against the bare absolute `Cities\Farmsville.sc3` fixture,
`-AtSec 75`. The game launched, ran the full 71 s and was closed by the harness. It did not crash,
did not hit the ~840 ms single-instance guard, and was drawing continuously throughout:

- `blt_disp_1` 7,542 by t+5 s, rising past 57,997
- `raster_blit_hw` **26,565** by t+65 s, with `rasthw_throw = 0` and `rasthw_surfacelost = 0`
- `FNLOG[GZGraphicD]: 35/35 instrumented`

and **zero `### SHOT #` lines in 71 s.** No BMP was written, so `capture.ps1` exited 1. It correctly
refused the pre-existing `shot_01..03.bmp` from an earlier session on its mtime filter, so no
foreign frame was graded.

## `Blt=0 Flip=0 Lock=0` is NOT the symptom, and the earlier note should stop citing it

§7 records the 2026-08-22 in-city attempt as `Blt=0 Flip=0 Lock=0` with zero SHOT lines, reading the
zero counters as part of the failure.

**The u068 three-shot run reports `Blt=0(+0) BltFast=0 Flip=0(+0) Lock=0(+0)` at t+5 s, t+10 s and
t+15 s — and then writes a fully rendered 1024x768 city at t+20.786 s.** Those counters are the
DirectDraw IAT hooks; the engine does not render through them. They are zero in a run that works.

**The only diagnostic observable is the presence or absence of `### SHOT #`.**

## The two instruments differ, and the difference is on the shot path itself

Effective argv, run 1 (`capture.ps1` composes the last three itself):

```
-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -shot -gzlog gz_draw.txt -log capture.log -- <abs .sc3>
```

The run that produced a good in-city frame carried the same base switches — the log shows
`NOINTRO`, `FITCLIENT`, `WINDOWED`, `FIX16` and the same `gz_draw.txt` 35/35 table — **plus** four
things `capture.ps1` cannot pass:

1. **`-u068shot`.** This replaces the shot trigger entirely. Plain `-shot` requests a dump on a
   timer (every 3 s) with a 4,000-blit mirror window. `-u068shot` **suppresses that timer** and
   instead requests each dump explicitly at a chosen instant with a **400-blit** window.
2. **An auto-resize armed at t+22.0 s** (`RZ> auto-resize armed: 1280x1024 client at t+22.0s`).
   Shot A is taken at t+19.797 s, *before* it fires, so the resize is not what makes A work — but
   the `rz_*` machinery that arms it is present in that process and absent from a plain `-shot` run.
3. **Camera setup: zoom 3.** Run 1 accepted whatever camera the save restored.
4. **Five capture detours** armed at t+31 ms (`GZGraphicD!0x10015E3D`, `SIMSPR!0x10005B42`,
   `SIMSPR!0x10016EBA`, `GZGraphicD!0x10009EFB`, `SIMSPR!0x1000EF50`).

So the premise correction that unblocked T1 — that in-city rendering works pre-resize — is sound,
and **it is a statement about the u068 probe's `-shot` path, not about `capture.ps1`.** Only one of
the two instruments is known to produce an in-city frame, and T1 was run on the other one.

## A concrete mechanism, and why it fails silently

`sc3probe.c` latches `g_rasthw_dest` from `*(this+4)` on the **first** `raster_blit_hw`
(`FUN_10018c58`) hit, at ~1.1 s. Everything downstream is gated on that one value:

- `g_fb` is allocated only by locking `g_rasthw_dest` through its vtable slot 25.
- a blit is mirrored only when `((DWORD*)this)[1] == g_rasthw_dest`.
- arming is `if (g_shot_req && g_fb)`, so **with `g_fb` NULL the timer request is discarded every
  3 s and nothing is logged.**

The two runs latched different objects from the same code path:

| run | first `raster_blit_hw` | latched `dest_surface` | frame |
|---|---|---|---|
| u068 three-shot | t+1.141 s, `this=0x005A8168` | `0x00A45AB8` | **written, 1024x768** |
| T1 run 1 | t+1.110 s, `this=0x005A9018`, `ret=0x0043D4F7` | `0x0BEC4A80` | **none in 71 s** |

`0x0BEC4A80` stayed as `engine_dest` for the whole run while 26,565 blits went past. Whether `g_fb`
failed to allocate or no blit ever matched the latch is **not distinguishable from the log**,
because neither branch logs anything. `[UNCERTAIN]` — the missing evidence is a single log line on
the `g_fb` allocation attempt and its result.

**That is the actionable defect: a first-blit latch decides the whole capture, it can latch the
wrong object, and when it does the instrument reports success-shaped silence.**

## What run 1 does not establish

**It does not establish that Farmsville loaded.** The §7 invocation carries no `-filetrace`, and
with no frame there is no status bar to read a city name from. `GAME_PROTOCOL.md` rule 6 item 1
requires confirming the city from the log, and this run cannot. The sustained blit activity proves
the process was drawing something; it does not name it.

## For the next attempt

1. **Fix the instrument first, on its own run.** Add a log line on the `g_fb` allocation attempt so
   the two silent failure modes separate, and reconsider latching `g_rasthw_dest` on the first blit.
2. **Or run T1 through the u068 probe's own shot path** rather than `capture.ps1` — that path has a
   witnessed in-city frame and `capture.ps1` does not.
3. **Add `-filetrace` to both T1 runs** so the loaded city is named in the log, per rule 6 item 1.
4. Keep §4's outcome table frozen. It was never reached.
