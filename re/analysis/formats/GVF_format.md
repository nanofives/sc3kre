# GVF format (`FE_GVF_BIN_0001`) — FusionEngine keyed table

Parser: `re/tools/gvf_dump.py`. Full key dump: `re/analysis/formats/gvf_keys.csv`
(13,167 keys across 739/748 `.gvf` files in `data.fez`).

## Layout (reverse-engineered from `strings.gvf`)
```
0x00  16 bytes  ASCII magic "FE_GVF_BIN_0001\0"
0x10  11 bytes  header (two u32-ish fields; role [UNCERTAIN])
0x1b  entries:  repeating  [u16 keyLen LE][key ASCII (keyLen)][u32 value LE]
```
The entry-start offset is auto-detected (offset yielding the most clean `[len][key][u32]`
entries). `value` is a small int — a **string/record ID** (e.g. `QI_GRADE_D`=112,
`QI_LABEL_TRAFFIC`=34); the localized display text is resolved elsewhere by that id
(`[UNCERTAIN]` — the id→text table not yet located; likely the `data/sc3strings/*.gvf`).

## What the keys reveal (SC3 data/enum vocabulary)
- **Top-level modules** (`package.gvf`): `Terrain Vehicles Deals Script SSTrBlk SC3Strings
  GameEffects AppSetup License App`.
- **Zoning enums**: `QI_ZONE_RES_LD/MD/HD`, `QI_ZONE_COM_LD/HD`, `QI_ZONE_IND_LD/MD/HD`,
  `QI_ZONE_SEAPORT/AIRPORT/LANDFILL`, `QI_LABEL_ZONE_TYPE` — the RCI zone type × density matrix.
- **Traffic enums**: `QI_TRAFFIC_NONE/LIGHT/MEDIUM/HEAVY/CONGESTED`, `LC_TRAFFIC_DENSITY_HISTORY`.
- **Power/finance**: `QI_POWER_PER_MONTH`, plus grade/label families (`QI_GRADE_*`, `QI_LABEL_*`).
- **App/audio** (`app.gvf`): `MusicMgr::Track`, `Default_FullscreenDims_Normal`, `enCoreModule`,
  `StringVariables`, transport verbs `Play/Pause/Stop/Unpause`.

## Value to the project
- These enum labels are the **data-model vocabulary** for S4 (zoning), S5 (demand) and S6
  (traffic). When an SC3U `FUN_` switches over the same enum cardinality (e.g. 3 densities ×
  3 zone classes, 5 traffic levels), the label set here names what the raw integers mean.
- Next (P2): locate the id→text resolution so `value` maps to display strings; and compare the
  GVF key set against SC3U's `SC3StringsApp.IXF` / `SYS.PAK` to bridge desktop ↔ iOS data.
