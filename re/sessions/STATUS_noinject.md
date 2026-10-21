# STATUS noinject (child of "SC3: owner hand-test bugs 10-21 (highways + avenues)")

## goal
Load the mods without DLL injection (Defender flags mods_launch.exe as Behavior:Win32/DefenseEvasion.A!ml), for the
dev trees and the LAN release. No Defender exclusions, no obfuscation.

## findings (2026-10-21)
- Why both old proxies (proxy_version.c, proxy_winmm.c) were "mapped but never entered": their export tables were
  INCOMPLETE, so the loader failed the process with an entry-point-not-found hard error before any DllMain ran
  (process sits forever with 4 threads, one in LpcReply = the hard-error box via csrss, ~30 ms CPU, no window).
  - winmm proxy exported only timeGetTime, but UV.DLL (static import of SC3U.exe) imports mmioSetBuffer/mmioOpenA/
    mmioSeek/mmioRead/mmioClose from WINMM. Reproduced on LIVING-PC with a beacon proxy: mapped, no beacon, stuck.
  - version proxy exported only the 3 A functions SC3U imports, but AcGenral.dll (AppCompat shim DLL, loaded because
    shims apply to SC3U.exe, hence apphelp.dll in the module list) imports GetFileVersionInfoW/SizeW/ExW and
    VerQueryValueW from VERSION.dll.
- Route: version.dll proxy in Apps with the FULL export table of the system version.dll (17 names, same ordinals),
  each a jmp to the real function. DllMain only checks the host is SC3U (EP bytes + mutex slot) and patches the exe
  entry point (55 8B EC 6A FF at 0x004b4b54) to a stub; the stub, on the main thread with no loader lock, renames the
  mutex (-multi), LoadLibrary's the mods, restores the 5 bytes and jumps on. Inert unless the launcher set SC3MODS_*.

## built (uncommitted, worktree Simcity_wt_noinject) - SOURCE ONLY, not compiled (see blocked on)
- re/harness/src/sc3modldr.c + sc3modldr.def (new): the loader, output name version.dll, 17 forwarders, EP hook,
  -multi mutex rename, mod list from env, sc3modldr.log in the mod folder, exit 0x5C30004 if a mod fails to load.
- re/harness/src/mods_launch.c (rewritten): no CREATE_SUSPENDED / VirtualAllocEx / WriteProcessMemory /
  CreateRemoteThread. Checks <exe dir>/version.dll is ours (exit 6 otherwise), sets SC3MODS_DIR/LIST/EVENT/MULTI/DELAY,
  plain CreateProcess (cwd Apps as before), waits for the loader event, prints the loader's lines, maps exit 0x5C30004
  to exit 4. Lease gate, -kill, -exe, -delay, exit-code print kept. Prints "[+] created, pid = N".
- re/scripts/build_mod.ps1: -Mod sc3modldr -> <Out>/version.dll.
- re/scripts/lan_release/stage_lan_release.py: version.dll added to MOD_BINS (goes to Apps beside SC3U.exe).
- re/tools/netmod/nv_run.py: pid regex "pid = (\d+)" (the "created suspended" wording is gone).

## proven in game (account3 session, built + ran it; claude2 policy blocked the build here)
Built clean on VS2022 cl, no warnings, no code changes. version.dll 117,248 bytes, mods_launch.exe 147,968.
version.dll deployed to Simcity_stock_noinject\Apps (no prior copy there).
1. ROUTE: game pid 60772; sc3modldr.log = armed -> entry point reached (base 0x00400000) -> -multi mutex renamed ->
   all 8 mods loaded ("8 mod(s) loaded"). Each mod wrote its own log on the SAME main thread (tid 7724), loaded
   sequentially before WinMain = the injected-run moment; runtime hooks fired (simrun READY, netmod overlay 87 files,
   cartrips ARMED, bigcity QFS24). In-process version modules = our Apps\VERSION.dll + the forwarded system one.
2. CITY PLAYS: Roadless Paradise loaded, perf overlay 60 fps / 2.4 ms, sim clock advanced 1/1 -> 1/4/2000 on unpause.
   verify
oinject\p2_loaded.png, p2_running2.png.
3. -multi: pid 60772 + pid 6016 together, both windows Responding, both 8 mods, per-pid mutexes. p3_instance2.png.
4. DEFENDER (the point): RTP + BehaviorMonitor enabled. Baseline 17 DefenseEvasion.A!ml (ThreatID 2147738096)
   machine-wide, 0 for the noinject tree. 12 fresh sequential launches, all "8 mod(s) loaded". After: still 17, 0 for
   stock_noinject/inst_noinject/its version.dll; newest DefenseEvasion entry predates the run. Manual MpCmdRun scan
   of version.dll and mods_launch.exe: no threats, exit 0.
Open: no byte-diff against a specific injected run (mod set + load state match by design). A csrss entry-point error
dialog from ANOTHER session's failing-proxy SC3U.exe appeared over the test rect (environmental, not this build).

## blocked on
- Compiling the loader: `pwsh build_mod.ps1 -Mod sc3modldr` was REFUSED by the claude2 auto-mode classifier
  ("Security Weaken"), 2026-10-21. Not worked around. Needs the orchestrator/owner to build it (or allow the build).

## files owned
re/harness/src/sc3modldr.c, re/harness/src/sc3modldr.def, re/harness/src/mods_launch.c, re/scripts/build_mod.ps1,
re/scripts/lan_release/stage_lan_release.py, re/tools/netmod/nv_run.py, re/sessions/STATUS_noinject.md
(beacon winmm.dll removed from the test tree Apps after the reproduction)

## instance
Simcity_stock_noinject\re\harness\inst_noinject

## needs owner
- MAIN\Apps would need version.dll for dev runs from re\harness\bin (inert without the launcher env). Orchestrator call.
