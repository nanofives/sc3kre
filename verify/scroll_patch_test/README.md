# scroll_patch_test — does a BINARY patch made with these tools change what the player sees?

The question `tunable_mod_test` answered for a shipped data file, asked again for a value that has
no data file. `T3` established that an INI tunable edited with `syspak_mod.py` reaches the running
game (`RESULTS.md`, 2026-08-19: `MaxAirPolluteForUI` flipped the tile-query panel from *Alta/High*
to *Peligrosa/Hazardous*). Every mechanism proven so far edits a **file the game parses**.

The camera has no such file. That is not an assumption; it is an exhaustive negative:

- **No INI or CFG key controls map scroll.** `SYS.PAK`'s 51 members contain no `Navigation`,
  `Scroll*`, `Camera`, `Zoom` or `EdgeScroll` key except `[CreditsTunables]
  ScrollRateInPixelsPerMinute`, which is the end-credits text crawl and is already disproven
  (`verify/tunable_mod_test/README.md:11-14` — 1500 → 4242, no effect, because `0x004293fd` ceils
  it every frame at a ctor-set 4).
- **`[Navigation] ScrollMarginFactor` in `Apps\SC3U.ini` is a decoy.** The strings `"Navigation"`
  @ `0x1007215c` and `"ScrollMarginFactor"` @ `0x10072170` exist in SIMSPR.DLL **and in no other
  shipped binary**, and exactly one function references them: `FUN_100440f4`
  [CONFIRMED @ `0x100440f4`], reached only from the teardown path `FUN_10047e6d:88`, and it
  **writes**. The value is literally `5.0f / window height` [CONFIRMED @ `0x100441a6`:
  `fdivr [0x10066500]` where `DAT_10066500` = `00 00 a0 40` = 5.0f; `5.0 / 0.006510 = 768.05`,
  and this install runs at 768). Nothing reads it back and the game overwrites it on exit.
- **No registry value either.** `re/analysis/REGISTRY_PORTABILITY.md` enumerates the complete
  registry surface: `Country, Language, User, Password, ergc, SKU` read, `EnableAutodial` written.

So the camera step is a **compiled-in literal**, and a byte patch is the only mechanism. This test
is the first thing in the project to make one, and the gate it opens is broader than the camera:
every hardcoded constant in every module becomes moddable if it passes.

## The marker and its evidence chain

`Apps\SIMSPR.DLL` `.rdata` `0x10067690`..`0x100676a0` — **five float32s, all shipped 32.0f.**
This module maps 1:1 (`--info`: every section's `va-base` equals its `raw`), so file offset =
VA − 0x10000000.

Every link was read directly in the export or in the file's bytes. None is inferred.

1. **Initialiser.** `FUN_100440b1` (67 bytes) [CONFIRMED @ `0x100440b1`] copies the bank into the
   `cSC3WinCityView` object (vtable `0x10067894`):

   ```
   +0x1dc <- DAT_100676a0   +0x1d8 <- DAT_1006769c   +0x1d4 <- DAT_10067698
   +0x1d0 <- DAT_10067694   +0x1cc <- DAT_10067690   +0x1c8 <- DAT_10067694
   ```

   Note the last line: **`+0x1c8` is initialised from `0x10067694` unconditionally**, so that slot
   is the construction default as well as a zoom slot.

2. **Selector.** `ZoomIn` [CONFIRMED @ `0x10042d8a`] re-picks `+0x1c8` by zoom index:
   `0 → +0x1dc`, `1 → +0x1d8`, `2 → +0x1d4`, `3 or other → +0x1d0`, `4 → +0x1cc`. Composing with
   step 1 gives the slot for each zoom level:

   | zoom | object field | `.rdata` VA | file offset |
   |---|---|---|---|
   | 0 | `+0x1dc` | `0x100676a0` | `0x676a0` |
   | 1 | `+0x1d8` | `0x1006769c` | `0x6769c` |
   | 2 | `+0x1d4` | `0x10067698` | `0x67698` |
   | **3 (and the default)** | `+0x1d0` / `+0x1c8` | **`0x10067694`** | **`0x67694`** |
   | 4 | `+0x1cc` | `0x10067690` | `0x67690` |

3. **Consumer.** The per-frame scroll tick `FUN_10043daf` [CONFIRMED @ `0x10043daf`] reads
   `param_1[0x72]` — `param_1` is `int*`, so byte offset `0x72 * 4 = 0x1c8`, the active step — and
   passes it to `Translate` (vtbl `+0x34`) as ±step on one or both axes. The **same** four
   direction flags are set by the arrow keys (VK `0x26`/`0x28`/`0x25`/`0x27`, polled through
   `param_1[0x84]` vtbl `+0xc`) and by edge-scroll. One step, no acceleration, no ramp, no
   delta-time scaling.

4. **The boundary of the float run was checked, not assumed.** `0x100676a4` is 12.0f and
   `0x100676a8` is 80.0f (the mouse-drag dead zone and clamp), and `0x100676ac` is **not a float**
   — it reads `29 ad 04 10`, the pointer `0x1004ad29`. So the bank is exactly five floats.

### Why this cannot repeat the credits failure

`ScrollRateInPixelsPerMinute` was read into `param_1[0x4c]` and then **discarded downstream** by a
per-frame ceil. `+0x1c8` has no clamp between the `.rdata` load and `Translate`: `FUN_10043daf`
passes it straight through. It is the argument itself.

### The built-in negative control

Mouse right-drag pan does **not** use `+0x1c8`. `FUN_10043daf`'s `+0x1e6 != 0` branch passes
`param_1[0x7d]`/`[0x7e]` (= `+0x1f4`/`+0x1f8`), computed separately in `UpdateScroll`
[CONFIRMED @ `0x10043a38`] as `(anchor − mouse) / −2` with a 12.0f dead zone and an 80.0f clamp.

**That separation is free and it is what makes a zero-step observation interpretable:** if the
step is 0 and right-drag still pans the map, the client is running and reading input, so "the map
did not move" cannot be a frozen or hung game. No other test in this project has had a negative
control that sits inside the same function as the marker.

## The ladder

One variable per rung, as in `city_load_test` and `tunable_mod_test`. **Run S1 first.**

| rung | file | what differs from shipped | what it establishes / what a failure would prove |
|---|---|---|---|
| **S1** | `SIMSPR.DLL.S1_all_zero` | all five steps 32.0f → 0.0f. **5 bytes, 5 runs**, same length (512,000). | The mechanism. Arrow keys and edge-scroll dead at every zoom, right-drag still works. A failure means either the patch does not reach the game or `+0x1c8` is not what feeds `Translate` — and it cannot be a tool fault, because the file is shipped-identical apart from 5 bytes. |
| **S2** | `SIMSPR.DLL.S2_zoom3_zero` | only `0x67694` (zoom 3 + construction default) → 0.0f. **1 byte.** | The selector. Arrows dead at *one* zoom level and working at the others localises which `.rdata` slot the live zoom uses — the per-zoom claim that step 2's table makes. |
| **S3** | `SIMSPR.DLL.S3_zoom4_zero` | only `0x67690` (zoom 4) → 0.0f. **1 byte.** | Whether **zoom 4 is reachable at all**, which is currently open. `re/tools/sprite_patch.py`'s object index found sprite instances only at zoom 0..3, and the colour-index probe at max zoom read `0x000C` = zoom 3. If S3 changes nothing at any zoom while S2 changes one, zoom 4 is internal-only. |

S3 is the rung that answers the address the work started from (`0x67690`). It is deliberately
**last**, because it is the one whose null result is ambiguous on its own and only becomes
informative once S1 and S2 have fixed the mechanism and the selector.

## Provenance and integrity

Built from `Apps\SIMSPR.DLL` on 2026-08-20, verified at the shipped anchor
`eec71500…` first. Nothing under `Apps\` was modified to produce them. Hash every file before you
load it rather than trusting a filename; full list in `MANIFEST.txt`.

The tool is `re/tools/pe_patch.py`, new for this test and built to the same bar as the rest of the
toolkit rather than as a one-off script in this directory (the debt `syspak_mod.py` had to be
promoted out of `tunable_mod_test/build_mod.py` to clear). Its four invariants — declared expected
bytes, same length, never writes the input, re-derivable diff — and the reasoning are in its
docstring. `--selftest` is **23/23 on `Apps\SIMSPR.DLL` and 23/23 across all 36 PEs in `Apps\`**,
including identity build byte-identical on all 36, and it re-reads every constant this README
cites out of the file instead of trusting the prose.

**The selftest already earned its keep.** The first edge-margin address table was a list of
*instruction start* VAs (`0x10043992`, …); `--expect` refused it because `0x10043992` holds `0x8d`,
the `lea` opcode, not 48. The displacement byte is instruction start + 2. The eight sites were then
re-derived by scanning `0x43989..0x43a38` for `8d` with `mod=01`, which finds exactly eight. That
is invariant 1 catching a wrong address before it reached a file, which is the entire reason it
exists.

Reproduce the three files with:

```
py -3.12 re/tools/pe_patch.py Apps/SIMSPR.DLL --recipe scroll_zero         --out verify/scroll_patch_test/SIMSPR.DLL.S1_all_zero
py -3.12 re/tools/pe_patch.py Apps/SIMSPR.DLL --recipe scroll_default_zero --out verify/scroll_patch_test/SIMSPR.DLL.S2_zoom3_zero
py -3.12 re/tools/pe_patch.py Apps/SIMSPR.DLL --set 0x10067690:f32=0.0 --expect 32.0 --out verify/scroll_patch_test/SIMSPR.DLL.S3_zoom4_zero
```

Independent re-diff (does not trust the code that wrote the files):

```
py -3.12 re/tools/pe_patch.py Apps/SIMSPR.DLL --diff verify/scroll_patch_test/SIMSPR.DLL.S1_all_zero
```

S1 reports 5 runs / 5 bytes at `0x67693 0x67697 0x6769b 0x6769f 0x676a3` — one byte per float, the
high byte, since `00 00 00 42` → `00 00 00 00` differs in one place. S2 reports `0x67697` only;
S3 reports `0x67693` only.

## What each outcome means, written down BEFORE running

Committing in advance is the point; otherwise any result can be rationalised afterwards.

**PREDICTION (S1).** With S1 staged, in a loaded city: pressing any arrow key produces **no map
movement**, and pushing the cursor into any screen edge produces **no map movement**, at every
zoom level. Holding the **right mouse button and dragging still pans the map normally**. Zoom in,
zoom out and rotate all still work, because `ZoomIn`/`ZoomOut`/`Rotate*` do not read `+0x1c8` for
their own motion — they only re-select it.

**PREDICTION (S2).** Arrows and edge-scroll are dead at exactly one zoom level and work normally at
the others. If the game's zoom index is 3 on entry, they are dead immediately on load.

**PREDICTION (S3).** Unknown by design, and both answers are results. Dead at some zoom level →
zoom 4 is reachable and the table in step 2 is complete. Dead at none → zoom 4 is internal-only,
which agrees with the sprite-side evidence and means `0x67690` is **not** a slot a player ever
experiences.

> ### AMENDMENT, 2026-08-20 — added BEFORE any run, and it prevents a FALSE POSITIVE
>
> Recorded as an amendment rather than edited into the text above, because the point of a
> pre-registration is that you can see what changed and when. **No prediction is altered.**
>
> **A SHIPPED-SIMSPR CONTROL RUN IS NOW MANDATORY, and it must come first.** An offline re-read
> found a gate that makes "arrows did nothing" ambiguous on its own:
>
> `FUN_10043daf` polls the arrow keys only inside `if (*(char *)(param_1 + 0x177) != '\0')`, and
> the same flag gates the edge-scroll branch (`:42`) and `UpdateScroll`'s (`0x10043a38:19`).
> Exhaustive grep over the SIMSPR export: `+0x177` has **exactly two writers** —
> `SetEdgeScroll` [CONFIRMED @ `0x10042cd3`], which is `cSC3WinCityView` vtable slot 14 and also
> clears all four direction flags when passed 0, and `0x100484c2:60`, which sets it to **0**.
>
> So **arrow-key and edge scroll are OFF until something calls slot 14 with a non-zero argument.**
> No static caller is visible, because slot 14 is reached by vtable dispatch — the same
> data-driven-at-runtime situation as the `0xC2DCC228` message id in `tunable_mod_test`. In normal
> play something clearly sets it (the game scrolls with arrows), most plausibly a focus or
> activate handler. **In a headless run with no real window focus it may never be set**, in which
> case arrows would be dead on the *shipped* DLL too, and reading that as an S1 pass would be
> exactly the kind of self-deception this directory exists to prevent.
>
> **Therefore, before staging anything:** run the full observe procedure on the **unmodified**
> `Apps\SIMSPR.DLL` and confirm that step 6's two captures **DIFFER** — that arrows do move the
> map under the harness. If they do not, S1 is not runnable as written and the finding to record
> is about `+0x177`, not about the patch. In that case the drag-only routes remain available
> (`drag_divisor`, dead zone, clamp), since `UpdateScroll`'s mouse branch is reached through
> `+0x1e6`, not `+0x177`.
>
> **Second thing settled offline, and it de-risks the run.** The arrow-key poll bottoms out in a
> hookable Win32 call, so this is drivable rather than requiring a real keyboard:
> SIMSPR calls `(**(code **)(*(int *)param_1[0x84] + 0xc))(0x26)`; **SIMSPR does not import any
> key-state API** (checked against all 36 PE import tables in `Apps\` — only `GZWIND.DLL`,
> `GZGraphicD.dll` and `SC3U.exe` do). The slot-`+0xc` target is GZWIND vtable `0x1002e130`,
> whose `+0xc` is `FUN_10025790` [CONFIRMED @ `0x10025790`] — 19 bytes, `return
> GetAsyncKeyState(param_1) >> 0xf;`.
>
> `re/harness/src/sc3probe.c` **already IAT-hooks `GetAsyncKeyState` and `GetKeyState`** and fakes
> `VK_LBUTTON` for `-clicks`. Two changes make arrow keys drivable: hook **GZWIND.DLL's** IAT
> rather than only the exe's (`iat_hook(exe, ...)` at `:602-603` is exe-only, and the call site is
> in GZWIND), and extend the faked set past `VK_LBUTTON` to `0x25`/`0x26`/`0x27`/`0x28` on a
> scheduled window. Neither is done yet, and **the run is blocked on it.**

Outcomes and what each one licenses:

- **S1: arrows and edges dead, right-drag works → the mechanism is PROVEN.** A binary patch made
  with these tools changes what the player sees. This promotes `0x100440b1`, `0x10042d8a` and
  `0x10043daf` to a confirmed behavioural witness (**C3**), and `pe_patch.py` to a proven write
  path. Every compiled-in constant in every module becomes moddable from here.
- **S1: arrows and edges dead AND right-drag also dead.** Do not read this as success. It is
  consistent with a hung client. Check the log for progress after the last frame and re-run;
  right-drag is the discriminator and it must be positive for S1 to count.
- **S1: nothing changed, and the log shows the game loaded our `SIMSPR.DLL`.** The tool is
  exonerated by the 5-byte diff and the finding is about the consumer: `+0x1c8` is not the value
  `Translate` receives, or something writes `+0x1c8` after construction that the export does not
  show. Log an `[UNCERTAIN]` and look for a second write site. **Re-diff the staged file before
  concluding anything** — the `ARM3_RESULTS.md` method rule.
- **S1: nothing changed and the log shows no load of our DLL.** Staging failed. Not a result;
  re-stage and re-run.
- **S1: the game fails to start or crashes on load.** The most informative failure available,
  because the file is shipped-identical apart from 5 bytes in `.rdata` with no length change: it
  would mean a 0.0f step destabilises SIMSPR, which is a finding about the game and not the
  toolkit. Try `scroll_speed=1` instead of 0 before drawing any conclusion.
- **Any rung: the observer could not tell.** Not a result. The observation must be a read-off (see
  below), not a judgement of speed — that rule is inherited from the credits failure.

## What this cannot tell you

It settles one binary question: whether a byte patch made with `pe_patch.py` reaches the running
game and changes what the player sees. It says nothing about the *other* camera knobs (drag
divisor, dead zone, clamp, edge margins), nothing about patching `.text` rather than `.rdata`
(all three rungs are `.rdata`; the `drag_divisor` and `edge_margin` recipes are `.text` and are
**untested game-side**), and nothing about the diagonal 1.41× over-speed, which needs code
injection and is deliberately outside this tool.

## The state of the install RIGHT NOW

**Nothing is staged.** Verified 2026-08-20 before the build:

```
Apps\SIMSPR.DLL           eec71500…   512,000 bytes   (shipped anchor)
Apps\SIMSPR.DLL.original  absent
```

## How to run it

One rung at a time. The point of a ladder is knowing which rung broke.

### Stage

```
move "Apps\SIMSPR.DLL" "Apps\SIMSPR.DLL.original"
copy "verify\scroll_patch_test\SIMSPR.DLL.S1_all_zero" "Apps\SIMSPR.DLL"
certutil -hashfile "Apps\SIMSPR.DLL"          SHA256   :: 1d4e886a…
certutil -hashfile "Apps\SIMSPR.DLL.original" SHA256   :: eec71500…
```

The shipped DLL is moved aside, never overwritten.

### Launch

```
re\harness\bin\sc3launch.exe -nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace -log "re\harness\s1run.log"
```

Every flag is load-bearing per `re/analysis/LAUNCH_CONTROL.md`: `-nocom` and `-fix16` are what make
the client render at all, `-quiet` disables the probe framebuffer sampling that caused the ~35 s
crash in the T1 run, `-filetrace` is the machine-checkable proof the game loaded our DLL. Do
**not** add `-r800x600` (§29.1 — crashes with `0xC0000409`).

### Observe — as a read-off, not a judgement

The credits failure is the reason this is prescriptive. "Did it feel slower?" is not admissible.

1. Load any city.
2. **Before interpreting anything**, confirm in `s1run.log` that `FILETRACE` shows the load of
   `Apps\SIMSPR.DLL`.
3. Capture the framebuffer (`re\harness\capture.ps1`).
4. Press and hold `Left Arrow` for ~2 seconds. Release.
5. Capture again.
6. **Compare the two captures byte for byte.** Identical → the map did not move. That is the
   read-off; no opinion about speed is involved. On shipped SIMSPR the same sequence moves the map
   by many tiles and the two captures differ in most of the client area.
7. **Now the negative control, and do not skip it.** Right-click-drag the mouse across the client,
   capture again, and confirm this capture **differs** from the previous one. If it does not, the
   client is not responding and step 6 proves nothing.
8. Repeat 3–6 with the cursor parked hard against the left screen edge instead of the arrow key.
9. Zoom out one level and repeat 3–6, so the claim covers more than one zoom slot.

Record what was seen **before** interpreting it, in `RESULTS.md`.

### Then S2, then S3

Restore first (below), then repeat the whole stage/launch/observe cycle. **One rung at a time —
never two staged at once.** For S2 and S3, step 9 stops being optional: the whole claim is *which*
zoom level went dead, so walk every zoom level available and record the arrow-key result at each.

### UNDO

Do this even if the run crashed.

```
del  "Apps\SIMSPR.DLL"
move "Apps\SIMSPR.DLL.original" "Apps\SIMSPR.DLL"
certutil -hashfile "Apps\SIMSPR.DLL" SHA256    :: must be eec71500…
```

`SIMSPR.DLL.original` must no longer exist afterwards, and the hash must be the shipped anchor.

## After it passes: the actual mod

S1 proving the mechanism is what makes a *usable* sensitivity mod a one-liner, since the value is
a plain float and all five slots are independent:

```
:: half speed everywhere
py -3.12 re/tools/pe_patch.py Apps/SIMSPR.DLL --recipe scroll_speed=16 --out SIMSPR.slow.dll

:: double speed everywhere
py -3.12 re/tools/pe_patch.py Apps/SIMSPR.DLL --recipe scroll_speed=64 --out SIMSPR.fast.dll

:: what the shipped binary never does -- make scroll speed track the zoom level
py -3.12 re/tools/pe_patch.py Apps/SIMSPR.DLL --recipe scroll_speed=z0:8,z1:16,z2:32,z3:64,z4:96 --out SIMSPR.perzoom.dll
```

The last one is worth stating plainly: **all five slots ship 32.0f**, so zoom currently has no
effect on scroll speed at all. The per-zoom bank exists in the code and is unused in the data.
