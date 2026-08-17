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

## What this cannot tell you

Opening a file is not the same as *preferring* it. If the trace shows both paths opened, the
remaining question is precedence, and the honest next step is the code — the method on that object
that consults `this+0x04` and `this+0x64`. A worker is on that question in parallel; this test is
the empirical half of the same answer, and the two should agree.

> Note for whoever runs it: this file is the only change to the install, and deleting it restores
> the shipped state exactly. If you would rather not run with a modified install at all, say so and
> delete it — the code-side answer is being pursued independently.
