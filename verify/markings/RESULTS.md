# markings (2026-10-22)
Owner img13: plain road corners had white dashes. Cause: avenue_markings reskinned 11203 (stock plain-road curve).
Fix: avenue_markings reskins 11204 only. Test tree Simcity_stock_markings (own copy, shared tree overlay was locked), instance inst_markings, lab.sc3 copy.
After (owner_shots): after_road_corner.png = plain road S corner, yellow centre line, no dashes; after_avenue_end.png = avenue (two parallel drags, AVL converted 30 cells), end U-turn keeps white dashes (21701 art from avenue_lanes).
Before = owner's img13 (not re-rendered; shared tree locked).
Reinstall for release: avenue_markings only (art/11204 is not shipped: build or copy it).
