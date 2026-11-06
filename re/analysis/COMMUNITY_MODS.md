# Community mods: integration plan (owner decisions 2026-11-06)

Three third-party SC3U packages by thronevintagetech. The owner has the authors' permission (exact wording still
to be filed here). Sources:

- Apache Flyover v0.9 RC1, MIT, full source: https://github.com/thronevintagetech/ApacheModSC3KU/releases/tag/simcity
- Civic Deals + Extra Cheats v1.0 and Classic Natural World v1.0:
  https://github.com/thronevintagetech/SC3KU-Unofficial-Enhancements

All DLLs are plain GZCOM directors (`sc3k-gzcom-dll` SDK: MIT, Apache build vendors an LGPL-2.1 copy). The game's
own Apps scan (`FUN_0040b00f` / `0048a575`) loads them, so they do not need `sc3mods.dll`. None has run beside our
mods yet.

## Redistribution rule

The authors can clear their own code and art, not EA data. Their own work ships as is (Apache DLL + sprites,
`SC3KExtraCheats.dll`, `SC3KCivicDeals.dll`). Files that are EA files with edits (`SYS.PAK`, the 6 petitioner
`.IXF`, `455A72B1_LandPalettes.IXF`, `PALWATER/PALEDGEL/PALEDGED.BMP`) ship as **patchers that apply the change to the
player's own files**, which also lets the Spanish texts keep their language. This follows
`project-sc3kre-publish-policy`.

## Decisions, per feature

### Apache Flyover
| Feature | Decision | Work |
|---|---|---|
| `apache on` 3-minute flyover | Keep the cheat. Add it as a **Reunirse** (petitioner) entry | New petitioner record (Spanish + English). Offered only when the city **has a military base** and **the base relationship holds** (base deal accepted) and **crime is high**. Thresholds to set from SIMADV / crime layer reads |
| `apache patrol` | **Tie to police / military** | Patrol route limited to the area around police stations and the military base instead of a city-wide road bias |
| `apache pilot` (WASD, `[` `]`) | Accept as is | None |
| Visuals | **Fix for our zoom / size mods, then add rotor sound** | Check sprites, shadow and route at cityzoom x2/x3, sc3resize sizes and 1024 maps (sc3bigcity). Then a rotor sound through the game's audio |

### Civic Deals + Extra Cheats
| Feature | Decision | Work |
|---|---|---|
| `forestfill`, `forestthicken` | Keep cheats. Add a **terrain-tool button**, and a **tick in the New City terraformer side panel** | The terraformer side panel likely needs a rework to hold more options (owner: "more customization"). Scope that panel first |
| `clouds on/off` | **Weather toggle on the "Opciones de mods" page** | Clear / Rain switch. Fix the fade quirk so rain stays visible while on. **Built 2026-11-06** (child/terrpanel, `sc3resize_weather.c`): the fade is SIMSPR's 1-in-3 roll at 0x1002b559 plus SIMMISC's season tick sending SetWeather(0); see `verify/terrpanel/RESULTS.md` |
| Back Door Development Deal (D9) and WMT Redevelopment Offer (DA) | Accept as is (cheat `corruptncrazy`, once per run) | **Translate both into Spanish** and install with a patcher that appends D9/DA to the player's own `SYS.PAK` and petitioner `.IXF` (owner's `Res\Text\ENGLISH` holds Spanish) |
| Extra Cheats (Null 45: `dotcom`, `moolah`, `SimDate`, ...) | Accept as is | Ship the original DLL unchanged |

### Classic Natural World
| Feature | Decision | Work |
|---|---|---|
| Terrain palettes (5 themes, height shading, snow caps) | **Switchable**: stock vs Natural World on the mods page (and the terraformer panel) | Redirect the palette loads in `SIMDIRT.DLL` `sc3_dirt_load_palette` (`0x10016cce`) to an alternate set. Alternate set is generated from the player's own files by a patcher |
| Water depth + shoreline | **Same switch as terrain** | One toggle covers all 4 files |

## Terraformer panel scoping (2026-11-06, static read, not yet confirmed in game)

- The panel is entirely in SIMUI.DLL. Window-proc vtable `0x100aaae0` (Linux name `cSC3WinProcTerrEdit`):
  DoWinMsg `0x1005f352`, CreateTerrEditWin `0x1005f44c` (window id `0x72e85997`, size from image 2 of
  `22DEC90F_TerrEdit.ixf` = 172x480, docked at root width - 0xac).
- Controls are built with fixed coordinates in `0x1005f621` (ids `0x72e867a1..b2`: Accept, Re-Generate, zoom,
  rotate, Lower/Raise/Level, Plant Trees/Water/Demolish, 3 sliders 0..255, a features widget, 2 labels).
  The panel uses no checkboxes, but the control manager can create them (`+0x3c` CreateCheckBox).
- Clicks: `0x100607ab`. Re-Generate posts `0x2f2ee63` with the 3 slider values packed (`FUN_10060ab2`). SIMDIRT
  `0x10005500` handles it and resets flora through `cISC3DirtBag::InitFloraLevel` (`0x100064a0`), the per-cell call
  a forest fill would use.
- No hook of ours on this proc yet. sc3resize only docks and scales the panel (`rz_dialogs_poll`, DLGSCALE; it
  recognises the panel by width 172, so **keep the width**). Hook pattern to copy: `ho_prefs_msg` (add controls after
  build message `0xa2bf8ace`, take our own ids first).
- Ways to fit more options: A) a tick in an existing gap (if one exists), B) a taller panel with our own strip,
  C) **a "Mas opciones" button opening a page of options** (same mechanism as the Opciones de mods page, stock layout
  untouched), D) drawn tabs (tight at 172 px), E) scroll area (no precedent, high risk).
- Unknowns: free vertical space (needs one screenshot), which slider controls trees, what "open land" means for the
  fill, whether `InitFloraLevel` is safe before Accept.

## Before any of it

1. File the authors' permission wording in this document.
2. Coexistence run in a dev workspace (`sc3dev.ps1 new community`): startup with our mods, zoom past 4, a 1024 city,
   city switch, `[sc3resize.log]` VEH FAULT lines. Civic Deals only on an English text copy until the patcher exists.
