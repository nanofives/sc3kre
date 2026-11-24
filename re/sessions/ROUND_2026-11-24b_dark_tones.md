# Round 2026-11-24b: protect dark tones in the baked brightening (SC4 police cars read as white blobs)

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner 2026-11-24: "Protect dark tones" (police cars), "Leave it" (Alamo wall: camera limit, the post's disclaimer covers it).
Evidence (verify/sc4art/RESULTS.md, owner_shots/02): the baked tone y' = 1.33 y^0.75 (bldrender STYLES["baked"],
applied at bldrender.py ~716 and the same in bldweb.js) lifts the cars' black body panels: 25% of the car texels sampled
are darker than 60, 2.7% of the output pixels. `baked_raw*` keeps them black and white but darkens the whole building.
The 0.75 / 1.33 curve was fitted on the 18 JMyers designs to sit SC4 art with the stock buildings (verify/sc4conv).

## Stream darktone (opus / medium)

1. Mock first, offline: 2-3 curves that keep the baked curve for mid and light tones and bring near-black back toward
   its own value (for example a blend toward y' = y below a knee, a toe on the curve, or a luminance-weighted mix).
   Apply to the Small Police Station (cars), the Large Fire Station, a JMyers house, Hagia Sofia and a park with trees.
   Measure: the share of pixels the change touches, mean lightness of each building before / after, and how far the
   fitted match to the stock buildings (verify/sc4conv's 0.23 / 0.40 / 0.73 prediction) moves. Pick the curve that keeps
   the cars reading as cars while moving the rest least. Say whether it applies to props only or to the whole frame,
   with evidence (owner's complaint is the cars; trees must not get darker than now).
2. Build it into the `baked` family (baked, baked_sharp; baked_raw* unchanged) in bldrender.py and bldweb.js, byte for
   byte. Every non-SC4 golden byte identical; SC4 goldens regenerated.
3. Re-make every forum sheet in verify/sc4cmp/forum/ whose frames change (in-city strips from new game frames only
   where the frame changed), look at each one, before / after crops (police cars, a tree-heavy lot, a dark-roof house).
4. Full suite (CHILD_PROTOCOL suite modes), sync_css.py --publish, guide line if the `baked` description changes.
   Results verify/darktone/RESULTS.md, STATUS re/sessions/STATUS_darktone.md.

## Rules

SC4 install read in place, EA content never in git or docs. Windowed game, never the real mouse or keyboard, test
slot, harness claim before game runs, kill only PIDs you started, delete BMP dumps, no git add / commit.
