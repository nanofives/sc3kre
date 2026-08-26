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
| 2 | **New road types** | `cmt96pjiy…` | `STATUS_roadtypes.md` | the **constructive** rung (T1 was destructive) |
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
| **Camera scroll + drag** | `pe_patch.py` | `formats/CAMERA_MODDING.md` | `drag_divisor` **C3 observed** (velX 50→25→50) staged live with `scroll_speed=16`; `edge_margin` **C3 observed** (band 48/64→24/32→48/64), not staged; only OS-input "feel" leg unmeasured (**D-002**, optional), zoom-4 reachability (**D-003**) |
| **Network tiling rules** (retune / re-skin an existing network) | `tilingrules.py` | `formats/TILINGRULES_MODDING.md` | T1 met game-side 2026-08-25. One edit of one kind; render-path result, no simulation claim |
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

**Next, in order:** (2) Development, **now the critical path**, which needs an unpause path —
**none exists among the 90 shipped menu commands** — plus road and power. Several sibling workstreams
need unpause solved too, so it is the highest-leverage item on this board. (3) A bound above 512.
Stride/corner measurement is deferred as cosmetic (~8 runs).
Session CLOSED. Anyone may pick it up.

### 2. Resizable window / arbitrary resolution — black-vs-garbage RESOLVED 2026-08-25 (U-068 = "renders but does not blit"; see the run-4 subsection below)
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

## ⚠️ THE INSTALL IS DELIBERATELY MODIFIED — `SIMSPR.DLL`, slower camera (TWO mods now)

**Staged 2026-08-25 at the owner's request. As of the drag4 close, this is now TWO mods, not one.**
`Apps\SIMSPR.DLL` carries **both** `scroll_speed=16` (arrow-key + edge scroll at half speed) **and**
`drag_divisor=4` (right-drag pan at half sensitivity). Built in one invocation from
`SIMSPR.DLL.shipped`.

**This means `game_lock.ps1 -Status` reports `install : MODIFIED -> SIMSPR.DLL`, and that is
EXPECTED, not contamination.** Any session that sees it should read this note before assuming a run
left debris behind.

| | |
|---|---|
| backup | `Apps\SIMSPR.DLL.shipped`, sha256 `eec715009152eec0ce756f74…` |
| staged build | `verify/drag_divisor_test/SIMSPR.DLL.slow16drag4`, sha256 `117fa3b1…` |
| staged | **7 differing runs, 12 bytes**, verified by an independent `--diff` (5×2-byte scroll + 2×1-byte drag) |
| live values | scroll `0x10067690`–`0x100676a0` all `16.0`; drag imm8 `0x10043a5e`/`0x10043a68` both `fc` (−4) |

**Undo (removes BOTH mods), and do this before any run that needs a stock install:**

```powershell
Copy-Item Apps\SIMSPR.DLL.shipped Apps\SIMSPR.DLL -Force
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10067690:f32 -n 5   # expect 32.0 x5
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10043a5e:hex -n 1   # expect fe (-2)
```

⚠️ **Any measurement taken while this is staged is on a modified SIMSPR** — that is the module carrying
the camera, the iso view and the sprite paths, so it is not a neutral change for rendering or camera
work. **The live install now perturbs BOTH the step bank AND the drag divisor**, so a drag measurement
taken against it would read `-4` as if it were shipped. **Any subsequent camera measurement must
restore shipped SIMSPR first.** `U-082`'s record is unaffected (it closed before this was staged).

## ⚠️ STANDING RULE — the owner's SIMSPR build must be live when you finish

The owner's standing install state is a **two-recipe** `Apps\SIMSPR.DLL`: `scroll_speed=16` **and**
`drag_divisor=4` (half-speed keys, edge-scroll **and** right-drag).

**Any session that touches `SIMSPR.DLL` must restore that build as its LAST action, and verify it.**
Not usually — every time. Sessions legitimately restore shipped SIMSPR to take a measurement (it
carries the camera, the iso view and the sprite paths, so it is never neutral), and on 2026-08-25 that
left the install stock **three separate times** with no run in flight. **The failure mode is silent:**
the owner launches the game expecting a slow camera, gets a fast one, and nothing in any log explains
it.

```powershell
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL.shipped --recipe scroll_speed=16 --recipe drag_divisor=4 --out SIMSPR.DLL.slow16drag4
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL.shipped --diff SIMSPR.DLL.slow16drag4   # gate: 7 runs / 12 bytes
Copy-Item SIMSPR.DLL.slow16drag4 Apps\SIMSPR.DLL -Force
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10067690:f32 -n 5   # expect 16.0 x5
py -3.12 re/tools/pe_patch.py Apps\SIMSPR.DLL --read 0x10043a5e:hex -n 1   # expect fc
```

Both recipes pin the shipped SHA, so they must be applied **to `SIMSPR.DLL.shipped` in one
invocation** — neither will anchor against an already-patched module. The 7-runs/12-bytes gate is five
2-byte step-slot runs plus two non-adjacent 1-byte drag runs; **a different count means stop, not
stage.** `Copy-Item Apps\SIMSPR.DLL.shipped Apps\SIMSPR.DLL -Force` still undoes both.

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

   ⚠️ **The real residual is the opposite failure:** if the shell running `capture.ps1` is killed
   rather than exiting, the `finally` never runs and **the lease is orphaned**. Observed 2026-08-25
   when the owning session ended mid-capture — lease still `HELD` by `capture-slowcam`, `game up : no`.
   Release with `-Release -Owner <name>`; if the install is deliberately modified the lock **refuses**
   and you must pass `-DirtyOk -Note '<why>'`, which is audited. Check `-Status` before assuming a
   sibling session is really running.

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
