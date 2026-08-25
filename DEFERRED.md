# DEFERRED.md — SimCity 3000 RE

Work explicitly out of scope for now. Each row has a re-pickup condition so nothing is
silently dropped.

| ID | item | reason deferred | re-pickup condition | opened |
|----|------|-----------------|---------------------|--------|
| **D-001** | **Standalone proxy-DLL delivery vehicle** (`version.dll` / `winmm.dll` shims to load mod code into SC3U without the RE harness) | **DROPPED, not deferred — owner's call 2026-08-24.** See the rationale below. | **None. Reopening requires arguing against the rationale, not merely preferring the feature.** | 2026-08-24 |
| D-002 | Camera `drag_divisor` (drag4 effect not yet observed in-game) and `edge_margin` (static-only) | **What IS measured (2026-08-25):** static patch byte-verified (`verify/drag_divisor_test/SIMSPR.DLL.drag4`, `--diff` = 2 bytes `fe→fc`); the drag **mechanism** confirmed in a running game by the surgical `dragtest` (direct call to `FUN_10042cfe`+`FUN_10043a38` on the live city view, shipped `-2` → `velX=50.0 velY=20.0` = `(anchor-mouse)/-2`); routing `0x10043daf`→`FUN_10043a38` decompilation-CONFIRMED. **What is NOT measured:** the `-4` arm — no `25.0` has been observed. drag4's halving is **inferred from the two bytes, not observed in a running game.** The faithful OS-input test (`rdrag:` `SendMessage(WM_RBUTTON*)`) was falsified — the pan routing needs real async state (`GetAsyncKeyState` in GZWinD/winmgr), only `SendInput` sets it; the 0px pan was caught by the validity gate. **Cheap close available and missed:** a second `dragtest` after hot-patching `0x43a5e/68` to `0xfc` returns `velX=25.0` — a within-process A/B, independent of the failed transport. `re/sessions/STATUS_camera.md`. | `drag_divisor`: one short dragtest-A/B run to OBSERVE `-4` (`50/20`→`25/10`). `edge_margin`: an instrument + one lease. Fully-faithful "feel" test: `SendInput` + one lease. | 2026-08-24 |
| D-003 | Zoom level 4 reachability in-game | Never established, so the `z4` step slot is untested. Cosmetic. | Only if a user reports the `z4` value having no effect. | 2026-08-24 |

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
