# Round 2026-11-18b: import buildings from 3D models + a classifier

Orchestrator: "SC3 Simtropolis feedback triage". Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspaces from main 82d8ae2
(release sc3mods-2026-11-18b, base stage\release = LAN 2026-11-18b).

## Owner request (Mariano, 2026-11-18)

"can we create a tool (maybe within the game) that can load a folder of models and classify them with metadata
whether those should be residential, commercial, even other zone types like airports that may not have replacements?"
Answers: input first 3D models (obj, etc.), then downloaded SC3 buildings. Zone types in order: R / C / I, then airports
and seaports, then ploppables (civic, landmarks). Standalone first, an in-game browser after.

## The shared metadata (both streams read and write this, one file per folder: `models.json`)

```json
{ "sc3models": 1,
  "models": [ {
    "file": "house_a.obj",            "name": "Red brick house",
    "kind": "growable",               "class": 3300,
    "lot": [1, 1],                    "weight": 1,
    "height_m": 9.5,                  "scale": 1.0,   "rotate_deg": 0,
    "style": "any",                   "enabled": true,
    "notes": "" } ] }
```
- `kind`: `growable` (R/C/I now), later `airport`, `seaport`, `ploppable`. `class` = the game's lot class (LandUse
  id, prop 0x65): the same numbers and lot sizes as `tools\bat_growables.ps1` (its `$Classes` table) and
  `re/analysis/BUILDING_PICK.md`. Unknown keys are kept on round trips. New fields need the orchestrator's OK.

## Stream bldrender (opus / high): a 3D model grows as a zoned building

Background: `re/analysis/NET_ART.md` (section 9) and `re/tools/netmod/netart.py` + `netart_blender.py` +
`netart_calib.json` (Blender 4.5, camera pixel-exact at zoom 3-4, frame = zoom*4 + rotation, anchor rules),
`re/analysis/BUILDING_PICK.md` (families, TKB1 exemplars, prop 0x67 frame tables), `re/tools/netmod/netpack_growables.py`
(proven: a red copy at id 36001 grew 954 lots, traps: Key line first, exemplar in `[OccAttribCache]`),
`re/scripts/bat_growables.ps1` (how a BAT building becomes a growable, ids 37000+).
Do:
1. Find how a stock building's art is laid out (frames per zoom and rotation, sizes, anchors, palette / pixel format,
   shadow, night lights if any) from a stock 1x1 house. Cite RVAs or file offsets.
2. Render an OBJ (use a simple test house you make in Blender, untextured plus one textured) into that art at every
   zoom and rotation, with the netart calibration extended to buildings (height, lot size 1x1 and 2x2).
3. Package it as a new growable from a `models.json` entry (ids 38000+), and show it growing in Sacramento with
   pictures at zoom 4 next to stock houses. Tool: `re/tools/bldimport/` (`render`, `pack`, one command from a folder).
4. Write `re/analysis/BUILDING_ART.md` and `verify/bldrender/RESULTS.md`.

## Stream bldclass (sonnet / medium): the standalone classifier

A local page (one HTML file, opened from disk in Chrome or Edge) that opens a folder of models (OBJ first; glTF and
FBX if the loader is cheap), shows a turnable 3D preview and a thumbnail grid, suggests `class` / `lot` / `kind` from
the footprint and height (rules written in the page, editable), lets the player edit one or many at once, and saves
`models.json` into that folder (File System Access API, with a download fallback). Libraries only from a CDN with a
pinned version (three.js). English text. Light and dark. No server. File: `re/tools/bldimport/classifier.html`, with a
sample folder `re/tools/bldimport/samples/` (2-3 small OBJs you make). Check it in headless Chrome (render shots) and
write `verify/bldclass/RESULTS.md`.

## Later rounds (not now)

Downloaded SC3 buildings (the owner sends sample files, formats to identify), airports / seaports (their rules pick
differently: `BUILDING_PICK.md`, Apply exceptions 0x100032d1 / 0x1002b04c / 0x1002d27f), ploppables (menu path), the
in-game browser.

## Rules

Windowed game, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, STATUS file
at every milestone, no git add / commit. Run a real check before reporting done, and keep working until the task is
finished.
