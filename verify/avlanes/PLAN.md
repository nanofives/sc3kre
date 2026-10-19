# avlanes: plan for two-lane one-way avenue halves (2026-10-19, milestone 1)

Owner 2026-10-19: "i want avenues to follow the lanes logic in real life, avenues are 4 lanes, 2 on one side, 2 on the
other, we need to rework avenues to allow for that". Orchestrator defaults: (a) right-hand traffic like the highways,
(b) one-way halves in ROUTING too (turn matrix props 310 allows only the half's direction), avenue ends become U-turns,
(c) road x avenue T and X keep every turn through a median opening, (d) avenue_markings' white dashes between the two
lanes of a half, the median between the directions. Owner sheet: `MAIN\verify\avlanes\owner_shots\avlanes_plan.png`.
Data: `verify/avlanes/data/` (scans of the 15 shipped cities, stock lane dumps). Tools: `re/tools/netmod/avlanes_*.py`.

## 1. Stock facts (measured on the 15 shipped cities, `avlanes_scan.py`, `avlanes_scan2.py`, `avlanes_bands.py`)

- **26,752 cells of 11204** in 13 cities (Berlin 3,904 ... Farmsville 2; Big One, Europolis, Roadless Paradise none).
  11204's lane records equal plain road 29's: one lane each way, +x at z 80, -x at z 175 in the state-0 frame
  (`data/stock_lanes.txt`; CAR_TRIPS.md 2). Its matrix is two-way (`0x01040104`, x- => x+, x+ => x-).
- **State = which half, 100% consistent**: band along z, state 1 is always the x- half and state 3 the x+ half
  (6,229 / 6,229 pairs); band along x, state 2 the z- half and state 0 the z+ half (5,992 / 5,992). The median lies on
  world side s for state s (N E S W = 0 1 2 3; same as avx.py `half_state`).
- **11204 is avenue-only.** Every 11204 without an 11204 partner across has a road T 39 (1,850) or a bend 11203 (438)
  as its other half (`data/scan2_cities.json`).
- **Everything else on an avenue half is a plain road piece shared with ordinary roads** (`data/bands_cities.json`,
  cells on avenue halves): T 39 4,438, X 43 1,672, bend 11203 >= 607 (avenue ends: two 11203 forming a U), rail
  crossing 69 300, highway crossings 11258 148 / 15098 138, slopes 31 108 / 11201 104 / 32 102 / 11202 48, straight
  29 78, wire crossing 67 14, rare junction pieces 11211 / 11213 / 11214 / 14030 / 11208 34. **11203 is the stock road
  curve**: 2,735 plain road corners against ~1,350 in avenue ends. These pieces cannot get one-way lanes without
  changing every plain road, so on an avenue they must become avenue-half VARIANTS written by a block.
- Junction shapes across the band (cells of the x- / z- half | the other half): road meets one side only (T 39 on the
  near half, 11204 on the far half) 2,996; road crosses both halves (43 | 43) 1,344; T 39 on both halves 1,356; T + X
  548; end bend + something 611; rail 69 | 69 259; slopes ~300; highway crossings 206.
- **The stock curve library has one straight curve per direction per lane position** ((0,80) -> (255,80) and
  (255,175) -> (0,175), several keys each); a second lane in the same direction ((255,80) -> (0,80) or (0,175) ->
  (255,175)) has no curve: the rework needs new VPathAtt curve shapes (as hwave / hwx do), so a shape grant.

## 2. Direction rule (right-hand traffic, the highways' side)

A car on a half drives with the median on its left: travel direction of a state-s half = world side (s - 1) mod 4
(state 1 -> -z, 3 -> +z, 2 -> +x, 0 -> -x). It matches the highways (Seoul: x 244 = 73.2 runs -z, x 245 = 73.0 +z;
row 108 runs +x, row 109 -x). In the state-0 frame both lanes of a half run x+ -> x- at z 80 and z 175, and the turn
matrix is the single entry x+ => x-; the game rotates the stored matrix per state, which gives exactly the rule above
for all four states (R(x, z) = (-z, x): x+ => x- becomes z+ => z- at state 1, x- => x+ at 2, z- => z+ at 3).

Turn matrix: low half x+ => x- (the half's direction), high half its transpose x- => x+, because the tiler counts a side
as an arm when either half has a bit there and every stock mask has high = transpose(low) (311 of 311, NET_LANES.md 1.2);
an empty low half would mean "unconstrained" to LANEDENSITY (sc3netmod_lanes.c:161). The router reads the low half.

## 3. Who reads what (survey of NET_LANES.md, LANE_DENSITY.md, HIGHWAY_TRIPS.md, CAR_TRIPS.md, NETPACK.md)

| reader | reads | consequence for one-way halves |
|---|---|---|
| STRTSIM cars (stock and sc3cartrips route cars) | TrBlkAtt lanes, per state, per language | new lanes are enough for the animation |
| stock tiler | props 310 only (arms) | keep high = transpose(low), arms stay |
| SimTransit router, road nodes (type 1 / 0x41) | nothing: ring scan, every road cell around is a candidate (`[CONFIRMED @ SimTransit 0x1000755e]`) | **a stock props-310 edit alone changes no trip**; trips keep walking a half both ways and hopping between halves |
| sc3netmod LANEDENSITY (default mode 1) | props 310 of VARIANT pieces only (`g_base[id] != 0`); exits = the row of the entry side, wrong-way entry fails, per-trip refused list (LD_TRIPMAX 32) | honours avenue-half variants; stock 11204 needs a variant or a small honour list (mode `all` honours every stock piece and changes stock routing everywhere: Berlin 4.5% of road steps forbidden by stock matrices) |
| RAMPFIRST | runs after LANEDENSITY's closes, never reopens a lane-closed side | no conflict |
| sc3cartrips corridor solver | the lanes in game memory | follows the new lanes by itself; today's failures are hops between halves (Berlin 362 of 368) |
| save | id + state per cell | lanes are not saved; variants save as their base (rb_save_id) |
| game without sc3netmod | stock files (the overlay is served only by sc3netmod's file hooks, NETPACK.md 3) | stock two-way avenues, same city |

Overlay feasibility: a netpack `lanes` / `connects` entry for a STOCK id replaces its TrBlkAtt records and its exemplar in
copies of the containers (`netpack_lanes.py`, done once for piece 39 by `example_lanes_t_exit_only`); one package per
piece. Enough for the lanes and the tiler; not enough for routing (row above). Mod pieces built with `copy_base` from
11204 (avx noses 20810/20811, bvx noses 20910/20911, DAV 20558/20559/20567/20574) copy the STOCK records at build time,
so each needs its own lanes entry; rbt9 and DAV templates write plain stock 11204 next to their blocks (rbt9.c:111,
dav.c:216-221).

**Decision: do not override stock 11204; write a one-way VARIANT of it.** An overlay edit of stock 11204 would make every
avenue one-way, including bands the rule must leave two-way (a refused band would then mix one-way 11204 cells with
two-way road pieces and strand cars at every border). A variant (base 11204, saved as 11204) written only on converted
bands avoids that, is honoured by LANEDENSITY in its default mode (no honour-list code), and leaves a game without the
mod exactly stock. Cost: one variant cell per avenue cell (Berlin 3,904, London 5,067): the load pass, the save section
and every block's capacity limits must take that many (the HWY_MAXP lesson, project-highway-program).

## 4. Inventory: every piece that carries an avenue half

| piece | owner | today | change |
|---|---|---|---|
| 11204 straight half (26,752 cells) | stock | 1 lane each way, matrix two-way | NEW variant (2 one-way lanes, new curves, one-way matrix) written by the band block on converted bands; stock 11204 itself is NOT edited (see below) |
| 11203 bend pair = avenue end (~1,350 of 4,083 bends) | stock, shared with road corners | two two-way bends | NEW variants: two-lane U-turn half to half (written by the band block, saved as 11203) |
| 39 T on a half (4,438), 43 X on a half (1,672), T+X, T on both halves | stock, shared | plain road junction per half, halves never link | NEW junction variants with a median opening and every turn (AVX boxes already cover avenue x avenue / avenue T / road x avenue / road T: rework their lanes; the road-meets-one-side T needs a box across both halves) |
| 69 rail, 67 wire, 11258 / 15098 highway crossings, 31 / 32 / 11201 / 11202 slopes on a half (~800) | stock, shared | two-way | NEW one-way variants with the base's art (lanes + matrix only) |
| 29 on both halves (avenue continuing as two roads, 78 cells), 11211-11214 / 14030 / 11208 (34) | stock, shared | two-way | refuse: the whole band stays stock two-way (rule below) |
| 20800-20804 avx boxes; 20810/20811 noses | AVX | stock style; noses copy_base 11204 | lanes rework (boxes: 2 in / 2 out per avenue edge, opening turns); noses: one-way lanes |
| 20900-20905 bvx boxes; 20910/20911 noses | BVX | stock style | as AVX |
| 20700 boulevard outer row (base 11204), 20750-20768 boulevard narrowing to an avenue | BV | 1 each way / road 29 fallback | outer row stays a boulevard (owner call: boulevards keep their lanes?); narrowing pieces get one-way avenue edges |
| 20500-20505, 20510-20524, 20530-20534, 20540-20594 diagonal avenue | DAV / diagx | 1 in + 1 out per edge per carriageway | lanes rework for the whole diagonal family (mid, junctions, merges, crossings) |
| 20950-21063 diagonal boulevard narrowing to a diagonal avenue (20972-20992) | DBV | copy_base | avenue-side edges one-way |
| 20603/20604, 20612, 20615-20618 rbt9 avenue arms | RBT9 | 1 in + 1 out at the arm edge | arm edges: 2 in from the incoming half, 2 out to the outgoing half |
| 21602/21603 straight transition ground row; 21604-21609 diagonal transition | HWAVE | crossover swap | straight lanes, no swap (the owner's original report) |
| avenue_markings (art of 11204 / 11203) | art | dashes | check the dashes sit between the two same-direction lanes; U-turn art for the end variants |

Band rule (new block): an avenue band = the two halves along an axis between two ends. Convert a band only when every
cell on it has a one-way form (11204, a crossing / slope variant, a junction box, an end U-turn, a transition); else
leave the WHOLE band stock two-way. Mixing one-way and two-way cells on one half strands cars at the border (lanes that
do not line up: the arrival node is found by position, NET_LANES.md 2.3; seen on hwdx's hand-offs, verify/hwcars).

## 5. Risks

| risk | why | how to see it / handle it |
|---|---|---|
| more failed trips | a trip can no longer walk a half the wrong way or hop to the other half; it must reach its direction at a junction or an end (router is a first-arrival walk with a 1,024 budget, HIGHWAY_TRIPS.md 1) | measurement M1 below, before any art |
| dead ends without a U-turn | a half that just stops (end not a 11203 pair, map edge, a T on one half at the end) leaves its lane with no way back | band rule: no U-turn form at both ends -> band stays stock |
| lots on the far side | a start node next to a half can only leave in that half's direction (LANEDENSITY gives a lot-entry node the union of its rows) | real-life behaviour; watch failed trips of lots on long avenues without openings |
| lane mismatch at band borders | arrival node found by position; two-way neighbours have one lane per direction at 80 / 175 | all-or-nothing band rule; every converted band ends at a piece the block authored |
| English-UK | TrBlkAtt is per language and English-UK files are mirrored (NET_LANES.md 4, `mirror_uk` on by default) while props 310 is one value for all languages | check what a mirrored one-way spec does under English-UK before building (likely: build UK unmirrored for one-way pieces) |
| LANEDENSITY cost | every honoured step runs the C path: measured +1.8..2.8% ms/trip for 16..29 k honoured steps; avenue halves were 18% of Berlin's road steps (404,335 of 2.2 M) | M1 also logs ms/trip (one game per arm is noisy: compare inside one game with `ld_alt.py` where possible) |
| refused-transition list | LD_TRIPMAX 32 per trip; many one-way cells may fill it ("trip list full" counter) | read the counter in M1 |
| RAMPFIRST | runs after the lane closes and never reopens them | no change expected; the straight transition becomes a plain one-way hand-off |
| cartrips | follows the lanes; its hop failures between halves should disappear once trips stop hopping | re-run the corridor success numbers after the build (not a blocker) |
| block capacity | tens of thousands of variant cells per city | each block's limits and the save section sized from the scan (London 5,067 avenue cells) |
| other packages' copies | copy_base pieces froze the stock two-way lanes at build time | each owner stream gives them one-way lanes |

## 6. Build split (proposed; new id grants, all clear of the ranges in use)

Free ranges found: piece ids 21700..21999 (after hwave's 21600..21699), lane curve shapes 23600..23999 (after hwave's
23400..23599). The existing streams' free sub-ranges (avx 20805..20849, bvx 20906..20949, DAV 20506..20509 /
20525..20529 / 20535..20539, bigrbt 20605..20649, hwave 21610..21699) stay theirs.

| stream | owns | ids / shapes | depends on |
|---|---|---|---|
| `avcore` (first) | the band rule block `sc3netmod_avl.c` (find bands, all-or-nothing, write / revert / save as base, load pass); the one-way straight variant of 11204; one-way variants of the crossings and slopes on a half (69, 67, 11258, 15098, 31, 32, 11201, 11202); the two-lane end U-turn pair replacing the 11203 pair; the new straight curves; markings check | pieces 21700..21749, shapes 23600..23699 | M1 result |
| `avjunc` | road x avenue X, road T on one side (box across both halves), T on both halves, avenue x avenue: median openings with every turn; reworks AVX 20800..20804 / 20810..20811 and BVX 20900..20905 / 20910..20911 lanes; stock junction pieces refused today (11211.., 14030) | 21750..21799 + avx / bvx own ranges, shapes 23700..23799 | avcore's lane positions |
| `avdiag` | diagonal avenue family (DAV 20500..20594, diagx crossings), DBV narrowing to a diagonal avenue, hwave diagonal transition 21604..21609 | DAV / diagx / diagbv own ranges + 21800..21849, shapes 23800..23899 | avcore |
| `avmisc` | boulevard narrowing to an avenue (BV 20750..20768) and the boulevard outer row question, rbt9 avenue arms, hwave straight transition 21602 / 21603 (no swap) | own ranges + 21850..21899, shapes 23900..23999 | avcore |

Shared-file rule as in the earlier programs: each block in its own file, a few marked lines in sc3netmod.c /
sc3netmod_rbt.c, every block named in the install gate.

## 7. Measurement first: M1, failed trips with one-way halves in routing only (no art, no new lanes)

Question: how many more trips fail when trips must follow the halves? Light, two games, Seoul copy (2,722 avenue cells,
known highway / avenue traffic from hwcars).
- Arm A: sc3netmod with `SC3NETMOD_LANEDENSITY=all` (every stock piece's matrix honoured), stock 11204 matrix.
- Arm B: the same plus a test package with one `connects` entry for stock 11204: low x+ => x-, high x- => x+ (no lanes,
  no art). Only 11204's matrix differs between the arms, so the difference is the one-way halves' effect on routing
  (the junction pieces stay stock in both arms, so B is a WORST case: no median openings yet).
- Read monthly: trips routed, failed (+0xb4) and the failed ratio (+0xb8) as hwtraffic_probe.py does, plus
  sc3netmod.log's wrong-way fails / arrivals refused / trip list full, 12 sim months each at speed 4.
- Decision: if B's failed ratio stays within A's monthly range, go; if it rises clearly, the junction openings and ends
  (avjunc) carry the fix and M1 repeats after them.
This test package is a measurement tool only; it must not ship (it would make every avenue one-way, see section 3).

## 8. Owner calls

1. Right-hand traffic like the highways (default). 2. Boulevards: keep their own lanes, or also two lanes one way per
outer row? 3. A band the rule cannot convert (avenue turning into two parallel roads, rare junction pieces) stays
two-way: acceptable? 4. English-UK: drive on the left there too (mirror) or right everywhere?
