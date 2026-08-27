# PROMPTS.md — ready-to-paste session briefs, one per mod

Paste one of these into a fresh session to pick up that workstream. Each is self-contained.
**State is current as of 2026-08-27.** If a session tells you something here is stale, believe the
session over this file — but make it prove it, and then fix this file.

---

## COMMON PREAMBLE — paste this at the top of ANY of the briefs below

> You are working on the SimCity 3000 RE project (`C:\Users\maria\Desktop\Proyectos\Simcity`).
> Read `CLAUDE.md` and `BOARD.md` first. `BOARD.md` is the live board; read the standing SIMSPR/
> GZGraphicD rule and the cross-cutting debt section before touching anything.
>
> **Rules of engagement, non-negotiable:**
> - **NO-GUESSING.** Cite `[CONFIRMED @ 0xADDR]` for every constant, offset and call site. Otherwise
>   `[UNCERTAIN]` plus exactly what evidence is missing. Never "probably" or "seems".
> - **A confirmed code path is not a confirmed cause.** This project lost two leases to a message
>   verified to clear a pause bit that was **already clear at load**. Before declaring X responsible
>   for symptom Y, measure that X is what is actually happening.
> - **Pre-register outcomes before every game run, and `git add` + commit the `PRE.md` BEFORE taking
>   the lease** (`.gitignore` whitelists `verify/*/PRE.md`). A pre-registration written beside the
>   result proves nothing. Include what a *plausible but wrong* success looks like.
> - **Instruments must fail loudly.** Four failure classes are on the board: silent instruments,
>   nondiagnostic proxies (a save-size delta the *paused control* also showed), an unreset counter
>   that printed a false `HEADLINE REFUTED`, and a swallowed error (`| Out-Null`). Every abort path
>   names itself.
> - **Re-derive every byte count yourself.** Do not adopt one from the orchestrator; one was asserted
>   as 16 bytes when the answer was 9.
>
> **Hazards that have already bitten:**
> - The harness `Grep` tool **cannot see** `re/ghidra_export*/` and reports that as "0 matches". Pass a
>   module's `functions/` directory explicitly or walk the filesystem. **And the export itself can be
>   incomplete** — clean decompiled text is not evidence of absence; exhaustive negatives about call
>   sites need an instruction-level scan over `.text`.
> - **`functions.csv` is keyed on `(module, rva)`, never `rva` alone** — 9.9% of rows collide.
> - **Game runs are serial.** `pwsh re/harness/game_lock.ps1 -Acquire -Wait -Owner <name>`.
>   `capture.ps1` **self-acquires** — never wrap it in an outer acquire, that has deadlocked a session.
>   Keep `-AtSec` under ~800 s. Never kill a process you did not start.
> - **Harness build lock:** `pwsh re/scripts/harness_claim.ps1 -Claim -Owner <name>` before touching
>   `re/harness/src/sc3probe.c`. Hunk-merge, never file-replace. `re/harness/` is gitignored.
> - ⚠️ **A shipped code cave and the harness's `-gzlog` fnlog detour CANNOT share a hook address** —
>   two hooks on one address corrupt the function and **the game hangs** with no crash and no error.
>   Hook past the fnlog entry detour.
> - ⚠️ **`SIMSPR.DLL` and `GZGraphicD.dll` both prefer base `0x10000000` and collide, so one is
>   relocated — and which one varies per run.** Any code cave must be **position-independent**
>   (`call $+5 / pop reg`, then everything `[reg+offset]`). An absolute address in a cave is a latent
>   crash. This already shipped once and had to be hardened.
>
> ⚠️ **THE OWNER'S LIVE INSTALL IS DELIBERATELY MODIFIED.** Restore shipped modules for any
> measurement, and **re-stage the owner's standing build as your final action** — read the exact gated
> command from `BOARD.md`, do not reconstruct it. One-line restore of everything:
> ```powershell
> Copy-Item Apps\SIMSPR.DLL.shipped Apps\SIMSPR.DLL -Force; Copy-Item Apps\GZGraphicD.dll.shipped Apps\GZGraphicD.dll -Force
> ```

---

## 1. CAMERA — essentially DONE, only optional work left

> You own the **camera** workstream. Read `re/analysis/formats/CAMERA_MODDING.md` and
> `re/sessions/STATUS_camera.md`.
>
> **Shipped and live in the owner's install:** `scroll_speed=8` (arrow keys + edge-scroll),
> `drag_divisor=4` and `drag_deadzone=2` (right-drag). All three measured in-game at C3.
>
> **The mechanism, so you do not re-derive it:** drag velocity is `(anchor - mouse) / -N`
> `[CONFIRMED @ 0x10043a38]`, and the dead zone is a **per-axis box tested AFTER the divide**, not a
> radius. Consequences: **engage distance = `deadzone × divisor`**, and diagonal movement is narrow
> because each axis must clear the dead zone independently. **Raising `drag_divisor` to slow the pan
> also doubles the engage distance** — that caused a real complaint once.
>
> **Open, all optional:**
> 1. `edge_margin` is **C3-observed but NOT staged** (band `48/64→24/32→48/64`). One command if wanted.
> 2. `D-002` — proving a *real mouse drag* feels different. **ENVIRONMENT-BLOCKED**: both
>    `SendMessage` and `SendInput` move the camera **0 px** in this harness because there is no real
>    foreground window. **Do not rebuild that instrument expecting a different answer.** The `rinput`
>    verb exists but is **disarmed** (needs `SC3PROBE_RINPUT=1`, verifies foreground, saves/restores
>    the cursor). Only a real-display run can close this.
> 3. `D-003` — zoom-4 reachability. A read, not an experiment. Ride it along on another run.
>
> **The reusable technique this workstream produced:** a **transport-independent within-process
> A/B/A** — you cannot synthesise a real drag, so call the computation directly and hot-patch the
> constant between calls: measure at shipped, patch, measure, restore, measure again. The
> return-to-baseline third leg is what makes it a measurement rather than a coincidence. Harness verbs
> `dragtest`/`setdiv`, `edgetest`/`setedge`, `setdead`.

---

## 2. NEW ROAD TYPES / TILING RULES — T1 and T2 met; T3 open

> You own the **road types / network tiling rules** workstream. Read
> `re/analysis/formats/TILINGRULES_MODDING.md`, `re/analysis/NETWORK_TYPES.md`,
> `re/analysis/NETWORK_RULE_ENGINE.md` and `re/sessions/STATUS_roadtypes.md`.
>
> **Settled — do not re-litigate:** a **7th network type is impossible** without patching code (closed
> 6-member enum, `*6` stride baked into piece-matrix addressing, 42 predicate vtables flush). What
> works is **re-skinning and re-tuning an existing network**.
>
> **T1 met** (destructive): a 7-byte `ROAD_GRND_Set.txt` made every road tile vanish while rail drew
> normally. **T2 met** (constructive): a **2-line SimpleRules edit** re-skinned a freshly-drawn
> straight to the curve piece — predicted `11203`, measured `11203 ×11`.
>
> ⚠️ **The lever is `SimpleRules` (fixpoint, FIRST), NOT `final.txt` (last).** Editing `final` gives a
> **byte-identical save** — it only resolves what earlier passes leave open. `final` is named like the
> answer and is the wrong file. Also: a drawn tile bakes its piece id into the save, so an edit +
> reload changes nothing; you must **draw a road after loading**.
>
> **Tool built here:** `re/tools/network_layer.py` decodes the SIMNTWRK network save layer
> (`0x2147c2dd`) to per-tile `(x,y,pieceId,state)` — a camera- and pixel-independent oracle. **It is a
> READER.**
>
> **Open work, in value order:**
> 1. ⭐ **A network-layer WRITER**, extending `network_layer.py`. This is the single highest-value item
>    on the whole board: it **unblocks bigger-cities development** (planting connected road offline).
> 2. **T3 — a simulation-level tiling test.** Every result so far is **render-path only, no simulation
>    claim**. The unpause primitive now exists (`msg:0xc2a35d80`), so traffic/growth effects along a
>    network are finally testable. **Keep the render-path fence until such a test actually runs** — an
>    unpause capability is not a simulation result.
> 3. **Scope "what a new road type can mean"** honestly in the modding doc.
> 4. `compass labelling` — low priority, static, 4 of 8 conventions remain.

---

## 3. BIGGER CITIES (N > 256) — 512 works; development is the frontier

> You own the **bigger cities** workstream. Read `re/analysis/formats/BIGGER_CITIES.md` and
> `re/sessions/STATUS_bigcities.md`.
>
> **Two patches, both required:** `re/tools/patch_citysize.py` (SIMUI dialog) and
> `patch_dirtbuf.py` (SIMDIRT vertex-buffer overrun). **The SIZE group alone is the entire fix** —
> config C survived 6/6, shipped 0/6. Both have `--check` and `--restore`, **neither has `--selftest`**.
>
> **Proven at 512:** the engine reads, renders and re-serialises tiles to coordinate 495 with **no
> coordinate-dependent failure**; **in-game authoring works** (a tool drag wrote and saved 151 zone
> tiles at world x 441..460, no clamp to 255, no wrap); the saved file round-trips L0–L4.
>
> ⭐ **The sim UNPAUSES and runs at 512** — post GZ message **`0xc2a35d80`** (probe verb
> `msg:0xc2a35d80,0,0,0`) → `FUN_10002fa6` → `vt+0x210` = `FUN_10005773`, decrementing suspend-depth
> `+0x140` and resuming the clock. Game-verified: `+0x140` 1→0, cursor 2415021→2415022→2415024.
>
> ⚠️ **`0x231e2493` is INERT and is a documented dead end.** It clears `+0x38`, which is **already 0 at
> load** — measured under both Post and Send. It looks exactly like an unpause in the decompilation.
> Quartet: `7e` suspend cmd / `7f` suspended notify / `80` resume cmd / `81` resumed notify.
>
> **Development is the frontier, and it is gated on ONE thing: authoring CONNECTED SERVICE.** A
> residential tile's develop check early-returns in order on demand (`0xd`), radioactivity (`0xa`),
> **power (`0xe`)**, **transport (`0x10`)**, land-value band (`0xb`/`0xc`) and an eligible family
> (`0xf`/`0x12`) `[CONFIRMED @ SIMRCI 0x10028f12, iOS goResZoneDeveloper::UpdateCell 0x0026e7c8]`.
> So a null result is multiply-confounded and **none of those causes are 512-specific**.
> `city_write.py` writes **zones only**. Unblock paths: a **network-layer writer** (the roadtypes
> session has a validated reader) or an **anchored screen→world map** so drags can target coordinates.
>
> **Design the development run with a PAUSED CONTROL on the same served zones**, or "it grew" cannot
> be separated from "service alone did it". Pin the tick count and speed before firing.
>
> **Also open:** a bound above 512 (never tried). Stride/corner measurement is **deferred as cosmetic**.

---

## 4. RESIZABLE WINDOW — three pieces ship; the bridge is the last one

> You own the **resizable window** workstream. Read `re/sessions/STATUS_resize.md` in full — it is a
> complete handoff — then `BOARD.md` section 2 and `re/analysis/LAUNCH_CONTROL.md` §31.12.
>
> **Already shipped and live:**
> 1. **`resize_rectfix`** (SIMSPR code cave) — Init whole-range-erases the present-rect list at
>    `iso+0x4d0` and nothing refills it, so the per-frame present `FUN_1000e058` iterates **zero
>    rects**. The cave replays the ctor's `push_back {0,0,w,h}` via `FUN_10010586`. Witnessed off disk.
> 2. **`resizable_frame`** (GZGraphicD, 3 bytes) — adds `WS_THICKFRAME|WS_MAXIMIZEBOX`. Confirmed at
>    runtime: `style=0x80CF0000`. **No snap-back** — `SetWindowPos` is a mode-apply method, not a
>    WM_SIZE refit.
> 3. **`close_button_quit`** (GZGraphicD cave) — the shipped WndProc **swallows `WM_CLOSE`**
>    (`param_2 == 0x10 → return 0`) `[CONFIRMED @ 0x10017e2f]`. The cave resolves `PostQuitMessage` via
>    `LoadLibraryA`+`GetProcAddress` and calls it, fail-closed on NULL. **`DestroyWindow` alone is
>    UNSAFE** — the main loop (`GZWIN FUN_10020971`) is a PeekMessage loop exiting only on `WM_QUIT`
>    or `0x700`, with **no window-alive check**, so it would orphan the process.
>
> **What is left — the bridge. The renderer has NO resize entry point; only the constructor ever
> sized the view.** Four steps:
> 1. **Re-create the render target** — `iso+0x74` is a GZGraphicD raster; vtable `+0x0c` =
>    `FUN_10009efb`. Clear the `+0x08` created-guard, reconstruct the format tuple from the live
>    raster's own fields.
> 2. **Refill grid B via `FUN_10018cdf`** — the bridge whole-map fill. **This is the render lever**,
>    proven by a run where suppressing it blacked the view *regardless* of everything else. It is
>    **not** `FUN_1000fa36` and **not** the tile cache — both were tried and refuted.
> 3. **Push a present rect** — already shipping as #1 above.
> 4. **Do it on the render thread.** `WM_SIZE` arrives on the message-pump thread. The `WM_SIZE` cave
>    reads the new size from `lParam` (no `GetClientRect` needed — SIMSPR imports only `SetCursor` and
>    `LoadCursorFromFileA` from user32 and **cannot see the window**) and sets a pending flag; a
>    per-frame SIMSPR cave does the work.
>
> **The pointer problem is SOLVED:** hook `FUN_10016eba` **past the fnlog entry detour, at
> `0x10016ec4`** (entry collides with the harness and hangs the game), stash the bridge pointer into a
> `.data` slot position-independently. **One stash yields both pointers — `bridge+0x18` IS the iso
> view**, asserted at `sc3probe.c:5742`. Witnessed: same valid pointer, survives a resize, **exactly
> one iso view exists**.
>
> **Status of the two remaining pieces:** the `WM_SIZE` cave and the deferred per-frame resize routine.
> Build each position-independent, witness each before wiring the next.
>
> **Known-good / known-bad:** rasterisation post-resize is **proven good** (1,310,342/1,310,720 px) —
> do not look there. The display list is **proven good** — do not look there. A real-display hand test
> showed maximize works, the city stays **clipped top-left**, and there is **no black viewport and no
> crash** — evidence the DirectDraw primary does **not** need re-creating (`D-004`). If it turns out it
> does, the hook point is device slot **`+0x50`** (the fullscreen↔windowed recreate path), **not**
> `SetMode`, which is startup-only.
>
> **Also open:** the **HUD does not reflow** — root-caused at `[CONFIRMED @ 0x100270e5]`, three
> hardcoded tables with **no branch above width 800**, so every resolution ≥ 801 gets the 1024x768
> layout. Fix specified (add a `width >= 0x500` branch + a registered layout resource), not built.
> Independently shippable and probably the easier win. And **`U-069`**: downward resize has **never
> been exercised at all**.

---

## 5. SMALLER SHIPPED MODS — for reference

- **Tunables** — `syspak_mod.py`, any `SYS.PAK` INI value. `formats/SYSPAK.md`.
- **Sprites** — `sprite_patch.py`, PNG import + RGB565 quantizer, validated game-side.
  Residual: `-filetrace` is blind to `Apps\Res\Sprites\`, so sprite runs have no file-access gate.
- **City saves** — `city_write.py`, zone raster per tile. Residual: the **name-collision load crash**
  needs writing up for users.
