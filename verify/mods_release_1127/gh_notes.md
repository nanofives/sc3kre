Replaces sc3mods-2026-11-26. Changed: `Apps\sc3netmod.dll` and `Apps\sc3perf.dll`. Nothing was added or removed.

**Big cities no longer crash on load because of an old road file**
- An update installed over an older one could keep `mods\netmod\overlay\Apps\Res\Sprites\CSATTRIB.IXF`. The 2026-11-09 release removed that file, but unzipping never deletes files and `update.bat` deletes them only with `-Prune`. It points one avenue road piece at art that later releases moved, so a city with that piece crashed while loading (`SIMSPR.DLL+0x15B9`).
- sc3netmod now skips any file in `mods\netmod\overlay` that this release did not ship and that replaces a game file, and names it in `Apps\sc3netmod.log` ("ovstale"). You can delete that file, or run `update.bat -Prune` once.
- sc3perf also stops the crash itself: a building or road picture with missing art is left empty instead of closing the game. `SC3PERF_NULLIMG=0` turns this off.

`sc3netmod.dll` and `sc3perf.dll` scan clean on Jotti's malware scan (0 of 13 engines each).

**Install**
1. Unzip into the game folder, the one with `Apps` and `Cities` (`SC3U.exe` is inside `Apps`), replacing the older files.
2. First install only: in PowerShell in the game folder, `powershell -ExecutionPolicy Bypass -File .\sc3mods_patch.ps1`. On Linux or macOS: `sh sc3mods_patch.sh`.
3. Start `Apps\SC3U.exe`.

**Note**
The road and building data in `mods\netmod` is built from the game's own files. You need your own copy of SimCity 3000 Unlimited.
