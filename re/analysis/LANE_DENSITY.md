# LANE_DENSITY.md - road traffic density that follows lanes (task lanedensity, 2026-10-13)

Owner decision: "que la densidad respete los carriles". Branch `child/lanedensity`. Code: sc3netmod LANEDENSITY block
(`re/harness/src/sc3netmod_lanes.c`). Proof: `verify/lanedensity/PRE.md` -> `RESULTS.md`. Addresses are Ghidra VAs of
SimTransit.dll unless another module is named.

## 1. How the router expands a node (decoded)

Trips: `FUN_100070d0` (route_trip) is a DFS with an explicit stack. Per step: arrival test `FUN_10008a94`, push,
`FUN_1000755e` (select_next_cell) picks ONE next node; on failure the stack is popped and the previous node retried
while its `+0x1d` flag is set. Visited cells: the byte grid `layer+0x78` (rows[x][z]), one bit per node type, never
cleared during a trip. Density is deposited only after arrival, while popping the final path: `FUN_10006edd(x, z,
amount, mask)` per cell of each node (mask 0x15 road/rail/bus, 2 highway, 8 subway) [CONFIRMED @ 0x100070d0].

Node (32 bytes): +0 occupant (an interface of the piece; QI 0x41658d28 gives the piece object at occupant-4, measured
on 5 vtables), +4/+8/+0xc/+0x10 cell rect x0, z0, x1, z1, +0x14 type, +0x15 previous node's type, +0x18 cost,
+0x1c entry side (world: 0 x-, 1 z-, 2 x+, 3 z+), +0x1d "retry" flag. Start node: type 0x80, +0x15 = 0
[CONFIRMED @ 0x10006fe3, 0x1000706a].

`FUN_1000755e` by node type [CONFIRMED @ 0x1000755e]:

| type | branch | neighbours |
|---|---|---|
| 1 road, 4 rail, 8 subway, 0x14 / 0x18 / 0x30 stations, 0x41 bus | ring scan `0x10007a63` | every cell of the rect grown by one, corners excluded, CENTRE INCLUDED. A cell is a candidate when the visited byte lacks the node type's bits and the flags grid `+0x5c` gives a step: for type 1, `& 0x10` (stations: 0x50 / 0x30 / 0x14 / 0x18 by the trip's mode flags) or `& 1` (road: next type 1, or 3 when `& 0x40`). Non-candidates get the type's bits in the visited grid. Selection, mechanically: a candidate whose `+0x6c` byte is below `DAT_1001f0c0` replaces the kept one unless its byte is lower than the kept one's (decompilation lines 150-166 of the export); one at or above it is kept only when nothing is kept yet. PERFORMANCE.md Finding 22 says "keep the least congested"; this read says the opposite and was not checked live `[UNCERTAIN]`. |
| 2 highway, 3 ramp-road, 0x42 / 0x43 bus | matrix `0x10007881` | QI the occupant, piece `vt+0x4c(0, *(u8*)(layer+0x54), entry side)` -> four bools for x-1, z-1, x+1, z+1, each checked by `FUN_100086e7` (same visited grid, same flags) |
| 0x80 start | radius scan | cells within the per-kind radius of the lot |

After the pick: the next node's footprint gets the CURRENT node's type bits, its entry side is set from the rects
(`0x100083c5` .. `0x100083e4`: 1, 0, 3, else 2), cost added.

So a ROAD node never reads the piece's lanes or turn matrix: any road cell beside it is a candidate, including a
parallel road one cell away (no junction) and the cell itself.

Quirk (stock): a road node entered from a lot has its cell marked with 0x80, not 1, so the ring scan offers its own
centre; the copy gets entry side 2 (same rect -> the else branch at `0x100083e4`). Harmless in stock (one extra step).

## 2. Stock matrices vs today's router (measured, `SC3NETMOD_LANEDENSITY=count`)

See RESULTS.md arm S_cnt. Honouring the stock matrices would change stock routing (steps the matrix forbids, entries
through sides with no lane), so the default honours only netmod VARIANT ids (`g_base`, the tables of installed
packs); `SC3NETMOD_LANEDENSITY=all` honours every piece.

## 3. The patch (sc3netmod LANEDENSITY)

- Entry detour of `FUN_1000755e` (6 bytes `55 8b ec 83 ec 68` -> jmp; trampoline replays them), and the arrival call at
  `0x100071eb` retargeted. Both checked against the shipped bytes. sc3perf patches nothing in these ranges (it hooks
  0x7158, 0x6fe3, 0x706a, 0x6edd, 0x6a72, 0x9242, 0x5237, 0x526c, 0x154e and the ceil IAT), so the two coexist.
- A 1x1 road node (type 1 / 0x41) on an honoured piece: allowed exits = the matrix row of its entry side, asked exactly
  as the game asks it for highways (`vt+0x4c`, half `layer+0x54`), cached per (half, id, state); entered from a lot or
  a station (previous type not a network type): the union of the four rows. Each road neighbour on a closed side, and
  the node's own cell, get the node type's bits in the visited grid for that one call (so the ring scan skips them);
  only the bits added are cleared afterwards. Station neighbours stay candidates.
- Entered against the lanes (row empty): the step fails, the cell's own visited mark is cleared (so it stays reachable
  through a legal side), and the transition (from cell -> this cell) is remembered per thread for the rest of the
  trip and closed in every later scan from that cell, whatever its type. Without that list the DFS retried the
  previous node, which picked the same cell again, for ever (measured once: 6.3e8 refusals, the trip never ended).
  The list is cleared when a trip's start node is scanned; when full (32) the cell keeps its mark. The arrival test
  is refused for such a node.
- A piece whose matrix half is all zero is unconstrained (no lane data).
- Threads: the visited grid and the node belong to the trip (sc3perf traffic_mt workers each have a shadow layer and
  marker grid); caches are written with interlocked operations; the per-thread list is TLS.
- Logs every 10 s in sc3netmod.log: counters, and per variant cell the router steps by (entry side, exit side).

## 4. Results

See `verify/lanedensity/RESULTS.md`.
