# STATUS importldr - mod loader as a PE import, not a system-DLL proxy

Branch `child/importldr` from `main` `a593a05`. Worktree `Simcity_wt_importldr`, test tree
`Simcity_stock_importldr`, instance `inst_importldr`. Owner decision 2026-10-27 (parent orchestrator): replace
the `version.dll` proxy loader with a structural fix that does not look like DLL sideloading. Do NOT publish a
release, push, or touch the LAN server - the owner decides that after review.

## Done
Replaced the `version.dll` proxy (`sc3modldr.c`, flagged `Program:Win32/Contebrew.A!ml` on 10-25 and again on
10-27) with:
- `sc3mods.dll` (`sc3mods.c` + `.def`): own name, no forwarders, exports `sc3mods_version` + `sc3mods_id`
  marker. `DllMain` loads the mods (same env overrides, `-multi`, log) with no run-time exe patching.
- `sc3mods_patch.ps1`: adds a `sc3mods.dll` import descriptor to the player's own `SC3U.exe` (new `.sc3mod`
  section, `DataDirectory[IMPORT]`/`SizeOfImage`/section-count updated, bound-import cleared, PE checksum
  recomputed). Anchor SHA check, `SC3U.exe.orig` backup, `-Restore`, idempotent, writes-new-and-renames so
  hard-linked trees are safe, removes an old ours-`version.dll`.
- `build_mod.ps1`: `-Mod sc3mods`.
- Packaging: server hosts the stock exe (seeded); `sc3mods.dll` + `sc3mods_patch.ps1` ship; `sc3_update.ps1`
  removes the old `version.dll` and runs the patcher per PC.

Full evidence (hashes, logs, pefile parse, Defender history, pictures): `verify/importldr/RESULTS.md`.

Proven: patched exe starts directly, 7 mods load on the main thread before GZGraphicD, Frankfurt plays (perf
overlay 57 fps), `-multi` runs two instances, `-Restore` returns the exact anchor. Defender RTP on, no
detection on `sc3mods.dll` across build + 2 launches + dump. Caveat recorded: a clean run does not prove the ML
will never re-flag, but the sideloading shape is gone.

## Files to commit (orchestrator commits by path)
Force-add (`/re/*` deny-by-default; `sc3modldr.c` was force-added the same way):
- `re/harness/src/sc3mods.c`
- `re/harness/src/sc3mods.def`
- `re/sessions/STATUS_importldr.md`

Normal add:
- `re/scripts/sc3mods_patch.ps1`
- `verify/importldr/RESULTS.md`
- `re/scripts/build_mod.ps1`                     (changed)
- `re/scripts/lan_release/stage_lan_release.py`  (changed)
- `re/scripts/lan_release/sc3_update.ps1`        (changed)

`sc3mods.c`/`.def` are our own loader code (publishable as a tool, like `sc3modldr.c`). No game assets, no
decompiled output. Not committed: `sc3mods.dll` and the patched exe (built/applied per machine).

## What the owner must do on MARIANO-PC to get the game running
The current install's `Apps\version.dll` is quarantined, so the game fails `0xc0000906`. Options:
1. Quick: delete/restore-nothing of `version.dll`, start the game - it runs STOCK (no mods), since `SC3U.exe`
   still imports the system `VERSION.dll`.
2. Mods via the new loader (needs a build + patch; run on account3 if claude2's classifier refuses the build as
   it did for the noinject loader in Oct):
   - build `sc3mods.dll` into `MAIN\Apps` (`build_mod.ps1 -Mod sc3mods`),
   - run `sc3mods_patch.ps1 -Apps MAIN\Apps` (it backs up to `SC3U.exe.orig`, removes the ours-`version.dll`),
   - start `SC3U.exe` normally.
   Stock again: `sc3mods_patch.ps1 -Restore` or `SC3MODS_OFF=1`.
Do NOT add a Defender exclusion or restore the quarantined `version.dll`.

## Open risks
- ML re-flag of `sc3mods.dll` cannot be ruled out from a single clean run (see caveat above).
- The LAN/GitHub release and the build of `sc3mods.dll` on MARIANO-PC are the owner's call. If claude2 refuses
  the build, hand it to account3 (do not work around the classifier).
- Test tree `Simcity_stock_importldr` left in place (hard-linked, no extra disk); delete when done.
