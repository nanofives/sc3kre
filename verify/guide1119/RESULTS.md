# guide1119 results (2026-11-19): the building guide brought up to date for players

Verdict: done. `docs/buildings/index.html` regenerated from `verify/bldpack/work/guide_template.html` (edited in place)
with `make_docs.py --wt dev/guide1119/wt --tree dev/guide1119/tree --zip <the 2026-11-18 sample pack release URL>`, so the
sample pack link is unchanged. Headless Chrome check 13 of 13 PASS (`guide_check.mjs`, log `guide_check.log`).

## What changed in the guide

New sections (and nav entries):
- **Real views for .bld files** (`#render`): what the kit is, where the next sc3mods zip puts it (`tools\bld_render\`),
  the steps (folder of .bld, install parts first, drop on render_bld.cmd, 800 x 600 window, closes by itself, 65 s for
  17 / 43 s for 19 from sc3compat-a, bld_frames.ixf + .txt, Open folder), safety in plain words (Baapp.exe never
  changed, BaappW.exe copy, mode switches refused and watched, BAT.DAT / Res\BA never written, GOG 2.0.949 only,
  Jotti 0 of 13, `-Remove`), the in-game check (3 of 4 1999 buildings grew in Sacramento in 10 game-run minutes).
- **Building Architect packs from Simtropolis** (`#packs`): what a pack holds (.bld, parts in Paints / Details /
  Props, plugins identified only), Open SC3 pack / Open a pack folder, the dependency report states (labels as the
  page prints them: colour, in the .bld, game (Res\BA), this pack, game (BACustom), MISSING) and what to do about
  missing, installing parts (conflict tick + backup, unknown kind pick, close the BA first), removing (backups in
  `mods\netmod\sc3pack\`, never undoes buildings), the no-folder-access .zip route, then installing the buildings
  (unpack, parts, render, Open folder, Install; or Show its N buildings here + Make the install .zip).
- **SC4 section**: commercial / industrial classes and the cut rule ("a rule of this tool, not a measured match"),
  tall towers convert (251 m tower -> 6700 on 4x4, grew in Berlin by the first autosave with commercial churn), lots up
  to 4x4, growable versions only (ploppable / landmark listed, not converted), night textures unused, new
  subsection "Packs that hold only lots" (page converts nothing, names every missing building and the readme links).

Lines the new work made wrong, fixed:
- Lead: "No Python, no Building Architect" -> "No Python and no other tool to install" (the render kit uses the BA),
  plus one line that the page reads Simtropolis packs and SC4 buildings.
- "What it does not do": formats line now names SC4 buildings; ploppables line says pack plugins are listed, not installed.
- .bld section: art order is now bld_frames.ixf, then BAT.DAT, then the preview (sc3compat-a); 1999 files read;
  "The first view is right" removed for 1999 files (8 of 19 previews show another side); the "add it through the BA
  so it lands in BAT.DAT" advice replaced by the kit.
- SC4: "Commercial, industrial ... get no class and stay off" removed (sc4pass2 classes them); "several meshes in one
  view" skip narrowed to views that are not tiles of one picture; "BAT houses" -> "BAT buildings".
- Troubleshooting: two new entries (wrong side / plain faces on a .bld, kit refuses the Building Architect).

No new pictures: no third-party or EA content added. Text checked for em-dashes, semicolons, ellipsis, intensifiers
(none in the prose). Every number is from sc3compat-a / sc3compat-b / sc4pass2 RESULTS.

## Check (headless Chrome, `node verify/guide1119/guide_check.mjs <page> <out>`)

| check | desktop 1280 | phone 390 (DPR 3, mobile) |
|---|---|---|
| no horizontal scroll | PASS (scrollWidth 1264) | PASS (390) |
| nothing in main past the edge (tables scroll inside .tablewrap) | PASS | PASS |
| every in-page link has its target | PASS | PASS |
| "SC3 Text" game font loaded | PASS | PASS |
| light only (color-scheme light, body #d8d9ff) | PASS | PASS |
| every picture loads | PASS | PASS |
| no page errors | PASS | |

Pictures `owner_shots/`: `desktop_*.jpg` (top, what, bld, render, packs, sc4, trouble) and `phone_*.jpg` (780 px
wide, the 390 px page at 2x, tall sections split into numbered parts).

## Noted, not changed
- `re/tools/bldbat/player/README.md` is fine on disk (`tools\bld_render\`), only a terminal rendering showed `\b`.
- The "Show its N buildings here" grid installs only through the .zip route (sc3compat-b section 6), so the guide
  recommends unpacking the pack into a folder for the normal install.
