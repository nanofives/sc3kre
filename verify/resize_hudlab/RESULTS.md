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

---

# RUN 7 (2026-08-31) — wait attribution: **INCONCLUSIVE**. The scan is matching data, not frames.

Both phases collected well above the floor (A: 5771 attributed / 500 no-game-frame; B: 6005 / 282),
so this is not VOID. It is the pre-registered **INCONCLUSIVE** outcome, and the instrument's own
output is what establishes that.

## The disqualifying evidence: impossible "return addresses"

| rank | A-native | B-fullwidth |
|---|---|---|
| #01 | `SC3U.exe+0x41000` **29.39%** | `SC3U.exe+0x41000` 2.65% |
| #02 | `SC3U.exe+0x41237` 0.88% | `GZGraphicD+0x180FF` 1.08% |
| #03 | `GZGraphicD+0x21FA` 0.54% | **`SC3U.exe+0x9`** 0.82% |
| #04 | `SC3U.exe+0x39237` 0.45% | `SC3U.exe+0x80000` 0.67% |

Three entries cannot possibly be return addresses:

- **`SC3U.exe+0x9`** is inside the **DOS header**. Nothing calls from the PE header.
- **`SC3U.exe+0x41000`** and **`SC3U.exe+0x80000`** are **page-aligned**. A return address points
  *after* a call instruction; landing exactly on a page boundary is the signature of a base pointer
  or an allocation value, not a frame.

`+0x9` alone settles it. **The first in-module value above `Esp` is frequently not a return address
at all** — it is whatever spilled local, pointer or constant happens to sit at the top of frame and
coincidentally falls inside a module's range. The heuristic has no way to tell those apart, and the
ranking is therefore contaminated throughout, not just at the top.

## Why the B ranking cannot be mined either

B is **flat**: the highest entry is 2.65% and the rest sit under 1.1%. There is no concentration
comparable to the EIP profile's 61.86%. Some plausible-looking engine addresses do appear in B and
not in A (`GZGraphicD+0x180FF`, `SIMSPR+0x42ADC`, `SIMSPR+0x72B8C`), and it would be easy to write
those up as the lead.

**Doing so would be the exact error the pre-registration warned about, made worse by an instrument
that has failed its own validity check.** A ranking containing `SC3U.exe+0x9` has no earned
credibility at rank 6 either. Not mined, deliberately.

Note also that the top A entry *dropped* from 29.39% to 2.65% in B — a large differential pointing
the wrong way for a stall cause, and further sign the signal is ambient rather than causal.

## The fix, and it is cheap

Validate each candidate as a real return address before bucketing: **check that the bytes
immediately preceding it are a call.** Walk back and accept only if a `call rel32` (`E8`, 5 bytes) or
a `call r/m32` (`FF /2`, 2-7 bytes) ends exactly at the candidate. That is the standard test and it
would have rejected all three impossible entries above outright — `+0x9` is not preceded by code at
all.

Also worth adding: require the address to lie in an **executable section**, not merely inside the
module image. `+0x41000` page-aligned in a data section would die to that check alone.

## Status

- Wait attribution: **not achieved.** Instrument needs return-address validation before it can be
  trusted; the current ranking must not be cited.
- The EIP-level finding from runs 3-5 is untouched by this - it never depended on the stack scan.
- Recorded as a method note: a stack scan without call-site validation produces a confident-looking
  ranking made largely of data. It looked like a working instrument until its output was checked
  against what a return address can physically be.

---

# RUN 8 (2026-08-31) — validation WORKS; attribution still INCONCLUSIVE, now for a diagnosable reason

## The validator did its job

Every entry in both rankings is now a plausible code address. No page-aligned values, no
`SC3U.exe+0x9`, no header offsets. The run 7 contamination is gone.

## But the attribution is biased against exactly the samples we care about

| phase | attributed | no-game-frame | miss rate |
|---|---:|---:|---:|
| A-native | 717 | 5550 | **89%** |
| B-fullwidth | **240** | 6146 | **96%** |

**Phase B attributed FEWER samples than phase A** (240 vs 717), despite both collecting ~6200
samples. That is the opposite of useful, and the reason is structural:

Runs 3-5 showed that in phase B the thread spends **62% of its time inside a syscall wait**. Deep in
a kernel transition the nearest game-side frame is **further up the stack than our 1024-byte scan
window**. So the waiting samples systematically find no game frame and land in `no-game-frame`,
while the samples we DO attribute are disproportionately the ones where the thread is *not* waiting.

**The instrument is attributing the complement of the population under investigation.** B's ranking
largely describes what the thread does when it is NOT stalled - which is precisely not the question.

## A pre-registration weakness, recorded against myself

I set the VOID guard at "< 200 attributed samples". B returned **240** and therefore passes by the
letter. **The floor was the wrong guard for this failure mode**: it checks quantity, not whether the
attributed samples are the ones being asked about. A sample-count threshold cannot detect selection
bias. The 89% -> 96% miss-rate asymmetry between phases is the signal that mattered, and I did not
pre-register it.

Scoring this INCONCLUSIVE on the substance rather than PASS on the technicality.

## The fix, and it is small

- **Raise `STK_BYTES` substantially** (1024 -> 8192). The game frame during a wait is above the
  kernel transition frames; the window simply has to reach it.
- **Record several validated frames per sample**, not just the first, so a caller chain survives
  rather than one nearest hit.
- **Pre-register the miss rate as a scoring criterion**: if phase B's miss rate is not brought down
  to roughly phase A's, the attribution is still biased and the result is INCONCLUSIVE regardless of
  how many samples were collected.

## Not mined

`SIMCITY.DLL+0xD3ED` tops B at 16.67% (40 samples). It is not cited as a lead: it comes from the
biased non-waiting population, on 40 absolute samples, from an instrument that has now been
INCONCLUSIVE twice. The bar for naming a caller has not been met.

## Status

- Return-address validation: **working**, keep it.
- Wait attribution: **still not achieved**, cause of failure now understood and cheap to fix.
- Everything from runs 3-5 stands; none of it depended on the stack scan.

---

# RUN 9 (2026-08-31) — blit timing: **the regression is localized to ONE object**

Structurally sound: 23768 intervals in A, 12749 in B, **zero outliers** in either. The A/B comparison
is valid (this is the check run 8 failed).

## The result

| | A-native | B-fullwidth | change |
|---|---|---|---|
| `obj=0x0F7AFC70` calls | 19849 | 12475 | **-37%** |
| `obj=0x0F7AFC70` avg | **0.400 ms** | **0.779 ms** | **x1.95** |
| `obj=0x0F7AFC70` share of window | 79.5% | **97.1%** | +17.6 pts |
| `obj=0x00567528` avg | 0.875 ms | 2.233 ms | x2.55 (calls 1082 -> 116) |
| `obj=0x0F7B1110` avg | 1.187 ms | 1.271 ms | flat (calls 914 -> 16) |

**One object, `0x0F7AFC70`, is the whole story.** Its per-call interval nearly doubled, it now
consumes 97.1% of the phase window, and the blit rate fell 37% (1985/s -> 1248/s) — which is the
owner-reported FPS drop, measured.

## The most useful part is a NEGATIVE

**The bar's own surface does not appear as a hot blit.** No object with `2048x56` dims shows up
anywhere in the ranking, in either phase. If the cost were "an extra wide bar blit each frame", that
is exactly where it would appear, and it does not.

So the mechanism is **not** the bar being drawn. It is that the **main per-frame blit became
2x slower while the bar is wide.** That reframes the problem: the bar's width is degrading something
else, not adding work of its own. No amount of stack-scanning would have suggested this.

## Limitation, stated plainly — this instrument cannot say WHERE inside the interval

The metric is *interval between consecutive heartbeat entries*, attributed to the previous call. For
the dominant object that is effectively frame time. **It does not distinguish "the Blt call itself
got slower" from "something after the Blt, before the next one, got slower."**

So the honest claim is: *the interval following `0x0F7AFC70`'s blits doubled*, NOT *that blit got
slower*. Distinguishing them needs **entry AND exit timing** (hook the return), which is a small
increment on the existing hook and is the obvious next step.

`[UNCERTAIN]` — `0x0F7AFC70`'s identity. It printed no dims, which means its vtable is neither
`gz+0x1E894` nor `gz+0x1F328`, so it is not a raster of the two classes we know. Identifying it is
one added log line (dump `*(DWORD*)obj` and resolve to `MODULE+RVA`). **Do not guess what it is** —
the low-address `0x00567528` sits in the same range as the device surface seen in earlier runs
(`iso+0x4ec = 0x00547970`), but `0x0F7AFC70` is heap-range and unidentified.

## Status

- Blit timing instrument: **works**, structurally sound, zero outliers. Keep it.
- Regression localized to one object and quantified (x1.95 interval, -37% throughput).
- Bar's own blit **excluded** as the cost — a real elimination.
- Next, in order: (1) log the dominant object's vtable to identify it; (2) add entry/exit timing to
  split "inside the blit" from "after the blit".

---

# RUN 10 (2026-08-31) — **INSIDE**. The cost is in the DirectDraw blit itself. Object identified.

## The split: INSIDE, unambiguously

| | A-native | B-fullwidth | change |
|---|---:|---:|---:|
| inside-Blt calls | 26116 | 11693 | **-55%** |
| inside-Blt **avg** | **0.2930 ms** | **0.7482 ms** | **x2.55** |
| inside-Blt share of window | 76.5% | **87.5%** | +11 pts |
| dominant object interval avg | 0.330 ms | 0.793 ms | x2.40 |

**In phase B, inside-Blt total (8749.0 ms) is 99% of the dominant object's total interval
(8835.9 ms).** Essentially the entire frame interval is spent inside `IDirectDrawSurface::Blt`.

That is the pre-registered **INSIDE** outcome. `AFTER` is excluded: the interval did not grow around
a flat blit, the blit itself grew and grew by the same factor (x2.55 vs x2.40).

**Two independent instruments now agree.** The EIP profiler said the thread blocks in
`NtGdiDdDDIWaitForSynchronizationObject`; this says the time is inside the DirectDraw blit. A GPU
sync wait inside `Blt` is exactly what produces both readings. They were built on different
principles (sampling vs direct timing) and converge.

## Identity: the blitters are surface SUB-OBJECTS

Run 9's unidentified `0x0F7AFC70` printed no dims because it is not a raster at all:

```
BLT> A-native #01 obj=0x0F77E068 vt=GZGraphicD.dll+0x1F0AC calls=22229 avg=0.330 ms
BLT> A-native #02 obj=0x00567528 vt=GZGraphicD.dll+0x1F628 calls=1287  avg=1.115 ms
```

**`GZGraphicD+0x1F0AC` is `PTR_FUN_1001f0ac` - the exact sub-object (DirectDraw surface) vtable
parsed from the PE earlier in this session** for Lock/Unlock/Create. So the objects doing the
blitting are the surface wrappers, not the rasters that own them. `0x00567528` carries a different
class, `+0x1F628`.

The dominant blitter `0x0F77E068` is the same object in both phases (22229 calls in A, 11147 in B),
so it is the main scene blit - and it is the one that slowed down.

## What is NOT yet known

**Which surface `0x0F77E068` belongs to, and why its blit costs 2.55x more when an unrelated bar is
wide.** No mechanism is claimed. Two cheap reads settle the next question, both from structure
already decoded this session:

- **Owner raster:** `FUN_100142a2:41` writes `*(sub+0xe8) = the owning raster`
  `[CONFIRMED @ GZGraphicD 0x100142a2]`. One read gives the owner, hence its dims.
- **Memory class:** the `DDSURFACEDESC` sits at `sub+0x0c` and `DDSCAPS.dwCaps` is at `DDSD+0x68`,
  i.e. **`sub+0x74`** - which is exactly the field `FUN_10019273` writes when choosing video vs
  system memory (`|0x800` = `DDSCAPS_SYSTEMMEMORY` on the fallback path at `0x1001943a`, clearing
  `0x4000` `DDSCAPS_VIDEOMEMORY` at line 81) `[CONFIRMED @ GZGraphicD 0x10019273]`.

Dumping `sub+0x74` for the main surface **in both phases** directly tests whether widening the bar
pushes a surface out of video memory - a hypothesis that would explain a 2.5x cliff. **Stated as the
next test, not as a finding.** The board's standing rule applies: a plausible mechanism is not a
measured one.

## Status

- Cost located: **inside `IDirectDrawSurface::Blt`**, x2.55 per call, on the main scene blit.
- Blitting object class identified (`GZGraphicD+0x1F0AC` surface sub-object).
- Bar's own blit remains excluded (run 9) - it never appears as a hot object.
- Open: why an unrelated wide bar makes the main blit 2.55x more expensive.

---

# RUN 11 (2026-08-31) — H-mem **FALSIFIED**. Surface identified as `iso+0x4ec`.

## H-mem: dead, on identical bytes

| | A-native | B-fullwidth |
|---|---|---|
| dominant obj | `0x0F8E7488` | `0x0F8E7488` (same) |
| **caps** | **`0x00006040` [VIDMEM OFFSCR]** | **`0x00006040` [VIDMEM OFFSCR]** |
| owner | `0x00547970`, **2048x1089** | `0x00547970`, **2048x1089** |
| avg inside Blt | 0.344 ms | **0.748 ms** |

**The caps dword is byte-identical across phases.** No demotion to system memory, no `NONLOCAL`, no
change of owner, no change of size. **H-mem is falsified exactly as pre-registered** - the surface
stays in video memory and gets 2.2x slower anyway.

Recorded as intended: it was a tidy story, written down with a falsifier before the run, and the
run killed it. Surface residency is now excluded as the mechanism.

## Identity: the main blit is `iso+0x4ec`, the device surface

`owner = 0x00547970` at **2048x1089**. That pointer appears in this session's own resize logs as
`device-surface iso+0x4ec 0x00547970`, and 2048x1089 is exactly the resized extent
(1081 + `RZ_SURFACE_SLACK` 8). **So the hot blit is the composite destination - the device surface
the iso view draws into.** The `[UNCERTAIN]` carried since run 9 is closed.

The secondary object `0x00567528` (`vt=GZGraphicD+0x1F628`, a different class) went 1367 -> 122
calls at ~1.1-1.7 ms; the third, a `SYSMEM` surface with a null owner, went 349 -> 3 calls.

## Replication

Inside-Blt avg `0.3198 -> 0.7229 ms` this run (x2.26), against run 10's `0.2930 -> 0.7482` (x2.55).
Same direction, same magnitude, different process. **The core measurement replicates.**

## What this leaves

Same surface. Same video-memory residency. Same dimensions. Same owner. **And each Blt into it costs
2.2-2.55x more when the HUD bar is wide.** Since nothing about the destination changed, the
difference must be in either:

1. **the blit's own parameters** - source surface, source/dest rects, `dwFlags` (colour-key, ROP,
   async vs wait); or
2. **external contention** on the GPU that the wide bar induces elsewhere.

Both are directly testable with the hook that already exists: `rz_blt_hook` **already receives
`dr`, `src`, `sr`, `fl`** and currently ignores them. Aggregating flags, and dest-rect area, per
phase is a few lines and no new risk. That is the next step.

## Status

- Cost: inside `IDirectDrawSurface::Blt`, replicated across two runs.
- Destination: `iso+0x4ec` device surface, 2048x1089, VIDMEM - **unchanged between phases**.
- Excluded so far: bar's own blit (run 9), surface residency (run 11), stack-inferred callers
  (runs 7-8, instrument failures).
- Next: aggregate the Blt arguments the hook already receives.

---

# RUN 12 (2026-08-31) — smaller blits, 7.7x slower. Cost is not proportional to work.

## ⚠️ FIRST, A CORRECTION: my flag labels in the log are WRONG

The log prints `WAIT`, `ROP`, `KEYSRC`, `ASYNC` from a decode I wrote from memory instead of
checking. Correct `DDBLT_*` values:

| bit | real name | what I printed |
|---|---|---|
| `0x01000000` | `DDBLT_WAIT` | WAIT — correct |
| `0x00010000` | **`DDBLT_KEYSRCOVERRIDE`** | (unlabelled) |
| `0x00000400` | **`DDBLT_COLORFILL`** | **"ROP" — WRONG** (`DDBLT_ROP` is `0x00020000`) |
| `0x00000080` | `DDBLT_ALPHASRCNEG` | **"KEYSRC" — WRONG** (`DDBLT_KEYSRC` is `0x00008000`) |
| `0x10000000` | not a Blt flag | **"ASYNC" — WRONG** (`DDBLT_ASYNC` is `0x00000200`) |

**The raw hex in the log is correct; the names beside it are not.** Read the hex. The three observed
combinations are:

- `0x01000000` = `DDBLT_WAIT`
- `0x01010000` = `DDBLT_WAIT | DDBLT_KEYSRCOVERRIDE`
- `0x01000400` = `DDBLT_WAIT | DDBLT_COLORFILL`

Logged against myself: decoding constants from memory rather than checking is exactly the NO-GUESSING
violation this project forbids, and it nearly went into a result as fact.

## The measurement

| | A-native | B-fullwidth | change |
|---|---:|---:|---:|
| `0x01000000` (WAIT) calls | 15850 | 10932 | -31% |
| `0x01000000` **avg** | **0.1100 ms** | **0.8463 ms** | **x7.7** |
| `0x01010000` (WAIT+KEYSRCOVERRIDE) calls | 4874 | 521 | **-89%** |
| `0x01010000` avg | 1.1766 ms | 0.9303 ms | x0.79 (faster) |
| **average dest area** | **253,716 px** | **41,849 px** | **x0.16** |
| max dest rect | 2048x1081 | 2048x1081 | same |
| NULL-dest / NULL-src | 0 / 336 | 0 / 186 | — |

## The headline: SMALLER blits, 7.7x SLOWER

Average destination area **fell six-fold** (253,716 -> 41,849 px) while the dominant flag's per-call
cost **rose 7.7x**. Less work per call, far more time per call.

**That rules out throughput.** Whatever the cost is, it is not moving pixels — it is per-call
overhead or synchronization. This is the same conclusion the EIP profiler reached from a completely
different direction (`NtGdiDdDDIWaitForSynchronizationObject`), now supported by the blit's own
geometry.

## Scoring: neither pre-registered outcome cleanly, and that is the honest answer

- **Not "PARAMETERS IDENTICAL":** the mix changed a lot (keyed blits -89%) and rect sizes shrank 6x.
- **Not "PARAMETERS CHANGED" in the sense intended either:** that outcome meant *parameters changed
  in a way that explains the slowdown*. These changed in the **opposite** direction — smaller,
  simpler, fewer keyed blits should all be **faster**.

So the parameter changes are a **consequence** of the slowdown (fewer frames, different work
composition per sampled window), not its cause. The cause remains external to the call.

`[UNCERTAIN]` and worth stating: part of the mix shift is simply that phase B renders fewer frames in
the same 10 s, so the sampled population differs. **This run cannot separate "the engine issues
different blits" from "the same blit pattern sampled at a lower frame rate."** A per-frame
normalisation would be needed, and it was not built.

## Elimination ledger

| excluded | by | how |
|---|---|---|
| the bar's own blit | run 9 | never appears as a hot object |
| surface residency | run 11 | caps byte-identical, VIDMEM both phases |
| pixel throughput | run 12 | 6x smaller blits, 7.7x slower |
| stack-inferred callers | runs 7-8 | instrument failures, scored honestly |

**Remaining:** per-call synchronization / external GPU contention induced by compositing a
full-width surface. That is a far smaller and more specific space than the starting claim
("intrinsic to the engine's compositing, would require a compositor rewrite"), which is now dead
several times over.

## Suggested next step (not taken)

Normalise per frame, and instrument what the wide bar makes the DRIVER do — e.g. count
`NtGdiDdDDI*` transitions per frame, or test the bar at intermediate widths (600 / 1024 / 1536 /
2048) to see whether cost scales with width continuously or steps at a threshold. A threshold would
point at a resource limit; smooth scaling at per-pixel driver work.

---

# RUN 13 — width sweep: saturating curve, but TWO self-inflicted problems make it non-decisive

| width | calls | total inside-Blt | avg | avg dest area |
|---:|---:|---:|---:|---:|
| 600 | 20328 | 7186.1 ms | **0.3535 ms** | 255,813 px |
| 1024 | 10544 | 7460.6 ms | **0.7076 ms** | 131,116 px |
| 1536 | 9144 | 7683.2 ms | **0.8402 ms** | 80,721 px |
| 2048 | 8797 | 7843.9 ms | **0.8917 ms** | 69,699 px |

## Shape: neither SMOOTH nor THRESHOLD

Per-call increments for roughly equal width steps: **+0.354, +0.133, +0.052** — each about half the
last. A **saturating curve**: nearly all the cost appears at the first step and then asymptotes.
That matches neither pre-registered shape.

## ⚠️ PROBLEM 1: my "% of window" figures are WRONG in sweep mode

`rz_blt_dump` divides by 100.0, hardcoded for the 10 s A/B window. **Sweep windows are 8 s.** The
printed percentages (71.9 / 74.6 / 76.8 / 78.4) are all understated. Correct values:

| width | real % of the 8 s window |
|---:|---:|
| 600 | **89.8%** |
| 1024 | **93.3%** |
| 1536 | **96.0%** |
| 2048 | **98.0%** |

Absolute milliseconds in the log are correct; only the percentages are wrong. Second labelling bug
of the session after the `DDBLT_*` names — both were mine, both from reusing a constant without
re-checking it against the new context.

## ⚠️ PROBLEM 2: the 600 baseline is CONFOUNDED — and it is the step carrying the effect

`rz_hud_fit_surface` skips when `liveW == oldw`. The bar surface is natively 600 wide, so **at width
600 no refit happens and the bar keeps the ENGINE's original surface.** At 1024/1536/2048 it is
running on a surface WE created.

So the one large step (600 -> 1024, x2.00) is exactly the step where the surface changes hands. The
remaining, much smaller increments (x1.19, x1.06) are the only ones that isolate width. **The sweep
cannot separate "wider costs more" from "our recreated surface costs more".**

## And a deflationary observation that matters

**Total inside-Blt time is nearly constant across all four widths** (7186 -> 7844 ms, +9%) while call
count falls 57% (20328 -> 8797). Corrected, the thread is inside Blt **89.8% of the time even at the
600 baseline**, rising only to 98%.

So the thread is essentially always inside Blt at every width, and the per-call average rises
largely because a near-saturated time budget is divided among fewer calls. **"Average ms per Blt" is
therefore not an independent measure here** — it partly reports the frame-rate drop rather than
explaining it. Earlier runs quoted that x2.55 figure as the finding; it needs this caveat attached.

## Scoring

**Non-decisive.** Not SMOOTH, not THRESHOLD, not FLAT. The instrument answered a slightly different
question than intended because of the skip-when-equal confound, and one of its readouts was
mislabelled.

## The clean follow-up, which is cheap

Sweep **600(engine) -> 2048 -> 600(ours)**. The final step puts our recreated surface at the
original width:

- if cost returns to baseline at 600(ours), **width is the driver**;
- if it stays high, **our recreated surface is the driver** — and that would be a mod bug, not an
  engine property, which is a very different and much more fixable conclusion.

That single control separates the two explanations the sweep confounded.

## Status

- Shipping build unaffected (sweep is diagnostic, two flags, off by default).
- FPS mechanism: still open, now with a named confound to resolve and a cheap control to resolve it.
- Two instrument defects recorded against myself: the hardcoded percent divisor and the
  skip-when-equal baseline.

---

# RUN 14 — **WIDTH IS THE DRIVER.** The confound is resolved; the owner's read is confirmed.

| step | surface | width | calls | avg inside-Blt |
|---|---|---:|---:|---:|
| `S1_W600` | **engine's** | 600 | 22213 | **0.3029 ms** |
| `S2_W2048` | ours | 2048 | 9105 | **0.8552 ms** |
| `S3_W600` | **ours** | 600 | 18806 | **0.3186 ms** |

**`S3_W600` (0.3186 ms) returns to `S1_W600` (0.3029 ms) — a 5% difference.** Our recreated surface
at 600 costs essentially what the engine's own surface costs at 600. Call throughput recovers too
(9105 -> 18806).

**Pre-registered outcome: WIDTH IS THE DRIVER.** The recreated surface is exonerated — it is not a
mod bug. The owner's own reading, *"the issue is extending the UI, that's killing the FPS"*, is
exactly what the measurement says.

## This vindicates runs 3-12 rather than invalidating them

The pre-registration stated plainly that if `S3_W600` stayed high, the width attribution had been
wrong since run 3 and the x2.55 headline was really "our surface costs more". **It did not stay
high.** The attribution holds: widening the bar is what costs frame rate.

Recorded because it cuts both ways — the same pre-registration that would have forced me to retract
twelve runs is what now licenses keeping them.

## Combined with run 13: the cost SATURATES, and that is the actionable part

Run 13 (now trustworthy, since ownership is excluded): 600 -> **0.3535**, 1024 -> **0.7076**,
1536 -> 0.8402, 2048 -> 0.8917 ms.

**Nearly all the cost arrives by 1024.** Going 600 -> 1024 doubles it; 1024 -> 2048 adds only ~26%
more. So there is **no cheap middle ground**: a partially-extended bar costs almost as much as a
fully-extended one. The practical choice is binary — native width (fast) or extended (costly).

That is a genuinely useful result for the mod's design, and it is why `SC3RESIZE_HUDNATIVE=1` earns
its place rather than being a token opt-out.

## Standing caveat, still attached

Inside-Blt is 84% of the window even at the 600 baseline, so "avg ms per Blt" partly reports the
frame-rate drop rather than explaining it (run 13). What runs 9-14 establish is **that** extending
the bar costs frame rate and **how it scales** — not the driver-level mechanism, which remains open.

## Incidental: the shrink path works

`S2 -> S3` refit the surface DOWN (2048 -> 600, pitch 4096 -> 1200, art re-tiled at 33600 px, lock
and unlock balanced). That is the shrink behaviour run 6 left unverified, now exercised — though
still not as a full window-resize test.

## Cosmetic defect

`SWEEP> starting 3-point width sweep (600/1024/1536/2048)` — the label is a stale hardcoded string;
`SWEEP_N` is correct at 3 and the actual widths run were 600/2048/600. Log text only.

---

# ⚠️ CORRECTION TO RUN 9, made 2026-09-01 before run 15

Run 9 concluded: *"The bar's own surface does not appear as a hot blit... If the cost were an extra
wide bar blit each frame, that is exactly where it would appear, and it does not."* It was written up
as "the most useful part is a NEGATIVE" and used to reframe the whole investigation.

**That conclusion is unsupported.** `IDirectDrawSurface::Blt` is a method on the **DESTINATION**
surface, and the instrument buckets by `self` — the destination. So every blit into `iso+0x4ec`
lands in one bucket **including the HUD bar's own blit into it**. The bar's blit could never have
appeared as a separate hot object; its absence carries no information.

This is the same error class the board records repeatedly: reading a null result from an instrument
that was structurally incapable of producing a positive one. Runs 10-14 are unaffected (they measure
total inside-Blt time and its scaling, which the destination bucketing does not distort), but the
"bar's own blit excluded" line must be struck from the elimination ledger.

**Corrected ledger:**

| status | item | by |
|---|---|---|
| excluded | surface residency | run 11, caps byte-identical |
| excluded | pixel throughput | run 12, 6x smaller blits 7.7x slower |
| excluded | our recreated surface | run 14, S3 returns to baseline |
| ~~excluded~~ **OPEN** | the bar's own blit | run 9's negative was structural, not evidence |
| failed instruments | stack-inferred callers | runs 7-8 |

---

# RUN 15 PRE-REGISTRATION — source-side attribution

## Instrument

Bucket Blt time by **SOURCE** surface as well as destination. The hook already receives `src` and
discarded it. At dump, label the known sources by pointer: the bar's own `IDirectDrawSurface*` and
the render target's, both read from `sub+0x04` `[CONFIRMED @ GZGraphicD 0x10018a82]`.

**Match on POINTER, not dims** — the discipline that made the U-068 blit-source result decidable,
where a dims-based filter could not have separated "not blitting" from "not recognised".

## Pre-registered outcomes

- **THE BAR IS THE COST:** the bar's source surface accounts for a large and width-scaling share of
  inside-Blt time. Then the cost is literally drawing the wide bar each frame — a system-memory
  surface (the bar is created with `p7=0`, which `FUN_10019273` routes to the `DDSCAPS_SYSTEMMEMORY`
  branch) transferred to a video-memory destination, which is exactly the shape of an expensive
  per-frame transfer. Mitigation becomes concrete: make the bar surface video-memory, or draw it
  less often.
- **THE BAR IS NOT THE COST:** the bar's source is a small share, and the growth is in the scene's
  own tile blits. Then the wide bar degrades the scene's blits indirectly, and run 9's conclusion —
  though unsupported as argued — was right by accident.
- **VOID:** the bar's surface pointer cannot be resolved (logged as `0x00000000`), or fewer than 100
  calls in a window.

## Conditions

Sweep `600 -> 2048 -> 600` again, so source attribution is measured at both widths with the
ownership control still in place. If the bar's share grows from `S1` to `S2` and falls back at `S3`,
that is the same within-run control that settled run 14.

---

# RUN 15 — ONE source carries 93% of the wide-bar cost. Identity not yet pinned.

## The control replicates run 14

| step | width | calls | total | avg |
|---|---:|---:|---:|---:|
| `S1_W600` | 600 (engine surface) | 21035 | 6499.4 ms | 0.3090 ms |
| `S2_W2048` | 2048 (ours) | 8449 | 7798.6 ms | 0.9230 ms |
| `S3_W600` | 600 (ours) | 18131 | **6501.2 ms** | **0.3586 ms** |

`S3` total is **6501.2 ms against `S1`'s 6499.4 ms** — within 0.03%. Run 14's result reproduces
exactly: **width is the driver, our recreated surface is not.**

## The finding: a single source dominates only when the bar is wide

| step | top source | calls | total | share of window's Blt time |
|---|---|---:|---:|---:|
| `S1_W600` | `0x0C1DF3B0` **iso render target** | 1523 | 1529.3 ms | 24% |
| `S2_W2048` | **`0x0BEF89E8`** | **6796** | **7267.7 ms** | **93%** |
| `S3_W600` | `0x0C1DEAB0` | 1010 | 1587.3 ms | 24% |

At 600 the work is spread across ~7 sources of roughly 1000-1500 calls each — the normal pattern in
both `S1` and `S3`. At 2048 **one source takes 6796 calls and 93% of all blit time**, and the iso
render target's own share collapses (1529 ms -> 86 ms).

**And `0x0BEF89E8` all but vanishes when the bar narrows again: 29 calls, 31.5 ms in `S3`.** So this
source IS the wide-bar cost, isolated by the same within-run control that settled run 14.

## `[UNCERTAIN]` — what `0x0BEF89E8` is. Do not guess it.

It is **not** the pointer the dump labelled as the bar surface (`0x0C1DF250` at `S2`). Two reasons
that label cannot be trusted here, both mine:

1. **The bar's surface pointer changes on every refit** (each recreate makes a new sub-object and a
   new DirectDraw surface), and the label is computed at DUMP time — the end of the window. It
   describes the surface as it is at dump, not necessarily the one blitting during the window.
2. Heap regions hint but do not prove: our recreated surfaces land in `0x0C1Dxxxx` (alongside the
   render target), while `0x0BEF89E8` sits in `0x0BEFxxxx` — the region where `S1`'s **engine-created**
   bar surface (`0x0BEF8708`) lived. That points at an ENGINE-allocated surface rather than one of
   ours, which would weaken "it is the bar's own backing" — **but region adjacency is not identity
   and is not being treated as evidence.**

## The fix that pins it, and it is small

- **Capture the bar's `IDirectDrawSurface*` at the moment of the refit** (inside `rz_hud_fit_surface`,
  right after the recreate) instead of reading it at dump time.
- **At dump, resolve the top source by search**: walk the HUD children `[0x2a..0x2f]` and the iso
  surfaces, compare each one's `sub+0x04` against the hot source pointer, and name whichever matches.
  If none match, that is itself informative - the surface belongs to something we have not been
  looking at.

## Status

- Width-is-the-driver: **replicated** (runs 14 and 15).
- The cost is concentrated in **one blit source**, not spread - a much sharper target than "the wide
  bar costs more".
- That source's identity: **open**, one instrument fix away.
- Run 9's struck conclusion stays struck; source-side bucketing is what should have been measured
  from the start.

---

# RUN 16 — **NAMED: HUD child[0x2b], a 16x64 filler tile, blitted ~46x PER FRAME when the bar is wide**

## The identification

| step | `0x0C259300` = **HUD child[0x2b] (16x64)** | share of that window's Blt time |
|---|---:|---:|
| `S1_W600` | **below the top 8** | negligible |
| `S2_W2048` | **6892 calls, 7201.9 ms** | **93%** |
| `S3_W600` | **24 calls, 23.1 ms** | 0.4% |

**6892 calls at 2048 versus 24 at 600 — a 287x change in call count from the same surface**, and it
returns to nothing when the bar narrows. Resolved by pointer against a reachable owner, exactly as
pre-registered: `<<< HUD child[0x2b] (16x64)`.

This matches run 2's census: `child[0x2b] = 16x64, pitch 32 (COHERENT), non-zero 1024/1024` — a
small, fully-opaque strip. **A filler tile.**

## Per-frame estimate `[UNCERTAIN - frames inferred, not counted]`

Most sources blit once per frame, so their call counts approximate the frame count: ~993 in `S1` and
~982 in `S3` over 8 s (~123 fps), against ~150 in `S2` (~19 fps).

| | frames (est.) | child[0x2b] blits | per frame |
|---|---:|---:|---:|
| `S1_W600` | ~982 | <42 | **~0.02** |
| `S2_W2048` | ~150 | 6892 | **~46** |

**At native width the tile is essentially never drawn. At 2048 it is drawn about 46 times every
frame.** Frame counts are inferred from other sources' call counts rather than measured directly, so
the ratio is an estimate — but the 287x raw call-count change needs no inference.

## The mechanism, and it explains every earlier result

**Widening the bar makes the engine cover the extra width by TILING a 16-pixel-wide strip, one
DirectDraw `Blt` per tile, every frame.** The cost is not pixels — it is ~46 fixed-overhead
DirectDraw calls per frame, each carrying a GPU synchronization wait.

This reconciles the whole investigation:

- **run 3/4** — time in `NtGdiDdDDIWaitForSynchronizationObject`: 46 tiny blits per frame, each waiting.
- **run 12** — average dest area fell 6x while cost rose 7.7x: the added calls are *tiny* 16px blits.
- **run 12** — "smaller blits, slower" now has a cause rather than a paradox.
- **run 13** — saturation with width: as frame rate collapses, tiles-per-second stops growing.
- **run 9's struck conclusion** — the bar's drawing WAS the cost all along; destination-bucketing hid
  it, and the correction made before run 15 was necessary to find this.

## The fix is concrete and uses machinery we already have

If the tile count is the region width divided by the SOURCE surface width, then **widening
`child[0x2b]` (with its 16x64 art tiled into it) reduces the blit count proportionally** — a 1024-wide
filler would cut ~46 calls per frame to ~1.

`rz_hud_fit_surface` already does exactly this for `child[0x2a]`: snapshot, `FUN_10009efb` replay,
lock, tile, unlock. Applying it to `child[0x2b]` is a parameter change, not new machinery.

`[UNCERTAIN]` — that the engine's tile count is driven by source width rather than a fixed step. Not
established; it is the hypothesis the next run tests, and it has an obvious falsifier (widen
`[0x2b]`, count its blits: unchanged = hypothesis dead).

## Minor defect noticed in passing

`S1` labelled `0x0C2591C0` as "THE HUD BAR'S PREVIOUS surface (replaced, not freed)" — but no refit
happens at `S1`, so `g_bar_surf_prev` had been set to the CURRENT surface. Cosmetic mislabel in the
no-refit case; the pointer and its 993 calls (once per frame, 42.2 ms) are correct and normal.

---

# RUN 17 — THE FIX FAILED. Tile count is NOT driven by source width. Hypothesis dead.

## What the log shows

```
HUDFIT> child[0x2b]: cached pristine art 16x64 pitch=32 (one-time)
HUDFIT> child[0x2b]=0x0F4677E8 -> refitting to 2048x64 (art 16x64)
BLT> ---- S2_W2048 ---- INSIDE ddraw Blt: 9677 calls, 7821.0 ms total, 0.8082 ms avg
BLT> S2_W2048 SRC #1 0x03F852D8 calls=7662 total=7256.0 ms  <<< THE HUD BAR (captured at refit)
```

The widen applied exactly as intended — `child[0x2b]` went from 16x64 to **2048x64**, art cached and
tiled, no fault, no refusal.

**And its blit count did not fall. 7662 calls against run 16's 6892 — if anything slightly more.**

| | run 16 (no fix) | run 17 (fix) |
|---|---:|---:|
| `[0x2b]` calls at 2048 | 6892 | **7662** |
| total inside-Blt at 2048 | 7747.1 ms | **7821.0 ms** |
| avg at 2048 | 0.9195 ms | 0.8082 ms |

Total inside-Blt is **unchanged within noise**. This is the pre-registered **HYPOTHESIS DEAD**
outcome, and the pre-registration's first bar — *"a drop in `[0x2b]`'s call count alone is not
success; total inside-Blt must fall too"* — never even came into play, because the count did not drop
at all.

## What that rules out, and what it points to

**The engine's tile count is not a function of the source surface's width.** Widening the source
changed nothing, so the count must come from somewhere else. The most likely remaining reading, and
it is `[UNCERTAIN]`:

> the engine passes a **16-pixel source RECT** on every blit regardless of how wide the surface is,
> so a bigger surface simply leaves most of itself unused.

Under that reading no surface-side change can ever help. The count lives in the **loop that issues
the blits**, which is engine code — and this project patches engine code routinely (FIX A's four
grid-B clamps, FIX C's null guard).

## The next instrument is now trivial and exact

Earlier attempts to find callers used stack SCANNING and failed twice (run 7 contamination, run 8
selection bias). **That is no longer necessary.** We hold the `Blt` call in a C function, so:

> in `rz_blt_hook`, when `src == g_bar_surf`, record `_ReturnAddress()`.

That is the **exact** caller, an MSVC intrinsic, no scanning, no heuristics, no validation needed.
Bucket those and the tiling loop names itself in one run. It is the instrument the earlier stack work
was groping for, and it only became available once the COM hook replaced the prologue hook.

## Also recorded: a labelling ambiguity I introduced this run

`g_bar_surf` is set by `rz_hud_fit_child` for whichever child ran LAST — now `[0x2b]`, not `[0x2a]`.
So `<<< THE HUD BAR` in run 17's log means **child[0x2b]'s surface**, not the background. The
attribution is correct (the resolver's `g_bar_surf` check short-circuits before the child search) but
the label is misleading. `g_bar_surf` should be per-child.

## Status

- Fix: **failed, reverted in conclusion though still in the build** (it is harmless - a wider filler
  surface costs nothing extra; it simply does not help).
- Mechanism: still `child[0x2b]` tiled ~46x/frame. **Confirmed twice now** (runs 16 and 17).
- Cause of the COUNT: engine-side loop, not surface geometry.
- Next: `_ReturnAddress()` in the ddraw hook, filtered to that source. One run to name the loop.

---

# RUN 18 — caller captured: **`GZGraphicD+0x18C89`, a SINGLE site, 100% of the tiled blits**

| step | caller | calls | total |
|---|---|---:|---:|
| `S1_W600` | *(no `[0x2b]` blits - filter set at S2's refit)* | 0 | — |
| `S2_W2048` | **`GZGraphicD.dll+0x18C89`** | **8538** | **7403.2 ms** |
| `S3_W600` | `GZGraphicD.dll+0x18C89` | **15** | 12.2 ms |

**One caller, no spread.** 8538 of 8538 `[0x2b]`-sourced blits come from a single address, and it
collapses to 15 when the bar narrows. The `_ReturnAddress()` approach worked exactly as intended -
no junk, no validation needed, no ambiguity. Contrast runs 7-8, which produced rankings containing
`SC3U.exe+0x9`.

## But it is ONE LEVEL TOO SHALLOW - and that is diagnostic in itself

`FUN_10018c58` spans `0x18c58..0x18d1c` (197 bytes), so **`0x18C89` is `FUN_10018c58+0x31` - inside
the engine's own `Blt` wrapper.** The captured return address is the instruction after the wrapper's
`call [vtable+0x14]`, not the tiling loop.

So what run 18 actually proves is: **every one of the tiled blits goes through `FUN_10018c58`**, the
same wrapper the mod has hooked as its per-frame heartbeat since the beginning. The tiling loop is
`FUN_10018c58`'s CALLER, one frame further up.

## Getting that frame needs no new mechanism either

`FUN_10018c58` is already hooked (`fnlog_enter` idx 1), and the stub's documented frame layout gives
**`f[9]` = the return address into its caller** (`sc3resize.c`: *"f[0]=eflags, f[1..8]=edi..eax,
f[9]=return address, f[10..]=stack args"*, taken verbatim from `sc3probe.c:8650-8658`).

The heartbeat fires at `FUN_10018c58` entry, immediately before the `Blt`. So:

1. in `fnlog_enter` idx 1, stash `f[9]` into a global;
2. in `rz_blt_hook`, when the source is `child[0x2b]`, bucket **that** stashed value instead of
   `_ReturnAddress()`.

That yields the tiling loop's address with the same exactness and no stack scanning. Both hooks
already exist; this is a wiring change.

## Why `S1` shows no blits, and why that is correct

`g_ret_filter` is set when `child[0x2b]` is refit, which first happens at `S2`. So `S1` legitimately
has no filtered blits - the pre-registered `NO BLITS` case, occurring for the stated reason and
diagnosable from the logged `filter=0x0BFFA9A8`. `S3` confirms the filter still tracks the surface
(15 calls) rather than pointing at a stale one.

## Status

- Tiled blits: **single call site**, confirmed, `FUN_10018c58+0x31`.
- That site is the Blt wrapper, not the loop - the loop is its caller.
- Next: stash `f[9]` in the existing heartbeat hook. No new hooking, no scanning.

---

# RUN 19 — caller is `FUN_10014894+0x76`. Chain proven; still one frame short of the loop.

| step | caller | calls | total |
|---|---|---:|---:|
| `S2_W2048` | **`GZGraphicD+0x1490D`** | 6609 | 7075.1 ms |
| `S3_W600` | same | 33 | 33.0 ms |

Single site again, and it collapses when the bar narrows. **`LOOP NAMED`** as pre-registered - the
address is now outside `FUN_10018c58`.

## The call chain, proven in the disassembly and the PE

```
0x1490a  ff502c   call dword ptr [eax + 0x2c]    <- issues the blit
0x1490d  eb02     jmp  0x10014911                <- the captured return address
```

and from the PE's static `.rdata`:

```
sub vtable (PTR_FUN_1001f0ac) +0x2c -> 0x10018c58
```

So **`FUN_10014894+0x76` calls `sub->vt[0x2c]` = `FUN_10018c58`, returning to `0x1490D`** - exactly
the captured value. `[CONFIRMED @ GZGraphicD 0x10014894, vtable 0x1001f0ac+0x2c]`

## What `FUN_10014894` is - and why it is NOT the loop

Reading it: it copies a **dest RECT** (`param_2`) and a **source RECT** (`param_3`) to locals, calls
`this->vt[0xac]` to clip/validate, then on success compares the source's pixel format
(`param_1->vt[0x50]`) against `this+0x10` and either

- **same format** -> `sub->vt[0x2c]` = the `Blt` wrapper (the path we are hitting), or
- **different** -> `this->vt[0x1d4]`, a converting path.

**It blits ONE rect.** It contains no loop. So the tiling is driven by *its* caller - the chain is
`loop -> FUN_10014894 (blit one rect) -> FUN_10018c58 (wrapper) -> IDirectDrawSurface::Blt`, and we
have now walked three of those four links.

## Going up without another run per level

Rather than hook `FUN_10014894` and repeat, capture several frames from the heartbeat at once.
`FUN_10014894` establishes a frame pointer (`push ebp; mov ebp,esp` at `0x14894`), and at
`FUN_10018c58` entry that `ebp` is still live. The stub's `pushad` layout gives **`f[3]` = EBP**
(order edi, esi, ebp, esp, ebx, edx, ecx, eax), so:

- `f[9]` -> `0x1490D`, inside `FUN_10014894` (confirmed this run);
- `*(ebp + 4)` -> the return address into **`FUN_10014894`'s caller** = the tiling loop;
- `*(*(ebp) + 4)` -> one further, if that frame also uses `ebp`.

`[UNCERTAIN]` for the third level only: frame-pointer walking is valid exactly as far as the frames
actually use `ebp`, and `/O2` omits it freely. Level 2 rests on a frame pointer **proven in the
disassembly above**; level 3 is opportunistic and must be read as a hint, not a result. This is the
same hazard that made runs 7-8's scanning useless - the difference is that here the first hop is
verified rather than assumed.

## Status

- Chain: `?? -> FUN_10014894+0x76 -> FUN_10018c58+0x31 -> ddraw Blt`, three links proven.
- `FUN_10014894` reads as a single-rect clipped blit with a format check - not the loop.
- Next: capture `*(f[3]+4)` (proven-valid) and `*(*(f[3])+4)` (opportunistic) in the same heartbeat.

---

# RUN 20 — ⭐ **THE TILING LOOP: `SIMUI FUN_10026841`.** Decoded, and it explains run 17.

```
LOOP(L2)  SIMUI.DLL+0x268AF  calls=7371   <- FUN_10014894's caller
hint(L3)  SIMUI.DLL+0x6D317  calls=7371   [UNCERTAIN - frame-pointer walk]
```

Single site, all 7371 calls. `0x268AF` is inside **`FUN_10026841`** (0x26841..0x26973), at +0x6E.

## The loop, in the decompilation

```c
iVar1 = *(int *)(param_1 + 0x2c);                              // bar's RIGHT edge
if (*(int *)(param_1 + 0x130) < iVar1) {
    iVar4 = *(int *)(param_1 + 0xd8) - *(int *)(param_1 + 0xd0);   // STEP = source RECT width
    local_14 = iVar1 - iVar4;
    local_c  = iVar1;
    do {
        (**(code **)(**(int **)(param_1 + 0x5c) + 0x118))
                  (*(undefined4 *)(param_1 + 0xac), param_1 + 0xd0, &local_14, 0);   // the blit
        local_c  -= iVar4;
        local_14 -= iVar4;
    } while (*(int *)(param_1 + 0x130) < local_c);
}
```

**It tiles right-to-left from the bar's right edge (`+0x2c`) down to `+0x130`, stepping by
`iVar4`, one blit per step.** `[CONFIRMED @ SIMUI 0x10026841]`

## ⭐ Why run 17's fix could never have worked - now explained, not just falsified

**The step is `*(param_1+0xd8) - *(param_1+0xd0)` - the SOURCE RECT's width, not the surface's.**

Widening `child[0x2b]`'s surface to 2048 left that rect at 16 px, so the loop still stepped 16 px at
a time and issued the same number of blits. Run 17 measured that (7662 calls, unchanged); run 20
explains it. The empirical falsification and the mechanism now agree.

## The whole HUD bar paint routine is decoded

`param_1` is the HUD window: children `this[0x2a..0x2f]` are at byte offsets `+0xa8..+0xbc`
(`0x2a * 4 = 0xa8`), which matches every earlier observation.

| child | offset | how it is drawn |
|---|---|---|
| `[0x2a]` background | `+0xa8` | **once**, src `+0xc0` -> dest `+0x120` |
| **`[0x2b]` filler** | **`+0xac`** | **TILED in the loop**, src rect `+0xd0`, dest walked leftwards |
| `[0x2c]` | `+0xb0` | once, `+0xe0` -> `+0x140` |
| `[0x2d]` | `+0xb4` | once, `+0xf0` -> `+0x150` |
| `[0x2e]` | `+0xb8` | once, `+0x100` -> `+0x160` |
| `[0x2f]` | `+0xbc` | once, `+0x110` -> `+0x170` |

Five widgets blitted once each; **one filler tiled across the gap.** That is the entire cost model,
and it confirms independently that `[0x2c..0x2f]` were correctly left alone in run 17.

## The fix is now a FIELD WRITE, not a code patch

If the step is the source rect's width, then **widening the source rect widens the step**:

- `child[0x2b]`'s surface is already widened to 2048 (run 17, harmless and now useful);
- set `*(hud+0xd0) .. *(hud+0xd8)` to a wider span, e.g. 1024;
- the loop then runs ~2 iterations instead of ~46.

No cave, no engine code patch, no hooking - the same class of write as the `vt+0xc8` SetRect that
already ships. **`[UNCERTAIN]`** and falsifiable: that `+0xd0..+0xd8` is a plain source RECT the blit
path will honour at a larger width. If the art tiles wrongly or the count does not fall, the
hypothesis is dead and the log will say which.

## Status

- Chain complete: **`FUN_10026841` (tile loop) -> `FUN_10014894` (blit one rect) -> `FUN_10018c58`
  (wrapper) -> `IDirectDrawSurface::Blt`**. All four links proven.
- Run 17's failure: explained.
- Fix candidate: a field write, testable next run.

---

# RUN 21 — side panel IDENTIFIED, and **its tiling path is INACTIVE**

```
### SIDE: panel window captured 0x0D487950 (SIMUI FUN_1004e123 ctor)
SIDE> panel=0x0D487950 vt=0x03469834 rect this+0x14..0x20=[704 0 800 442]
SIDE> child +0xc0 = 0x100EA9D0 dims=96x417
SIDE> child +0xc4 = 0x00000000 (null/unreadable)
SIDE> child +0xc8 = 0x100EA2C8 dims=96x25
SIDE> child +0xcc = 0x00000000 (null/unreadable)     <<< THE TILED ONE
SIDE> child +0x114 = 0x00000000 (null/unreadable)
```

## IDENTIFIED, as pre-registered

`vt = 0x03469834` = SIMUI base + `0xa9834` — the vtable found statically. Rect **`[704, 0, 800, 442]`
= 96 wide x 442 tall at x=704..800**, i.e. **the rightmost 96 px of the native 800-wide screen**.
A tall narrow rect at a screen edge: exactly the pre-registered IDENTIFIED signature. The
static chain (`.rdata` pointer -> vtable base -> `.text` immediate -> constructor) landed on the
right object.

## ⭐ But `+0xcc`, the tiled child, is **NULL** — so the loop never runs

`FUN_1004e63e` guards its tile loop with `if (*(int **)(param_1 + 0xcc) != (int *)0x0)`. With
`+0xcc` null, **the entire tiling branch is skipped for this instance.** The panel draws its two
real children (`+0xc0` 96x417 background, `+0xc8` 96x25) with one blit each and nothing else.

**So the vertical UI has no tiling cost to inherit.** The expensive mechanism that dominates the
bottom bar is present in the code but inactive in this object.

## The garbage tilespan is expected, and is itself a check

`tilespan=1462513952-825242161` is nonsense because `+0x104`/`+0x10c` are **uninitialised** - the
constructor zeroes dwords `[0x30..0x33]` and `[0x45]` (= `+0xc0..+0xcc`, `+0x114`) and `[0x38..0x3f]`
(= `+0xe0..+0xfc`), but **not** `+0x100..+0x10c`. Those fields are only ever read inside the
`+0xcc != NULL` branch, so leaving them uninitialised is safe engine behaviour.

That the uninitialised fields are exactly the ones the null-guarded branch uses, and the initialised
ones exactly what the unguarded code touches, **independently corroborates the offset map** rather
than undermining it.

## What this means for extending the side panel

Docking/extending it vertically should be **cheap** - there is no per-frame tile loop to multiply.
The likely cost is one stretched or re-fitted background blit, not ~46 small ones.

`[UNCERTAIN]`, and it matters: **only ONE instance was captured** (the hook keeps the first and the
log shows a single construction). Another instance of this class elsewhere in the UI could have
`+0xcc` populated and would tile. This result covers the panel that was built in this session, not
the class in general.

## Status

- Side panel object: **captured and confirmed** (vtable, rect, children all agree).
- Its tiling path: **inactive** (`+0xcc` null) - no FPS penalty expected from extending it.
- Offset map: corroborated by which fields the constructor does and does not initialise.
- Next, if pursued: dock/extend via the same `vt+0xc8` SetRect used for the bar, then measure -
  the prediction is **no material FPS change**, which is a real falsifiable claim.

---

# RUN 22 — ⭐ **PREDICTION HOLDS.** Extending the side panel costs NOTHING. Model confirmed positively.

Owner: *"you moved the vertical panel, below the buttons there's a black line, minimap was not moved,
there's no FPS drop."*

```
SIDE> SetRect vt+0xc8  [704,0,800,442] -> [1952,0,2048,1081]
SIDE> SetRect returned; rect now [1952,0,2048,1081] (tiled child +0xcc=0x00000000)
```

| | A (panel native) | B (panel extended full height) | change |
|---|---:|---:|---:|
| inside-Blt calls | 25341 | **25419** | **+0.3%** |
| inside-Blt total | 8636.7 ms | **8387.5 ms** | **-2.9%** |
| inside-Blt avg | 0.3408 ms | **0.3300 ms** | **-3.2%** |

**No cost. B is fractionally CHEAPER than A**, comfortably inside the pre-registered ~15% band, and
the owner independently reports no FPS drop.

## The contrast is the point

Same framework, same `vt+0xc8` SetRect, same instrument, same measurement window:

| element | change | inside-Blt avg | calls |
|---|---|---|---|
| **bottom bar** (tile loop **ACTIVE**) | 600 -> 2048 wide | 0.34 -> **0.85 ms (x2.5)** | -60% |
| **side panel** (tile loop **NULL-GUARDED, inactive**) | 442 -> 1081 tall | 0.34 -> **0.33 ms (flat)** | +0.3% |

**This is the first POSITIVE confirmation of the tiling model.** Everything before it established the
mechanism by elimination - removing width, residency, throughput, surface ownership. This one
predicted, in advance and in writing, that a structurally similar UI element *without* an active tile
loop would be **free** to extend. It was.

A model that only explains costs after the fact is weak. This one called a null result correctly
before the run.

## The black line was predicted

Pre-registration: *"the two real children are 96x417 and 96x25 and will NOT stretch, so a full-height
panel will very likely show a blank region below them. That is expected and is not the thing being
measured."* Owner saw exactly that. **Not a defect - the panel has no art to fill the extra height**,
which is a content problem, not a performance one, and is fixable the same way the bar's was
(cache the art, refit the child surface, tile it).

## NEW: the minimap is a SEPARATE window

Owner: *"minimap was not moved."* So the minimap is not one of this panel's five children - it is its
own UI window with its own object and paint routine, and it needs its own capture to move. **Not a
failure of this run**; a newly identified piece of the surface. Candidates from the earlier SIMUI
scan (6-blit paint routines) include `FUN_1001ad52` and `FUN_10060f59`, neither of which has a loop.

## Status

- Side panel: **docks and extends to full height at 2048x1081 with ZERO frame cost.**
- Tiling model: **confirmed positively**, not just by elimination.
- Open (cosmetic): the panel's blank region needs art, exactly as the bar's did.
- Open (new): the minimap is a separate window, not yet captured.
