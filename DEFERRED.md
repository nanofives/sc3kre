# DEFERRED.md — SimCity 3000 RE

Work explicitly out of scope for now. Each row has a re-pickup condition so nothing is
silently dropped.

| ID | item | reason deferred | re-pickup condition | opened |
|----|------|-----------------|---------------------|--------|
| **D-001** | **Standalone proxy-DLL delivery vehicle** (`version.dll` / `winmm.dll` shims to load mod code into SC3U without the RE harness) | **DROPPED, not deferred — owner's call 2026-08-24.** See the rationale below. | **Proxy route: none.** ⚠️ **Scope corrected 2026-08-27: the foreclosure is PROXY-SPECIFIC, it does NOT foreclose injection-based delivery.** A standalone loader EXE and an IAT static-import were never evaluated. See the correction note + `re/analysis/SLIDER_DELIVERY.md`. Building either is still the owner's value call. | 2026-08-24 |
| D-002 | Camera `drag_divisor` + `edge_margin` + `drag_deadzone` — all RESOLVED at C3; only the OS-input "feel" leg remains (now known ENVIRONMENT-blocked) | ✅ **Both OBSERVED in a running game — 2026-08-25**, each via a transport-independent within-process A/B/A (direct call to the pure computation, hot-patch, call again, restore). **`drag_divisor`:** velX `50.0→25.0→50.0` across `-2/-4/-2`, live bytes `FE→FC→FE` (`dragtest` calls `FUN_10042cfe`+`FUN_10043a38`; velY=0 at `-4` is the confirmed deadzone `(0-40)/-4=10 < 12` `[CONFIRMED @ 0x10043a38]`, X is the clean witness). **`edge_margin`:** trigger band `48/64→24/32→48/64` (`edgetest` calls `FUN_10043989` `[CONFIRMED @ 0x10043989]`, reads the 8 rect displacements). Both also static byte-verified. A third knob, **`drag_deadzone`**, joined at C3 on 2026-08-25 the same way (`setdead:N` + `dragtest:mx,my`, engage flip velX `0→8→0` across dead zone `12→4→12`); staged live. **The OS-input "feel" leg is now known to be blocked by the ENVIRONMENT, not the transport:** the faithful `rdrag:` `SendMessage(WM_RBUTTON*)` moved 0px (2026-08-25), AND a new `rinput:` `SendInput` instrument (OS-level, sets `GetAsyncKeyState` state) **ALSO moved 0px on a clean negative control** (idle drift `(0,0)`, gesture Δ `(0,0)`). A first `SendInput` run showed movement but its idle control read `(176,128)` (churn) and was correctly voided — the `(0,0)`-control run is dispositive. So "only SendInput would drive it" is **falsified in this harness**: the capture runs headless (frame rebuilt from the blit mirror, no real display), so the game window is not a true foreground/focused window and injected input is not delivered. `[UNCERTAIN]` whether SendInput arms the pan on a real display — untestable headless. `re/sessions/STATUS_camerafeel.md`. | The OS-input "feel" needs a run against a REAL foreground window on a REAL display (not the headless capture harness); the `rinput:` instrument is already built. | 2026-08-24 |
| D-003 | Zoom level 4 reachability in-game | Never established, so the `z4` step slot is untested. Cosmetic. | Only if a user reports the `z4` value having no effect. | 2026-08-24 |
| **D-004** | **Device-side resize validation — does the DirectDraw PRIMARY need a SetMode / surface re-create on a real on-display window resize** | **ENVIRONMENT-blocked (real display required), not technique-blocked — established statically 2026-08-26.** The capture harness reconstructs frames from the game's blit stream into the raster **composite**, reading the render-target (`iso+0x74`) directly through its GZGraphicD-raster vtable — it never observes the DirectDraw **primary/front buffer** or the Flip/present, which are downstream. So a primary re-create leaves **no signature the headless harness can see**, by construction. Confirmed adjacent facts: a real `WM_SIZE` routes to GZGraphicD `vt+0x30` = `FUN_100185f5`, which only stores the client rect (`vt+0x28`=`FUN_10016b90`, a pure rect setter — no surface work) `[CONFIRMED @ 0x10016b90]`; SetMode `FUN_10015e3d` is **startup-only** — an exhaustive `.text` sweep found its sole reaching function is the device bring-up routine `FUN_100114b8`, and even the fullscreen↔windowed toggle `FUN_10011f73` recreates surfaces via interface slot `+0x50`, not SetMode `[CONFIRMED @ 0x100114b8, 0x10011f73]`. So the stock resize recreates nothing; a *modded* resizable window that needed surfaces recreated would hook the toggle's slot-`+0x50` path — but **whether it needs them recreated at all can only be observed on a real foreground display**. ⭐ **PARTIALLY ANSWERED — OPTIMISTIC BRANCH, 2026-08-26 real-display hand-test:** the owner dragged/maximised the style-flipped window on a real display and got **NO black viewport and NO crash** (no `C0000005`, no exception in the log) — the iso view clipped/locked top-left but the DirectDraw windowed path **survived** a real client resize. So the primary does **not** need re-creating for a windowed resize (the pre-registered device-surface-failure and crash outcomes did not occur). This is the real-display observation the headless harness could never produce, and it **de-risks the bridge** (the render-target resize + `FUN_10018cdf` refill should suffice; no primary/SetMode/`+0x50` surgery needed). Remaining under D-004: only whether a *downward/extreme* resize or a fullscreen-toggle-then-resize stresses the primary. | A run against a REAL foreground window on a REAL display (same blocker family as D-002). The iso-side minimal routine (render-target resize + `FUN_10018cdf` refill + present) is already de-risked by the harness's own resize path; the device/primary leg is the untestable-headless part. | 2026-08-26 |

## D-001 — why the proxy-DLL vehicle is closed

**The feature it was meant to enable already ships without it.** `re/tools/pe_patch.py` writes
SHA-anchored, `--expect`-guarded, length-preserving patches to `Apps\SIMSPR.DLL`, and the game loads
the patched module off disk with **no injection at all**. That path is validated game-side
(`verify/scroll_patch_test/RESULTS.md`, S1/S2/S3). The proxy would have added runtime
configurability — an INI `[Camera]` section, and a distributable form of the working `-pref`
Preferences slider — on top of a mechanism that already works.

**What was established before dropping it** (so nobody re-runs it):

- `version.dll` and `winmm.dll` proxies are both **mapped into SC3U from the game directory**, and
  the import binding is correct: measured under `cdb`, `WINMM!timeGetTime` resolves into our module
  and the system `winmm` is not loaded.
- **Neither proxy's `DllMain` nor its exports are ever entered.** Two independent fixed-path beacons
  confirm our code is genuinely never reached.
- AppCompat shims are active: `Apps\SC3U.exe` carries the **`DWM8And16BitMitigation`** layer in
  `HKCU\...\AppCompatFlags\Layers`, which is why `apphelp.dll` is in the module list, and is the
  standing suspect for the non-entry.

**Why the two remaining diagnoses were not worth their cost.** Deleting the `DWM8And16BitMitigation`
value is non-elevated but mutates state shared by the whole install, and it sits on exactly the
graphics path that `U-020` (is observed behaviour SC3U or SC3U-plus-shim?) and `U-068` are open on —
so it would invalidate the resizable-window baseline mid-investigation. `gflags /i SC3U.exe +sls` is
worse on the same axis: elevated, global, persistent.

**Consequence on record:** the `-pref` in-game slider works but has no distributable vehicle, so
camera mods ship as a patched DLL. Documented in
[`re/analysis/formats/CAMERA_MODDING.md`](re/analysis/formats/CAMERA_MODDING.md). The proxy sources
(`re/harness/src/proxy_version.c`, `proxy_winmm.c`, `version.def`, `winmm.def`) stay on disk in the
gitignored harness tree as the record of the attempt; `build.ps1` no longer builds them.

### ⚠️ Scope correction — 2026-08-27: the foreclosure is proxy-specific, not "no distributable vehicle"

The consequence line above ("the `-pref` slider works but has no distributable vehicle") **overstates
D-001**. D-001 killed exactly one delivery flavor: the **proxy DLL** that substitutes for a system
DLL. It does **not** foreclose injection-based delivery, and the sentence conflated "the RE harness is
a dev tool" with "no shippable loader can exist." Evidence:

- **Injection provably works in this exact environment, and it is not the proxy path.**
  `re/harness/src/sc3launch.c` is a launcher-injector: `CreateProcessA(CREATE_SUSPENDED)` →
  `VirtualAllocEx`/`WriteProcessMemory` → `CreateRemoteThread(LoadLibraryA)` → `ResumeThread`
  (`sc3launch.c:13-44,270-297`). The `-pref` slider itself ran live through this path, **under the
  same `DWM8And16BitMitigation` shim that skips the proxy's `DllMain`.** So an injected DLL's
  `DllMain` runs; only the system-DLL-substitution `DllMain` was skipped.
- **The blocker is proxy-scoped and its cause is `[UNCERTAIN]`** — every D-001 sentence is about
  `version.dll`/`winmm.dll` non-entry, and the decisive tests (HKCU-delete, `gflags +sls`) were never
  run. Nothing in D-001 concerns `CreateRemoteThread` or a loader-resolved import of a mod DLL.
- **Vehicles never evaluated or rejected anywhere in the repo:** a standalone loader EXE (ship the
  `sc3launch`-style injector + a slim mod DLL — the slider was already written for a standalone ship,
  `sc3probe.c:9088-9098`); an **IAT static-import** added to `SC3U.exe`; a TLS/entry-point hook;
  AppInit_DLLs.

**What is corrected vs what still stands.** Corrected: "no way to ship the slider." Still standing:
the owner's *value* call that the static byte patch already delivers the scroll knob and the live UI
is optional. Building a shippable slider is scoped in `re/analysis/SLIDER_DELIVERY.md` and is not
started — it needs the owner's go, plus one deferred validation lease (camera is priority 4).
