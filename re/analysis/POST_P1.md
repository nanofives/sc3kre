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
| QFS / RefPack | ✅ | ✅ **byte-identical** | compressor transcribed from GZResourceD `FUN_1001694d`; 59/59 city streams re-encode exactly |
| city save family | ✅ 59/59 | ✅ **byte-identical**, 5 layers | `city_roundtrip.py`; plus an editing API, `city_write.py` |
| sprites | ✅ | ✅ **byte-identical** | 62,552/62,552 re-encode |
| `.IXF` container | ✅ | ⚠️ **writer exists but is not exposed** | the container writer lives inside `city_roundtrip.py`, a test harness, not in `ixf_parse.py` |
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
