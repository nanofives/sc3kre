# BOARD.md — the orchestrator's view

**What this is:** the open surface organised by **mod / feature**, which is how work is actually
parcelled out to sessions. `ROADMAP.md` is the phase-and-gate record and is largely historical now;
this file is the live board. Opened 2026-08-24.

**What this is not:** a history. Decisions and rationale live in `ROADMAP.md`, deferrals in
`DEFERRED.md`, open questions in `UNCERTAINTIES.md`, per-session state in `re/sessions/STATUS_*.md`.
This file points at them and does not restate them.

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
| **Camera scroll** | `pe_patch.py` | `formats/CAMERA_MODDING.md` | `drag_divisor` / `edge_margin` static-only (**D-002**), zoom-4 reachability (**D-003**) |
| **Network tiling rules** (retune / re-skin an existing network) | `tilingrules.py` | `formats/TILINGRULES_MODDING.md` | T1 met game-side 2026-08-25. One edit of one kind; render-path result, no simulation claim |
| **Bigger cities** (N > 256, proven at 512) | `patch_citysize.py` + `patch_dirtbuf.py` | `formats/BIGGER_CITIES.md` | ⭐ **engine reads/renders/re-serialises tiles to 495 with no coordinate-dependent failure** (2026-08-25). Still open: development (city loads paused; bare zones have no road/power), in-game authoring at 512, and **`U-081`** drag-scroll apparently dead at 512 |

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

**Next, in order:** (1) **`U-081` — a NO-KEY NULL CONTROL** (`wait:15000;cam;wait:3000;cam`), one run.
Five causes are eliminated and **the question has moved upstream of 512**: the recorded `-6848` camera
baseline does **not** reproduce on a path-loaded city at matched field, zoom, key and duration
(`Δ = +26, 0` vs `-6848, 0` — the axis reproduces, the magnitude does not). **Until a null control
exists, no delta measured in this investigation can be attributed to the key**, and a 512 number would
mean nothing. The uncontrolled variable is **menu-load vs path-load**: path-loaded cities are paused,
and the baseline's pause state is recorded in neither source file. If a paused city simply does not
scroll, that explains both of the owner's original observations with **no map-size involvement at
all**. (2) In-game **authoring** at 512
(`fire:<toolcmd>` + `drag:`, established at 256, untried at 512). (3) Development, which needs an
unpause path — **none exists among the 90 shipped menu commands** — plus road and power. (4) A bound
above 512.
Stride/corner measurement is deferred as cosmetic (~8 runs).
Session CLOSED. Anyone may pick it up.

### 2. Resizable window / arbitrary resolution — BLOCKED, only open session
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

### 4. Camera scroll — SHIPPED 2026-08-24
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
| `U-063` | Who calls the RECT zone writer `0x10032afa`. Gates rect-level zone edits. |

## Cross-cutting debt

Ordered by how much damage it can do silently.

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
   - **`capture.ps1` splits `-GameArgs` on whitespace.** `Cities\Berlin, Germany.sc3` was passed as two
     arguments and **the game loaded it anyway**, because SC3U recombines its command-line tail. It
     worked by luck of the exe's argument handling, not by the harness being correct. Any fixture with
     a space in its name is on borrowed time.
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
4. **`capture.ps1` does not take the game lease itself.** Until it does, wrap every call in
   `game_lock.ps1 -Acquire -Wait -Owner … / -Release`.
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
