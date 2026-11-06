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

## Step 4: the flyover as a Reunirse petition 0xDB (this commit)

Static read (worker, 2026-11-06), from the Civic Deals DLL (MinGW, symbols kept) and SIMADV:
- Queue: SIMADV `FUN_100208ac(mgr, id, 0, 1, 0, 120)` thiscall, not a vtable slot, mgr = city vt+0x1b4. Returns 0 if
  the id was ever queued in this process (so one offer per game session).
- Answer: SIMADV `0x1002096a` PetitionerButtonPressed(mgr, id, button) 1 = button 1, 2 = button 2. Texts:
  `0x10021b7c` GetPetitionerStructureFromID(mgr, id, rec), cIGZString* at rec+0x10..0x28 (name, title, message,
  button 1, button 2, reaction 1, reaction 2). Civic Deals swaps the manager's vptr to reach these; we detour both
  functions at their prologue instead (7 and 5 bytes, checked), so the two plugins chain whichever loads first.
- 0xDB: free id; SIMADV's stock switch sends it to a no-op case. PetitionerExtraInfo `19,2` = portrait 19, advisor
  slot 2 (as D7 / D9). `NumberOfPetitionerMessages` is read by nothing (no string match in the exe or any DLL).
- Conditions: military base = BuildingLayer vt+0x60(0x2AFA) > 0 (the base lot is placed only after the mayor accepts
  petition 0xCD, so a base means the deal was accepted); crime = CrimeLayer()->GetAverageValue() > 40 with population
  > 10000 (Public Safety advisor's HIGH_CRIME_LEVEL=40, SIMADV 0x100145ef). Checked every 15 s while a city is open
  and no flight is running. Accept = the "apache on" cheat path (3-minute flyover); reject = nothing.
- Text: Spanish when `sc3mods.dll` `sc3mods_lang()` says "es", else English. The DLL sets name, title, message,
  buttons, reactions; `re/tools/apache_patch.py` adds the SYS.PAK line and the six IXF records (list heading, impact
  analysis, buttons, reactions) to the player's files and copies the DLL + the author's sprites.
- MSVC: the SDK's overloaded virtuals (cIGZString::FromChar) are called by slot, since MSVC orders overloads
  differently from the GCC the SDK was written for.

| check (Craterville, `APACHE_PETITION_FORCE=1` because its crime is 15) | result |
|---|---|
| hooks | `PETITION_HOOKS_IN`; `PETITION_CHECK base 4 crime 15 pop 208780` |
| queue | `PETITION_QUEUED`; Reunirse lists "Patrulla aérea de la base militar" |
| open | "Operación Cielo Seguro", "Coronel Vidal, base militar", message and both buttons in Spanish |
| Autorizar la patrulla | reaction in Spanish, `PETITION_ACCEPTED`, `START_TIMED`, formation flies |

Not checked: the unforced path in a city with crime > 40, the reject button, English / other folders, together with
Civic Deals in one tree. [UNCERTAIN] the frame rate fell to 3-7 fps during this run (120 in earlier runs) from the
queue onward; not traced (the machine was shared, and nothing of ours runs per frame there).

## Frame rate check (A/B, Craterville, sim running, 100 s each, sc3perf CSV t = 70..150 s)

| run | median fps | min fps |
|---|---|---|
| A: no Apache DLL | 102.3 | 21.0 |
| B: Apache DLL, petition hooks in and petition queued | 118.7 | 108.7 |

The 3-7 fps seen in step 4 was with the Reunirse window open: the stock per-glyph slowdown of that dialog
(`project-dialog-overlay-scale` in memory), not the petition code.

## Step 5: rotor sound (this commit)

- The game's own loop: AUDIO.INI [Actor] `131="VehicleHelicopter"`, `sfx\vehicles\helilp.xa`. Static read (worker):
  vehicles push their sound to AUDIO, AUDIO never scans for them. cISC3App vt+0x34 GetBoxX -> cIBoxX vt+0x14
  `Event(n, actorId, handle, a, b)` = AUDIO 0x10008d77: 6 kSfxSpecial2 (altitude), 3 kSfxUpdate (x, z in cells * 256,
  every 10th move tick in STRTSIM 0x10018750), 4 kSfxKill. One loop per actor id; the handle is only compared.
- Plugin: every 100 ms of `Paint`, Special2 + Update with the lead aircraft (handle 0x739A61B0); Kill in `Stop`.
- AUDIO's own gating stays: only the two closest zooms (mgr+0x9bc > 3), surface view, on screen, more than 99/256 of a
  step above ground; volume = ambience volume (mgr+0x2c) - (5 - zoom) * VehicleAttenuation 300. A game helicopter that
  holds actor 131 first keeps it until it lets go (one loop per id).
- `re/tools/apache_heliaudio.py`: Frida read of actor 131 (tracked handle, current volume, position, height).

| check (Craterville, `apache on` then `apache pilot` to hover, closest zoom, camera on the aircraft) | result |
|---|---|
| updates reach AUDIO | actor 131 position follows the lead aircraft (x, z = POS * 256), height above ground 3072 |
| off screen | volume 0, not tracked (AUDIO's on-screen test) |
| on screen, hovering | `tracked 0x739a61b0` (ours), volume 1024 (full ambience volume) |
| flight ends (3 min, `STOP_OK`) | Kill: volume 0, not tracked |

Not checked by ear (no listener at the PC). Not checked: two flights in one session, a game helicopter competing for
actor 131, zoom 3 volume (1024 - 300 = 724 by the formula).
