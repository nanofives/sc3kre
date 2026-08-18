# tunable_mod_test — does a tunable edit made with these tools change what the player sees?

Roadmap gate **T3**: *one change, made with these tools, visible in the running game.*

Everything else about the toolkit is now proven. T1 established the game loads files this
project wrote, including our QFS compressor's output and a one-tile zone edit
(`verify/city_load_test/RESULTS.md`). T2 established every shipped format has a byte-identical
writer with a `--selftest`. ARM3 established the `SYS.PAK` writer game-side: the game opens an
archive we wrote and boots on it (`verify/loose_file_test/ARM3_RESULTS.md`).

What is **not** established is that an edit we make *changes the game's behaviour*. The one
attempt failed: `[CreditsTunables] ScrollRateInPixelsPerMinute` 1500 → 4242 produced no visible
effect, while a byte diff proved the archive differed from shipped by exactly the 4 digit bytes.
The writer was sound; the premise was wrong.

**That failure is the reason this test picks its marker differently.** The rule adopted from it:
the marker must be a value whose consumer is *traced in the decompilation*, and it should change
a **word on a panel** rather than a rate a human has to judge, so the observation is a read-off
and not an opinion.

## The marker and its evidence chain

`SC3Pollution.ini`, section `[TuningParameters]`, key `MaxAirPolluteForUI`, shipped value `11000`.

Every link below was read directly in the export. None is inferred.

1. **Loader.** `re/ghidra_export_simeco/functions/100046bb_FUN_100046bb.c`
   - `:396` references the literal `MaxAirPolluteForUI` (`s_MaxAirPolluteForUI_10020324`)
   - `:414` `DAT_1002025c = FUN_10012ad7(local_4c);` — the parsed value lands in a module global
2. **Consumer.** `0x1000c95c` (SIMECO), the tile-query text builder. In its `param_5 == 3`
   (air) branch it emits label instance `0x187`, then bands the tile's air value — read from
   `local_14[7] + 0x58` — against `DAT_1002025c`
   (`re/ghidra_export_simeco/functions/1000c95c_FUN_1000c95c.c:604-769`).
3. **Strings.** Each branch selects an instance from IXF group `0x82e0074c`, resolved per
   language in `re/data/ixf_text.csv`.

| tile air value | branch line | instance | English-UK | ES |
|---|---|---|---|---|
| `== 0` | 630 | 0x188 / 392 | None | Nula |
| `< max >> 3` | 652 | 0x189 / 393 | Low | Baja |
| `< max >> 2` | 674 | 0x18a / 394 | Medium | Media |
| `< max >> 1` | 696 | 0x18b / 395 | High | Alta |
| `< (max << 2) / 5` | 718 | 0x18c / 396 | Very High | Muy Alta |
| else | 740 | **0x18d / 397** | **Hazardous** | **Peligrosa** |

Six code branches, six shipped strings, in order. The top branch also sets the caller's
out-flag (`*param_6 = 1`), the same "hazardous" signal.

**Why this one cannot repeat the credits failure.** `ScrollRateInPixelsPerMinute` fed
`param_1[0x4c]`, which `0x004293fd` then **ceils every frame** at `param_1[0x4e]`; the ctor
`0x004286d7` sets that to `4`, and `MaxPixelsToScrollPerFrame` is absent from the shipped INI, so
the value was read and then discarded downstream. `DAT_1002025c` has no clamp between the INI and
the comparison — **it is the comparand itself.**

## The ladder

One variable per rung, as in `city_load_test`.

| rung | file | what differs from shipped | what a FAILURE here would prove |
|---|---|---|---|
| **M1** | `SYS.PAK.m1_samelen` | `MaxAirPolluteForUI` `11000` → `00008`. **3 bytes, 2 runs, same total length (272,507).** | The game boots but the panel is unchanged → `0x1000c95c` is not what feeds this panel, or `DAT_1002025c` is overwritten after load. Cannot be a writer fault: the archive is shipped-identical apart from 3 digit bytes. |
| **M2** *(optional)* | `SYS.PAK.m2_shorter` | `11000` → `8`. **-4 bytes; 9,324 diff runs, 80,827 bytes**, because every record and TOC offset shifts. | The game fails to boot on M2 while M1 booted → a real defect in `build()`'s offset recomputation, which no test has exercised game-side. |

**Run M1 first.** M2 is a bonus claim (that the game accepts an archive we re-laid-out) and is
not required for T3.

`00008` is used rather than `8` so M1 keeps the archive length and layout identical, which
preserves the ARM3 diagnostic. **Leading zeros are safe, and this was read rather than assumed:**
`FUN_10012ad7` @ `0x10012ad7` is a radix *chooser* — `0x`/`0X` prefix → `strtoul` radix 16; any
`a-f`/`A-F` anywhere in the string → radix 16; otherwise radix 10. It never uses radix 8. So
`"00008"` → `strtoul(s, NULL, 10)` = **8**.

With `max = 8` the thresholds collapse from `1375 / 2750 / 5500 / 8800` to **`1 / 2 / 4 / 6`**.

## Provenance and integrity

Both archives were built from `Apps\Sys\SYS.PAK` on 2026-08-18, verified at the shipped anchor
`172c02d9…` first. Nothing under `Apps\` was modified to produce them. Hashes, exact diff offsets
and the full assertion list are in `MANIFEST.txt`; hash every file before you load it rather than
trusting a filename.

They were originally produced by a one-off `build_mod.py` in this directory. That script has been
**promoted into the library** as `re/tools/syspak_mod.py`, so there is one implementation instead
of a copy per experiment — the same debt `.IXF` had before `ixf_parse.py` absorbed its writer. The
move was checked rather than assumed: the tool regenerates both archives **byte-identically**
(`e9709032…` and `2b89839c…`). Reproduce them with

```
py -3.12 re/tools/syspak_mod.py Apps/Sys/SYS.PAK --set "SC3Pollution.ini:TuningParameters:MaxAirPolluteForUI=8" --pad --out verify/tunable_mod_test/SYS.PAK.m1_samelen
py -3.12 re/tools/syspak_mod.py Apps/Sys/SYS.PAK --set "SC3Pollution.ini:TuningParameters:MaxAirPolluteForUI=8"       --out verify/tunable_mod_test/SYS.PAK.m2_shorter
```

`--pad` is what makes M1 same-length: it left-pads `8` to `00008`.

Offline assertions that passed for both: `build()` and `replace_member()` agree byte for byte on
the same edit; re-parse gives 51 members with names and order unchanged; **exactly one** member's
content differs, checked by comparing all 51 members' line lists rather than by trusting the
diff. `build_mod.py --selftest` checks the diff routine itself against 7 hand-computed cases → 7/7.

## What each outcome means, written down BEFORE running

Committing to the interpretation in advance is the whole point, otherwise any result can be
rationalised after the fact.

**PREDICTION.** With M1 staged, querying a tile that on the shipped archive reads a middle band
(**Low / Medium / High** — any developed tile near industry or a busy road) will instead read the
**last band: Hazardous / Peligrosa**. A tile reading **None** stays **None**, because the `== 0`
branch is tested before any threshold and does not depend on `max`.

- **A tile that read a middle band now reads the last band → T3 IS MET.** One change, made with
  these tools, visible in the running game. Close the gate. This also promotes `0x100046bb` and
  `0x1000c95c` to a confirmed behavioural witness (C3 evidence).
- **The panel is unchanged, and `FILETRACE` shows the game opened our archive.** The writer is
  again exonerated by the 3-byte diff, and the finding is about the consumer: log a new
  `[UNCERTAIN]` recording that `0x1000c95c` is falsified as the source of this panel's air line,
  and look for a second banding site. **Do not conclude anything before re-diffing the staged
  archive against shipped** — the `ARM3_RESULTS.md` method rule.
- **The panel is unchanged and `FILETRACE` shows no `CreateFileA` on our archive.** Staging
  failed. Not a result; re-stage and re-run.
- **The game fails to boot on M1.** The most informative failure available here, because M1 is
  shipped-identical apart from 3 digit bytes — it would mean the value itself destabilises
  SIMECO, which would be a finding about the game, not the toolkit.
- **Every tile reads None.** The observer sampled undeveloped tiles. Not a result; re-observe on
  a developed city near industry.

## What this cannot tell you

It settles one binary question: whether a tunable edit made with this toolkit reaches the running
game and changes what the player sees. It does **not** tell you that the *simulation* consumes
`MaxAirPolluteForUI` (the name and the code both say it is a UI display scale only), nor anything
about the other 50 members, nor about formats outside `SYS.PAK`.

## The state of the install RIGHT NOW

**Nothing is staged.** Verified before the build:

```
Apps\Sys\SYS.PAK          172c02d9…   272,507 bytes   (shipped anchor)
Apps\Sys\SYS.PAK.original absent
loose .ini in Apps\Sys\   0
```

The change this test stages is deliberately harmless: it scales a **display band** for the tile
query panel and is fully reverted by restoring the archive.

## How to run it

One rung at a time. The point of a ladder is knowing which rung broke.

### Stage

```
move "Apps\Sys\SYS.PAK" "Apps\Sys\SYS.PAK.original"
copy "verify\tunable_mod_test\SYS.PAK.m1_samelen" "Apps\Sys\SYS.PAK"
certutil -hashfile "Apps\Sys\SYS.PAK"          SHA256   :: e9709032…
certutil -hashfile "Apps\Sys\SYS.PAK.original" SHA256   :: 172c02d9…
```

The shipped archive is moved aside, never overwritten.

### Launch

```
re\harness\bin\sc3launch.exe -nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace -log "re\harness\t3run.log"
```

Every flag is load-bearing per `re/analysis/LAUNCH_CONTROL.md`: `-nocom` and `-fix16` are what
make the client render at all, `-quiet` disables the probe framebuffer sampling that caused the
~35 s crash in the T1 run, `-filetrace` is the machine-checkable proof the game read our archive.
Do **not** add `-r800x600` (§29.1 — crashes with `0xC0000409`).

### Observe

1. Load any developed city with industry.
2. **Before interpreting anything**, confirm in `t3run.log` that `FILETRACE` shows
   `GetFileAttributesA` → exists and `CreateFileA` → ok on `Apps\Sys\SYS.PAK`.
3. Use the tile query tool on a tile beside industry or a busy road.
4. Read the **air pollution** line and record the word verbatim.
5. Useful control, free: query an empty tile far from development. It should still read the
   first band (None / Nula).

Record what was seen **before** interpreting it, in `RESULTS.md`.

### Then M2, as a second staged run

Restore first (below), then repeat the whole stage/launch/observe cycle with
`SYS.PAK.m2_shorter` in place of `SYS.PAK.m1_samelen`. **One rung at a time — never both.**

M2 carries the *same* tunable edit, so its pollution-band prediction is identical to M1's. What
it adds is a second, independent claim: **the game boots and runs on an archive whose layout our
`build()` recomputed.** M2 is 4 bytes shorter than shipped, which shifts every subsequent record
and every TOC offset by `-4` (verified offline: 9,324 diff runs, and the spot-checked offsets
each moved by exactly 4).

Pre-registered, before the run:

- **M2 boots and the panel matches M1 → `build()`'s relayout is validated game-side.** That is a
  claim nothing has tested: ARM3 only ever exercised a same-length edit, so every archive the
  game has accepted from us so far had shipped-identical offsets.
- **M1 booted but M2 does not → a real defect in `build()`'s offset table**, isolated to the
  relayout path, since the two archives differ in nothing else. This is the informative failure
  and it would matter well beyond this test: every future multi-key or key-adding edit goes
  through the same path.
- **M2 boots but the panel differs from M1's** → the two archives disagree despite carrying the
  same edit, which would point at the relayout corrupting a *different* member. Re-parse both and
  diff member by member.

A companion test, `verify/credits_discriminator/`, exercises the opposite direction (an archive
one byte **longer** than shipped). Between them, both signs of relayout get covered.

### UNDO

Do this even if the run crashed.

```
del  "Apps\Sys\SYS.PAK"
move "Apps\Sys\SYS.PAK.original" "Apps\Sys\SYS.PAK"
certutil -hashfile "Apps\Sys\SYS.PAK" SHA256    :: must be 172c02d9…
```

`SYS.PAK.original` must no longer exist afterwards, and the hash must be the shipped anchor.
