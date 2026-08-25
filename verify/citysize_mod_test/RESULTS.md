# citysize_mod_test — RESULTS (2026-08-20)

## Verdict

**The simulation accepts N = 512. The renderer does not.**

Two separate results, and conflating them would be wrong:

1. **The city object is constructed at 512 × 512 × 512** — traced live, no error. Four bytes.
2. **512 then crashes the process** a couple of seconds later, inside the GZGraphicD blit
   dispatcher, after the city already exists. 192 and 256 do not.

So the seeding chain is fully size-agnostic and the blocker is downstream in the draw path.
**512 is not playable.** See "Where it dies" and "The threshold is not clean".

## ✅ RESULT (2026-08-22): the SIZE group alone is the whole fix. The stride hypothesis FAILED.

24 runs, four configurations, **one lease, one probe, one batch** (`run_batch.ps1`). Every run
valid, dimensions confirmed from the seeder's arguments on all 24.

| config | SIMDIRT state | N | survived | deaths |
|---|---|---|---:|---|
| **B** | shipped | 512 | **0/6** | 4.5 – 6.8 s (median 4.8) |
| **E** | all 12 sites | 512 | **6/6** | — |
| **C** | **SIZE group only** | 512 | **6/6** | — |
| **D** | all 12 sites | 192 | 6/6 | — |

**What is established, decisively:** B vs C differ *only* in the four SIZE immediates, and that
alone takes N=512 from 0/6 to 6/6. B is deterministic — six deaths inside a 2.3-second band. The
`0x20402` buffer overrun is THE corruptor, and fixing its size is sufficient to stop the crash.

### ⭐ INDEPENDENT CORROBORATION of the 0/6 baseline (resizable-window session, 2026-08-23)

The unpatched-512 crash was reproduced **by another session, by accident, with no knowledge that
the city was 512**. That is stronger than my own measurement of it, because they were not looking
for it.

Cause: a saved 512 city left in `Cities\` sorted to position 11, and the load dialog's confirm id
selects a **position, not a city** (now GAME_PROTOCOL.md rule 6), so their auto-load pulled a
512 city onto a **stock SIMDIRT**.

| evidence | when | fault |
|---|---|---|
| `cull.log` | 2026-08-23 06:06 | `0xC0000005`, SIMDIRT `0x10013A8F` |
| `cull2.log` | 2026-08-23 06:08 | `0xC0000005`, SIMDIRT `0x10005AE1` from `0x10006871` |
| `ctrl2` | same command, **no resize switches** | crashed identically at 4.5 s |

Both postdate the save (2026-08-22 22:48) and both land inside the measured **4.5 – 6.8 s** band.
The `ctrl2` control rules out their instrumentation.

**Deliberately NOT cited:** their `ver5.log` (2026-08-21 18:07) faults at the *same* address
`0x10013A8F` but **predates the save by over a day**, logged `map(+0xec,+0xf0)=256x256`, and had
`ECX = 0xBC`. That is a different bug (a missing surface lock), and counting it would overstate
this result. Scoping supplied by the session that owns those logs.

**The discriminator, since one address serves two bugs.** `0x10013A8F` is inside the span
rasterizer `FUN_10013556` and appears in both lists. The faulting register tells them apart:

* **small constant** (e.g. `ECX = 0xBC`) -> a null bits pointer plus a struct offset, i.e. an
  unlocked surface;
* **wild-but-large** (`0x740d8c90`, `0x5baa5baa`, `0x8800d900`) -> heap garbage from the 132 KB
  `0x20402` overrun.

Same crash site, two causes, distinguishable on sight from the register value alone.

**What FAILED: my prediction that C would land at ~4/6.** The aliasing argument said a size-only
patch leaves rows overlapping and should therefore be measurably worse than E. **C and E are
indistinguishable — both 6/6.** The discriminating half of the hypothesis did not survive contact.

**Why the earlier C = 4/6 was probably wrong.** That measurement ran on the old probe *during the
window when another session was killing SC3U processes by name*. This file already flagged those
two deaths (18.2 s, 26.2 s) as impossible to clear of external interference. Re-measured under a
lease with no foreign killer, C is 6/6. The honest conclusion is that the earlier 4/6 was
contaminated, not that the stride patch fixed something.

**Where that leaves the STRIDE and CORNER groups.** They are still *correct* on code-reading
grounds: with stride 257 against an enlarged buffer, row X's cells 257..511 alias onto row X+1, so
the terrain data is wrong. But **survival cannot see wrong data, only wrong memory** — and this
experiment measured survival. So:

* the stride/corner fix is justified by the arithmetic and by the derivation reproducing the
  shipped `0x204` at N=256, and it costs nothing to apply;
* it is **NOT validated by any measurement**, and must not be described as such;
* testing it needs a different observable — e.g. save a 512 city under C and under E and diff the
  terrain section, or compare rendered terrain. That experiment has not been designed or run.

**Probe rebuild was neutral.** B replicated across it (0/6 at 4.7–5.3 s on the old probe, 0/6 at
4.5–6.8 s on the new one), so re-running the baselines cost ~12 minutes and bought certainty.

Install restored and hash-verified against `original/modules/` for all three DLLs; lease released
(another session acquired it one second later).

## ❌ RAN, NEGATIVE AND UNDERPOWERED — the C vs E frame diff found nothing (2026-08-22)

Ran it. **No detectable difference**, and the reason it is not conclusive is identifiable.

Method: save one 512 city, load *that same save* under both builds (menu-driven), capture a frame
each, diff. Determinism comes from the fixed save, since fresh terrain uses seed `-1`.

**Raw diff looked like a strong positive and was not.** C vs E differed in 233,337 px (6.33%).
But the essential control — the SAME build run twice — differed by 233,639 px (6.34%), identical
bounding box. **The frame diff is entirely dominated by the live simulation** (clock, traffic,
smoke). Without that control this would have been reported as "6.33% of pixels differ, the stride
matters", which is false.

**Denoised with a stability mask** (pixels identical across two same-build runs = not animated;
93.66% of the frame), then compared on the mask only. Three same-build runs exist (E1, E2, E), so
the masked noise floor is measurable rather than assumed:

| comparison | differing px on the stable mask |
|---|---|
| E1 vs E — same build | 14,639 (0.4240%) |
| E2 vs E — same build | 14,639 (0.4240%) |
| **C vs E — different build** | **14,922 (0.4322%)** |

The different-build excess is **283 px in 3.45 M**, 0.008 percentage points. Not a signal.

### Second attempt WITH the camera jump: still no valid comparison (2026-08-23)

The underpowered-ness below was addressed: `run_diff.ps1` now dismisses the startup tip dialog
(`0xE2FA5BC2`, frame `0xC2FA5860`, which covers the centre of every capture) and steers the camera
by opening **Map View** (`fire:0x10008004`), clicking deep into the far quadrant
(`at:384,390`; the Map View frame `0x42F0DA12` spans 40,34..464,474 with a mode toolbar at
x 4..30, so that is ~80% along both axes), then closing it.

**It still did not produce a result, for a different reason: the drive sequence is unreliable.**
The C/E pair drove correctly once. The matching same-build control then failed. Without a control
the pair is uninterpretable — the first round proved that decisively, where a 6.33% raw difference
turned out to be a 6.34% noise floor.

The failure is **binary, not a timeout margin**:

```
working run : GZSEQ[0]: target 0x712BF5BF  target ready after 813 ms
failing run : GZSEQ[0]: target 0x712BF5BF  never appeared within 45000 ms - SKIPPING
```

Either the Load City tile is found in under a second, or it is never found at all, and every later
step then cascades into SKIPPING so the capture is of the main menu. A boot probe confirms the menu
and that tile both exist at 19 s, so this is not the game failing to start.

One real variable was found and removed along the way: the holding directory for the shipped saves
was originally created **inside `Cities\`**, which the game enumerates. Moving it to the repo root
fixed one round of failures but not all of them.

Also unresolved: after the jump, the dump shows **430 windows**, i.e. Map View is still open at
capture time — the second `fire:0x10008004` did not close it. Consistent across both arms, but it
covers a large part of the view.

**Cost so far: 6 game runs and ~5 leases, no interpretable result.** Making this rigorous needs
harness work — per-step verification, retry on a missed target, and confirming Map View closed —
which is disproportionate to what is being tested: a **cosmetic** defect, in a patch that is free
to apply and already justified by derivation. Parking it here is the right call, and the design
plus the two failure modes are recorded so a future attempt starts from them rather than rediscovering them.

### Why the FIRST attempt was UNDERPOWERED, not evidence of absence

**The aliasing only manifests for Z >= 257** — that is the whole mechanism. The camera on load
shows a small part of the map (tens of tiles), and nothing in this experiment steered it. If the
visible region has Z < 257, **no collision is ever rendered and the experiment cannot see the
defect it was built to detect.** That is the same failure mode as the mtime check and the
hardcoded `N in (128,192,256)` detector: a measurement structurally unable to observe the thing
under test.

**To make it conclusive**, scroll the camera into a region with Z >= 257 before capturing. The iso
view exposes scroll at vtable `0x1006250c` slot `+0x2c` (`FUN_10006226(dx, dy, repaintFlag)`, per
the resizable-window session). Alternatively drive a Map View jump. Neither was done.

**Current honest status of the STRIDE + CORNER groups:** correct by derivation, reproducing the
shipped `0x204` at N=256, costing nothing to apply — and with **no measured effect on anything**.
Not validated, not falsified. The crash fix remains the SIZE group alone.

## Superseded design notes — does the STRIDE fix matter? (C vs E terrain diff)

### What `obj+0x2c` actually is: a per-vertex memoized COLOUR cache

[CONFIRMED @ 0x1001309e] — this is what makes the experiment designable:

```c
iVar4  = X * 0x101 + Z;                          // stride 257
puVar1 = (ushort *)(buf + iVar4 * 2);
if (*puVar1 == 0) {                              // MISS: compute
    uVar3 = (map20[X][Z] - map18[X][Z]) + 0x100; //   slope -> palette index
    iVar4 = paletteTable[(this[8] & 0x3f) * 8][uVar3];
    uVar3 = *(ushort *)(iVar4 + (bVar2 >> 1) * 2);
    *puVar1 = uVar3;                             //   CACHE the resolved colour
    (*DAT_10025bb4)(..., uVar3, param_5, param_5+1, param_5+2);   // -> RGB out-params
} else {                                         // HIT: reuse blindly
    (*DAT_10025bb4)(..., *puVar1, param_5, param_5+1, param_5+2);
}
```

Zero means "not yet computed". Same shape in `FUN_10013fab`. The three `memset`s in the SIZE group
are cache invalidations, which is why they carry the same constant as the allocation.

**Therefore:**

1. **Aliasing is VISIBLE, not silent.** With stride 257 and Z reaching 512, vertex `(X, Z+257)`
   shares a slot with `(X+1, Z)`. Whichever is computed first wins; the second takes a cache HIT
   and renders a colour belonging to a different vertex. Roughly half the grid collides.
2. **It cannot corrupt memory or the simulation.** Values are derived from the correctly-sized
   CellMaps (`+0x18`/`+0x1c`/`+0x20`, both sized from `vt[0xcc]`/`vt[0xd0]`) and feed only RGB
   out-params. **This explains the 6/6 result for C exactly**: nothing crashes, terrain just looks
   wrong.
3. So the observable is a **rendered frame**, not a save file and not a memory dump.

### The design

**Determinism is the hard constraint.** Terrain generation runs with seed `-1`
(`vt+0x1c(0xffffffff, 0x40,0x40,0x40, 0x24)`), so two fresh cities are never comparable. The
experiment must therefore compare *the same terrain* across two builds:

1. Under **E** (all 12 sites), create a 512 city and **save** it. Save writes the dimensions into
   the IXF record `0fa1:617e198d:0`, and the loader validates them, so a 512 save is legitimate.
2. Under **C** (SIZE only), **load that save** and capture a frame.
3. Under **E**, load the same save and capture a frame.
4. Diff the two images.

**Prediction:** C and E frames differ in terrain colouring, with the difference concentrated where
`Z >= 257`. E is the correct rendering. If the frames are *identical*, the stride fix is
unnecessary in practice and should be dropped from the recommended patch.

**Stronger variant, no image diff needed.** The collision is arithmetic: under C the colour at
vertex `(X, 257+k)` must EQUAL the colour at `(X+1, k)`. Sampling those pairs in the captured
frame is a direct, falsifiable prediction that does not depend on comparing builds at all — but it
requires mapping vertex coordinates through the iso projection to screen pixels, which is real
work and is why the frame diff is the cheaper first cut.

**Prerequisites not yet established:**
* driving Save and Load headlessly (menu-driven load is documented in `LAUNCH_CONTROL.md` §29;
  Save has a command id in `MENUITEM_INI.md` but has never been driven here);
* that a 512 city survives long enough to be saved — all runs so far stopped at the same modal;
* `capture.ps1`'s frame is reconstructed from the blit mirror and has already produced stale
  frames once in this investigation (§"Traps"), so the shot must be verified as post-load.

**Cost:** one lease, ~10 minutes, plus the save/load driving work which is the real unknown.

**Worth stating plainly:** this experiment tests a *cosmetic* defect. The crash fix is already
confirmed and is the SIZE group alone. Nobody should block a bigger-cities mod on this.

## Superseded: the queued-experiment plan

Everything below is done. This is the one thing left, and it is a single batch.

**Hypothesis.** The size-only patch stopped the heap overrun but left rows aliasing, which is why
N=512 measured 4/6 instead of 6/6. With the STRIDE and CORNER groups also patched (12 sites total,
all verified in the binary, **never run**), N=512 should reach 6/6 — indistinguishable from the
192 control, which itself measured 5/6.

**Prerequisite — SATISFIED 2026-08-22.** The queue landed. Use the turnkey wrapper, which acquires
a FIFO lease, launches, and releases:

```powershell
pwsh re/harness/with-game.ps1 -Owner "bigger-cities" <sc3launch args>
```

See `re/harness/GAME_PROTOCOL.md`. Never kill a process you did not start.

### ⚠️ THE OLD BASELINES ARE NOT COMPARABLE — re-run them in the same batch

`re/harness/bin/sc3probe.dll` was rebuilt **2026-08-22 08:16** (`find_game_window` is now
PID-filtered and boot-verified). **Every measurement below was taken 20-21 Aug against the OLD
probe.** The oracle here is process lifetime and the rebuild changes behaviour on exactly that
path, so it cannot be assumed neutral.

**Therefore the experiment is 4 configs x 6 runs = 24 runs in ONE batch, one lease, one probe** —
not 6 runs compared against stale numbers. B-vs-E is the load-bearing pair and should be adjacent.

| config | binaries | N | OLD-probe result (do not compare directly) |
|---|---|---|---|
| B | SIMUI only | 512 | 0/6 survived, deaths 4.7 – 5.3 s |
| C | SIMUI + SIZE group only | 512 | 4/6 survived, deaths 18.2 – 26.2 s |
| D | same binaries as C | 192 | 5/6 survived |
| **E** | **SIMUI + all 12 sites** | **512** | **predicted 6/6** |

**Procedure**, per config, all at `-Duration 40`:

```powershell
# B
py -3.12 verify/citysize_mod_test/patch_citysize.py --n 512
pwsh verify/citysize_mod_test/measure.ps1 -Radio 0x25524852 -Runs 6 -Tag b512
# C
py -3.12 verify/citysize_mod_test/patch_dirtbuf.py --n 512      # then hand-revert stride+corner,
#   or keep a SIZE-only variant, so C differs from E only in groups B and C of the patch
# E
py -3.12 verify/citysize_mod_test/patch_dirtbuf.py --n 512      # all 12 sites
py -3.12 verify/citysize_mod_test/patch_dirtbuf.py --check      # confirm size/stride/corner
pwsh verify/citysize_mod_test/measure.ps1 -Radio 0x25524852 -Runs 6 -Tag e512
# D control, same binaries as E, only N differs
pwsh verify/citysize_mod_test/measure.ps1 -Radio 0x25524851 -Runs 6 -Tag e192

py -3.12 verify/citysize_mod_test/patch_dirtbuf.py  --restore
py -3.12 verify/citysize_mod_test/patch_citysize.py --restore
```

**Falsified if** E is not clearly better than C over 6 valid runs *on the same probe*. C-vs-D was
already statistically indistinguishable, so **E-vs-D is the honest bar, not "zero deaths"**.

**Caveats to carry in.** `measure.ps1` counts a run only if the seeder fired with confirmed dims,
which excludes single-instance exits. But an external `Stop-Process` is indistinguishable from a
crash under a process-polling oracle, so a lease must actually be held for the numbers to mean
anything. Configs C and D were measured while another session was killing processes and cannot be
cleared of interference; re-run them alongside E if their exact values matter.

## ❓ OPEN: a possible SECOND corruptor — the SIMSPR flag-change queue

Reported by the resizable-window session, and it is the same shape as the defect already found.
The iso view keeps a flag-change queue at `iso+0x448`/`+0x44c` (4-byte records
`{opcode, x, y, zoomIdx}`) drained by `FUN_10008dd4`. `FUN_10005b42` (Init) reallocates the tile
cache **zeroed**, so a stale record's footprint-size byte at `+0x0a` reads 0, and the drain then
computes `this + 0*4 + 0x48c` in `FUN_100080a9` — **one slot BEFORE** the five-cache array at
`+0x490` — and dereferences it. They measured 20 stale entries; discarding the vector fixed it.

**Confirmed statically here:** `FUN_10005b42` does **not** clear `+0x448`/`+0x44c`. Reading the
whole function, the only vector housekeeping is `FUN_1001084b` on `+0x4d0` and `+0x4dc` (the
present-rect lists). So Init leaves the queue intact and the landmine stands.

**Why it might apply to N=512:** every new city drives Init with new dimensions, which is exactly
the trigger condition.

### ✅ RESOLVED — it does NOT apply to the new-city path

`FUN_1001c4a1` constructs the view per city and Inits it immediately, so the vectors are empty and
there is nothing stale to drain [CONFIRMED @ 0x1001c4a1]:

```
line 75   pvVar5 = operator_new(0x528)
line 91   (**(code **)(iVar3 + 0xc))(uVar8)     <- Init on the fresh view
line 107  pvVar5 = operator_new(0x124)
line 123  (**(code **)(iVar3 + 0xc))(uVar8)     <- second object, same pattern
```

That function is in this investigation's own crash stack (frame `SIMSPR+0x1c733` =
`FUN_1001c4a1+0x292`), so the N=512 path demonstrably goes through it. The resizable-window
session adds that the records come from the async sprite path, which has no work to do before the
first tile fill.

**So the landmine is specific to RE-ENTERING Init on a live view (a resize), not to constructing a
new view per city.** It is not a second corruptor for the bigger-cities work, and the 6/6
prediction for the twelve-site patch does not have to survive it.

Earlier note, kept because the reasoning was wrong in an instructive way: this was first written up
as "not resolvable from the export" because Ghidra lost the `this` bindings on the ctor
(`FUN_1000523a`) and dtor (`FUN_100057e9` / `FUN_1000578c`) callers. That was the wrong place to
look — the answer was in the *caller* of Init, which was already sitting in the crash stack.

## The patch

One instruction, `SIMUI.DLL` file offset `0x05ECF8`, VA `0x1005ECF8`:

```
c7 86 74 01 00 00 | 00 01 00 00     mov [esi+0x174], 0x100   (shipped)
c7 86 74 01 00 00 | 00 02 00 00     mov [esi+0x174], 0x200   (patched)
```

Four bytes at `0x05ECFE`. Apply / revert / inspect with `patch_citysize.py`
(`--n 512` / `--restore` / `--check`). Shipped DLL preserved as `SIMUI.DLL.shipped`
(sha256 `2efdf265…92103fd`, verified identical to `original/modules/SIMUI.DLL` before patching).

The other three arms (`0x05ED0A`=192, `0x05ED16`=128, `0x05ED22`=64) are left untouched and the
script refuses to run if any of them has drifted. That is what makes an in-binary control possible.

## Why this one site is sufficient — the whole chain

`FUN_1005eb40` stores N in the dialog at `+0x174`. That single field feeds **both** consumers:

1. **Terrain.** `generator->vt[0x0c](N, N)` → `SIMDIRT 0x1001742c` stores `N+1` as the vertex
   count and heap-allocates four grids at `(N+1)×(N+1)`. Generator identity: GZCLSID
   `0xa2705d06`, IID `0xa2705d07`, ctor `0x10017352`, vtable `0x10020be8`, `operator_new(0x30)`.
   Created into the dialog's `+0x178` by `SIMUI 0x1005e570`.
2. **City.** `SIMUI 0x10011dd6` (the `0x855a2dc4` settings provider, `vt+0x30`) returns
   `*(dialog + 0x174)` — the same field — and falls back to a hardcoded `0x100` only when the
   dialog pointer is null. That value reaches the SIMINIT new-city descriptor
   (ctor `0x1000bdc3`, GZIID `0x43271e76`), then `cSC3City` slot 7 `FUN_10003b8b`, then the single
   seeder `FUN_10003ea6`, which writes `city+0x3c/+0x40/+0x44`.

Nothing on that path holds a fixed-size buffer. The one 256-entry array in the generator
(`0x10017c2d` `local_42c`) is a histogram indexed by a **byte**, not by N.

## Observations

Harness: `re/harness/capture.ps1`, switches
`-nocom -windowed -origin -fix16 -fitclient -nointro -quiet`, plus
`-modlog SIMCITY.DLL:0x10003ea6` (logs `ecx` and the first five stack args of the seeder).
Sequence, identical in both arms:
`0x712BF5BE@9` (New City tile) `; <size radio>@16 ; 0x2552483D@20` (confirm checkmark) `; dump@60`.

| run | radio | seeder `FUN_10003ea6` args (X, Y, Z) | window tree | GZSEQ |
|---|---|---|---|---|
| `ctrl192b` | `0x25524851` (192, **untouched arm**) | `0xC0, 0xC0, 0xC0` | 13 | COMPLETE @ 4453 ms |
| `n512b` | `0x25524852` (patched arm) | `0x200, 0x200, 0x200` | 13 | COMPLETE @ 4719 ms |

Both called from `SIMCITY.DLL+0x3D2E`, i.e. inside `FUN_10003b8b` — independently confirming that
**slot 7 (the descriptor path) is what the new-city UI actually drives**, not slot 5 (load) or
slot 6 (the 128×128×256 fallback).

No exception, no assert, no early exit in either arm. An earlier 512 run also showed
`raster_blit_hw = 4935` and live `setpixel_a` traffic, so the renderer was working after the
512 city was constructed.

## ⚠️ CONCURRENCY: this repo is shared, and it invalidated data in both directions

Another session was running SIMSPR captures against the same install throughout this work. Two
consequences, both confirmed, both mine to own:

1. **My tooling killed their runs.** The first version of `measure.ps1` (and several ad-hoc
   commands before it) ran `Stop-Process -Force` on **every** SC3U/sc3launch it found at the start
   of each run, not just its own. Across configs A-D that is roughly 25 unconditional kills.
   `measure.ps1` now refuses to kill anything it did not start, tracks its own sc3launch PID,
   finds the SC3U **parented by that PID**, and aborts outright if a foreign instance is present.
2. **My patched DLLs were live on disk during their runs.** `Apps/SIMUI.DLL` spent long stretches
   patched to 272 or 512, and SIMDIRT/SIMINIT were patched at times too. Any of their results in
   that window may be contaminated.

### ⚠️ mtime CANNOT detect that a shared binary was patched — copy2 erases the evidence

`patch_*.py` back up and restore with `shutil.copy2`, which **preserves mtime**. After a restore the
file's timestamp is the original's, so an integrity check based on "has any `Apps\*.dll` been
modified recently" returns CLEAN whether or not the file was patched an hour earlier. Measured:

```
Apps\SIMUI.DLL    mtime 2000-04-18 23:47   (identical to original\modules\SIMUI.DLL)
Apps\SIMDIRT.DLL  mtime 2000-04-18 23:38   (identical to reference)
copy2 test: source mtime 0 -> dest mtime 0  => PRESERVES
```

A hash check *after* restoration is equally blind, since the bytes are back to shipped. Another
session used an mtime check to conclude their captures were taken against a stock install; that
conclusion was not supported, and at least one of their runs provably overlapped a patched SIMUI.

**Honest windows, from the backup files' creation times (not copy2'd, so trustworthy):**
SIMUI from 2026-08-20 10:43, SIMINIT from 2026-08-20 11:59, SIMDIRT from 2026-08-21 00:55 —
intermittently patched from each point onward.

**The only reliable method is to hash at run time and record it with the result.**
`game_lock.ps1 -Acquire` stores `modifiedBinaries` in the lease and `-Status` prints live
`Apps\` vs `original\` for exactly this reason.

### ⭐ SC3U IS SINGLE-INSTANCE — and this explains the "transients"

If an SC3U is already running, a new launch takes the `FUN_0040496d` path (a mutex plus
`FindWindowExA` on `"Gonzo"` / `"SimCity 3000"`), **exits with `0xFFFFFFFF` at roughly 840 ms and
writes NO crash dump.** `-restart:on` bypasses the check if genuine concurrency is wanted.
(Credit: the concurrent SIMSPR session.)

**This retires the "pre-existing boot transient" explanation used earlier in this file.** The runs
that died at 812 ms, 972 ms and ~1.5 s were almost certainly this handoff, i.e. another session's
game was up — not a harness flake. Anything that ends early with no dump should be checked against
`Get-Process SC3U` before it is believed.

The headline B-vs-C result survives, because `measure.ps1`'s validity gate requires the city seeder
to have fired with confirmed dimensions, and a single-instance exit never gets that far (all 24
runs in A-D reported real dims). But **the residual deaths at ~18-26 s in C and 21.2 s in D cannot
be cleared of external interference** — an outside `Stop-Process` is indistinguishable from a crash
under this oracle. Those specific deaths need re-running under the fixed script.

## Traps hit, recorded so they are not re-hit

1. **The screenshot lies.** `capture.ps1`'s frame comes from the blit mirror and showed the New
   City dialog in every run, including after the confirm click and after the tree had already
   changed. The **window dump is the oracle**; the PNG is not. This is the §31.4 stale-frame trap
   and it cost three reads here.
2. **A differing final verb invalidates the comparison.** The first 512 run ended in
   `wait:12000` and reported no COMPLETE, which read as "512 hung". Re-run with the control's
   exact `dump@60` it completed normally. The apparent failure was mine, not the game's.
3. **One run is not evidence.** A 192 control run exited at 812 ms with an immediate process
   detach, before the menu. Re-running it succeeded unchanged. Any single-run conclusion here
   would have been wrong.

## Where it actually dies — heap corruption, caught under cdb

> ⚠️ **The blit-dispatcher story in the section below is RETRACTED.** `blt_disp_3` was simply the
> last thing the probe happened to log before the process died. It is not the fault site. Kept
> below only because the A/B survival data in it is still valid.

Run under `cdb` (Windows Kits x86, `-o -g -G`, `sxe av`, `sxi eh`) at N=512:

```
Last event: Access violation - code c0000005 (!!! second chance !!!)
eip=SIMGEOM+0x41d8   cmp dword ptr [eax+8],0    ds:002b:740d8c98=????????
eax=740d8c90                                     <- unmapped
```

`0x100041d8` is inside **SIMGEOM `FUN_100041cd`** (+0xb), 49 bytes, which is a textbook
**red-black-tree iterator increment**: it walks `node+0xc` (parent), `node+4` (left), `node+8`
(right). It faults dereferencing a **garbage node**.

**That means the bug is heap corruption, and this crash site is only the symptom.** An
out-of-bounds write somewhere earlier trashes a `std::map`/`std::set` node, and the process dies
later when something walks that tree.

This is exactly what the non-monotonic survival table below looks like from the inside: corruption
whose lethality depends on what happened to be allocated next, which varies per run because the
terrain generator is invoked with seed `-1`.

Reported stack (`kb`), **with the caveat cdb printed: `WARNING: Stack unwind information not
available. Following frames may be wrong.`** So treat everything below the fault frame as a lead,
not as fact:

```
SIMGEOM  0x100041d8 -> FUN_100041cd (+0xb)      <- fault, tree iterator
SIMGEOM  0x100039d6 -> FUN_100039a8 (+0x2e)
SIMGEOM  0x1000e165 -> FUN_1000df90 (+0x1d5)
SIMGEOM  0x1000d3f6 -> FUN_1000d290 (+0x166)
SIMGEOM  0x1000df7c -> FUN_1000df50 (+0x2c)
SIMGEOM  0x1000c369 -> FUN_1000c250 (+0x119)
SIMDIRT  0x100058d9 -> FUN_10005500 (+0x3d9)    first stack arg = 0x200 (512)
GZServiceD  (message dispatch)
```

`SIMDIRT FUN_10005500` is the terrain-generation message handler (gated on
`*param_2 == 0x2f2ee63`). Near its end it runs two full-map rect operations at the runtime size:
`FUN_10007010(this, 0, 0, w-1, h-1)` and `FUN_10006370(this, 0, 0, w-1, h-1, 0)`.

**Hypothesis checked and killed:** the `generator->vt[0x1c](0xffffffff, uVar6, uVar6 >> 8)` call in
that function looked like a dimension packed into 8 bits. It is not — `uVar6 = param_2[1]` is
unpacked as `uVar6`, `>>8`, `>>0x10`, which are the three **terrain-gen limits**
(mountain / water / flora, `0x40` each from the dialog), not a dimension.

### Two hypotheses tested and FALSIFIED by experiment

**H1 — the vertical extent is an 8-bit field, and N was being written into it. FALSIFIED as the
cause (but the defect is real).**

Occupant positions pack into one 32-bit word as **11 bits X | 11 bits Y | 8 bits Z | 2 bits
orientation** [CONFIRMED @ 0x1001dd49, 0x1001cd38, 0x1001d128], duplicated verbatim across 10
modules. The Z setter does not even mask [CONFIRMED @ 0x1001d1bf: `shl eax, 0x16`, no `and`], so
Z >= 256 silently overwrites the orientation bits. And SIMINIT `FUN_1000c09c` writes one scalar
into **all three** descriptor dimension fields [CONFIRMED @ 0x1000c09c], one of which
(desc+0x40 -> city+0x44 -> `vt[0xd4]`) is the **vertical** extent, not a map axis. That predicted
the 256-pass / 257-fail-3/3 boundary exactly.

Test: NOP the middle store (`SIMINIT` VA 0x1000c0a3, `89 41 40` -> `90 90 90`), pinning the
vertical at the ctor default 0x80. Runtime confirmation the patch worked: the seeder was called
with **`a1=0x200, a2=0x80, a3=0x200`** (512, 128, 512). Result: **crashed 3/3 anyway.**

So this is a genuine latent defect worth fixing on its own terms, and it is **not** what kills
N>256. Note also that X and Y get **11 bits (2047)**, and SIMDIRT has a fast path explicitly
guarded at `< 0x201` for a 512-entry buffer [CONFIRMED @ 0x1000e350] — the engine anticipates 512
horizontally, so the horizontal ceiling is not a design limit.

**H2 — the fixed 256x256 SIMUI surface is overrun by a city-sized raster. FALSIFIED.**

[CONFIRMED @ 0x10053114] in `FUN_10052ed2`: `mov eax,0x100 / push eax / push eax /
call [esi+0xc]` — one immediate sizing a surface squarely to 256x256, created in the same
window-factory path (class 0x5a9, IID 0x5df) as the map view. Patched the immediate to 0x200
alongside the city size. Result: **crashed 3/3 anyway.**

### An over-read I have to correct

One crash showed the faulting iterator holding `0x5baa5baa`, whose two 16-bit halves are
identical. I read that as the signature of a 16bpp (RGB565) pixel fill overrunning into the heap,
which is what motivated H2. **That was one sample.** The earlier crash held `0x740d8c90`, whose
halves are *not* identical. So the garbage value varies and does not support a specific 16-bit
fill pattern. Generic wild-pointer / heap corruption remains the reading; the RGB565 story was
inference from a single observation and should not be repeated.

`!address` on the bad pointer reports **MEM_FREE** (a 1.334 GB free region), i.e. it is not a
freed heap block but garbage.

### What would finish this

### ⛔ PAGE HEAP DOES NOT WORK ON THIS TARGET — do not retry it

Attempted with elevation, three configurations, all via `gflags /p` + cdb. **None reached the
point where a city is created**, so none produced any evidence. The IFEO key was removed
afterwards and verified gone.

| configuration | `PageHeapFlags` | result |
|---|---|---|
| `/full` (all allocations) | `0x3` | game boots but is so slow the main-menu window never appears within 40 s; ran to 16.9 s of log with heartbeats, sequence never fired |
| `/full /dlls SIMGEOM.DLL SIMDIRT.DLL` | `0x403` | **game dies at 972 ms with zero heartbeats** — never boots at all |
| light / tail-check (`/p /enable`, no `/full`) | `0x2` | game runs to 115 s, but the menu window `0x712BF5BE` never appears; both drive steps timed out and were skipped |

Note the light configuration is only a tail-check on free, so even had it booted it would have
reported the overrun at free time rather than at the write.

A first attempt also mis-scripted cdb with `sxe av`, which breaks on FIRST-chance access
violations. `KERNEL32!IsBadReadPtr` probes memory deliberately and swallows its own AVs, and under
page heap those fire constantly, so the debugger stopped on a benign probe. Use **`sxd av`**
(break only when an AV goes unhandled) for this target.

**So the exact out-of-bounds write is still unidentified, and the cheap route to it is closed.**

## ⭐ THE FINDING: a hardcoded 257 x 257 terrain buffer in SIMDIRT

**[CONFIRMED @ 0x100166e0]** in the lazy singleton constructor `SIMDIRT FUN_1001665c` (reached from
`FUN_1001214d`, `if (DAT_10025bac == 0) DAT_10025bac = FUN_1001665c(operator_new(0x30))`):

```
0x100166e0  68 02 04 02 00   push 0x20402       ; 132098
0x100166e5  e8 e6 7b 00 00   call operator_new
0x100166ef  89 46 2c         mov  [esi+0x2c], eax
```

**`0x20402` = 132,098 = 257 x 257 x 2** — one `ushort` per vertex of a **256-tile** map
(N+1 vertices per axis). The buffer at `obj+0x2c` is indexed by map coordinates throughout
SIMDIRT, e.g. `(ushort *)(*(int *)(DAT_10025bac + 0x2c) + iVar4 * 2)` in `FUN_1001309e` and
`FUN_10013fab`. On a map larger than 256 tiles it is overrun, which corrupts the heap.

Required size is `2 * (N+1)^2`: N=256 -> `0x20402` (shipped), N=512 -> `0x80802`,
N=1024 -> `0x200802`. All are `imm32`, so the patch is length-preserving
(`verify/citysize_mod_test/patch_dirtbuf.py`).

### How it was found — instrumentation, after three static hypotheses failed

A conditional cdb breakpoint was placed at `SIMGEOM+0xe0b2` to catch the previously top-ranked
candidate (the unclamped occupancy-grid loop) in the act. **Its one-shot probe never fired**, which
proves `FUN_1000df90`'s loop is never even reached on this path — **candidate #1 is ruled out.**

Instead the run stopped at an earlier fault, **SIMDIRT `0x10012eab`**, whose register mapping was
then read off the disassembly:

```
mov   eax, [0x10025bac]      ; the singleton
mov   edi, [eax + 0x18]      ; a CellMap
movzx esi, word [ecx + 4]    ; X  (16-bit)
mov   edi, [edi + 0xc]       ; row-pointer table
movzx ebx, word [ecx + 6]    ; Z  (16-bit)
mov   esi, [edi + esi*4]     ; esi = rowtable[X]   <- GARBAGE
movzx si,  byte [esi + ebx]  ; FAULT
```

Observed with X=394, Z=438 (and X=395, Z=457 on a second run) on a 512 map — both far above 256.
Callers were SIMSPR `FUN_1001a291` / `FUN_10018cdf` / `FUN_10016eba`, and `FUN_10016eba` /
`FUN_1001c4a1` are already-known consumers of the city dimensions.

### ⭐ THE FIX IS TWELVE SITES IN THREE GROUPS — size, stride, and one corner displacement

Patching the allocation size alone was **half a fix**. The buffer is addressed as
`buf[(X * stride + Z) * 2]` and the **stride is separately hardcoded to 257**.

| group | pattern | sites | shipped | N=512 |
|---|---|---:|---|---|
| SIZE | `push 0x20402` | 4 | 132098 = 2*(257)^2 | `0x80802` |
| STRIDE | `imul reg, reg, 0x101` | 7 | 257 | `0x201` |
| CORNER | `mov word [edx+ecx*2+0x204]` | 1 | 516 = 2*(stride+1) | `0x404` |

All twelve are `imm32`/`disp32`, so length-preserving. `patch_dirtbuf.py` patches all of them from
one `--n` and refuses if any prefix or current value is unexpected.

STRIDE sites: `0x10012d0f`, `0x10012d2d`, `0x10012d4e`, `0x10012d6c` (the four cell corners in
`FUN_10012cf3`), `0x100130b0` (`FUN_1001309e`), `0x10013fc0` (`FUN_10013fab`), `0x10014512`
(`FUN_100144ff`).

The CORNER site is subtle and was nearly missed: `FUN_10012cf3` clears a cell's four vertices, and
`0x204` = 2*258 = 2*(stride+1) reaches the (X+1, Z+1) corner from base index `X*stride+Z`. It is a
**memory displacement, not an immediate operand**, so an imm-operand scan does not see it — it was
found by scanning `X86_OP_MEM` displacements, and it is the only `0x204` displacement in the
module. Its sibling `+2` displacement is the (X, Z+1) corner and is stride-INDEPENDENT, so it is
deliberately left alone.

**The arithmetic explains the entire measurement history:**

| configuration | max byte index at N=512 | buffer | outcome |
|---|---:|---:|---|
| shipped | 264,190 | 132,098 | **132 KB heap overrun** — the confirmed corruptor |
| size-only patch | 264,190 | 526,338 | fits, but rows **alias** (row X cells 257..511 land on row X+1) |
| all 12 sites | 526,334 | 526,338 | correct |

That is why the size-only patch moved N=512 from 0/6 surviving to **4/6 and not 6/6**: it stopped
the corruption but left the terrain data wrong.

**Independent confirmation of the interpretation — the buffer fits EXACTLY, with zero spare.**

Computed over all four corner writes at the maximum CELL (X = Z = N-1, not the maximum vertex):

| corner | N=256, stride 257, disp 0x204 | N=512, stride 513, disp 0x404 |
|---|---:|---:|
| c1 (X+1, Z) | 132094 .. 132095 | 526334 .. 526335 |
| **c2 (X+1, Z+1)** | **132096 .. 132097** | **526336 .. 526337** |
| c3 (X, Z+1) | 131582 .. 131583 | 525310 .. 525311 |
| c4 (X, Z) | 131580 .. 131581 | 525308 .. 525309 |
| buffer last valid index | 132097 | 526337 |
| **spare bytes** | **0** | **0** |

The highest byte touched is the last byte of the buffer, at both sizes. A coincidental constant
does not do that.

This also **independently validates the CORNER patch value**: `2*(N+2)` is the only displacement
that makes N=512 land exactly on `size-1`. A wrong corner constant would show up here as either an
overrun or a gap, and it shows neither.

> ⚠️ Two arithmetic traps, both of which produced wrong numbers in this investigation before being
> caught. **(1)** Using the maximum VERTEX (N) instead of the maximum CELL (N-1). This file
> previously claimed "a 4-byte margin" from `2*(N*stride + (N-1))`, which is the vertex formula and
> also ignores the corner displacement entirely. **(2)** Applying the `+0x204` corner to the last
> vertex row. It reaches (X+1, Z+1) and is only ever evaluated for cells, so it never runs at the
> vertex maximum; assuming otherwise produces a phantom 516-byte overrun at the shipped size. The
> resizable-window session hit trap (2), this session hit trap (1), and the two errors point in
> opposite directions.

**Status: NOT YET MEASURED.** The stride and corner patches have never been run. The prediction to
test is 6/6 survival at N=512, versus the measured 4/6 with size-only. Queued behind the
game-run protocol (`re/harness/GAME_PROTOCOL.md`).

### The SIZE group: four sites, not one

A targeted scan for area-sized immediates derived from 255/256/257/258 (matching capstone's real
operand values, not hex substrings) found `0x20402` at **four** places in SIMDIRT, all touching
the same `obj+0x2c` buffer:

| VA | file off | role |
|---|---|---|
| `0x100166e0` | `0x0166e0` | `operator_new` -> `obj+0x2c` (ctor `FUN_1001665c`) |
| `0x100132c3` | `0x0132c3` | `memset(obj+0x2c, 0, 0x20402)` in `FUN_10013241` |
| `0x10014159` | `0x014159` | `memset(obj+0x2c, 0, 0x20402)` in `FUN_100140d8` |
| `0x1001469f` | `0x01469f` | `memset(obj+0x2c, 0, 0x20402)` in `FUN_1001461d` |

All three memsets are `push size; push 0; push ptr; call 0x1001e48c`. Patching the allocation
alone leaves the enlarged tail never zeroed, so all four must move together.
`patch_dirtbuf.py` now patches all four and refuses if any site's immediate is unexpected.

Note the scan's `0x10000` / `0x20000` / `0x40000` hits (208 in total) are **noise** — round powers
of two used as flags, thresholds and generic buffers. Only the non-round `0x20402` is diagnostic,
precisely because 257^2 is not a round number.

### ✅ CONFIRMED with a proper harness: the patch works, and 512 becomes as stable as 192

`verify/citysize_mod_test/measure.ps1` was built to fix the two flaws that invalidated every
earlier comparison (see the retraction below, which it supersedes):

* **Real oracle.** sc3launch runs WITHOUT `-kill`; the script owns the lifetime, polls for the
  SC3U process and records when it actually vanishes. "Alive at the deadline" is a survivor.
* **Validity gate.** A run counts only if the city seeder fired. `-modlog SIMCITY.DLL:0x10003ea6`
  is required to hit, and its `a1/a2/a3` are parsed so the achieved dimensions are **confirmed,
  not assumed** (the tables below show the dims actually observed).

Deadline 40 s in all four configurations:

| # | binaries | N | valid | survived | died | death times |
|---|---|---|---|---|---|---|
| A | all shipped | 192 | 4/5 | 3 | 1 | 19.6 s |
| **B** | SIMUI only | **512** | 6/6 | **0** | **6** | **4.7 – 5.3 s** (median 5.0) |
| **C** | SIMUI + all 4 SIMDIRT sites | **512** | 6/6 | **4** | 2 | **18.2 – 26.2 s** (median 22.2) |
| D | same binaries as C | 192 | 6/6 | 5 | 1 | 21.2 s |

**B vs C is the result.** Survival goes 0/6 -> 4/6, and the death-time distributions do not
overlap at all (B max 5.3 s, C min 18.2 s). B is also remarkably tight — 6 of 6 within 0.6 s —
so the ~5 s death is deterministic, and moving it is a real effect, not variance.

**C vs D is the important control.** On *identical* binaries with only N differing, 512 survives
4/6 and 192 survives 5/6, with near-identical death times (18–26 s vs 21.2 s). Those are
indistinguishable at this sample size. Config A shows the same ~1-in-4 death on fully shipped
binaries at 192.

**Conclusion: the 257^2 x 2 buffer was the size-specific defect.** With all four sites patched, a
512-tile city is as stable as a 192-tile city on this harness, and the residual ~1-in-5 death at
~20 s affects both sizes equally, so it is a pre-existing instability rather than anything to do
with map size.

Not established: that a 512 city is *playable*. Both sizes still stop at the same 13-window modal
in this drive sequence, and the residual ~20 s death is unexplained.

### ⚠️ RETRACTED (superseded by the table above): an earlier claim that the patch does NOT help

An earlier batch read 43.7 s / 22 s / 27 s with the patch against ~5 s without, and that looked
like a large improvement. **It does not survive more runs.** With all four sites patched:

| N=512, all 4 sites patched, `-kill 90` | result |
|---|---|
| run 1 | died at 5 s |
| run 2 | died at 66 s |
| run 3 | died at 27 s |
| run 4 | died at 16 s |

A 5 s death is indistinguishable from the unpatched case. **Death time varies from 5 s to 66 s in
both configurations, so the earlier three-run comparison was measuring variance, not the patch.**

**What is solid** is the static finding: `0x20402` is exactly 257^2 x 2, it sits at four sites, and
the buffer is indexed by raw map coordinates in `FUN_1001309e` / `FUN_10013fab`. That is a real
256-tile assumption in the code regardless of what the runs say.

**What is not established** is that fixing it changes behaviour at N=512. There is at least one
other corruptor, and the noise floor of this measurement is larger than the effect being claimed.

**Before any further patch claims:** build the measurement first. Use
`re/scripts/harness_run.ps1` (fixed duration, K repeats, graded by `harness_check.py`) with
enough repeats to separate a real effect from 5-to-66-second variance, and use whether the game
exited on its own versus was killed as the oracle rather than the log's last timestamp.

### Superseded first measurement of the patch (kept for the record)

With the city size at 512 and the buffer at `0x80802`, the first batch of three runs gave
**43.7 s (survived the 45 s window), 22 s, 27 s** — against a consistent **~5 s** before the
patch. The crash is clearly pushed much later, so the buffer was a real corruptor. But it is
**not the only one**, and one further batch appeared to survive 5/5 at 512.

> ⚠️ **The survival numbers in this section are not trustworthy, and the reason is a flaw in how
> they were measured.** Runs were classified by the last timestamp in the probe log, but
> `sc3launch -kill N` terminates the game at N seconds, so a SURVIVOR's last log entry lands just
> under N. "died at 55 s" with `-kill 60` is actually a survivor. Worse, control batches came out
> inconsistent: N=192 (an untouched arm) was scored as crashing, and one N=512 run *without* the
> buffer patch was scored as surviving, where earlier batches died at ~5 s in 3 of 3.
>
> **Do not quote a survival rate from this file.** Re-measure with `re/scripts/harness_run.ps1`,
> which already exists for exactly this purpose (fixed duration, K repeats per scenario, graded by
> `harness_check.py`), and use whether sc3launch reports the game exiting on its own versus being
> killed as the oracle — not the log's last timestamp.

### The remaining route

Targeted instrumentation, no elevation needed. The strongest unverified candidate is
**SIMGEOM `FUN_1000df90`**, the occupancy-grid write at `0x1000e0ba`–`0x1000e12a`
[CONFIRMED @ 0x1000e0ce, 0x1000e0e7, 0x1000e107, 0x1000e117]: four writes (`mov byte [edx+eax],1`,
`mov [ebp+eax*4],edx`, `mov byte [edx+eax],3`, `mov [edx+eax*4],ebp`) whose loop bounds come from
a footprint **masked to a byte** (`and eax,0xff` at `0x1000dfe0` and `0x1000dffd`) with **no clamp
against the grid extents** `param_1[0x28]`/`[0x29]` (set by `FUN_1000d290` to `vt[0xcc]-1` /
`vt[0xd0]-1`). It writes both a byte and a 4-byte value that can resemble a pointer, into
per-row `operator_new` blocks that sit adjacent to other heap allocations including tree nodes.

What is needed: the loop indices and the grid extents at `0x1000e0ba` in a crashing run. `-modlog`
hooks function prologues, so it cannot hook mid-function; this needs either a prologue hook on
`FUN_1000df90` plus reconstruction, or a purpose-built detour.

## Where it appeared to die (RETRACTED — see above)

A/B with a 75 s kill window, same binary, only the radio differing:

| size | last log timestamp | outcome |
|---|---|---|
| 192 (control) | 71,058 ms | survived the window |
| 512 | 6,375 ms | process gone |

The two logs are **structurally identical** up to the divergence: both emit `setpixel_a` ×5 (the
probe caps logging at 5), then `blt_disp_3`. At 192 it reaches `blt_disp_3` hit #5 and runs on.
At 512 it logs `blt_disp_3` hits #1 and #2 and dies before #3.

`blt_disp_3` = **GZGraphicD `0x1001499c`**, one of the eight blit dispatchers in
`re/harness/gz_draw.txt`. The `setpixel_a` caller resolves to **SIMUI `0x1004F265`**, inside
`FUN_1004effa` (base + 0x26b) — the per-pixel loop that writes a bitmap sized from a *resource
image's* own `vt+0x38`/`vt+0x3c` (source `0x53244588`), i.e. a fixed-size destination, into which
a city-sized raster is then blitted.

No WER event is generated, so the process is not taking an unhandled Win32 exception through the
normal path. That is unexplained.

## The threshold is not clean

**Two distinct failure modes had to be separated first.** Some runs die at ~1.5 s, *before* the
city is seeded (seeding is at ~4.3 s). Those are the pre-existing boot transient, not the size
crash, and counting them cost two wrong readings. Classification used here:
`< 3 s` = transient (invalid run), `3–22 s` = post-city crash, `> 22 s` = survived.

| N | valid runs | result |
|---|---|---|
| 192 | 1 | survived |
| 256 | 1 | survived |
| **257** | 3 | **crashed 3/3** |
| 264 | 4 | survived 3, crashed 1 (at 11 s) |
| 272 | 2 | survived 2/2 |
| 288 | 1 | crashed |
| 320 | 1 | crashed |
| 384 | 1 | crashed |
| 512 | 3 | crashed 3/3 |

**There is no monotonic cap.** 257 fails reliably while 264 and 272 mostly work, and 264 failed
once out of four. That pattern is not a fixed-size buffer being exceeded at a specific N; it is
consistent with a **data-dependent** fault, which fits the generator being invoked with seed
`-1` (`vt+0x1c(0xffffffff, 0x40, 0x40, 0x40, 0x24)`) so each run generates different terrain.
Larger N raises the failure rate rather than switching it on.

`[UNCERTAIN]` why 257 fails 3/3 while 264/272 largely pass. An odd N is the obvious suspect
(row-stride alignment in the blit), but 288 also fails and is a multiple of 8, so a simple
alignment story does not hold either. Missing evidence: the surface dimensions and stride at the
`blt_disp_3` call, which `-modlog GZGraphicD.DLL:0x1001499c` plus the surface descriptor would give.

## Open

- **Playability at 512 is unmeasured.** Both arms stop at the same 13-window modal
  (`SIMUI.DLL+0xA4D64` frame, children `0x00000001`–`0x00000004`). Identifying and clicking
  through it is the next step, then compare in-city trees at 192 vs 512.
- The second hardcoded 256 in `0x10011dd6`'s null-dialog fallback is unpatched. Not on the
  dialog path, but it would matter to any non-UI creation route.
- N was only tested at 512. No upper bound has been searched for.

## State of the install

`Apps/SIMUI.DLL` is **currently patched to N = 272** (sha256 `acc4e06e…33965650`), the largest
size that survived every valid run. Revert with
`py -3.12 verify/citysize_mod_test/patch_citysize.py --restore`. No other game file was touched.

---

# Does a 512-tile city PLAY? One run, 2026-08-25. P1 MET, P2 MET, P3 not evaluable.

Pre-registration: `re/sessions/PREREG_512_gameplay.md`, written and saved before the launch.

**Verdict against that table: row 9 (P1) and the P2 criterion are met; row 1 applies to P3; row 7
applies to the save-confirm step; row 6's validity gate was unavailable rather than failed.**

**The headline: the engine reads, renders and re-serialises tiles at coordinates up to 495, and the
high-coordinate blocks survived BETTER than the low-coordinate control.** No crash, no coordinate
threshold, nothing changed outside the planted area.

## Patch state, before and after

| moment | SIMDIRT sha256 | reads |
|---|---|---|
| before | `f1708fc1…b070` | shipped: size `132098`, stride `257`, corner `0x204` |
| patched for the run | `7c87b9ac…05bf` | `size=526338 stride=513 corner=0x404`, 12 sites |
| after `--restore` | **`f1708fc1…b070`** | shipped values on all 12 sites |

Install `stock (matches original/)` at release; lease and harness claim both released. The
apply/restore round-trip was verified **before** the run as well, so the restore was not first
exercised on live evidence.

## What was planted, and what the file contained

`N512_city.sc3` is empty (`{0: 262144}`), so zones were planted offline with `city_write.py`
(round-trip byte-identical L0–L4 on this exact file). Four **32x32** blocks of slot 1 at origins
`(16,16)`, `(464,16)`, `(16,464)`, `(464,464)` — tiles spanning `16..47` and `464..495`.

**Histogram after planting: `{0: 258048, 1: 4096}`** — 4,096 tiles, exactly 1,024 per quadrant.

Block size was raised from 6x6 to 32x32 **before** launching, because the minimap read-off is ~80x90
px for a whole map and a 6x6 block is under one minimap pixel at `N=512`. That correction was made
by arithmetic in advance, not after a null.

## P1 — the game reads and renders tiles at high coordinates. MET.

**Confirmed twice, by two independent observers.**

1. **Direct human observation, on the live screen: "I see the 4 residential zones fine."** The owner
   was watching the run.
2. **In the captured frame, by pixel measurement.** Bright-green minimap marks (residential zone
   colour) cluster at exactly three positions of ~30 px each — `(942,626)`, `(999,683)`,
   `(942,740)` — the minimap diamond's **N, E and S** corners. A fourth 6-px green cluster at
   `(991,627)` is the layers **button**, not a map mark, and is excluded.

**The diamond's WEST corner is occluded in the composite** by main-view blits overdrawing the
minimap panel, so the fourth mark's absence from my measurement is a **capture artifact, not a
missing zone**. Three measured plus the owner's four is the honest statement; I am not claiming four
from the pixels.

Frame: `n512_planted_094120.png` (Happy share folder; a game screenshot, not committed).

⚠️ **The owner was interacting with the window during this run.** Their clicks and drags are an
uncontrolled input the capture did not account for. **Nothing in that frame about camera position or
sim state is clean.** It does not touch P1 — a rendered zone block is a rendered zone block, and the
minimap draws the whole map regardless of camera — but every other reading from the frame is
qualified by it.

## P2 — the engine's own serialiser round-trips high coordinates. MET.

The in-game Save fired and **the engine rewrote the file**: 920,821 → **922,007 bytes**, mtime moved.
Re-parsed clean: 11 records, 1 payload, 875,378 → 6,043,226 bytes, **58 sections**, `SC3WorldLayer
x1`, `SC3ZoneLayer x13`, `DEADBEEF=True`, `N = 512`. `city_roundtrip.py` **PASS L0–L4**.

So this is the engine's serialiser, not ours, writing a 512 map with tiles at 495 and producing a
file our tools re-read without complaint.

### The coordinate read-off — and it points the opposite way to the risk

| block | origin | kept | lost | lost % |
|---|---|---|---|---|
| lo-lo (**the control**) | `(16,16)` | 932 / 1024 | 92 | **9.0%** |
| hi-lo | `(464,16)` | 957 / 1024 | 67 | 6.5% |
| lo-hi | `(16,464)` | 893 / 1024 | 131 | 12.8% |
| hi-hi | `(464,464)` | **1006 / 1024** | 18 | **1.8%** |

- Changed tiles: **308**, all `1 -> 0`. Extremes **x 16..495, y 16..495**. **216** of the 308 have
  x>256 or y>256.
- **Zero tiles changed outside the four planted blocks** — nothing spurious anywhere on the 512 map.
- **The best-preserved block is `(464,464)`, the far corner, at 1.8% loss. The worst is `(16,464)` at
  12.8%. Those are diagonally opposite.** Both high-x blocks lost *less* than the low-coordinate
  control.

> **There is no coordinate threshold in this data.** A 256-assumption would damage the high blocks
> preferentially. The high blocks did better than the control.

### The 308 lost tiles are unattributed, and I am not going to guess

Two candidate explanations tested and **both fail**:

- **Not terrain.** Cross-tabulated against the SIMGEOM tile-grid plane: loss is flat at **7.3%** for
  grid value 0 (3,991 of the 4,096 tiles). Every non-zero grid value has 1–13 tiles and a noisy rate.
  No terrain class explains it.
- **Not coordinates.** See the table above.

`[UNCERTAIN]` what removed them. The live candidate I cannot exclude is **the owner's own clicks and
drags during the run**, which is exactly why that confound is declared. A roughly uniform ~7.5% loss
spread across four widely separated corners does not look like localised bulldozing, but "does not
look like" is not evidence and I am not recording a mechanism. **What matters for the 512 question is
settled either way: the loss is neither coordinate-dependent nor terrain-dependent.**

## P3 — development. NOT EVALUABLE. Pre-registered row 1.

**Population `Pob: 0`, city `Nueva ciudad`, and the funds and date fields are BLANK.** No development
anywhere, control block included — which row 1 fixes in advance as **inconclusive about 512**, not as
evidence against it.

Three independent reasons, two of them pre-registered:

1. **The sim was paused.** The status bar's pause glyph is lit beside the play triangle, and the date
   field never populated. `[UNCERTAIN]` but consistent with the only explicit record on this
   question (a menu-loaded city where "the sim is PAUSED and the date never advances").
2. **No unpause mechanism exists to drive.** There is no Pause/Speed/Resume command among the 90
   shipped menu commands; the pause/resume functions are known in code only and have never been
   driven from the harness.
3. **A bare zone has no road and no power**, and `city_write` cannot supply either — roads are
   network-layer, not the zone plane.

**The void condition fired:** the date never advanced, so rows 1–4 of the table say nothing about the
simulation. Reported as such rather than dressed up.

## Instrument outcomes, reported because they are the reusable part

**The save-confirm step SKIPPED, and by the rule fixed in advance that is a failure, not a result:**

```
GZSEQ[1]: target ready after 0 ms
GZFIRE: tile=0x12D1BF90 cmdID=0x10009002 -> FUN_1004c209 ; GZFIRE: returned 1
GZSEQ[2]: target 0x02DFDD6A never appeared within 70000 ms - SKIPPING
GZSEQ: COMPLETE (3 step(s)) at t+74156 ms
```

`### GZSEQ: COMPLETE` printed anyway — the documented trap. **Save nevertheless succeeded**, at
t+4.04 s, without the confirm dialog: firing `0x10009002` on an already-named city writes straight
through. So the recorded `fire:0x10009002` + `0x02DFDD6A` recipe carries a **superfluous second
step**, and that step costs 70 s of timeout. `[UNCERTAIN]` whether the confirm is needed on a
*newly*-named city; on this path it is not.

**The `cam` validity gate was unavailable, not contradictory:**

```
CAM: no object with vt SIMSPR+0x6250C (0x034D250C) reachable from cityView 0x12D24988
     or cityViewIso within 0x280 bytes - not reading camera state from an object we cannot identify
```

The step armed (`target ready after 2563 ms`) and then declined to read from an object it could not
identify — the right behaviour, and it means **no `512x512` witness was obtained from `cam`.** Row 6
is therefore not triggered: the map identity is anchored instead by `-filetrace` naming the fixture
directly, 29 lines, `CreateFileA "…\N512_planted.sc3" -> ok`. That is the whole reason the
bare-absolute-path fixture is preferred over the list-position dialog, and here it carried the run.

⚠️ **The `cam` map-N witness that the camera-scroll session offered for exactly this question was
therefore NOT obtained.** The drag-scroll and keyboard-scroll comparison was not run either: the
owner's report arrived after `capture.ps1` had already terminated the game at t+74.4 s, and
relaunching to chase it was declined. **"Right-click + move does nothing" at 512 is unmeasured and
remains open.**

## Coordination lesson worth keeping

`capture.ps1` killed the game at t+74.4 s while a human was actively looking at it. The script is
correct to clean up what it started, but **a run that a person is watching wants a longer `-AtSec`
or a hold**, otherwise their observations arrive after the evidence is gone. That is what happened to
observations 2 and 3.

## What is now established, and what is not

**Established at `N=512`, patched SIMDIRT:** the game loads a planted city by absolute path, renders
zoned tiles at coordinates up to 495, draws them on the minimap at all four corners, runs 74 s
without a crash, and its own serialiser writes them back into a file that re-parses as a genuine 512
map with no out-of-block damage.

**Not established:** that the simulation *advances* in a 512 city (it was paused, and there is no
recorded way to unpause); that development works at high coordinates; that camera scroll clamps
correctly at 512 (the owner reports drag-scroll dead, and it is unmeasured); and what removed 7.5% of
the planted tiles.

**Tier 2 (authoring at a far corner) was not attempted and is not blocked in principle.** The
capability is established at 256 — `fire:<toolcmd>` plus `drag:`/`at:` aimed at the city view, scored
against the funds oracle and against zone-histogram deltas — but it has never been done at 512, and
improvising it across runs was out of scope for one lease.

---

# U-081 at N=512, one run, 2026-08-25. Row B RULED OUT. The origin delta is UNRESOLVED — my sequencing error.

Pre-registration: `re/sessions/PREREG_512_gameplay.md`, U-081 addendum, written before launch.

**Verdict: pre-registered row B is ruled out — the extent is 512-derived, not 256-derived. Rows A, C
and D are all UNREACHED, because my second `cam` fired 63 ms into a 2,500 ms hold instead of after
it. The like-for-like comparison against `-6848` was not obtained.** Owned below, not buried.

The run is not wasted: `cam` was repaired and four things are now measured that were not before.

## Patch state

| moment | SIMDIRT sha256 |
|---|---|
| before | `f1708fc1…b070` (shipped) |
| patched | `7c87b9ac…05bf`, `size=526338 stride=513 corner=0x404`, 12 sites |
| after `--restore` | **`f1708fc1…b070`**, shipped on all 12 sites |

Install `stock (matches original/)`; lease and claim released.

## The three numbers, verbatim

```
### CAM: cell map found at cityViewIso+0x158 -> 0x0EEC9DB8 (vt SIMSPR+0x6250C)
### CAM: iso=0x0EEC9DB8  rectA=556,111,1580,879 span=1024x768  centre=1068,495
### CAM: rectB=556,111,1580,879 span=1024x768
### CAM: zoom=0 rot=0 tilepx=8 (8<<zoom=8)  presentGate(+0x7c)=0  flag(+0x32c)=0
### CAM: MAP 512x512 tiles  (world extent ~130816x130816 px)
```

Identical in both readings, before and after the key.

## ⭐ Row B is ruled out: the extent is computed from 512, not from 256

**`130816 = (512-1) * 0x100`.** Had the extent been 256-derived it would read **65,280**
= `(256-1) * 0x100`. It does not. `MAP` reads `512x512` and the world extent agrees with it exactly.

> **The clamp is NOT being computed from a 256 extent.** That was the leading hypothesis and it is
> now off the table. Whatever `U-081` is, it is not a stale extent.

The validity gate also passed on its own terms: `MAP 512x512`, so row F does not fire and this run is
not void.

## ⭐ The input path is NOT being dropped — the gate opens

```
### GZKEY: cityView=0x12CA3860 vt=0x03507894  +0x177=0 (before)
### GZKEY: scroll step +0x1c8=32.000  bank z4=32.000 z3=32.000 z2=32.000 z1=32.000 z0=32.000
### GZKEY: vt+0x64(vk=0x25) = 0x034E979A -> returned 0x03507A01
### GZKEY: +0x177=1 (after), flags up/down/left/right = 0/0/1/0, holding 2500 ms
```

- **The scroll gate `+0x177` went 0 → 1.** Input reached the city view and was accepted. Confounding
  explanation "input is dropped before the camera sees it" is **eliminated**.
- **The left direction flag is set** (`0/0/1/0`) — the correct one for `VK_LEFT`.
- **The scroll step `+0x1c8` is 32.000, non-zero at every zoom bank.** So this is *not* the S1
  patched-build defect where the step was 0.0f and the map "could not" move.

Gate open, flag set, step non-zero. Three of the four stages of the scroll path are confirmed
working at 512.

## The error, stated plainly

`key:` **dispatches and returns immediately** — the 2,500 ms hold runs asynchronously ("holding 2500
ms"). The following `cam` step has no target to wait for, so it reported `target ready after 0 ms` and
ran **63 ms** after the dispatch (`t+17871.98` → `t+17934.90`).

**So the "after" reading is 63 ms into a 2,500 ms hold, not after it.** The origin was unchanged at
that instant, and that is not the same statement as "unchanged after a 2.5 s hold". It cannot be
compared against the `-6848` baseline, which is a 2.5 s figure.

> **Rows A, C and D are all unreached.** Reporting "origin delta 0, row C" would have been a
> plausible-looking number produced by a broken measurement, which is exactly the failure this
> project has now hit twice (`iso+0x524`, the `Blt=0` misreading).

**The fix for the next run is one step:** `...;key:0x25,2500;wait:3000;cam` — a `wait:` longer than
the hold, between the key and the second `cam`. `wait:` is a real verb and it worked here
(`GZSEQ[0]: waited 15000 ms`).

## A lead that may matter more than the clamp: the present gate is SHUT

**`presentGate(+0x7c)=0`** in both readings, and `flag(+0x32c)=0`.

From the probe's own annotation of `FUN_10006226`: `+0x7c` gates the full-surface present — the path
requires `param_3 != 0` **and** `+0x7c != 0` before `vt+0x14c` (invalidate+paint) and then `vt+0x158`
(`0x1000e206`, present). **With `+0x7c` at 0, a camera move would not be repainted or presented even
if the origin did change.**

`[UNCERTAIN]` and explicitly not a conclusion: this is a plausible mechanism for "scrolling appears
to do nothing" that is **independent of any coordinate clamp**, and it would apply at 256 too. It is
recorded so the next run reads `+0x7c` at both N values rather than assuming the clamp.

## Instrument findings

### `cam` is repaired, and the diagnosis was the pre-registered one

Last run `cam` declined. **Cause: it ran too early.** It fired at t+3.92 s, ~0.1 s before the in-city
readiness signal. With `wait:15000` in front it found the object immediately:

```
### CAM: cell map found at cityViewIso+0x158 -> 0x0EEC9DB8 (vt SIMSPR+0x6250C)
```

**`cityViewIso+0x158`, exactly where the camera-scroll session placed `cISC3CitySpriteCellMap`, and
the same offset as at N=256.** So: **not** paused-related, **not** a wrong walk, and **not** different
at 512 — pre-registered row E resolved to "ran before the object existed". Independently
corroborated: the bridge-init hook logged `a3=0x0EEC9DB8`, the same address `cam` later found.

### `MAP WxH` needs `-resize`, and `-resize` alone does not resize

Both pre-registered instrument facts held:

- The bridge detour is armed only under `SC3PROBE_RESIZE`
  (`RZ> armed capture detour on SIMSPR!0x10016EBA`, t+71 ms; hit #1 at t+6.56 s). **Last run had no
  `-resize`, so its `MAP` number was unobtainable regardless of the camera object.**
- **Zero resizes were performed** — no `AUTO at t+` and no `resize #1` line. The auto-resize requires
  `-resizeto`, which was not passed. So `U-068`'s black-viewport path was never entered, confirmed by
  measurement rather than by hope.

### The instrument-bug report from the pre-registration stands

`cam`'s failure message names `cityViewIso` unconditionally, but that base is only searched when
`*(cityView+0xb8)` is non-null and readable. **Last run's line was an assertion, not a measurement.**
Unchanged this run; still worth fixing.

### The trailing `wait:` did not hold for 180 s

`wait:180000` was **SKIPPED at 90 s** — `GZSEQ[4]: target 0x00000000 never appeared within 90000 ms`.
A step with no `@N` inherits the 90 s default timeout, which is shorter than the wait it is asked to
perform, so a long `wait:` cancels itself. **A `wait:` longer than 90 s needs an explicit `@N` larger
than its own duration**, e.g. `wait:180000@200`. Sequence completed at t+108.5 s instead of ~t+197 s.

## Interactive window for the owner

Launched **11:04:48**. **The measurement was banked at t+17.93 s = 11:05:06.** The game then stayed up
and interactive until `capture.ps1` terminated it after the sequence completed at t+108.5 s, i.e.
**11:05:06 → ~11:06:38, about 92 seconds.**

Intended 180 s; delivered 92 s, for the `wait:` timeout reason above. Any manual right-drag in that
window is uncontrolled input and cannot confound the numbers in this section, all of which were
recorded at t+17.8–17.9 s, before the window opened.

## Where U-081 stands after this run

**Eliminated:** stale 256-derived extent (the extent is 130,816, correct for 512); input being dropped
before the camera (the gate opens and the flag sets); a zeroed scroll step (32.000 at every bank).

**Still open:** whether the origin moves over a full 2.5 s hold at 512, and by how much against
`-6848`. One run fixes it, with `wait:3000` inserted between the key and the second `cam`.

**New lead:** `presentGate(+0x7c)=0`, which would suppress the repaint irrespective of the clamp, and
which should be read at 256 as well before it is treated as a 512 finding.
