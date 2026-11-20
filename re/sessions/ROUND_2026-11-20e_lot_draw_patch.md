# Round 2026-11-20e: draw non-square buildings whole (SIMSPR patch), then importer lot shapes + 5x5

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main a09cc35+.
Owner (2026-11-20): "True 2x3, patch drawing" (asked after re/analysis/LOT_SHAPES.md + verify/lot2x3/RESULTS.md, read
both first): a 2x3 landmark places, saves, moves and bulldozes correctly, but SIMSPR 0x100192aa registers the sprite as
n x n from the footprint's first value (prop 0x66 value 1, 0x10019341), with one size byte in the sprite map, anchor
and clip (0x10007b4d, 0x1000c678, 0x1000be25): a 2x3 draws as 2x2 with the far end cut, a 3x2 claims a 3x3 block and
corrupts its neighbours (ghost after bulldoze until reload). The save writes the first footprint value twice (SIMGEOM
0x1001cd38, one byte at 0x1001cda8). Growables cannot be non-square (SIMRCI 0x10027699 lays out square lots).
Probe tools: verify/lot2x3/work/make_lot2x3.py (test plugin, 2x3 and 3x2 test landmarks), lab.py (drives the game).

## Stream lotdraw (opus / high): the drawing patch

1. Patch the draw path so a building's sprite uses its real width and depth (both orientations, all four view
   rotations, the anchor, the clip, the sprite map), plus the save byte so saves record the true size. Host it in an
   existing mod (sc3perf already patches SIMSPR, sc3resize hosts most features: your call with the reason), behind
   its own switch and mods page row like the other features. No new DLL.
2. Square buildings must draw exactly as before: frame dumps of a busy city (several zooms and all four rotations)
   with the patch on and off must be identical pixel for pixel. Measure the draw time too (sc3perf).
3. The 2x3 and 3x2 test landmarks: whole in every rotation and zoom, neighbours on every side untouched, the 3x2
   ghost gone, placement highlight, Mover, bulldoze, save + reload, the save's footprint field. Pictures.
4. Mod rules: memory notes on SIMSPR (reference-sc3-mod-recipes, project-mod-startup-races: never restore
   VirtualProtect, shared pages; feedback-simspr-restore-staged-last: END the session with the owner's staged build
   restored and verified if you touched SIMSPR on disk, patch in memory only if you can).
5. Results verify/lotdraw/RESULTS.md, LOT_SHAPES.md updated, STATUS re/sessions/STATUS_lotdraw.md.

## Stream lotshape (after lotdraw and sc4ground are merged)

Importer: landmarks and rewards keep SimCity 4's real lot shape (w x d, both up to 5, the patch's switch required,
else the smallest square), 5x5 for landmarks and rewards (stats from a stock 5x5 landmark / reward), bldimport and the
page byte identical, art anchors for w != d, guide. Civic looks keep their base's lot, growables stay square.

## Rules

Windowed game, never the real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add /
commit. Another child (sc4ground) edits re/tools/sc4conv and re/tools/bldimport right now: lotdraw stays in
re/harness and the test tree.
