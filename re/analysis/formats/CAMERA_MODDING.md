# Changing SimCity 3000's camera scroll — the working procedure

**Status: the scroll-speed knob is validated in the running game, 2026-08-20/21**
(`verify/scroll_patch_test/RESULTS.md`, rungs S1/S2/S3). Two further knobs on this page,
`drag_divisor` and `edge_margin`: `drag_divisor` is now **validated at C3** (static byte-verified +
in-game surgical arithmetic, 2026-08-25); `edge_margin` is still **derived from the decompilation and
never run game-side** and must not be quoted as proven.

Tool: `re/tools/pe_patch.py`. Target: `Apps\SIMSPR.DLL`.

## Why this is a byte patch and not a config file

There is no INI, no registry key and no `SYS.PAK` member for camera scroll. The scroll step is a
`.rdata` float bank compiled into `SIMSPR.DLL`. Every other tunable this toolkit changes lives in a
shipped data file (`syspak_mod.py`, `sprite_patch.py`, `city_write.py`); this class of value has no
such home, so the only mechanism is a same-length overwrite of the module.

`pe_patch.py` makes that safe rather than reckless: every patch declares the bytes it expects to
replace and **refuses on a mismatch**, each recipe pins the input file's SHA-256, patches are
length-preserving by construction, and the input is never written to.

Verified before writing this page:

```
py -3.12 re/tools/pe_patch.py Apps --selftest
23 passed, 0 failed
```

That run also re-reads the shipped constants out of the file rather than trusting this document:
all five zoom steps ship `32.0f`, the drag dead zone `12.0f`, the drag clamp `80.0f`, both drag
divisors `-2`, and the eight edge displacements `(48, 64, -48, -64, 64, 48, -48, -64)`.

## Delivery: you replace the DLL. There is no loader hook.

**A standalone proxy-DLL vehicle was attempted and is closed — see `DEFERRED.md` D-001.** Both
`version.dll` and `winmm.dll` proxies are mapped into the process and correctly bound, and neither
one's `DllMain` or exports are ever entered. The remaining diagnoses needed either elevation or a
mutation of AppCompat state shared across the whole install, and buy only runtime configurability
over a mechanism that already works.

So the shipping shape of a camera mod is: **a patched `SIMSPR.DLL`, or the one-line command that
produces it.** That is how the validated result was obtained — the game loads the patched module
off disk with no injection involved.

## The knobs

### `scroll_speed` — keyboard and edge-scroll step  ✅ proven game-side

The step bank is five `float32`s at `.rdata` `0x10067690..0x100676a0`, **all shipped `32.0f`**.
`[CONFIRMED @ 0x100440b1]` copies them into the view object at construction; `+0x1c8` is the
**active** step, and `[CONFIRMED @ 0x10042d8a]` (ZoomIn) re-selects it by zoom index:

| zoom | `.rdata` slot | object field |
|---|---|---|
| 0 | `0x100676a0` | `+0x1dc` |
| 1 | `0x1006769c` | `+0x1d8` |
| 2 | `0x10067698` | `+0x1d4` |
| 3 (and the boot default) | `0x10067694` | `+0x1d0` → `+0x1c8` |
| 4 | `0x10067690` | `+0x1cc` |

`0x10067694` is both the zoom-3 slot and the construction default, because `0x100440b1` writes it
into `+0x1c8` unconditionally. The consumer `[CONFIRMED @ 0x10043daf]` reads `+0x1c8` and passes it
to Translate (vtbl `+0x34`) as ±step on one or both axes, for **both** the arrow keys (VK
`0x25`–`0x28`) and edge-scroll. One step, no ramp, no acceleration.

```
# SLOWER camera (the common request): shipped is 32.0, so 16 is half speed, 8 a quarter
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe scroll_speed=16 --out SIMSPR.DLL.slow

# double the scroll speed at every zoom level
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe scroll_speed=64 --out SIMSPR.DLL.fast

# or per zoom level (the shipped binary uses one value for all five, so zoom
# currently has no effect on scroll speed at all)
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe scroll_speed=z0:16,z3:64 --out SIMSPR.DLL.mine
```

Larger is faster. Omit `--out` for a dry run: the report prints every staged address, its file
offset, and the old and new value.

What the game runs showed: the shipped step reads `32.000` at `cSC3WinCityView+0x1c8` and a patched
one reads the patched value; with an arrow held 2.5 s the shipped build moves the camera origin
`-6848` world px and the all-zero build moves `0`. S2/S3 confirmed **one byte on disk moves exactly
one bank slot**, and that the active slot at the default zoom is `0x10067694`, three ways.

### `drag_divisor` — right-drag pan sensitivity  ✅ validated C3 (2026-08-25)

The mouse-drag path is **separate** from the step bank: `0x10043daf`'s `+0x1e6 != 0` branch uses
`+0x1f4`/`+0x1f8`, computed in `[CONFIRMED @ 0x10043a38]`. Drag velocity is
`(anchor - mouse) / -N` where `N` is the `imm8` of `push -2` at `0x10043a5e` (X) and `0x10043a68`
(Y), so a **smaller magnitude is more sensitive**: `-1` doubles it, `-4` halves it.

```
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe drag_divisor=1 --out SIMSPR.DLL.drag
```

The sign carries the direction and stays negative; `N=0` is refused (division by zero), and `N>128`
does not fit a signed `imm8`.

> **Validated at C3 — 2026-08-25.** Three independent legs:
> 1. **Static, byte-verified.** `drag_divisor=4` from shipped → `verify/drag_divisor_test/SIMSPR.DLL.drag4`
>    (sha256 `6ba82b2b…`); an independent `--diff` shows **exactly 2 bytes, `fe→fc` (−2→−4)** at
>    `0x10043a5e`/`0x10043a68`, scroll slots untouched.
> 2. **In-game arithmetic, surgical.** The harness `dragtest` calls `FUN_10042cfe` (arm) then
>    `FUN_10043a38` (update) on the live city view and reads back the velocity field: with the shipped
>    `-2`, anchor `(0,0)` + mouse `(100,40)` gives `velX=50.0 velY=20.0` = `(anchor-mouse)/-2` exactly.
>    Since drag4 changes ONLY those two imm8 bytes to `-4`, the same call computes exactly half.
> 3. **Routing CONFIRMED** from the decompilation: `0x10043daf`'s `+0x1e6 != 0` branch dispatches to
>    `FUN_10043a38`, which consumes these bytes.
>
> **Not measured: an OS-input-driven pan *feeling* half as fast.** A fully-faithful `rdrag:` instrument
> was built and run 2026-08-25; the `SendMessage(WM_RBUTTON*)` transport **moved the camera 0 px** (the
> validity gate caught it, no false verdict). The pan-recognition routing in GZWinD/winmgr polls
> `GetAsyncKeyState`, so a posted WM message without real async button state is never classified as a
> drag — only `SendInput` (which sets that state) would drive it. Owner accepted the surgical+static
> proof as sufficient; the SendInput "feel" test is optional gilding. Detail:
> `re/sessions/STATUS_camera.md`, `DEFERRED.md` D-002.

> That separation is also a **free negative control** for any step-bank test: if the step is zeroed
> and right-drag still pans, the game is running and reading input, so "nothing moved" cannot be a
> frozen client.

### `edge_margin` — the edge-scroll trigger band  ⚠️ never run game-side

Eight signed `lea` displacements build the edge hit rects `[CONFIRMED @ 0x10043989]`, shipped **64
horizontal, 48 vertical**. All eight move together so every ± pair stays consistent.

```
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe edge_margin=32,24 --out SIMSPR.DLL.edge
```

Range is 1..127 per axis (signed `imm8`).

### `scroll_zero` / `scroll_default_zero` — discriminators, not mods

`scroll_zero` sets all five slots to `0.0f`; `scroll_default_zero` sets only the zoom-3 slot,
isolating the selector. These exist to make a test falsifiable and have no use as a mod.

## Staging it into the install

**Move aside, never overwrite** — the same rule as `verify/tunable_mod_test/README.md`. The patcher
refuses to write over its own input, so the discipline only has to be kept at the copy step.

```powershell
Copy-Item Apps\SIMSPR.DLL Apps\SIMSPR.DLL.shipped      # once, and keep it
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe scroll_speed=64 --out SIMSPR.DLL.fast
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL.shipped --diff SIMSPR.DLL.fast   # re-check independently
Copy-Item SIMSPR.DLL.fast Apps\SIMSPR.DLL -Force
# to undo:
Copy-Item Apps\SIMSPR.DLL.shipped Apps\SIMSPR.DLL -Force
```

`--diff` reads two files and compares them without going through the patcher, so a claim of the form
"this differs from shipped by exactly 5 bytes at these addresses" is checkable independently of the
code that produced it. **Re-diff the staged file before interpreting any observation** — that became
a method rule in `verify/tunable_mod_test`.

## ⚠️ A shipped bug you may hit while testing this: the camera is not clamped

Filed as **`U-082`**, and ⚠️ **the clamp explanation below was investigated and does NOT hold — read
the correction.**

The camera *can* sit at negative coordinates: measured at origin `-1088` on a 192 map, with the whole
viewport left of x = -64. (⚠️ Earlier notes compared this against `0..48896`; that is SIMGEOM's
zoom-independent `(N-1) x 0x100` extent and is **8x the wrong scale** for this field, whose values sit
inside `0..6144 = N x tilepx` at zoom 2. Negative under either, but the number should not be reused.)
**And the view renders fine there** — the
frame shows the map edge, the terrain cross-section as a cliff and off-map void, with all UI correct.
So "the camera leaves the map, therefore the view dies" is **contradicted by measurement.**

Worse for the tidy story: on that run the origin was **already out of range before any input**
(`-722` at load), and the load-time camera turned out to be **non-deterministic** — the same save
loaded at `1356,266` in one run and `-722,1817` in another. So the earlier "it scrolled off the map"
reading may have been two different load positions rather than scrolling.

**What is still real:** the owner reports the camera works and then stops responding after moving
around a while, and a run did show **7 consecutive input taps moving nothing** — though it recovered
on the 8th, so it is intermittent, not terminal. Two taps also moved the camera the **wrong way**,
which no clamp explains.

⭐ **A mechanism has since been identified** (`LAUNCH_CONTROL.md` §31.14): SIMSPR has a **follow/track
re-centre** on the paint tick (`FUN_1000dc17` -> `FUN_1000ec0b` -> ScrollTo) that moves the camera with
**no input at all**, armed while `cellmap+0x354 != 0` and `+0x524 == 0`. A user scroll cancels it; its
own scroll does not. That is consistent with a camera that moves on its own and appears to fight you,
and it is **not** yet proven to be the cause of the reported symptom.

**None of this is caused by any patch on this page** — it was all observed with SIMSPR untouched. If
you hit it while testing a scroll-speed change, it is not your patch.

## Limits, stated

- Every address here is anchored to **one** `SIMSPR.DLL`, SHA-256
  `eec71500…09e9291d`. A different language build or a later EA release will be **refused**, by
  design, not silently mispatched.
- The PE `OptionalHeader` `CheckSum` ships as `0x00000000` in this module and is left alone. `--info`
  warns if a future target ships a non-zero one.
- **No code injection.** Operands change in place; instructions are never added. The one camera knob
  that would need that — the missing `1/sqrt(2)` on diagonal scroll, so diagonal movement is faster
  than straight — is deliberately absent from the recipe table rather than half-supported.
- `drag_divisor` is validated at **C3** (static byte-verified + in-game surgical arithmetic; see its
  section above). `edge_margin` is still static-only. The "one patched run each would settle them"
  estimate was wrong for the OS-input path: the pan routing needs real async button state, so a
  faithful drag needs `SendInput`, not a bare run.
- Zoom level 4's reachability in-game was never established, so the `z4` slot is untested.
- The `+0x32c` scroll-gate flag ("dirty-rect queue overflow → force full repaint", set at
  `FUN_1000d725:105`, cleared in `FUN_1000dc17`) is read from the decompilation and not
  runtime-witnessed. It is not a knob here, but it is on the same path.

## An alternative that needs no patch at all

`re/harness/src/sc3probe.c` `-pref` adds a real **"Camera Scroll Speed" slider** to the game's own
Preferences window and applies the value live (dragged 21.25 → 128.0 monotonically; shots
`pref1_202726.png`, `pref3_005306.png`). That is a nicer end-user shape than a patched DLL, and it
works — but it arrives by injection through the RE harness, which is not a distributable vehicle.
With the proxy route closed there is no way to ship it today. Recorded here so the option is not
rediscovered from scratch.
