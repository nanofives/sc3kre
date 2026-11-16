# diagonal_xnet (task diagxnet, round 2026-11-15b)

Diagonal avenues (2+2, median) and diagonal boulevards (3+3) across a rail line or under a highway. Stock keeps its
straight crossing pieces there (69 road x rail, 15098 / 11258 highway over road), drawn as a 2-lane road. These 70 pieces
(30000..30069) are variants of those crossing pieces, so the rail and the highway keep working and a save loads as the
stock crossing without the mod:

- level crossing: the band's own lanes with the tracks through them, ballast across the median and sidewalks, a white
  stop line on each carriageway's approach side (owner: "Keep them");
- underpass: the stock deck, one opening the shape of the band, abutment walls along its edges.

sc3netmod's DAVXN block (sc3netmod_davxn.c) writes them on the crossing cells DAVXNET keeps, from the `crossing_lines`
table (`davxn <base> <base state> <band piece> <band state> <variant>`). Off: `SC3NETMOD_DAVXNRAIL=0`,
`SC3NETMOD_DAVXNHWY=0`.

Build the art before install (it is made from the game's frames and is not shipped):
`py -3.12 -m netmod.xnet_build re/tools/netmod/examples/diagonal_xnet` from re/tools, SC3_GAME_ROOT = a stock tree.
Checks and pictures: verify/diagxnet/RESULTS.md.
