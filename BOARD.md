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

> **Correction on record:** `HANDOFF.md` still claims sprite modding has "no RGB565 quantizer and no
> PNG import". That is **stale** — `sprite_patch.py` has `quantize565()`, `export_png()` and
> `replace_from_png()`, `--pngtest` is 62,552/62,552, and it was validated game-side 2026-08-19.
> Trust `ROADMAP.md`'s T2 table over `HANDOFF.md` on this.

## Active workstreams

### 1. Bigger cities (N=512) — not blocked, closest to done
Sim accepts 512; the renderer crash is fixed by the SIMDIRT SIZE group alone (config C 6/6 survive,
shipped 0/6). Four bytes are the whole fix. Tool: `patch_dirtbuf.py`.
**Next:** one execution of the rewritten `verify/citysize_mod_test/run_diff.ps1`, which has never
been run in its current form. **Then:** drive actual gameplay in a 512 city (zoning, building) —
nobody has played one. No bound above 512 has been tried.
Stride/corner measurement is deferred as cosmetic (~8 runs).
Session CLOSED. Anyone may pick it up.

### 2. Resizable window / arbitrary resolution — BLOCKED, only open session
`U-068`: display lists stay empty after a resize Init. Root cause established 2026-08-23 by two
independent angles — Init sizes and zeroes grid B, only object registration fills it, and Init's only
route early-outs on a zero-equality guard. **The fix is to re-drive registration, not to repair the
builder.** Two fix candidates written with a pre-registered falsifier.
**Next:** 2 to 4 runs of ~60 s (`-kill >= resizeat+22`).
**Behind it:** `U-069` — downward resize has never been exercised at all, so read every "resize
works" claim as "resize *upward* works". Only 1280x1024 has been tested; four unpinned device-vtable
slots.
**Owner:** the resizable-window session. Do not take its lease.

### 3. Road types / tiling rules — one rung from closed, queued behind #2
Verdict already reached: a 7th network is impossible without patching code (closed 6-member enum,
`*6` stride baked into the piece-matrix addressing, 42 predicate vtables flush with no room for a
43rd). Retuning and re-skinning an existing network is possible and partly game-proven. The format
round-trips 68/68 byte-identical.
**Next:** T1, "an edited tiling rule changes the map" — 2 runs, armed and self-contained in
`verify/tilingrules_read_test/README.md` §7 including a Step 0 backup. Blocked only because it needs
a rendered in-city frame, which is `U-068`.
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

1. **`U-068` fix** — 2 to 4 runs. Unblocks #3 and `U-078`.
2. **Road-type T1** — 2 runs. Closes workstream #3.
3. **Bigger-cities `run_diff.ps1`** — 1 run, then gameplay in a 512 city.
4. **Credits discriminator** (`U-051`) — 1 run. Cosmetic closure; `verify/credits_discriminator/`
   `RESULTS.md` is still an unfilled template.
5. **`drag_divisor` / `edge_margin`** (`D-002`) — 1 patched run each.

## Static pool — no lease, runnable in parallel right now

| item | what | state |
|---|---|---|
| ~~`U-076`~~ | ✅ **CLOSED 2026-08-24 at C2.** The premise was wrong: `0xc14f8955` is `GZIID_cISC3Occupant`, an **interface** id, and the catalogue §27c had said so since 2026-08-18 — the uncertainty was filed off a stale label in a second doc. Real factory is `FUN_1000bdcd` in SIMNTWRK, 22 piece classes. `NETWORK_RULE_ENGINE.md` §11. Also closed `U-077`'s class half. | done |
| ~~`U-078`~~ | ⭐⭐ **CLOSED 2026-08-24 at C3, no game run.** `state` is a rigid quarter turn toward increasing `dir` index; **there is no global compass zero** — `state 0` is the identity and absolute facing is per-piece exemplar data, with two authoring zeros in the shipped data. Three independent witnesses, zero counterexamples in 95 + 1,660 + 249 observations. `NETWORK_RULE_ENGINE.md` §13. **The rule-geometry route won; the sprite-render route did not exist** (§13.7). ⚠️ Compass *words* still depend on the §4.1 world-axis convention, which was not re-derived — safe to build a rule editor on the rotation sense, not on the word "clockwise". | done |
| `0x82237425` `+0xb0` | Highest-value lead behind `U-078`: `FUN_1000cd35` calls `vt[0xb0](x,y,z,state,&b0,&b1,&b2,&b3)` — four booleans from a coordinate plus a state, the shape of a per-side connectivity query. Would pin the facing **from code alone**. Declared vtable `0x1002bdcc` is abstract; find the concrete implementor. | **DISPATCHED 2026-08-24**, orchestrator — deliberately isolated from the sprite/rule agent so the two routes stay independent |
| ~~`U-075`~~ | ✅ **SWEPT 2026-08-24.** `+0xb0` closed at C3 — the drive path is **GZ message `0x637c0dab`**, six posters plus one SIMRCI direct call; the UI is not a holder at all. `+0xac`/`+0xf0` have **no cross-module caller in any shipped binary** (C2, measured absence). `NETWORK_RULE_ENGINE.md` §12. | done |
| ~~`U-080`~~ | ✅ **LATENT, not live (C3).** All 42 predicate vtables share slot 0 `FUN_1001a9bb`, which accepts `0xA1C085DB`; 25/25 call sites pass exactly that. ⚠️ **But it turns live for mod authors** who install a slot-0 that rejects it — belongs in published toolkit docs. | done, one doc action |
| ~~`U-079`~~ | ✅ **CLOSED 2026-08-24 at C3, no run spent.** Full `*_Protected.txt` → netType binding in `re/analysis/NETWORK_TYPES.md` §9, three independent cascades agreeing. The 1–2 run differential that `UNCERTAINTIES.md` costed is now **redundant — do not spend it.** Two corrections fell out: the loader reads **22** rule files, not 11 (a second parser `FUN_10019600`), and the refuted order-based guess was the slots' **address order**, which is why it kept looking right. | done |
| `U-077` | Class behind occupant IID `0x41658d28`; label flag bits `0x400`/`0x4000`. Can sit indefinitely. |
| `U-063` | Who calls the RECT zone writer `0x10032afa`. Gates rect-level zone edits. |

## Cross-cutting debt

Ordered by how much damage it can do silently.

1. **`gzseq` target-wait is unreliable and SKIPs silently**, producing a plausible-looking capture.
   Make a missed target abort loudly. This one manufactures false results.
2. **`capture.ps1` does not take the game lease itself.** Until it does, wrap every call in
   `game_lock.ps1 -Acquire -Wait -Owner … / -Release`.
3. **Build→run probe-DLL swap.** `build.ps1` will relink the shared `sc3probe.dll` out from under a
   live session. Either add a per-session `-Out` name or make `build.ps1` refuse without the claim.
   Deferred by decision in `COORDINATION.md`; do it while the harness is quiet.
4. **`STUBS.md` is still an empty template.** `DEFERRED.md` was too until 2026-08-24.
5. **Writing `functions.csv` safely — two rules learned the hard way 2026-08-24.** The file is
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
