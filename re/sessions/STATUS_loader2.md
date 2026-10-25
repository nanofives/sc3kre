# STATUS loader2 - Defender-clean mod loading

Branch `child/loader2` from main `01ebe99`. Worktree `Simcity_wt_loader2`, test tree
`Simcity_stock_loader2`.

## Milestone 1 (options) - DONE 2026-10-25
Investigated the `Program:Win32/Contebrew.A!ml` flag on `Apps\version.dll` (built from
`re/harness/src/sc3modldr.c`). Full write-up: `verify/loader2/RESULTS.md`.

Findings:
- False positive on the loader's *shape*: same unchanged binary was clean 2026-10-21; only the signature
  set moved (1.461.192.0). `!ml` scores the DLL-sideloading-loader fingerprint: proxy version.dll beside
  the exe forwarding all 17 exports + entry-point inline patch (0xE9 JMP into .text) + RWX VirtualProtect
  on host .text + env-var-directed LoadLibrary of a DLL list. (sc3modldr.c lines cited in RESULTS.)
- The game is already a GZCOM plugin host: `cRZCOMDllDirector::Load @0x0048a575` does
  LoadLibrary -> GetProcAddress("GZDllGetGZCOMDirector" @0x004f810c) -> register via cGZCOM
  (@0x0048a920/@0x0048aa95). Data-driven discovery via Maxis.ini `[PlugIn] Directories`
  (@0x00482532/@0x00482aee), `%PluginDirectory%`/`PlugIn\` (@0x00464368), FindFirstFile (@0x0047ffd2).

Options (cheapest first), recommendation = Option 1:
1. **Native GZCOM director** (no proxy/patch/injection) - mods become directors the game loads itself.
   Removes the whole fingerprint. Open item: data-driven vs hardcoded director list (decides exe-change
   cost). RECOMMENDED.
2. Keep env-gated version.dll proxy, drop EP patch + RWX via (2a) piggyback early version-API call,
   (2b) TLS callback, or (2c) delay-thread. Cheapest; proxy shape may still score - must MpCmdRun-verify.
3. Pure `.def`-forwarder version.dll (no code) + Option 1 for loading.
4. mods_launch.exe ASR/reputation is a separate problem (sign / stable hash / launch from Explorer).

## Load-order gate (Option 1 chosen) - BLOCKER found, reported before rewriting
Checked first per orchestrator instruction. A pure GZCOM plugin director loads too late for sc3resize.
- GZGraphicD is NOT a static import (PE parse of SC3U.exe: static imports are UV, GDI32, WINMM, VERSION,
  ADVAPI32, KERNEL32, USER32, IMM32, SHELL32, MSVCP60/IRT/RT, WSOCK32) - it loads dynamically at app init.
- sc3resize must run before GZGraphicD loads: EARLY Ldr-notification patch before GZGraphicD DllMain
  (sc3resize.c:12439-12502), bails to a racing watcher if GZGraphicD already loaded (12543-12547); DPI set
  once before any window (12509). Today guaranteed by version.dll(static)->EP hook->mods before WinMain.
- GZCOM directors load in the user-plugin phase (%PluginDirectory%/PlugIn, FUN_00464368<-00407bec/00408999),
  after core graphics bring-up. No zero-exe-change way to load before GZGraphicD: SimUtil2.dat is opaque
  (not DBPF), SIM core directors are registered in SimInit.dll code.
- Tolerant mods (plugin OK/degraded): sc3perf, sc3netmod, sc3undo, sc3simrun likely OK; sc3bigcity/
  sc3overscroll degraded (poll-race); **sc3resize = hard blocker**.

Recommended pivot: the flag is on the loader SHAPE, not on early loading. Keep the early static-import
load, drop the malware-shaped features. Triage empirically with MpCmdRun on minimal variants (V1
forwarders-only; V2 forwarders+load, no EP patch/no RWX; V3 baseline). Heavy fallback = mod directors in
the core list (SimInit.dll binary edit). AWAITING orchestrator redirection before building.

## Defender triage V1/V2/V3 (RTP-based) - in progress 2026-10-25
- MpCmdRun local scan is BLIND to this detection (scans a known-flagged version.dll as clean) - only RTP/cloud counts.
- Detection = RTP on-access, cloud `Program:Win32/Contebrew.A!ml` (ThreatID 251873), DetectionSourceTypeID=3.
  Mere file ACCESS (the originals were triggered by ls.exe / pwsh.exe / mods_launch.exe) fires it. Keyed to the
  old build's specific hash(es).
- Built V1 (pure forwarder, 86528b), V2 (forwarders + DllMain-load, no EP patch/no RWX, 114688b), V3 (current
  source rebuilt, 117248b, hash 2ACF..). Placed each beside a copy of SC3U.exe and accessed; launched from Apps.
- RESULT so far: NONE of V1/V2/V3 (all fresh hashes) flagged on access/launch. V3 (same shape as the flagged
  build, new hash) NOT flagged => detection is hash/sample-specific, a rebuild alone currently evades it. Caveat:
  SubmitSamplesConsent=1, cloud may re-verdict later; 18-min re-access monitor running (scratch/monitor.txt).
- V2 PRESERVES sc3resize early hooks: sc3modldr.log "GZGraphicD loaded now? no" at each mod load; sc3resize.log
  DPI PER_MONITOR_AWARE_V2 set before any window + "EARLY: loader notification registered (status 0)" (not the
  fallback watcher). Caveat: DllMain-load is slow (~1-3s/mod, likely Defender scanning each new-hash mod DLL on
  load) => ~15-20s startup stall; a lock-free IAT-hook variant would avoid it.
- Correction: real game exe is Apps\SC3U.exe with version.dll beside it in Apps (root SC3U.exe is an identical
  hard-link; launching it loads System32 version.dll). mods_launch mod list has 9 names incl sc3startsize/sc3cartrips.

## Milestone 2 - DONE 2026-10-25 (V2 picked + implemented)
Triage RTP results (MpCmdRun is blind; only RTP/cloud counts): V1/V2/V3 + prod, all fresh hashes, NONE
flagged on access/launch; 18-min/12-cycle monitor = 0 hits. Detection is hash/sample-specific (old build's
bytes); V2's cleaner shape is the durable fix. V2 verified: all 7 mods load before GZGraphicD, sc3resize
EARLY+DPI+STARTRES+FRAME fire, only the benign 0xC0000096 fault. First-load ~24s (Defender scans new-hash
mod DLLs), 125ms cached.

Implemented (worktree child/loader2):
- re/harness/src/sc3modldr.c  -> rewritten: V2 (DllMain-load, NO entry-point patch, NO RWX) + built-in
  mod list from Apps on normal SC3U.exe start (no launcher), SC3U.exe host guard, env overrides
  (SC3MODS_DIR/LIST/MULTI/OFF). Stock = rename version.dll or SC3MODS_OFF=1. sc3modldr.def unchanged.
- re/scripts/lan_release/stage_lan_release.py -> MOD_BINS drops mods_launch.exe; "Jugar SimCity (mods).bat"
  starts Apps\SC3U.exe directly.
- re/harness/src/sc3netmod_avflow.c -> AVF_DEFAULT_AVSTART 0->1 (owner call). Launch log confirmed
  "avflow: avstart on (avenue and boulevard cells)". SC3NETMOD_AVSTART=0 still off.

Workflow change for other sessions: mods_launch.exe is no longer the launch path (ASR-flagged, dropped
from the package). Launch Apps\SC3U.exe directly (built-in load) or with SC3MODS_MULTI=1 for parallel
test instances. CHILD_PROTOCOL launch lines and the mods_launch lease-gate path need updating.

## Files to commit (orchestrator commits by path; no git add/commit here)
- re/harness/src/sc3modldr.c                    (rewritten loader - the Defender fix)
- re/harness/src/sc3netmod_avflow.c             (AVSTART default ON)
- re/scripts/lan_release/stage_lan_release.py   (drop mods_launch.exe, .bat -> SC3U.exe)
- verify/loader2/RESULTS.md                     (full write-up)
- re/sessions/STATUS_loader2.md                 (this file)
Removed (scaffolding, do not commit): re/harness/src/sc3modldr_v1.c, sc3modldr_v2.c (triage only).

## (historical) earlier milestones below
Build chosen candidate; MpCmdRun scan of it + rebuilt mods_launch.exe = no detection; launch test tree
with all 8 mods (8 loaded, city loads, no VEH fault beyond benign 0xC0000096 @ SC3U+0x84122); update
`stage_lan_release.py` MOD_BINS if names change; then flip `sc3netmod` AVSTART default ON + one launch
check logging AVSTART on.

## Files to commit (orchestrator commits by path; no git add/commit here)
- `verify/loader2/RESULTS.md` (new) - Milestone 1 write-up.
- `re/sessions/STATUS_loader2.md` (this file).
(No source changed yet - Milestone 2 waits on the option pick.)
