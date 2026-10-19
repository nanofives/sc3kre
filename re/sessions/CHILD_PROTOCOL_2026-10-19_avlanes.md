# Child protocol, 2026-10-19: the avenue lane rework (2 lanes each way, 3 on boulevards)

You are one child of the orchestrator session titled **"SC3 avenues merged; highway intersections + diagonal"** (find it
with `mcp__happy__list_peers`). Owner request (2026-10-19): "i want avenues to follow the lanes logic in real life,
avenues are 4 lanes, 2 on one side, 2 on the other, we need to rework avenues to allow for that", and "3 wide avenues
need replanning as well". Owner decisions: **right-hand traffic everywhere (English-UK included, no mirrored lanes)**;
**an avenue the mod cannot convert whole stays stock two-way**; boulevards (3-wide) become 3 lanes each way.

THE PLAN IS `verify/avlanes/PLAN.md` (sections 1-9) with M1 in `verify/avlanes/RESULTS.md`. Read it first; it holds the
inventory, the half -> direction rule (11204 state s: the half's median on world side s, traffic runs toward world side
(s-1) mod 4), why a stock override is not enough (block-written one-way variants, saved as the stock base), and the risks.
Owner sheets: `MAIN\verify\avlanes\owner_shots\avlanes_plan.png`, `avlanes_3wide_plan.png`.

Rules otherwise as `re/sessions/CHILD_PROTOCOL_2026-10-18_highways.md` sections 1-4, 7-10 (worktree + hard-linked test
tree per stream, claude2 policy: no git add / commit, the orchestrator commits by path; launch via cmd //c or pwsh -c;
never kill by name, only your own PID; always windowed; light testing; owner reviews pictures; STATUS file
`MAIN\re\sessions\STATUS_<name>.md`; message the orchestrator at every milestone). Reuse the established tools: lanekit /
netpack_lanes (lanes, turn matrices, `"mirror_uk": false` for right-hand English-UK), the LANEDENSITY block (default mode
enforces variants' matrices: that is what makes one-way halves real for trips), the scene painters (diagave_paint,
boulevard_paint, avenue_markings, lanelines), hwtraffic_probe.py / hwtrips_probe.py / ld_alt.py for routing numbers.

## Streams, ownership and ids (no two streams own the same piece)
| stream | owns | piece ids | lane curve shapes |
|---|---|---|---|
| `avcore` (FIRST, publishes the base) | the band rule block `sc3netmod_avl.c` (find avenue bands, convert all-or-nothing, write / revert / save as base, load pass, claims so BV / DBV / other blocks' cells are left alone); the one-way straight variant of 11204; one-way variants of the crossings and slopes on a half (69, 67, 11258, 15098, 31, 32, 11201, 11202); the two-lane end U-turn replacing the 11203 pair; the new same-direction lane curves; the LANEDENSITY per-trip refused list size (M1 overflowed it); routing speed check | 21700..21749 | 23600..23699 |
| `avjunc` | road x avenue X, road T on one side (a box across both halves), T on both halves, avenue x avenue: median openings with every turn; AVX 20800..20804 / 20810..20811 lanes; stock junction pieces refused today | 21750..21799 + AVX free 20805..20849 | 23700..23799 |
| `avdiag` | the diagonal avenue family (DAV 20500..20594, diagx crossings), the hwave diagonal transition 21604..21609 | 21800..21849 + DAV free sub-ranges | 23800..23899 + 25000..25499 (granted 2026-10-19) |
| `avmisc` | big roundabout (rbt9) avenue arms, the hwave straight transition 21600..21603 (no lane swap any more) | 21850..21899 + bigrbt free 20605..20649 | 23900..23999 |
| `bvlanes` | ALL boulevard pieces: BV 20700..20768 (outer, middle, caps, tapers, junctions 20710..20712, narrowing to an avenue 20750..20768), BVX 20900..20911, DBV 20950..21063 (its narrowing to a diagonal avenue meets avdiag's pieces: agree the edge with avdiag) | 21900..21949 + BV / BVX / DBV free sub-ranges | 24000..24999 (24200..24999 granted 2026-10-19) |

**avcore publishes, the others merge.** avcore states its base API (how a block asks "is this avenue converted, which
direction does this half run", how other blocks' pieces join the one-way convention, the lane positions and curve
numbers for one-way halves) in `re/analysis/AVENUE_LANES.md` and messages "published". The orchestrator commits it on
`child/avcore` and merges it into your branch. Until then: inventory your pieces, design the new lanes and junction
layouts, draw the plan picture (milestone 1), and do NOT edit the shared files avcore owns
(sc3netmod_avl.c, AVENUE_LANES.md). Change requests to avcore go through `mcp__happy__send_to_session` (cc the
orchestrator).

## Milestones
1. **Plan** per stream: your pieces, their new lanes (one direction per half, right-hand), turn matrices, what changes
   in art (usually nothing: the markings already show the lanes; median openings at junctions may need art), the rule,
   refusals; a picture `MAIN\verify\<name>\owner_shots\<name>_plan.png`; message "plan ready".
2. **Build** on avcore's base: lanes + matrices + any new pieces, block changes, offline check, one in-game check (a
   populated city copy where traffic shows: Seoul works, hwcars' tools in re/tools/netmod/hwcars_*.py track cars;
   check routing with the probes and that cars keep their lane through your pieces), save + reload, a game without the
   mod loads stock pieces, sheet `<name>_sheet.png`, `verify/<name>/RESULTS.md`, files to commit; message.
