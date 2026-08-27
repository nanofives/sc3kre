# SLIDER_DELIVERY.md — shipping the in-game Camera Scroll Speed slider

**Status: SCOPED, NOT BUILT. Needs the owner's go (reopens D-001's value call) + one deferred
validation lease (camera is priority 4).** This is the extraction plan only — no source carved, no
build, no run.

## Why this exists

The `-pref` slider (`re/harness/src/sc3probe.c`, "Camera Scroll Speed" in the game's Preferences
window) works by injection and was labelled "no distributable vehicle." That label was
**proxy-specific** — see the 2026-08-27 scope correction in `DEFERRED.md` D-001. Injection-based
delivery is not foreclosed, so the slider can ship. This doc scopes the lowest-risk vehicle.

## Chosen vehicle: standalone loader EXE + slim mod DLL

Reuse the injector the project already has and proves working, plus a stripped mod DLL that carries
only the slider.

- **Loader:** `re/harness/src/sc3launch.c` already does `CreateProcessA(CREATE_SUSPENDED)` →
  `VirtualAllocEx`/`WriteProcessMemory` → `CreateRemoteThread(LoadLibraryA)` → `ResumeThread`
  (`sc3launch.c:13-44,270-297`), cwd `Apps\`. Repackage it to inject the slim DLL instead of
  `sc3probe.dll`. The user launches this EXE instead of the GOG shortcut.
- **Mod DLL:** carve the `pref_*` block out of `sc3probe.c` into a slim source (~360 lines + a small
  helper set), no capture/fnlog/gzlog/verb machinery.

**Rejected for now:** IAT static-import of `SC3U.exe` (cleaner UX — no separate EXE — but it edits the
anchored game binary and adds an import descriptor, more invasive). Keep as fallback if the owner
dislikes a launcher EXE.

## What to carve into the slim DLL

From `re/harness/src/sc3probe.c` (line ranges from the 2026-08-27 survey; re-confirm before cutting):

- **The 8 slider functions, `~1836-2196`:** `pref_patch_rdata` (`:1917`, `VirtualProtect` + 5 floats
  to `SIMSPR.DLL+0x67690`), `pref_patch_live` (`:1931`), `pref_apply` (`:1948`), `pref_find_window`
  (`:1956`), `pref_add_slider` (`:1968`), `pref_add_label` (`:2074`), `pref_read_slider` (`:2153`),
  `pref_tick` (`:2166`).
- **Helper dependencies:** `gz_winmgr`, `gz_vslot`, `gz_find_by_vtable`, `gz_find_by_id_quiet`,
  `fnlog_install_one`, `logf`.
- **The standalone tick path, `~9088-9113`:** when no `-gzlog` table is present the code installs its
  own single detour at GZGraphicD `0x10018c58` and drives `pref_tick` from `gz_tick_gamethread`
  (`:3180-3183`). Comment at `:9088-9098` says this was written specifically for a standalone ship.
  This is the piece that makes the DLL self-sufficient — keep it.
- **A minimal `DllMain`** that turns the slider on unconditionally and reads `slider.ini` from the
  loader's directory (decision 1), pre-applying the value before the slider is shown — replacing the
  `SC3PROBE_*` env-var gate arm at `sc3probe.c:9049-9060`. Add a small INI read + write-back
  (`GetPrivateProfile*`/`WritePrivateProfile*` or equivalent).

## Hard constraints carried from the harness (do not relearn these)

- ⚠️ **Position-independence.** SIMSPR and GZGraphicD both prefer base `0x10000000` and one gets
  relocated, per run. The `0x10018c58` detour and every address the slider touches must be resolved
  from a live module handle (`GetModuleHandleA`) + offset, never an absolute. An absolute in a cave is
  a latent per-run crash (BOARD standing rule).
- ⚠️ **The `0x10018c58` detour must not collide** with any other hook. In the standalone DLL it is the
  only detour, so this is simpler than in the full probe, but confirm nothing else installs there.
- **The slider applies live via `VirtualProtect` to `SIMSPR.DLL+0x67690`** in memory — it does NOT
  patch the DLL on disk, so it composes with a **stock** install and must re-apply every launch (the
  heartbeat already does this). No `SIMSPR.DLL.shipped` dependency.

## Design decisions — DECIDED 2026-08-27 (owner)

1. **Value persistence: INI beside the loader.** Ship a config file (e.g. `slider.ini`, scroll value)
   that the mod DLL reads on init and pre-applies before the slider is touched, and that the slider
   writes back when moved, so the value survives restarts. The loader already owns a known file
   location (its own directory). Init order: read INI → `pref_apply` the value → slider reflects it.
2. **Target: stock `SIMSPR.DLL`.** The shipped form assumes an **unpatched** `Apps\SIMSPR.DLL` and
   applies the value live at runtime — the slider IS the camera mod, no disk patch involved. It does
   NOT try to layer on a `pe_patch.py` build. (The owner's own dev install stays byte-patched; that is
   separate from the shipped product.)
3. **Scope: scroll speed only** — exactly the `-pref` slider as already built and run live. No
   drag/edge/deadzone sliders in v1; those remain byte-patch-only. Keeps v1 small and matches the code
   that already has a live run behind it.

## Build + validation plan (staged, lease deferred)

1. **Carve** the slim source, keep position-independence. Local. Harness claim required
   (`harness_claim.ps1 -Claim`) — it shares the `re/harness/src` tree and `bin/`.
2. **Build** the slim DLL + repackaged loader (`build.ps1`, add targets). Offline.
3. **Offline gates (no lease):** DLL loads into a suspended-then-resumed SC3U without the rest of the
   probe; `DllMain` runs (beacon); the `0x10018c58` detour installs; `pref_apply` resolves the GZ
   window/vslot by ID/vtable **without** the probe's other state. If any GZ lookup depends on probe
   init that we dropped, fix before spending a lease.
4. **One validation lease (DEFERRED — camera is priority 4, ride a sibling or wait):** on a **stock**
   install, launch via the loader, confirm the slider appears in Preferences, drags, and moves the
   camera live; A/B/A the value (set → observe → restore) so it is a measurement, not a coincidence.
   Pre-register per the common preamble before taking the lease.

## Risks / unknowns

- `[UNCERTAIN]` whether `pref_add_slider`/`pref_find_window` resolve the Preferences window and slot
  purely from GZ-tree lookups, or lean on probe state initialised elsewhere. Resolved by offline gate
  3, cheaply, before any lease.
- `[UNCERTAIN]` why the proxy `DllMain` is skipped under the AppCompat shim (never confirmed, D-001).
  Does not affect this route — injected-DLL `DllMain` demonstrably runs (the `-pref` slider ran) — but
  worth noting the loader must not itself trip the same shim (it does not: `sc3launch` already runs).
- UX cost: the user launches a loader EXE, not the store shortcut. Standard for mod loaders; flag it
  in the ship notes.

## Effort

Extraction is mechanically small (self-contained block per the survey). The cost is the offline
gating and the single deferred lease, not the carving. No new RE is required.
