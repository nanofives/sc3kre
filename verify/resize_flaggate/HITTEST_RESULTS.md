# HITTEST_RESULTS.md — **R-REACHED.** The hit test finds the relocated HUD.

**2026-09-01, one lease, no human clicks.** Scored against `HITTEST_PRE.md` (committed `a3fee81`,
before the run). Raw: `hittest.json`, run log `hittest_run.log`.

## Verdict: R-REACHED

The engine's own find-window-at-point walk, called on the game thread from `root = *(*(*(GZGraphicD
+0x6cdb8)+0x30)+0x38)` through its **live** `vt+0x8c`, returns the relocated windows:

| point | | returns | rect of the returned window |
|---|---|---|---|
| `bar_new` | (1547,1053) | `0xe2eea68` | **`[1248 1025 1847 1081]`** — exactly the relocated bar |
| `side_new` | (2000, 702) | `0xdfe60a8` | `[1985 700 2041 732]` — a widget inside the relocated side panel |
| `mini_new` | (1968, 999) | `0xddcc0f8` | `[1902 932 2031 1061]` — inside the relocated minimap |
| `bar_native` | (299, 572) | `0xeedd5bc` | `[0 0 800 600]` — **not** the bar; the bar really did move away |
| `viewport` | (400, 300) | `0xeedd5bc` | `[0 0 800 600]` — **control passes**, the walk is functioning |

The control is what makes this readable: a point over the open city view returns a real window, so
the walk was exercised and working when the HUD points were tested.

**So reachability is exonerated, and so is the shown bit.** The relocated windows are on the path
from `sink+0x38`, they are visited, and they win the point. `R-UNREACHED`, `R-STALE` and
`R-FLAGGED` are all **falsified**.

**This refutes my own framing from earlier today.** I said the surviving suspects were walk
reachability and `vt+0xf0(1)`. Both are now excluded. The hit test is not the blocker.

## Corroboration of the static read

`root` vtable resolves to **`GZWIND+0x2d764`** — the exact `PTR_FUN_1002d764` base-window vtable the
decompilation pass identified, and `vt+0x8c` resolves to **`GZWIND.DLL+0x1e748`** = `FUN_1001e748`.
The static chain and the live objects agree.

## ⭐ THE NEW LEAD — the UI root window is still 800x600

```
root : 0x53f708  rect [0, 0, 800, 600]  flags 0x903
```

The client area is **2048x1081**. The `D-004` fix updates the *GZGraphicD* window object's stored
rect (`win+0x38..0x44`), but **this UI root window's own rect `+0x14..0x20` is stale at 800x600.**

My probe **bypassed** whatever sits between a real click and this walk: it called `vt+0x8c`
directly with raw client coordinates. The real path is
`WndProc FUN_10017e2f -> (win+0x30)->vt[0x64] = GZWIND FUN_10020818 -> (sink+0x38)->vt[0x8c]`.
**If anything in that upper segment clamps or transforms the point against the root's stale
800x600, a real click at (1547,1053) never arrives as (1547,1053)** — and the walk would then be
asked about the wrong point, which is entirely consistent with everything measured so far:
geometry correct, walk healthy, clicks still dead.

`[UNCERTAIN]` — **not established.** No measurement here shows what coordinates a real click
delivers to the walk. That is the next run, and it is the whole question.

## ⚠️ Instrument gap — declared, not buried

`flagCalls=0` and `comparators=0` for **every** point. The hooks on `SIMUI FUN_1006dedb` (flag
query), `FUN_1006de62` (vt+0xe4) and `FUN_1006ddbd` (vt+0x1a0) attached without error and **never
fired**, although `FUN_1001e748` provably calls `vt+0xf0(1)` per child.

The reason is visible in the data: the returned windows carry **class-specific vtables**
(`SIMUI+0xa40ec`, `+0xa8f60`, `+0xa7e68`, and the root's children `SIMUI+0xa9cc8` x12), and those
classes override the slots. The three functions I hooked are the copies found in *other* SIMUI
vtables. `bar_native`/`viewport` return an object whose vtable (`0x33776ac`) is not even in the
range I resolved.

**So `flagCalls=0` means "my hooks were on the wrong functions", NOT "no flags were queried".** It
is an instrument gap and must not be cited as evidence about flags. The R-REACHED verdict does not
depend on it — that rests on the returned pointer and its rect, which is a direct comparison, not a
proxy.

**Fix for next time:** resolve `vt+0xe4` / `vt+0xf0` from each *live* window's own vtable and hook
those addresses, the same way `vt+0x8c` was resolved. I applied that discipline to one slot and not
to the other three.

## What is now excluded, cumulatively

| candidate | status |
|---|---|
| window rect `+0x14..0x20` | correct on the HUD windows, and it is what the walk compares |
| extents `+0x80..0x8c` | engine-maintained; our write never executes (`NOHIT_RESULTS.md`) |
| paint dest `+0x90` | moved and honoured — the HUD renders |
| `vt+0xf0(0x80000)` | not a gate (static, `PRE.md`) |
| `vt+0xf0(1)` shown bit | **excluded** — the windows are visited and returned |
| walk reachability | **excluded** — the walk returns them |
| WndProc coordinate clamp | excluded by run 36 (62 clicks, zero clamped) |

**Remaining, and now narrow: the segment between the WndProc and the walk** — `FUN_10020818` and
whatever it does to the point — **or the dispatch that happens after the window is found.**

## Next run (no human needed)

Hook `FUN_10017e2f` (WndProc), `FUN_10020818` (mouse dispatch) and `FUN_1001e748` (the walk), then
**`PostMessage` a real `WM_LBUTTONDOWN` at (1547,1053)** and log the coordinates at each stage. If
the WndProc sees (1547,1053) and the walk is asked about something else, the defect is located
exactly.

## Verdict line for the board

**The unclickable HUD is not a hit-testing defect.** The engine's hit test, asked directly, returns
the relocated bar, side panel and minimap for points inside them.
