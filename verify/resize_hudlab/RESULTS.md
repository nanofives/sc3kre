# RESULTS — HUD lab run 1, 2026-08-31

**VERDICT on the pre-registered question: NO DATA. Both instruments are exonerated; the resize
faulted at step 7 and the routine aborted before step 12 ever armed the phase machine.**
Zero `HUDSURF>` lines, zero `PROF>` lines. Nothing in `PRE.md` can be scored.

**What the run bought instead: a caught, fully-localized crash with a root cause proven in the
disassembly.** The SEH catcher and the VEH logger both fired and gave registers, access address and
the caller return address. This is the third time on this workstream that the fault-catcher, not a
hypothesis, is what settled a crash.

## The run

Owner hand-drove: ~2 min in menus, loaded a city, maximized to 2048x1081.

| t | event |
|---|---|
| 114 ms | lab armed, all 4 grid-B clamps applied, producer wrap installed, sampler thread up (tid 1180) |
| 123.47 s | bridge captured (`iso = bridge+0x18 = 0x00000000` at that moment) |
| 125.59 s | stored RECT written 800x600 -> 2048x1081; `WM_SIZE 2048x1081` |
| 125.59 s | resize DEFERRED — 2125 ms since bridge capture, gate is 3000 ms |
| 126.46 s | resize runs (2990 ms after capture — the first frame past the gate) |
| 126.46 s | steps 1-6 all clean: extent, griddims, dirtygrid, gridB, render target, device surface |
| 126.47 s | **step 7 FAULT** `0xC0000005` at `SIMSPR+0xEFE3`, caught by the SEH wrap |
| 127.58 s | **second fault** `0xC0000005` at `SIMSPR+0xEFDB`, VEH only — OUTSIDE our `__try`, on the game's own path. This is what killed the process. |

Both faults: `access=READ addr=0x00000004`, `eax=0x00000000`. Callers `SIMSPR+0xF21D` and
`SIMSPR+0xFA29`.

## Root cause — `FUN_1000efa1` dereferences the NULL list terminator

⚠️ **First reading was WRONG and is recorded here as the trap.** `0xEFDB`/`0xEFE3` look like they sit
in `FUN_1000ef50` — one of the four functions the mod patches — which would have made our own clamp
the prime suspect. **`FUN_1000ef50` is 81 bytes and ends at `0xEFA1`.** The faults are in the NEXT
function, `FUN_1000efa1`, which the mod does not touch. Checking the function's length before
attributing an RVA to it is what avoided blaming our own patch.

`FUN_1000efa1` is the grid-B node **REMOVE** (unlink a node from its bucket list). Disassembled from
the untouched `original\modules\SIMSPR.DLL` `[CONFIRMED @ SIMSPR 0x1000efa1]`:

```
0efbe  8b01        mov  eax,[ecx]          ; bucket head
0efc0  85c0        test eax,eax
0efc2  741f        je   0x1000efe3         ; EMPTY BUCKET -> jumps straight into the deref
0efc5  8b30        mov  esi,[eax]          ; walk
0efc7  3b742410    cmp  esi,[esp+0x10]
0efcb  7409        je   0x1000efd6         ; found
0efcd  8bd0        mov  edx,eax            ; prev = cur
0efcf  8b4004      mov  eax,[eax+4]        ; cur = cur->next
0efd2  85c0        test eax,eax
0efd4  75ef        jne  0x1000efc5         ; loop; exits with eax == 0 when NOT FOUND
0efd6  85d2        test edx,edx
0efd8  5e          pop  esi
0efd9  7408        je   0x1000efe3
0efdb  8b4804      mov  ecx,[eax+4]        ; <<< FAULT (not found, prev != 0)
0efde  894a04      mov  [edx+4],ecx
0efe1  eb05        jmp  0x1000efe8
0efe3  8b5004      mov  edx,[eax+4]        ; <<< FAULT (empty bucket, or not found w/ no prev)
0efe6  8911        mov  [ecx],edx
0efe8  85c0        test eax,eax            ; the author DOES null-check eax here
0efea  740d        je   0x1000eff9
0eff9  c20c00      ret  0xc
```

**Both unlink sites dereference `eax` without a null check, and `eax` is exactly 0 on the
"not found" and "empty bucket" paths.** `[eax+4]` with `eax==0` is a read of `0x00000004` — the
observed access address, on both observed instructions. The `test eax,eax` at `0xEFE8` proves the
author knew the pointer could be NULL; the two unlink sites just get there first.

**Why the resize triggers it.** The caller `FUN_1000f122` computes the bucket range from the LIVE
extent origin `this+0x54`/`this+0x58` and scale `this+0x39c`/`this+0x3a0`
`[CONFIRMED @ SIMSPR 0x1000f122]` — precisely the fields step 1 rewrites. This run logged
`extent BEFORE (624,2436,1424,3036) -> AFTER (624,2436,2672,3517)`, `scale39c=0.003906
3a0=0.007407`. Nodes inserted under the OLD geometry now hash to DIFFERENT buckets, so remove looks
in a bucket the node is not in, walks to the end, and falls off it. 86 live nodes, **0 dangling** —
consistent: the list is intact, the lookup is in the wrong list.

Same *class* as the OOB bucket-index AV that Fix A repaired: a latent missing guard in the grid-B
machinery, harmless at a fixed extent, exposed the moment the view geometry changes. Fix A clamped
indices; this one needs a null guard.

## `[UNCERTAIN]` — this may also be the open zoom-after-resize crash

The board's remaining shipping blocker is "zooming in after a resize CRASHES", uninstrumented.
A zoom changes the same scale fields `+0x39c/+0x3a0`, which is the same stale-bucket mechanism.
**Not asserted** — it needs the VEH logger to catch a zoom crash and name the address. Worth testing
because it is nearly free: the logger is already installed.

## Proposed fix (designed, NOT built, NOT tested)

Two edits, both SIMSPR-internal and base-invariant, in the existing fail-closed `g_clamps[]` style:

1. **In place, 2 bytes, no cave.** `0xEFC2` `je 0xEFE3` -> `je 0xEFF9` (`74 1f` -> `74 35`). Empty
   bucket means nothing to unlink, so return. Same instruction length. Stack is balanced: this path
   never pushed `esi`.
2. **One cave hooked at `0xEFD6`**, stealing the 5 bytes `85 d2 5e 74 08`, adding the missing guard:
   `pop esi` / `test eax,eax` / `je -> 0xEFF9` / `test edx,edx` / `je -> 0xEFE3` / `jmp -> 0xEFDB`.
   Stack balanced against the original (which also pops `esi` before reaching `0xEFF9`), and the
   found-node paths are unchanged. `0xEFD6` is a branch target (`0xEFCB je 0xEFD6`) — landing on the
   hook jmp is fine.

Skipping the unlink when the node is absent is the correct semantic, not merely a crash suppressor:
there is nothing in that bucket to remove.

## Secondary observation

The resize fired 2990 ms after bridge capture — the first frame past the 3000 ms readiness gate,
with `iso` still 0 at capture time. Not the root cause (the mechanism above is geometry-driven, not
timing-driven), but a later gate would give the city more time to settle and is a cheap control if
the fix needs one.

## Status

- HUD lab: **built, armed, unexercised.** Instruments are not implicated in the crash and need no
  change. The run is repeatable as-is once the resize survives step 7.
- New engine defect: **root-caused in the disassembly, fix designed, not built.**

---

# RUN 2 (2026-08-31) — FIX C **PASSES**; I1 **H SUPPORTED**; I2 no data

## FIX C: PASS, scored exactly as pre-registered

Resize to 2048x1081 on a hand-loaded city. **All of steps 1-11 completed, plus step 12.
Zero `FAULT CAUGHT`, zero `*** VEH FAULT ***`** other than the known-benign startup `0xC0000096`.
Step 8c re-showed **65536 cells, 0 bad**; step 11 restored the active layer.

That is the pre-registered PASS condition verbatim, against the exact fault FIX C targets. Both
parts applied with their fail-closed checks passing (`GRIDB_CLAMP FUN_1000efa1`, `EFA1_GUARD`).

**The engine's grid-B node REMOVE no longer faults when the resize invalidates its bucket mapping.**

## I1 — the child surfaces: H SUPPORTED, decisively

`HUDSURF> BEFORE-setrect`, HUD `ownrect=[0 544 599 600]`, class vtable `0x034840EC`:

| child | class | dims | bpp | pitch | coherence | non-zero |
|---|---|---|---|---|---|---|
| `[0x2a]` | RASTER `gz+0x1E894` | **600x56** | 16 | 1200 | COHERENT (= w*2) | 25525/33600 |
| `[0x2b]` | RASTER `gz+0x1E894` | 16x64 | 16 | 32 | COHERENT | 1024/1024 |
| `[0x2c]` | RASTER `gz+0x1E894` | 136x18 | 16 | 272 | COHERENT | 2448/2448 |
| `[0x2d]` | RASTER `gz+0x1E894` | 112x18 | 16 | 224 | COHERENT | 2016/2016 |
| `[0x2e]` | RASTER `gz+0x1E894` | 104x18 | 16 | 208 | COHERENT | 1872/1872 |
| `[0x2f]` | RASTER `gz+0x1E894` | 148x18 | 16 | 296 | COHERENT | 2664/2664 |

**All six are `GZGraphicD+0x1E894` rasters. Every pitch is exactly `width * 2` (fix16). Every one
holds real content.** Six for six, no refusals, no incoherent reads.

⛔ **This retires the 2026-08-31 "three layers of the model are wrong / unknown class" conclusion in
`verify/resize_hud/RESULTS.md`.** The class was never unknown — it is the raster surface family this
project mapped long ago and which `rz_census_one` already read. The earlier diagnostic probed
widget-shaped fields (`+0xe0` rect, `vt+0xcc` set-position) on surface-shaped objects and correctly
got garbage; the objects were fine, the questions were wrong. `vt+0xcc` resolving to a flag getter
and `+0xe0` reading garbage are exactly what a raster surface should produce.

**The reflow target is now a named object.** The bar's background is a **fixed 600x56 raster** inside
a window whose own rect is 599 wide. It cannot span 2048 because its backing surface is 600 px wide.
Making the HUD adapt means resizing *that surface* — and the mod already owns proven machinery for
exactly this class: `rz_replay_create` drives `FUN_10009efb` (Init, `vt+0x0c`) on `iso+0x74` and
`iso+0x4ec`, the same vtable family, every resize.

## I2 — profiler: no data (run ended mid-phase-A)

Phase A started at t+21.13 s. At t+27.52 s the window was restored to 800x600 and the process ended
— **6.4 s into a 10 s phase**, before the `PROF> A-native` dump. No widen, no phase B, no profile.
The bar was never widened this run, so nothing about the FPS question can be scored either way.

The instrument itself is uncontradicted: the sampler thread started (tid 38260) and the phase machine
armed and fired on schedule. It needs a run left undisturbed for ~25 s after the maximize.

## What run 2 settles and what it does not

- **Settles:** FIX C works. The HUD children are coherent fixed-extent rasters of a known class, and
  the specific surface blocking a full-width bar is child `[0x2a]`, 600x56.
- **Does not settle:** the FPS cost. Still unmeasured, still the open question from run 1.
- **Untested:** whether FIX C's non-unlink leaves stale nodes in old buckets (see PRE.md "not
  claimed"). No visual artefact was reported, but nothing probed for one.

---

# RUN 3 (2026-08-31) — I2 **PASS, cause named**. The "intrinsic composite cost" conclusion is REFUTED.

Both phases ran to completion undisturbed. `A-native`: 6232 samples, 530 distinct buckets, 0 probe
failures. `B-fullwidth`: 6199 samples, 204 distinct buckets, 0 probe failures. Sample counts are
comparable and far above the 200 VOID floor. `HUD SetRect [0,544,599,600] -> [0,1025,2048,1081]`
landed between them, so the only variable across the two profiles is the bar's width.

## The delta is concentrated in three buckets — pre-registered PASS

Addresses resolved against the **live process** module list while it was still running, then to
nearest exported symbol in the on-disk 32-bit binaries.

| bucket | resolves to | A-native | B-fullwidth | delta |
|---|---|---:|---:|---:|
| `0x77939AC0` | `ntdll+0x79AC0` (WoW64 syscall stub) | 2148 (34.47%) | **3835 (61.86%)** | +1687 |
| `0x757E3840` | **`win32u!NtGdiDdDDIWaitForSynchronizationObject`** | 453 (7.27%) | **875 (14.12%)** | +422 |
| `0x77939E80` | `ntdll+0x79E80` (syscall stub) | 289 (4.64%) | **630 (10.16%)** | +341 |

Three buckets account for **+2450 samples**, the overwhelming majority of the shift. That satisfies
the pre-registered PASS: *"a small number of buckets (<= 5) account for the majority of the increase,
resolving to nameable MODULE+RVA sites."*

⚠️ The two `ntdll` names a nearest-export lookup returns (`ZwWorkerFactoryWorkerReady`,
`ZwCloseObjectAuditAlarm`) are **not** meaningful. ntdll's `Zw*` stubs are identical contiguous
16-byte syscall thunks, so nearest-export lands on an arbitrary neighbour. Both addresses are hot in
*both* phases, which is what a shared syscall/WoW64 transition point looks like. **Do not cite those
two names as the functions being called.** `win32u` is unambiguous and is the load-bearing one.

## What moved the OTHER way — this is what makes the reading decidable

| bucket | resolves to | A-native | B-fullwidth |
|---|---|---:|---:|
| `0x757E3780` | `win32u!NtGdiDdDDISubmitCommand` | 111 (1.78%) | 57 (0.92%) |
| `0x6489A600` | `nvd3dum+0x163A600` (NVIDIA UMD) | 351 (5.63%) | 22 (0.35%) |
| `0x6489A640` | `nvd3dum+0x163A640` | 279 (4.48%) | absent |
| `0x6489A700` | `nvd3dum+0x163A700` | 222 (3.56%) | 7 (0.11%) |

**GPU work SUBMITTED went down. Time in the NVIDIA user-mode driver collapsed. Distinct buckets fell
530 -> 204.** The thread is doing less varied work and sitting in one place more.

## Conclusion: the cost is a GPU synchronization STALL, not CPU compositing

The render thread is **not** burning more CPU compositing a wider bar. It is **blocking longer on a
D3D kernel synchronization object** — `NtGdiDdDDIWaitForSynchronizationObject` doubles, submissions
fall, driver work collapses, and syscall-stub residency nearly doubles.

⛔ **This refutes the standing conclusion in `verify/resize_hud/RESULTS.md`:** *"the full-width HUD
bar's FPS cost is intrinsic to this engine's per-frame compositing... Removing it would mean changing
the compositor."* That was reached by elimination after three falsified hypotheses, and it named the
wrong mechanism. A CPU-compositing cost would show as more time in the blitter (SIMSPR / GZGraphicD /
nvd3dum). The measurement shows the opposite: **less** time there and more time waiting.

`[UNCERTAIN]` — the *reason* the wider bar induces the wait is not established. A plausible and
untested mechanism is that the widened bar region forces a CPU touch of a surface the GPU still has
work pending on, serialising CPU and GPU each frame. **Not asserted.** What is measured is the wait
itself, and that it scales with bar width.

**Why this matters for the goal:** "change the compositor" was the reason the HUD-scaling goal was
declared unreachable. A synchronization stall is a different and much more tractable class of
problem than a compositor rewrite.

⚠️ **Not yet confirmed: that the owner perceived the FPS drop during phase B of this run.** The
pre-registration makes owner perception the ground truth the instrument must match. The profiles
differ strongly, which is consistent, but the confirmation has not been collected. Ask before
treating the FPS drop and this measured stall as the same event.

## Method note, in credit rather than in scorecard (run 3)

The address resolver in the mod only knows the six game modules, so all three hot buckets logged as
`(no known module)` and the run looked uninterpretable at first glance. They were resolved by
querying the **still-running** process's module list, then mapping to nearest export offline.
Reading the profile before closing the game is what saved the run.

---

# RUN 4 (2026-08-31) — HUDFIT: PARTIAL as pre-registered. H-fps is CONFOUNDED, not falsified.

Owner: **"bar spans with black areas, FPS still drops."**

## Visual: PARTIAL — the surface widened, but with NO BACKING

| | before | after |
|---|---|---|
| child `[0x2a]` dims | 600x56 | **2048x64** |
| `sub` | `0x0F7915A0` | `0x0F7A5970` (new) |
| `bits` / `pitch` | `0x0C1F3BD8` / 1200 (COHERENT) | **`0x00000000` / 0 (INCOHERENT)** |
| non-zero | 25525/33600 | 0/0 |

`FUN_10009efb -> 1` and the dims were written, so the recreate itself succeeded. But the new
sub-object has **no allocated backing**, so the tile step correctly refused:
`HUDFIT> recreate OK but the new backing is unreadable (bits=0x00000000 pitch=0) - not tiling`.
That is the guard doing its job — it declined to write into a null pointer and said so — and it is
the pre-registered **PARTIAL (blank bar)** outcome. The black areas are a 2048-wide surface with
nothing in it.

**Most likely cause, and it is cheap to test: the backing is allocated LAZILY, and the census ran
microseconds after the recreate.** `iso+0x74` takes the identical call with the identical tuple
(`[_ _ 7 16 0 0 0 0]`) and does have bits — but it is censused ~2 s later, after frames have drawn
into it. `[UNCERTAIN]` — not established, and the alternative (the HUD surface needs a create
parameter the field read-back does not recover) is not excluded. Note the tuple came from field
read-back, which the log itself flags as **not proven equivalent** to a recorded create.

## H-fps: CONFOUNDED. Do NOT record it as falsified.

The tempting read is "the surface matched the window at 2048 and the drop persisted, so H-fps is
dead." **That is not what was tested.** During phase B the surface had 2048 in its dims field and
**no allocated backing at all**. A surface with no pixels is not "a surface matching the window" —
it is a third state neither arm of H-fps describes.

**H-fps remains open and needs a re-run with a genuinely backed 2048-wide surface.** Declaring it
dead here would be exactly the error this board has logged repeatedly: scoring a hypothesis against
a test that did not implement it.

## What run 4 DID establish independently: run 3 replicates

| bucket | A-native | B-fullwidth |
|---|---:|---:|
| `ntdll+0x79AC0` (syscall stub) | 44.43% | **57.50%** |
| `win32u!NtGdiDdDDIWaitForSynchronizationObject` | 9.86% | **12.73%** |
| `ntdll+0x79E80` (syscall stub) | 6.39% | **8.47%** |
| distinct buckets | 417 | **244** |

Same three buckets, same direction, same bucket-count collapse, on a separate run with a different
process. **The GPU sync stall finding from run 3 is reproduced.** It is not a one-run artefact.

Note this also means the stall does **not** depend on the bar surface holding content — it happened
with an empty 2048 surface too.

## Next step (small, targeted)

Defer the tile write until the backing exists: after the recreate, poll for `sub+0xf0 != 0` on later
frames (the same pattern `g_census_ms` already uses) and tile then. That fixes the black bar if the
lazy-allocation reading is right, and if the bits never appear, that itself falsifies the reading and
points at the create tuple instead. Only then is H-fps testable on a genuinely backed surface.

## Status after run 4

- FIX C: PASS, holding across runs 2-4.
- HUD child class + reflow target: settled (run 2).
- GPU sync stall: **measured and now replicated** (runs 3 and 4), owner-confirmed.
- Bar background surface: widens, but comes back with no backing. Tiling untested.
- H-fps: **open**, needs a backed surface to test.

---

# STATIC READ (2026-08-31) — why the widened surface had no backing. Tuple EXONERATED.

Asked to investigate the create tuple before building anything. **The tuple is not the cause, and
the real mechanism is now proven statically, end to end.** No lease was needed; the sub-object
vtable was parsed straight from `original\modules\GZGraphicD.dll` (project rule: vtables are static
`.rdata`, do not open Ghidra, and `globals.csv` vftable rows lie).

## The allocation chain

`FUN_10009efb` (Init, raster `vt+0x0c`) writes the fields and delegates:
`vt+0x1dc` (`FUN_1001420d`) -> `vt+0x1e0` (`FUN_100142a2`) -> `sub->vt[0x40]`.

`FUN_100142a2:23` calls the allocator with **only** width (`this+0x24`), height (`this+0x28`), the
format block (`this+0x0c..0x18`), `this+0x3c` and `this+0x40` — exactly the tuple we replay.

## Sub-object vtable, read from the PE (`PTR_FUN_1001f0ac`, RVA `0x1f0ac`)

| slot | target | role |
|---|---|---|
| `vt+0x0c` | `FUN_10018a82` | **Lock** |
| `vt+0x10` | `FUN_10018b53` | **Unlock** |
| `vt+0x40` | `FUN_10019273` | **Create** (DirectDraw surface) |

## The finding: bits/pitch come from the LOCK, never from CREATE

`FUN_10019273` (create) builds the DirectDraw surface and on success sets `sub+0xec = param_4` and
`sub+0xe0 = 1`. **It never writes `sub+0xf0` or `sub+0xf4`** `[CONFIRMED @ GZGraphicD 0x10019273]`.

`FUN_10018a82` (lock) is where they appear. It refcounts on `sub+0xe4` and, on the 0->1 transition,
calls `IDirectDrawSurface::Lock` (COM vtable `+0x64`) with a `DDSURFACEDESC` at `sub+0x0c`
(`dwSize = 0x6c` is written by the create), then copies out
`[CONFIRMED @ GZGraphicD 0x10018a82]`:

| written | from | DDSURFACEDESC field |
|---|---|---|
| `sub+0xf0` = **bits** | `sub+0x30` | `lpSurface` (DDSD+0x24) |
| `sub+0xf4` = **pitch** | `sub+0x1c` | `lPitch` (DDSD+0x10) |

The offsets line up exactly with the documented `DDSURFACEDESC` layout against a struct base of
`sub+0x0c`. That is the confirmation, not a coincidence of two plausible numbers.

**So `bits == 0` immediately after a recreate is the CORRECT, EXPECTED state for every surface of
this class, the render target included.** Run 4 measured the surface microseconds after creating it
and before anything locked it. The create tuple never had anything to do with it.

## Bonus: this mechanically explains an older observation, and refines a standing rule

`FUN_10018b53` (unlock) drops the refcount and calls `IDirectDrawSurface::Unlock` — but **it does not
clear `sub+0xf0`.** The stale pointer stays readable.

That is exactly why the board recorded *"the bits were always present; the out-of-band `vf1c` lock
was tearing the backing down"*. Both halves now have a mechanism: raw reads keep working because
unlock leaves the pointer behind, and an out-of-band unlock is destructive because it drops the depth
to 0 and invalidates a pointer the engine is mid-use of. **The rule "read `sub+0xf0/f4` RAW, never
call the lock out of band" stands — but the reason is refcount inversion, not the bits vanishing.**

## Consequence for the fix — and a new risk worth pre-registering

Writing tiled art into the widened surface **requires holding a lock**. Two routes:

1. **Deferred poll** (the plan before this read): wait for `sub+0xf0 != 0`, then write.
   ⚠️ **New risk this read exposes: it may never fire.** The bar surface only gets a lock when
   something draws *into* it, and the HUD is built once. Per-frame compositing **blits from** the
   surface, which needs no CPU lock. So the poll could wait forever. That is now a predictable
   outcome rather than a surprise.
2. **Drive a balanced lock ourselves** — `sub->vt[0x0c]` to lock, write the tiled art, `sub->vt[0x10]`
   to unlock. This is the designed API and it is refcounted, so a balanced pair nests safely with
   engine usage. It is also the direct route and does not depend on the engine ever repainting.

Route 2 is the better bet on this evidence. It must still be `[UNCERTAIN]`-flagged and
expect-or-refuse gated: nothing here proves the bar surface is lockable at an arbitrary moment on the
render thread.

---

# RUN 5 (2026-08-31) — lock/tile **PASSES**. H-fps **FALSIFIED**, properly this time.

Owner: **"Bar has art now, FPS still drops."**

## Visual: PASS, exactly as pre-registered

```
HUDFIT> bar background child[0x2a]=0x0F477008 600x56 pitch=1200 -> widening to 2048x56
HUDFIT> lock vt+0x0c=0x02F98A82 -> 1 | depth=1 bits=0x0C09FFE0 pitch=4096
HUDFIT> tiled the 600x56 art across 2048x64 (pitch 4096, 114688 px written)
HUDFIT> unlock vt+0x10 -> 1 | depth now 0
HUDSURF> AFTER-setrect child[0x2a] ... dims=2048x64 ... pitch=4096 (COHERENT vs w*2=4096)
         | non-zero 86366/131072
```

Every number checks out independently:

- **lock returned 1** and produced `bits`/`pitch` where the create had left zeros — the static read's
  prediction, confirmed in the running game.
- **pitch 4096 = 2048 x 2** (fix16), COHERENT.
- **114688 px written = 2048 x 56** exactly — the tiled region, to the pixel.
- **depth 1 -> 0**: the lock/unlock pair is balanced. We never dropped below our own level.
- **non-zero 86366/131072**: the source was 25525/33600 (76%). Tiling 600-wide art across 2048 gives
  3 full tiles plus a 248-px partial; 25525 x (2048/600) ~= 87,100, and 86366 is that minus the
  partial tile's shortfall. The content count is arithmetically consistent with the tiling actually
  performed.

**The HUD bottom bar now docks to the bottom, spans the full window width, and carries its art.**

## H-fps: FALSIFIED — and this time the test implemented the hypothesis

Run 4 could not score H-fps: the surface had 2048 in its dims and **no backing**. This run the
surface is genuinely backed at 2048, coherent pitch, real content — the exact condition H-fps needs.

**The drop persists.** So the window/surface size mismatch was **not** the cause of the GPU sync
stall. H-fps is dead, on a test that actually implemented it.

Combined with run 4's finding that the stall occurs even with an **empty** bar surface, two
properties of the stall are now established:

1. it does not depend on the bar surface holding content;
2. it does not depend on the surface being the wrong size.

**What remains: the stall scales with the bar's WIDTH itself.** That is now the whole hypothesis
space, narrowed by two eliminations that were each measured rather than argued.

## Where the FPS question stands

Measured twice (runs 3 and 4), owner-confirmed, localized to
`win32u!NtGdiDdDDIWaitForSynchronizationObject` with submissions and driver time falling. Two
candidate causes eliminated. Still unknown: **what the render thread is waiting FOR.**

The next instrument is the obvious one and follows the same logic that made the EIP profiler work:
**sample the CALL STACK, not just EIP.** A few return addresses per sample, filtered to known
modules, would name the engine-side caller that leads into the wait. EIP alone says where the thread
is; the stack says who put it there — and that is what makes the stall actionable.

## Status of the HUD goal

- **Adapts (dock + span full width, with art): ACHIEVED**, this run.
- **Scales (widgets repositioned/resized within the bar): not attempted.** The 5 small child
  surfaces are still at their native sizes and native positions.
- **FPS cost: unresolved**, but two hypotheses down and the mechanism measured rather than assumed.

---

# RUN 6 (2026-08-31) — ship path CONFIRMED. Second-resize verification NOT performed.

## Ship path: works, end to end, with no environment variables set

```
RZ    size change: client 2048x1081 vs render target 800x600
HUDLAB> HUD SetRect [0,544,599,600] -> [0,1025,2048,1081]
HUDFIT> cached the pristine native art 600x56 pitch=1200 (one-time)
HUDFIT> bar background child[0x2a] -> refitting to 2048x56 (art 600x56)
HUDFIT> lock vt+0x0c -> 1 | depth=1 bits=0x0BEE5890 pitch=4096
HUDFIT> tiled the 600x56 art across 2048x64 (pitch 4096, 114688 px written)
HUDFIT> unlock vt+0x10 -> 1 | depth now 0
```

No faults, no refusals. The producer wrap installs without the lab, `g_hud_top` is captured, step 12
docks and refits on the render thread, and the art cache is taken once. **The dock+span is now a
property of the mod, not of a diagnostic harness.** Game ran ~54 minutes before the resize, so this
also exercises a long-settled session rather than a fresh load.

## ⚠️ What this run does NOT verify — and it is exactly what it was designed to verify

**The log contains ONE `size change`.** The run was pre-registered to drive **three** (maximize ->
restore -> maximize) because the two bugs fixed in this build can only appear on the SECOND resize:

1. bar height growing 8 px per resize (`56 -> 64 -> 72 ...`);
2. re-tiling already-tiled art, compounding seams.

A single maximize passes **whether or not those fixes work**. `refitting to 2048x56` shows the first
refit uses the cached native height, which is consistent with fix 1 — but the failure mode is
*accumulation*, and one iteration cannot show accumulation. The shrink path (`liveW == oldw` guard)
is likewise untested.

**Status of both fixes: written, reasoned, NOT verified.** They must not be described as confirmed
until a multi-resize run exists. Recording this rather than letting a clean-looking single-resize log
stand in for the test that was actually specified.

## Status

- Ship path (dock + span + art, no env vars): **CONFIRMED**.
- Second-resize behaviour (height stability, seam stability, shrink re-fit): **UNVERIFIED**, one
  hand-run away.
- FPS cost: unchanged and still open (runs 3-5).
