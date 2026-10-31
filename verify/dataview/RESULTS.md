# dataview: new data views B, A, C, H (owner pick 2026-10-30)

Owner: "Add custom data views of things that are not shown today." Plan `re/analysis/DATAVIEW_PLAN.md`, picks B, A, C, H.
New mod `sc3dataview.dll` (`re/harness/src/sc3dataview.c`). Off: `SC3DATAVIEW=0`. Per item: `SC3DATAVIEW_POLLUTION=0`
(B), `SC3DATAVIEW_TRAFFIC=0` (A, C), `SC3DATAVIEW_HNUM=0` (H), `SC3DATAVIEW_CAPTION=0` (captions). `dataview.ini`
beside the DLL: `[dataview] key=86` (V), `pollution`, `traffic`, `measure`. Saves are never touched.

## What the player gets

| item | where | what |
|---|---|---|
| B radiation | Ver datos > Contaminacion, key V | orange cells where the game marks the ground radioactive |
| A trips | Ver datos > Trafico y transporte, key V (1st) | each lot that made a trip: green = arrived, red = failed |
| C traffic by network | same panel, V (2nd, 3rd, 4th) | congestion on streets only, highways only, subway only, stock palette; stock layer hidden meanwhile |
| H capacity | Ver datos > Cuadros, tabs Educacion and Salud | students vs places for school and college (%), teachers, professors, strike; patients vs hospital capacity (%), doctors, strike |

V cycles the open panel's extra layers and back to stock. A caption at the top of the map names the layer on show
("V: radiacion", "Viajes: verde llega, rojo no (V)", "Congestion en calles (V)" ...). V does nothing outside those two
panels (the key goes to the game as before).

## How (all [CONFIRMED] unless noted)

- One vtable slot: the map view layer interface SIMUI `0x100a7db8 +0x98` (AddLayer `0x1004339b`). When the game adds
  stock layer 0x2731 (pollution panel) or 0x2715 (traffic panel), the extras are added to the same view, hidden.
- **B = layer 0x2735**, built by SIMECO's own factory (`0x1000e0e7`, kind 5) and registered by `0x1000c54a`, but no
  panel adds it. Its colour function `0x1000e4cc` paints (0xff,100,0) where `cISC3PollutionLayer::IsRadioactive`
  (vt+0x54, slot 21, `0x10008db8`) is true: bit 31 of the pollution cell value. The game sets it with SetIsRadioactive
  (slot 37, `0x10008f65`) from SIMDSTR `0x10007815` and SIMUTIL `0x10009295` (radius 10, random fringe to 20).
- **A** reads the traffic layer's trip bits (+0x7c tried, +0x80 ok, SimTransit `0x10006965`). **C** reads the live
  congestion grids +0x6c / +0x70 / +0x74 where the cell's network mask (+0x5c, 0x15 / 2 / 8) has that network.
  Both are our layer objects: SIMECO's layer base (ctor `0x1001853b`, vtable copy of `0x1001cca4`) with our +0x48.
- **H** detours the Cuadros page fill SIMUI `0x100245c7` (tab 6 Educacion, 9 Salud) and adds native labels (GRAPHAXIS
  label recipe) fed from the residential layer, city +0xe4 (vt SIMRCI `0x1004c99c`, fields +0x650..+0x68c).

## Checked in game (dev/dataview/tree, all mods, posted input only, pictures in `owner_shots\`)

| check | city, size | result |
|---|---|---|
| B measured before naming | Craterville 1600x900 | 0 radioactive cells (city has 115 landfill cells, so 0x2735 is not the landfill mask). Owner+0x1c = the city's pollution layer, slot +0x54 = IsRadioactive |
| B drawn (lab switch `SC3DATAVIEW_TEST_RAD=128,128`, 113 cells set with the game's setter) | Craterville 2560x1351 | 140 cells read back (the pollution map is stored in blocks); orange disc; V again hides it. `1_*.png` |
| A trips | Craterville / Berlin 2560x1351 | 7,193 lots with a result, 222 failed / 20,382, 126 failed. `2_viajes*.png` |
| C streets / highways / subway | Craterville, Berlin | Craterville highway 0 cells (none built); Berlin highways 1,558 cells, max 81 of 255, drawn light. `3_*.png` |
| H | Craterville 2560x1351 | school 44,482 / 51,000 (87%), college 20,907 / 15,000 (139%), hospital 12,322 / 6,000 (205%), teachers 1,700, profs 300, doctors 400. Capacities equal staff x 30 / 50 / 15. `4_*.png` |

Captions and numbers are native labels, so DLGSCALE scales them and NATIVETEXT draws them sharp (2.25x checked).

## Not checked / open

- B is only seen with the lab switch: no shipped city has radiation. A real meltdown was not driven.
- A dialog close/reopen cycle and a city reload were not driven (objects are refcounted and pooled for that case).
- The legend box keeps the stock "Ligero / Alto" text; it fits C, not A or B (the caption explains those).
- Lab: `re/tools/dataview_lab.py` (Ver datos, icons 1..12, `NAME:key` posts V). `sc3wait.MODS` now lists sc3landfill
  and sc3dataview.
