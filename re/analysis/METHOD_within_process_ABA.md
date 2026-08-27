# METHOD — transport-independent within-process A/B/A

A reusable measurement pattern for validating a **byte-patch value knob** in the running game
**without being able to drive the real input** that normally reaches the code. Invented by the
camera workstream (2026-08-25) to take `drag_divisor`, `edge_margin` and `drag_deadzone` from
"derived from the decompilation, never run" to **C3, observed at runtime**. Recorded here so the
next value-knob subsystem does not rediscover it from scratch.

## The problem it solves

Many tunables in this game are `imm8`/`.rdata` constants consumed by a function that is only ever
reached through **real OS input** (a mouse drag, an edge-scroll, a keypress). Two independent walls
block the obvious "synthesise the input and measure the pixels" approach:

1. **The input transport does not work headless.** A posted `WM_RBUTTONDOWN` (`SendMessage`) is never
   classified as a drag, because the routing layer that recognises a right-drag polls
   `GetAsyncKeyState`, which a posted message does not set. And `SendInput` (which *does* set async
   state) still moves the camera **0 px** in the capture harness, because there is no true
   foreground window on a real display for the OS to deliver to. Both were tried and both failed
   (D-002). So the gesture that reaches the code cannot be manufactured here at all.
2. **Cross-process reads are ambiguous.** Comparing "shipped build" vs "patched build" across two
   separate launches means comparing two different process states — and the `cam`-object locator
   returns the FIRST object matching a vtable and stops, so which camera object you measured can vary
   per process (BOARD debt item 2). A delta between two launches is not trustworthy.

## The pattern

Do not drive the input. **Call the pure computation directly, and change the constant between calls,
inside one process.** Three legs:

```
measure at shipped constant   →  A
hot-patch the constant live    →  measure again  →  B
restore the shipped constant   →  measure again  →  A'
```

The verdict is `A → B → A'`, not just `A → B`. **The return-to-baseline third leg (`A'`) is what
makes it a measurement and not a coincidence:** it proves the delta tracked *the constant you
changed* and nothing else drifting in the process (churn, a background re-centre, allocation state).
`A == A'` with `B` different is the signature of a real, isolated effect.

Because both measurements happen in **one process on one object**, the pattern sidesteps BOTH walls
at once: no input transport is needed (leg calls the computation function directly), and there is no
cross-process object ambiguity (same object, same launch).

## What makes a knob eligible

The consumed constant must feed a function you can **call in isolation and read the result of** —
ideally a **pure computation** (reads object fields, writes object fields, no vtable dispatch, no
side effect on the live camera/sim). Check the decompilation before building the instrument:

- `FUN_10043a38` (drag velocity): reads anchor + mouse, writes `+0x1f4/+0x1f8`. Pure enough — the
  `dragtest` verb arms the anchor (`FUN_10042cfe`) then calls it and reads back the velocity fields.
- `FUN_10043989` (edge hit-rects): reads view bounds, writes 8 rect fields, **no vtable, no camera
  side-effect** — a clean pure computation, `edgetest` calls it and reads the 8 displacements.

If the function has camera/sim side-effects you cannot call it freely for a measurement; find the
pure sub-computation, or fall back to a runtime witness of the field it writes.

## Harness shape (the verbs)

Two verbs per knob, both already in `re/harness/src/sc3probe.c`:

- a **measure** verb that locates the live view object and calls the pure computation:
  `dragtest[:mx,my]`, `edgetest`.
- a **hot-patch** verb that writes the constant into the loaded module's memory (not the file) for
  the B leg, then is called again to restore for A':
  `setdiv:-N` (drag divisor imm8), `setedge:H,V` (8 edge imm8s), `setdead:N` (dead-zone f32).

The hot-patch must be **byte-equivalent to the shipped patcher's output** — verify with
`pe_patch.py --diff` first that the recipe changes exactly the bytes `setX` flips, so the live A/B/A
and the shipped DLL are the same change (e.g. drag4 is the two imm8 bytes `FE→FC` and nothing else).

## Pre-registration (mandatory, same as any run)

- **A validity/negative control leg.** An **idle-drift** read before the gesture must be ≈ `(0,0)`;
  drift comparable to the measured delta means the process is churning and the run is VOID (this
  caught a false positive — a `-6368` "movement" that was camera churn, not the instrument, read off
  an idle control of `(176,128)` and correctly voided).
- **A confirm and a falsify, in numbers.** State the expected `A`, `B`, `A'` before the run. Example:
  drag `velX 50 → 25 → 50`; edge band `48/64 → 24/32 → 48/64`; dead-zone engage `velX 0 → 8 → 0`.
  Ratio ~1.0 (patch inert) or `A != A'` (not isolated) **falsifies**.
- **Same object every leg.** Assert the `cam` locator returns a single candidate and it is the same
  object across all three legs (`cityViewIso+0x158`), so the debt-item-2 ambiguity cannot apply.

## Honest scope of the result — what A/B/A does and does NOT prove

It proves the **geometry/arithmetic the game computes** from the constant, at runtime, on the live
object (**C3**). It does **not** prove the **OS-input "feel"** — that a real mouse gesture routes
through this same function and the user perceives the change — because the input transport that would
close that leg is environment-blocked (D-002). Report the knob as *observed at the geometry level*,
and keep the feel leg as an explicit open item that needs a run on a real foreground display. Do not
let a confirmed code path masquerade as a confirmed felt effect.

## Results this pattern has produced (camera)

| knob | A/B/A witnessed | confidence | doc |
|---|---|---|---|
| `drag_divisor` | velX `50 → 25 → 50` (bytes `FE→FC→FE`) | C3 geometry | `formats/CAMERA_MODDING.md` |
| `edge_margin` | band `48/64 → 24/32 → 48/64` | C3 geometry | `formats/CAMERA_MODDING.md` |
| `drag_deadzone` | engage velX `0 → 8 → 0` (dz `12→4→12`) | C3 geometry | `formats/CAMERA_MODDING.md` |

Full run records: `re/sessions/STATUS_camera.md`, `re/sessions/STATUS_camerafeel.md`.
