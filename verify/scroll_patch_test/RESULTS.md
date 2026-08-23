# RESULTS — scroll_patch_test

## C0 — the shipped-SIMSPR control run (2026-08-20)

Run **before** staging anything, as the pre-run amendment in `README.md` requires. Nothing was
patched; `Apps\SIMSPR.DLL` was at the shipped anchor `eec71500…` throughout, verified before and
after.

**VERDICT: the control FAILS, exactly as the amendment feared, and S1/S2/S3 are NOT runnable as
written.** The function that reads the step bank never executes under the harness, so "arrows did
nothing" would have been a false positive. The run also produced the mechanism that makes a real
run possible, so the block is scoped rather than open-ended.

### What was observed

Method: `-modlog SIMSPR.DLL:<VA>` (LAUNCH_CONTROL §31.9.4), which installs the fnlog trampoline on
a late-loading module and reports hit counts, the caller's return address, `ecx`, and the first
stack args. Driver in every run:

```
$sw = '-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace -modlog SIMSPR.DLL:<VA>'
& re/harness/capture.ps1 -Name <n> -Switches $sw -GzSeq '0x712BF5BF;0x02DFDD6A;0xE2FA5BC2;wait:6000'
```

Recorded before interpreting:

| run | hooks | outcome |
|---|---|---|
| `scrollctl` | `0x10042cd3, 0x10043daf, 0x10043989` | all 3 installed at 104 ms, **process detach at 825 ms**, no frames, no shot |
| `baseline` | none | **sequence complete 13.7 s**, shot produced |
| `sc_edge` | `0x10042cd3` only | complete 13.9 s; **SetEdgeScroll hit 3×, every call `a1 = 0x00000000`** |
| `sc_tick` | `0x10043daf` only | complete 14.2 s; **scroll tick hit 0×** at 5.5 s, 11.0 s and 16.4 s |

The `baseline` run is what makes the first row a finding about the hooks rather than about the
game: the identical sequence completes without `-modlog`. By elimination against `sc_edge` and
`sc_tick`, which are both stable, **the destabilising hook is `0x10043989`** (the edge-rect
builder). Same class as the raster slot 3/4 detours recorded in LAUNCH_CONTROL §15.12 — do not put
`0x10043989` in a table used for normal runs.

### 1. `+0x177` is never enabled — it is set to 0, three times

`SetEdgeScroll` [CONFIRMED @ `0x10042cd3`] is `__thiscall(int this, char param_2)`, so `param_2` is
the first stack arg. All three hits:

```
### MODLOG SIMSPR.DLL!0x10042CD3 hit #1  <- called from SIMSPR.DLL+0x490CE  (ecx=0x12DA6710 a1=0x00000000 …)
### MODLOG SIMSPR.DLL!0x10042CD3 hit #2  <- called from SIMSPR.DLL+0x490CE  (ecx=0x12DA6710 a1=0x00000000 …)
### MODLOG SIMSPR.DLL!0x10042CD3 hit #3  <- called from SIMSPR.DLL+0x490CE  (ecx=0x12DA6710 a1=0x00000000 …)
```

Same caller and same object every time. `a1 = 0` means `+0x177 = 0`. **Nothing ever passes 1.**
The caller `SIMSPR+0x490CE` is inside `FUN_10048d7a` (`0x10048d7a`, 1180 bytes), a message
dispatcher switching on `*param_1`.

### 2. The consumer never runs at all — 0 hits

`FUN_10043daf` [CONFIRMED @ `0x10043daf`], the only reader of the active step `+0x1c8`, reported
**0 hits** at all three report points, including 6 s parked in a loaded city.

This is the stronger result and it subsumes the first. A patch to the step bank cannot have an
observable effect while its only consumer does not execute.

Cross-check that the 0 is real rather than a hook that failed to arm: `FUN_10043daf` itself calls
vtable slot `+0x38` on both of its branches, and slot `+0x38` **is** `0x10042cd3` — verified by
reading the `cSC3WinCityView` vtable out of the file:

| slot | +off | target |
|---|---|---|
| 13 | `+0x34` | `0x1004327d` `Translate` |
| **14** | **`+0x38`** | **`0x10042cd3` `SetEdgeScroll`** |
| 15 | `+0x3c` | `0x10042cfe` `SetMouseScroll` |
| 16 | `+0x40` | `0x10043a38` `UpdateScroll` |

So if the tick had been running per frame it would have produced thousands of `SetEdgeScroll(0)`
calls. It produced 3, all from a message dispatcher and none from the tick. **The two hooks agree.**

### 3. Why it does not run — read after the run, and it closes the loop

The tick has exactly one static caller, `FUN_10042a95:87`, and the call sits in an `else`:

```c
if ((((*(char *)(param_1 + 0x1e2) == '\0') && (*(char *)(param_1 + 0x1e0) == '\0')) &&
    (*(char *)(param_1 + 0x1df) == '\0')) &&
   ((*(char *)(param_1 + 0x1de) == '\0' && (*(char *)(param_1 + 0x1dd) == '\0')))) {
    /* ... hover / tile-coordinate readout ... */
} else {
    uVar1 = FUN_10043daf((int *)(param_1 - 4));      /* the scroll tick */
}
```

`FUN_10042a95`'s `param_1` is `this + 4` (note the `- 4` at the call), so those five offsets are
`+0x1e6`, `+0x1e4`, `+0x1e3`, `+0x1e2`, `+0x1e1` on the object — the mouse-scroll flag and the four
direction flags.

**So the scroll tick only runs when a direction flag is ALREADY set.** The `GetAsyncKeyState` poll
*inside* the tick is therefore a key-**repeat/hold** mechanism, not the trigger, and the earlier
reading of it as the entry point was wrong. Nothing polls the arrow keys while the map is idle.

### 4. The actual trigger, and the route to drive it

`FUN_1004979a` [CONFIRMED @ `0x1004979a`], 192 bytes, is the keydown handler and is the missing
link:

```c
undefined1 __thiscall FUN_1004979a(int *param_1, int param_2) {
  if (param_2 == 0x26 || param_2 == 0x28 || param_2 == 0x25 || param_2 == 0x27) {
    /* poll all four arrows through param_1[0x84] vtbl+0xc, store into +0x1e1..+0x1e3, +0x1e4 */
  }
  if (any of the four flags set) {
    (**(code **)(*param_1 + 0x38))(1);          /* SetEdgeScroll(1) -> +0x177 = 1 */
    (**(code **)(*param_1 + 0x3c))(0,0,0);
    (**(code **)(*param_1 + 0x50))(0,0,0);
    (**(code **)(*param_1 + 0x4c))(0);
  }
}
```

This is what sets `+0x177 = 1`, and it is the only thing that does so with a non-zero argument. It
takes a VK code, so it is a keydown entry point.

**It is `cSC3WinCityView` vtable slot 25 (`+0x64`).** Established by scanning the whole PE for the
pointer `0x1004979a`: exactly **one** occurrence, at `.rdata` `0x100678f8`, which is
`0x10067894 + 0x64`. No static caller exists in the decomp — dispatch only, the same
data-driven-at-runtime situation as the `0xC2DCC228` message id in `tunable_mod_test`.

So the corrected chain, end to end:

```
keydown (VK 0x25/0x26/0x27/0x28)
  -> cSC3WinCityView vtable slot 25 = FUN_1004979a
     -> GZWIND vtable 0x1002e130 slot +0xc = FUN_10025790 = GetAsyncKeyState(vk) >> 15
     -> sets +0x1e1..+0x1e4, and SetEdgeScroll(1) sets +0x177
  -> next frame FUN_10042a95 sees a flag set, takes the else branch
     -> FUN_10043daf reads +0x1c8  <-- THE PATCHED VALUE
        -> Translate(+-step, +-step)  (vtable slot 13, 0x1004327d)
```

### What this licenses, and what it does not

- **The pre-run amendment was correct and it prevented a false positive.** Had S1 been run first,
  arrows would have done nothing and the honest-looking conclusion would have been wrong.
- **No claim is made about the patch.** `pe_patch.py` is unaffected: it still passes 23/23 on all
  36 PEs, the three rungs still differ from shipped by exactly the bytes in `MANIFEST.txt`, and
  none of them was staged. The block is in the *driver*, not the tool and not the patch.
- **`0x10042cd3`, `0x10043daf`, `0x10042a95`, `0x1004979a` and vtable slots 13/14/15/16/25 are now
  runtime-witnessed** to the extent stated above: slot 14 observed called with 0, the tick observed
  *not* called, and the gating condition read from the decomp. The step bank itself remains
  **C2** — no behavioural confirmation yet.
- **Unchanged from the README:** nothing here says anything about the drag path, which is reached
  through `+0x1e6` and not `+0x177`. `UpdateScroll` (`0x10043a38`) is still the untested
  alternative route.

### Next step, now well-scoped

Two changes to `re/harness/src/sc3probe.c`, then re-run the control:

1. **Fake the arrow keys where they are actually read.** The probe already IAT-hooks
   `GetAsyncKeyState`/`GetKeyState` and fakes `VK_LBUTTON` for `-clicks`, but at `:602-603` it
   hooks the **exe's** IAT only. The read happens in **GZWIND.DLL**, which is the sole importer on
   this path (verified against all 36 PE import tables: only `GZWIND.DLL`, `GZGraphicD.dll` and
   `SC3U.exe` import a key-state API, and SIMSPR imports none). Hook GZWIND's IAT and extend the
   faked set to `0x25`/`0x26`/`0x27`/`0x28` on a scheduled window.
2. **Deliver the keydown.** `FUN_1004979a` is vtable slot 25 and has no static caller, so it needs
   a direct dispatch — which is machinery the probe already has in `-gzdirect` ("window id — call
   its `vt+0x1bc` down handler directly"). Generalising `-gzdirect` to an arbitrary slot and one
   integer argument makes this `slot 25, arg 0x25` on the resolved city-view window.

Both are additive and neither touches a patched binary. Until they exist, **do not stage S1.**

### Install state after the control

```
Apps\SIMSPR.DLL           eec71500…   512,000 bytes   (shipped anchor, unchanged)
Apps\SIMSPR.DLL.original  absent      (nothing was ever staged)
```

---

## C1 — the control PASSES once the keys are driven (2026-08-20)

Both probe changes made, `re/harness/src/sc3probe.c`. Still nothing staged; `Apps\SIMSPR.DLL` at
`eec71500…` before and after.

**VERDICT: the driver works, the gate opens, the scroll tick runs, and the step bank is readable
live. S1 is now runnable.** The blocking condition recorded in C0 is cleared.

### The measurement

```
$sw = '-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -modlog SIMSPR.DLL:0x10043daf'
& re/harness/capture.ps1 -Name sc_key4 -Switches $sw \
    -GzSeq '0x712BF5BF;0x02DFDD6A;0xE2FA5BC2;key:0x25,3000;wait:4000'
```

```
### GZKEY: treeWindow=0x12DAE87C (vt SIMSPR+0x676AC) -> primary=0x12DAE878 (vt SIMSPR+0x67894) OK
### GZKEY: cityView=0x12DAE878 vt=0x03397894  +0x177=0 (before)
### GZKEY: scroll step +0x1c8=32.000  bank z4=32.000 z3=32.000 z2=32.000 z1=32.000 z0=32.000
### GZKEY: vt+0x64(vk=0x25) = 0x0337979A -> returned 0x03397A01
### GZKEY: +0x177=1 (after), flags up/down/left/right = 1/0/1/0, holding 3000 ms
### MODLOG SIMSPR.DLL!0x10043DAF hit #1  <- called from SIMSPR.DLL+0x42ADC (ecx=0x12DAE878)
### MODLOG SIMSPR.DLL!0x10043DAF hit #2  <- called from SIMSPR.DLL+0x42ADC (ecx=0x12DAE878)
```

Four things are established, each a read-off rather than a judgement:

1. **`+0x177` goes 0 → 1.** The gate that C0 showed was never opened, opens. `SetEdgeScroll(1)` is
   reached exactly where the C0 analysis said it would be, from inside `FUN_1004979a`.
2. **The scroll tick runs.** `FUN_10043daf` went from **0 hits in 16 s** (C0) to hits at 8134 ms
   and 8235 ms, ~100 ms apart, called from `SIMSPR+0x42ADC` — inside `FUN_10042a95`, the one static
   caller. C0's causal account is confirmed by construction.
3. **The step bank reads 32.000 in the live object, all five slots.** This is the read-off channel
   for a patch and it now demonstrably works: it matches the shipped `.rdata` exactly, so a zeroed
   slot will show as `0.000` here. No detour needed — which matters, because a `-modlog` hook on
   `Translate` (`0x1004327d`) **kills the game** (measured; see the anomalies below).
4. **The subobject delta was verified at runtime, not assumed.** `0x12DAE87C − 4 = 0x12DAE878`, and
   the primary vtable there is `0x03397894` = module base `0x03330000` + `0x67894`.

### Two bugs found in my own changes, both by regression testing rather than by reading

Recorded because each was silent and would have been misattributed to the game.

- **A two-thread race made the game die at ~840 ms.** `keyhook_poll()` was reachable from the
  watcher thread and the gz init, guarded by a plain `if (flag) return; flag = 1;`. Both threads
  can pass it; the second `iat_hook()` then reads an IAT slot that *already* holds
  `h_GetAsyncKeyState` and stores it as the original, so the hook calls itself forever. Symptom: a
  clean `process detach` at ~840 ms with no frames — indistinguishable from a game problem.
  **Caught by re-running the known-good baseline sequence with the new probe and seeing it fail**,
  which is the only reason it was attributed correctly. Fixed with `InterlockedCompareExchange`
  plus a second guard that refuses to chain our own handler, and by removing the second call site.
- **The wrong vtable found nothing.** `cSC3WinCityView` is multiply inherited: the window tree
  holds the **cIGZWin subobject** (`SIMSPR+0x676AC`), not the primary (`SIMSPR+0x67894`). Matching
  the primary while walking the tree found nothing and the key step timed out and was skipped.
  Established by dumping the tree in a loaded city:
  `GZWIN id=0x6104489C vt=SIMSPR.DLL+0x676AC local=0,0,1024,768`. Note `0x676AC` is the address
  C0 called "not a float, it reads `29 ad 04 10` = pointer `0x1004ad29`" — correct that the float
  bank ends at `0x676a8`, wrong about what follows: it is the start of this second vtable.

### New harness capability

`-gzseq "key:VK[,HOLDMS]"` — hold an arrow key on the map view, headless. Locates the city view by
the cIGZWin vtable, asserts the primary subobject at `−4`, logs `+0x177` and the whole step bank
before and after, then dispatches primary vtable slot 25 with the VK while the faked key is held.
`GetAsyncKeyState`/`GetKeyState` are now also hooked in **GZWIND.DLL's** IAT, which is where the
map's poll actually reads (the pre-existing hook was exe-only and could never intercept it).

### Anomalies, recorded not explained

- **The `up` flag also reads 1** with only `VK_LEFT` (`0x25`) held, so the drive is up-left rather
  than pure left. `FUN_1004979a` polls all four arrows and only `0x25` was faked, so
  `GetAsyncKeyState(0x26)` returned pressed from the real call. Cause not established. It does not
  affect the S1 claim (both axes use the same `+0x1c8`), but a pure-axis drive would need the
  unheld arrows forced to 0 as well.
- **The run hangs after the post-action shot.** The log ends cleanly at `SHOT #2` (8404 ms) and the
  sequence never reports `COMPLETE`, so `capture.ps1` waits out its timeout. Data and screenshot
  are produced; the trailing `wait:4000` step does not finish. Not investigated.
- **Only 2 tick hits before the shot.** The shot is taken ~280 ms after the keypress, so this is
  consistent with a ~10 Hz tick, not with a stall — but total movement is ~2 steps, which is why
  the S1 read-off should be the step *value* and the tick *count*, not a pixel diff.
- **`-modlog` on `0x1004327d` (`Translate`) and on `0x10043989` (the edge-rect builder) each kill
  the game** on their own, at ~840 ms. `0x10042cd3` and `0x10043daf` are both stable. Same class as
  the raster slot 3/4 detours in LAUNCH_CONTROL §15.12. Do not put either in a run table.

### What S1 should now show (written before the S1 run below)

Unchanged predictions from `README.md`, plus one that is now machine-checkable and is the primary:

**`### GZKEY: scroll step +0x1c8=0.000  bank z4=0.000 z3=0.000 z2=0.000 z1=0.000 z0=0.000`**

with `+0x177` still going 0 → 1 and the tick still taking hits. That combination — gate open, tick
running, step 0.000 — is the whole claim in one log line, and it cannot be confused with a hung
client or an unopened gate, because both of those are separately visible in the same output.

---

## S1 — PASSES. A byte patch made with these tools reaches the running game (2026-08-20)

Staged per `README.md` (move aside, never overwrite), verified at both hashes before launching:

```
Apps\SIMSPR.DLL           1d4e886a…   (S1_all_zero)
Apps\SIMSPR.DLL.original  eec71500…   (shipped, moved aside)
```

Driver identical to the C1 control, so the only variable between the two runs is the 5 bytes:

```
$sw = '-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace -modlog SIMSPR.DLL:0x10043daf'
& re/harness/capture.ps1 -Name s1run -Switches $sw \
    -GzSeq '0x712BF5BF;0x02DFDD6A;0xE2FA5BC2;key:0x25,3000;wait:4000'
```

Recorded before interpreting. Sequence **complete after 12.6 s**, shot produced:

```
### GZKEY: treeWindow=0x12DAA4F4 (vt SIMSPR+0x676AC) -> primary=0x12DAA4F0 (vt SIMSPR+0x67894) OK
### GZKEY: cityView=0x12DAA4F0 vt=0x033A7894  +0x177=0 (before)
### GZKEY: scroll step +0x1c8=0.000  bank z4=0.000 z3=0.000 z2=0.000 z1=0.000 z0=0.000
### GZKEY: vt+0x64(vk=0x25) = 0x0338979A -> returned 0x033A7A01
### GZKEY: +0x177=1 (after), flags up/down/left/right = 1/0/1/0, holding 3000 ms
### MODLOG SIMSPR.DLL!0x10043DAF hit #1  <- called from SIMSPR.DLL+0x42ADC (ecx=0x12DAA4F0)
### MODLOG SIMSPR.DLL!0x10043DAF hit #2  <- called from SIMSPR.DLL+0x42ADC (ecx=0x12DAA4F0)
```

### Side by side with the control

| | C1 control (shipped) | S1 (patched) |
|---|---|---|
| step `+0x1c8` | **32.000** | **0.000** |
| bank z4/z3/z2/z1/z0 | 32.000 ×5 | **0.000 ×5** |
| `+0x177` before → after | 0 → 1 | 0 → 1 |
| scroll tick `FUN_10043daf` | hits | hits |
| boots, loads a city | yes | yes |
| sequence | complete | complete (12.6 s) |

**This is the pre-registered S1 prediction, met exactly.** The five `.rdata` floats we changed on
disk are the five floats the live object holds, and the tick that consumes them still runs.

### What this licenses

- **The mechanism is PROVEN: a binary byte patch made with `pe_patch.py` reaches the running game
  and changes the value the camera uses.** Every compiled-in constant in every module is now
  reachable for modding, not just values that live in a shipped data file. That is a strictly
  larger surface than T3 closed (`SYS.PAK` tunables and sprite archives).
- **`pe_patch.py` is a validated write path**, joining `city_write`, `syspak_mod` and
  `sprite_patch`. It is the first of them to operate on an executable.
- **The step bank is promoted C2 → C3.** `0x100440b1` (the initialiser), `0x10042d8a`'s zoom
  selector and `0x10043daf` (the consumer) now have a behavioural witness: the bytes at
  `0x10067690..0x100676a0` are observed arriving at `+0x1c8..+0x1dc` in a live `cSC3WinCityView`.
- **Both readings that could have faked a pass are separately excluded in the same output.** The
  gate still opens (so this is not a disabled input path) and the tick still runs (so this is not a
  hung client). That is why the C0 amendment insisted on the control first.

### What it does NOT establish

- **Not a pixel-level movement claim.** The step is 0.0 and the tick ran twice, so the map cannot
  have moved — but that is inferred from `Translate(0,0)`, not measured against a screenshot. A
  frame diff was not attempted: the two runs' cities differ in sim state, so an image comparison
  would not have been the clean read-off the step value is.
- **Nothing about the other knobs.** `drag_divisor` and `edge_margin` are `.text` patches and
  remain **untested game-side**; all three rungs here are `.rdata`.
- **S2 and S3 are still unrun.** S1 zeroed all five slots at once, so it says nothing about which
  slot a given zoom level selects, and nothing about whether zoom 4 is reachable.

### Install state after S1

Undo performed immediately after the run, per `README.md`:

```
Apps\SIMSPR.DLL           eec71500…   512,000 bytes   (restored to the shipped anchor)
Apps\SIMSPR.DLL.original  absent
```

---

## S2 and S3 — the ladder is complete (2026-08-20)

Each staged in turn per `README.md`, hashes verified before launching, undone immediately after.
Driver identical to C1 and S1 in all three runs, so the only variable is which byte is zeroed.

### The pair

| run | staged sha256 | bytes changed | `bank z4 z3 z2 z1 z0` | **active `+0x1c8`** |
|---|---|---|---|---|
| C1 control | `eec71500…` (shipped) | 0 | `32.000 32.000 32.000 32.000 32.000` | **32.000** |
| S1 | `1d4e886a…` | 5 | `0.000 0.000 0.000 0.000 0.000` | **0.000** |
| **S2** | `5fc8c020…` | **1** (`0x67697`) | `32.000` **`0.000`** `32.000 32.000 32.000` | **0.000** |
| **S3** | `3c8ebb81…` | **1** (`0x67693`) | **`0.000`** `32.000 32.000 32.000 32.000` | **32.000** |

Both booted, loaded a city, opened the gate (`+0x177` 0 → 1) and ran the tick, exactly as S1 did.

### What the pair establishes

1. **The patch is surgical.** In S2 exactly one bank slot reads `0.000` and the other four still
   read `32.000`; in S3 the complementary slot does. One byte on disk moves one float in the live
   object and nothing else — which no earlier rung showed, because S1 zeroed all five at once.

2. **The active slot at the live zoom is `0x10067694`, not `0x10067690`.** This is the
   discriminating result and it comes from the two runs *disagreeing* in the right place:
   zeroing the z3 slot drives `+0x1c8` to `0.000` (S2), while zeroing the z4 slot leaves it at
   `32.000` (S3). So the mapping composed offline from `FUN_100440b1` and `ZoomIn`'s selector —
   `3 or other → +0x1d0 ← 0x67694`, `4 → +0x1cc ← 0x67690` — is confirmed on the live path.

3. **`0x67690` is not the slot a player experiences at the default zoom.** That is the address this
   whole task started from, and the sprite-side evidence (object index finding zoom 0..3 only, the
   colour probe reading `0x000C` = zoom 3 at max zoom) pointed the same way. Making S3 the last
   rung rather than the first was the right call: on its own, `bank z4=0.000` with no visible
   change would have looked like a failed patch instead of a correct patch on an inactive slot.

### What S3 does NOT establish

**It does not show that zoom 4 is unreachable** — only that it is not the *active* zoom on city
entry. Distinguishing "internal-only" from "reachable but not the default" needs a zoom driver
(`ZoomIn`/`ZoomOut` are `cSC3WinCityView` vtable slots 9/10, `0x10042d8a`/`0x10042f27`, so the
`-gzseq` slot-dispatch route already built for `key:` would reach them). Left undone; the claim
above is limited to the default zoom.

### Two anomalies resolved, one new

- **The `up`-flag anomaly did NOT recur.** S2 and S3 both logged
  `flags up/down/left/right = 0/0/1/0` — pure `VK_LEFT`, as intended. C1's `1/0/1/0` was a
  transient real key state on the machine, not a systematic fault in the drive. Withdrawn as a
  concern.
- **The post-shot hang did not recur** either: S1, S2 and S3 all reported `sequence complete`
  (12.6 s, 11.7 s, 12.6 s). C1's hang was not reproduced and is not a property of the `key:` step.
- **NEW: an early exit hit S2 on its first attempt** — `process detach` at 839 ms. It is **not**
  attributable to S2: the death is long before a city loads (~8 s) and before the city view object
  exists, so no scroll value can be implicated. A straight re-run with the identical staged file
  and identical command completed in 11.7 s.

> ### CORRECTION, 2026-08-21 — the ~840 ms exits were misdiagnosed
>
> This file originally called those exits "the pre-existing intermittent early clean-exit" and
> drew the rule *"a single early-exit run is not a result — re-run before interpreting"*. The rule
> is useful but the **explanation was wrong**, and the right one is far more actionable.
>
> Per the windowed-resize session: SC3U has a **single-instance handoff** at `FUN_0040496d` — a
> mutex plus `FindWindowExA` on `"Gonzo"` / `"SimCity 3000"`. When another SC3U is already
> running, a new launch takes that path and **exits with code `0xFFFFFFFF` at about 840 ms,
> writing no crash dump.**
>
> That matches every early exit recorded in this document — 825, 828, 835, 839, 840, 844 ms — and
> I had **repeatedly observed leftover SC3U processes** during these sessions (pids 17388, 14632,
> 30520, and once a full `sc3launch -> Apps\SC3U.exe` tree alongside my own launch). Some of those
> leftovers were another session's, not mine.
>
> **The corrected rule: an early exit with no crash dump means "check for another SC3U", not
> "my patch is broken" and not "flaky game".** Check before launching, and check by
> `StartTime`/parent, not by image name.
>
> **What this does NOT change.** The four passing rungs (C1/S1/S2/S3) all completed normally and
> their read-offs stand on their own output; nothing about them rests on interpreting an early
> exit. **What it weakens:** the C1 attribution of the ~840 ms deaths to my own `keyhook_poll`
> two-thread race. That race was a **real defect** — non-atomic claim, `iat_hook` chaining our own
> hook, genuine infinite recursion — and fixing it was correct. But the evidence I gave for it
> causing *those specific deaths* was a three-run A/B (old probe pass, new probe fail, fixed probe
> pass), and that A/B could have been confounded by a foreign SC3U appearing and disappearing. The
> defect is confirmed by inspection; its causal link to those timings is **downgraded to
> [UNCERTAIN]**.

### Install state after the ladder

```
Apps\SIMSPR.DLL           eec71500…   512,000 bytes   (restored to the shipped anchor)
Apps\SIMSPR.DLL.original  absent
```

### Ladder status

| rung | result |
|---|---|
| C0 control (no drive) | consumer never runs — false-positive trap caught |
| C1 control (with drive) | **PASS** — gate opens, tick runs, bank reads 32.000 |
| S1 all five zeroed | **PASS** — mechanism proven, step bank C2 → C3 |
| S2 z3 slot zeroed | **PASS** — patch is surgical; active slot is `0x67694` |
| S3 z4 slot zeroed | **PASS** — active slot is not `0x67690` |

Untested game-side, unchanged: the `.text` recipes (`drag_divisor`, `edge_margin`), the drag path
via `UpdateScroll`, and whether zoom 4 is reachable at all.

---

## S1 re-measured — the movement claim is now a NUMBER (2026-08-21)

S1's original write-up was honest that its movement claim was an **inference**: with the step at
`0.0f` the map "cannot" move because `Translate` receives 0,0. That was never measured, and the
"What it does NOT establish" section said so. It is measured now.

Made possible by the windowed-resize session's runtime work on the camera. Every vtable claim in
it was re-checked against `Apps\SIMSPR.DLL` before use, and all five matched:

| iso vt slot | expected | in the binary |
|---|---|---|
| `+0x2c` | scroll `0x10006226` | ✓ |
| `+0x38` | SetZoom `0x10006752` | ✓ |
| `+0x48` | SetRotation `0x10006a55` | ✓ |
| `+0x158` | present `0x1000e206` | ✓ |
| `+0x98` | `0x10008eee` — flagged as **NOT** the scroll | ✓ |

### Two corrections to that hand-off, both found by the runtime guard

1. **The camera class is not reachable at `cityView+0xb8`.** That field holds vt `SIMSPR+0x63390`
   = `cSC3CityViewIso`. The new `cam` step refused to read from it rather than printing numbers
   from an unidentified object.
2. **`SIMSPR+0x6250c` is `cISC3CitySpriteCellMap`, not the "isometric view".** The naming matters
   because both objects exist and both are camera-ish. Its `+0x28` zoom / `+0x2c` rotate /
   `+0x30` cell size are exactly the trio described, so the *object* was right and only the route
   to it was wrong.
   **Found by scanning for the vtable instead of guessing an offset: it lives at
   `cityViewIso+0x158`.** Now a recorded offset.

### The measurement

Sequence `cam; key:0x25,2500; wait:3000; cam` — identical in both runs, only the 5 patched bytes
differ.

| | shipped (`eec71500…`) | S1 (`1d4e886a…`) |
|---|---|---|
| step `+0x1c8` / bank | `32.000` ×5 | `0.000` ×5 |
| `+0x177` before → after | 0 → 1 | 0 → 1 |
| direction flags | `0/0/1/0` (left) | `0/0/1/0` (left) |
| origin **before** | `512,2352` | `512,2352` |
| origin **after** | **`-6336,2352`** | **`512,2352`** |
| **Δ** | **`-6848, 0`** | **`0, 0`** |
| right/bottom, span | `1536,3120`, `1024x768` | `1536,3120`, `1024x768` |

**The inference is replaced by a measurement: shipped moves the camera 6,848 world pixels, S1
moves it exactly 0, with the same key held for the same duration and the gate open in both.**

Three things fall out for free:

- **The reference measurement reproduces exactly.** `512,2352,1536,3120` with a 1024x768 span,
  independently, on a different session and a different run. The hand-off's numbers are sound.
- **`zoom=3` read directly off the object**, and `tilepx=64 = 8<<3`. That is a **third independent
  confirmation** that the live/default zoom is 3 and therefore selects `.rdata` slot `0x67694` —
  after the S2/S3 byte patches and the sprite-instance evidence. Three methods, same answer.
- **Span is preserved across the scroll** (`1024x768` before and after), matching the claim that
  `0x10006226` adds deltas to all of `+0x54..+0x70` while holding the span.

Sanity check on the magnitude: 6,848 px in 2.5 s at 32 px/step is ~214 steps, i.e. ~86 ticks/s —
consistent with a per-frame tick at that framerate, not with the ~10 Hz the earlier hit-count
sampling suggested. The earlier "2 hits" reading was an artifact of the report interval, not the
tick rate.

`presentGate(+0x7c)` printed as `-1593218560` — read as a signed int, which is almost certainly
wrong for that field (it looks like a pointer). Not relied on for anything here; the `cam` step
should print it as raw hex.

### Install state

```
Apps\SIMSPR.DLL           eec71500…   restored to the shipped anchor
Apps\SIMSPR.DLL.original  absent
```

### `cam` step finished — field semantics derived, not received (2026-08-21)

The `presentGate` nit above is fixed, and rather than wait on the hand-off the types were read
straight out of `FUN_10006226`:

| field | truth | evidence in `FUN_10006226` |
|---|---|---|
| `+0x54..+0x60` | rect A: left, top, right, bottom | `:150-151` computes span as `+0x5c-+0x54` by `+0x60-+0x58` |
| `+0x64..+0x70` | rect B: same layout, moved in lockstep | `:61-68` adds `param_1` to both lefts/rights and `param_2` to both tops/bottoms |
| focus point | centre of rect A | `:71-72` uses `((+0x5c + +0x54)/2, (+0x60 + +0x58)/2)` |
| **`+0x7c`** | **a BYTE, not a dword** | every test is `*(char *)(this + 0x7c)` (`:45`, `:154`); written as a byte at `:147` |
| `+0x32c` | a second byte flag | tested alongside `+0x7c` at `:154` |

That `param_1` goes to lefts/rights and `param_2` to tops/bottoms **is** the span invariance — it
is not a separate property to be trusted, it is visible in the arithmetic.

The present gate is `param_3 != 0 && +0x7c != 0` → `vt+0x14c` (invalidate+paint) then `vt+0x158`
(`0x1000e206`, present) at `:45-47`.

Verified in-game after the fix:

```
### CAM: cell map found at cityViewIso+0x158 -> 0x0F704A58 (vt SIMSPR+0x6250C)
### CAM: iso=... rectA=512,2352,1536,3120 span=1024x768  centre=1024,2736
### CAM: rectB=512,2352,1536,3120 span=1024x768
### CAM: zoom=3 rot=0 tilepx=64 (8<<zoom=64)  presentGate(+0x7c)=0  flag(+0x32c)=0
   ... arrow held 2000 ms ...
### CAM: iso=... rectA=-6336,2352,-5312,3120 span=1024x768  centre=-5824,2736
### CAM: rectB=-6336,2352,-5312,3120 span=1024x768
```

`presentGate` now reads **0** instead of the nonsense `-1593218560`. **Rect B tracks rect A
exactly** — same values before and after — which is the lockstep the arithmetic predicts.

**Method note, applied live:** this run first died at 825 ms. Under the corrected rule that is
"check for another SC3U", not "my edit broke it". Checked (none live), re-ran unchanged, completed
in 9.9 s. The corrected rule earned its keep on its first use.

---

## CAVEAT added 2026-08-22 — the camera numbers were not anchored to N at measurement time

The bigger-cities session flagged a shared-state hazard that bears directly on every camera
reading above: **the load-city dialog's confirm id (`0x02DFDD6A`) selects a list POSITION, not a
city**, and camera/scroll values scale with map size N (SIMGEOM world extent
`(width-1)*0x100` by `(height-1)*0x100` [CONFIRMED @ 0x100023e8]). A run on the wrong N does not
crash — it yields plausible numbers for the wrong map. My `cam` step did **not** log N at the time,
so this is the exact "answer that looks like an answer" trap.

**Reconstruction — the runs were Berlin, N=256 — supported three independent ways, but it is
reconstruction after the fact, not a logged measurement:**

1. The auto-load sequence `0x712BF5BF;0x02DFDD6A;0xE2FA5BC2` is the project's documented
   "loads Berlin" sequence (`.happy/project-info.json`: "Auto-load … verified on Berlin
   (Pob 794,278)").
2. The `-pref` screenshots I read visually (`pref1_202726.png`, `pref3_005306.png`) show
   **"Berlin  Pob: 794,278"** in the status bar. The `cam` runs used the identical sequence.
3. `Berlin, Germany.sc3` sorts to **list position 0**; the only non-shipped save in play (the
   bigger-cities 512 city) sorted to **position 11**, so it never displaced position 0. `Cities\`
   is stock now (15 `.sc3`, none newer than shipped) and this session never wrote a save.

Berlin is a **256-tile** map (the warning and the pane both give Berlin = 256), so the numbers
above are for **N=256**: `zoom=3`, `tilepx=64`, extent ~`65280x65280` px, and the recorded rects
(512..3120) sit well inside that.

**What stands and what is now conditional:**

- **The core S1 result stands unconditionally.** "Shipped moves the camera 6848 px, S1 moves 0"
  is a within-comparison at a *fixed* N: both figures are Berlin/256, and the claim is about the
  byte patch changing the step, not about absolute extents. The step-bank read-offs (`32.000` vs
  `0.000`) do not depend on N at all.
- **The shipped-vs-S1 pairing is sound but rests on both launches loading position 0.** They did
  (identical start origin `512,2352` across the two separate launches is the corroborating
  signal), but that was luck of a stable position 0, not verification.
- **Absolute rects and any px-per-tile calibration are Berlin-specific** and must not be carried to
  another map size without re-measuring.

**Fixed going forward:** `gz_cam_step` now logs `### CAM: MAP WxH tiles` from the occupant bridge
(`+0xec/+0xf0`) next to every reading, or says the dimensions are unavailable rather than printing
an unanchored number. Needs a rebuild + queued run to take effect; not run here (harness is being
rewired and I am not holding the game lease).
