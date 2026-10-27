# RESULTS - import-descriptor mod loader (child/importldr, 2026-10-27)

Replaces the `version.dll` proxy loader (`sc3modldr.c`) that Defender flagged twice as
`Program:Win32/Contebrew.A!ml` (ThreatID 251873): 2026-10-25 (`verify/loader2/RESULTS.md`) and again
2026-10-27 on the shipped `sc3mods-2026-10-27` `version.dll` (SHA A5448995..., quarantined on MARIANO-PC and
LIVING-PC). The loader source had not changed since 5e603c6 (10-25), so a rebuild alone only moves the hash
until the model re-flags the shape. The flagged shape: a DLL named like a system DLL, beside the exe,
forwarding all 17 `version.dll` exports, `LoadLibrary`ing a mod list from `DllMain`.

## What changed

The mods now load through a **normal PE import** instead of a system-DLL-named proxy.

1. **`re/harness/src/sc3mods.c` + `sc3mods.def` -> `sc3mods.dll`** (new). Own name, no export forwarders. It
   exports one trivial `sc3mods_version()` so the exe import has a symbol to reference, plus the `sc3mods_id`
   marker string. `DllMain` does what `sc3modldr.c` did: built-in default mod list from its own folder,
   `SC3MODS_OFF` / `SC3MODS_DIR` / `SC3MODS_LIST` / `SC3MODS_MULTI` overrides, `-multi` mutex rename, logs to
   `sc3mods.log`. No exe patching at run time, no `VirtualProtect` on `.text`, no entry-point hook.
2. **`re/scripts/sc3mods_patch.ps1`** (new). A text PowerShell script the player runs on their own install. It
   adds one import descriptor for `sc3mods.dll` to `Apps\SC3U.exe`. Windows then maps `sc3mods.dll` as a static
   import during process init, before the CRT, WinMain and the dynamic load of GZGraphicD, which is the window
   `sc3resize`'s EARLY hooks need. We never ship a modified game exe (publish policy): the patch is applied per
   PC. Guarantees:
   - checks the input SHA-256 is the anchor `49DD55E1...349DC7` (or already patched), refuses otherwise;
   - backs up to `SC3U.exe.orig` (a real copy), `-Restore` puts it back, idempotent (detects its own `.sc3mod`
     section);
   - writes a NEW file and renames, never patches in place (dev trees hard-link the exe, confirmed below);
   - method: a new `.sc3mod` section holds a copy of the import descriptor array plus the new one, then it
     updates `DataDirectory[IMPORT]`, `SizeOfImage`, `NumberOfSections`, clears the bound-import directory, and
     recomputes the PE checksum;
   - removes a leftover `Apps\version.dll` only if it carries our `sc3modldr`/`sc3mods` marker.
3. **`re/scripts/build_mod.ps1`**: `-Mod sc3mods` target (was `sc3modldr -> version.dll`).
4. **Packaging** (`stage_lan_release.py`, `sc3_update.ps1`): the server hosts the STOCK exe (anchor), seeded so
   the updater never overwrites a locally patched copy; `MOD_BINS` ships `sc3mods.dll`; `sc3mods_patch.ps1`
   ships in the install; `sc3_update.ps1` removes an old `version.dll` loader and runs the patcher on each PC.

## Proof

Target: a fresh hard-linked tree `Simcity_stock_importldr` (link_tree of the live install), mods built into
`re/harness/inst_importldr`, `sc3mods.dll` + the patched `SC3U.exe` in its `Apps`.

### Patch is correct (pefile)

`sc3mods_patch.ps1` on a copy of the anchor exe produced a file pefile parses with **no warnings**:
- 13 original import descriptors preserved, `sc3mods.dll` added importing `sc3mods_version`;
- new `.sc3mod` section RVA `0x11B000`, chars `0xC0000040` (init data, read, write - the loader fills our IAT);
- `DATA_DIRECTORY[IMPORT]` -> `0x11B000` size `0x12C`, bound-import directory cleared;
- `SizeOfImage` `0x11B000 -> 0x11C000`, `NumberOfSections` `5 -> 6`;
- PE checksum recomputed, `pe.verify_checksum() == True` (stored `0x11cb5f` == generated).
- Patched exe SHA-256 (deterministic): `E5B6330C46E3A3C80769EB8172D21EFE339D8FC626D7364A60F924CCD5727BE2`.

### In-place safety (hard links)

`Move-Item -Force` over a hard-linked file breaks the link: in a controlled test `a.bin` stayed `ORIGINAL`
while `b.bin` became `PATCHED`, and `a.bin`'s link list dropped to one. Patching the test tree's `SC3U.exe`
(a 59-way hard link shared with `main` and every other tree) left it as a single-link file; `main\Apps\SC3U.exe`
and all other trees were untouched. `SC3U.exe.orig` is created with `File.Copy`, so the backup is independent.

### Game runs (patched exe, direct start)

Launched `Apps\SC3U.exe` directly with Frankfurt, `SC3MODS_DIR` = the instance folder, `SC3MODS_MULTI=1`,
windowed. `sc3mods.log`:

```
[+] -multi: mutex renamed to "SimCity 3000 Mutex 11260"
mod-load start from ...\inst_importldr (static import, process init, tid 3720, GZGraphicD loaded now? no)
[+] loaded sc3resize.dll ... sc3bigcity ... sc3overscroll ... sc3simrun ... sc3perf ... sc3netmod ... sc3undo
[+] 7 mod(s) loaded
```

All 7 mods load on the game's **main thread** during process init, **before GZGraphicD** - the same moment
the old static-import `version.dll` gave. `sc3resize.log` confirms the early path is intact:
`SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` before any window, `EARLY: loader notification
registered (status 0x00000000)` (not the fallback watcher), only the known-benign `0xC0000096 @ SC3U+0x84122`
fault. The city rendered: FRAMEDUMP `fd_001.bmp` is a full Frankfurt (Pob 480,675, 10/13/2054) with the UI,
minimap and the `sc3perf` overlay (57 fps / 9.6 ms/frame). Pictures: `importldr_frame.png` (mid-load),
`importldr_frame2.png` (loaded). sc3io window grabs came back white, the documented DWM/monitor capture
artifact on this shared PC (`project-dwm16-mitigation-root-cause`, `project-test-display-environment`), not a
loader fault - the FRAMEDUMP (in-process surface) renders.

### -multi

Two instances (Frankfurt pid 11260, Berlin pid 3996), both alive together, each `7 mod(s) loaded`, each with
its own per-pid mutex (`SimCity 3000 Mutex 11260` / `... 3996`).

### Restore

`sc3mods_patch.ps1 -Restore` on the tree returned `SC3U.exe` to the exact anchor
(`49DD55E1...349DC7`) and removed the backup. Idempotent re-run of the patch on an already-patched exe is a
no-op (`section .sc3mod present`).

### Defender

Real-time protection, BehaviorMonitor and OnAccessProtection all **On**, signature `1.461.224.0` (newer than
the `1.461.192.0` that first flagged). `Get-MpThreatDetection` across the build, both launches and the dump
run: **no detection on `sc3mods.dll` or the `importldr` tree**. Every `Contebrew.A!ml` (251873) hit is on
`version.dll` (latest 2026-10-27 08:42 on `Simcity_release`); every `DefenseEvasion` (2147738096) hit is on
the retired `mods_launch.exe`. No Defender exclusions were added, no quarantine items restored.

**Caveat, stated plainly:** a clean run is necessary but does not prove the ML will never flag `sc3mods.dll`
later. The 2026-10-27 `version.dll` detection fired hours after a clean launch check. What changed structurally
is that `sc3mods.dll` no longer presents the sideloading shape (system-DLL name, full export forwarding, beside
the exe); it is an ordinary named import. MpCmdRun on-demand scans are blind to this cloud detection, so only
real-time protection plus actually starting the game counts, and that is what was tested.

### AppCompat shims

The `DWM8And16BitMitigation` layer is registered in `AppCompatFlags\Layers` (HKCU + HKLM) keyed by the
exe's **absolute path**, not by file attributes. Patching changes the exe's size and checksum but not its path,
so a path-keyed Layers entry still applies. SDB shims that match on file SIZE/CHECKSUM/BIN_FILE_VERSION are the
theoretical exception, but the layer that matters on this machine is path-keyed and therefore unaffected.

## Files

New (loader source, force-add like `sc3modldr.c`):
- `re/harness/src/sc3mods.c`
- `re/harness/src/sc3mods.def`

New (tracked normally):
- `re/scripts/sc3mods_patch.ps1`
- `verify/importldr/RESULTS.md`

New (force-add, `/re/*` deny-by-default like the other session files):
- `re/sessions/STATUS_importldr.md`

Changed:
- `re/scripts/build_mod.ps1`
- `re/scripts/lan_release/stage_lan_release.py`
- `re/scripts/lan_release/sc3_update.ps1`

Not committed (gitignored harness binaries): `sc3mods.dll` and the patched exe are built/applied per machine.
