# credits_discriminator — does the game actually READ `ScrollRateInPixelsPerMinute`?

This test exists to settle `U-051`, and it is deliberately **not** a T3 marker. T3 is being closed
by `verify/tunable_mod_test/` on a traced consumer. This one answers a narrower question that the
first failed attempt left behind.

## Why the original test could not answer anything

On 2026-08-17 the credits rate was set 1500 → 4242 and the credits scrolled at what the observer
judged to be normal speed (`verify/loose_file_test/ARM3_RESULTS.md`). That was recorded as "the
tunable does not drive the credit scroll". **Reading the code shows that conclusion does not
follow, and neither does the tidy explanation offered later.**

Mechanism, all read directly in `SC3U.exe`:

- `FUN_00428801` @ `0x00428801` (credits init) is the only body referencing `[CreditsTunables]`
  (strings `0x004f746c`, `0x004f747c`, `0x004f7450`, `0x004f7434`). It reads the three keys into
  `param_1[0x4c]` (rate), `[0x4d]` (min), `[0x4e]` (max).
- Ctor `0x004286d7` presets `[0x4a]=0`, `[0x4c]=0x3ccccccd`, `[0x4d]=0`, `[0x4e]=4`.
- Per frame `0x004293fd` computes `px = ftol((now - [0x4a]) * [0x4c])`, floors at `[0x4d]`,
  **ceils at `[0x4e]`**, advances the baseline `[0x4a]=now` (line 231) and carries the sub-pixel
  remainder back (line 236). When `px` rounds to 0 the baseline is *not* advanced, so elapsed
  keeps accruing — it is a fractional accumulator, not a stuck counter.
- The shipped `SC3Tune.ini` supplies **only** `ScrollRateInPixelsPerMinute`.
  `MinPixelsToScrollPerFrame` and `MaxPixelsToScrollPerFrame` are **absent**, so they keep the
  ctor defaults `0` and `4`.

**The clamp does not explain the null.** A ceiling of 4 px/frame at ~60 fps is 240 px/s =
**14,400 px/min**. Both 1500 and 4242 px/min sit far below it, so neither was clamped, and 4242
should have run **~2.83x faster**. Two things are therefore live:

- **H1 — the read works.** The rate drives the scroll, and a 2.83x change was simply misjudged by
  eye with no side-by-side reference.
- **H2 — the read silently fails.** `0x3ccccccd` is exactly `0.025f` = `1500/60000`, i.e. **the
  ctor default already equals the shipped value.** So on a shipped archive a failed config read
  is indistinguishable from a successful one, and every "no effect" observation is consistent
  with both. This is the trap that makes the credits useless as a pass/fail marker.

## The fix: measure a duration, do not judge a speed

The credits scroll a fixed distance and exit on their own (`0x004293fd` line 101-106 posts
`0x417` once `param_1[0x4b]` passes the end threshold). **Time to completion is therefore a
number**, and a stopwatch does not have an opinion. That is the single methodological change
from the failed run.

## The ladder

| rung | file | value | length | diff vs shipped |
|---|---|---|---|---|
| **C0 control** | *(shipped archive)* | `1500` | 272,507 | — |
| **C1** | `SYS.PAK.c1_9999` | `9999` | 272,507 (**+0, same length**) | **1 run, 4 bytes** at `[249902, 249906)` |
| **C2** | `SYS.PAK.c2_90000` | `90000` | 272,508 (**+1**) | 1,867 runs, 18,993 bytes |

C1 is same-length, so its 4-byte diff proves the archive is sound exactly the way ARM3's did —
and it lands at the *same offsets* ARM3's edit did (`249,902–249,905`), which is an independent
check that the tooling writes where the previous session's did.

C2 is one byte longer, so it also exercises `build()` on a **growing** archive, where
`tunable_mod_test`'s M2 exercises a shrinking one.

## Predicted durations, written BEFORE the run

Let **T0** = the measured shipped credits duration (rung C0, measured first).

| | H1 (read works) | H2 (read ignored) |
|---|---|---|
| **C1** `9999` | `T0 × 1500/9999` ≈ **T0 / 6.67** | **T0** (unchanged) |
| **C2** `90000` | ceiling binds: speed = `4 px/frame × fps`. At 60 fps that is 14,400 px/min ⇒ **T0 / 9.6** | **T0** (unchanged) |

**The discriminator is robust to frame rate.** If fps is lower than ~42, C1 is clamped too and
its factor shrinks — but under H1 both rungs are still *dramatically* shorter than T0, and under
H2 both are *exactly* T0. The hypotheses predict a categorical difference, not a subtle one.

**Bonus fact available for free.** If C1 and C2 come out at the **same** duration, the ceiling
binds for both, and that shared speed equals `4 × fps` px/s — which yields the harness's actual
frame rate as a by-product.

### What each outcome settles

- **C1 and C2 both much shorter than T0 → H1. `U-051` resolves to "the read works."** The
  original 4242 result was an observer misjudgement of a 2.83x change, and the lesson stands:
  never use a judged rate as a marker. Close `U-051`.
- **C1 and C2 both equal to T0, and `FILETRACE` confirms the game opened our archive → H2.**
  The config read for `[CreditsTunables]` fails or is bypassed. That is a real finding about
  `FUN_00428801`'s config object, and the next step is to read `FUN_00486c5e`'s failure path.
  It would also mean the shipped INI value is decorative.
- **C1 unchanged but C2 shorter.** Would mean something binds between 9999 and 90000 that this
  reading does not predict. Re-read `0x004293fd` before explaining it.
- **C2 shorter than C1 by more than the ceiling allows.** The ceiling reading is wrong; re-read
  `[0x4e]`'s use.

### What this cannot tell you

It settles whether *this one key* reaches *this one consumer*. It says nothing about T3, which is
being closed independently, and nothing about whether other `[CreditsTunables]` keys work — note
that adding `MaxPixelsToScrollPerFrame` to the section would be a *different* test, since that
key is absent from the shipped file entirely.

## How to run it

Measure **C0 first**, on the untouched install, or the other two numbers have nothing to compare
against.

```
:: C0 control -- no staging, install already shipped
re\harness\bin\sc3launch.exe -nocom -windowed -origin -fix16 -fitclient -nointro -quiet -log "re\harness\c0.log"
```
Open the credits, start a stopwatch when the first line appears, stop it when the credits end.
Record T0.

Then for each of C1 and C2, one at a time:

```
move "Apps\Sys\SYS.PAK" "Apps\Sys\SYS.PAK.original"
copy "verify\credits_discriminator\SYS.PAK.c1_9999" "Apps\Sys\SYS.PAK"
re\harness\bin\sc3launch.exe -nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace -log "re\harness\c1.log"
:: time the credits again
del  "Apps\Sys\SYS.PAK"
move "Apps\Sys\SYS.PAK.original" "Apps\Sys\SYS.PAK"
```

Confirm in each log that `FILETRACE` shows `CreateFileA` ok on `Apps\Sys\SYS.PAK`. Without that
line a null result means nothing at all.

### UNDO

```
del  "Apps\Sys\SYS.PAK"
move "Apps\Sys\SYS.PAK.original" "Apps\Sys\SYS.PAK"
certutil -hashfile "Apps\Sys\SYS.PAK" SHA256    :: must be 172c02d9…
```

Record the three durations verbatim in `RESULTS.md` before interpreting them.
