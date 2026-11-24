# Round 2026-11-24d: non-square growables, full version

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner 2026-11-24: "Build the full version" after the lotgrow research (re/analysis/LOT_SHAPES.md section 11,
verify/lotgrow/RESULTS.md, merged 3b1cdb5f). Read section 11 first: it is the design.

## Stream lotgrowb (opus / high)

1. Mod side (owner of LOTRECT is sc3perf; put it there unless the evidence says another mod owns the zone developer):
   C copies of the generic rule bodies that read both SizeInCellsX and Z (the 3 bodies of section 11: block-fill
   0x10026b01 family, corner-and-strip 0x10027699 / 0x1000dd1a, commercial block 0x1000cf87, as section 11 groups them),
   installed by swapping the rule vtable pointers (9 writes), bytes checked before patching, one switch (mods page row
   "Non-square zoned buildings", env var, ini), off = stock.
   Square buildings take exactly the stock path, random-number order included.
   Pass test before anything non-square is installed: identical occupant layers with the switch off and on, same city,
   same seed / same days run (Sacramento and a 1024 city).
2. Limits from section 11: long side along z only (w < d), sides differing by 1 (1x2, 2x3, 3x4, 4x5), LOTRECT on,
   families no fixed-layout rule shares (copy a family + INI row for 3500 / 3700 as section 11 says), no layout-role
   flags, not in the replaceable list. Fixed layouts (row houses, large lot, L blocks, farm, ports) stay stock.
3. Open questions to settle in game first: which art a w x d growable shows under construction and abandoned; loading a
   save with the package removed (stand-in overlap by a row): measure it, and if it overlaps, find the least bad
   fallback (for example the stand-in on the w x w square plus the extra row left empty).
4. Importer side (bldimport.py, bldweb.js, classifier.html): growables may take w x d lots within the limits above,
   suggested from the model footprint (a long factory gets 2x3 instead of 3x3). Python and page byte for byte. NOTE:
   the child `objprops` is editing the same importer files now: do the mod side first; start the importer side only
   after objprops is merged into main (pull main), and keep importer edits to the lot-size planning parts.
5. Check in game: sample pack members re-planned on non-square lots (Shop Row, Long Factory, Chimney Factory, Office
   Block where their footprint fits) grow by themselves in Sacramento / Berlin / Madison, every rotation draws whole,
   save / reload, bulldoze, abandonment, redevelopment over them, the save opened in stock. sc3perf monthly sim time
   before / after. Pictures of each.
6. Full suite (CHILD_PROTOCOL suite modes), sync_css.py --publish, guide (docs/buildings lot rules), README mods row.
   Results verify/lotgrowb/RESULTS.md, STATUS re/sessions/STATUS_lotgrowb.md.

## Rules

Windowed game, never the real mouse or keyboard, test slot, harness claim before game runs, kill only PIDs you
started, delete BMP dumps, NO-GUESSING (cite addresses), no git add / commit. EA art only in dev trees and verify.
