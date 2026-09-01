# HUD LAB — session handoff (2026-08-31 / 09-01, 42 runs)

## What SHIPS and is owner-confirmed

| feature | state |
|---|---|
| Viewport resize | fills the monitor, city renders, zoom stable |
| **HUD cluster layout** (`SC3RESIZE_CLUSTER=1`) | **whole native HUD relocated to the bottom-right corner at native size** |
| **No FPS cost in cluster mode** | owner-confirmed |
| Minimap dock (`SC3RESIZE_MINI=1`) | docks to the corner, re-docks on every resize |
| Bar dock+span (default) | works, but carries the tiling cost - see below |
| `SC3RESIZE_HUDNATIVE=1` | opt-out, leaves the HUD untouched |

⛔ **The relocated HUD is NOT CLICKABLE.** Everything below is about that.

## FIX C — a real engine bug, fixed

`FUN_1000efa1` (grid-B node REMOVE) dereferenced the NULL list terminator on its "not found" and
"empty bucket" paths. Caught in-game (`0xC0000005` READ at `0x00000004` on both `0xEFDB` and
`0xEFE3`), root-caused in disassembly, fixed with a 2-byte in-place retarget plus one cave. Held
across every subsequent run. `[CONFIRMED @ SIMSPR 0x1000efa1]`

## The FPS cost — root-caused, then side-stepped

`SIMUI FUN_10026841` tiles a 16x64 filler (`child[0x2b]`) across the bar's width, **one DirectDraw
Blt per 16 px, ~46 per frame at 2048** = 93% of all Blt time. Chain proven end to end:
`FUN_10026841 -> FUN_10014894 -> FUN_10018c58 -> IDirectDrawSurface::Blt`.

Eliminated by measurement along the way: surface residency, pixel throughput, our recreated surface,
source-surface width. **Cluster mode avoids the cost entirely by never widening the bar** - the
owner's design, and better than the fix that was being built toward.

## ⛔ THE OPEN PROBLEM — clickability

The input chain is now **completely mapped**, every link confirmed statically:

```
WndProc FUN_10017e2f
  -> FUN_100178a6                    clamps x,y to the stored rect      -- INNOCENT (run 36, measured)
  -> (window+0x30)->vt[0x64] = GZWIND FUN_10020818        mouse dispatch
       -> (sink+0x38)->vt[0x8c] = GZWIND FUN_1001e748     find-window-at-point
            walks children at +0x34, gated per child on vt+0xf0(1)
            -> vt+0xe4 = SIMUI FUN_1004efcd               point-in-window
                 -> vt+0xd8 = FUN_1006dd8c                screen->local (subtract origin)
                      -> vt+0xdc = FUN_1006dd44           origin = sum of vt+0x98/0x9c up parents
                 -> vt+0x1a0 = FUN_1002cb22               containment
                      -> FUN_1006ddbd                     THE COMPARISON
```

### A window carries FOUR position/extent representations

| field | drives | moved? |
|---|---|---|
| `+0x14..0x20` | window rect (what `vt+0xc8` SetRect maintains) | ✅ |
| `+0x80..0x8c` | **HIT-TEST RECT** (l,t,r,b) - what `FUN_1006ddbd` compares | ✅ |
| `+0x90` | paint destination (generic painter blit) | ✅ |
| `+0xc0..` | per-class child rects (bar/side panel) | n/a |

**All are now provably correct** (run 42 log: minimap hit rect `[1888 917 2048 1081]` 160x164, bar
`[1248 1025 1847 1081]` 599x56, side `[1952 481 2048 923]` 96x442, all positive extents).

**And it is still not clickable.**

### The next suspect, unexplored: FLAGS, not geometry

`FUN_1006ddbd` does not stop at the rectangle:

```asm
bl = 1                          ; geometric hit succeeded
call dword ptr [eax + 0xf0]     ; vt+0xf0(0x80000) - a flag query
test al, al
je  <reject>                    ; flag clear -> the hit is DISCARDED
```

and `FUN_1001e748` gates each child on `vt+0xf0(1)` **before recursing into it**.

So the hit test is **geometry AND flags**, and only geometry has been addressed. Two concrete
questions for whoever picks this up:

1. Does `vt+0xf0(1)` reject our relocated windows during the tree walk (so they are never visited)?
2. Does `vt+0xf0(0x80000)` reject them after a successful geometric hit?

Both are answerable by logging `vt+0xf0`'s result for the HUD windows - one read-only run.

⚠️ **Also unverified:** whether the find-at-point tree walk from `sink+0x38` even reaches these
windows. Their parent is a common root (`0x00641B88` in run 41), but nothing has confirmed that root
is on the path from `sink+0x38`.

## Scorecard, honestly

Three consecutive confident fixes for clickability failed: the origin write (`+0x80/+0x84` alone -
left right/bottom stale, making the rect inside-out), the full-rect write (correct, still not
clickable), and before those the `+0x90`-only move. Each looked definitive. **The pattern was fixing
what I had just found rather than checking what else the code required**, and the flag gates were
visible in the same disassembly the whole time.

Other errors worth carrying forward:
- **`rz_modstr` had `"GZWIN.DLL"` for 37 runs; the file is `GZWIND.DLL`.** Every `(no known module)`
  result in this session's logs was degraded by it, including the stack-scan rankings. Now a PEB walk.
- Three features wired behind the wrong flag (lab-vs-ship twice, producer-vs-consumer once), each
  invisible in a log that looked internally consistent, each caught only by comparing runs.
- Run 24's tree walk threw 21 access violations from guessed offsets after I described it as
  "bounded and defensive".

## Tooling left behind

- `verify/resize_hudlab/auto.ps1` - path-loads a city, maximizes, holds, kills, prints results.
  **Env vars must be set in the parent shell** (`-EnvVars` with `pwsh -File` embeds quotes).
- Flags: `HUDLAB` (A/B phases + profiler), `SWEEP`, `SIDE`, `ANCHOR`, `CLUSTER`, `MINI`, `INPUT`,
  `HUDFIT`, `HUDNATIVE`.
- EIP sampler, ddraw `Blt` COM-slot timer with per-source/per-flag/dest-rect attribution, exact
  caller capture via `_ReturnAddress` and `f[9]`, PEB-walking symbol resolver.
