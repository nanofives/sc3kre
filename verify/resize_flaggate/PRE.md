# PRE.md — the vt+0xf0 flag-gate probe (READ-ONLY)

**Written before the build. Committed before the run.** Score the run against this file and nothing
else.

## Why this run exists

The relocated HUD (`SC3RESIZE_CLUSTER=1`) renders correctly and is **not clickable**. Two candidate
causes have been positively excluded by measurement, not by argument:

- **Coordinates are innocent** — run 36, `verify/resize_hudlab/INPUT_RESULT.md`. 62 clicks, zero
  flagged outside the clamp, and six clicks measured *inside* the relocated bar rect
  `[1120 953 1719 1009]` at 1920x1009. The UI did not respond.
- **Geometry is correct** — run 42, `verify/resize_hudlab/HANDOFF.md`. All four position/extent
  representations move and all carry positive extents: window rect `+0x14..0x20`, hit-test rect
  `+0x80..0x8c`, paint dest `+0x90`.

What has **never been read at runtime** is the flag half of the hit test. The hit test is geometry
**AND** flags, and only geometry has been addressed.

## ⛔⛔ STOP — GATE 2 IS REFUTED STATICALLY, BEFORE THE RUN (2026-09-01)

**This probe's headline premise is wrong, and it was wrong in `HANDOFF.md` too.** The decompilation
of `FUN_1006ddbd` was read before building the instrument, and the `0x80000` flag **does not reject
a geometric hit**:

```c
/* [CONFIRMED @ SIMUI 0x1006ddbd] */
cVar1 = <geometric in-rect result>;
(**(code **)(*(int *)this + 0xf0))(0x80000);
if ((extraout_AL != '\0') && (cVar1 != '\0') && (*(int *)((int)this + 0x58) != 0)) {
    cVar1 = FUN_1006d91d(this,param_1);       /* per-pixel bitmap mask test */
    cVar1 = '\x01' - (cVar1 != '\0');         /* inverted */
}
return CONCAT31(uVar2,cVar1);
```

When `vt+0xf0(0x80000)` returns **false, the raw geometric result `cVar1` is returned unmodified.**
The flag being *set* only enables an **additional** per-pixel mask refinement through `this+0x58`.
It is an opt-in refinement, not a gate.

**And the flag is clear by default.** Both window base ctors initialise the flags field to `0x903`
`[CONFIRMED @ GZWIND 0x1001dd9a, SIMUI 0x1006c2f7]`, which is `0x800|0x100|0x2|0x1` — bit `0x80000`
is **not** in it. Only two functions ever set it and neither ever clears it
`[CONFIRMED @ SIMUI 0x100171dd, 0x1004faec]`. So for the overwhelming majority of windows this
branch never runs at all, and "the hit is discarded because the flag is clear" describes behaviour
that does not exist.

**How the error was made:** the `HANDOFF.md` asm excerpt read `je <reject>` off the disassembly. The
`je` does not jump to a reject — it jumps **past the mask-refinement block**, to the return of the
already-computed geometric result. The jump target was assumed rather than followed.

**This is the board's own recurring failure mode, caught one step earlier than usual for once:** a
confirmed code path (the `call [eax+0xf0]` is really there, with really that mask) was turned into a
confirmed cause without establishing that the mechanism was load-bearing. The only thing that
prevented another spent lease was reading the decompilation before building the probe.

## What survives of the two gates

1. `vt+0xf0(1)` — **still live.** `FUN_1001e748` gates each child on it **before recursing**, and a
   false result genuinely skips the child outright `[CONFIRMED @ GZWIND 0x1001e748]`. Bit `0x1` is
   **Show/Hide**: set by `FUN_1001f98c` / `FUN_1006deee`, cleared by `FUN_1001f999` / `FUN_1006defb`.
   It is set by default. So this is only the blocker if something in the relocation path hides the
   window.
2. `vt+0xf0(0x80000)` — **REFUTED, remove from the plan.** Not a gate.

## ⭐ SECOND FINDING — THERE ARE TWO HIT TESTS, AND THE MOD MOVED THE FIELD THAT DOES NOT DECIDE

The chain in `sc3resize.c`'s comment block names `FUN_1006ddbd` as "THE COMPARISON". It is not the
one `FUN_1001e748` calls.

| slot | function | compares |
|---|---|---|
| **`vt+0xe4`** | **SIMUI `FUN_1006de62`** | **`this+0x14/0x18/0x1c/0x20` — the WINDOW RECT** |
| `vt+0x1a0` | SIMUI `FUN_1006ddbd` | `this+0x80..0x8c`, as **extents**, against client-relative coords |

`FUN_1001e748`'s fallthrough calls **`vt+0xe4`** `[CONFIRMED @ GZWIND 0x1001e748]`, and
`FUN_1006de62` is a literal copy of GZWIND `FUN_1001f8ef`.

**And `FUN_1006ddbd` cannot be moved by translation.** Its compare is
`param_1 >= (this+0x88) - (this+0x80)` and `param_2 >= (this+0x8c) - (this+0x84)` — it reads those
four fields **only as a width and a height**, against coordinates that have already been transformed
to client-local. `rz_win_move_hit` translates the rect *preserving its size*, so both differences are
unchanged and **the function returns exactly what it returned before the move.** That fix was a
no-op for containment by construction.

⚠️ **What the `+0x80/+0x84` write DOES affect is the coordinate transform.** `vt+0xdc`
(`FUN_1006dd44`) computes the origin as the **sum of `vt+0x98`/`vt+0x9c` up the parent chain**, and
those slots read `[ecx+0x80]` / `[ecx+0x84]`. So `+0x80/+0x84` is a **link in a parent-relative
origin sum**, and the mod writes **absolute screen coordinates** into it. `[UNCERTAIN]` — whether
that is correct depends on whether these windows' parent chain is rooted at (0,0). If it is not,
the mod is double-counting the offset and *causing* a miss. **This is now the leading hypothesis and
it is the opposite of a missing fix: it is a write that may itself be the defect.**

A third possibility is open and must be distinguished from both:

3. The find-at-point walk from `sink+0x38` **never reaches these windows at all**, regardless of
   flags. Their parent is a common root (`0x00641B88` in run 41), but nothing has confirmed that root
   is on the path from `sink+0x38`. `[UNCERTAIN]` — this is unverified, not assumed false.

## What the probe does

**READ-ONLY. It writes no engine state and patches no code.** It queries flags the engine already
exposes and logs the answers.

For each captured HUD window (bar, side panel, minimap) it logs, at click time:

- the result of `vt+0xf0(1)`
- the result of `vt+0xf0(0x80000)`
- the window pointer, its class vtable, and its current hit rect `+0x80..0x8c`
- whether the walk from `sink+0x38` reaches the window

## Pre-registered outcomes

Scored on a real click landing inside a relocated HUD window's hit rect (the click position must be
verified against the logged rect — an unverified "no response" is not evidence, per run 36).

| # | observation | verdict | what it means |
|---|---|---|---|
| **A** | `vt+0xf0(1)` returns **false** for a relocated window | **Gate 1 is the blocker** | The tree walk skips it. Fix targets whatever bit 0x1 means and why relocation cleared it. |
| **B** | `vt+0xf0(1)` true, `vt+0xf0(0x80000)` **false** | **Gate 2 is the blocker** | Visited and geometrically hit, then discarded. Fix targets bit 0x80000. |
| **C** | Both flags **true**, still not clickable | **Both gates exonerated** | The defect is elsewhere — most likely outcome 3 (the walk never reaches these windows) or downstream of the hit test entirely. |
| **D** | The walk from `sink+0x38` demonstrably never reaches the windows | **Outcome 3 confirmed** | Flags are moot. The fix is a parenting/registration problem, not a flag problem. |
| **VOID** | The probe cannot resolve `vt+0xf0`, or dispatching it faults, or no click is verified inside a logged hit rect | **VOID** | Do not interpret. Fix the instrument and re-run. |

## Falsification conditions, stated in advance

- **If both flags read true (outcome C), I do not get to claim a flag fix.** The flag hypothesis is
  then falsified and must be written up as falsified, not quietly dropped.
- **A flag reading false is not by itself a confirmed cause.** Standing board rule: *a confirmed code
  path is not a confirmed cause.* Outcome A or B identifies the gate that rejects; it does not prove
  that clearing the gate makes the HUD clickable. That needs a separate build and a separate run.
- **No fix is designed in this run.** The handoff's scorecard records three consecutive confident
  clickability fixes that failed, each because the pattern was *fixing what had just been found
  rather than checking what else the code required*. Both flags get read before anything is built.

## Instrument-safety rules carried in

- **Expect-or-refuse, never dispatch-to-identify.** Resolve `vt+0xf0` and validate the vtable against
  a known `MODULE+RVA` before calling through it. Never dispatch through a pointer in order to decide
  what that pointer is (the `GetSurfaceDesc` crash, BOARD.md).
- **No guessed offsets on a tree walk.** Run 24 threw 21 access violations from guessed offsets after
  being described as "bounded and defensive". Every offset used here is cited or the read is skipped.
- **SEH around the dispatch**, with the MODULE+RVA fault resolver already in the DLL.
- **`rz_modstr` uses the PEB walk** (`GZWIND.DLL`, not the `GZWIN.DLL` typo that degraded 37 runs).

## Verdict

*(filled in after the run — leave empty until then)*
