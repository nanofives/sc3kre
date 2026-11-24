# Round 2026-11-24e: build the style copies' lot colours (owner picks 2026-11-24)

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner picks (Happy question card, recorded in re/sessions/STATUS_stylepal.md "owner pick"):
- European and Asian copies (in a North American host): option c, lawn lightened and garden soil turned to lawn.
- North American copies (in a European / Asian host): option a, lawn toned to the host. Needs their own frame tables and
  about 10 MB of pixels: netpack_stylesets.py change.
- One art variant (tuned for a North American host), no per-host DATs.
- Per-id tuning: each copy matches its own base building's lawn, not the class mean.

## Stream stylepal (same child, opus / medium)

1. Build the recolour into the style_mix package build (netpack_stylesets.py / re/tools/netmod/examples/style_mix),
   reusing verify/stylepal/work/recolor.py as the reference. Done once at package build time, deterministic.
2. North American copies get their own frame tables + pixels, each copy pointed at its new table. Stock art and stock
   cities untouched (a stock European city still draws its own art).
3. Per-id tuning as picked. Measure the result the same way as the mock-ups (scene lawn L, lawn share, brown share) on
   the owner's Sacramento camera and on Moscow, and compare with the mock-up numbers.
4. In game in a dev tree: Sacramento style pick European (owner's camera) and Moscow North American, pictures, save /
   reload, a save with copies opened with the package removed. Package size and install time before / after.
5. Bump style_mix's version, netpack lint, the suite parts that cover netpack (CHILD_PROTOCOL suite modes), and the
   stage-source note for the next release (stage/src needs the package re-installed, as in verify/mods_release_1121).
   Results verify/stylepal/RESULTS.md (new section), STATUS_stylepal.md.

## Rules

EA set art only in dev trees, stage and gitignored verify folders, never in git or docs. Windowed game, never the real
mouse or keyboard, test slot, harness claim before game runs, kill only PIDs you started, delete BMP dumps, no git add /
commit.
