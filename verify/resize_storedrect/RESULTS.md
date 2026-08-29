# RESULTS — the window stored-RECT write, 2026-08-29

**VERDICT: PARTIAL, exactly as pre-registered.** The geometry fix **WORKS** — the resized view now
reaches the physical monitor and fills the window, which was the whole of `D-004`. Contents in the
newly exposed area are wrong, which the pre-registration classified in advance as
*"geometry reaches the primary, contents wrong. New question, separate item."*

Pre-registration: `PRE.md`, committed **before** the build as `a85a7f2`.
Prior failure this fixes: `verify/resize_handtest/RESULTS.md`. Mechanism: `RESIZABLE_WINDOW.md` §8/§8b.

**`RESIZABLE_WINDOW.md` §8 is CONFIRMED, not falsified.** The pre-registered falsification case (write
lands, screen unchanged) did **not** occur. The stored RECT really is what `FUN_100185f5` publishes and
what `FUN_10018c58` Blts.

---

## The change did what it claimed

Six writes, **zero refusals** — the expect-or-refuse vftable identity check
(`*(DWORD *)win == gz_base + 0x1f740`) passed every time. Window object stable at `0x00B4A7E0`.

| t (ms) | BEFORE | AFTER |
|---|---|---|
| 57639 | `{0,0,800,600}` | `{0,0,2048,1081}` |
| 75046 | `{0,0,2048,1081}` | `{0,0,800,600}` |
| 75721 | `{0,0,800,600}` | `{0,0,1920,1009}` |
| 106586 | `{0,0,1920,1009}` | `{0,0,800,600}` |
| 107615 | `{0,0,800,600}` | `{0,0,1920,1009}` |
| 153432 | `{0,0,1920,1009}` | `{0,0,800,600}` |

Every `BEFORE` equals the previous `AFTER`, so **the write persists and the engine never reverts it**.
Five complete resize cycles (`---- done (all 9 steps) ----`), **zero `FAULT CAUGHT`**, at 2048x1081 and
1920x1009. Install unchanged before and after: `GZGraphicD acefadf0`, `SIMSPR f5b9f1d9`.

## Owner observation, real display

| # | pre-registered row | result |
|---|---|---|
| 1 | the city fills the whole window | **PASS** — "city fills the window" |
| 2 | the enlarged view is a real image | **FAIL** — see defect A |
| 3 | shrinking works | **PASS mechanically** (3 downward cycles complete); same content defect |
| 4 | no crash | **PASS** — 5 cycles, zero faults |
| 5 | HUD reflow | **not a blocker**, unchanged — "UI doesn't [fill]" |

## Defect A — resize does not repaint the newly exposed area

**Observed:** immediately after a resize the new area is **black**, with only **moving traffic sprites**
drawing. **Moving the camera makes terrain and zones appear** in that area.

So the redraw path works; it is not being triggered for the new region. The log shows step 7
`FUN_10018cdf -> 1` and step 9 pushing the full present rect `{0,0,w,h}` on every cycle, and the dirty
grid is reallocated at the new size (step 3, e.g. `40x30 cell=20x20` -> `12x8 cell=160x126`). Yet no
repaint occurs until camera motion marks cells dirty.

`[UNCERTAIN]` — **not diagnosed**. Mechanically: something must mark the new cells dirty after the grid
realloc, and either nothing does or the marking is cleared. Do not write a fix against this paragraph;
it is a description of the symptom, not a located cause.

## Defect B — buildings and roads NEVER render (independent of resize)

**Observed:** buildings and roads are missing **at launch, before any resize**, and stay missing
throughout. Only terrain and zones draw.

**This is NOT caused by the stored-RECT change, and the log proves it.** The subclass installs at
**4295 ms**; the first `STOREDRECT` write is at **57639 ms**, when the owner first maximized. Everything
seen before that happened with the stored RECT untouched at `{0,0,800,600}`. The timestamps exclude this
change as a cause.

`[UNCERTAIN]` — **cause unknown and untested.** The only other load-time changes this mod makes are
`patch_windowed` and `patch_surfacefmt` (`FIX16`, the 16bpp 5-6-5 cave at `+0x19349`). Whether either is
responsible, or whether the defect predates the mod entirely, **has not been tested**.

⚠️ **The obvious control has not been run:** launch the game **without** the mod and see whether
buildings and roads render. Until that is done, defect B's origin is open, and it is a **confound for
every rendering judgement in this file** — including defect A, which is being observed on an install
where a whole class of drawables is already missing.

## Third observation — input and display now disagree

Before this change: the view drew at 800x600 in the top-left, and the **cursor worked across the whole
window**. After it: the view fills the window, and **navigation only works within the top-left
800x600 region**. The two are inverted, which indicates input picking reads a different size source
than the blit path does. Not investigated. Not pre-registered. Recorded because it is new information
and a future reader will otherwise rediscover it.

## Status

- **`D-004` — the real-monitor flip: CONFIRMED.** The resized view reaches the physical primary and
  fills the window. This was the one headless-unverifiable step and it is now witnessed.
- **The mod is NOT shippable.** Defects A and B both produce a visibly broken city view.
- Fix A (4 grid-B clamps): holds again, 5 more hand-driven cycles, zero faults.
- The `wmsize_setrect` on-disk patch remains unnecessary — the DLL now genuinely does this in C, which
  is what §3 wrongly claimed before today.

## What was NOT done

No on-disk patch (both hashes unchanged). No control run without the mod. Defects A and B are recorded,
not diagnosed and not fixed.
