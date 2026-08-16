# Cross-RE: SimCity Deluxe (iOS) as a named sibling of SC3U.exe

## What it is
`SimCity Deluxe` (EA Mobile, 2011) — `IPA\SimCity Deluxe.ipa`. The game logic is the
**SimCity 3000 engine** re-compiled for iOS inside EA's **FusionEngine** mobile wrapper.

- Main binary: `Payload/SimCity DLX.app/SimCity DLX` — fat Mach-O, **armv6 + armv7**, 32-bit.
- Analyzed slice (anchored): `original\SimCity_DLX_armv7`
  - SHA-256 `f3d8ab754e7c8150baee4f19d55b8327de88b4661ec9faace9fb1d7652c86c5b`
  - thin Mach-O, MH_EXECUTE, cputype=ARM sub=9 (armv7), 9,138,336 bytes.
- **Decrypted**: `LC_ENCRYPTION_INFO cryptid=0` → `__TEXT` code is readable (Internet-Archive copy).
- **Not stripped**: ~72k `_ZN…` Itanium-mangled C++ symbols → full class/method names.
- Assets: `data.fez` (76 MB) + `data/sc3strings/*.gvf` (SC3's own advisor/petitioner/sim
  string tables) — shared SC3 data, useful for P2 format work.

## Lineage evidence (why this maps to SC3U)
- Live string: `cSC3ZoneLayer::PlaceBuilding: could not acquire attrib!` (`cSC3` = SimCity 3000 class prefix).
- Bundled `data/sc3strings/sc3strings*.gvf` = SC3's string content.
- Clean `SimCity::` C++ namespace with the exact sim subsystems:
  `goCitySimulator`, `goZoneLayer`, `goZoneDeveloper`, `goBuildingLayer`, `goBuilding`,
  `goOccupant`/`goOccupantManager`, `goPowerLayer`/`goPowerPlant`, `goTrafficLayer`,
  `goTerrainLayer`/`TerrainGenerator`/`TerrainMap`, `goFloraLayer`, `goDemolitionLayer`,
  `Residential`, `PaletteTable`, `Constants` (e.g. `kZoomToPixelShift`), globals
  `g_game`/`g_city`/`g_vocity`.

## What kind of cross-RE this is (and is NOT)
This is a **named semantic sibling**, NOT a byte-identical twin like Mashed's Xbox/PS2 builds.

| Property | Mashed Xbox/PS2 twin | SC3 iOS sibling |
|---|---|---|
| Same source & era | yes | no (2000 PC vs 2011 mobile re-engineer) |
| 1:1 function/address map | yes (xtwin RVA↔VA) | **no** (ARM vs x86, different compiler) |
| Leverage | address-level matcher | **class/method names + algorithm shape + constants** |

**Rules of evidence (inherited from Mashed twins):**
- SC3U.exe is the AUTHORITY. The iOS sibling is a **reading aid / second static witness** only.
- The mobile port may simplify, cut, or restructure systems — never assume a subsystem
  exists or behaves identically without confirming in SC3U.
- A name learned from iOS is a *hypothesis* for the SC3U counterpart until anchored by
  SC3U-side evidence (matching constants, string xref, struct shape, call topology).
  Cite as `[iOS-HINT]` until confirmed `[CONFIRMED @ 0xADDR]` on the SC3U side.

## How to use it (per-subsystem, manual)
1. In `re\ghidra_export_ios\` grep the named subsystem (e.g. `goPowerLayer`, `goZoneDeveloper`).
2. Read the clean, named ARM decompilation to learn the model/algorithm + key constants.
3. Find the SC3U counterpart in `re\ghidra_export\` by shared constants, referenced
   strings (both use the SC3 string ids), data-structure field layout, and call topology.
4. Name/annotate the SC3U `FUN_`; record the iOS class in `functions.csv` notes as provenance.

## Commands
```
pwsh re\scripts\ghidra_headless.ps1 -IOS -Import    # analyze armv7 slice
pwsh re\scripts\ghidra_headless.ps1 -IOS -Export    # -> re\ghidra_export_ios\
pwsh re\scripts\ghidra_headless.ps1 -IOS -Count
```
