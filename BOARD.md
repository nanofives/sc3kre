# BOARD.md — the orchestrator's view

**What this is:** the open surface organised by **mod / feature**, which is how work is actually
parcelled out to sessions. `ROADMAP.md` is the phase-and-gate record and is largely historical now;
this file is the live board. Opened 2026-08-24.

**What this is not:** a history. Decisions and rationale live in `ROADMAP.md`, deferrals in
`DEFERRED.md`, open questions in `UNCERTAINTIES.md`, per-session state in `re/sessions/STATUS_*.md`.
This file points at them and does not restate them.

## ⭐ The live fleet — four child sessions, spawned 2026-08-25

Owner's call: pursue all four in parallel child sessions, steered from here. Each owns its STATUS file
exclusively and makes integration commits **by path**.

Relaunched on the **`claude2`** account 2026-08-25 at the owner's request; the first `claude3` fleet was
stopped after ~30 min. All four STATUS files survived the switch, which is the whole point of the
one-session-one-STATUS-file rule.

| prio | workstream | session id | owns | first task |
|---:|---|---|---|---|
| ~~1~~ | ✅ **Camera movement speed — CLOSED 2026-08-25** | `cmt96p4rv…` (archived) | `STATUS_camera.md` | `drag_divisor` **and** `edge_margin` both taken from "derived, never run" to **C3 observed**; combined build staged live |
| ~~2~~ | ✅ **New road types — CLOSED 2026-08-25** | `cmt96pjiy…` (archived) | `STATUS_roadtypes.md` | **T2 met**: predicted `11203`, measured `11203 ×11`. Network save layer decoded and documented |
| 3 | **Bigger cities** | `cmt96q1v4…` | `STATUS_bigcities.md` | in-game authoring at 512 |
| ~~4~~ | ✅ **Resizable window — CLOSED 2026-08-25** | `cmt96qpp9…` (archived) | `STATUS_resize.md` | `U-068` taken from "the display list is empty" to **"renders but does not blit"**, both adjacent causes positively excluded |

> ⚠️ **Stopping a fleet mid-flight leaves orphans — measured, not predicted.** The `claude3` stop left
> the game lease **HELD** by `bigcities` with a **triple-patched install** (`SIMDIRT` + `SIMUI` +
> `SIMSPR`), and the harness claim **ACTIVE** for `camera`. Neither releases itself. Cleanup that was
> needed: `patch_citysize.py --restore` and `patch_dirtbuf.py --restore` (both re-verified by
> `--check`), `harness_claim.ps1 -Release -Owner camera`, and `game_lock.ps1 -Release -Owner bigcities
> -DirtyOk`. **Any interrupted run's measurements are void** — `bigcities` was mid-`capture author512`
> and banked nothing. Run this checklist before respawning a fleet.
>
> ⚠️⚠️ **CORRECTION, same day: the sentence above about interrupted runs being void is WRONG, and the
> error is instructive.** I declared both interrupted runs worthless without reading their transcripts
> or checking their evidence on disk. **Two of the four had banked complete, correctly pre-registered
> results before the stop**, and both had cleaned up after themselves. `bigcities` **passed** the 512
> authoring test; `resize` ran the redesigned instrument for a full 55 s and returned a disciplined
> VOID plus two structural findings. **Both replacements were briefed to disregard or redo that
> work**, and had to be corrected after the fact.
>
> **The rule that actually holds: a stopped session's STATUS file and artefacts are evidence until
> checked, not debris.** Read the transcript and re-verify on disk *before* briefing a replacement.
> Only an *unfinished* run is void, and neither of these was unfinished.

**The priority column is the game-lease order**, because runs are serial and four sessions can queue on
one install. Each was told to do its desk work first and take the lease only with a run pre-registered.

`re/harness/` is gitignored, so **`harness_claim.ps1` is the only collision protection** between these
four on `sc3probe.c` and `build.ps1`. A locked `bin/sc3probe.dll` means it is injected in a live
process — wait, do not kill it.

## How to run a workstream from here

One session per workstream. That session owns its `re/sessions/STATUS_<name>.md` exclusively, writes
its own findings there, and makes **integration commits by path** — never sweep another session's
dirty files into your commit. Shared files (`re/harness/src/sc3probe.c`, `build.ps1`,
`COORDINATION.md`) are merged by hunk, not by file.

Two hazards that have already bitten:

- **`functions.csv` is keyed on `(module, rva)`, never on `rva` alone.** 9.9% of rows share an RVA
  with another module. Filter on module before any read or bulk write, and verify the blast radius
  after a write. Detail in `CLAUDE.md`.
- **The harness `Grep` tool cannot see `re/ghidra_export*/`.** It reports that as "0 matches". Pass a
  module's `functions/` directory explicitly or walk the filesystem. Any exhaustive-negative claim
  made with `Grep` at or above `re/` is a false negative. See `U-056`.
- **⚠️⚠️ A CONFIRMED CODE PATH IS NOT A CONFIRMED CAUSE. My error, 2026-08-25, and it cost two leases.**
  Asked for the unpause path, I read `FUN_10002fa6`, confirmed `0x231e2493 → vt+0x44(0)` clears a pause
  bit at coordinator `+0x38`, declared the gate **solved**, committed it (`df797e3`), wrote it into
  `BIGGER_CITIES.md` and told a second workstream to plan on it. **Every one of those reads was
  correct.** The message does reach that slot; the slot does clear that bit.
  **But `+0x38` was already 0 at load** — measured in Lease 2 — so it was never what held a
  path-loaded city paused. The real pause is clock suspend-depth `+0x140`, and the resume is a
  different message entirely (`0xc2a35d80` → `vt+0x210`).

  **The missing question was not "does this code do what I think?" but "is this the thing that is
  actually happening?"** Verifying a mechanism says nothing about whether that mechanism is load-bearing
  for the observed state. **Before declaring a gate solved, measure the field you believe is holding it
  — a state read is cheap and a wrong mechanism is not.**

- **⚠️ The export itself can be incomplete, which is a SECOND and different false-negative source.**
  Found 2026-08-24: Ghidra rendered **zero** `+0xf0` call sites in SIMNTWRK because it discarded the
  containing block as unreachable, yet the call is right there in the bytes at `0x1001491c`. So a
  clean decompiled-text sweep is **not** evidence of absence. **An exhaustive-negative claim about
  call sites needs an instruction-level scan** (`FF /2` with the slot displacement) over `.text`,
  then receiver resolution — not the decompilation. `NETWORK_RULE_ENGINE.md` §12.0.

---

## Shippable now

RE done, tool exists outside a test harness, validated in the running game.

| feature | tool | procedure | residual |
|---|---|---|---|
| **Tunables** (any `SYS.PAK` INI value) | `syspak_mod.py` | `formats/SYSPAK.md` | `U-051` credits discriminator, 1 run, cosmetic closure only |
| **Sprites / asset art** (recolour and author from PNG) | `sprite_patch.py` | `formats/SPRITE_MODDING.md` | `-filetrace` is blind to `Apps\Res\Sprites\`, so sprite runs have no file-access gate |
| **City saves** (zone raster, per tile) | `city_write.py` | `formats/CITY_SAVE.md` | tile (28,0) never visually confirmed; the **name-collision load crash** needs writing up for users |
| **Camera scroll + drag** | `pe_patch.py` | `formats/CAMERA_MODDING.md` | `drag_divisor` (velX 50→25→50), `drag_deadzone` (engage 0→8→0) **and** `scroll_speed` **staged live** (three-recipe `scroll8 + drag4 + deadzone2`, retuned gentler 2026-08-26, `--diff` 8/9, diagonal confirmed by owner feel); `edge_margin` **C3 observed** (band 48/64→24/32→48/64), not staged. OS-input "feel" leg (**D-002**) now known ENVIRONMENT-blocked: `SendMessage` AND `SendInput` both moved 0px in the headless harness. Zoom-4 reachability (**D-003**) |
| **Network tiling rules** (retune / re-skin an existing network) | `tilingrules.py` + `network_layer.py` | `formats/TILINGRULES_MODDING.md` | ⭐⭐ **T1 AND T2 both met game-side 2026-08-25.** T1 destructive (roads vanish), **T2 constructive: a 2-line SimpleRules edit re-skins a freshly-drawn straight to the curve piece — predicted `11203`, measured `11203 ×11`.** ⚠️ The lever is **SimpleRules (fixpoint, first), NOT `final.txt`** (last) — the `final` edit gave a **byte-identical** save. Render-path result, **no simulation claim** |
| **Bigger cities** (N > 256, proven at 512) | `patch_citysize.py` + `patch_dirtbuf.py` | `formats/BIGGER_CITIES.md` | ⭐ **engine reads/renders/re-serialises tiles to 495, in-game authoring works (x=460), AND the sim UNPAUSES + runs at 512** (2026-08-25): post GZ `0xc2a35d80` (probe `msg:`), game-verified `+0x140` 1→0 + clock ticks. ⚠️ `0x231e2493` measured **inert** (wrong pause field) — the two-mechanism trap. Still open: **development** needs *connected service* (road+power) authored at chosen coords, gated on a network writer or an anchored screen→world map. `U-081` closed |

> **Correction on record:** `HANDOFF.md` still claims sprite modding has "no RGB565 quantizer and no
> PNG import". That is **stale** — `sprite_patch.py` has `quantize565()`, `export_png()` and
> `replace_from_png()`, `--pngtest` is 62,552/62,552, and it was validated game-side 2026-08-19.
> Trust `ROADMAP.md`'s T2 table over `HANDOFF.md` on this.

## Active workstreams

### 1. Bigger cities (N=512) — not blocked, closest to done
Sim accepts 512; the renderer crash is fixed by the SIMDIRT SIZE group alone (config C 6/6 survive,
shipped 0/6). Four bytes are the whole fix. Tool: `patch_dirtbuf.py`.
✅ **Documented and substantially de-risked 2026-08-25.** `formats/BIGGER_CITIES.md`. Four 32x32
zone blocks planted at the map corners were **read, rendered and re-serialised by the engine**;
extremes `x 16..495, y 16..495`, 216 of 308 changes above 256, zero changes outside the blocks, and
**no coordinate threshold** — the far corner survived best (1006/1024) and the low-coordinate control
worst of the pair (932/1024). Verified independently before promotion.

~~**`U-081` — a no-key null control**~~ ✅ **ANSWERED 2026-08-25, and it was never a 512 question.**
The three-arm control gave drift `0,0` and a key delta of `-32,0` — **exactly one 32-px step** where
the `-6848` baseline is precisely `214 x 32`. **`gzseq`'s `key:` does not sustain a hold; it taps
once.** A working camera looked like a 512 clamp bug for five runs. Debt item 1.

### ⭐⭐ IN-GAME AUTHORING AT 512 PASSES — 2026-08-25, game-side, independently re-verified
A screen drag at (250,160)→(380,250) on a bare-path-loaded 512 city placed **151 Res-Low tiles at
world x 441..460, y 18..25 — all 151 above 256, with no clamp to 255 and no wrap.** That was the
actual 512-specific risk (screen→world picking carrying a stale 256 assumption) and it is now
falsified. The **game itself wrote the save**, and that game-written file passes `city_roundtrip.py`
L0–L4 byte-identical.

The baseline `N512_city.sc3` is **all-zero across 262,144 tiles**, so every non-zero tile is
necessarily the tool's work — that is what makes the result clean. Re-parsed independently rather
than taken on the run's word: `{0: 261993, 1: 151}`. Artefact:
`verify/citysize_mod_test/N512_authortest.sc3` (game-derived, **never commit**).

The run was **pre-registered** with PASS / FAIL-picking / FAIL-noregister / FAIL-save spelled out
before firing, which is why it survives its session being killed mid-flight.

`[UNCERTAIN]` The second drag (Com-Low, lower on screen) placed nothing. The run read this as that
region projecting off-map near the corner — **post-hoc and unverified**. The pre-registration already
allowed "one rectangle placing = partial PASS", so the result does not depend on it. Do not cite the
off-map story as fact.

### ⭐⭐ THE SIM UNPAUSES AND RUNS AT 512 — game-verified 2026-08-25, three leases
`msg:0xc2a35d80,0,0,0` (Post to the message server, expect-or-refuse) → `FUN_10002fa6` →
`vt+0x210` = `FUN_10005773`, which decrements suspend-depth `+0x140` and calls clock Resume
`[CONFIRMED @ 0x10002fa6, PE 0x13260]`.

| read | suspendDepth `+0x140` | clock cursor `+0x4c` |
|---|---|---|
| #1 baseline, paused | **1** | 2415021 |
| #2 after post (+8 s) | **0** | 2415021 |
| #3 (+8 s) | 0 | **2415022** |
| #4 (+15 s) | 0 | **2415024** |

**The cursor had been frozen at 2415021 through the whole of Lease 2 and this run's own baseline**, so
the fixture supplies its own control — same field, same city, never moved under the wrong message. The
extra long final gap was added to catch a running-then-stall and instead confirmed **sustained**
ticking rather than one delivered tick. Date `+0x40/+0x44` stayed `0/0`; a blank city's date serial
rolls only after many cursor ticks, so **the cursor is the witness**, not the date.

⚠️ **`0x231e2493` is inert and must stay documented as a dead end.** It clears `+0x38`, which was
**already 0 at load** — measured under both Post *and* Send. It looks exactly like an unpause in the
decompilation, so the next reader of `FUN_10002fa6` will find it and draw the same wrong conclusion
this board did. Quartet: `7e` suspend cmd / `7f` suspended notify / `80` resume cmd / `81` resumed
notify.

**This unblocks every workstream that needs a running sim**, not just this one.

**Next, in order:** (2) **Development — still the critical path, and now gated on ONE thing:**
authoring *connected service* (road **and** power) at chosen coordinates. Both are hard preconditions
— a residential tile's develop check early-returns on demand (`0xd`), radioactivity (`0xa`), power
(`0xe`), transport (`0x10`), land-value band (`0xb`/`0xc`) and an eligible family (`0xf`/`0x12`)
`[CONFIRMED @ SIMRCI 0x10028f12, iOS goResZoneDeveloper::UpdateCell 0x0026e7c8]`. `city_write.py`
writes **zones only**, so this needs either a **network-layer writer** (`roadtypes` has a validated
reader) or an **anchored screen→world map** so drags can target coordinates. (3) A bound above 512.
Stride/corner measurement is deferred as cosmetic (~8 runs).

### 2. Resizable window / arbitrary resolution — ⭐ CONSOLIDATED HANDOFF: `re/analysis/RESIZABLE_WINDOW.md`
> **Read `RESIZABLE_WINDOW.md` first** — single authoritative summary (2026-08-29). Headline: the mod
> works headless in both resize directions at 2048x1152, the crash is fixed engine-wide (4 grid-B
> clamps), ships as `sc3resize.dll`+`resize_launch.exe` patching nothing on disk. **`D-004` was
> hand-tested on a real display 2026-08-29 and FAILED** — see the block below. The detailed history
> below is retained as the working record.
>
> ✅ **SHIPPED 2026-08-31 — VIEWPORT, HUD native.** The resizable-window mod is done for the in-city
> view: resize fills the monitor, city renders (no toggle), zoom in/out stable, no crash. The HUD is
> left NATIVE by design — it can dock+span full-width (`verify/resize_hud`, SIMUI SetRect vt+0xc8) but
> full-width has an INTRINSIC per-frame composite cost (three FPS hypotheses falsified) and per-widget
> reflow hit engine class/offset mismatches; the shipped build does not install the HUD wrap. Full HUD
> evidence for a future engine-level pass: `verify/resize_hud/RESULTS.md`.
>
> ✅✅✅ **RENDER FIXED END-TO-END, 2026-08-30 (step 11).** Owner-confirmed: after a resize, with NO
> manual layer toggle, **the whole city renders** — terrain, zones, buildings, roads. Root cause: the
> resize's step 7 called `FUN_10018cdf(bridge, layer=0, .., force=0)` which **nulled the active layer
> `bridge+0x28`**, so nothing downstream could draw. Step 11 replays SetDataView(0)'s core
> (`FUN_10018cdf(bridge, *(bridge+0x2c), *(bridge+0x80), .., force=1)`), restoring the active layer +
> forcing the refresh. Defects A and B CLOSED. `verify/resize_setdataview/`. Five earlier hypotheses
> (8a/8b, 8c, repaint, device batch, rotation) failed because none restored the active layer.
>
> ⛔ **REMAINING, blocks shipping: zooming in after a resize CRASHES** (owner: "it closed itself when i
> zoomed in"). Uninstrumented — our SEH wraps only the resize routine and SC3U swallows the fault (no
> WER). Likely the §4 grid-B OOB class on the zoom path (`FUN_10006752`) at the resized window size.
> **Next: add a process-wide VEH crash logger to localize it** (build the fault-catcher first).
> `verify/resize_zoomcrash/`.
>
> ✅✅ **`D-004` IS CONFIRMED, 2026-08-29 — the resized view reaches the physical monitor and fills the
> window.** The fix is the **window stored-RECT write** (`verify/resize_storedrect/`, pre-registered
> `a85a7f2`): on `WM_SIZE` the DLL reads the window object from `GZGraphicD+0x6cdb8` and sets
> `win+0x40 = win+0x38 + w`, `win+0x44 = win+0x3c + h` behind an expect-or-refuse vftable check.
> **Six writes, zero refusals, five resize cycles, zero faults**, hand-witnessed at 2048x1081 and
> 1920x1009. `RESIZABLE_WINDOW.md` §8 is **confirmed, not falsified** — the pre-registered
> falsification case did not occur.
>
> ⛔⛔ **BUT THE MOD IS NOT SHIPPABLE — two rendering defects, now ROOT-CAUSED (verified in decomp),
> not yet fixed. `RESIZABLE_WINDOW.md` §9.** One root cause: **step 8 calls the leaf `FUN_1000fa36`
> instead of the real object re-register `FUN_1000c9bd`.**
> - Two draw systems: **A = sprites/objects** (buildings, roads) via hash-map `iso+0x3a4` -> fine grid
>   `iso+0x380`, and **B = terrain/zone tiles** via `iso+0x24`, repainted by scroll `FUN_100071a3`.
>   B self-heals on camera move; A does not.
> - `FUN_1000fa36`'s sole caller `FUN_1000c9bd` first clears the grid (`FUN_1000edd9`) and does a tag-2
>   region pickup (`FUN_1000cedb`), THEN calls it; the grandparent `FUN_10006a55` also recomputes draw
>   keys (`FUN_1000c8f9`) and repaints System B (`FUN_100071a3`). The mod runs only the final leaf.
> - **Defect B** = `iso+0x380` object grid never rebuilt + scroll never touches it. **Defect A** =
>   `FUN_100071a3` not run for the new region. `patch_windowed`/`FIX16` exonerated by the witness.
> - ⛔ **DRAWABLE RE-REGISTRATION IS FALSIFIED (2026-08-30) — two builds, both ran clean, neither fixed
>   B.** 8a/8b (sprite grid `iso+0x380` via `FUN_1000c9bd`, `verify/resize_objreregister/`) and 8c (tile
>   grid `iso+0x24` via per-cell `FUN_10006c67`+`FUN_10006efc` over all **65536 cells, 0 bad, 0 faults**,
>   `verify/resize_gridreshow/`, pre-reg `24d67ec`) both drove the exact engine primitives and produced
>   **no visual change**. The drawable `+0x34` show was invoked for every building/road and they still
>   did not draw; a manual data-layer toggle is still required.
> - **The defect is DOWNSTREAM of per-cell registration** — in the render/composite pipeline the show
>   feeds. The data-view toggle switches render MODE (3D -> flat overlay) and back via a **cross-DLL**
>   (SIMUI/SIMCITY) path that is NOT `FUN_100071a3`, and that mode round-trip resets whatever the resize
>   leaves stale. `[UNCERTAIN]` — the specific stale state is unidentified. **Do NOT build another
>   drawable-re-register variant; that class is exhausted.**
> - **PROGRESS 2026-08-30: the defect is the PRESENT, localized.** Cross-DLL read found the toggle's
>   repair = iso whole-view repaint (`FUN_1000db86` = iso vt+0x144, PE-verified) bracketed by a **device
>   present batch** (`device+0x240`/`+0x244`, `device = *(bridge+0x14)`) at `FUN_1001818c:53-55`.
>   - Step 10 = repaint ALONE: hand-tested FAIL (ran clean, screen unchanged). `verify/resize_pipeline/`.
>   - Owner: **rotating does NOTHING** (refutes the transition/repaint path); **only a data/utility
>     overlay toggle and back fixes it** — the one path that runs the device batch. So the **device
>     present batch is the operative part.**
>   - Next build `verify/resize_present/` (pre-reg committed): wrap step 10's repaint in the device
>     batch, verbatim `FUN_1001818c:53-55`, live-vtable + SEH guarded. `[UNCERTAIN]` until hand-tested.
> - Falsified: 8a/8b (sprite re-register), 8c (tile re-register, 65536/65536 cells), step-10-alone
>   (repaint), and rotation. The fix is narrowed to the device present batch.
> - **`D-004` (the session goal) is CONFIRMED and complete** — the resizable window fills the monitor.
>   A + B are polish with a working manual workaround (toggle a data view and back).
> - Also: view fills the window but **navigation works only in the top-left 800x600** (input picking
>   reads a different size source than the blit). Not investigated.
>
> ---
> **History — the first hand-test, which FAILED.** Record: `verify/resize_handtest/RESULTS.md`
> (+ the witness log committed beside it).
>
> Owner maximized by hand on a real 2048x1152 display: **the city stayed drawn in the top-left at the
> pre-resize size and did not fill the window** — the pre-registered FAIL signature for row 1. Cursor and
> input DID follow the full window. Row 4 (no crash) **PASSES**: three resize cycles including
> maximize/restore, **zero `FAULT CAUGHT`**.
>
> **What the run banked (do not re-litigate these):** Fix A's 4 grid-B clamps hold on a real display
> under hand-driven churn — first non-headless witness; the readiness gate fires on a real Europolis
> load; the WndProc subclass publishes the **true** client size (`WM_SIZE 2048x1081`); the clamps rebase
> correctly onto a relocated `SIMSPR` (`0x03310000`).
>
> **Where the defect sits — IDENTIFIED same day, see `RESIZABLE_WINDOW.md` §8.** All `GZGraphicD`:
> `FUN_10017e2f` (WM_MOVE/WM_SIZE -> `vt+0x30`, called with **no size args**) -> `FUN_100185f5` (builds
> the dest rect from the window object's **stored** size via `vt+0x68`/`vt+0x6c` + `ClientToScreen`,
> publishes it to the display singleton `FUN_1001a7ad()+0x24 -> +0x28`) -> `FUN_10018c58`
> (`IDirectDrawSurface::Blt`, `vtable+0x14`, with `DDERR_SURFACELOST` recover-and-retry at
> `vtable+0x60`). The mod resizes the **SIMSPR** surfaces and never touches the **GZGraphicD window
> object**, so an 800x600 rect keeps getting published and Blt-ed into the window's top-left.
> All four functions were re-read locally and verify. ⚠️ `FUN_10018c58` is the **same RVA the mod hooks
> as its per-frame heartbeat** (`GZGraphicD+0x18c58`) — the mod has been polling from inside the very
> function that presents the wrong rectangle.
>
> ⛔⛔ **AND A FALSE CLAIM IN OUR OWN DOCS, corrected today.** `RESIZABLE_WINDOW.md` §3 said the DLL's
> WndProc subclass "makes a real `WM_SIZE` publish the true client size", which is why `wmsize_setrect`
> was called optional. **It does not.** `re/harness/src/sc3resize.c:721-731` calls the original proc,
> `logf`s `lParam`, returns — it writes nothing, it is an OBSERVER. The same false claim sits in the
> mod's own header comment (`sc3resize.c:44`) and function comment (`:719`). **`wmsize_setrect` is NOT
> optional.** The log line `RZ WM_SIZE 2048x1081` is an echo of the message parameter, and I initially
> misread it here as evidence the stored-size defect was fixed.
>
> **Fix target:** update the window object's stored width/height on `WM_SIZE`, or intercept `vt+0x30` /
> `FUN_100185f5` so the published rect matches the resized surfaces. Recreating SIMSPR surfaces alone
> can never help — the primary Blt does not read them for geometry.
>
> ✅ **VFTABLE READ SAME DAY — inference replaced by bytes (`RESIZABLE_WINDOW.md` §8b).** Done by
> parsing `Apps/GZGraphicD.dll` directly; the vftable is static `.rdata`, **no Ghidra project lock was
> needed**. ⛔ The worker's `0x100212bc` was **WRONG** — an auto-named `globals.csv` row (line 89) with
> **zero xrefs**. The real window-object vftable is **`0x1001f740`**, installed as `[this+0]` at RVA
> `0x17bf7` / `0x17c6e` (with `0x1001f730` as a second base class at `[this+4]`).
>
> | slot | target | body |
> |---|---|---|
> | `vt+0x30` | `0x100185f5` | **byte-proven**, no longer ABI inference |
> | `vt+0x68` | `0x10017c1e` | `mov eax,[ecx+0x40]; sub eax,[ecx+0x38]; ret` = right-left = **WIDTH** |
> | `vt+0x6c` | `0x10017c25` | `mov eax,[ecx+0x44]; sub eax,[ecx+0x3c]; ret` = bottom-top = **HEIGHT** |
>
> **Stored size is a RECT at `win+0x38`(l) `+0x3c`(t) `+0x40`(r) `+0x44`(b); HWND at `win+0x34`.**
> Confirms the earlier `sc3resize.c:42` measurement. **The window object is reachable from a fixed
> global, `GZGraphicD+0x6cdb8`** — the WndProc thunk at RVA `0x17e11` does `mov ecx,[0x1006cdb8]`
> before calling `FUN_10017e2f`, and the constructor stores it there (`A3 B8 CD 06 10`). So the fix is
> reachable from the DLL with the module-handle+offset pattern it already uses.
>
> **Fix spec (NOT built, NOT tested):** in the WM_SIZE subclass, `win = *(void**)(gz_base + 0x6cdb8)`,
> then `win+0x40 = win+0x38 + newW`, `win+0x44 = win+0x3c + newH` (relative to existing left/top —
> `FUN_100185f5` maps through `ClientToScreen`). Needs a committed `PRE.md`, an expect-or-refuse vftable
> check (`*(DWORD*)win == gz_base + 0x1f740`) before the write, and a fresh owner hand-test.
>
> `[UNCERTAIN]`, still not proven: the link "the rect `FUN_10018c58` receives is the one `FUN_100185f5`
> published" is **DirectDraw-ABI inference** (called virtually, no textual caller in the export), and
> `FUN_100185f5`'s guard `(*piVar3 + 0x34)() == 0` was labelled "windowed" by the worker without
> evidence. **A CONFIRMED CODE PATH IS NOT A CONFIRMED CAUSE** — see the standing warning above. The
> iOS oracle cannot help: that build is OpenGL-ES, no DirectDraw analog.
>
> ⚠️⚠️ **METHOD FINDING, and it is the nondiagnostic-proxy class again — third instance, first time the
> proxy PASSED while the real thing FAILED.** `verify/resize_census` censused `iso+0x74` / `iso+0x4ec`
> at ~100% fill and that was written up as "on-screen fill at 2048x1152". **It was not on-screen fill.**
> Both surfaces were equally full on the run that failed on the monitor. Measuring the last surface the
> harness can reach is not measuring the flip, and the distance between the two is exactly `D-004`.
>
> ⛔ **Trap for the next reader:** `verify/resize_handtest/PRE.md` (2026-08-26, pre-bridge) pre-registers
> this exact visual as meaning "the render target is NOT resized". **The log proves it WAS resized.**
> Score future runs against `HANDTEST.md`, not `PRE.md`.

### 2a. (history) black-vs-garbage RESOLVED 2026-08-25 (U-068 = "renders but does not blit"; see the run-4 subsection below)
`U-068`: display lists stay empty after a resize Init. Root cause established 2026-08-23 by two
independent angles — Init sizes and zeroes grid B, only object registration fills it, and Init's only
route early-outs on a zero-equality guard. **The fix is to re-drive registration, not to repair the
builder.** Two fix candidates written with a pre-registered falsifier.
**Next: dump the render target, not the display list.** ⭐ Measured in pixels 2026-08-24
(`LAUNCH_CONTROL.md` §31.12): control shot renders Europolis in full, post-resize shot is **black**,
post-fix shot is **still black** — while grid B went 0 → 208 type-1 nodes and the builder logged
**+208 calls, +208 non-zero, +208 appends**. Everything this project has instrumented for two days
works. **The defect is downstream of the display list, in the rasterisation or blit of the iso render
target.** Next instrument: a lock-and-dump of `iso+0x74`'s surface against `iso+0x4ec`, the blit
destination — one read run. It answers the open question, **black vs garbage**, which are different
defects.

> ⭐ **Separate defect found in the same shots: the in-city UI does not reflow.** Window 1280x1024,
> UI still laid out for 1024x768, ~256 px black margins right and below, a stray magenta widget at
> ~(1126, 875). This **contradicts the menu path**, where exact re-centring was measured
> (`192,144,832,624` → `320,272,960,752`). Only the menu behaviour was ever verified.

> ⚠️ **Any instrument on grid B must split nodes by the type byte at `node[2]`.** It holds two
> classes — `FUN_1000ef50` tags type 1 (drawable), `FUN_1000cedb` tags type 2 — and **both builders
> gate on type 1**. The tile refill restores 1537 *type-2* nodes into all 64 cells, so an
> undifferentiated count reads a fully-populated-but-invisible grid as healthy. That mistake cost a
> run on 2026-08-24.
### ⭐ INSTRUMENT FIXED, verdict VOID by design — 2026-08-25, one lease
The redesigned surface dump **ran the full 55 s and was killed on schedule**, where the previous
version took the process at t+19.6 s. Expect-or-refuse fired, `__try/__except` was never needed, and
the `GetSurfaceDesc` COM path is gone. The root cause of the old crash: it called `GetSurfaceDesc`
through `*(iso+0x74 + 4)` to *decide* whether the object was a surface — dispatching through the
pointer it was trying to identify. Identity is now decided by **comparing** the vtable against a known
`MODULE+RVA`, never by dispatching through it.

**Black-vs-garbage is VOID, and that was the correct call.** The pre-registration said *control dump
reads no known-good frame → instrument suspect, ABORT*. The control gave no image, so the post-resize
reading was not interpreted. Held to, after the result was in.

Two structural findings, which is what the lease actually bought:

1. ⚠️ **`iso+0x4ec` was REFUSED both times** — vtable `GZGraphicD+0x1F328`, not `GZGraphicD+0x1E894`.

   ⭐ **But the follow-up refutes the refusal's interpretation, and the correction matters.** The first
   reading was *"the blit dest is a foreign class and needs its own read interface."* **False.**
   `+0x1F328` is a **subclass** of `+0x1E894`: ctor `FUN_10015c88` calls the raster base ctor
   `FUN_10009db4` then installs its own vtable `[CONFIRMED @ 0x10015c88]`. Byte-read from the
   untouched `original\modules\GZGraphicD.dll`, **only 9 of 109 slots differ**
   (`0x0,0x4,0x8,0x10,0x14,0x18,0x34,0x38,0x3c` — lifecycle plus the w/h getters). **The whole read
   interface is identical function pointers**: lock `FUN_10014649`, unlock `FUN_1001467e`, bits
   `FUN_1001575d` (`+0x1a8`), pitch `FUN_10015767` (`+0x1ac`), and the `+0x0c == FUN_10009efb` second
   witness. Reproduced independently with `re/tools/gz_vtdump.py`.

   **So `iso+0x4ec` was never unreadable — the gate hard-coded one accepted vtable.** The identical
   bracket reads both; the fix is to accept either. The fail-loud gate still did its job (it refused
   rather than crashed), but the conclusion drawn from the refusal was wrong and is corrected here.
2. **`iso+0x74` has no lockable bits even in the healthy control** — `vf1a8` returns `0x28`, pitch
   `0`, while Europolis renders in full. Raw dims *do* track the resize (1024x768 → 1280x1024) and
   `created` is set.

   ⭐ **Now mechanically explained.** `vf1a8` = `*(*(this+0x44)+0xf0)` and `vf1ac` =
   `*(*(this+0x44)+0xf4)`, with `vf1c` delegating the lock to `sub->vt[+0xc]`
   `[CONFIRMED @ 0x1001575d / 0x10015767 / 0x10014649]`. Because `vf1a8` dereferences `this+0x44`
   **before** `+0xf0`, a null sub-object would fault — it did not. **So the sub-object exists.**

   ⛔ **REFUTED IN-GAME 2026-08-25, and the refuted half is mine.** I wrote here that "the pixels are
   backed only inside the engine's own lock bracket". **False.** A raw read of the same object
   microseconds apart gives `bits(sub+0xf0) = 0x1110C028`, `pitch = 2560` — a real pointer and the
   **exact** 1280 × 16bpp / 8 stride — while the `vf1a8`/`vf1ac` *calls* return `0x28` / `0`.
   **The bits were always present; the out-of-band `vf1c(0x40)` lock was tearing the backing down.**
   The instrument was destroying the thing it measured.

   **Rule that falls out: read `sub+0xf0` / `sub+0xf4` RAW. Never call `vf1c` out of band.**

### ⭐⭐ BLACK-VS-GARBAGE IS SETTLED — and it is NEITHER. The iso target is never blitted.
**2026-08-25, run 3, fix OFF, Europolis, stock SIMSPR, resized 1024→1280 at t+22.**

| | result |
|---|---|
| **control, pre-resize** | the iso view's `sub(+0x44)` **matched a blit source by pointer** within 8 blits, and censused **786,233 / 786,432 px non-zero (99%), not uniform** — a full Europolis image |
| **post-resize** | **1,500 blits, ZERO matched** the render target or its sub. 19 distinct sources, none of them the render target |

**The pre-registered third outcome fired: the iso view is not blitting its render target.** The screen
is black not because the target is black and not because it is garbage — it is created at the new
size, it holds a live backing surface, and pre-resize its sub is a proven source of a full image —
but **post-resize it never reaches the composite**. The defect is a **missing or misdirected iso
blit**, downstream of both rasterisation and the display list, each already shown working.

**Pointer identity is what made this decidable.** Post-resize every surface is 1280x1024, so a
dims-based filter could not have separated "not blitting" from "not recognised", and a null would
have been uninterpretable. Match on the object pointer, keep dims as a secondary witness.

**Stage 1 validated live:** `dest_iso+0x4ec` verified as the `+0x1F328` subclass through the identical
bracket, no crash and no refusal — the byte-verified interface identity holds in a running game.

### ⭐⭐⭐ U-068 CLOSED: "renders but does not blit" — 2026-08-25, run 4 (probe `963b8105…`)
Run 4 added a per-blit **live re-snapshot** (closing the mid-window-recreate escape) and a **raw
`sub+0xf0` census** (content, read RAW per the rule above). Two results, one of them nearly a
self-inflicted false conclusion:

- **Rasterisation is PROVEN GOOD at the new size.** The post-resize render target holds
  **1,310,342 / 1,310,720 px non-zero (99%, not uniform)** at 1280x1024, read raw from `sub+0xf0`. The
  control raw census equals the blit-source census to the pixel (786,233 both), so the method is sound.
  **A U-068 fix must NOT look at rasterisation.**
- **The conclusion needs no match counter.** Black screen (§31.12) + a 99% image in the render target
  are two independent measurements that **force "renders but does not blit"**. This over-determines the
  result, which is why no confirming re-run was spent.
- ⚠️ **A counter bug produced a FALSE `HEADLINE REFUTED` line, caught by an internal cross-check.**
  `g_u068src_livematch` was not reset per window, so it accumulated the control window's matches into
  the post-resize verdict. The census (gated on the correctly-reset `dumped`) **never fired in the
  post-resize window**, which proves **zero** post-resize matches — the `36` was carry-over. **Fixed**
  (probe `963b8105…`); any pre-fix `U068SRC` verdict line is unreliable.

**Verdict: `U-068` is no longer "the display list is empty". It is a named, localised defect — the iso
view renders a full frame into its render target and never blits it to the frame buffer.** Fix target:
the **missing render-target blit**, downstream of rasterisation (proven good) and the display list
(proven good). Both adjacent possibilities are positively excluded. Full record + handoff:
`STATUS_resize.md`.

⚠️ **Two caveats on record, both from the run itself.** The post-resize sub pointer was snapshotted at
window open, so a mid-window recreate could dodge a stale snapshot (mitigated but not closed: the
pre-resize snapshot matched within 8 blits, and the more stable render-target *object* never matched
either). And **post-resize render-target content is still uncensused** — Stage 2 cannot census what
never blits. Moot for the screen, but it decides whether rasterisation *also* fails or only the blit
does, which changes what a fix must repair.

**Cost named by the run:** two launches produced nothing because the control and Stage 2 both ride the
`0x10018c58` fnlog stub installed by `-gzlog <existing gz_draw.txt table>`, and a nonexistent file was
passed. No crash; those launches did bank the raw-bits refutation above.

**Superseded plan** (kept for the reasoning): **Stage 1** — relax the gate to accept
either vtable, dump both objects, log the raw sub-object. Cheap, safe, settles the dest side and
witnesses both sub-objects. **Stage 2** — sample **inside** the paint bracket, between a `vf1c` and
its `vf20` on `iso+0x74`. That is the only thing that settles black-vs-garbage; cheapest candidate is
piggybacking the existing `FUN_10018c58` blit hook (already game-thread, mid-paint,
re-entrancy-guarded), fallback a filtered hook on the hot `FUN_10014649`.

⚠️ **Dumping `sub(+0x44)` directly is VOID by construction at heartbeat** — same empty `0x28`/pitch-0
state. Keep it as logged data, never as the discriminator.

### ⭐⭐ SHIPPABLE MOD `sc3resize` BUILT + a HARD SIZE CEILING FOUND (2026-08-28). Full: `verify/resize_ship/`
The validated resize routine is carved into a slim injected DLL (`re/harness/src/sc3resize.c` +
`resize_launch.exe`, Branch B of `RESIZE_DELIVERY_COST.md`). Offline gates all PASSED. Three game runs:

- **v1**: wiring validated end to end (inject, both hooks, subclass, poll, trigger, 7 of 8 steps) but
  the frame was clipped to 800x600 — my error, step 9 relied on `resize_rectfix` which is Init-gated and
  the routine is Init-free. **Fixed:** the DLL now pushes the present rect itself.
- ⛔ **v1/v2 were CONFOUNDED — I never controlled the display mode** (owner caught it). The 6 validating
  runs used `-windowed -fix16`; the DLL replicated neither and launched fullscreen. **Fixed in v3:**
  `patch_windowed` + `patch_surfacefmt` carved into the mod, verified applied (`window 800x600 titled`).
- **v3**: display mode fixed, real game-driven resize triggered — then **crashed at 2048x1081**.
- ⭐⭐ **ROOT CAUSE (static, no lease): a HARD ENGINE CEILING.** The grid-B builders `FUN_1000be25`
  (zoom<3) and `FUN_1000d0f5` (zoom>=3) carry **fixed `int[16384]` stack arrays, filled one entry per
  visible tile with NO bound check** `[CONFIRMED @ 0x1000be25:26-27, 0x1000d0f5:29-30]`. Visible-tile
  count scales with view area: **under 16384 at 1280x1024 (proven, 6 runs), over it at 2048x1081** →
  /GS stack-cookie corruption = `0xC000041D`. **Not a mod bug — a cap on how large the iso view can be.**
  My "un-resized DirectDraw primary" guess was **refuted**: the leaf blits between `iso+0x4ec` and
  `iso+0x74`, both resized `[CONFIRMED @ 0x1000e058, 0x1000e206]`.

**Fix is a CLAMP, not a routine change:** cap the client size the mod acts on to a validated max
(1280x1024 safe), ignore/letterbox larger, and stop the window auto-maximizing.

⛔⛔ **THE 16384-OVERFLOW ROOT CAUSE IS NOT CONFIRMED — measurement contradicted it (2026-08-28).**
A headroom census (`-spritecount`, `verify/resize_headroom/`) on dense Europolis read the builders'
fill structures at 800x600 and 1280x1024, **both at zoom 3**: grid nodes **1114 → 1692**, sector
records **flat 144**. Linear fit puts **2048x1081 at ~2320 grid nodes — 7x UNDER the 16384 cap**, and
even 2560x1440 stays ~4.9x under. **So the v3 crash was NOT a grid-array overflow at zoom 3**, and my
earlier "root cause = fixed int[16384] overflow" (`609e97a`) — reported from the worker's static array
read plus an area-scaling story, without measuring the fill — is **contradicted at the tested zoom**.

Two possibilities remain open: (1) the v3 crash was at **min zoom**; (2) `0xC000041D` is a plain
repaint AV, not an overflow. **Established:** at zoom 3, headroom is large and a clamp is not the binding
constraint up to ≥2560x1440.

### ⭐⭐⭐ CRASH HUNT (2026-08-28): NO CRASH at 2048x1152 MIN ZOOM. Both crash theories REFUTED.
A crash-hunt build (`SC3RESIZE_MINZOOM=1` forces zoom 0; `__try/__except` + per-step breadcrumb +
MODULE+RVA fault resolver) drove an external resize to **2048x1152 at t+42s on a settled city**. **Zero
faults, zero crash, all 9 steps completed at 2048x1152 AND 2048x1081 at min zoom, twice; game exited
clean.** `FUN_10018cdf` returned 1 in ~62 ms. Full: `verify/resize_crashhunt/RESULTS.md`.

- ⛔ **16384-overflow root cause FULLY REFUTED** — min zoom (hypothesized worst case) at a size *larger*
  than the v3 crash ran clean.
- ⛔ **My "crash in FUN_10018cdf / step 7" localization REFUTED** — step 7 completes here.
- **The real correlate is TIMING.** v3 fired the resize at **t+11.6 s (~5 s after bridge capture, city
  still loading)**; this ran at **t+42 s settled**. Size, zoom, routine all excluded. Evidence points to
  a **resize-during-load race** `[UNCERTAIN, not proven]`. **Actionable fix: gate the poll until the
  city is initialized** — the mod should do this regardless.

⚠️ **Scorecard, recorded against myself:** I asserted a crash root cause twice from static/structural
evidence without the load-bearing measurement, and was wrong both times (the primary-blit story, then
the overflow story). The **SEH fault-catcher is the instrument I should have built first** — it turns
the crash into a logged address instead of a guess. The board's own recurring lesson, re-learned.

**So there is NO evidence of a size ceiling at 2048x1152.** The clamp may be unnecessary; the real open
item is the load-timing gate, not a size cap.

### ⭐⭐⭐ THE v3 CRASH IS NOT REPRODUCIBLE — 5 controlled conditions, all clean (2026-08-28)
SEH-catcher build, `verify/resize_crashhunt/`. Three runs (plus a settle) exclude the crash across
**sizes 2048x1152 & 2048x1081, zoom 0 & zoom 3, timing t+5s (during load) & t+42s (settled)** — all 9
steps complete, `FUN_10018cdf` returns 1, the fault-catcher never fires. **Timing is refuted** (run 2
resized during load, clean); **zoom is refuted** (run 3 at zoom 3, clean — correcting my own confound
where runs 1-2 forced zoom 0). The v3 crash (`0xC000041D`, one occurrence) is most consistent with a
transient tied to the exact auto-maximize-during-load sequence, or a fault outside `rz_do_resize`
`[UNCERTAIN, not asserted]`.

**Net: the "hard ceiling / crashes at 2048" narrative reduces to a single non-reproducing incident.**
The routine is demonstrated **robust at 2048x1152 across zoom and timing** on a dense city. Genuinely
open, and smaller than it looked: ~~(a) a **load-readiness gate**~~ ✅ **DONE (2026-08-28,
`verify/resize_gate/`):** the poll now defers a resize until >=3000 ms since bridge capture AND the
render target has a backing (one frame drawn), then fires on a later poll. Witnessed: early resize
deferred at t+6.1s, landed at t+8.4s once ready, all 9 steps, no fault. Tunable `SC3RESIZE_READYMS`.
~~Still open: (b) on-screen correctness at large sizes~~ ✅ **SETTLED (2026-08-28,
`verify/resize_census/`):** an in-mod RAW census at 2048x1152 (load zoom, dense Europolis) reads BOTH
the render target `iso+0x74` (**100%** non-zero, full bbox) AND the blit-dest `iso+0x4ec` (**99.7%**,
full bbox) holding a **full 2048x1152 image**, ~1.88M non-zero px **beyond** the old 800x600. **The frame
fills the window — not clipped.** This retires the earlier "clipped 800x600" `PrintWindow` shot as a
D-004 capture artifact, not the engine frame. The blit-dest feeds the DirectDraw present, so the
composite is full-size; the only hop a headless census cannot see is the final **primary flip to a
physical monitor (D-004)** — an owner hand-test on a real display closes it. ✅ **`U-069` (downward) ANSWERED 2026-08-29 (`verify/resize_u069_v2/`): downward resize WORKS.** Two
downward resizes (2048x1081->800x600 and 1280x1024->800x600) completed all 9 steps, zero faults,
render-target census shows the frame correctly at the smaller extent (bbox fills 800x600,
`beyond-800x600=0` — no stale large content). With FIX A in place there is no shrink-specific fault.
Combined with the upward census, the routine handles resize in **both directions** on a settled city.

### ⚠️ THE CRASH IS REAL AND NOW LOCATED — intermittent dangling grid-B node AV (2026-08-28)
Attempting `U-069` (downward resize), the auto-maximize to 2048x1081 fired first and step 7 faulted —
**the SEH catcher trapped it: `0xC0000005` AV at `SIMSPR+0xD005 = FUN_1000cedb+0x12a`** (the grid-B
type-2 tagger, reached from the `FUN_10018cdf` repaint). Disassembly: `+0x12a` is
`cmp dword ptr [eax],edx` with `test eax,eax` two instructions earlier — so **`eax` is non-null but
INVALID: a grid-B bucket holds a dangling node pointer**, dereferenced during the repaint while the
resize is tearing down/refilling the grid. **A lifetime/ordering hazard, NOT overflow and NOT a size
ceiling** — which reconciles "real crash" with "not reproducible under 5 conditions" (it is
**state-dependent**, intermittent). The int[16384] story is doubly dead (an AV, not /GS; census already
refuted the count). ⚠️ **The load-readiness gate does NOT fix this** (the fault is post-gate).
`U-069` remains **OPEN** — the down-resize deferred after the caught fault and never ran. Full:
`verify/resize_down/RESULTS.md`.

### ⭐⭐⭐ ROOT CAUSE FOUND (2026-08-28) — OOB grid-B bucket index, a latent engine off-by-one
Enhanced the SEH filter to dump fault-time registers + grid state, churned 8 resizes, caught it:
`FUN_1000cedb+0x12a`, `edi = base+284 = bucket index 71` on a **64-bucket (8x8)** grid — **7 past the
array**; `eax=0x80020003` is the garbage dword read from `bucket[71]`, unreadable → AV. **Grid scan: 0
dangling nodes** → NOT a freed node (that hypothesis refuted); it is an **out-of-bounds INDEX.**
`FUN_1000cedb` computes far-edge col/row = `round((far-1-origin)·8/extent)` = `round(2047·8/2048)=8`
and `round(1080·8/1081)=8` (valid 0..7); `(8<<3)+7=71`, matching `edi` exactly. The `-1` guard is
defeated by round-half-up.

⚠️ **LATENT AT NATIVE TOO:** `round(799·8/800)=8` at 800x600 — the engine computes the same OOB index-8
at native res; it just doesn't crash there because the memory past the array is benign. **The crash is
heap-layout-dependent** (faults only when `bucket[64..71]` is unreadable), which is why it is
intermittent and why 5 controlled runs were clean while the churn caught it. Real crash + not-repro now
reconcile. Full: `verify/resize_rootcause/RESULTS.md`.

**Fix (design):** ⛔ enlarging grid B does NOT work (round-up scales: `round((W-1)·16/W)=16`).
(A) clamp the index in a `FUN_1000cedb` cave, or (B, DLL-friendly) over-allocate the bucket buffer.

### ✅ FIX A BUILT + PASSES (2026-08-28, `verify/resize_fix_a/`)
A 59-byte SIMSPR-internal cave recomputes the bucket index as `(min(row,gh-1)<<stride)+min(col,gw-1)`,
so it cannot exceed `gw·gh-1 = 63` (disassembly-verified — the OOB read is impossible by construction).
Applied **in memory** by the mod at load (`patch_gridb_clamp`, rel32s base-invariant, fail-closed byte
check — **still patches nothing on disk**). Witness (the churn that caught the fault unfixed): clamp
installed, **zero faults including 2048x1081 twice** (the exact faulting size), all triggered resizes
completed 9 steps, plus an incidental clean **downward 2048x1081→800x600** (partial `U-069`).
### ✅✅ FIX A COMPLETE (2026-08-28) — all 4 grid-B walkers clamped, witnessed, zero faults
`FUN_1000cedb` + `FUN_1000d0f5` + `FUN_1000be25` + `FUN_1000ef50` all clamp the bucket index to
`gw*gh-1` (proven by construction). Table-driven `g_clamps[]`, fail-closed per entry, all
position-independent, applied in memory — **mod still patches nothing on disk.** Churn witness: all four
log `index clamped`, **zero `FAULT CAUGHT`**, 8/8 resizes complete. `ef50` avoids its absolute
`cmp [0x10072670]` (would not survive relocation) by clamping the incoming params on the stack at entry.
Full: `verify/resize_fix_a/RESULTS.md`. **The OOB grid-B bucket-index AV is fixed engine-wide.**
Two self-inflicted bugs along the way, both caught by fail-closed (a verify-check comparing the wrong
bytes) or by construction — never mispatched a hot function.

**Workstream summary:** resize routine renders a full-window frame at 2048x1152 (raster + composite
censused); shippable as `sc3resize.dll` + `resize_launch.exe` (offline-gated). **Real open defect: an
intermittent dangling-grid-B-node AV in the post-resize repaint (`FUN_1000cedb+0x12a`), now located.**
Also open: `U-069` (downward, preempted) and the D-004 final flip to a physical monitor (hand-test).

⚠️ **Crash-arc scorecard, against myself:** three asserted causes (DirectDraw primary, int[16384]
overflow, load-timing), three refutations, plus one self-inflicted confound (min-zoom on during the
"timing" test). The **SEH fault-catcher, built last, is what settled it** — build the catcher first.

### ⭐ THE `WM_SIZE` CAVE IS DROPPED — one cave, not two (2026-08-27, static, no lease)
The plan of record wanted a GZGraphicD `WM_SIZE` cave setting a pending flag plus a SIMSPR per-frame
cave reading it: **two** position-independent caves, two relocation-safe hooks, and a cross-module flag
needing GZGraphicD's runtime base. **None of it is needed.**

`O2` — the `this` of the WM_SIZE rect setter `FUN_10016b90` — **is `B + 0x6C`**, a secondary-base
subobject of the very object SIMSPR already holds at `iso+0x4ec`. Ctor `FUN_10015c88` writes
`B+0x00`=`0x1001f328`, `B+0x6C`=`0x1001f290` `[CONFIRMED @ 0x10015c88]`; `FUN_10016a93` is literally
`return this - 0x6c` `[CONFIRMED @ 0x10016a93]`. So the rect lands at **`B+0x70/0x74/0x78/0x7C`**, and
B's own getters read exactly it — `vt+0x38` = `*(B+0x78)-*(B+0x70)`, `vt+0x3c` = `*(B+0x7c)-*(B+0x74)`
`[CONFIRMED @ 0x10015d42, 0x10015d49]`. **The iso view ctor already walks this chain verbatim**
(`FUN_1004feba` → `vt+0x24` → `vt+0x3c` → stores it at `iso+0x4ec`) `[CONFIRMED @ 0x1001c4a1]`.

So a **SIMSPR-only per-frame poll** self-triggers on member offsets alone: `live_w/h` from
`B+0x70..0x7c` against the render target's `R+0x24/+0x28` (set by Init `FUN_10009efb`). No absolute
address, no base derivation, no flag. **SIMSPR imports nothing from GZGraphicD** (6 descriptors, none a
game DLL) — the GZCOM lookup with the identical `0xC416025C`/`0x73283C` pair is the only route
`[CONFIRMED @ 0x1004ffec, 0x100157ed]`. The rect updates synchronously in the WndProc
`[CONFIRMED @ 0x10017e2f]`, so a next-frame poll is sound rather than racy.

⚠️ **`B+0x1C..+0x28` is a DIFFERENT rect** — the device surface size / clip rect
`[CONFIRMED @ 0x1000e058]`, changing only on a surface re-Init. Second witness, not the same field.

⚠️ **Static reachability, not a runtime result.** Per this board's own rule, the poll needs a live
**observe-only** witness (log `live_w/h`, `rt_w/h`, `B+0x24/+0x28` across a real resize) **before** any
resize work is wired behind it. That same run settles the one `[UNCERTAIN]`: whether GZGraphicD
re-Inits its own device surface on resize, or our cave must. One lease, both answers. Full derivation:
`STATUS_resize.md`.

### ⛔ CORRECTION SAME DAY (2026-08-27): the section above is HALF WRONG, and it is my error
**The reachability is right; the VALUE does not move.** `B+0x70..0x7C` does **not** update on a stock
resize, so the per-frame poll would compare stale against stale and never fire. **The `WM_SIZE` cave is
NOT dropped** — but the cross-module flag still is, and the cave's job changes.

`FUN_100185f5` reads neither `lParam` nor `GetClientRect`: it takes the **window object's STORED** size
via `vt+0x68` = `FUN_10017c1e` = `*(win+0x40) - *(win+0x38)`, ClientToScreens it, and pushes that
`[CONFIRMED @ 0x100185f5, 0x10017c1e]`. **Nothing updates `win+0x38..0x44` on a stock resize**, so the
handler faithfully republishes the OLD size. Window vtable located in `.rdata` at **GZGraphicD+0x1F740**
(`+0x1c` SetRect `FUN_10018691`, the only writer of `win+0x38..0x44`; `+0x30` `FUN_100185f5`; `+0x68`/
`+0x6c` the stored w/h getters).

⚠️ **This was already written down in our own harness and I had not read it.** `rz_apply` calls
`FUN_10018691 SetRect(0,0,w,h)` and *then* re-runs `FUN_100185f5`, commented *"the WINDOW object still
holds the old rect"* (`sc3probe.c:6362-6387`). **Same failure mode as `0x231e2493`: I confirmed a path
reached a field and never asked whether the field moves.**

**Corrected design, better than both previous plans.** The cave stops being *"set a pending flag"* and
becomes *"make the stored rect true"* — then the corrected rect **is** the signal and nothing crosses
the module boundary. At `FUN_10017e2f` line 126 the WM_SIZE branch has `this` = the window object and
`param_4` = `lParam` `[CONFIRMED @ 0x10017e2f]`; the cave calls `this->vt[0x1c](this,0,0,LOWORD,HIWORD)`
before letting `vt+0x30` run. No user32 call needed (GZGraphicD imports `GetWindowRect` and
`AdjustWindowRect` but **not** `GetClientRect`). Then the SIMSPR poll works exactly as derived.

⚠️ **TRAP: WM_MOVE(3) shares that branch** — gate on `param_2 == 5` only, or a move overwrites the
stored size with screen coordinates.

**The witness run gets sharper, not cancelled:** it now has a falsifiable prediction —
`B+0x78-B+0x70` will **not** change across a real resize. If it does, this correction is wrong.

### ⭐⭐ WITNESS RUN PASSES — the correction is MEASURED, not just derived (2026-08-27, one lease)
`PRE.md` git `49ea7bd`, committed before the lease. Full record: `verify/resize_wmsize_poll/RESULTS.md`.

| point | `B+0x70..0x7C` -> live | dev `B+0x1C..0x28` | `R` | stored `win+0x38` | OS `GetClientRect` |
|---|---|---|---|---|---|
| PRE | **800x600** | 800x600 | 800x600 | 800x600 | 2560x1351 |
| **MID** (real WM_SIZE done) | **800x600** | 800x600 | 800x600 | 800x600 | **1280x1024** |
| **POST** (after repair) **[CONTROL]** | **1280x1024** | 1280x1024 | 1280x1024 | 1280x1024 | 1280x1024 |

The OS client moved and **every engine-side field stayed at 800x600**. The control — same instrument,
same field, same object `0x0054C540` — reads 1280x1024 after the repair, so **the VOID outcome is
positively excluded** rather than assumed away. Both modules were RELOCATED during the run.

⭐ **Secondary `[UNCERTAIN]` CLOSED in the same run: GZGraphicD does NOT re-Init its own device
surface** (`B+0x1C..0x28` stayed 800x600 at MID). **A resize fix must drive the device surface itself.**

⚠️ **Unregistered but important: the render target is a NEW OBJECT after a resize** (`0x12329750` ->
`0x12A7EFC0`). **Re-read `R` from `iso+0x74` on every sample — never cache it**, or the poll reads a
freed object.

`[UNCERTAIN]` At PRE the OS client was **2560x1351** while every engine field said 800x600 — the engine
was already out of sync before any resize, so `-fitclient` did not produce the size the engine believed
in. Does not affect this result (the test is whether the field *moves*). **Do not cite the PRE row as
evidence that engine and OS agree at startup.**

### ⭐⭐⭐ `wmsize_setrect` CAVE BUILT AND PASSES — WM_SIZE now publishes the REAL size (2026-08-27)
Recipe `c49dbb0`, `PRE.md` `c233790`, result `bbcf082`. Full record: `verify/resize_wmsize_cave/`.
39-byte **position-independent** GZGraphicD cave at `0x1001d860` + a 7-byte hook at the WndProc
WM_MOVE/WM_SIZE landing site `0x10017f17`. Gate **44 bytes / 4 runs** alone, **109 / 16** combined with
the two existing GZGraphicD recipes (exactly additive).

**A/B at MID, arm A measured before the cave existed:**

| field | arm A (no cave) | **arm B (cave)** | predicted |
|---|---|---|---|
| `win+0x38..0x44` stored | 800x600 | **1280x1024** | ✓ |
| `B+0x70..0x7C` -> live | 800x600 | **1280x1024** | ✓ |
| device surface `B+0x1C..0x28` | 800x600 | **800x600** | unchanged ✓ |
| render target `R` | 800x600 | **800x600** | unchanged ✓ |

**All four predictions landed, both no-change rows included** — which is what excludes something other
than the cave acting. No crash, city reached.

⭐ **It also closed arm A's open `[UNCERTAIN]` for free.** Arm A saw the engine already out of sync at
startup (OS 2560x1351 vs engine 800x600); arm B's PRE reads `stored = 2560x1351`, matching the OS.
**Same defect, not a separate one** — the engine was stale from the first `WM_SIZE`.

⚠️ **NOT shown, and it gates shipping: `WM_MOVE(3)` safety is UNEXERCISED.** `SWP_NOMOVE` generates no
`WM_MOVE`, so the `cmp ebx,5` gate is **disassembly-verified only**. Needs a real move before this
joins a standing build. ⚠️ **No rendering claim** — the render target and device surface are untouched
by design. `wmsize_setrect` is **not** in the owner's standing build; owner's `acefadf0` restored and
verified at close.

### ⭐⭐⭐ THE MINIMAL Init-FREE RESIZE ROUTINE IS COMPLETE AND PASSES — 2026-08-27, 6 runs
Full record `verify/resize_minimal/`. Prototyped in the harness (`-resizemin`), **not yet a cave**.

Against run 2 as the known-good control: **401 distinct RGB colours vs 463**, 168 grey levels vs 175,
mean 76.0 vs 75.9, std 14.1 vs 14.2 — with the content bbox now the **full 1280x1024**. Independent
mechanism witness: grid-B inserts **364** vs **222 frozen** in run 5.

**The sequence, in order. Init is NEVER called.**

| # | step | note |
|---|---|---|
| 1 | `iso+0x5c = iso+0x54 + w`, `iso+0x60 = iso+0x58 + h`, mirror `+0x64..0x70` | ⚠️ **world space, moving origin** (measured `-848, 2924`) — NOT `{0,0,W,H}` |
| 2 | `FUN_100059fb(w,h,&gw,&gh,0)` -> 40x64 | the game's own table |
| 3 | `FUN_1000e2c0(iso, gw, gh)` | |
| 4 | `FUN_1000ee29(iso, 8, 8, 0)` | **grid B is 8x8 at EVERY resolution.** Omitting it **HUNG** the game |
| 5 | `FUN_10009efb` replay on `iso+0x74` | guard `+0x08` cleared, original 8-arg tuple |
| 6 | `FUN_10009efb` replay on `iso+0x4ec` | **measured necessary** — the engine will not |
| 7 | `FUN_10018cdf(bridge, 0, b+0x78, b+0xa8, 0, 0)` | the render lever, 47 ms |
| 8 | `FUN_1000fa36(iso, 1, 0)` | omitting it = **terrain only, 32 colours** |
| 9 | present rect `iso+0x4d0` | **already ships as `resize_rectfix`** |

⛔ **Two of my own conclusions were corrected along the way, both recorded:** *"the extent and the
per-tile grid `iso+0x24` are coupled"* is **WRONG** (`iso+0x24` is **map**-sized, `param_1 << 2` where
`param_1` is Init's first arg — a view resize never needed it, and the Init-free premise survives);
and *"stale grid B is the leading suspect"* is **WRONG** (8x8 is correct at every resolution).

`[UNCERTAIN]` 401 vs 463 is a **~13% palette shortfall** — camera/time variance between launches, or a
small unregistered subset. Passes the declared bar; **not** a claim of pixel-equivalence.

⚠️ **Scope:** upward only, one city, one zoom, headless (no `D-004` claim), and it is a **prototype,
not a cave**. 8 calls + ~10 field writes is far bigger than `wmsize_setrect`'s 39 bytes — **cost the
hand-assembly before starting it.**

### ⭐ UI reflow root-caused, 2026-08-25, no lease — the shippable half
`[CONFIRMED @ 0x100270e5]` SIMUI `FUN_100270e5` holds three hardcoded HUD tables and **has no branch
above width 800**, so **every resolution ≥ 801 gets the 1024x768 top-strip table**. Consumer is
`FUN_10024a96` (single caller). Field layout decoded: idx 0 is a resource tag, odd fields are X
anchors that scale, even fields are fixed top-strip Y. An exhaustive **filesystem-walk** negative (not
`Grep`, which cannot see the export) confirms **no 1152 or 1280 table exists anywhere in SIMUI**.
Modding fix specified: add a `width >= 0x500` branch plus a registered layout resource.

The uninitialised-buffer theory for the stray magenta widget at ~(1126, 875) is **refuted** — the
consumer never reads past the written region. Two grounded leads recorded in its place.

**Behind it:** `U-069` — downward resize has never been exercised at all, so read every "resize
works" claim as "resize *upward* works". Only 1280x1024 has been tested; four unpinned device-vtable
slots.
**Owner:** the resizable-window session. Do not take its lease.

### 3. Road types / tiling rules — one rung from closed, queued behind #2
Verdict already reached: a 7th network is impossible without patching code (closed 6-member enum,
`*6` stride baked into the piece-matrix addressing, 42 predicate vtables flush with no room for a
43rd). Retuning and re-skinning an existing network is possible and partly game-proven. The format
round-trips 68/68 byte-identical.
### ⭐⭐ T1 IS MET — 2026-08-25, game-side, third attempt
**"An edited tiling rule changes the map" is now measured.** Replacing `ROAD_GRND_Set.txt` with a
7-byte `{99999}` made **every road tile vanish** — the corridor from the settlement, the segments
between farm plots, the roads inside the settlement (houses intact), and the vehicles on them —
while **the railway drew normally**. That is the discriminator: a different network with its own
untouched Set file. Not "the map stopped drawing"; one network's tiles disappeared, the one whose
piece list was replaced.

Controls that hold: status bar character-identical (`Farmsville`, `Pob: 36,172`, `§45,724`,
`5/16/1904`) — **and the reason is that path-loaded cities load PAUSED**, corrected 2026-08-25 from the
original "matched sim times" claim; a frozen sim makes the frames *more* comparable, so the conclusion
is unaffected. (**Note the fixture is N=192, not 256** — see `formats/BIGGER_CITIES.md`. Irrelevant to
T1, whose result is size-independent, but the record should be right.) camera identical to the pixel; terrain, trees, fields, farmhouses,
silos, pylons and their lines all unchanged; **111 `TilingRules` filetrace lines in each run**, the
loader-ran-identically control. Both frames are `### SHOT #5` at t+63.55 s and t+65.58 s, matched for
sim time as well as camera. Hash restored and re-verified to `9926948A…1358`.

**Also established:** a 7-byte Set file causes **no crash** — so the allowed-piece list is **not
validated** and degrades rendering silently. Verdict: §4 row 1, *"Rules are honoured. The surface is
real and moddable."* Full record: `verify/tilingrules_read_test/RESULTS.md`.

**Ladder complete:** T0 files are read → T1b contents are consumed → T1 contents change what is
drawn. All measured, none inferred.

**Limits on record:** one edit of one kind to one file; no claim about the *simulation* (this is a
render-path result); and no claim about `U-068` — these are pre-resize frames.

> ⭐ **The `U-068` dependency is dissolved — but one instrument question survives, and run 1 answers
> it.** Corrected 2026-08-24 after re-reading §7; the first version of this note overstated.
>
> **What is settled:** §7's premise, *"in-city rendering does not work"*, is **falsified**. Shot A
> (§31.12) is a rendered in-city frame — Europolis in full at 1024x768, `Pob: 2,069,432`. `U-068`
> breaks the iso view **only after a resize**, and T1 involves no resize.
>
> **What is NOT settled:** §7 also records an empirical re-check on 2026-08-22 where an in-city run
> through **`capture.ps1`** gave `Blt=0 Flip=0 Lock=0` and **zero SHOT lines**. Shot A came through
> the u068 probe's own `-shot` path under different switches, so it does **not** directly show
> `capture.ps1`'s blit-mirror reconstruction works in-city.
>
> **Therefore T1's run 1 (baseline, stock rules) is also the instrument control.** If it yields no
> frame, that is a finding about the capture path — reconcile it against shot A's switches — and
> **nothing may be concluded about tiling rules.** T1 heads the queue because run 1 is worth spending
> either way: it returns either the baseline the test needs, or the reason the instrument differs.
### ⭐ T3 (simulation-level tiling test) IS NOW UNBLOCKED — nobody has started it
The road-types session parked its last rung as *"gated on bigcities' message-post primitive"*. **That
primitive landed and is game-verified the same day** (`msg:0xc2a35d80` → suspend-depth `+0x140` 1→0,
clock cursor 2415021→2415022→2415024). **So the gate is open and the session closed before learning
it.**

That matters because **every tiling result so far carries a render-path fence** — T1 and T2 both prove
what is *drawn*, with no claim about the simulation. With a running sim, a tiling edit can finally be
tested for simulation effects (traffic, growth along a network). **The fence stays until such a test
actually runs** — an unpause capability is not a simulation result.

Session CLOSED, test ready to fire.

### 4. Camera scroll — SHIPPED 2026-08-24, workstream CLOSED 2026-08-25

⭐ **The reusable technique, which outlives this workstream: a transport-independent within-process
A/B/A.** Both `drag_divisor` and `edge_margin` were stuck at "derived from the decompilation, never run
game-side" because driving them needs *input*, and the harness cannot synthesise a real drag —
`SendMessage(WM_RBUTTON*)` moves the camera **0 px**, since the pan recognition in GZWinD/winmgr polls
`GetAsyncKeyState` and never classifies a posted message as a drag.

**The way past it is to stop trying to drive the input and call the computation directly**, hot-patching
the constant live between calls: measure at shipped, hot-patch, measure, restore, measure again.
`velX 50 → 25 → 50` and band `48/64 → 24/32 → 48/64`. The **return-to-baseline third leg is what makes
it a measurement** rather than a coincidence — a one-way `50 → 25` leaves drift and one-way state
changes unexcluded.

This sidesteps the input-transport problem **and** the cross-process `cam`-object ambiguity in one
move. Harness verbs `dragtest`/`setdiv` and `edgetest`/`setedge` are in `sc3probe.c` for the next
value knob that needs it.

**Only open leg:** the OS-input "feel" test, needing a `SendInput`-class instrument (`D-002`,
optional). `STATUS_camera.md` carries a self-contained record of why WM messages fail, so nobody pays
that run twice. `D-003` zoom-4 reachability is a **read-only rider**, not worth a lease.
See the shippable table. The proxy-DLL delivery vehicle is **dropped, not deferred** (`D-001`).
Reopening it means arguing against the recorded evidence.

## The game-run queue — this is the scarce resource

Runs are **serial**: one install, one lease, and SC3U is single-instance. A second launch exits
`0xFFFFFFFF` at ~840 ms with no dump, which is **indistinguishable from a broken patch**. Take the
lease with `re/harness/game_lock.ps1` (never pipe it, the exit code is the contract) and rebuilds with
`re/scripts/harness_claim.ps1`. **Never kill a process you did not start** — match by StartTime and
parent PID, not by image name.

Order:

1. **Road-type T1** — **attempted 2026-08-24, stopped at the instrument control.** Run 1 produced no
   frame, so no game content was edited and nothing was concluded about rules (hashes verified
   unchanged before and after). **The blocker is now identified and fixed** (debt item 1): a
   mirror-window re-arm loop, not `U-068` and not the latch. **Also established on the 2026-08-25
   attempt: the fixture works.** `-filetrace` showed `CreateFileA …\Cities\Farmsville.sc3 -> ok`
   and **111 of 328 filetrace lines naming `TilingRules`** — the right city loaded and the rules were
   read. Everything except the capture path is now known good. Retry is **2 runs**, keep
   `-filetrace`.
2. **`U-068`** — **DEMOTED, not abandoned.** Five runs spent; the last one crashed the game inside its
   own control (§31.13) and settled nothing. What was bought is real: the defect is localised below
   the display list and specific to the iso path. The next instrument needs a **safe** redesign first
   (verify a vtable pointer against a known `MODULE+RVA` before calling anything, `__try/__except`
   around the first call per object) — that is desk work, not lease work. ⚠️ `SC3PROBE_U068SURF` must
   not be re-enabled as written.
3. **Bigger-cities `run_diff.ps1`** — 1 run, then gameplay in a 512 city.
4. **Credits discriminator** (`U-051`) — 1 run. Cosmetic closure; `verify/credits_discriminator/`
   `RESULTS.md` is still an unfilled template.
5. **`drag_divisor` / `edge_margin`** (`D-002`) — 1 patched run each.
6. **Standalone slider ship-validation** (`camera`) — **RIDER, not a lease.** Validates the shippable
   wiring of the in-game Camera Scroll Speed slider (`slider_launch.exe` + `sc3slider.dll` + `slider.ini`,
   built + offline-gated 2026-08-27; `re/analysis/SLIDER_DELIVERY.md`). PRE committed:
   `verify/slider_ship_validate/PRE.md`. Needs **stock both modules** (restore shipped, re-stage owner's
   build after). **Leg A** (loader injects, slim DllMain + heartbeat install, boot `.rdata` apply) is
   read straight from `sc3slider.log` and only needs the run to reach the **menu** — a sibling holding a
   headless lease can carry it. **Leg B** (slider appears in Preferences, drags, `slider.ini` round-trips)
   needs Preferences **open on a real display** — owner hand-test, like the resize hand-test. The scroll
   arithmetic (C3) and the slider UI (harness `-pref`, witnessed) are already proven; this is wiring only.

> ⚠️⚠️ **PATTERN, not an incident: this board keeps listing questions the repo has already answered.**
> `U-063` went **open → parked → closed** in one afternoon, and *nothing was discovered* to close it —
> the answer had been sitting in `LAUNCH_CONTROL.md` §31.9.1 the whole time. It joins `U-076` (answered
> in catalogue §27c since 2026-08-18, filed off a stale label in a second doc), `U-079` (the costed
> 1–2 run differential was redundant), and `U-075`. **Four uncertainties closed by reading, not by
> working.**
>
> **So: before opening or costing any item here, grep the analysis notes for it.** A row on this board
> is not evidence that a question is open. The cheapest possible run is the one you do not spend.

## Static pool — no lease, runnable in parallel right now

| item | what | state |
|---|---|---|
| ~~`U-076`~~ | ✅ **CLOSED 2026-08-24 at C2.** The premise was wrong: `0xc14f8955` is `GZIID_cISC3Occupant`, an **interface** id, and the catalogue §27c had said so since 2026-08-18 — the uncertainty was filed off a stale label in a second doc. Real factory is `FUN_1000bdcd` in SIMNTWRK, 22 piece classes. `NETWORK_RULE_ENGINE.md` §11. Also closed `U-077`'s class half. | done |
| ~~`U-078`~~ | ⭐⭐ **CLOSED 2026-08-24 at C3, no game run.** `state` is a rigid quarter turn toward increasing `dir` index; **there is no global compass zero** — `state 0` is the identity and absolute facing is per-piece exemplar data, with two authoring zeros in the shipped data. Three independent witnesses, zero counterexamples in 95 + 1,660 + 249 observations. `NETWORK_RULE_ENGINE.md` §13. **The rule-geometry route won; the sprite-render route did not exist** (§13.7). ⚠️ Compass *words* still depend on the §4.1 world-axis convention, which was not re-derived — safe to build a rule editor on the rotation sense, not on the word "clockwise". | done |
| ~~`0x82237425` `+0xb0`~~ | ✅ **CLOSED 2026-08-24.** Run **blind** against §13 and it reached the same function, table and closed form independently — the strongest evidence in the subsystem. Class is GZCLSID `0xe223741f`, size `0x150`, in SIMNTWRK all along. Corrected §11.5 twice (no coordinate args; the "abstract vtable" was a base-address error). `NETWORK_RULE_ENGINE.md` §14. | done |
| **compass labelling** | The *only* surviving residue of `U-078`, and it is a **labelling** question, not a mechanism one: 4 of 8 conventions remain. Closes with one call site feeding the same integer into both `FUN_1000d73d`'s index space **and** a signed `dx`/`dy` or `x == 0` test. Two candidate witnesses found and both correctly **disqualified** (§14.5). | open, low priority |
| ~~`U-075`~~ | ✅ **SWEPT 2026-08-24.** `+0xb0` closed at C3 — the drive path is **GZ message `0x637c0dab`**, six posters plus one SIMRCI direct call; the UI is not a holder at all. `+0xac`/`+0xf0` have **no cross-module caller in any shipped binary** (C2, measured absence). `NETWORK_RULE_ENGINE.md` §12. | done |
| ~~`U-080`~~ | ✅ **LATENT, not live (C3).** All 42 predicate vtables share slot 0 `FUN_1001a9bb`, which accepts `0xA1C085DB`; 25/25 call sites pass exactly that. ⚠️ **But it turns live for mod authors** who install a slot-0 that rejects it — belongs in published toolkit docs. | done, one doc action |
| ~~`U-079`~~ | ✅ **CLOSED 2026-08-24 at C3, no run spent.** Full `*_Protected.txt` → netType binding in `re/analysis/NETWORK_TYPES.md` §9, three independent cascades agreeing. The 1–2 run differential that `UNCERTAINTIES.md` costed is now **redundant — do not spend it.** Two corrections fell out: the loader reads **22** rule files, not 11 (a second parser `FUN_10019600`), and the refuted order-based guess was the slots' **address order**, which is why it kept looking right. | done |
| `U-077` | Class behind occupant IID `0x41658d28`; label flag bits `0x400`/`0x4000`. Can sit indefinitely. |
| ~~`U-063`~~ | ✅ **CLOSED — and it was already closed before this board ever listed it as open.** The RECT zone writer's caller is **`SIMGEOM.DLL FUN_10007760+0x5BB` = `0x10007D1B`**, `FF 50 38  call dword ptr [eax+0x38]` reaching SIMRCI `FUN_10032afa`, runtime-confirmed, with **exactly two observed callers**. Written up in `LAUNCH_CONTROL.md` §31.9.1–.3, including `FUN_10007760` named as `cISC3BuildingLayer::commit_placement`. Verified at `LAUNCH_CONTROL.md:3564/3577/3787` before closing this row. | done |

## ⚠️ THE INSTALL IS DELIBERATELY MODIFIED — `SIMSPR.DLL`, slower camera (THREE mods now)

**Staged 2026-08-25, retuned gentler 2026-08-26, at the owner's request. THREE mods.**
`Apps\SIMSPR.DLL` carries `scroll_speed=8` (arrow-key + edge scroll at a QUARTER of shipped `32.0`),
`drag_divisor=4` (right-drag pan at half sensitivity) **and** `drag_deadzone=2` (right-drag engages at
8 px with a much gentler onset — dead zone `12→2`). Built in one invocation from `SIMSPR.DLL.shipped`.
(The 2026-08-25 build was `scroll16 + drag4 + deadzone4`; the owner confirmed the diagonal held better
and asked for a gentler onset and gentler keys, hence `scroll8 + deadzone2`.)

**This means `game_lock.ps1 -Status` reports `install : MODIFIED -> SIMSPR.DLL`, and that is
EXPECTED, not contamination.** Any session that sees it should read this note before assuming a run
left debris behind.

| | |
|---|---|
| backup | `Apps\SIMSPR.DLL.shipped`, sha256 `eec715009152eec0ce756f74…` |
| staged build | `verify/drag_divisor_test/SIMSPR.DLL.gentle`, sha256 `e63ec800…` |
| staged | **8 differing runs, 9 bytes**, verified by an independent `--diff` (5×1-byte scroll `42→41` + 2×1-byte drag + 1×2-byte dead zone). NB fewer bytes than the `16/4` build: `8.0`/`2.0` change fewer bytes than `16.0`/`4.0` |
| live values | scroll `0x10067690`–`0x100676a0` all `8.0`; drag imm8 `0x10043a5e`/`0x10043a68` both `fc` (−4); dead zone `0x100676a4` = `2.0` |

**Undo (removes ALL THREE mods), and do this before any run that needs a stock install:**

```powershell
Copy-Item Apps\SIMSPR.DLL.shipped Apps\SIMSPR.DLL -Force
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10067690:f32 -n 5   # expect 32.0 x5
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10043a5e:hex -n 1   # expect fe (-2)
```

⚠️ **Any measurement taken while this is staged is on a modified SIMSPR** — that is the module carrying
the camera, the iso view and the sprite paths, so it is not a neutral change for rendering or camera
work. **The live install now perturbs the step bank, the drag divisor AND the drag dead zone**, so a
camera measurement taken against it reads the modded values as if shipped. **Any subsequent camera
measurement must restore shipped SIMSPR first.** `U-082`'s record is unaffected (it closed before this
was staged).

## ⚠️ STANDING RULE — the owner's build must be live when you finish (UPDATED 2026-08-26: FOUR recipes + GZGraphicD)

**Two modules are now modified** (2026-08-26, resize hand-test):

1. **`Apps\SIMSPR.DLL` is a FOUR-recipe build** (was three): `scroll_speed=8` + `drag_divisor=4` +
   `drag_deadzone=2` + **`resize_rectfix`** (the U-068 post-resize present-rect code cave). sha
   `f5b9f1d9…`, **gate 13 runs / 45 bytes** (5 scroll + 2 drag + 2 dead-zone + 36 resize_rectfix =
   33 cave + 3 hook). `resize_rectfix` is inert unless the iso Init runs, so it does not change camera feel.
2. **`Apps\GZGraphicD.dll` carries TWO recipes: `resizable_frame` + `close_button_quit`** (style flip
   WS_THICKFRAME|WS_MAXIMIZEBOX, 3 bytes; plus the WM_CLOSE→PostQuitMessage **position-independent** code
   cave that makes the X quit, 62 bytes), combined sha `acefadf0…`, **gate 65 bytes / 12 runs**.
   ⚠️ `close_button_quit` was hardened from an earlier ABSOLUTE version (sha `fc89a394`, which would crash on
   WM_CLOSE when GZGraphicD relocates — a load-order coin flip); the live build `acefadf0` is
   position-independent. Experimental for the D-004 hand-test; if the owner reverts, GZGraphicD → shipped.

**Any session that touches either module must restore the owner's live build as its LAST action, and verify
it.** Every time. `game_lock.ps1 -Status` will report `install : MODIFIED -> SIMSPR.DLL` (and now also
GZGraphicD) — EXPECTED, not contamination.

**Re-stage the owner's build (both modules, from shipped, one invocation each):**
```powershell
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL.shipped --recipe scroll_speed=8 --recipe drag_divisor=4 --recipe drag_deadzone=2 --recipe resize_rectfix --out SIMSPR.DLL.4
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL.shipped --diff SIMSPR.DLL.4   # gate: 13 runs / 45 bytes
Copy-Item SIMSPR.DLL.4 Apps\SIMSPR.DLL -Force
py -3.12 re/tools/pe_patch.py Apps\GZGraphicD.dll.shipped --recipe resizable_frame --recipe close_button_quit --out GZGraphicD.dll.rf
py -3.12 re/tools/pe_patch.py Apps\GZGraphicD.dll.shipped --diff GZGraphicD.dll.rf   # gate: 65 bytes / 12 runs
Copy-Item GZGraphicD.dll.rf Apps\GZGraphicD.dll -Force
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10067690:f32 -n 5   # expect 8.0 x5
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x100676a4:f32 -n 1   # expect 2.0
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10005f55:hex -n 5   # expect e8 40 b5 05 00 (cave hook)
py -3.12 re/tools/pe_patch.py Apps\GZGraphicD.dll --read 0x10018570:hex -n 1  # expect cd
```

**Full undo — return BOTH modules to shipped (the owner's one-line restore):**
```powershell
Copy-Item Apps\SIMSPR.DLL.shipped Apps\SIMSPR.DLL -Force; Copy-Item Apps\GZGraphicD.dll.shipped Apps\GZGraphicD.dll -Force
```
(That undoes the resizable frame AND the camera mods. To keep the camera build but drop only the resizable
frame, restore just GZGraphicD.) Every recipe pins its module's shipped SHA, so all recipes for a module
must be applied **to that module's `.shipped` in one invocation**. A different `--diff` count means stop,
not stage. ⚠️ **Restoring shipped SIMSPR for a measurement is still legitimate — but re-stage the FOUR-recipe
build (not the old three) as your last action.**

## ⚠️ `capture.ps1` LEASES FOR 15 MINUTES REGARDLESS OF `-AtSec` — found 2026-08-25

`capture.ps1:71` hardcodes `-Minutes 15` on the acquire. **`-AtSec` sets the kill timer, not the lease
duration.** So any run longer than 15 minutes spends its remainder holding an **expired** lease.

Measured on the owner's 30-minute playtest: lease log says *"acquired by 'capture-playtest' for 15
minute(s)"* while `-AtSec 1800` kept the game alive for 30. Halfway through, `-Status` reported
**`lease : STALE - reclaimable`** with the game still running.

**Why this is dangerous rather than untidy:** a stale lease is *reclaimable*, so a sibling session
polling `-Status` is told the game is free and may launch. **SC3U is single-instance** — a second
launch exits `0xFFFFFFFF` at ~840 ms with no dump, which this board already records as
**indistinguishable from a broken patch**. The failure would land on the innocent session and look
like its own patch failing.

It did not bite this time only because the game had already exited when the state was next checked.

**Fix:** derive the lease minutes from `-AtSec` with headroom (e.g. `[math]::Ceiling($AtSec/60) + 5`)
rather than hardcoding 15, or renew the lease periodically while the run is live. Until then,
**do not use `-AtSec` above ~800 s**, and treat a `STALE` lease as "verify no game process is alive"
rather than "free".

## ⚠️ Pre-registration must be COMMITTED before the run, not written beside the result

`verify/tilingrules_constructive/PRE.md` opens *"PRE-REGISTRATION (committed before any run)"* — but it
was **untracked**, with an mtime of 22:51 against `RESULTS.md` at 22:52. **The file could not
demonstrate its own claim.** An auditor sees a pre-registration dated, as far as the filesystem knows,
at result time.

In that instance the claim was **true and independently provable** — the session stated the prediction
(`11203`, stock control `29`) to the orchestrator *before* the fire order, so it is attested in the
conversation transcript. **But that was luck, not design.**

**Rule: `git add` + commit the `PRE.md` BEFORE taking the lease.** Git then supplies an independent,
tamper-evident timestamp and pre-registration becomes a fact rather than an assertion. One commit.

Related: game-content artifacts (`.sc3` saves) are correctly **not retained**, so a result is usually
not re-derivable afterwards. That makes `RESULTS.md` the sole record — **write the per-run counts and
hashes into it in full**, because nobody can recompute them.

## ⚠️ A THIRD instrument-failure class, found 2026-08-25: the NONDIAGNOSTIC PROXY

Debt item 1 covers **silent** failures — instruments that produce nothing and say nothing. This is a
different animal and needs a different defence.

**A nondiagnostic proxy reports something true that does not answer the question.** Measured: an
unpause run's `.sc3` grew 920,753 → 921,206 B, which looks like proof the sim mutated state. **The
paused control — which never received the message — grew to 921,209 B, more than the unpause arm.**
The save re-serialises non-deterministically per reload, so a changed file witnesses nothing at all.
Two sibling proxies failed the same way in the same run: the in-game date was **not legible** in the
composite (a new city's status bar shows the name, no date bar renders), and the pause/play toolbar
icons are fixed-colour, differing between frozen and running frames by a 2x9 px artifact.

**The defence is not a louder instrument — it is a control that can invalidate the proxy.** A silent
failure is caught by making the instrument shout; a nondiagnostic proxy is caught only by an arm that
*should* show no effect and does anyway. Without that control this would have been reported as
"the save changed after unpause, therefore it unpaused", and it would have been wrong.

**Rule: prefer a definitive internal state read over any UI or file-size proxy.** Here that is the
coordinator's pause bit at `+0x38` (semantics confirmed at `FUN_100072d8`) plus the clock — two
internal witnesses, neither depending on the UI rendering anything.

## Cross-cutting debt

Ordered by how much damage it can do silently.

> **Cross-workstream dependency (bigcities → roadtypes), recorded not requested (2026-08-25).**
> `bigcities` Lease 2 (development at 512 with served zones) needs road+power planted at chosen
> coordinates. `city_write.py` writes zones only; the network layer `0x2147c2dd` has a validated
> **reader** in `roadtypes`' `re/tools/network_layer.py` but **no writer**. Extending that reader to
> write is a much smaller step than starting from nothing, and it would unblock offline service
> planting for the development test (the other unblock path is anchoring the screen→world map).
> **Not a request — `roadtypes` owns its priorities and has its own lease-ready run.** Flagged so it
> is visible if they finish first.

1. **⚠️ SILENT-FAILURE INSTRUMENTS — now a pattern, not an incident. Two confirmed.**
   - **`gzseq` target-wait** SKIPs silently, producing a plausible-looking capture.
   - ~~**`capture.ps1`'s frame reconstruction** produces *nothing* and says *nothing*~~ **MADE LOUD
     2026-08-25 — but see the scope limit below.** Found 2026-08-24 by T1 run 1: 71 s, engine
     drawing hard at `raster_blit_hw` 26,565, **zero `### SHOT #` lines**, exit 1, no explanation.
     `sc3probe.c` latches `g_rasthw_dest` from `*(this+4)` on the **first** `raster_blit_hw` hit,
     and `g_fb` allocation, the mirror match and the arming all hang off it. Two runs latched
     **different objects from the same code** — `0x00A45AB8` wrote frames, `0x0BEC4A80` produced
     nothing.

     **What was changed** (`sc3probe.c`, `capture.ps1`; both gitignored, so this note is the record):
     every `g_fb` abort path now names itself once — unreadable dest, dest vtable with fewer than 33
     slots, `Lock(slot 25)` failure with `hr`, implausible dims, `VirtualAlloc` failure — plus a
     warning when a shot is requested while `g_fb` is NULL, and a mirror-window summary
     (`N matched, M aimed elsewhere`) that says outright when an image is **blank by construction**
     rather than blank because the game drew nothing. `capture.ps1` now prints those `SHOT>` lines on
     failure and no longer asks *"did the game render?"* — that framing presupposed the game was at
     fault and is what sent the 2026-08-22 note to "in-city rendering does not work".

     ✅ **AND IT IMMEDIATELY PAID OFF — root cause found 2026-08-25, one run, one log line.**
     The diagnostic printed exactly `SHOT> g_fb READY 1024x768 from latched dest 0x038B6ED8`, which
     **ruled out the entire allocation family** (dest readable, `Lock` succeeded, dims plausible,
     `VirtualAlloc` fine) — and then **no `mirror window closed` line at all**. The window opened and
     never closed in 72 s. So the latch was never the problem and the
     `0x00A45AB8`-vs-`0x0BEC4A80` hypothesis is **refuted**.

     **The real defect is a re-arm loop, and it is arithmetic.** `g_shot_arm_n = 4000`; the 3 s timer
     sets `g_shot_req` unconditionally; servicing a request **RESET** `g_shot_arm` to 4000. In-city
     the engine runs **~391 blits/s ≈ 1,170 per 3 s**, so the countdown was restarted before it could
     ever reach zero — **at any run length**. It was the reset, not the volume: 26,351 blits
     accumulated in 72 s, so an un-reset window would have closed around t+12 s.

     **That also closes the instrument comparison.** `-u068shot` does exactly two things that matter:
     sets `g_shot_arm_n = 400` **and** suppresses the 3 s timer. **The two instruments were the same
     code separated by one constant and one boolean** — which is the whole reason shot A exists and
     `capture.ps1` had never made an in-city frame.

     **Fixed 2026-08-25:** a request landing while a window is still open is now **dropped, not
     honoured** (correct at any blit rate, unlike lowering the constant), and both window open and
     close now log. Probe rebuilt. ⚠️ Still **unverified by a run**, though the diagnosis is
     arithmetically established and confirmed in source (lines 211, 1034, 5166, 6970).

   Both manufacture confident wrong answers rather than errors. **Any harness instrument must fail
   loudly**; this is the same class of defect as `+0x524` being read as a symptom (§31.11).

   ✅ **The `capture.ps1` half is CLOSED 2026-08-25** — the loud diagnostic found the real defect (a
   mirror-window re-arm loop, not the latch), the fix is in, and T1 then ran and passed. Verified
   working in the log: `mirror window OPEN: 4000` at t+3.89 s, one `request arrived … IGNORED` at
   t+7.17 s (the fix firing), `mirror window closed: 3577 matched, 423 aimed elsewhere` at t+13.49 s.
   Five dumps per run at ~10 s each. **`gzseq` is still open.**

   `[UNCERTAIN]` the steady **5.6%** `aimed elsewhere` (225/4000, stable across every window in both
   runs). The latched dest is the dominant destination, not one of several rivals, so it does not
   affect the T1 result — but what that 5.6% is was not investigated.

2. **⚠️ `gzseq` step semantics — three traps, all found 2026-08-25, all of the silent kind.**
   - **`key:` dispatches and returns immediately.** The hold runs asynchronously, so a following
     `cam` measures ~63 ms in, not after the hold. A 2.5 s-hold comparison needs
     `key:0x25,2500;wait:3000;cam`. This produced an apparently clean "delta 0" that was **not
     reportable** — the run that hit it said so instead of banking the number.
   - **A `wait:` longer than 90 s cancels itself.** A step without `@N` inherits the 90 s default
     timeout, so `wait:180000` skipped at 90 s. Use `wait:180000@200`.
   - ⭐ **`key:` DOES NOT SUSTAIN A HOLD — it registers as a single tap.** Established 2026-08-25 by
     a within-process three-arm control: null arm drift `0,0` exactly, key arm `-32,0` = **exactly one
     32-px step** where a 2.5 s hold should give **214** (the recorded `-6848` baseline is precisely
     `214 x 32`). **This one defect is the whole of `U-081`** — it made a working camera look like a
     512 clamp bug and consumed five runs. Any timed-input measurement taken with `key:` before this
     date is suspect.
   - ✅ **`capture.ps1` `-GameArgs` whitespace splitting — FIXED 2026-08-25.** It split unconditionally, so
     `Cities\Berlin, Germany.sc3` became two arguments. It loaded on one run (SC3U happened to
     reassemble the tail) and **failed on a later identical run** with *"El archivo especificado en la
     linea de ordenes no es valido o no se ha encontrado"*, voiding a whole lease. **Intermittent is
     worse than broken.**

     **The fix needed BOTH ends**, which the run agent caught and I had missed: `capture.ps1` gained a
     `-GamePath` parameter appended as one quoted argv element, **and `sc3launch.c` was re-flattening
     the passthrough with bare spaces and no quoting** (`lstrcatA(gameargs, argv[i])`), so no amount
     of care on the PowerShell side would have survived. The launcher now re-quotes any forwarded
     argument containing whitespace and echoes what SC3U will actually receive. Both rebuilt.

     Two further guards, each from an error made while fixing it: `-GamePath` is **`.Trim()`ed**
     because the `-GameArgs:" $path"` idiom carries a deliberate leading space to stop PowerShell
     binding `-lC:` as a parameter; and the **pre-flight `Test-Path` sits ABOVE the lease acquire**,
     because when I first placed it below, its `exit` bypassed the `finally` and **orphaned a lease**.
     Verified by running it: bad path now exits non-zero with `lease : (none)`.
   - ⭐ **`cam` reads the FIRST object matching vtable `SIMSPR+0x6250c` and stops — and it is not the
     only such object.** The minimap is also a city view and would own a cell map. So which rect gets
     measured may depend on allocation order and **vary per process**, which fits every camera anomaly
     seen 2026-08-25: byte-identical reads on one fixture, ~1,000 px/s churn on another, and a frame
     showing a normal in-map view while the field read `x = -2396`. ✅ **FIXED 2026-08-25** (probe rebuilt,
     244,736 b): the search now enumerates **every** match across both bases, de-duplicates objects
     reached via two fields, prints each candidate's `rectA`, span, zoom and tilepx so they can be told
     apart, marks which one is used, and emits a loud `!! N objects carry vt …` line when there is more
     than one. It still uses the first, so earlier readings stay comparable — but never again without
     disclosing the ambiguity. ⚠️ **UNVERIFIED — no run has exercised it yet.** Until a run does, treat
     any single-process camera series as provisional and any **cross**-process camera delta as void,
     and keep the `FUN_10006226` counter parked: a scroll counter is uninterpretable while it is
     unknown whose rect is observed.
   - **`cam`'s failure message asserts rather than measures.** It names `cityViewIso`
     unconditionally, even though that base is only searched when `*(cityView+0xb8)` is non-null — so
     an earlier "no object reachable at `cityViewIso+0x158`" line was an assertion, not a
     measurement. The real cause was **timing**: it ran ~0.1 s before in-city readiness.

3. **Pre-existing `-filetrace` startup race, found 2026-08-25 and NOT introduced by the fixes.** One
   control run died at **t+117 ms** with `C0000005` at `sc3probe.dll 01:000070BD` on a non-game
   thread, with **`EAX = 0x00005A4D`** — the `MZ` DOS-header magic, i.e. a PE-header parse while
   modules are still arriving. Consistent with `ft_hook_all()`'s 100 ms module walk. **Not
   deterministic** (an identical relaunch ran clean for 75 s) and **not a regression** (the previous
   build ran `-filetrace` for a full 75 s). `[UNCERTAIN]` the exact function — there is no `.map` or
   `.pdb`, and rebuilding to get one would have replaced the binary under test.
4. ~~**`capture.ps1` does not take the game lease itself.**~~ ✅ **STALE — corrected 2026-08-25 by
   reading the file.** It **does** acquire the lease (line 71) and release it in a `finally` (line 202).
   Do **not** wrap calls in an outer `game_lock.ps1 -Acquire`; that self-deadlocks or orphans a lease.

   ⚠️ **A killed shell orphans the lease** — the `finally` never runs. Observed 2026-08-25 when a
   session ended mid-capture: lease still `HELD` by `capture-slowcam`, `game up : no`.

   ⚠️⚠️ **BUT THAT IS THE MINOR CAUSE. THE REAL ONE IS SILENT, SYSTEMIC, AND FIRES ON EVERY CLEAN
   EXIT — found 2026-08-26.** `capture.ps1:202` is:

   ```powershell
   & pwsh -NoProfile -File $lock -Release -Owner $Owner | Out-Null   # free the queue
   ```

   **`game_lock.ps1 -Release` REFUSES when the install is MODIFIED** unless `-DirtyOk` is passed —
   and **`| Out-Null` swallows the refusal**. So the `finally` runs, the release fails, nothing is
   printed, and the lease is held until its 15-minute expiry.

   **The owner's camera build is permanently staged, so the install is ALWAYS dirty. Therefore every
   capture run currently leaks its lease, silently.** Measured: `bptmim8jp` exited **0**, `game up :
   no`, and the lease was still `HELD` by `capture-resizehand`. This is what produced every "idle
   lease with no game behind it" on 2026-08-25/26 — those were misattributed to killed shells.

   **Fix:** `capture.ps1` already detects and prints `NOTE: install is already MODIFIED -> …` at
   acquire, so it knows. Pass `-DirtyOk -Note "pre-existing: <modules>"` on the release in that case,
   and **stop piping the release to `Out-Null`** — a failed release must be loud. This is the same
   silent-failure class as debt item 1 and the nondiagnostic proxy: it does not error, it just
   quietly does nothing.

   Until fixed: after any `capture.ps1` run, check `-Status` and release with
   `-Release -Owner capture-<name> -DirtyOk -Note '<why>'`.

   ⚠️⚠️ **The stale claim caused a real deadlock, 2026-08-25.** A session that believed the old note
   took an outer lease as `bigcities`, then called `capture.ps1` — which **self-acquires under its own
   owner name** (`capture-author512`). The inner acquire queued behind the outer one and blocked until
   expiry, while the session reported its run as "executing in the background". `-Status` showed the
   truth: `lease : HELD owner: bigcities` with `queue : 1 waiting - capture-author512`.

   **Rule: never wrap `capture.ps1` in an outer `game_lock.ps1 -Acquire`.** It takes and releases its
   own lease. If you need one lease held across several launches, use `re/harness/with-game.ps1` —
   `game_lock` passes a same-owner re-acquire through (line 206), but `capture.ps1`'s `finally`
   releases, which breaks a multi-launch hold. **A blocked acquire looks exactly like a slow run**,
   so check `-Status` before believing a background launch is live.
5. **Build→run probe-DLL swap.** `build.ps1` will relink the shared `sc3probe.dll` out from under a
   live session. Either add a per-session `-Out` name or make `build.ps1` refuse without the claim.
   Deferred by decision in `COORDINATION.md`; do it while the harness is quiet.
6. **Pre-existing brace bug in the resizable-window harness code, flagged not fixed.** In
   `rz_iso_resize`, `if (redraw != simspr + 0xb4b3) ... else` has no braces, so `FUN_1000b4b3` is
   called even when the vtable check fails. Benign so far. It is that session's code and its call.
7. **`STUBS.md` is still an empty template.** `DEFERRED.md` was too until 2026-08-24.
8. **Writing `functions.csv` safely — two rules learned the hard way 2026-08-24.** The file is
   **fully quoted**, so a writer must use `QUOTE_ALL`; a default `csv.writer` re-quotes every field
   and flattens the 61 bare LFs inside quoted `notes`, which turns a 23-row edit into a
   **50,668-line diff**. And records must be matched on the **parsed** `(module, rva)` pair, never a
   raw string prefix. Always check `diff functions.csv.bak functions.csv | grep -c '^<'` equals the
   number of rows you meant to touch, and restore from the backup rather than hand-patching if it
   does not. **Never bulk-overwrite rows already at C2+** — they were written by someone who read the
   function, and a fresh report is not automatically better (`NETWORK_RULE_ENGINE.md` §12.7).

## Camera thread — `U-082`, six runs deep, mechanism still open

**Your slower camera is DONE and unstaged:** `verify/scroll_patch_test/SIMSPR.DLL.slow16`, verified as
exactly 10 bytes across the five step slots. `scroll_speed=16` = half the shipped `32.0`.

**The bug is real and unexplained.** Five mechanisms have been falsified one gate at a time:
off-map-kills-view, soft clamp / pull-back, minimap cell map (first-match), repaint-driven tick count,
and follow/track (`+0x354` read zero on 16/16 reads while the churn ran). Each cost a run. Two of the
five were mine.

**Robust facts:** `span = 1024x768` on **76/76** rect prints with `rectB == rectA`, so this is a
**rigid translation**, not corruption · the load origin is **deterministic** (`-160,1604` three times) ·
`FUN_10006226` has **zero call sites** and exactly one vtable dword (`.rdata 0x10062538`) · the
frozen-vs-churning regime is **not** selected by elapsed time · a **fixed sub-tile phase lock** appears
mid-process with zero input (x ≡ 9, y ≡ 28 mod 32, axes locking one read apart).

**Built and ready, never run: a hardware write watchpoint** (`SC3PROBE_CAMWATCH=1`, probe 246,272 b).
DR0 on `iso+0x54`, `DR7 = 0x000D0001` (write, 4 bytes, verified bit by bit), a vectored handler
recording faulting EIPs into a bounded table, resolved to `MODULE + offset`. **It names the writer
instead of eliminating candidates** — which is the point, because candidate elimination has lost five
times in a row.

Two limits are printed in its own arm line so they cannot be missed: data breakpoints are **per
thread**, so **zero hits is ambiguous**; and the reported EIP is the instruction **after** the store.

🔒 **CLOSED AS UNREPRODUCIBLE 2026-08-25, after ~22 launches.** Every proposed variable was eliminated — instrument suppression (twice, by crossed designs), warm cache, switch set (byte-identical), cadence, and window length. The early onsets failed a direct three-launch re-test, so they are **not reproducible**, and the era probe binary is **gone** (searched, not assumed), leaving build-vs-machine-state permanently unseparable. **Fix applied so it cannot recur: `capture.ps1` now logs the probe SHA-256 at every launch.** If resumed, **change the fixture** — every churn observation is Farmsville.

**What is banked and does NOT depend on the churn:** ⭐⭐ **WRITER NAMED 2026-08-25: `FUN_10006226 + 0x89` (`SIMSPR+0x62AF`), the translate itself** — and a second, `SetZoom + 0x177`, at city load. **29 of 29 intervals separate perfectly: stores happen iff the origin moved**, and no moving interval lacked writes, so **the writer is on the game thread and the cross-thread hypothesis is retired.** The per-interval census is what did it — one launch supplied 12 moving samples and 17 controls, and the launch that would have been a wasted lease under run-level scoring contributed 15 of those controls.

⭐ **The reframe, and it is the live question now: ~75-165 calls per SECOND into the translate with zero input** — while `FUN_10006226` has zero direct call sites, one vtable pointer, and its only known input-free path is gated closed. **Something enters iso vt `+0x2c` a hundred-plus times a second through a path nobody has identified.** Next step, same technique: hook `FUN_10006226` entry, record the **return address**, difference per interval.

~~UN-PARKED - the wall was an artefact of run-level verdicts.~~ Three controls with the watchpoint disabled produced a freeze (E2, 15 reads / 27.9 s), which **kills the suppression confound and exonerates the instrument**. And E1 showed **churn stops by itself** — it churned 7 transitions then froze for 6 — so churning and frozen are properties of a **window**, not a run. Every run-level verdict here, mine included, was really about *when it sampled*.

**So the blocker dissolves.** The problem was never "we cannot get a moving camera"; it was that we labelled whole runs. **Next step: have `cam` report the watchpoint census PER INTERVAL beside that interval's `dx,dy`.** Each interval becomes its own experiment, the moving intervals are the ones whose EIPs matter, and a single launch yields both a moving sample and a frozen control. Needs no reliable churn at all.

⭐ **Also found: the ZOOM moves with no input** (`zoom=2` → `zoom=4`, zero keys), and `SetZoom` is a *different* vtable slot from the translate — so the driver touches more than one entry point, and a translate-only hunt could miss it. And the out-of-bounds bound is **zoom-dependent** (`N x tilepx`), so every such claim in this thread needs re-checking against the zoom on the same read.

~~PARKED at a non-reproducibility wall, after seven runs.~~ The watchpoint was built, armed correctly and reported 0 hits — **but the camera did not move that run**, so it measured the instrument rather than the camera. Churn onset across four identical runs: **t+16.6 s, t+14.6 s, t+8.0 s, never.** A 3-of-4 rate that **nothing identified sorts** — not elapsed time, not the fixture, not input, not the sim.

**Before any further run in this thread, two things are required, and they are the reason it is parked rather than continued:** a **live churn-detection gate** (so a null cannot masquerade as a negative — this run fell in that trap) and **a base rate instead of another single run** (at 3-of-4, one run cannot separate "my change suppressed it" from "this one was quiet"). Single runs against a scarce lease are the wrong instrument for a sample-size problem.

**One confound owed on my own instrument:** run D was the only one with `SC3PROBE_CAMWATCH=1` and the only fully frozen one. No mechanism is nameable, but the cheapest test on the list is rerunning it with the env var unset, and it should happen before the watchpoint is trusted on a moving camera.

**Also still open:** whatever flips the quantisation at t ≈ 19–21 s.

## Publish hygiene — `github.com/nanofives/sc3kre` is PUBLIC

Tools and notes only. **Never** game assets or decompiled output.

- **Owner's call outstanding:** the local Windows username is in the public history. Rewrite or
  accept. Scrubbed going forward either way.
- Exclude the game-derived binaries before the next push: `N512_city.sc3` and the three
  `*.DLL.shipped`. **Never** add `verify/tilingrules_read_test/TilingRules.bak/` — 68 files of game
  content.

## Decision log

| date | decision | recorded in |
|---|---|---|
| 2026-08-17 | End-state is a **modding / format toolkit**. The source port is **closed**, not deferred. | `ROADMAP.md` P1 gate |
| 2026-08-24 | Camera ships as a **byte patch**; the **standalone proxy-DLL vehicle is dropped**. The `-pref` slider works but has no distributable form. | `DEFERRED.md` D-001 |
