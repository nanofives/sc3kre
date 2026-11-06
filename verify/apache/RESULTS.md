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
