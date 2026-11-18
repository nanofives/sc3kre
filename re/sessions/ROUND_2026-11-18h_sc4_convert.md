# Round 2026-11-18h: SimCity 4 buildings into SC3U (prototype)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main.
Related: ROUND_2026-11-18b/c/d (re/tools/bldimport: OBJ -> growable, models.json, render styles, importer page).

## Owner (2026-11-18)

Sent an SC4Evermore pack (`BSC JMyers Homes Pack V3.1`, SimCity 4) and chose "Yes, prototype it" for an SC4 -> SC3U
building converter.

## Input (local only, never in git, never redistributed)

`MAIN\stage\st_packs\sc4_jmyers_homes\` (unzipped; the Java installer unpacked in `jar\`):
- `jar\installation\BSC\BSCProps#\BSC BATProps JMyers - Homes Pack\*.dat`: DBPF 1.0, 7,577 entries: 2,560 S3D
  (type 0x5AD0E817, QFS-packed, `3DMD`), 4,760 FSH (0x7AB50E44), 128 exemplars (0x6534284A), 128 of type 0x88777601,
  1 directory (0xE86B1EEF). 18 house designs x 6 colours = 128 models, each 5 zooms x 4 views.
- `jar\installation\BSC\JMyers\Homes Pack#\<design>\JFM_Homes_*_Lots_v3.dat`: lot + building exemplars, LText names.
- Readme: R$ residential, lots 1x2 / 1x3 (corners 2x2 / 2x3), growth stage 1-3, occupants 11-22. Lot props need the
  BSC Common Dependencies Pack (not here): the house models do not.
- Terms: "Feel free to modify the lots for yourself ... please don't distribute them without asking first." So the
  converter runs on the player's own downloads; converted output stays local. Test pictures for the owner only.

## Stream sc4conv (opus / high)

1. Readers in `re/tools/sc4conv/`: DBPF 1.0 / 1.1 (index, directory of compressed entries, QFS), S3D (3DMD chunks:
   HEAD, VERT, INDX, PRIM, MATS, ANIM, PROP, REGP: document field layouts with offsets in re/analysis/SC4_FORMATS.md),
   FSH (each pixel format used here, mipmaps), exemplars (property ids for occupant group / wealth / lot size /
   building name / the model's resource key), LText.
2. Geometry: what coordinate space each zoom/view S3D is in, which faces each view keeps (back faces removed?), and
   whether the four zoom-5 views can be combined into one model or each SC3 view should use its matching SC4 view.
   Decide with renders, not by reasoning alone.
3. Export: per building OBJ + MTL + PNG textures (baked SC4 lighting noted), and a models.json entry filled from the
   exemplars (SC3 class from SC4 wealth + occupancy, lot size from the footprint: SC3 growables are square, so say how
   1x2 / 1x3 lots map, name from LText, weight). Command: `sc4conv.py <sc4 folder or .dat> --out <folder>`.
4. Render with bldimport (default style), install in a dev tree, grow a sample (6+ designs) in Sacramento, pictures at
   zoom 3 / 4 next to stock and next to the SC4 originals' own look, phone-sized in MAIN\verify\sc4conv\owner_shots\.
5. Report what converts well, what does not (camera angle, baked light, hidden faces, props), and what a player-facing
   route needs (the importer page reading .dat directly, in JS, like bldweb).
Results MAIN\verify\sc4conv\RESULTS.md, STATUS MAIN\re\sessions\STATUS_sc4conv.md.

## Rules

Windowed game, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, no git add /
commit. Nothing from the pack (models, textures, renders) goes into the repo or docs/.
