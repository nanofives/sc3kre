# GATE_RESCOPE.md — re-scoping P1 criterion 2 against the toolkit end-state

**Status: ⭐ ADOPTED and then MET, both 2026-08-17.** Option A became P1 gate criterion 2 on the
owner's call at 251/513 = 48.9%, and the remaining 279 were read the same day in 17 delegated
clusters over two rounds. **Final: 530 / 530 = 100%.** The set grew 513 → 530 during the reading
because the exports were regenerated mid-flight, so the number to quote is whatever
`re/scripts/scope_toolkit.py` reports, not this figure.

**P1 now holds in full.** Criterion 1 regressed while criterion 2 was being closed (the mid-session
re-export left `FUN_` bodies with no tracker row) and was re-closed the same day:
`enumerate_functions.py` added **129** rows, and a direct check finds 0 unenumerated `FUN_` bodies
across all 30 binaries. That gap was first reported as 271 — wrong, and mine: the check matched
`'_FUN_' in filename`, which also catches the 142 `thunk_FUN_*` import stubs the criterion
excludes.

> ⚠️ **The tracker moved while these numbers were being taken.** A concurrent session wrote 17 new
> **C3** rows into `functions.csv` mid-measurement, which shifted SIMRCI's remaining count from 57
> to 55 between two runs of the same script. The **513** is binary-derived and stable; every count
> derived from `functions.csv` is a snapshot. Re-run the script rather than quoting a figure here.
> Those 17 C3 rows are also worth a look on their own: C3 in this project means behaviour
> confirmed by runtime observation, a second witness or data-file validation, and the project rule
> is to verify worker claims against the binary before trusting them.

## The question

P1 gate criterion 2 reads *"≥ C1 for every function in the eleven core-sim modules"* — **2,312 of
9,575 = 24.1%** today. That criterion was written while the end-state was undecided. The end-state
is now a **modding / format toolkit** (owner's call, 2026-08-17), and `ROADMAP.md` already says to
deprioritise anything that only matters to a reimplementation. So: **how much of the 9,575 does a
toolkit actually need?**

This document answers with a measurement, not a preference.

## What the current 24.1% is made of

| | count |
|---|---|
| core-sim `fun` rows | 9,575 |
| ≥ C1 | 2,312 |
| — of those, written by `classify_families.py` (**a regex, C1, nothing read**) | **1,473** |
| — of those, actually read by a human or worker | **839** |
| C2 / C3 | 823 / 21 |
| still C0 | 7,263 — **71% of them under 100 bytes**, median 57 B |

So the honest read-coverage of the core-sim set is **839 functions**, and the gate as written has
**7,263 to go**, of which roughly five thousand are sub-100-byte accessors and forwarding stubs.
`HANDOFF.md` already records that grinding those 25-at-a-time is the wrong tool.

## The toolkit-necessary set: 513 functions, 5.4%

A toolkit reads, edits and rewrites shipped files; it does not simulate. So the functions it needs
are the ones that touch bytes on disk or name what is on disk. Four criteria, each citable:

| | criterion | hits |
|---|---|---|
| **S1** | ≥ 3 calls to a **pinned** GZCOM stream slot (writes `+0x64/0x68/0x84/0x88/0x8c/0x98/0xac`, reads `+0x14/0x18/0x34/0x38`; primitives pinned by construction at `0x1000c169` etc., `formats/CITY_SAVE.md`) | 349 |
| **S2** | mentions a known section **TYPE** literal — the `{type, group}` store pair | 138 |
| **S3** | mentions a GZCOM **class id that occurs as a section `group`** in a shipped file (the registration / factory / ctor chain that names a section) | 95 |
| **S4** | references a `.INI` string — the content is data-driven (`U-006`: no per-building classes in code), so the INI loaders **are** the taxonomy | 71 |

**Union: 513 of 9,575 = 5.4%. Already ≥ C2: 251. Left to read: 262.**

| module | fun | toolkit | ≥C2 | to read |
|---|---|---|---|---|
| SIMRCI | 1,536 | 109 | 52 | 57 |
| SIMMISC | 1,200 | 79 | 40 | 39 |
| SIMDSTR | 1,191 | 77 | 42 | 35 |
| SIMUTIL | 763 | 48 | 18 | 30 |
| SIMSERV | 713 | 47 | 16 | 31 |
| SIMGEOM | 1,148 | 44 | 29 | 15 |
| SIMECO | 659 | 32 | 13 | 19 |
| SimTransit | 619 | 27 | 22 | 5 |
| SIMNTWRK | 809 | 27 | 12 | 15 |
| SIMCITY | 587 | 19 | 6 | 13 |
| SIMVARIABLES | 350 | 4 | 1 | 3 |
| **TOTAL** | **9,575** | **513** | **251** | **262** |

54 functions satisfy **S1+S2+S3 together** — stream slots *and* a section key *and* a class id,
i.e. the textbook serialiser shape. That the three independent criteria converge on the same 54 is
an internal consistency check nobody designed for.

## Why the number is trustworthy, and where it is not

**Recall: 50/50 = 100%.** `--validate` tests the instrument against every serialiser site located
by `find_section_producers.py`, an unrelated method — all 50 land in S1 or S2. That is the only
reason the sizes above are quotable, and it is the check `classify_families.py` taught this project
to run first.

**Threshold-insensitive.** The `≥3 slot calls` cutoff is not fitted:

| min slot calls | toolkit set | to read | recall |
|---|---|---|---|
| 2 | 731 | 427 | 50/50 |
| **3** | **513** | **262** | 50/50 |
| 5 | 378 | 168 | 50/50 |
| 8 | 317 | 132 | 50/50 |
| 12 | 282 | 119 | 50/50 |

Across a 6x range of thresholds the answer stays **119–427 functions to read**, against **7,263**
for the gate as written. The conclusion survives any cutoff in that range.

**Precision is NOT measured, and that is the honest limit.** A slot offset only means "stream" if
the object holding it *is* a stream, and a text sweep cannot tell. The project's own direction test
has the same limitation and handles it the same way (require several calls, report counts). Six
`S1`-only members of SIMRCI were sampled by hand: five make multiple raw-block or `u32` read-slot
calls, consistent with serialisers; one (`0x1000dd1a`) makes three `+0x68` calls on an object at
`this+0x38` that is **not** established to be a stream. So expect some false positives, and expect
the true set to be *smaller* than 513, not larger — which does not change the decision.

Two instrument bugs were found and fixed while building this, both silent, both caught by a
disagreement between two methods rather than by inspection:

1. **`S4` reported 0 across all eleven modules** — impossible, SIMRCI alone has five INI names.
   Ghidra renames string symbols with dots as underscores (`s_Sys_SC3ComLayer_ini_10057528`), so a
   `\.ini` pattern matches nothing in the export. Same family as the leading-zeros bug in
   `find_section_producers.py`.
2. **The summary printed "the gate as written costs 9,388"**, which contradicted an independent
   count of `functions.csv` (7,263). The summary line was comparing total core-sim functions
   against the *toolkit set's* C1 count. Two numbers that had to agree and did not.

A third disagreement went the other way and is worth recording: a hand grep found no slot call in
`0x1000dd1a` while the script found three. **The script was right** — Ghidra wraps long calls
across lines and the script's `\s` spans newlines. The narrow instrument was the shell one.

## Options, with their costs

| | gate | cost | what it guarantees |
|---|---|---|---|
| **A** ⭐ **ADOPTED** | **≥ C2 across the 513-function toolkit set**; the rest of core-sim drops to "enumerated" like the UI/framework tier | **262 reads** (~11 cluster runs of 25) | every function that touches a shipped byte or names a section has been *read*. Directly underwrites the toolkit end-state |
| B | ≥ C1 across the toolkit set only | 262 rows, but C1 accepts a regex label | cheapest, and weakest — C1 does not mean anyone read it, which is exactly what a format needs |
| C | leave criterion 2 as written | 7,263 | completeness over the core-sim set, most of it sub-100-byte accessors irrelevant to a toolkit |
| D | A as the binding gate, plus "≥ C1 across all core-sim" kept as a non-blocking stretch | 262 to pass, 7,263 to finish | passes the gate on capability without discarding the wider goal |

**Recommendation: A.** It is the smallest gate that actually guarantees the declared end-state, it
raises the bar where it matters (C2 = the decompilation was read, versus 1,473 rows currently
labelled by regex), and it is re-measurable by a validated script rather than by judgement. B is
weaker than the current gate in the only dimension a format cares about. C keeps a number that
`HANDOFF.md` already identifies as the wrong tool for the remaining tail.

If A is adopted, the follow-on is mechanical: `scope_toolkit.py --list <MODULE>` emits the RVAs,
which is exactly the input `delegate_cluster.ps1` takes.
