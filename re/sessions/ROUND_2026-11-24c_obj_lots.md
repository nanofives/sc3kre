# Round 2026-11-24c: props on OBJ building lots, then non-square growables (research)

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner 2026-11-24, looking at the sample pack overview (verify/bldpack/owner_bare_lawn.png): "skyscraper doesn't have
anything on its floor?", "all buildings ... are really square?". Owner calls: "Stock props on the lot, and then Research
non-square growables", then re-render the sample pack pictures (overview + Berlin skyscraper) for the forum post.
Today an OBJ model is drawn on a plain patch of lawn (docs/buildings "on its own patch of lawn"): a slim tower on 3x3
or a long factory on 2x2 leaves bare grass. SC4 lots already carry props (verify/sc4props, sc4baseprops).

## Stream objprops (opus / medium): the game's own small props on the free part of an OBJ building's lot

1. Evidence first: where SC3's own small lot objects can come from. SC3 has no SC4-style prop exemplars as far as we
   know: say with evidence what exists (stock building frames with painted lot dressing, park / plaza pieces, tree
   sprites, the BAT parts in BACustom / Building Architect part library, vehicles). The importer runs on the player's
   PC and already reads the player's game files, so reading art from the player's own install at install time is the
   pattern (never ship EA art in the sample pack or docs).
2. Design per class: houses (garden, trees, a car), shops (parking, benches), offices / towers (plaza paving, trees,
   lamps), industry (yard, crates, trucks). Place only on the free part of the lot (outside the model's footprint), in
   every rotation and zoom, drawn with the same camera and light as the building. A per-building switch like
   SC4's `x_sc4.props`, default on.
3. Python and page byte for byte. Every existing golden byte identical unless the building now gets props (then new
   goldens for those cases, listed).
4. Check: the sample pack installed in a dev tree, the overview frames and Sacramento / Berlin grown. Look at every
   picture.
5. Re-render the sample pack pictures for the post: verify/bldpack/owner_shots/00_whole_pack_z3.jpg (overview) and
   13_berlin_skyscraper_zoom3.jpg (fresh in-city frame, Berlin, same camera idea). Keep the old ones as *_pre_objprops.
6. Full suite, sync_css.py --publish, guide lines. Results verify/objprops/RESULTS.md, STATUS_objprops.md.

## Stream lotgrow (opus / high): can zone growth place non-square lots? Research only, nothing built

Start from re/analysis/LOT_SHAPES.md section 5.4 (developer SIMRCI 0x10027699 sizes lots from SizeInCellsX only)
and BUILDING_PICK.md. With CodeView names (CV_SYMBOLS.md):
1. Map the zone developer path end to end: how it picks a lot size, scans zoned cells for a free block, chooses a
   building from the families (BUILDFAM weights), places it, and how redevelopment / merging of lots works.
2. Every place a square is assumed (block scan, merge, demolish for redevelopment, abandonment, the RCI lot pass, save).
3. What a w x d growable would need: hook points, a rotation choice (2x3 vs 3x2 on the cell grid), interaction with
   LOTRECT (draw), the family lists, and what breaks without the mods (save opened in stock).
4. A feasibility verdict with an estimate of the change (number of hook sites, risk), and a smaller first step if one
   exists (for example 1x2 / 2x1 only, or a non-square building inside a square lot with filler on the rest).
   NO-GUESSING, cite addresses. Results re/analysis/LOT_SHAPES.md new section + verify/lotgrow/RESULTS.md,
   STATUS_lotgrow.md. Stop and report.

## Rules

EA art only from the player's own install at run time, never in git, docs or the sample pack. Windowed game, never
the real mouse or keyboard, test slot, harness claim before game runs, kill only PIDs you started, delete BMP dumps,
no git add / commit.
