Replaces sc3mods-2026-11-21. Changed: `Apps\sc3bigcity.dll`, `Apps\sc3resize.dll`, `Apps\sc3simrun.dll`, the text tables in `Apps\sc3lang`, and the building style data in `mods\netmod`. New: `mods\netmod\overlay\Apps\Res\Sprites\2627D60E_netpack_set.DAT`. Nothing was removed, so unzipping over 2026-11-21 is fine.

**Power and water reach across 512 and 1024 cities**
- On a 512 or 1024 map, a power line stopped carrying power about 600 tiles from its plant, and a water pipe stopped carrying water about 500 tiles from its tower or pump. A second plant past that point powered its own patch and never joined the first. Power and water now reach the whole map.
- Cities of 256 tiles and smaller work as before. `SC3BIGCITY_GRIDCAP=0` turns the fix off.

**Zoned buildings on lots that are not square**
- Buildings made with the building importer on 1x2, 2x3 and 3x4 lots now grow by themselves in the zones, like the game's own buildings. Square buildings grow as before.
- Mods page row "Non-square zoned buildings" on the Turn mods on/off page (on). It needs the row "Non-square buildings" on as well.

**Lawns that match the city**
- A European or Asian house grown in a North American city brought its own dark lawn and vegetable plots, so a street of them read as another neighbourhood. These houses keep their buildings, but their lawn now takes the colour of the same building's North American lawn, and most garden plots become lawn where the North American version has none.
- North American houses grown in a European or Asian city get the darker European and Asian lawn the same way.
- The game's own buildings and styles are not changed.

`sc3bigcity.dll`, `sc3resize.dll` and `sc3simrun.dll` scan clean on Jotti's malware scan (0 of 13 engines each).

**Install**
1. Unzip into the game folder, the one with `Apps` and `Cities` (`SC3U.exe` is inside `Apps`), replacing the older files.
2. First install only: in PowerShell in the game folder, `powershell -ExecutionPolicy Bypass -File .\sc3mods_patch.ps1`. On Linux or macOS: `sh sc3mods_patch.sh`.
3. Start `Apps\SC3U.exe`.

**Note**
The road and building data in `mods\netmod` is built from the game's own files. You need your own copy of SimCity 3000 Unlimited.
