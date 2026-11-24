# lotgrow: non-square growables, research (round 2026-11-24c)

Static research only. Nothing built, nothing run in game. Full analysis with every address: `re/analysis/LOT_SHAPES.md`
section 11.

## Verdict

**Feasible with code in one layer: the zone developer's rule bodies.** Everything else on the growth path already
handles X and Z apart:

- the buildable block a rule receives is W x D, grown one column and one row at a time (FindBuildableRect SIMRCI
  `0x100332e4`, growers `0x10033525` / `0x10033611`)
- PlaceBuilding claims, checks and clears X x Z (`0x10032dfc`: vt+0x40 and vt+0x44)
- abandonment, re-occupation and construction-done re-place the same key at the origin (`0x10029a38`)
- the evaluator handles each building once, at its origin cell (`0x10028f12`, occupant vt+0xbc)
- drawing and the save field are LOTRECT's (sc3perf, LOT_SHAPES section 8)

The square sits in the 16 rule Apply bodies (rule vtable slot 0x1c): all read SizeInCellsX (vt+0x40) only and use it
for both axes, and none calls SizeInCellsZ. 9 of them are generic (3 distinct algorithms). 4 are fixed layouts that keep
stock behaviour and get no non-square members. The other 3 serve airports and seaports.

## Square assumptions (addresses in LOT_SHAPES 11.2)

| where | square because |
|---|---|
| 6 block-fill rules (`0x10026b01`, `0x10020762`, `0x10014794`, `0x100152a2`, `0x10013c66`, `0x1000c3eb`) | n = X for both bounds and the n x n grid fill |
| corners + strip + fill (`0x10027699`, `0x1000dd1a`) | corner offsets and the strip use n on both axes |
| com block `0x1000cf87` | n <= W and n <= D, n x n fill |
| fixed layouts (`0x1002a1af` row houses, `0x10011721` large lot, `0x10012661` L blocks, `0x100015ab` farm) | hard-coded steps or n-based patterns |
| load with the package removed (SIMINIT `0x1000c60c`, `0x1000cb3d`) | stand-in index holds only (n, n) and is asked for (saved X, saved X) |
| BAT list (SIMINIT `0x100053be`, SIMUI `0x1001bb56`) | filtered by X |
| tuning only: corner list `0x100274bb` (X >= 3), evaluator roll divisor (X) | X only |
| drawing and save field | X only, fixed by LOTRECT |

## What a w x d growable needs

1. C copies of the generic rule bodies that read X and Z, installed by rewriting rule vtable slot 0x1c, with square
   members on exactly the stock path and RNG order.
2. X < Z only, because a load without the package gives an X x X stand-in. With X > Z that stand-in overlaps the
   neighbour.
3. |X - Z| = 1 only (1x2, 2x3, 3x4, 4x5), because that is where LOTRECT's draw order is exact.
4. LOTRECT on.
5. Data: prop 0x66 (X, h, Z), LOTRECT-anchored frames, a family line in a family that only generic rules use, no
   layout-role attrib bits, not in `[ReplaceableBuildings]`.

## Size of the change

| option | code | risk |
|---|---|---|
| full (R, C, I generic rules) | 3 C bodies (about 520 lines), 9 `.rdata` slot writes, 1 switch | medium: runs on every develop call; gate = identical occupant layers with no non-square members, switch off vs on |
| **first step** | rule 0xa22653c0 only: 1 C body (about 120 lines), 1 slot (`0x1004ccb0` +0x1c); 1x2 and 2x3 in families 11 (3100) and 4 (3300), which no other rule uses | low |
| no code | model on the smallest square lot plus lot dressing (objprops) | none, costs density |

## Open (needed before or during a build round)

- Construction (state 4) and abandoned (state 2) art for a w x d growable: which sprite is drawn was not read
  `[UNCERTAIN]`. This is the first in-game look of a build round.
- Load of a save holding w x d growables with the package removed: X x X stand-in derived statically, not run.
- 180-degree turned w x d (large-lot rule only, not proposed) draws as slot r + 2 with LOTRECT: derived, not run.
