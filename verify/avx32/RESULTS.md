# avx32: boulevard / avenue crossings from the owner hand test 2026-10-21 (img6, img7, img8)

Owner reports on the LAN build of main 664a685: "3 road avenue intersecting with 2 road avenue is not working" (img6)
and "asymmetrical intersection is not working for 3 lanes and 2 lanes" (img7, img8). Read from the screenshots:
img6 = boulevard x avenue, centred; img7 = boulevard through, the crossing road a boulevard on one side and an avenue
on the other; img8 = avenue through, the crossing road an avenue on one side and a single road on the other.
Light test (owner rule): one lab game per case, pictures, save and reload. Sheet:
`MAIN\verify\avx32\owner_shots\avx32_sheet.png` (before / after per case, both drag orders, regression, no-mod load).
Lane plan of the new boxes: `MAIN\verify\avx32\owner_shots\avx32_plan.png` (built before the owner saw it; open for
owner corrections).

Setup: worktree `Simcity_wt_avx32` (child/avx32 from main 664a685), test tree `Simcity_stock_avx32` (hard-linked copy of
`Simcity_release`), instance `re\harness\inst_avx32`, all 8 mod binaries built from the worktree.

## Causes (in game, sc3netmod.log)

| case | log | cause |
|---|---|---|
| img6 | `bv: run axis 0 from (50,27), 17 column(s) left to the stock tiler: an avenue arm that would stay two-way` | AVX runs before BV in the edit pass. It read the stock 11204 / 29 / 11204 boulevard as three single roads crossing the avenue (avjunc's box run goes up to 4) and wrote its box and one-way nose 20800 into the avenue arm. BVX's `avl_band_ok` on the arm cell 2 past the box then found AVX's 20800 (not a band row: `no band row at the cell (80015140)`) and refused the whole boulevard. Result: stock boulevard + AVX road box = img6 |
| img7 | axis 0 `road beside the boulevard is not a straight single road`, axis 1 `a junction inside an end region` | BVX had no box for a 3-column span whose side holds an avenue on 2 of its 3 columns (it fell to BV's per-column rule), and the crossing boulevard's run read the box columns as an avenue narrowing. Stock 3x3 of 43 = img7 |
| img8 | `avx: edit run: 1 junction box(es)` (a 1-position road x avenue box) | The stock tiler caps the crossing avenue's left half at the through avenue (11203 at (57,26)) and joins the right half with a T 39, because only the right column goes on as a road. AVX then sees a road crossing on that column only, and the crossing avenue stays stock two-way, cut off from the box |

## Changes

1. **AVX leaves boulevard junctions to BV** (`sc3netmod_avx.c` `avx_bv_box`, twin `avjunc_rule.bv_box`): a box run of
   3 positions that BV's own run rule takes. New `bv_takes(mgr, x, z)` in `sc3netmod_bv.c` runs `bv_run1` as a dry run
   on the cells as they stand with the AVL band checks taken as passed (`g_bv_dry`, macro `BV_BAND_OK` at the three
   band checks), so AVX and BV share one definition of a boulevard and leftover AVX pieces in an arm cannot flip the
   answer. Twin: `boulevard.runs()` (band_ok None). Orchestrator ruling 2026-10-21 (no separate heuristic).
2. **BVX asymmetric boxes** (`sc3netmod_bvx.c`, `sc3netmod_bv.c`, twin `bvx.py` / `boulevard.py`): a 3-column span may
   hold a 2-column avenue arm at one end of a side; a BV run may end in a box with an avenue going on past it (end
   type 6). The box side letter is `L` / `H` (the arm at the low / high end of the side in real coordinates) in the
   `bvxc` lines. Covers img7 (both alignments) and, with the same pieces, an avenue crossing a boulevard one column
   offset (both ways). Package `boulevard_junctions`: 25 new box pieces (20933..20949, 21920..21927), 108 new bvxc lines
   (213), lanes from `bvlanes.py` (new scenes `box_scene_asym`, the new pieces' curves allocated after all others:
   24818..24877), art from `bvx.py build`. Every one of the 245 existing lane specs is byte-identical after the rebuild.
   Schema: the bvxc pattern accepts `L` / `H`.
3. **AVX cap links** (`sc3netmod_avx.c` `avx_caps`, twin `avjunc_rule.cap_links`): the stock pattern "straight pair of
   the crossing avenue, then {11203, 39}, then the through avenue's two rows, then road in the T's column only" is
   re-read for the pass as a link row plus an arm into the box. The box forms as an avenue x avenue with the going-on
   road a two-way arm. No new pieces: all 21 patterns (every one-way / two-way arm combination, 8 drawings) are already
   declared in avenue_junctions.

## Offline

| check | result |
|---|---|
| `bvx.py check` (9 kinds x 4 rotations through `boulevard.runs()`) | 36 / 36 OK, rotation-invariant, 0 clashes; the old 20 unchanged; boulevard round-2 layout 39 cells |
| art edge pattern vs placement, every box cell of every scene | 72 cells, 0 mismatches |
| `netpack.py validate examples/boulevard_junctions` | exit 0 |
| `avjunc_rule.py check`, 15 shipped cities, edge check | before: 48,540 edges meet, 125 do not; after: 49,346 meet, 125 do not (same 125) |
| boxes the boulevard refusal changes in shipped cities | 0 (a first heuristic version removed 9 short 3-road stubs in Berlin / London; replaced by BV's own rule) |
| cap links in shipped cities | 32 road-x-avenue boxes become full 2x2 avenue junctions, 3 new boxes, 0 boxes lost (a first version also matched an avenue ending on an avenue in London (141,170); restricted to "road on the T's column only") |
| patterns the shipped cities need | 57, all declared |

## In game (Simcity_stock_avx32, lab city copies)

| case | result |
|---|---|
| img6, boulevard drawn first | BVX box 20900 / 20902 / 20901, noses 20910 / 20911, both avenue arms one-way 21700 with U-turns 21701 |
| img6, avenue drawn first | the same grid |
| img7 | 3x3 box (20933..20940, 20926), both boulevard runs, avenue one-way; save `100 variant tile(s) written as base`, reload `all restored`, load passes write 0, grid identical |
| boulevard x avenue one column offset | 3x3 box (20949, 21920..21922, 20905), both avenue arms one-way |
| img8, road on the high column | 2x2 box 20807 / 20808 / 20820, link noses 21772 / 21773, nose 20800, crossing avenue one-way; save 54 tiles, reload identical |
| img8, road on the low column, road drawn first | 2x2 box 20807 / 20825 / 20809, the same noses |
| DLL before bv_takes: img6 + img8 in one game | as above; save `133 variant tile(s) written as base`; the saved file read offline holds stock ids only (max 18002); reload `all 133 variant tiles restored`, every load pass 0 written, both grids identical |

| final DLL (bv_takes): img6, avenue drawn first | BVX box, noses, avenue one-way (AVX boxed it while 2 roads were drawn, BV took over with the 3rd) |
| final DLL: plain road x avenue (regression) | AVX road box 20805 + noses, as before |
| final DLL: img6 boulevard first + img7, save, reload | save `179 variant tile(s) written as base`; reload `all 179 variant tiles restored`, load passes 0 written, grids identical |
| the same save in a game WITHOUT sc3netmod (inst_avx32_nomod: mods_launch + sc3resize) | stock pieces only (11204 / 29 / 43), a sane stock layout (`nomod_img6_z3_r0.png`, `nomod_img7_z3_r0.png`) |
| before shot of the offset crossing | release code (HEAD sources built into inst_avx32_old): `road beside the boulevard is not a straight single road`, stock patch |

Traps met: the Frida camera call failed twice in one game and the game then went Not Responding (killed, one game per
case after that, the camera state file deleted before each camera call so a failed call cannot leave a stale one).
One relaunch crashed 0xC0000005 at 438 ms, before the city load; the next launch of the same city was fine.

## Not done / open

- Traffic not traced through the new boxes (lanes come from the same generators as bvlanes / avjunc; the lab city has
  no population).
- Asymmetric boxes not covered: a through avenue whose crossing road is a boulevard on one side and an avenue on the
  other (a 3x2 box), and a boulevard whose crossing is a boulevard and a single road. Both stay as today.
- Tree prep for package installs: the release ships no netpack ledger, so `Simcity_stock_avint`'s `ledger.json` and
  `packs\` were copied into the test tree before reinstalling boulevard_junctions. A republish needs the same
  reinstall in the staging tree (avint) with this package.
