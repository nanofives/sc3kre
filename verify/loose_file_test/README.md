# loose_file_test — does a loose file shadow `SYS.PAK`?

**This is the T3 scoping question, and it decides how much work T3 is.** If the game prefers a
loose file on disk over the copy inside `Apps\Sys\SYS.PAK`, then modding a tunable is "drop a file
next to the exe" and **no PAK writer is needed**. If it does not, the archive has to be rewritten
in place, which is a whole extra format to prove.

## The state of the install RIGHT NOW

**One file has been added to the game install** (2026-08-17):

```
Apps\Sys\SC3Tune.ini      3,304 bytes   sha256 7dcf2d560789322b4ad4f43cb54d4719...
```

It is the `SC3Tune.ini` extracted from `SYS.PAK`, **byte-for-byte, with exactly one value
changed**:

```
[CreditsTunables]
ScrollRateInPixelsPerMinute=1500     ->     4242
```

`SYS.PAK` itself is **untouched** — sha256 `172c02d98ac525dc01e42d17553be346…` before and after.

### UNDO

```
del "Apps\Sys\SC3Tune.ini"
```

That is the whole of it. Nothing else in the install was modified, nothing was overwritten, and
the archive still contains the original file.

## Why this file and this value

- `SC3Tune.ini` is the tuning file the zone developers actually read — `LandfillZoneDeveloper`,
  `ResidentialZoneDeveloper` and the rest each load a named section from it, and SIMGEOM reads
  `MaxAnimationsBase` / `BuildingAnimationTunables` from it `[CONFIRMED @0x1000d290]`. It is the
  file a modder would most want to change, so it is the right one to test.
- The loose path the code builds is `\Sys\<name>`, which is `Apps\Sys\SC3Tune.ini` here — three
  SC3U functions build that form alongside `\Sys\SYS.PAK` and hand them to two different setters
  on the same object (`FUN_004711f8` stores the loose path at `this+0x04`, `FUN_00486c43` stores
  the archive path at `this+0x64`) `[CONFIRMED @0x0042252d, 0x004229e0]`.
- **The changed value is deliberately harmless.** Credits scroll rate cannot break a save, a city
  or the sim. If the game ignores loose files, nothing happens at all.

## How to read the result

**The definitive observation is whether the process OPENS `Apps\Sys\SC3Tune.ini`**, not whether
the credits scroll faster. A file-open trace answers it in one run with no interpretation:

| observation | conclusion |
|---|---|
| the process opens `Apps\Sys\SC3Tune.ini` | **loose files are consulted.** Whether they *win* still needs the value check below, but a PAK writer is probably unnecessary |
| it never opens that path, only `SYS.PAK` | **the archive is the only source.** T3 needs a `SYS.PAK` writer, and `syspak_parse.py` is read-only today |
| it opens both | the order and the failure behaviour decide it — capture which one is read *last* |

Fallback if no trace is available: watch the credits. `4242` against `1500` is nearly 3x, so the
difference is obvious without timing anything.

## ⭐ THE CODE ANSWERED FIRST, so this test now has a PREDICTION

Recorded **before** the run, which is the only way a prediction is worth anything.

**The archive wins. A loose file does NOT shadow `SYS.PAK`.** `[CONFIRMED @0x004872e8]`

The resolver `FUN_004872e8` runs once (`if (*(this+0xb4) == 0)`) and, in order: checks the archive
path object is non-empty, checks **`SYS.PAK` exists on disk** (`FUN_0047b98f` →
`GetFileAttributesA`), opens it, then scans the PAK directory for an entry matching the key built
from the loose path at `this+0x04`. **On a match it sets `this+0xc0` = the member length,
`this+0xb4` = 2, and returns** (lines 69-82). Only if the PAK is absent, will not open, or has no
matching entry does it fall through to `this+0xb4` = **1** (line 99). The consumer `FUN_00486f55`
then switches on that field: `1` opens the loose file at `this+0x04`, `2` reads from the
already-open PAK stream.

Verified here rather than taken on trust: the resolver was re-read line by line, and the
read-only claim was settled with a **live vtable dump** — `PTR_FUN_004d87ec` slot 3 (`+0x0c`) is
`FUN_0047b437`, which maps `param_1 & 1` → `GENERIC_READ` and `& 2` → `GENERIC_WRITE`. The call
site passes `(1, 2, 1)`, so the archive is opened **`GENERIC_READ` / `OPEN_EXISTING` /
`FILE_SHARE_READ`** — no write access.

### So this test should show NOTHING

`SYS.PAK` contains `SC3Tune.ini`, so the loose copy should be ignored and the credits should
scroll at the shipped rate. **If the credits scroll ~3x faster, the code reading above is wrong
and that is the interesting result.** Either way it is worth the ten minutes: a confirmed
prediction closes T3's scoping question, and a falsified one means a re-read.

### ⭐ ARM 2 IS NOW STAGED (owner's call, 2026-08-17)

`Apps\Sys\` currently holds **51 loose `.ini` files extracted from the archive**, plus
`SYS.PAK.disabled`. The archive itself is **byte-unchanged** (sha256 `172c02d9…`, verified before
and after); it is only renamed, and the loader matches the literal `\Sys\SYS.PAK`, so its
`GetFileAttributesA` check now fails and the documented loose fallback is the only path left.

The `SC3Tune.ini` marker was re-applied after extraction, so **arm 2 is the observable half**:

| arm | install state | prediction |
|---|---|---|
| 1 | `SYS.PAK` present + one loose `SC3Tune.ini` | **no effect** — the archive wins, the loose file is ignored |
| **2** | `SYS.PAK.disabled` + all 51 loose | **the marker takes effect** — credits scroll at 4242, ~3x the shipped 1500 |

Arm 1 has already been overwritten by arm 2 on disk. To test arm 1, put the archive back first
(step 1 of the undo) and leave the loose files in place.

**If arm 2 shows no effect either**, then loose files are never read for these names and the
fallback reading is wrong — which would make route A (a `SYS.PAK` writer) the only way to mod a
tunable, and would be the more valuable result of the two.

### UNDO for arm 2

```
move "Apps\Sys\SYS.PAK.disabled" "Apps\Sys\SYS.PAK"
```
then delete the 51 extracted `.ini` files. Every filename, size and sha256 is in
`ARM2_MANIFEST.txt` next to this README. Nothing else in the install was touched.

Line endings: the extracted files use **CRLF**, chosen because every loose config the game ships
(`Apps\SC3U.ini`, `Apps\SC3.cfg`, `Apps\SC3Net.cfg`) is CRLF. The archive stores records
line-framed with no terminators, so a convention had to be picked and this is the shipped one.

## What this cannot tell you

Opening a file is not the same as *preferring* it. If the trace shows both paths opened, the
remaining question is precedence, and the honest next step is the code — the method on that object
that consults `this+0x04` and `this+0x64`. A worker is on that question in parallel; this test is
the empirical half of the same answer, and the two should agree.

> Note for whoever runs it: this file is the only change to the install, and deleting it restores
> the shipped state exactly. If you would rather not run with a modified install at all, say so and
> delete it — the code-side answer is being pursued independently.
