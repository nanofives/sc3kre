# HWY_BASE.md - the highway program's shared base (task hwcore, 2026-10-18)

Three files every highway shape stream (hwx, hwt, hwdx, hwdd) copies verbatim: `re/tools/netmod/hwpaint.py` (art),
`re/harness/src/sc3netmod_hwy.c` (placing pieces in game), `re/tools/netmod/hwlanes.py` (lanes and turn matrices).
Evidence: `verify/hwcore/RESULTS.md`. Proof package: `re/tools/netmod/examples/highway_core`.

## 1. One scene, three outputs

Describe the interchange once as hwpaint decks in world cells, then derive art and lanes from the same decks:

```python
from netmod import hwpaint as HP, hwlanes as HL
main = HP.highway(HP.Path.line((0, -6), (0, 6)))                             # two carriageways, traffic keeps right
loop = HP.ramp_deck(HP.Path.line((2.5, 1), (2.5, 2)).then_arc(1.5, -270),    # path = direction of travel
                    height=HP.ramp(HP.H, HP.H_LOW, 0, 4), support="slab", pillars=[(5.5, 2.0)])
scene = HP.Scene(main + [loop])
cells = HP.scene_cells(scene)
piece_of = {c: 21120 + i for i, c in enumerate(cells)}                       # your id range
for c in cells:
    HP.paint_cell(scene, c, "art/%d" % piece_of[c])                          # z*_r*.png + anchors.json
specs, _ = HL.build_cells(scene.decks, cells, 22500, piece_of)               # your curve shape range (protocol 5)
```

Each spec is a lanekit spec (state-0 frame, "connects": {"road": "auto"}, new curves under "curves"); save it next to
the manifest and list it under `"lanes"`. netpack writes the TrBlkAtt records, the turn matrix (prop 310) and the new
curves (every language folder's VPathAtt.IXF; English-UK gets the reversed copies). Pieces are painted for state 0, so
place them at state 0 from the block (`hwy_put(hp, x, z, piece, 0)`).

## 2. Rules the three files rely on (measured, see the module docstrings)

| fact | value |
|---|---|
| art / lane frame | lane x = (world x - X), z = (world z - Z); art 0..256, lanes 0..255 (border exactly 0 / 255) |
| heights | hwpaint e (zoom-3 px): stock deck H = 31.75, X lower 16, upper 47.5 (55.5 at the centre); lane node y = 32 e, snapped to the stock multiples of 256 (1024, 512, 1536, 1792) |
| carriageway | 1 cell, outer parapet on the driver's right; 73.0 drives +z on lanes x 61 / 145; 73.2 drives -z on 194 / 110 |
| diagonal highway | `highway_diag(path)` on a band median (x - z or x + z an integer): carriageways W_DIAG = 0.63 wide, read from the stock bands (x - z: 11223.2 / 11224.0 / 11223.0 at roles -1 / 0 / +1; x + z: 15052.2 / 15106.0 / 15052.0); repaint of the stock band cells 90..96% |
| ramps | `ramp_deck` default width RAMP_W = 0.62 = the stock ramp and the program width (hwx: W 0.31, ramp line 1.25 off the median, loop R 1.25, gap 0.19, turn arcs 0.75, tapers 0.62); the parapet / lane / curb split also holds on narrower decks |
| ground under a piece | a painted piece whose art leaves ground visible (slab ramps, pillars, gaps, a carriageway opened for a ramp) must take its frame table from stock **15127**: `"art": {"from": 15127, "png_dir": ..., "ground_under": true}`. 73's table (class 29440, draw flags 0) draws no terrain under the piece, and with 0x40 forced on it the terrain under it and under EMPTY cells next to it still goes missing in some views (back-buffer grey / slate). 15127's table (class 1650, flags 0x440) gave grass in all 16 shots (4 highway ends x 4 views, pieces at states 0..3, same art, 2026-10-18, verify/hwcore/RESULTS.md); confirmed by hwt in its own game (state-1 T in view 3 grass after reload, live rebuild grass at once). Frame shape does not matter with 15127's table: cropped, full-column and padded frames all passed (padding optional). Pieces whose art covers the whole cell (walls to the ground) may stay `from` 73. Mechanism (SIMSPR, traced): a frame table's class id picks the sprite class; 15127's 1650 = 0x672 draws the attached terrain, then the piece; 73's 29440 = 0x7300 ignores the attached terrain, so 0x40 has no effect on it |
| ramp joins | `Deck(..., gaps=[(s0, s1)])` opens the outer parapet over that span (`(s0, s1, "inner")` / `"both"` for the other side): the deck top runs to its edge as lane, so the ramp deck beside it reads as one road |
| traffic | keeps right: hwlanes drives a deck along its path for outer "right", against it for outer "left"; draw ramps in their direction of travel with outer "right" |
| turn matrix | low half = the ENGLISH lanes (side entered -> side left), high half its transpose; the router reads it for every highway node, so a missing turn blocks highway trips |
| curves | a lane links only if its curve key exists; stock shapes are fixed, so hwlanes writes one new curve per lane cut (keys = shape * 256 + rotation). Shape numbers: your stream's range in the protocol's section 5 table (`CHILD_PROTOCOL_2026-10-18_highways.md`, "Lane curve shape numbers"), not your piece ids |
| neighbours | the street sim finds the next cell's entry node by position (72-unit buckets): lanes of two cells meet when both are cut from one deck (same border point and height) |

## 3. Placing pieces (sc3netmod_hwy.c)

- Your block: `static void hwx_run(struct HwyPass *hp)`, prototype at the top of `sc3netmod_rbt.c`, one call line in
  `rb_hwy()` (marked with your task), its own table lines (`hwx ...` in the manifest's `highway_lines`, parsed by a
  dispatch line in `rb_file` next to hwcore's `hwy` one; `table_read` already skips every `hw*` line).
- Read with `hwy_at`, test empty land with `hwy_free`, check `hwy_claimed` before matching, write with `hwy_put`
  (claims and keeps), `hwy_keep` what is already right. Declare every piece with `hwyp <piece> <land> [save]`; what no
  block keeps in a pass is reverted by `hwy_end`.
- Land pieces (written into empty cells): a Protected HWAY base (15099..15105, 15107..15114, 15123..15128,
  15130..15141), so the stock tiler keeps them and connects the highway beside them. Pieces on the player's highway
  cells: a plain base (73 / 15051) so a retile re-places them.
- Save ids: a piece saves as its base unless `hwyp` gives a save id; pick a base a game without the mod can show.
  `hwyp <piece> <land> <save id> <state delta>` also turns the saved state by delta (a piece painted for one direction
  that a game without the mod should read as its base at another state). `hwys <piece> <id0> <st0> .. <id3> <st3>`
  gives the saved (id, state) for each state the piece can sit at: a rewritten highway cell saves as the stock straight
  (15051.2 +x, 15051.0 -x, 73.0 +z, 73.2 -z, its heading turned by the state) or the stock band piece for its role; a
  land piece as the nearest stock one-lane ramp piece (15123..15141). The variant section keeps the original state, so
  loading with the mod puts every piece back as it was (also with SC3NETMOD_HWY=0). The save cannot leave a tile out
  (the writer counts tiles before writing each one).
- Kept cells are safe from your own reverts: hwy_end re-places any kept cell a revert's 3x3 rect retile changed.

## 4. Not done / open

- `hwy_free` passes zoned empty land (what terrain vt+0xd0 tests is not decoded); buildings fail it (surface-layer
  occupants), not tried in game.
- New curves and lanes were checked offline (records decode back, every language compiles) and the game loads the
  extended VPathAtt files; animated cars on them were not watched (the lab city has no population).
- Curve record trailing u32: written as 2 (the value on 508 of 556 elevated stock curves); its meaning is unknown.
