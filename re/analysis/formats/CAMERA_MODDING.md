# Changing SimCity 3000's camera scroll — the working procedure

**Status: the scroll-speed knob is validated in the running game, 2026-08-20/21**
(`verify/scroll_patch_test/RESULTS.md`, rungs S1/S2/S3). Three further knobs on this page,
`drag_divisor`, `edge_margin` and `drag_deadzone` are all **observed in a running game (C3)** via
transport-independent within-process A/B/A tests (the technique is written up as a reusable method in
[`re/analysis/METHOD_within_process_ABA.md`](../METHOD_within_process_ABA.md)): `drag_divisor`'s
velocity halves `50→25→50` across `-2/-4/-2`, `edge_margin`'s trigger band moves
`48/64 → 24/32 → 48/64`, and `drag_deadzone`'s engage gate flips a near-threshold sample
`velX 0 → 8 → 0` across dead zone `12 → 4 → 12`. All three validate
the geometry the game computes; the OS-input "feel" leg is **not** measured — both a `SendMessage` and
a `SendInput` right-drag moved the camera 0 px in the headless harness (D-002, still open). The owner's
standing install is `scroll_speed=8 + drag_divisor=4 + drag_deadzone=2` (retuned gentler 2026-08-26;
the diagonal was confirmed better by the owner's own feel, which the headless harness could not test).

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

### `drag_divisor` — right-drag pan sensitivity  ✅ C3, drag4 halving OBSERVED in-game (2026-08-25)

The mouse-drag path is **separate** from the step bank: `0x10043daf`'s `+0x1e6 != 0` branch uses
`+0x1f4`/`+0x1f8`, computed in `[CONFIRMED @ 0x10043a38]`. Drag velocity is
`(anchor - mouse) / -N` where `N` is the `imm8` of `push -2` at `0x10043a5e` (X) and `0x10043a68`
(Y), so a **smaller magnitude is more sensitive**: `-1` doubles it, `-4` halves it.

> ⚠️ **Changing `N` also moves the right-drag ENGAGE DISTANCE, because the dead-zone gate is tested
> on the post-divisor velocity.** The drag does not engage until `|(anchor-mouse)/N| > deadzone`, so
> the engage distance is `deadzone * N` px: shipped `12 * 2 = 24`, but a `drag_divisor=4` build
> engages at `12 * 4 = 48` px. This is a real regression trap: raising `N` to slow the pan makes it
> "start after getting away from the initial point too much" (owner report, 2026-08-25). If you slow
> the pan with `N`, lower `drag_deadzone` (below) to keep the engage distance where you want it.
> `[CONFIRMED @ 0x10043a38 + 0x10043a5e]`

```
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe drag_divisor=1 --out SIMSPR.DLL.drag
```

The sign carries the direction and stays negative; `N=0` is refused (division by zero), and `N>128`
does not fit a signed `imm8`.

> **drag4's halving is OBSERVED in a running game — 2026-08-25.** A within-process A/B/A on the live
> Europolis city view (`cam;dragtest;setdiv:-4;dragtest;setdiv:-2;dragtest;cam`), the `dragtest` being
> a **direct call** to `FUN_10042cfe`+`FUN_10043a38` and so **independent of any input transport**:
>
> | live bytes `@+0x43a5e/68` | velX `+0x1f4` | velY `+0x1f8` |
> |---|---|---|
> | `-2` (`FE FE`, shipped) | **50.0** | 20.0 |
> | `-4` (`FC FC`, hot-patched live) | **25.0** | 0.0 |
> | `-2` (`FE FE`, restored) | **50.0** | 20.0 |
>
> **velX 50→25→50 is the halving, observed, with the bytes verified flipping `FE→FC→FE`.** The velY=0
> at `-4` is **not** a miss: velY there is `(0-40)/-4 = 10`, below the confirmed deadzone
> `12 < |v| <= 80` `[CONFIRMED @ 0x10043a38]` (`_DAT_100676a4 = 12`), so `+0x1f8` is correctly not
> written and keeps its idle 0 — the deadzone gating observed alongside the halving. (Test point y=40
> is simply too small for the Y axis at `-4`; the X axis, y-independent, is the clean witness.)
>
> Backing legs: **static byte-verified** (`verify/drag_divisor_test/SIMSPR.DLL.drag4` sha256 `6ba82b2b…`,
> `--diff` = 2 bytes `fe→fc`, scroll slots untouched) and **routing CONFIRMED** (`0x10043daf`'s
> `+0x1e6 != 0` branch → `FUN_10043a38`). Confidence **C3**.
>
> **Not measured: the OS-input "feel."** A faithful `rdrag:` instrument (`SendMessage(WM_RBUTTON*)`)
> moved the camera 0 px (2026-08-25), and a `rinput:` instrument using **`SendInput`** (OS-level, sets
> `GetAsyncKeyState` state) **also moved the camera 0 px on a clean negative control** (2026-08-25,
> idle drift `(0,0)`, gesture Δ `(0,0)`). So the "only SendInput would drive it" hypothesis is
> **falsified in this harness**: the blocker is now the **headless capture environment** — the frame is
> rebuilt from the blit mirror with no real display, so the game window is not a true foreground/focused
> window and injected input is not delivered to it. A first run that showed movement was contaminated by
> camera churn (its idle control read `(176,128)`) and correctly voided. `[UNCERTAIN]` whether SendInput
> arms the pan against a real foreground window on a real display — untestable headless. The arithmetic
> effect is already observed above; D-002's feel leg stays open. Detail: `re/sessions/STATUS_camerafeel.md`.

> That separation is also a **free negative control** for any step-bank test: if the step is zeroed
> and right-drag still pans, the game is running and reading input, so "nothing moved" cannot be a
> frozen client.

### `drag_deadzone` — right-drag engage threshold & onset  ✅ C3, engage flip OBSERVED in-game (2026-08-25)

The single lever behind the owner's three right-drag complaints ("engages too late", "diagonal has a
very short window", "starts too fast — start sooner and slower"). Drag velocity is computed from the
**anchor** and the dead zone is a hard **per-axis gate applied after the divide**
`[CONFIRMED @ 0x10043a38]`: an axis does not pan until `|v| > deadzone`, and at that instant its
velocity field steps discontinuously from 0 to ~`deadzone`. So one constant sets all three feels:

- **engage distance** = `deadzone * |divisor|` px. Shipped `12 * 2 = 24` px; on the `drag_divisor=4`
  build `12 * 4 = 48` px (the divisor the owner chose for a *slower* pan doubled the "starts too late").
- **onset step** = the 0→`deadzone` jump. The divisor does not soften it; only the dead zone does.
- **diagonal band.** The gate is **per-axis (a box), not a radius, and there is no axis-lock or
  dominant-axis rule** `[CONFIRMED @ 0x10043a38]`. An axis pans only when *it alone* clears the dead
  zone, so off-axis drags snap to pure H/V in the "arms" of a plus shape and diagonal exists only in
  the corner quadrants past **both** per-axis dead zones. A smaller dead zone thins the arms and widens
  the diagonal band.

`DRAG_DEADZONE_VA = 0x100676a4`, ships `12.0f`. The clamp (`0x100676a8`, `80.0f`) is a separate cap and
is not implicated in any of the three symptoms.

```
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe drag_deadzone=4 --out SIMSPR.DLL.dead
```

Range `0 <= N < 80` (below the clamp, or no proportional band remains); `0` disables the gate (pans on
any motion, risking tremor drift). Larger engages later and jumps harder.

> **Observed in a running game — 2026-08-25** (Europolis, transport-independent direct call, the same
> `dragtest` trick that measured `drag_divisor`). `setdead:N` hot-patches the dead-zone f32 live; a
> near-threshold sample `dragtest:16,0` on shipped divisor `-2` (`raw = 16/2 = 8`):
>
> | live dead zone | velX (+0x1f4) |
> |---|---|
> | `12.0` shipped | **0.000** (8 <= 12, dead) |
> | `4.0` (`setdead:4`) | **8.000** (4 < 8 <= 80, band) |
> | `12.0` restored | **0.000** |
>
> **velX 0 → 8 → 0 as the dead zone flips 12→4→12**, while a `(100,40)` control stays `50/20` (the knob
> only changes the near-threshold engage, not general motion). Confidence **C3**, geometry level. As
> with `drag_divisor`, the OS-input "feel" (a real drag engaging sooner) is not measured — same headless
> blocker as D-002. Staged live in the owner's build (at `2.0` since the 2026-08-26 gentler retune).

### `edge_margin` — the edge-scroll trigger band  ✅ C3, band change OBSERVED in-game (2026-08-25)

Eight signed `lea` displacements build the edge hit rects in `FUN_10043989` `[CONFIRMED @ 0x10043989]`,
shipped **64 horizontal, 48 vertical**. All eight move together so every ± pair stays consistent.

```
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --recipe edge_margin=32,24 --out SIMSPR.DLL.edge
```

Range is 1..127 per axis (signed `imm8`).

> **Observed in a running game — 2026-08-25.** `FUN_10043989(view)` is a **pure computation** (reads
> view bounds `+0xd8/+0xdc/+0xe0/+0xe4`, writes 8 rect fields `+0x178..+0x1c4` as `base ± margin`, no
> vtable call, no camera side-effect), so the harness `edgetest` calls it directly and reads back the
> band — transport-independent, the same trick that measured `drag_divisor`. A within-process A/B/A on
> the live Europolis city view:
>
> | live edge imm8 | rect displacements (V+, H+, V-, H-) |
> |---|---|
> | `48,64,…` shipped | `+48, +64, -48, -64` |
> | `24,32,…` (`setedge:32,24`) | `+24, +32, -24, -32` |
> | `48,64,…` restored | `+48, +64, -48, -64` |
>
> **The trigger band the live game computes tracks the imm8 bytes: 48/64 → 24/32 → 48/64**, all three
> `edgetest` verdicts PASS (displacement == byte). Confidence **C3**. As with `drag_divisor`, this
> validates the geometry the game computes, not the OS-input "feel" (mouse actually triggering scroll
> closer to / farther from the edge), which would need the `SendInput`-class instrument. `edge_margin`
> is **not staged live** — only `scroll_speed=16 + drag_divisor=4` are.

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
- ⚠️ **`drag_divisor` and `drag_deadzone` are COUPLED — do not tune one without the other.** The
  dead-zone box is tested on the post-divide velocity, so the right-drag **engage distance is
  `drag_deadzone × drag_divisor` px** (shipped `12 × 2 = 24`; a `drag_divisor=4` build alone jumps to
  `12 × 4 = 48`, the "starts too late" regression the owner hit). Slow the pan with the divisor and
  the dead zone must come down to hold the engage distance. Full mechanism in the `drag_divisor` and
  `drag_deadzone` sections above. `[CONFIRMED @ 0x10043a38 + 0x10043a5e]`
- `drag_divisor`, `edge_margin` and `drag_deadzone`: all **C3, observed in-game** via within-process
  A/B/A (velX `50→25→50`; band `48/64→24/32→48/64`; engage `0→8→0`) plus static byte-verified. The
  OS-input "feel" leg is not measured for any of them: **both** a `SendMessage` and a `SendInput`
  right-drag moved the camera 0 px on a clean control (2026-08-25), so the blocker is the headless
  capture environment (no true foreground window), not the message transport. That leg is optional; the
  geometry effect is already observed. D-002 stays open.
- Zoom level 4's reachability in-game was never established, so the `z4` slot is untested.
- The `+0x32c` scroll-gate flag ("dirty-rect queue overflow → force full repaint", set at
  `FUN_1000d725:105`, cleared in `FUN_1000dc17`) is read from the decompilation and not
  runtime-witnessed. It is not a knob here, but it is on the same path.

## An alternative that needs no patch at all

`re/harness/src/sc3probe.c` `-pref` adds a real **"Camera Scroll Speed" slider** to the game's own
Preferences window and applies the value live (dragged 21.25 → 128.0 monotonically; shots
`pref1_202726.png`, `pref3_005306.png`). That is a nicer end-user shape than a patched DLL, and it
works. It arrives by injection through the RE harness, which is a dev tool rather than a shippable
product.

⚠️ **"No distributable vehicle" was overstated (corrected 2026-08-27).** D-001 closed only the
**proxy-DLL** route (a `version.dll`/`winmm.dll` shim, whose `DllMain` is skipped under the game's
AppCompat shim). It did **not** close injection-based delivery: `re/harness/src/sc3launch.c` already
injects a DLL via `CreateProcess(SUSPENDED)` + `CreateRemoteThread(LoadLibraryA)`, and the `-pref`
slider ran live through exactly that path under the same shim. So a shippable form does exist — a
**standalone loader EXE plus a slim mod DLL** carrying only the `pref_*` block, which was already
written to run standalone (`sc3probe.c:9088-9098`). Scoped, not built, in
[`re/analysis/SLIDER_DELIVERY.md`](../SLIDER_DELIVERY.md); it is the owner's value call, since the
byte patch already delivers the scroll knob. Recorded so the option is not rediscovered from scratch.
