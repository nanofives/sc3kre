# MODULE_MAP.md — the sim does NOT live in SC3U.exe

**Found 2026-08-14** while probing U-006/U-007. This supersedes the working assumption that
`SC3U.exe` is the RE target. It is not: `SC3U.exe` is the **GZCOM shell/loader**. The actual
simulation is ~6.2 MB spread across **29 GZCOM director DLLs** in `Apps\`, none of which has
been imported into Ghidra or exported.

## Evidence (all `[CONFIRMED]`, byte-level scans of the shipped `Apps\` binaries)

1. **29 DLLs in `Apps\` export `GZDllGetGZCOMDirector`** — the GZCOM module entry point. They
   are GZCOM plugin modules, loaded at runtime; that is why SC3U.exe contains no layer classes.
2. **The `SC3*Layer` strings live in those DLLs**, not in `SC3U.exe` (`SC3U.exe` `strings.csv`
   has none — the long-standing "no name anchors" problem in `SIM_LAYERS_XREF.md` is explained:
   we were grepping the wrong binary).
   **CORRECTION 2026-08-14 (SIMRCI analysis):** this doc originally called these "class-name
   strings". They are not — every one is an **INI file path** (`Sys\SC3ValveLayer.ini`,
   `\Sys\SC3ZoneLayer.INI`, `Sys\SC3ResLayer.ini`, …) consumed by a per-layer *tuning loader*.
   They still identify which layer lives in which module, but the anchor they give you is the
   layer's **config loader**, not its class or vtable. Pinning the class needs the module
   director's GZCLSID→factory table (see `re/analysis/SIMRCI.md`).
3. **No `0x41F836xx` GZCLSID dword occurs in ANY shipped binary** (exhaustive unaligned scan of
   every `Apps\*.exe` / `*.dll`, and of `original\SC3U.exe`). Class ids exist only as ASCII in
   `SYS.PAK` / `CitySim.ini` and are parsed at runtime. U-006 is falsified project-wide.

## Layer → module map `[CONFIRMED — class-name strings present in the module]`

| Module | size | `*Layer` name strings found | subsystem |
|---|---:|---|---|
| `SIMRCI.DLL` | 393,216 | `SC3ValveLayer`, `SC3ZoneLayer`, `SC3ResLayer`, `SC3ComLayer`, `SC3IndLayer` | S4 zoning + S5 RCI demand |
| `SIMMISC.DLL` | 331,776 | `SC3BudgetLayer`, `SC3WorldLayer`, `WorldLayer` | **S10** budget/finance + S1 world + S14 ordinances + S12 aura |
| `SIMDSTR.DLL` | 266,240 | `SC3DisasterLayer` | S11 disasters |
| `STRTSIM.DLL` | 233,472 | `SC3StrtSimLayer` | startup/scenario sim |
| `SIMGEOM.DLL` | 221,184 | `SC3BuildingLayer` | S3 buildings/occupants |
| `SIMUTIL.DLL` | 192,512 | `SC3PowerLayer`, `SC3WaterLayer`, `MiscPowerLayerTunables` | S2 power + water |
| `SIMSERV.DLL` | 167,936 | `SC3FireLayer`, `FlammabilityLayer` | S9 city services |
| `SIMECO.DLL` | 151,552 | `SC3PowerLayer` | S2 power |
| `SimTransit.dll` | 147,456 | `TrafficLayer` | S6 traffic/transit |
| `SCENARIO.DLL` | 143,360 | `SC3ScenarioLayer` | scenarios |
| `SIMSPR.DLL` | 512,000 | `LayerFlags` | sprites/rendering |

Modules that are GZCOM directors with no `*Layer` string (still in scope):
`SIMUI.DLL` (847,872 — largest module in the game), `SIMBABLD.DLL` (528,384),
`SIMADV.DLL`, `SIMINIT.DLL`, `SIMNTWRK.DLL`, `SIMDIRT.DLL`, `SIMCITY.DLL`,
`simvariables.dll`, `MaxisAddOn.dll`, plus the engine layer
`GZWIND/GZWWWD/GZGraphicD/GZResourceD/GZServiceD/GZSOUNDD/GZTOOLSD`, `AUDIO.DLL`, `GIMEX.DLL`.

## Corrected picture of the engine

```
SC3U.exe (1.1 MB)      GZCOM shell: bootstrap, factory registration, resource keys, HTML/UI glue
  └─ loads ────────►   29 GZCOM director DLLs (6.2 MB) = the actual simulation
                       layer classes registered by name/GZCLSID read from SYS.PAK/CitySim.ini
```

`SIMECO.DLL` and `SIMUTIL.DLL` both carry `SC3PowerLayer` — the class is referenced across
module boundaries (one defines, one consumes) `[UNCERTAIN]` which is which; resolve by
comparing each module's exports/imports and by which one contains the grid update code.

## Consequences for the roadmap

- `SIM_LAYERS_XREF.md`'s "layers are data-driven, unfindable in the exe" conclusion is correct
  but incomplete: they are **findable, in the DLLs**, by name string. The live-Ghidra vtable
  xref hunt on `SC3U.exe` (option B) is aimed at the wrong binary and should be dropped.
- The iOS oracle (`re/ghidra_export_ios/`) now pairs directly: `goPowerLayer`↔`SC3PowerLayer`,
  `goValveLayer`↔`SC3ValveLayer`, `goZoneLayer`↔`SC3ZoneLayer`, `goTrafficLayer`↔`TrafficLayer`.
  Anchoring should be far cheaper than on the stripped shell.
- Ghidra work needed: import + auto-analyse the 29 DLLs (extend `ghidra_headless.ps1` with a
  per-module project), re-run `ExportAllDecomp.java`, and grow `functions.csv` with a `module`
  column (currently implicitly `SC3U.exe`).

## Anchor status
`[CONFIRMED]` items above are from byte/string scans of the shipped binaries, not decompilation.
Each layer's *code* is still C0 — no function in any DLL has been read yet.
