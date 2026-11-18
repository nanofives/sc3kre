# bldclass RESULTS (2026-11-18)

Page: `re/tools/bldimport/classifier.html` (worktree `dev/bldclass/wt`). three.js 0.160.0 from jsdelivr via importmap, OBJ loader (+MTL), glTF/GLB and FBX loaders imported on demand.
Test hooks: `?demo=1` (loads `samples/` by fetch, needs `--allow-file-access-from-files` in headless Chrome), `&select=all|a.obj,b.obj`, `&theme=light|dark`, `&turn=<deg>`, `&rules=1`, `&selftest=1`.

## Checked (headless Chrome, swiftshader)
- Grid of 3 sample models with thumbnails and badges (zone, class, lot, new): `grid_light.png` (light), `preview_dark.png` (dark grid + factory preview turned 40 deg, lot outline on the 16 m grid, suggestion with its reason text).
- Multi-select edit panel with "(mixed)" fields and the rules editor open: `edit_multi.png`.
- Phone width: `phone.png` rendered at 375 px, `scrollWidth == clientWidth` (375), no horizontal scroll.
- Suggestions for the samples (rules defaults): house 9.0 x 7.0 m, 9.0 m -> R, 3300, 1x1. Shop (file entry kept: 5100 1x1). Factory 28 x 20 m, 26 m high (chimney) -> I, 8300 dirty medium, 2x2 (name keyword "factory", height > 12 m -> density 2, lot from 1.75 cells).
- models.json round trip, `py -3.12 re/tools/bldimport/check_roundtrip.py` (output in `roundtrip_output.txt`): 8/8 PASS. Reads `samples/models.json`, multi-edits 2 models (class 3500, lot 2x2, notes), serializes, reloads from the saved text, serializes again. Unknown keys kept: top-level `generator`, per-entry `x_bldrender` (object) and `author`; the entry for a file not in the folder (`missing_building.obj`) is kept; the new model (factory) is added with all 12 known keys; second save is byte-identical to the first.

## Not checked (needs the owner in a real browser)
- `showDirectoryPicker` open and direct write into the folder (cannot be driven headless). The `webkitdirectory` fallback and the download-on-save path are in the code but also not exercised.
- glTF/GLB/FBX loading and OBJ + MTL textures (code present, no sample files).
- Mouse interaction (click, Ctrl-click, Shift-click range, drag to turn): screenshots use the URL hooks instead.

## Assumptions to confirm with the orchestrator (no new fields were added to the format)
- Units are meters, Y up. `height_m` is the model height after `scale`; editing one updates the other (`scale = height_m / raw height`).
- One lot cell = 16 m (`cell_m` in the rules, editable). Lots are written as `[n, n]`.
- Commercial classes have no mid wealth: rules map `mid` to `low` (`commercial_mid_as`).
