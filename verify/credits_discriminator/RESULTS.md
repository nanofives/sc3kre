# credits_discriminator — RESULTS (U-051)

> **TEMPLATE — nothing here is filled in yet.** Fill the `____` blanks. Complete §2 before
> reading §3. Do not edit `README.md`: its predictions were committed in `8d7b603` ahead of the
> run.

Run date: `____`  Run by: `____`

**The whole point of this test is that the observable is a duration, not a speed.** The 2026-08-17
attempt failed because a human was asked to judge a ~2.8x change by eye with nothing to compare
against. Use a stopwatch or a phone timer. Do not describe the scroll as "fast" or "normal"
anywhere in this file.

---

## 1. Timing protocol — read before the first run

Same start and stop cue all three times, or the numbers are not comparable.

- **Start** the timer when the first credit line becomes visible.
- **Stop** it when the credits end on their own (the screen exits / returns to menu). Do not
  click through.
- If you must stop early, use a fixed **landmark** instead — the same name appearing in all three
  runs — and say so in §2.

Cue used: `____`  (credits-end / landmark: `____`)

---

## 2. Raw measurements — fill before reading §3

Run **C0 first**, on the untouched install. Without T0 the other two numbers mean nothing.

| rung | staged archive | expected sha256 | verified sha256 | `CreateFileA` on SYS.PAK in log | **duration** |
|---|---|---|---|---|---|
| **C0** control | *(none — shipped)* | `172c02d9…` | `____` | n/a | **T0 = `____` s** |
| **C1** `9999` | `SYS.PAK.c1_9999` | `2089032d…` | `____` | `____` | **T1 = `____` s** |
| **C2** `90000` | `SYS.PAK.c2_90000` | `21b32adf…` | `____` | `____` | **T2 = `____` s** |

> C1 and C2 rows without a confirmed `CreateFileA` are void. A null duration on an archive the
> game never opened says nothing about the tunable.

Repeat measurements, if taken (timing noise matters at short durations):

- C0: `____`  C1: `____`  C2: `____`

Anything unusual — stutter, a pause, the window losing focus, a crash: `____`

---

## 3. Ratios — divide, then read the bucket

| ratio | value |
|---|---|
| T1 / T0 | `____` |
| T2 / T0 | `____` |
| T1 / T2 | `____` |

Pre-registered buckets. No arithmetic beyond the three divisions above.

| T1/T0 lands near | reading |
|---|---|
| **0.15** (range ~0.10–0.25) | C1 unclamped, rate drives the scroll → **H1** |
| **1.00** (range ~0.9–1.1) | C1 had no effect → **H2** |
| anything else | unpredicted; do not explain it before re-reading `0x004293fd` |

| T2/T0 lands near | reading |
|---|---|
| **0.10** (range ~0.05–0.25) | C2 took effect, ceiling likely binding → **H1** |
| **1.00** (range ~0.9–1.1) | C2 had no effect → **H2** |

---

## 4. Which pre-registered outcome fired

Tick exactly one.

| | outcome | what it settles |
|---|---|---|
| ☐ | **T1 and T2 both far below T0** | **H1: the read works.** `ScrollRateInPixelsPerMinute` does drive the credit scroll; the 2026-08-17 null was an observer misjudgement of a 2.83x change. **Resolve U-051.** The standing lesson holds: never use a judged rate as a marker. |
| ☐ | **T1 ≈ T2 ≈ T0**, with `CreateFileA` confirmed on both | **H2: the config read fails or is bypassed** for `[CreditsTunables]`. A real finding about `FUN_00428801`'s config object; next step is `FUN_00486c5e`'s failure path. Would also mean the shipped INI value is decorative. |
| ☐ | **T1 ≈ T0 but T2 < T0** | Something binds between 9,999 and 90,000 that this reading does not predict. Re-read `0x004293fd` before explaining it. |
| ☐ | **T2 far below the ceiling's floor** (T2/T0 < 0.05) | The 4 px/frame ceiling reading is wrong. Re-read `[0x4e]`'s use in `0x004293fd`. |
| ☐ | C1 or C2 failed to boot | Report separately — C2 is +1 byte, so a C2-only boot failure implicates `build()`'s relayout on a **growing** archive. |

Selected: `____`

### 4b. Free bonus — the harness's real frame rate

Fill only if **T1 ≈ T2** (which means the ceiling bound both rungs).

The credits scroll a fixed distance `D`. From the control, `D = 25 × T0` px (shipped rate is
1500 px/min = 25 px/s). When clamped, speed is `4 px/frame × fps`, so:

```
fps  =  D / (4 × T1)  =  25 × T0 / (4 × T1)
```

- `D` = 25 × `____` = `____` px
- **fps** = `____`

Sanity, and note this is **narrower than it first looks**: `T1 ≈ T2` can only happen if the
ceiling bound C1 as well, and C1 asks for 9,999 px/min = 166.65 px/s, so the ceiling
(`4 × fps`) must be *below* that — i.e. **fps < 41.7**. A plausible answer is therefore roughly
20–42, not "any normal frame rate". If this formula yields something above ~42 the ceiling was
not actually binding on C1, which contradicts `T1 ≈ T2`; re-check §3's ratios rather than
trusting this number.

---

## 5. Verdict on U-051

**U-051:** `____`  (RESOLVED-H1 / RESOLVED-H2 / still open — and if open, what is missing)

`____`

---

## 6. Settled vs not settled

- **SETTLED:** `____`
- **NOT SETTLED:** `____`

Note explicitly: this test says nothing about T3, which `verify/tunable_mod_test/` closes
independently, and nothing about `MaxPixelsToScrollPerFrame`, which is **absent** from the
shipped file — adding it would be a different test.

---

## 7. Restore — confirm, do not assume

| check | expected | got |
|---|---|---|
| `certutil -hashfile "Apps\Sys\SYS.PAK" SHA256` | `172c02d9…` | `____` |
| `Apps\Sys\SYS.PAK.original` | must NOT exist | `____` |

---

## 8. Follow-ups

Trackers to update once §5 is decided: `UNCERTAINTIES.md` (U-051 status — it is the single
owner of this finding), and `ROADMAP.md`'s T3 section, which currently carries the corrected
`ScrollRate` note pointing here.

- `____`
