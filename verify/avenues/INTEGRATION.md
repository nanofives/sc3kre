# Avenue program: integration on round/avenues (2026-10-18)

Branch `round/avenues` (worktree `Simcity_wt_avenues`): child/diagave + child/avx + child/boulevard + child/bigrbt.
Streams and protocol: `re/sessions/CHILD_PROTOCOL_2026-10-17.md`; each stream's evidence in `verify/<stream>/RESULTS.md`.

## Merge notes
- The shared files (`sc3netmod.c`, `sc3netmod_rbt.c`, `netpack.py`, `netpack.schema.json`) conflict on every merge:
  each block adds a table-line skip, an `#include`, forward declarations, an `rb_file` dispatch, edit / load calls, an
  install gate term and reset terms. Resolution keeps every block.
- Trap found in the bigrbt merge: git auto-merged part of `rbt_install`'s gate, so hand-numbered conflict
  resolutions landed one block off. The result built, but a reset line ran after hooking and switched off DAV's
  middle pieces, AVX and RBT9 (log: `diagonal avenues on (inner 0 0 0)`, no `rbt9:` / `avx: ... on` lines). Fixed by
  rewriting the install tail; a check that every branch's added hook lines survive in the merged files now runs
  after each merge.

## Combined game check (Simcity_stock_diagave, all five packages installed)

| Check | Result |
|---|---|
| Install diagonal_avenue, avenue_junctions, boulevard, big_roundabout, avenue_markings | TrBlkAtt.IXF grew: 1,069 slots, first payload 0xa004 (ixf_insert growth, f92c5c9) |
| DLL start | `avx: avenue junctions on`, `rbt9: automatic 3x3 roundabouts on`, `diagonal avenues on (inner 20500 ...)`, boulevard tables read |
| 3x3 block with avenue arms W and N, a road E, two roads S | `rbt9: edit: (107,97) -> 3x3 roundabout, 4 avenue arm cell(s), 9 cell(s) written` |
| Boulevard along x with a crossing road | `bv: edit: boulevard axis 0, columns 11..23 at row 47, 39 cell(s), 30 written` |
| Save, reload | 48 variant tiles written as base / all 48 restored; every block's load pass wrote 0 |
| Exceptions | 0 in both games |
