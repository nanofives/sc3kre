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

## Defect B — buildings and roads drop after RESIZE (CORRECTED — it is not a launch defect)

⚠️ **CORRECTION, owner clarification after the first write of this file.** The owner first reported
buildings/roads missing "when you launch the game". A more specific follow-up witness statement
supersedes it: **"upon launching i can see the game fine, everything breaks when i resize"**, and
**"buildings and roads are ALWAYS missing"** after that. The two are reconciled as: **at launch
everything renders correctly; the RESIZE routine drops buildings and roads, and they never come back**
(terrain and zones do come back on camera motion — see defect A — but buildings and roads do not, at
any camera position).

**This makes defect B a consequence of the resize, not a launch-time or load-patch defect.** The
earlier "control run without the mod" is no longer the priority — the witness has established that the
same mod, before any resize, renders the city fully. So `patch_windowed` and `FIX16` are **exonerated**
by the owner's own observation: buildings render fine under them until a resize happens.

### Diagnosis — CONFIRMED against the decompilation (2026-08-29)

Worker-drafted, then **every claim below re-read locally in `re/ghidra_export_simspr/functions/`.** All
RVAs are `SIMSPR.DLL`.

**Two independent draw systems on the iso view:**
- **System A — sprite/object drawables** (buildings, roads): a hash-map at `iso+0x3a4`, stamped into a
  fine screen-tile grid at `iso+0x380`, drawn by `FUN_1000af7c` reading `iso+0x380` bucket chains by
  tag byte (tag 2 = region sprites, tag 1 = `iso+0x3a4` objects). **Scrolling never rebuilds
  `iso+0x380`.**
- **System B — terrain/zone tiles**: per-cell flags in the map grid at `iso+0x24`, repainted by the
  scroll routine `FUN_100071a3` on every camera move. **This is why terrain/zones return on camera
  motion and buildings/roads never do** — System B self-heals on scroll, System A does not.

**Step 8 calls the wrong (inner) function.** `FUN_1000fa36`'s **only** caller is `FUN_1000c9bd`
`[CONFIRMED @ 0x1000c9bd, verified: it is the sole xref]`, which before calling it:
1. `FUN_1000edd9(this)` `[0x1000edd9]` — **clears the entire fine grid `iso+0x380`** (verified: frees
   every bucket node to freelist `DAT_10072670`, zeroes every head).
2. a region-scan loop that adds exposed-region sprites as **tag-2** nodes via `FUN_1000cedb`
   `[0x1000cedb]` (verified in the `FUN_1000c9bd` body).
3. **then** `FUN_1000fa36(this, param_3, 0)` to add the `iso+0x3a4` set as tag-1.

The mod runs only line 3, with `purge=0`, so it **skips the grid clear and the tag-2 region pickup**.

**And the draw key is never recomputed.** `FUN_1000c9bd`'s caller `FUN_10006a55` (the view-change
handler) runs, in order `[CONFIRMED @ 0x10006a55 lines 60-69]`:
`FUN_1000b70e -> FUN_1000e248 -> FUN_1000c8f9 -> FUN_100071a3 -> FUN_1000b352 -> FUN_1000c9bd`.
`FUN_1000c8f9` `[0x1000c8f9]` walks `iso+0x3a4` and rewrites every object's draw key `wrapper+0x24`
via `FUN_1000c962` (verified: `*(int *)(iVar1 + 0x24) = FUN_1000c962(...)`). `FUN_1000fa36` recomputes
the object *rect* (`FUN_1000e4ce`) but **not** the key, and `FUN_1000af7c` reads `wrapper+0x24` for
tag-1 nodes.

**So both symptoms have one root:** the mod hand-rolls the System-A re-register with the leaf function
instead of the real routine. Defect B (buildings/roads gone forever) = the `iso+0x380` object grid is
never properly rebuilt and scrolling never touches it. Defect A (new area black until scroll) = the
resize does not run the System-B field repaint `FUN_100071a3` for the newly exposed region, and only
camera motion triggers it.

**The candidate missing step(s):** the engine's real object re-register is **`FUN_1000c9bd`
(`SIMSPR 0x1000c9bd`)**, not `FUN_1000fa36`; and the full view-change is **`FUN_10006a55`
(`SIMSPR 0x10006a55`)**, which also does the System-B repaint. See the "Fix options" note below /
`RESIZABLE_WINDOW.md` §9.

`[UNCERTAIN]`, not resolvable read-only: (a) the cross-DLL callers that place specific building/road
objects into `iso+0x3a4` live in SIMCITY/SIMNTWRK and were not traced, so "buildings/roads = the
`iso+0x3a4` set" is inference from the two-system split + the symptom, not a proven placement call;
(b) whether `FUN_1000c9bd`'s region pickup fires depends on the exposed-rect list `iso+0x4c4` and the
zoom guard `2 < *(iso+0x28)` being consistent at step-8 time — a runtime question.

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
