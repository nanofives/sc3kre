# loader2 - Defender-clean mod loading (Milestone 1: options)

Date 2026-10-25. Branch `child/loader2` from main `01ebe99`. Test tree `Simcity_stock_loader2`
(no `Apps\version.dll`, no mods in `Apps\`). All findings are confirmed decompilation data from
`re/ghidra_export/` (SC3U.exe, anchor 49DD55E1...), cited by RVA.

## 1. The detection is a false positive on the loader's *shape*

- Same binary `Apps\version.dll` (built from `re/harness/src/sc3modldr.c` + `.def`) was Defender-clean
  on 2026-10-21 (memory `project-noinject-loader`). It is unchanged. Only the signature set moved:
  `Program:Win32/Contebrew.A!ml`, signatures 1.461.192.0, detected 2026-10-25 02:15. `!ml` = a
  generic machine-learning heuristic, not an exact signature.
- `Contebrew`/`!ml` scores the **DLL search-order-hijack (sideloading) loader** fingerprint. Our file
  matches that fingerprint feature-for-feature. The individual techniques are each legitimate and
  common in game mods; the ML model scores the *combination*.

### What sc3modldr.c presents to the model (cheapest-to-drop last)

| # | Feature | Where | Malware-signal strength |
|---|---------|-------|------|
| 1 | A module named `version.dll` placed **beside the exe**, forwarding **all 17** real version.dll exports | `sc3modldr.def`; `sc3modldr.c:56-132` | strong (this *is* "sideloading") |
| 2 | **Inline patch of the host entry point**: `g_ep[0]=0xE9; memcpy(g_ep+1,&rel,4)` over `AddressOfEntryPoint` | `sc3modldr.c:245-254, 283-293, 222-243` | strong (self-modifying host .text) |
| 3 | **`PAGE_EXECUTE_READWRITE` VirtualProtect on host .text** | `sc3modldr.c:226, 285` | strong (RWX on another image) |
| 4 | VirtualProtect + write into another spot of the host image (mutex-name pointer) | `sc3modldr.c:187-189` | medium |
| 5 | **Env-var-directed `LoadLibrary` of a DLL list** (`SC3MODS_DIR`/`SC3MODS_LIST`) | `sc3modldr.c:194-212, 265-266` | medium |
| 6 | `TerminateProcess` on failure | `sc3modldr.c:217, 240` | weak |

The mods themselves were never flagged (they loaded fine via injection before 2026-10-21). The flag
is on the **loader shape**, so the fix is to stop presenting that shape.

## 2. The game is already a GZCOM plugin host (confirmed)

SC3U.exe hosts the Maxis/EA **GZCOM** component framework (same as SimCity 4). It loads plugin DLLs
*itself*, through its own documented extension point - no proxy, no patch, no injection needed:

- **`cRZCOMDllDirector::Load` @ `0x0048a575`**: for a director entry it does
  `LoadLibraryA(entry+0xc)` -> `GetProcAddress(hmod, "GZDllGetGZCOMDirector")` (string @ `0x004f810c`)
  -> calls it -> gets a director object -> `director->vtbl[0xc](version, entry+8)` to register.
  `[CONFIRMED @ 0x0048a575]`
- **cGZCOM service manager**: register-from-path `@0x0048a920`, CLSID dispatch `@0x0048aa95`, director
  map at `this+0x4c/+0x58`, keyed by CLSID (e.g. 1000 @ `0x0048aa95`). `[CONFIRMED]`
- **Every shipped game DLL is a director**: `GZDllGetGZCOMDirector` is exported by SC3U.exe, SIMINIT,
  SIMCITY, GZServiceD, ... (grep of `re/ghidra_export*/functions`). The sim modules load through this
  exact path today.
- **Data-driven plugin discovery exists** (invoked virtually through the cGZApp framework, so no direct
  caller shows - consistent with config-driven):
  - reads `Maxis.ini` (`@0x00482aee`; strings "Maxis.ini" `0x004f7f74`, "PlugIn" `0x004f7f68`),
  - a `[PlugIn] Directories` list (`@0x00482532`; "Directories" `0x004f4b78`),
  - path tokens `%PluginDirectory%` `0x004f796c`, `%DataDirectory%` `0x004f7980`, `PlugIn\` `0x004f5210`
    resolved `@0x00464368`,
  - directory enumeration FindFirstFile/FindNextFile `@0x0047ffd2`.
  No `Maxis.ini` and no `PlugIn\` dir ship with the GOG install, so retail builds the director list
  another way (likely a hardcoded table in SIMINIT); the **code path to load extra plugins from a
  file/dir is present and live**. Confirming which source actually drives it is the one open item for
  Option 1 (see below).

## 3. Candidate methods, cheapest first

### Option 1 - Native GZCOM director (no proxy, no patch, no injection). RECOMMENDED.
Repackage each of the 8 mods as a GZCOM director: export `GZDllGetGZCOMDirector` returning a minimal
`cIGZCOMDirector`, and let the **game's own loader** map and register it. The mod's current DllMain
patch work moves into the director's Init/PostAppInit callback (that patching was never the flagged
part). Removes **every** row of the table in section 1 at once - the proxy, the EP patch, the RWX, the
env LoadLibrary all disappear, because the GAME does the loading via its extension API.
- Keeps "stock without launcher": directors self-gate on the `SC3MODS` env (present but inert without
  the launcher) exactly as `version.dll` does today, or are only placed in the modded tree.
- Open item (decides the exe-change cost): is the director list data-driven (`Maxis.ini`
  `[PlugIn] Directories` / a `PlugIn\` scan -> **zero exe change**) or hardcoded in SIMINIT (-> add a
  CLSID+path entry, a small data-table edit to a stock game DLL, far less malware-shaped than an EP
  patch). Resolve in Milestone 2 by tracing the virtual caller of `0x0048a920`/`0x00482532` and testing
  a `Maxis.ini`/`PlugIn\` drop-in.
- Main risk vs "load before WinMain on the main thread": directors load during AppServices init on the
  main thread, early - must confirm it is before the hook points sc3resize/STARTRES need. Validate by
  launch, not by assumption.
- Cost: medium, mechanical, 8 mods. Confidence it clears Defender: high (no sideloading shape left).

### Option 2 - Keep the env-gated version.dll proxy, strip the two strongest signals (EP patch + RWX).
Cheapest to build; **lower** confidence, because the forwarder-proxy-beside-exe shape (row 1) remains.
Replace the entry-point inline patch with a non-patching main-thread rendezvous:
- **2a. Piggyback an early version-API call.** If SC3U.exe calls one of the 3 version functions it
  imports (GetFileVersionInfoSizeA / GetFileVersionInfoA / VerQueryValueA) early, on the main thread,
  before WinMain, our forwarder for that export loads the mods on first call then tail-calls the real
  one. Zero code patching, zero RWX, correct thread + timing. The 3 imported version APIs are thunks
  `0x004842ea/e4/f0` called from 6 sites `0x0047a2a7, 0x0047a389, 0x0047a459, 0x0047a529, 0x0047a858,
  0x0047a96a` (a version-info helper cluster); whether any fires before WinMain on the main thread is
  the gate - confirm in Milestone 2. Removes rows 2,3,4.
- **2b. TLS callback** in the proxy: runs on the main thread during process init, after static DLLs,
  before the exe entry. No .text patch, no RWX. (A TLS callback is itself a weaker ML signal than an EP
  patch.) Removes rows 2,3,4.
- **2c. DllMain -> short-delay worker thread** (already the proven `SC3MODS_DELAY` path): no patch, no
  RWX, but loses main-thread-before-WinMain ordering.
Must be MpCmdRun-verified after building - the proxy shape may still score.

### Option 3 - Pure `.def`-forwarder version.dll (DATA forwards to `C:\Windows\System32\version.<name>`),
paired with Option 1 for loading. The proxy then has **no** DllMain logic, no LoadLibrary, no patch -
indistinguishable from a legit redirector - it only satisfies the import so the game runs; the mods
load natively (Option 1). Isolates the proxy from the loading.

### Option 4 - mods_launch.exe is a *separate* problem (ASR, not the ML DLL flag).
A freshly built `mods_launch.exe` (new hash, no reputation) started from cmd is blocked by the ASR
"ransomware" rule. No exclusion-free fix is fully in our hands: owner-sign the binary, ship a stable
prebuilt so its hash accrues reputation, or start it from Explorer/a shortcut instead of cmd. Owner
decision; track apart from the loader.

## Recommendation
Pursue **Option 1** (native GZCOM director) as the real fix - it is the only candidate that removes the
whole fingerprint with high confidence and uses the game's own mechanism. If registration turns out to
need a heavy SIMINIT edit, fall back to **Option 2a** (piggyback early version-API call) as a cheap,
scan-verified stopgap. Both keep the launcher/.bat flow and a stock game when launched directly.

## 4. Load-order gate (orchestrator pick = Option 1) - BLOCKER for sc3resize

Checked first, as instructed, before rewriting any mod. Result: **a pure GZCOM plugin director loads
too late for sc3resize, which is a hard blocker.**

Confirmed facts:
- **GZGraphicD is NOT a static import of SC3U.exe** - it is loaded dynamically during app init.
  PE import-table parse of `original/SC3U.exe`: the only static imports are UV.dll, GDI32, WINMM,
  **VERSION.dll**, ADVAPI32, KERNEL32, USER32, IMM32, SHELL32, MSVCP60, MSVCIRT, MSVCRT, WSOCK32.
  (version.dll static = today's hook; GZGraphicD/SIMSPR/SIMUI/SIMCITY are all GZCOM modules loaded
  later.)
- **sc3resize must run before GZGraphicD loads.** Its EARLY path registers `LdrRegisterDllNotification`
  to patch GZGraphicD's window style / windowed / 16-bit / STARTRES bytes *before GZGraphicD's DllMain*
  (`sc3resize.c:12439-12502`). If GZGraphicD is already loaded when sc3resize starts, it bails to a
  racing 100 ms watcher (`sc3resize.c:12543-12547`). DPI-awareness is set once in sc3resize DllMain,
  "before the game creates any window" (`sc3resize.c:12509`). All of this needs sc3resize loaded
  **before GZGraphicD**.
- **Today that is guaranteed**: version.dll (static import) -> EP hook -> all 8 mods LoadLibrary'd after
  static-DLL init but before CRT/WinMain, hence before GZGraphicD's dynamic load.
- **GZCOM directors load in the app's plugin phase**, not before graphics bring-up. SimInit.dll is a
  director (`GZDllGetGZCOMDirector @0x1001fe55` returns the SimInit director); the user-plugin loader
  `%PluginDirectory%`/`PlugIn\` (`FUN_00464368` <- `FUN_00407bec`, `FUN_00408999`) is the user-plugin
  stage, after the core graphics service (GZGraphicD) is up.
- **No clean zero-exe-change way to load a director before GZGraphicD.** The only data-driven
  registration (`%PluginDirectory%`/`Maxis.ini [PlugIn]`) is the *late* phase. The core module list
  that loads GZGraphicD early is not editable data: `Apps\SimUtil2.dat` is an opaque/encrypted format
  (header `cb 1c 02 f1 ...`, not DBPF), and the SIM core directors are registered in SimInit.dll code.

### Per-mod timing need
| mod | needs pre-GZGraphicD / pre-WinMain? | as a plugin director |
|-----|-----|-----|
| **sc3resize** | **YES** (EARLY frame/windowed/surfacefmt/STARTRES + DPI once before any window) | **breaks** |
| sc3bigcity, sc3overscroll | wants it, but uses 1 ms polling watchers that race GZGraphicD Init | degraded (may miss the window) |
| sc3simrun | patches 1 SIMSPR byte, poll-tolerant | likely OK |
| sc3perf, sc3netmod, sc3undo | patch sim modules that load later | likely OK |

### Consequence
Option 1 as a **pure** GZCOM plugin cannot keep sc3resize's behaviour. The Defender flag is on the
loader *shape*, not on loading early - so the fix that preserves timing is to keep the **early
(static-import) load** but drop the malware-shaped features (EP inline-patch + RWX-on-.text, env-list
LoadLibrary), not to move loading to the late plugin phase.

### Recommended pivot (decision for orchestrator/owner)
Empirically triage which feature trips the ML model by building minimal loader variants and scanning
each with `MpCmdRun -Scan -ScanType 3 -DisableRemediation` (cheap, decisive, no rewrite of the 8 mods):
- V1 forwarders-only `.def`, no DllMain loader logic (pure redirector) - is the proxy shape alone flagged?
- V2 forwarders + load mods, but NO entry-point patch and NO RWX-on-exe (load under a controlled early
  point) - removes the two strongest signals while keeping before-WinMain timing.
- V3 current sc3modldr (baseline).
Keep whichever first variant scans clean. Only if none clears the ML model do we take the heavy path
(mod directors inserted into the core module list, which needs a SimInit.dll binary edit).

Note: the EP hook exists precisely because it runs after `LdrpInitializeProcess` (loader lock released),
on the main thread, before CRT/WinMain (`sc3modldr.c:22-29`). DllMain/TLS alternatives reintroduce the
loader lock; a worker thread loses the before-WinMain guarantee. V2's exact early point needs care -
part of the triage.

## 5. Triage V1/V2/V3 - RESULTS (done 2026-10-25, RTP-based)

### How the detection actually fires (measured, this changes the test)
- **MpCmdRun local scan is blind to it.** `MpCmdRun -Scan -ScanType 3` reports a *known-flagged*
  version.dll as "no threats". So an on-demand scan proves nothing; only real-time + cloud counts.
- **It is RTP on-access, cloud-delivered** (`Get-MpThreatDetection`: `DetectionSourceTypeID=3`,
  `Program:Win32/Contebrew.A!ml`, ThreatID 251873). The original hits were triggered by `ls.exe`,
  `pwsh.exe`, `mods_launch.exe` merely *accessing* the file - so the valid test is: place the variant
  beside a copy of SC3U.exe, access it (and launch the game), then read `Get-MpThreatDetection`.
- Config: `MAPSReporting=2`, `SubmitSamplesConsent=1`, `CloudBlockLevel=0`, RTP on.

### Variants and verdicts
Built with the project toolchain; placed beside a copy of SC3U.exe; accessed; launched from `Apps\`.
| variant | shape | hash | flagged (RTP on-access/launch)? |
|---|---|---|---|
| **V3** control = current source rebuilt | EP patch + RWX + env-LoadLibrary (the flagged shape) | 2ACF.. | **No** |
| **V1** pure forwarder, no loader code | proxy only | 9CAD.. | **No** |
| **V2** forwarders + DllMain-load, no EP patch, no RWX | cleanest loader | AA42.. | **No** |
| **prod** V2 + built-in list (shipped) | cleanest loader | F2F1.. | **No** |

- **Control answer:** V3 (same shape as the flagged build, fresh compile) is **not flagged**. So the
  current detection is **hash/sample-specific** - the old build's exact bytes - and any rebuild evades
  it right now. An 18-minute monitor (12 cycles, repeated access of all four fresh hashes) logged **0**
  new detections and all files survived. Caveat: `SubmitSamplesConsent=1`, so a new sample could be
  re-verdicted by the cloud later; adopting the **cleaner V2 shape** (not just a rebuild) is the durable
  choice because it removes the features the ML model scores.

### V2 timing + function (the load-order gate from section 4, now satisfied)
From the logs of a full launch (all 7 mods, Berlin, built-in path):
- `sc3modldr.log`: every mod loads with **`GZGraphicD loaded now? no`**, then `7 mod(s) loaded`.
- `sc3resize.log`: **DPI `PER_MONITOR_AWARE_V2` set before any window**, `EARLY: loader notification
  registered (status 0)` (the real early path, not the fallback watcher), then on GZGraphicD load
  `--- EARLY: GZGraphicD mapped ... patching before its DllMain`, `STARTRES> ... starts at 800x600`,
  `FRAME: ... WS_THICKFRAME|WS_MAXIMIZEBOX`.
- Only fault: the **benign `0xC0000096 @ SC3U.exe+0x84122`**. No access violation.
- Load cost: ~24 s on the *first* load of freshly-built mod DLLs (Defender scans each new hash as it
  loads), **125 ms** once cached. Affects any loader equally; release DLLs gain reputation. Owner should
  expect one slow first launch per build.

## 6. Shipped fix

`re/harness/src/sc3modldr.c` rewritten to the **V2 mechanism + a built-in mod list**:
- No entry-point patch, no `PAGE_EXECUTE_READWRITE`, no `ep_hook`, no `TerminateProcess`.
- Mods LoadLibrary'd from `DllMain` (process init, before CRT/WinMain, before GZGraphicD).
- Built-in default list loaded from this DLL's own folder (`Apps`) on a normal `SC3U.exe` start, so
  **no launcher is needed**. Guarded to the `SC3U.exe` host (Baapp.exe stays a pure forwarder).
- Env overrides for the harness: `SC3MODS_DIR`/`SC3MODS_LIST` (custom), `SC3MODS_MULTI=1`
  (per-pid mutex rename for parallel test instances - the only remaining memory write, a single DWORD
  in `.data`, env-gated), `SC3MODS_OFF=1` (quick stock).
- **Stock = rename/remove `version.dll`, or `SC3MODS_OFF=1`.**
- `-multi` / `SC3_PID` for tests: set `SC3MODS_MULTI=1` and start `SC3U.exe` (a dev .bat), replacing
  `mods_launch.exe` (which is also ASR-flagged and is no longer shipped).

`re/scripts/lan_release/stage_lan_release.py`: `MOD_BINS` drops `mods_launch.exe`; the generated
`Jugar SimCity (mods).bat` now starts `Apps\SC3U.exe` directly (the loader loads the mods).

`re/harness/src/sc3netmod_avflow.c`: `AVF_DEFAULT_AVSTART 0 -> 1` (owner call). Confirmed in a launch:
`avflow: avstart on (avenue and boulevard cells)`. `SC3NETMOD_AVSTART=0` still turns it off.

### Workflow note for other sessions
`mods_launch.exe` is no longer the launch path. Dev/test launches should start `Apps\SC3U.exe`
directly (built-in load) or with `SC3MODS_MULTI=1` for parallel instances. `CHILD_PROTOCOL` launch
lines that call `mods_launch.exe` need updating; the lease gate that was compiled into `mods_launch`
is no longer in the launch path.
