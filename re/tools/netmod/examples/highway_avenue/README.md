# highway_avenue (task hwave)

Highway <-> avenue transition. Where a straight highway ends right at the end of a straight avenue (the stock game
leaves the highway's cap row against the avenue's U-turn row, not connected), those two rows become a ramp: the deck
lowers from the highway's height to the ground and goes on as the avenue, both directions connected. Either drag order
builds it (highway drawn up to an avenue, or an avenue drawn up to a highway end), along x and z.

- **Pieces** (painted for state 0 = the avenue at +z; the block turns them for the other three directions):
  21600 / 21601 = the cap row, exit / entry carriageway, deck H to H/2, variants of the on-ramp pieces 15137 / 15136
  (kind 15); 21602 / 21603 = the avenue's U-turn row, H/2 to the ground, variants of 15141 / 15140 (kind 14, road and
  highway). Those classes are what lets the trip router step between road and highway (`hwrc` lines, sc3netmod's
  NETRAMP class mapping).
- **Art:** `hwave_build.py art` (hwpaint scene from `hwave_paint.py`: the stock highway frames, eased descent, a grass
  median nose in the last 0.4 cell). Frame table from 15127 with ground under. Not shipped (game art).
- **Lanes:** `hwave_build.py lanes` (curve shapes 23400..23409). The stock avenue 11204 carries both directions in each
  cell, so the inner lanes swap sides in the ground row. The ground pieces' turn matrices leave out the two U-turns
  the crossover lanes add (comment in `hwave_build.py`).
- **Table lines** (manifest `highway_lines`): `hwyp` + `hwys` per piece (saved as the stock cap / 11203 the end rows
  had), `hwrc` per piece, `hwave 21600 21601 21602 21603` (the rule, `re/harness/src/sc3netmod_hwave.c`).
- **Saves:** without the mod the city loads today's stock ends (cap + U-turn rows); with it the transition comes back.
- **Off:** `SC3NETMOD_HWAVE=0` turns every transition back into the stock ends and builds none.

Build and install:

```
py -3.12 re/tools/netmod/hwave_build.py art re/tools/netmod/examples/highway_avenue
py -3.12 re/tools/netmod/hwave_build.py lanes re/tools/netmod/examples/highway_avenue
py -3.12 re/tools/netmod/hwave_build.py dart re/tools/netmod/examples/highway_avenue
py -3.12 re/tools/netmod/hwave_build.py dlanes re/tools/netmod/examples/highway_avenue
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/highway_avenue --tree <game tree>
```

**Diagonal** (phase 2): a diagonal highway ending at the end of a diagonal avenue (package `diagonal_avenue`, DAV) on
the same middle line, both families, either drag order. Pieces 21604..21609 (the cap, the cells either side of it and the
avenue's first middle cell; the j+1 far cell is empty land in stock), one set at four states. Art `hwave_build.py dart`,
lanes `hwave_build.py dlanes`. The rule is the `hwavd` line; DAV leaves the cells alone (`dbv_claimed` asks HWAVE). Saved as
the stock highway end plus DAV's own save ids (35 / 43) on the avenue side.

Needs an sc3netmod.dll built with `sc3netmod_hwave.c`, and for the diagonal one the `diagonal_avenue` package. Results:
`verify/hwave/RESULTS.md`.
