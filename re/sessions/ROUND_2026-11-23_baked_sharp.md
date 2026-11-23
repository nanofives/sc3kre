# Round 2026-11-23: `baked_sharp` render style (SC4 thin details at zoom 4)

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Workspace from main. Owner call 2026-11-23: "Build it" (BOARD.md, owner calls answered 2026-11-23, row 5).

Background (verify/sc4ground/RESULTS.md lines 27-30, re/sessions/STATUS_sc4ground.md): the `baked` style draws zoom 4
as the zoom-3 frame doubled (bldrender `zoom4 = "double"`, the stock look). At zoom 3 (2.83 px/m) the Alamo's 0.14 m
flagpole is 0.4 px wide and drops out under the alpha test. Native zoom 4 draws it (a grey 1-pixel pole).

## Stream bakedsharp (opus / medium)

1. Add a render style `baked_sharp`: the same as `baked` (brightness, tone, peel, ground) except zoom 4 is rendered
   natively instead of doubled. Also `baked_raw_sharp` only if it falls out for free. Read how `baked` / `baked_raw`
   are defined in bldrender.py and bldweb.js first and follow the same pattern.
2. Python and page byte for byte for the new style (as every other style). Every existing golden stays byte identical
   (`baked` stays the default, owner call 2026-11-23).
3. Where the player picks it: per entry `"x_bldrender": {"style": "baked_sharp"}` like `baked_raw`. Add a page control
   only if one already exists for `baked_raw`; otherwise the entry key is enough.
4. Check: the Alamo (SC4 install, Steam SimCity 4 Deluxe, read in place) converted with `baked_sharp` shows the pole at
   zoom 4 in pictures, and once in game (sc3dev run, windowed, posted input or Frida only, kill only PIDs you started).
   Compare against `baked` side by side (zoom 4, all four rotations) and say what else changes (edges, noise, size).
5. Guide: one line in docs/buildings (SC4 section, next to the `baked_raw` line) if the style ships. sync_css.py
   --check / --publish if the page changed.
6. run_all.sh with all six args + SC3PACK_PACKS + SC4INSTALL passes every step (CHILD_PROTOCOL suite modes).
   Results verify/bakedsharp/RESULTS.md, STATUS re/sessions/STATUS_bakedsharp.md.

## Rules

SC4 install read in place, EA and community content and pictures never in the repo or docs. Windowed game, never the
real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add / commit.
