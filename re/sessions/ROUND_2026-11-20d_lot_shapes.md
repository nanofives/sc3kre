# Round 2026-11-20d: non-square lots (2x3 probe), then 5x5 landmarks and rewards

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main.
Owner (2026-11-20): "Test a 2x3 lot, and then Allow 5x5". Why: SimCity 4's Small Police Station sits on a 2x3 lot and
the converter puts SC4 buildings on the smallest SC3 square (the stock base's lot for civic looks).
Measured by the orchestrator 2026-11-20 (batgrow.stock_buildings over stage\release, prop 0x66 footprint {x, ?, z}):
661 stock buildings carry a footprint, ALL square: 1x1 344, 2x2 82, 3x3 83, 4x4 50, 5x5 102 (the 5x5 ones are
mostly landmarks, LandUse 18xxx, plus a few civic / reward types). The 4-piece rewards are square pieces. bldimport and
the converter stop landmarks and rewards at 4x4 and write lot [n, n] only (re/analysis/BUILDING_ART.md 7).
Another child (sc4ground, round 2026-11-20c) is editing re/tools/sc4conv/* and re/tools/bldimport/bldrender.py,
bldweb.js, sc4web.js right now: stream lot2x3 must not edit those files.

## Stream lot2x3 (opus / high): can SC3U place, draw, rotate, save and bulldoze a non-square building?

1. Static: where the game reads prop 0x66 (footprint) and whether code paths assume x == z (placement tool and its
   highlight, the occupant's cell claim, the view-rotation swap of x and z, the art frame / anchor per view, save and
   load, bulldoze, the Mover, the query window). RVAs, NO-GUESSING. CodeView names for the exe, tracker for DLLs.
2. Probe: one 2x3 test LANDMARK (hand-made plugin in the test tree only, art from a test model drawn for a 2x3
   footprint in all four views, bldimport patched locally in the worktree if that is the simplest way to write it).
   In game (sc3dev run lot2x3, windowed, posted input or Frida game calls only, never the real mouse or keyboard,
   kill only PIDs you started): place it, the placement highlight, the four view rotations, save + reload, bulldoze,
   Mover, a neighbouring building placed against each side. Pictures local in verify/lot2x3/owner_shots.
3. Verdict for landmarks and rewards (hand-placed) and for growables (the zone developer lays out lots: does it ever
   make a non-square lot?). If it works for hand-placed buildings: what bldimport and the converter would need
   (lot [w, d], art anchors, the page), with the risks. Do not build that yet.
4. Results verify/lot2x3/RESULTS.md, analysis note re/analysis/LOT_SHAPES.md, STATUS re/sessions/STATUS_lot2x3.md.

## Stream lot5x5 (after sc4ground and lot2x3 are merged)

Landmarks and rewards up to 5x5 in bldimport, the page and the converter (stats from a stock 5x5 landmark / reward),
byte identity, suite, one in game, guide.

## Rules

Windowed game, never the real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add /
commit. EA content only in the test tree.
