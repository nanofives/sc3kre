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
