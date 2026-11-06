# APACHE: Apache Flyover v0.9 RC1 beside our mods (child/apache, 2026-11-06)

Owner decisions (re/analysis/COMMUNITY_MODS.md): keep the cheat and add a Reunirse entry (military base + base deal +
high crime), patrol tied to police / military, pilot as is, fix for our zoom / size mods, then a rotor sound.

## Step 1: source in the repo, MSVC build (this commit)

- The author's source (MIT; the vendored sc3k-gzcom-dll SDK is LGPL-2.1, kept with its notices) is in
  `re/community/apache/` (Source/, LICENSE.txt, README.txt). Sprites (.DAT/.IXF/.SII) are the author's art, not EA's.
- `re/community/apache/build_msvc.cmd` builds `out/SC3KUApacheFlyover.dll` with the VS2022 BuildTools already used for
  the mods (no Zig on this PC): `cl /std:c++20 /O2 /EHsc /MT /LD /DNOMINMAX` (windows.h min/max broke std::min/max).
  179,200 bytes, exports `GZDllGetGZCOMDirector`, imports only USER32 + KERNEL32. MSVC also gives the game's own C++
  ABI for the SDK's virtual interfaces.

## In game (dev/apache tree, Craterville 256, 800x600, FRAMEDUMP, posted input)

| check | author's DLL | our MSVC build |
|---|---|---|
| loads beside all 11 mods, `INIT` logged | yes | yes |
| `apache on` / `apache patrol` | 3 helicopters + shadows in formation over the city, ticker messages | same |
| patrol route | `ROAD_COUNT_EMPTY: city circuit fallback` every 7 s | same |

Findings that the next steps fix:
- **Road route never used**: `ZoneLayer()->GetRoadCount(begin, end)` returns 0 on Craterville (dense roads), so patrol
  always flies the fixed 8-point circuit. [UNCERTAIN] whether the SDK slot is wrong or the method counts something else.
- **Big maps**: `Paint` returns false (and the mod stops with `DRAW_FAILED`) when the city is over 256 cells, so no Apache
  on sc3bigcity 512 / 1024 maps.
- **Zoom**: `altitudeShift > 4` stops it too; cityzoom x2 / x3 not yet checked against that field.

## Step 2: big maps and zoom (this commit)

Changes in `Source/Apache/ApacheDirector.cpp` (marked `sc3kre`):
- City size limit 256 -> 1024 (`Paint`). Nothing else in the file depends on 256: positions are cells * 256 in
  int32, the ground read checks the map's own +0x14 / +0x18 size against CellCountX / Z.
- `PAINT_SIZE_REJECTED` / `PAINT_VIEW_REJECTED alt .. tile .. hor .. rot ..` in the log instead of a silent stop.
- `POS x z of w` every 5 s (lead aircraft cell), used to aim the camera in tests.

| check (Europolis 1024, sc3bigcity, 800x600) | result |
|---|---|
| `apache patrol`, `apache on` | no `DRAW_FAILED`, no rejection; formation drawn (`owner_shots/1_apache_1024.png`, zoom 3 and zoom 4) |
| zoom 1 -> 4 while flying | no rejection logged at any level |
| cityzoom x2 / x3 | not reached at 800x600 (the + button past zoom 4 left the view unchanged); [UNCERTAIN] at a bigger window |

Minimap -> cell mapping measured on the 1024 map, rotation 0, 800x600: centre (718,513) = cell (492,492), one pixel
right = (-7.95, +7.9) cells, one pixel down = (+7.94, +7.94).

## Step 3: patrol on roads, between the military base and the police stations (this commit)

- **Why the route never used roads**: `cISC3ZoneLayer::GetRoadCount` (SIMRCI 0x100331a1, slot +0x70, correct) counts
  road occupants in the one-cell strip BESIDE a straight row / column segment and returns 0 when begin and end differ
  on both x and z [static read]. The mod passed a square, so 0 always. `Roads()` now counts road cells one by one:
  `SurfaceOccupantManager()->GetOccupantAtCell(x,z)` + `IsGeomFlag(0x8000)` (the Roads network bit).
- **Posts** (owner: patrol tied to police / military): at each `apache patrol` a cell scan collects Military Base 11002
  (one per 12 cells, the lot is large) and PoliceStation 13130 / SmallPoliceStation 13120 (one per 4 cells), ids from
  CitySim.ini. The base goes first. At each road junction the choice gets +2 per cell of progress toward the current
  post. Reached = within 16 cells; skipped = no new best distance for 25 s. No posts: the old road patrol.

| check (Craterville 256, `apache patrol`) | result |
|---|---|
| route start | `ROAD_PATROL_FOUND` (was `ROAD_COUNT_EMPTY` every 7 s) |
| posts | `PATROL_POSTS military 1 police 8`, positions logged (first build said military 9: dedupe was 4 cells) |
| 6 min | 13 road turns; base `SKIPPED` at 32 cells (no road nearer to the lot's first scanned cell), police station 1 `REACHED` at 10 cells |

Known: the author's cruise speed (about 1.1 cells/s) makes a 100-cell leg take 1.5 min, so a full round of 9 posts takes
several minutes. Not changed. Post position = first scanned cell of the building, not its centre.
