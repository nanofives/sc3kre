Replaces sc3mods-2026-11-27. Changed: `Apps\sc3perf.dll`. Nothing was added or removed.

**Turned buildings with animations draw whole**
- A building turned with TAB showed patches of another view on the part that holds its animation, such as the Spaceport and the Science Center. The base picture turned and the animated part did not. They now turn together in every camera view, and the animation plays in place.
- Buildings you already placed turned are fixed too. Nothing needs to be placed again.
- The smoke of a turned coal power plant now comes out of its chimneys. Before, it rose where the chimneys of the unturned plant would be.
- The fix covers every building of that kind. I tested the Spaceport, the Science Center and the coal power plant.
- This is a bug of the original game that turning buildings made visible. `animrot=0` in `Apps\perf.ini` turns the fix off.

`sc3perf.dll` scans clean on Jotti's malware scan (0 of 13 engines).

**Install**
1. Unzip into the game folder, the one with `Apps` and `Cities` (`SC3U.exe` is inside `Apps`), replacing the older files.
2. First install only: in PowerShell in the game folder, `powershell -ExecutionPolicy Bypass -File .\sc3mods_patch.ps1`. On Linux or macOS: `sh sc3mods_patch.sh`.
3. Start `Apps\SC3U.exe`.

**Note**
The road and building data in `mods\netmod` is built from the game's own files. You need your own copy of SimCity 3000 Unlimited.
