# CLICKPATH_RESULTS.md — ⭐⭐⭐ THE WHOLE INVESTIGATION WAS ON THE WRONG CODE PATH

**2026-09-01, Frida, four game runs, zero human clicks.** Tool: `re/tools/frida_clickpath.py`.
Raw: `clickpath.json`, `gate.json`, `button.json`.

## Verdict

**Normal in-game clicks never execute `FUN_1001e748`, the walk that this project has spent two
sessions instrumenting.** They take a different function entirely, and that function has never been
looked at.

## The measurement that forced it

Posted real `WM_LBUTTONDOWN` messages and traced the engine handling them.

| run | `sink+0x28` (capture) | `sink+0x30` (focus/modal) | walk entries |
|---|---|---|---|
| `clickpath.json`, 3 points | `0x0` | *(not read)* | **0** |
| `button.json`, 4 points | `0x0` | **`0x0`** | **0** |
| `gate.json`, `bar_new` | `0x0` | **`0xf4f6d68`** (a dialog, `[246 163 553 437]`) | **48** |

The gate is explicit in the decompilation `[CONFIRMED @ GZWIND 0x10020818]`:

```c
piVar4 = *(int **)((int)this + 0x28);
if (piVar4 == 0) {
    if (*(int **)((int)this + 0x30) == 0) {
        return (**(code **)(**(int **)((int)this + 0x38) + 0x130))(param_1);  /* <<< NO HIT TEST */
    }
    /* ... only here is the vt+0x8c walk ever reached ... */
}
```

**`sink+0x30` is NULL during normal play**, so every mouse event early-returns through
`(sink+0x38)->vt[0x130]`. The `vt+0x8c` walk runs *only* when a modal/focus window exists.

## ⭐ And when the walk DID run, it worked perfectly

In `gate.json` a dialog was open, so `+0x30` was non-null and the walk executed. It was asked
**`(1547,1053)` — the exact posted coordinates, unclamped** — recursed through the children, and
returned:

```
WALK LEAVE ret=0xe45ebf0 retRect=[1248, 1025, 1847, 1081]
```

**That is exactly the relocated bar.** Coordinates arrive intact and the hit test resolves them
correctly. This independently confirms `HITTEST_RESULTS.md` on the real event path rather than by an
out-of-band call.

## The path normal clicks actually take

`(sink+0x38)->vt[0x130]` = **`GZWIND FUN_1001ec22`** (read from `Apps/GZWIND.DLL` `.rdata`,
vtable `GZWIND+0x2d764` slot `+0x130`). It is a *second, independent* traversal:

```c
/* [CONFIRMED @ GZWIND 0x1001ec22] */
for (child in this+0x34) {
    if ((*child->vt[0x100])()             != 0 &&        /* gate 1: no arguments */
        (*child->vt[0xe4])(ev[1], ev[2])  != 0) {        /* gate 2: point-in-window */
        ...
        return (*child->vt[0x130])(ev);                  /* recurse into the child */
    }
}
```

Same child list `+0x34`, but a **different gate (`vt+0x100`, not `vt+0xf0(1)`)** and a different
recursion slot. `vt+0xe4` = `FUN_1001f8ef` compares `+0x14..0x20`, the rect the mod does move.

## Scorecard — this is the expensive kind of error

Everything below was measured correctly and was about a path normal clicks do not take:

- the `vt+0xf0(0x80000)` "gate" (refuted; also on the wrong path)
- the `vt+0xf0(1)` shown bit (`FUN_1001e748` only)
- `+0x80..0x8c` hit rect (`FUN_1006ddbd`, reached from the walk)
- reachability from `sink+0x38` via `vt+0x8c`
- `rz_win_move_hit`, three commits, which never wrote a byte

The chain in `HANDOFF.md` and in `sc3resize.c`'s comment block is **accurate and irrelevant**: it
documents what happens when a dialog is open. The board's standing warning is exactly this failure —
*a confirmed code path is not a confirmed cause* — and the missing question was never "does this code
do what I think?" but **"is this the code that runs when a user clicks?"** One `PostMessage` with a
hook on the dispatcher answers it, and it was available the whole time.

## Next, and it is narrow

Instrument **`FUN_1001ec22`**, not `FUN_1001e748`:

1. Log `vt+0x100()` per child — the gate that runs *before* any geometry.
2. Log `vt+0xe4(x,y)` per child and its result.
3. Resolve both slots from each **live** child's vtable (the mistake corrected in
   `HITTEST_RESULTS.md`: hard-coded SIMUI copies never fired because classes override the slots).

Two candidate outcomes, both cheap to separate: the relocated windows fail `vt+0x100` and are
skipped before geometry, or they pass it and fail `vt+0xe4`.

## `[UNCERTAIN]` — stated, not glossed

- **Why `sink+0x30` is NULL is not established.** It may be normal for in-city play, or it may
  itself be resize damage. Not measured, and it matters: if the mod nulls it, that is a second
  defect.
- `button.json`'s three button points produced **no walk and no dispatch geometry**, so nothing is
  known about whether individual HUD buttons resolve. They were posted at rects harvested from a
  *different* run; the coordinates are plausible but unverified for that session.
- Posted messages are not hardware input. Every result here is about `WM_*` delivery. The board
  already records (`D-002`) that synthetic input has behaved differently from real input in this
  game.
