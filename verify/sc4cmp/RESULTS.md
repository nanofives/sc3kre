# sc4cmp results (round 2026-11-20b): SimCity 4 against SimCity 3000, side-by-side pictures for the forum

Input: SimCity 4's own buildings from the Steam SimCity 4 Deluxe on this PC, read in place. EA's art: the pictures are in
`MAIN\verify\sc4cmp\forum\` (gitignored, local only, never in the repository, docs or a release). No community building
is in the set.

**Verdict.**

- **12 pictures plus one four-sides picture** in `verify/sc4cmp/forum/`, 1280 px wide JPEG, SimCity 4 on the left,
  SimCity 3000 on the right, the same side of the building at the same metres per pixel. Six of them also show the
  converted building placed in a city (a strip under the pair, from the frame dumps of rounds sc4ci and sc4lottex).
  Four more in `forum/extra/` (why they are not in the set: section 2).
- **The SimCity 4 side is drawn through SimCity 4's own camera**, not grabbed from the game: the building's view box with
  SC4's own picture of that view, every lot prop with its own SC4 picture, and the whole SC4 lot's textures with SC4's
  grass kept. Against SC4's own picture of each building: **99.96 to 100% of the drawn building pixels are SC4's own
  opaque pixels, mean difference 4.8 to 10.4 levels of 255 per channel, 77 to 95% of pixels within 16 levels on every
  channel** (16 buildings, 623,279 pixels). What is left is resampling (the fitted camera puts the box 0.46 to 0.94 px
  off SC4's projection, so every pixel is a blend of neighbours). Section 3.
- **Script:** `re/tools/sc4conv/compare_sheet.py` (no SC4 data in it: exemplar names only). It is under the
  deny-by-default `.gitignore` (`/re/tools/*`), so it needs `git add -f` like the other sc4conv files.
- **Converter finding, not fixed here (section 5):** 24 of the 50 converted models reach 0.4 to 5.5 m below SC4's
  ground (every Small Shops and Retail Stores variant, Ferrrara Inc.). `bldrender.place` puts a model's lowest point on
  the lawn, so these buildings stand that far above it with their lot ground, and the SC3 frame shows a second lawn
  edge under the lot. It shows in pictures 06, 07 and 09. Rerun the script after a fix.

## 1. The pictures and captions

Captions in plain English for the post (no em-dashes, semicolons, emoji, ellipsis or intensifiers).

| file | caption |
|---|---|
| `00_small_police_station_four_sides.jpg` | The Small Police Station from all four sides. Each SimCity 3000 view is built from SimCity 4's own picture of the same side. |
| `01_small_police_station.jpg` | SimCity 4's Small Police Station with its parking lot and patrol cars, converted for SimCity 3000. Below, the converted station in a city. |
| `02_courthouse.jpg` | The Courthouse reward with its fountain, lamps and flower beds. SimCity 3000 looks from a lower angle, so the front looks taller. |
| `03_gazebo.jpg` | A small park. The gazebo, the lamp post and the bushes all come across. |
| `04_alamo.jpg` | The Alamo landmark. SimCity 4 puts a plaza and gardens in front of it. The SimCity 3000 lot is 2x2, so it keeps the building and the ground around it. |
| `05_independence_hall.jpg` | Independence Hall with its trees and brick paving. |
| `06_small_shops.jpg` | A corner shop that grows in SimCity 3000's commercial zones. Below, two of them grew side by side. |
| `07_retail_stores.jpg` | Retail Stores on a 2x2 commercial lot, with the planters by the door. |
| `08_lam_banking.jpg` | A low office building. The back wall and the planters come along. |
| `09_ferrrara_inc.jpg` | A 55 m office tower that grows downtown. Below, among SimCity 3000's own towers. |
| `10_eyler_refining.jpg` | A refinery for the dirty industry zone. Below, two of them grew next to each other. |
| `11_vilett_textiles.jpg` | A textile mill on a 3x3 industrial lot. SimCity 4's parking lot does not fit on the SimCity 3000 lot and is left out. |
| `12_pumpkin_acres.jpg` | A farm that grows among SimCity 3000's own fields. |

**Why these 12 (of the 14 the brief named, plus Independence Hall and City Hall tried):** two police and park civic
looks, a reward, two landmarks, and one of each commercial and industrial kind, so the post covers every kind of
building the importer converts from the game. Each one reads at 1280 px and looks like its SC4 original. The police
station leads because its SC3 lot keeps nearly the whole SC4 lot (35 of 36 props, the parking paint) and it has an
exact in-city match. The four-sides picture uses it for the same reason.

## 2. Not in the set (`forum/extra/`)

| building | why |
|---|---|
| City Hall | the SC3 frame has a grey hook above the dome that SC4's picture does not have (a converter artefact, worth a look) |
| Small Fire Station | SC4 lot 16 x 32 m on SC3's 3x3 civic lot: the SC3 side is mostly lawn and the building looks small |
| Mayor's House | SC4 lot 32 x 48 m of gardens, SC3 lot 1x1: the SC3 side is a small house next to a large garden |
| Lee Avionics | SC3 side reads washed out at this size, and the parking lot is dropped |

## 3. How close the SimCity 4 side is to SimCity 4

**Method.** An SC4 building view is a box whose texture is SC4's own render of that view, mapped by screen projection
(`views.py`). `compare_sheet.py` fits that projection (`views.fit_camera`), then draws through it the box, every lot prop
(each prop's own SC4 view for its turn, `props.prop_views`, placed by the lot exemplar), and a ground quad holding the
whole SC4 lot's textures (lottex's orientation and layering rules over the lot's full size, SC4 grass kept, bare cells
filled with SC4's plain grass texture `D400F050`). Z-buffer with alpha test, bilinear sampling, 3x3 supersampling.

**Check against SC4's own picture.** The building is drawn alone at SC4's scale and every fully covered pixel is looked
up in the view texture through the fitted projection.

| building | SC4 view, SC3 rotation | props drawn | lot textures | SC4 lot | drawn pixels opaque in SC4's picture | mean difference (0-255) | within 16 levels | camera fit (px) | scale vs SC3 zoom 4 | in a city |
|---|---|---|---|---|---|---|---|---|---|---|
| Small Police Station | S, 3 | 35 of 36 | 9 | 48 x 32 m | 100.00% | 4.75 | 91% | 0.576 | 1.41 | yes |
| Courthouse | S, 3 | 20 of 28 | 14 | 48 x 48 m | 100.00% | 6.09 | 90% | 0.523 | 1.41 | |
| Gazebo | S, 3 | 20 of 29 | 1 | 16 x 16 m | 100.00% | 8.72 | 81% | 0.507 | 1.75 | |
| The Alamo | S, 3 | 16 of 59 | 8 | 32 x 48 m | 99.98% | 5.30 | 90% | 0.648 | 1.75 | |
| Independence Hall | S, 3 | 4 of 16 | 6 | 32 x 32 m | 100.00% | 5.61 | 90% | 0.568 | 1.75 | |
| Small Shops | E, 0 | 3 of 4 | 1 | 16 x 16 m | 100.00% | 5.85 | 90% | 0.599 | 1.75 | yes |
| Retail Stores | S, 3 | 5 of 9 | 2 | 16 x 32 m | 100.00% | 5.81 | 89% | 0.497 | 1.75 | |
| Lam Banking | S, 3 | 9 of 9 | 7 | 32 x 32 m | 100.00% | 6.90 | 86% | 0.622 | 1.75 | |
| Ferrrara Inc. | S, 3 | 8 of 8 | 9 | 48 x 32 m | 100.00% | 7.99 | 82% | 0.936 | 1.29 | yes |
| Eyler Refining | S, 3 | 5 of 7 | 4 | 32 x 32 m | 99.99% | 6.74 | 87% | 0.562 | 1.75 | yes |
| Vilett Textiles | E, 0 | 13 of 13 | 10 | 32 x 64 m | 100.00% | 6.46 | 87% | 0.545 | 1.35 | yes |
| Pumpkin Acres | S, 3 | 3 of 3 | 1 | 16 x 16 m | 100.00% | 5.02 | 95% | 0.456 | 1.75 | yes |
| City Hall (extra) | S, 3 | 29 of 38 | 20 | 48 x 64 m | 100.00% | 7.75 | 84% | 0.471 | 1.40 | |
| Small Fire Station (extra) | S, 3 | 11 of 11 | 4 | 16 x 32 m | 100.00% | 5.46 | 90% | 0.510 | 1.41 | |
| Mayor's House (extra) | S, 3 | 75 of 77 | 12 | 32 x 48 m | 99.96% | 10.40 | 77% | 0.543 | 1.75 | |
| Lee Avionics (extra) | S, 3 | 12 of 12 | 10 | 32 x 48 m | 99.99% | 6.84 | 86% | 0.512 | 1.69 | |

Fitted camera, all 16: elevation 44.90 to 45.07 degrees, 6.97 to 7.03 px per metre (SC4 zoom 5), azimuth 22.5 degrees
off the lot axes. SC3 zoom 4 is 5.66 px per metre across the screen, so both sides are scaled to the same metres per
pixel (the SC3 frame by the factor in the table, SC4 by that factor x 5.66 / 7.0).

**What the SC4 side does not show**, for the 12 in the set: 141 of 221 prop rows are drawn. Of the 80 left out, 70 are
props whose model is a Resource Key Type 4 record without an S3D record (by their names animated people and effects, 41
of them on the Alamo's lot, the same family round sc4baseprops left unread), 2 have no model key, 2 a Resource Key Type
0 not read, 2 are seasonal props not shown on 1 July, and 4 prop models failed to load. SC4 also
casts building shadows on the lot at run time, which these pictures do not. The lot texture orientation is round
sc4lottex's measured rule (parked cars land on paving on 197 of 239 SC4 lots), not checked against an SC4 screenshot.

**A real SC4 screenshot route** (not used, not tested): SC4 runs windowed with `-w -CustomResolution:enabled
-r1280x1024x32 -intro:off`. The hard part is getting a lot placed without the real mouse. Two ways: (a) posted mouse
messages to SC4's window to pick the building and plop it (unknown whether SC4 reads posted input or only DirectInput,
one short test would tell), or (b) a prepared city save with the lots already placed (needs the .sc4 lot subfile
layout). Then a desktop-free window grab (PrintWindow) at zoom 5 in each rotation, and the same check as above against
the frame.

## 4. In-city strips

`verify/sc4cmp/work/match_ingame.py` (local, it names local frame dumps) finds each converted building in the existing
zoom-4 game frames: masked squared error of the bldrender frame (every model x rotation) over the frame, by FFT. Kept
only under 30 levels RMS:

| frames | match (RMS levels) | used |
|---|---|---|
| sc4lottex run2, police, 4 rotations | 2.8 to 2.9, same rotation as the frame | rotation 3 (SC4's front view) |
| sc4ci Ferrrara Inc., 4 rotations | 13.5 to 28.4 | rotation 3 |
| sc4ci Eyler Refining, 4 rotations | 23.3 to 46.6 | rotation 3 |
| sc4ci Pumpkin Acres, 4 rotations | 19.9 to 36.9 | rotation 3 |
| sc4ci Small Shops, Vilett Textiles (rotation 0 only) | 15.8, 22.1 | rotation 0, so the whole picture uses SC4 view E |
| sc4ci Lam Banking, Retail Stores, Lee Avionics | 56 to 62, off-centre | no strip |

The sc4ci frames are from a converter run of 2026-11-20 and match the current frames in rotation and place. The higher
RMS there is the city around the lot and sim overlays (cars, people), not a different building. Exemplars chosen for the
variants: Small Shops `CS$14x14_1ChiSmallShop1_05CD` (the one in the sc4ci city), Retail Stores
`CS$$12x28_1HouMediumStore1_05C5`, Vilett Textiles `IM28x40_2ManuOut8_0823`.

## 5. Converter finding: buildings below SC4's ground are lifted in SC3

`bldrender.place` sets `h = (y - y0) / cell_m` with `y0` = the model's lowest vertex, and sc4conv writes the lot quad
(`sc3ground`) at y = 0.01. An SC4 model with vertices below 0 (a foundation or basement SC4 hides in the terrain) is
lifted by `-y0`, and the ground quad with it, while bldrender's own lawn stays at the lot. Of the 50 models converted for
this round: Ferrrara Inc. -4.00 m, Retail Stores -2.13 to -5.49 m (12 variants), Small Shops -2.42 to -4.00 m (10
variants), Smith Tower -0.41 m. None of the civic, reward or industrial models. The same lift is in the game (the frame
is what the game draws). Possible fixes, owner or orchestrator call: clip the model at y = 0 in sc4conv, or pass a
ground height to bldrender. Not changed here (outside this stream, bldrender is shared).

## 6. Rebuild

```
set SC4="C:\Program Files (x86)\Steam\steamapps\common\SimCity 4 Deluxe"
py -3.12 re/tools/sc4conv/sc4conv.py %SC4% --growables --all --only "<verify/sc4cmp/work/only.txt>" --out verify/sc4cmp/work/conv
py -3.12 re/tools/bldimport/bldimport.py render verify/sc4cmp/work/conv
py -3.12 verify/sc4cmp/work/match_ingame.py            # optional: the in-city strips (ingame.json)
py -3.12 re/tools/sc4conv/compare_sheet.py %SC4% verify/sc4cmp/work/conv verify/sc4cmp/forum ^
    --ingame verify/sc4cmp/work/ingame.json --game-root <MAIN>
```

Times on this PC: conversion 36 s (50 buildings), render about 10 min, matcher 5 min, pictures 70 s. `forum/sheet.json`
holds every number of section 3. The game was not run by this session and no game PID was started.
