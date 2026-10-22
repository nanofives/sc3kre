# STATUS markings (2026-10-22)
Cause: 11203 is the stock plain-road curve (NET_ART.md, NET_LANES.md). avenue_markings reskinned 11204 AND 11203, so every road corner got white dashes.
Fix (worktree Simcity_wt_markings, branch child/markings): avenue_markings manifest reskins 11204 only; README updated. Avenue ends/corners keep dashes via avenue_lanes 21701/21726, which ship their own 11203-derived art (installed pack has art/11203).
Files: re/tools/netmod/examples/avenue_markings/{manifest.json,README.md}
Release: reinstall avenue_markings (netpack install ... --tree <tree>). avenue_lanes unchanged.
Not done: in-game before/after frames (shared tree install needs orchestrator OK).
Side effect: an avenue end/corner AVL does not convert stays stock yellow.
Test: own tree copy Simcity_stock_markings, game pid 16044 stopped. Verified frames in verify/markings/owner_shots. Extra file: verify/markings/RESULTS.md
