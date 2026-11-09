# Round 2026-11-09: remaining two-way avenue ends (groups B, C, A, E)
Orchestrator: "Avenue cars driving wrong direction". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace made from main dbd65a0
(released as sc3mods-2026-11-09: AVP off by default, avenue_markings gone, group D in, see verify/mods_release_1109).

| stream | owner report | expected |
|---|---|---|
| avends | 2026-11-09: cars drive against the lanes on avenues; owner chose "convert more avenues", D done, then "Start the next avenue groups (B, C, A, E)" | the remaining refused avenue ends on the owner's Big One convert to one-way halves where a correct one-way layout exists; the rest stay two-way (stock look) with the reason logged |

## Background (read first)
- `verify/avdiamond/RESULTS.md` (group D: how AVX/AVL were extended, avjunc_rule.py twin, avdiamond_diff.py offline diff,
  avdiamond_trips.py routed-trip recorder, lab traps), `verify/avdir/RESULTS.md`, `re/analysis/AVENUE_LANES.md`,
  `re/harness/src/sc3netmod_avl.c` / `sc3netmod_avx.c`, memories `project-avenue-lanes`, `project-avpaint-cornert`.
- AVL converts a band whole or not at all. A band stays two-way when an end row is not a U-turn pair, corner or avlj join.

## Your cases (owner's newest Big One 1024 save: `tree\Cities\BigOne_owner.sc3` = MARIANO-PC "Big One (auto 5 min).sc3",
pulled 2026-11-09 after the release; `-City BigOne_owner.sc3`)
Census of the old save (20 refused ends; D's 8 are done). Re-derive the exact cells from this save's log
(`avl: load: band ... stays two-way`) first, the owner may have built since:
- **B** (4 ends): avenue T avenue with a road continuing across.
- **C** (2): avenue under highway 11258 with a ramp T 39 beside it (not caught by D's ramp rule, find out why).
- **A** (2): U-turn / end with a road T on the last row, or an avenue ending into diagonal road 35.
- **E** (1 spot, 2 bands): one-cell 11225 stub T between slope rows.
- **(584,108)/(584,109)**: avenue shifting one column where a diagonal avenue arrives; it holds the 584 rail row and the
  585..597 x-avenue two-way. Include it if the design is clean, else report why not.
- Note: (608,134) in this save may still be cut (owner re-drag pending). Do not count that chain as yours.

## Deliverable
1. Per group: cause (which check refuses, log line), then a design (cells -> pieces, half directions vs the stock T/X lanes,
   AVENUE_LANES.md 2). Message the orchestrator with the designs BEFORE building art. Order is yours; say it.
2. Build per group behind its own switch `SC3NETMOD_<NAME>=0`: lanes + art + table lines, selfblock 0, netpack validate
   0 errors, English and English-UK lane checks. Offline diff over the 15 shipped cities + owner save: 0 changes outside
   the group's cases.
3. One in-game check on the owner's save per group: bands convert (log), routed trips per half in its direction, save +
   reload keeps it, no-mod load is stock. Pictures in `verify/avends/owner_shots/` (do NOT git add them, public repo).
Light testing (memory `feedback-light-testing`). Report at each group done; I commit by path at each milestone.

Grants: piece ids 20900..20999, shapes 26000..26499 (check both against the installed tables before use; if 26000.. is
taken by the wall-lighting twins, take the first free 500 above 25508 and say which).
Package art lives only in your worktree until release: never delete it.
Do not change behaviour outside these groups.
