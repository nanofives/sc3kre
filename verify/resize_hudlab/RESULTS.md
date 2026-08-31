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
