# HITTEST_PRE.md — does the walk reach the relocated HUD? (2026-09-01)

**Written and committed before the run. Score against this file only.**

Tool: `re/tools/frida_hittest.py` (Frida 17.9.3, attach to a running `SC3U.exe`). No human clicks.

## Why this run

Every geometric explanation for the unclickable HUD is exhausted:

| field | state | evidence |
|---|---|---|
| `+0x14..0x20` window rect | moved, correct | `CLUSTER>` lines; it is what `FUN_1006de62` compares |
| `+0x80..0x8c` extents | correct, **engine-maintained** | `NOHIT_RESULTS.md` — our write never executes |
| `+0x90` paint dest | moved, honoured | the HUD visibly renders in the corner |
| `vt+0xf0(0x80000)` | **not a gate** | refuted statically, `PRE.md` |

The untested link is **reachability**: `FUN_1001e748` only ever recurses into children of
`this+0x34`, and each child is gated on `vt+0xf0(1)` **before** recursion
`[CONFIRMED @ GZWIND 0x1001e748]`. Nothing has confirmed the relocated windows are on the path from
`sink+0x38`.

## What the probe does

Inside the **WndProc, on the game thread**, it resolves
`win = *(GZGraphicD+0x6cdb8)` → `sink = *(win+0x30)` → `root = *(sink+0x38)`, reads
`root`'s **live** vtable slot `+0x8c`, and calls it with each probe point. It logs the returned
window plus, during the call only, every `vt+0xf0` flag query and every `FUN_1006de62` /
`FUN_1006ddbd` comparison.

`vt+0x8c` is resolved live, not hard-coded: SIMUI statically links its own copy of the window base
class, so a child's find-window-at-point is a **different function** from the root's.

## Probe points (from the control run, `smoke_armB.log`, at 2048x1081)

| name | point | inside | expectation if the walk is healthy |
|---|---|---|---|
| `bar_new` | (1547, 1053) | relocated bar `[1248 1025 1847 1081]` | returns the bar window |
| `bar_native` | (299, 572) | the bar's **old** rect `[0 544 599 600]` | returns **nothing** (the bar moved away) |
| `side_new` | (2000, 702) | side panel `[1952 481 2048 923]` | returns the side panel |
| `mini_new` | (1968, 999) | minimap `[1888 917 2048 1081]` | returns the minimap |
| `viewport` | (400, 300) | open city view | control — returns whatever normally owns it |

## Pre-registered outcomes

| # | observation | verdict |
|---|---|---|
| **R-REACHED** | `bar_new` / `side_new` / `mini_new` return the relocated windows | **The walk reaches them and geometry passes.** Reachability is exonerated; the blocker is *downstream* of the hit test — in dispatch or in the click-to-hit-test coordinate handoff. |
| **R-UNREACHED** | those points return NULL or a non-HUD window, **and** `bar_native` also returns nothing | **The windows are off the walk's path entirely.** A parenting/registration defect, not geometry and not flags. |
| **R-STALE** | `bar_native` returns the bar window while `bar_new` does not | **Something on the hit path still uses native geometry** — the original board framing, finally with direct evidence. |
| **R-FLAGGED** | the points return NULL and the flag log shows `vt+0xf0(1)` returning **0** for a HUD window | **The shown bit is the blocker.** The surviving suspect from `PRE.md`. |
| **VOID** | probe never fires, a module is missing, the call faults, or `viewport` (the control) returns nothing | Do not interpret. Fix the instrument and re-run. |

**The `viewport` control decides whether the instrument works at all.** If a point over the open
city view returns nothing, the probe is not exercising a functioning walk and every other result is
uninterpretable. This is the check the surface-census work skipped three times, each time producing
a confident reading of a broken instrument.

## Stated in advance

- **R-REACHED is a real possible outcome and would refute my current framing.** It would mean the
  hit test works and I have been looking in the wrong half of the chain all session.
- A NULL for `bar_new` **does not by itself** mean unreachable — it could be flags, geometry, or
  path. The flag log and the comparator trace are what separate those, which is why both are
  captured in the same call.
- **This measures the engine's walk called out of band, not a real click.** It is one step removed
  from the user-visible behaviour. If it disagrees with a real click, the real click wins.
- No fix is designed from this run.

## Verdict

*(filled in after the run)*
