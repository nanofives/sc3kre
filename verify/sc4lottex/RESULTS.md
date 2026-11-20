# sc4lottex results (round 2026-11-19l): SimCity 4 lot textures on the ground under the converted building

**Verdict: done in Python and in the page, byte identical. A SimCity 4 lot's driveways, paths, paving and flower beds are
drawn on the ground under the building, from the download, the dependency packs and the SC4 install. SC4's own grass is
left to SC3's lawn. JMyers with the BSC pack and the install: 622 of 634 texture rows drawn, on all 110 buildings. SC4's
own civic buildings, parks, rewards and landmarks: 2,143 of 3,675 rows, on 111 of 112.** Per building switch
`x_sc4.textures.on`, kept on a rerun, `--no-textures` writes them off. In game: 4 JMyers designs installed with and without
textures, all 8 grew in Sacramento by the first autosave, and SC4's Small Police Station was picked in the Police list
window and placed with its parking lot. The suite passes 40 of 40 steps.

EA's files and the community packs are read in place. Nothing of them, and no picture, is in the repository or docs.
`owner_shots\` is local, for the owner. Rules and evidence: `re/analysis/SC4_FORMATS.md` section 12.

## 1. How a lot exemplar places its textures, with the evidence

| question | answer | evidence (SC4_FORMATS.md 12) |
|---|---|---|
| which rows | lot object kind 2, word 12 = texture id, FSH group 0x0986135E, instance id + zoom (0-4) | install: 290 ids with all 5 zooms, 128 x 128 px at zoom index 4 |
| size, position | words 6-9, a 16 x 16 m square in the lot frame | 326 of 326 JMyers rows exactly 16 m on the grid; install 25,452 rows 16 m up to 2^-16, often off the grid |
| rotation, mirror | word 2: low 2 bits quarter turns, bit 0x80000000 mirror | cars test (below) |
| how the image lies | turned 180 degrees, then rotation quarter turns clockwise, columns along +x and rows along +z; the mirror bit mirrors the columns first | of 16 mappings, the most parked cars on paving: install 197 of 239, JMyers 20 of 29 (next 195 / 17). Odd rotations only: 30 vs 28, 7 vs 4. Mirror columns vs rows: 43 vs 34 of 48, 6 vs 2 of 9 [UNCERTAIN: no SC4 render compared, small sense margins] |
| layering | textures without a transparent texel first, then the others, each group in lot order | lot order hides an overlay under an opaque base in 190 of 296 install pairs and 55 of 198 JMyers pairs. Cars: 197 / 20 against 182 / 11 for lot order. Order among overlays changes no car [UNCERTAIN] |
| base texture | no lot property names one. The base is the opaque rows: on JMyers every textured tile has exactly one (124 tiles), 8 plain grass and one vegetable garden | the lot properties that name an exemplar point at retaining walls (type 21) and foundations (type 17) |

Two ids the JMyers lots name, `D40F002A` and `D40F0030` (6 rows each), are in neither the BSC pack nor the install, in any
group.

## 2. SC3 lot, what is cut, and what replaces SC3's lawn

- **SC4 16 m cells on the square SC3 lot.** The canvas is the props' SC3 lot window (round sc4props: across the lot the SC4
  lot's own width or centred on the building, along the depth from the building's back wall to the street), 8 px per metre.
  A texture square inside it is drawn (`placed`), one partly inside is cut at the window edge (`cut`), one outside is left
  out. On JMyers the window is 16 m against SC4 lots of 16 x 32-48 m and starts at the house's back wall, so 556 of the 622
  rows drawn are cut. On SC4's civic lots (1x1 to 20x9 tiles) 1,532 rows fall outside.
- **Lawn decision: SC4 grass is cleared, SC3's lawn shows.** Every JMyers lot is fully covered by SC4 texture (ground share
  1.0 on all 110). The 8 plain grass bases have luminance 0.32-0.40 and hue 71-85 degrees (`D400F050`: 93 / 115 / 44),
  SC3's lit lawn at zoom 3 is 100 / 145 / 78, luminance 0.49, hue 100. Keeping SC4's grass makes the lot a darker, yellower
  square among the stock lawns (picture 06, middle column). The composite texel is cleared when it is grass (green the
  strictly strongest channel, hue up to 108 degrees, saturation above 0.15, integer test): it clears 0.88-1.00 of the grass
  bases and 0.65 of the garden plot. Bldrender's own lawn fills the cleared texels and everything the SC4 textures leave
  bare.
- **Light.** The canvas is drawn by a quad in the new OBJ group `sc3ground`, which bldrender and bldweb.js shade as their
  lawn: the stock front-edge rim, no `baked` tone (it would bring `D400F050` to luminance 0.66), no saturation, grain or
  contrast, no shadow cast. A transparent texel of it is the lawn itself.

Shares of the SC3 lot (`x_sc4.textures.ground`, `verify/sc4lottex/lawn_numbers.json`):

| | buildings | SC4 texture before clearing | cleared to SC3 lawn | drawn |
|---|---|---|---|---|
| JMyers, BSC + install | 110 | 100% on all | median 66% (42-91%) | median 34% (9-58%) |
| SC4 install, civic / park / reward / landmark | 112 | median 91% | median 10% | median 63% (0-99.8%) |

The one install building with nothing drawn is the Gateway Arch (10x10, off): its 20 rows are all grass.

## 3. Measured per source

JMyers Homes V3.1, 110 buildings, 634 texture rows of their smallest lots (`sc4_lottex_setup.py` counts.json; the page
gives the same lines):

| sources | rows drawn (buildings) | of them cut | outside the SC3 lot | in no source (ids) |
|---|---|---|---|---|
| download alone | 0 (0) | 0 | 0 | 634 (51) |
| + BSC pack | 526 (98) | 484 | 0 | 108 (7) |
| + SC4 install | 96 (42) | 72 | 0 | 538 (46) |
| + BSC pack + SC4 install | **622 (110)** | 556 | 0 | 12 (2: `D40F002A`, `D40F0030`) |

SC4 install, its 112 civic buildings, parks, rewards and landmarks (`sc4conv.py <install>`): 2,143 of 3,675 rows drawn
(111 buildings), 776 of them cut, 1,532 outside the SC3 lot, 0 in no source. The Small Police Station: 9 of 9 rows placed,
58% of its 3x3 lot drawn.

Time: Python 14 s for JMyers with both sources (BSC index cached), 2 min 30 s for the install. Node: 5.3 s with both
(after the session's BSC index), 29.1 s with the BSC zip indexed in the run.

## 4. Byte identity and the suite

| check | result |
|---|---|
| `sc4_lottex_setup.py` + `sc4_lottex.mjs` (new, test slot) | **24 of 24**: the report lines of the four source sets = Python; with both, 881 OBJ / MTL / models.json files byte for byte (330 `_lot` OBJ + PNG among them), 685 PNG pixel for pixel, the file list (1,566); `--no-textures` models.json; the rerun keeping both switches (textures off on one building: `_props.obj`, props off on another: `_lot.obj`, the house and the quad without props); the rerun packed = `bldimport.py pack` (11 game files, ids.json), 40 frames RGBA |
| existing SC4 checks | now also compare `<stem>_lot.obj / .mtl`, `<stem>_props_lot.obj / .mtl` and `<stem>_lot.png` where they exist (`sc4_props.mjs`, `sc4_baseprops.mjs`, `sc4_golden.mjs`, `sc4_packs.mjs`; `sc4_install.mjs` compares every file). `sc4_baseprops.mjs` alone: 132 of 132, its 240 frames are the `_props_lot` buildings |
| `run_all.sh`, six arguments, `SC3PACK_PACKS`, `SC4INSTALL`, `PROYECTOS_TEST_HUB=off`, test slot | **40 of 40 steps passed** (38 before + the 2 sc4lottex steps), log `dev\sc4lottex\work\runall1_full.log` |
| `sync_css.py --check` | in sync; `--publish` done after the last page change (docs/buildings/importer) |
| guide | `make_docs.py --wt dev\sc4lottex\wt --tree stage\release --zip <published sample-pack URL>`: only the SC4 text of docs/buildings/index.html changed, the sample-pack link kept, `stage\sample_pack\README.txt` byte identical (sha256 bdda1dee...) |

Command:
`SC4INSTALL="C:/Program Files (x86)/Steam/steamapps/common/SimCity 4 Deluxe" SC3PACK_PACKS=MAIN\stage\st_packs PROYECTOS_TEST_MEM_GB=6
PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh dev\sc4lottex\work\runall stage\release stage\kits
"<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes\jar stage\st_packs\sc4`.

## 5. In game

Tree `dev\sc4lottex\tree`, mods of `dev\sc4lottex\inst`, windowed 1600 x 1000, posted input and Frida game calls only.
Models folder `dev\sc4lottex\work\lab`: the converter's output with BSC + install, every building off but 4 designs
entered twice, `<stem>_props_lot.obj` "(textures)" and `<stem>_props.obj` "(no textures)", and the install's Small Police
Station with textures. `bldimport.py build work\lab --game tree`: ids 38106-38113 and 38114.

**Run 1, growth** (`bld_lab.py`, Sacramento, churn anarchy_res 5000, speed 4, autosave 150 s, PID 17252): at the first
autosave (2.5 game-run minutes) lots per id:

| design | textures on: id, lots | textures off: id, lots | found in the dumps by its own frames (score) |
|---|---|---|---|
| 670 Grove View Rd (Abby Glen) | 38106: 11 | 38107: 9 | not found in the dumps taken |
| Craftsman Bungalow | 38108: 9 | 38109: 9 | 0.95 / 0.95 |
| Shotgun house | 38110: 8 | 38111: 8 | 0.77 / 0.70 |
| Destiny Homes | 38112: 9 | 38113: 6 | 0.96 / 0.70 |

**Run 2, the SC4 civic look** (run 1's autosave, PID 12748, speed 1):

| check | result |
|---|---|
| load | `CIVVAR> base 0xD2: 0xB1D10002:0x94E2 "Small Police Station (SC"`, `CIVVAR> on: 1 civic button(s) with 1 variant look(s)`, `CIVDLG> on` |
| Police hotkey 0x18 | list window "Elegir aspecto": Comisaría, Small Police Station (SC4, textures); picked: its picture with the textured lot, "Precio: §500", "Aspecto 2 de 2" (owner_shots 02) |
| tool after OK | key `0x207EDC0E 0xB1D10002 0x94E2` |
| placed (posted click) | `RELOCATE> building placement (kind 0) at (232, 218): placed, price 505`; `find 13130`: (232..234, 218..220) key 0xB1D10002:0x94E2, flags 0x104, and the stock police station at (241..243, 210..212) |
| pictures | zoom 4, view rotations 0-3: the textured frame found pixel for pixel, score 1.00 in all four (owner_shots 01), zoom 3 |
| VEH FAULT | both runs: only the start-up `0xC0000096 at SC3U.exe+0x84122` |

Both games were started by this session and stopped by PID. No BMP left (PNG only).

| picture (`owner_shots\`) | what |
|---|---|
| `01_police_sc4_look_textures_4_rotations.jpg` | the placed SC4 police look, its parking lot and cars, in the four view rotations, with the stock lots around |
| `02_police_list_window_sc4_look.jpg` | the Police list window with the SC4 look picked |
| `03_jmyers_textures_off_vs_on_in_game.jpg` | per design the house as the game drew it, textures off and on (crops of the dumps, boxed) |
| `04_offline_textures_off_vs_on.jpg` | the same entries rendered by bldrender, off and on, views 0 and 2 |
| `05_sacramento_whole_dump_boxed.jpg` | one whole dump, the found houses boxed |
| `06_lawn_decision_sc4_grass_kept_vs_cleared.jpg` | textures off, SC4 grass kept, SC4 grass cleared (chosen), for 2 houses and the police station |

How it looks: the driveways and paths sit under the cars and lead from the doors, the police parking bays hold their
cars (the school's did too in a review render), the rest of the lot is the stock lawn. At zoom 3 in game the difference is small on a 1x1 house. [Owner call:
whether lot textures should be on by default, as they are now.]

## 6. Not run, limits

- No SC4 screenshot of a lot was compared: the orientation, mirror and layering rules rest on the cars and the seams (12.2,
  12.3). The order among transparent overlays is lot order, untested.
- Soft texture edges become hard: bldrender's alpha test keeps a texel at alpha 128 and above.
- The page's own controls have no textures switch: as for props, it is `x_sc4.textures.on` in models.json.
- Word 1 = 0x20 on 5,431 install rows is not read [UNCERTAIN: meaning].
- Other downloads than JMyers (the DiegoDL and I-M lot-only packs still have no building model to convert).

## 7. Files

Worktree `dev\sc4lottex\wt`, branch `child/sc4lottex`, nothing committed:

| file | change |
|---|---|
| `re/tools/sc4conv/lottex.py` (new, `git add -f`) | plan, composite, grass test, summary, quad |
| `re/tools/sc4conv/sc4conv.py` | `write_lottex`, `write_with_quad`, `file_for`, `tex_notes`, `--no-textures`, the textures switch on rerun, texture fetch from the packs |
| `re/tools/sc4conv/catalog.py` | lot objects carry the mirror bit (`flip`) |
| `re/tools/bldimport/bldrender.py` | OBJ group `sc3ground` (`GROUND_GROUP`, off switch `SC3BLD_GROUNDGROUP=0`): lawn shading, clear texels = lawn, no shadow cast |
| `re/tools/bldimport/bldweb.js` | the same in the page |
| `re/tools/bldimport/sc4web.js` | lot textures in the page (`lotPlan`, `lotComposite`, `writeLottex`, `texNotes`, `fileFor`, `opt.noTextures`), lot object bounds + flip |
| `re/tools/bldimport/classifier.html` | the two SC4 button titles mention lot textures |
| `re/tools/bldimport/webtest/sc4_lottex_setup.py`, `sc4_lottex.mjs` (new, `git add -f`) | the identity test |
| `re/tools/bldimport/webtest/run_all.sh` | 2 steps with `SC4INSTALL` + the BSC zip |
| `re/tools/bldimport/webtest/sc4_props.mjs`, `sc4_baseprops.mjs`, `sc4_golden.mjs`, `sc4_packs.mjs` | the house stem from `<stem>[_props][_lot].obj`, the `_lot` files compared |
| `docs/buildings/importer/index.html`, `bldweb.js`, `sc4web.js` | `sync_css.py --publish` |
| `docs/buildings/index.html` | `make_docs.py` from the template |
| `re/analysis/SC4_FORMATS.md` | section 12, pointers in 9.2 and 9.4 |
| MAIN `verify/bldpack/work/guide_template.html` (gitignored) | Lot textures section, switch, FAQ, the SC4 lists (backup `.bak_sc4lottex`) |
