# TILER_SIM.md - the offline network retiler (re/tools/netmod/tiler.py) and the `netrules` tool

2026-10-13, branch child/netrules. SIMNTWRK.DLL, image base 0x10000000, Ghidra VAs. Companion notes:
`NETWORK_RULE_ENGINE.md` (the engine, first trace), `formats/TILINGRULES.md` (file format), `NETPACK.md` (packages).

`tiler.py` re-implements the retile pass, `FUN_1001547b`, and the in-game rectangle retile around it, on a city
loaded from a save. `netrules.py` drives it: `validate`, `explain`, `preview`, `apply-edits`, `lint`. It is read-only
on the game install.

**Verdict.** Over the 16 shipped cities a from-scratch re-tile reproduces the saved tiles (id and state) for
ROAD 99.83%, RAIL 99.74%, HWAY 99.71%, PIPE 99.91%, SUBW 99.80%, POWR 91.54% (table in section 9; 237 of POWR's
263 disagreements are pole placement, which depends on the order of past retiles). One in-game
check (`verify/netrules/RESULTS.md`): an edit predicted by the simulator changed exactly the 22 predicted tiles in
the game, the stock control arm changed none.

Function bodies read for this note in the 2026-10-13 relaunch are marked **[read]**. The rest were implemented by the
earlier child from its own reading and are measured only through the validation table.

## 1. Entry points and the node list

| what | function | notes |
|---|---|---|
| GZ message `0x637c0dab` | `FUN_10013afe` [read] | `{0x637c0dab, mask, x0<<16 \| z0, x1<<16 \| z1}` -> rect `{x0<<8, z0<<8, 0, x1<<8, z1<<8, 0}` -> manager vt+0xb0 |
| rect retile | `FUN_100151f1` [read] | clips the rect to the map (`FUN_1000aa47` with manager +0x50). Mask bits 1\|2: HWAY then ROAD, ROAD over the rect grown to HWAY's work-list box (`FUN_10005fad`, skipped for an all-zero box); 4 RAIL, 0x20 POWR, 8 PIPE, 0x10 SUBW |
| node gather | `FUN_10016a25` [read] | grows the rect by e = 2 when `netType & 0x12` (RAIL, POWR, SUBW), else 1 (`FUN_1000aa9a`), clips, then collects only the **four border strips** (width e+1) in the order: bottom, left, right, top, x outer, z inner, duplicates kept. A node is an occupant passing the net's positive predicate. The flood fill of `FUN_1001547b` reaches the interior |
| drag / build | `FUN_10014a23` | not modelled (bridge path, funds, HWAY's second ROAD pass). Water tiles of a line come from here |

`tiler.Tiler.rect_nodes` / `retile_rect` reproduce the three [read] functions. Coordinates: x, then z (the save's
second network coordinate, `tiler.py` calls it y).

## 2. The manager's layers, `FUN_10012609` [read]

| field | from city vtable | used as |
|---|---|---|
| +0x3c | vt+0x11c | ROAD / RAIL / POWR / HWAY layer. It is the city's occupant manager, so **buildings are in it** |
| +0x40 | vt+0x120 | PIPE layer |
| +0x44 | vt+0x124 | SUBW layer |
| +0x30 | vt+0x13c | terrain (heights, water, flatness) |
| +0x34 / +0x38 | vt+0x14c / vt+0x15c | side tables (commit writes +0x34 for ROAD/RAIL/HWAY) |
| +0x48 | vt+0x18c | neighbour connection at the map edge (`vt+0x58(net, x, z)`) |
| +0x5c / +0x60 | (vt+0xcc - 1)<<8, (vt+0xd0 - 1)<<8 | map bounds |

Consequence for the model: a building next to a road is an occupant in the surface layer. It fails the positive
predicate and passes the negation, so the collector reports it as `id 0, state 0` ("foreign"), not `state 5`
("empty"), and a rule that would write a result onto it is refused (section 5). `netrules.prepared()` puts every
building of the save's occupant section `0xa0ab89f0` into the surface layer with flags 0 (`Options.buildings`).
Measured effect: ROAD +0.02% over five cities. Flags 0 and 0x400 give the same figures; which flags a building
really carries is `[UNCERTAIN]` (no class read).

Buildings in the other layers, measured, not decoded (`tiler.STATIONS`, `Options.stations = "utilities"`):
- subway stations (occupant type 12360, 12361) in the SUBW layer with flags 0x40100, the value `FUN_10019768`
  tests for SUBW in the final stage [read];
- water utilities (12810 Water Pump, 12820 Water Treatment Plant, 12830 Desalinization Plant, 12840 Water Tower) in
  the PIPE layer with flags 0x800000. PIPE agreement 98.85% -> 99.91% over the 16 cities. Before the change, 126 of
  Berlin's mismatched pipe arms pointed into those four building types (109 into pumps).
`[UNCERTAIN]` how they get into those layers and their real flag words: no code read. A live read of city
vt+0x120 / vt+0x124 at a pump / station cell (class, vt+0x3c(0x800000), vt+0x74) would settle it.

## 3. `FUN_1001547b` step by step [read]

Per netType the function loads the three rule stages, the layer and the predicate triple (positive A, negation,
crossing; `NETWORK_RULE_ENGINE.md` 5), plus two flags: "side table" (ROAD/RAIL/HWAY) and "underground"
(PIPE/SUBW, skips the water check).

1. **HWAY drag direction.** netType 4: (dx, dz) from the first two nodes.
2. **Flood.** Per node, window [x-r, x+r) x [z-r, z+r), r = 5 for ROAD/HWAY/SUBW, else 2. A cell is "occupied" if
   it is a node (`FUN_100162f5`) or holds an occupant passing predicate A. 8-connected flood from the node, at most
   32 iterations (horizontal then vertical pass, in place). Every flooded cell goes to one list.
3. **Sort + unique** (`FUN_1001b7cc`, comparator `FUN_10021213` [read]: x, then z; `FUN_1001bba6` unique).
4. **Crossing pre-pass.** For each node in node order, with a toggle flipped per node: an occupant with the surface
   flag 0x800 (`DAT_100323d8`) goes to `FUN_100167d4`; hits are "changed".
5. **Removal.** Each flooded cell holding a predicate-A occupant: not Protected (`FUN_1001a7f7`) and removable
   (vt+0x74) -> removed and added to the work list; Protected under POWR -> kept in a separate list (POWR only).
6. Nodes appended to the work list, sort + unique. Work cells whose occupant is a Protected predicate-A piece
   leave the work list.
7. **Slope split.** Cells that are not flat (`FUN_10016ccd`) but a legal slope (`FUN_10016d00`) form the slope list.
   `list70` = the whole work list (slope cells included) is the "pending" list; `list74` = POWR's kept Protected
   cells + the work list. Slope cells leave the work list.
8. **Slope pass.** A flag starts at `!(dx+dz < 0)` and flips per slope cell; `FUN_1001a2c0` gives one piece per
   slope row, committed through `FUN_100165d8`.
9. **Simple** (mode 8) over the work list, repeated while the list shrinks (cells that changed leave it).
10. **Complex** (mode 0x18) over `list74`, at most 5 passes, until a pass changes nothing.
11. **final** (mode 4) once, over the work list plus the deferred list.
The function hands back the box of the work list of step 6 (used by `FUN_100151f1`).

## 4. Per-cell evaluation, `FUN_10016327` [read]

Per cell of the list it is given: skip unless flat; collect the neighbourhood (section 6); first matching rule
(section 7); zero results -> skip. Then each result: out-of-map targets are skipped, an in-map target must be flat,
and its occupant must pass predicate A or the crossing predicate, and must not be Protected unless the result is
`id 0 state 5` (POWR exempt from the Protected test). Any failure refuses the whole rule. Else commit, and each
target goes to "changed", except `id 0 state 0` targets, which go to the deferred list for the final stage.
**Result dirs are not checked against the stage mode**: a result may write any of the 24 dirs in any stage.

## 5. Commit, `FUN_100165d8` [read]

Refused outright when the centre is water and the net is not underground (`FUN_10016d69`). Per result: id 0 ->
remove the occupant if removable; else build `factory(0xc14f8955, id, state)`, set its height from the terrain,
insert; if the cell is taken and the incumbent passes A or the crossing predicate and is removable, remove it and
insert again. The return value is the last insert's result; only the slope pass uses it.

## 6. The collector, `FUN_10019768` + `FUN_1001a056` [read]

**Modes 4 and 8 (final, Simple): 3x3, occupied cells only.**
- Mask bit d is set for a neighbour passing predicate A when d < mode. In the final stage (mode 4) for ROAD, RAIL,
  SUBW the bit also needs the neighbour's connectivity (`FUN_1000d73d` via interface `0x41658d28` vt+0x4c, selector
  0 / 1 / 2, "from" = (d+2) mod 4), except a SUBW occupant with flags 0x40100 (stations), which sets it directly.
- Every pending-list cell within 2 cells that is empty or fails A also sets its bit when d < mode, so in practice
  only the 3x3 ring (dirs 0..7).
- Map edges: x == 0 -> dir 0, x == W-2 -> dir 2, z == 0 -> dir 1, z == H-2 -> dir 3, each only if the +0x48 edge
  connection says so.
- Records: one per occupied cell. A predicate-A occupant -> its id and state through Convert (`FUN_1001a85a`), with
  its dir. Anything else -> `id 0`, state 5 if it passes the negation and has flag 0x400, else state 0, and **its
  dir stays 0x1f (self)**: `FUN_100220b7` initialises dir to 0x1f and `FUN_1001a056` only sets
  it for predicate-A occupants. So in these stages a condition `(d != self, id 0, ...)` can never be observed.

**Mode 0x18 (ComplexRules): 5x5, every cell, no mask.**
- The mask is never written: it is 0 for every Complex evaluation. A Complex rule fires only with selector 0x100
  (or 0). Every shipped Complex rule uses 0x100 (`NETWORK_RULE_ENGINE.md` 4.4).
- Every one of the 25 cells yields one record with its dir: off-map -> `0/5` (or `0/1` at the edge dir when the
  edge connection holds); empty -> `0/5`, or `0/1` when the cell is in the list being evaluated (`list74`); occupied
  -> as in modes 4/8 (Complex_Convert table), then `0/5` becomes `0/1` if the cell is in that list.
- Complex runs over `list74`, which holds every work cell, also those Simple already built and the slope cells, and
  repeats up to 5 times while something changes. That is how Complex rules see and rewrite what Simple placed (POWR
  poles, `pole-phase` below).

## 7. Matching and the parser [read]

`FUN_100228ff` walks the loaded rule sets, then rules in file order; `FUN_100222f9` takes a rule whose selector is
0x100 or equals the mask; `FUN_10022246` needs every condition present (`FUN_100220c5`: same dir, id, and state,
where a condition state 0 also accepts an observed 5). First match wins. The parser `FUN_10022676` stores one rule
per `1,` record when its result count is reached; a rule declared with `4,0` is never stored and its conditions run
on into the next rule. Convert tables: last matching row wins (`FUN_1001a85a`).

## 8. Implemented but not re-read in this relaunch

`FUN_1001a2c0` (slope tables 0x1003195c.., POWR every-5th-cell variant, HWAY toggle), `FUN_100167d4` (crossing
matrix 0x100318ac and its id switch), `FUN_1000cd35` / `FUN_1000d73d` (connectivity: exemplar properties 310 / 311 /
312 of `{0xE223741F, 0xA317745F, id}`, permutation table 0x1003123c; live-read by the earlier child, it disproved
`NETWORK_RULE_ENGINE.md` 14.6), `FUN_10016d00`, `FUN_10016ccd`, the crossing predicates `FUN_1001ab26/ac2b/abb2/acbe`.

## 9. Validation (from-scratch retile of each net vs the saved tiles, id and state)

`py -3 -m netmod.netrules validate <saves> --csv out.csv` (run from re/tools), default options (exemplar
connectivity masks, utilities, buildings in the surface layer). One FUN_1001547b call per net whose nodes are every
tile of that net, compared with the saved tile.

| saves | net | tiles | id+state agree | disagree | disagreements by class |
|---|---|---:|---:|---:|---|
| 16 shipped cities | ROAD | 121245 | 99.83% | 211 | arm-missing 114, water 31, diag 20, interior 19, gap 12, arm-to-empty 9, slope 5, near-slope 1 |
| 16 shipped cities | RAIL | 10634 | 99.74% | 28 | water 24, arm-missing 2, edge 1, diag 1 |
| 16 shipped cities | HWAY | 14677 | 99.71% | 42 | interior 21, arm-missing 13, near-slope 8 |
| 16 shipped cities | PIPE | 69121 | 99.91% | 60 | arm-to-empty 30, arm-to-building 7, water 7, near-slope 4, gap 4, edge 3, arm-missing 3, slope 2 |
| 16 shipped cities | SUBW | 17536 | 99.80% | 35 | arm-to-building 10, interior 9, gap 9, arm-to-empty 5, diag 2 |
| 16 shipped cities | POWR | 3109 | 91.54% | 263 | pole-phase 237, arm-to-empty 8, slope 5, arm-to-building 4, edge 4, near-slope 3, interior 2 |
| Berlin | ROAD | 17226 | 99.76% | 42 | arm-missing 31, diag 4, interior 3, arm-to-empty 2, gap 2 |
| Berlin | RAIL | 632 | 100.00% | 0 | - |
| Berlin | HWAY | 1558 | 100.00% | 0 | - |
| Berlin | PIPE | 6425 | 99.88% | 8 | arm-to-building 5, arm-to-empty 1, near-slope 1, gap 1 |
| Berlin | SUBW | 1232 | 98.54% | 18 | arm-to-building 6, interior 5, gap 5, arm-to-empty 2 |
| Berlin | POWR | 96 | 80.21% | 19 | pole-phase 18, arm-to-empty 1 |
| Europolis 1024 test city (`--seam 256`) | ROAD | 152848 | 99.80% | 304 | seam 304 |
| Europolis 1024 test city | PIPE | 104480 | 99.91% | 96 | seam 96 |
| Europolis 1024 test city | SUBW | 95216 | 99.70% | 288 | interior 112, gap 64, arm-to-building 64, seam 48 |
| Europolis 1024 test city | POWR | 992 | 90.32% | 96 | seam 48, arm-to-building 32, arm-to-empty 16 |

The 1024 city is 16 copies of Europolis (256). Most non-seam counts are exactly 16x the 256 city's (POWR
arm-to-building 2 and arm-to-empty 1, SUBW gap 4 and arm-to-building 4). SUBW interior is 112, not 16 x 4 = 64: 48
interior tiles exist only in the copy. Not examined `[UNCERTAIN]`.

Progress over the relaunch (same 16 cities): PIPE 98.85% -> 99.91% (utilities), ROAD 99.81% -> 99.83% and HWAY
99.65% -> 99.71% (buildings in the surface layer). POWR did not move: 237 of its 263 disagreements are pole
placement, which a save cannot determine.

### Disagreement classes (first that applies; `netrules.CLASSES`)
| class | what is observed | why it is not a simulator error |
|---|---|---|
| water | tile on water | commit refuses a water centre; these tiles come from the bridge path (`FUN_10014a23`) |
| slope | tile not flat | slope table / illegal slope, outside the rule stages |
| seam | next to a multiple of 256 in the 1024 test city | the city is a 4x4 copy of a 256 city; cut pieces keep arms into their old neighbour |
| pole-phase | POWR 14/15 positions differ inside a straight pole run | poles are placed 4 cells from any pole or non-straight piece in work-list order (Complex #20-36, #44-60), so they record the order and extent of past retiles |
| edge | map edge row or column | edge connection input (+0x48 vt+0x58) modelled from the save's neighbour-deal cells `[UNCERTAIN]` |
| arm-to-building | the saved piece has an arm into a building cell with no network piece | `[UNCERTAIN]` history: a building placed on the line's next tile, without a retile of the piece. Test: place a park on a line end and read the neighbour |
| arm-to-empty | the saved piece has an arm into an empty cell | same, with the neighbour bulldozed |
| arm-missing | the saved piece lacks an arm toward a network neighbour the simulator connects | `[UNCERTAIN]` one case read: `explain` on Berlin ROAD x=64 z=62 (saved 29/1, simulated 11204/3) shows Complex rule #44 matching a neighbourhood that still holds a pending cell, so the outcome depends on evaluation order |
| diag | a DIAG_Set piece in the 3x3 | diagonal drags (`FUN_1001da5f` / `FUN_1000abde`) are not modelled |
| gap, near-slope, interior | no mechanism identified | the honest residue |

## 10. `netrules` commands

- `explain <save> <x> <z> [--net]`: re-tiles the net with a trace limited to that cell (events at it, and rules at
  other cells that write it), prints the saved 5x5 neighbourhood, each stage's mask, observed records, first match
  (file, rule number = stock index, line), commit or refusal reason, and the class if the result disagrees.
  Examples: `verify/netrules/explain_farmsville_road_100_128.txt`, `explain_farmsville_powr_9_94.txt`.
- `preview <rules dir> <save> [--rect x0,z0,x1,z1] [--out map.png|map.txt]`: tiles that differ between the stock
  rules and the given directory, from a whole-net retile or from the in-game rectangle retile.
- `apply-edits <manifest...> [--save city]`: merges every manifest's `rule_edits` (variants' Set membership first,
  like netpack install) and applies them with `netpack_rules.apply()`, the single implementation, into a copy;
  lints the result against stock; optionally previews it. Variant ids borrow their base's connectivity masks (netpack
  copies the base exemplar, `newpiece.py` step 1).
- `lint [--rules DIR] [--base DIR] [--all]`: findings by severity and kind, from `rulecheck.py` (shared with
  netpack, section 11). Stock: 0 ERROR, 75 WARNING shadowed (a rule an earlier rule always pre-empts), 440 INFO
  duplicate (same conditions in another order, harmless), 0 never-matches, 0 unknown-id, 0 misparse, 0 bad-value.
  Exit 1 only on ERROR (before 2026-10-13 `netrules` never passed its return code to the shell, so it always exited 0).

## 11. One rule checker: `rulecheck.py` (done 2026-10-13, child/packlint)

The three asks to `netpack_rules` are closed. Its own `lint()` is gone: `netpack validate / build / install`,
`netrules lint` and `netrules apply-edits` all call `rulecheck.lint_rules` (bounds from this file's `tiler.py`), so
the two tools report the same finding for the same input (netpack selftest U7). Severities and kinds:
`NETPACK.md` 4.1.

- A result dir >= the mode is legal: `FUN_10016327` reads the result's dir through `FUN_1002205c` and checks the
  target cell (in map, flat, predicate A or crossing, not Protected), never the dir against the mode [read].
- A final-stage condition at dirs 4..7 is legal: the 3x3 collector of `FUN_10019768` reports every occupied cell of
  the ring, and `FUN_1001a056` sets its dir through `FUN_1002203e` with no mode test [read]. Only the MASK bit is
  gated, `(dir & 0xff) < mode` before `FUN_10022092`.
- A ComplexRules selector other than 0x100 or 0 is a WARNING never-matches: every `FUN_10022092` call (the only
  mask-bit writer) sits outside the `mode == 0x18` branch of `FUN_10019768` [read], so the mask `FUN_100222f9`
  compares is 0. The shadow check treats 0 and 0x100 as both matching there.

Engine facts added for the checks [read]:
- `FUN_10022676` (with its reader `FUN_10022552`, strtok over the file, isdigit then atoi per token) is a state
  machine, not a line parser: `2,N` goes to +0x18 and is never read back, a rule is stored when the `5,` count reaches
  the last `4,N`, and the selector is reset to 0 after each stored rule (`FUN_10022338`). A dir is kept as one byte
  (0xff -> 0x1f). `rulecheck.engine_parse` re-reads a file that way; all 18 stock stage files give exactly their `1,`
  records. `[UNCERTAIN]` the strtok delimiter string (a stack constant the export does not show): ',' CR LF assumed,
  the only separators in the shipped files and in what netpack writes.
- The table `FUN_1002205c` reads at `0x10032134` (2 bytes per dir) holds 24 real entries; entries 24..31 are zero
  bytes (offset 0, 0, so 31 = 0x1f = self), and from entry 32 (`0x10032174`) the bytes are other data (32 reads
  -1, +5). A rule record at a dir outside 0..23 / self is an ERROR.
- `[UNCERTAIN]` `FUN_10022552` reads the file into a 0x20000-byte stack buffer; the read length is not visible in
  the export, so a rule file over 128 KiB is unexamined (the largest shipped stage file, HWAY Complex, is 75,153 bytes).

## 12. Open
- Live read of the station / utility occupants in the SUBW / PIPE layers (class, flags, removable).
- `arm-*` classes: one in-game history test (building over a line end) would turn them from `[UNCERTAIN]` into a
  mechanism.
- The building flags (0 vs 0x400) and which occupants carry 0x400.
- `FUN_10014a23` (drag path) is the next piece for water / bridge tiles and HWAY's double pass.
