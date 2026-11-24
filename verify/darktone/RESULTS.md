# darktone results (round 2026-11-24b): protect dark tones in the baked style

Owner 2026-11-24: "Protect dark tones" (SC4 police cars read as white blobs under the baked tone y' = 1.33 y^0.75).
SC4 install read in place. Pictures with SC4 art are local only (`owner_shots\`, `fd\`, `runs\`, `p50t\`, `p100t\`,
`verify\sc4cmp\forum\`, `dev\darktone\work\`, all gitignored).

**Verdict.** A dark-tone guard on SC4 **prop** materials only (`sc4p_*`, the lot props: cars, lamp posts, signs,
benches), for **neutral, non-green** texels:

    protection = (1 - smoothstep(y / 1.0)) x ramp(s: 1 at <= 0.08, 0 at >= 0.20) x ramp(G - max(R, B): 1 at <= 0, 0 at >= 0.02)
    y' = y2 + protection x (y - y2)          y = texel luminance, y2 = the baked tone 1.33 y^0.75, s = saturation

`STYLES["baked"]` / `baked_sharp`: `tone_toe = (1.0, 0.08, 0.20, 0.0, 0.02)`. `baked_raw*`: none. Building views are not
touched, so the tone fitted on the 18 JMyers designs (verify/sc4conv) stays as it was.

| check | result |
|---|---|
| police cars (parking rows, sheet slot, zoom 4): pixels darker than 60 / 90 | 0.3% / 6.0% before, **4.0% / 11.0%** after (SC4's own tone `baked_raw`: 12.1% / 26.8%); median 162 -> 149 (raw 113) |
| JMyers fit set (12 enabled designs, zoom 3 + 4, 96 frames) | **96 of 96 byte-identical** (no lot props), so the 0.23 / 0.40 / 0.73 fit does not move |
| trees and bushes, palette off (the frame before the 255-colour cut) | green pixels darker by > 8: Hagia 0.56%, Mayor's House 0.29%, Small Fire Station 0.73%, Large Fire Station 0.28%, Branch Library 0.62% |
| full suite, normal mode | **41 of 41** (wall 1,180 s); doc line change: `SUITE_CHANGED=1` 39 of 39 |
| non-SC4 goldens vs main | 1,238 same, 46 differ = `meta.json` render key only (it hashes bldrender.py), **0 frames or data** |
| forum sheets | 17 re-made + the police four-sides picture, every one looked at, sheet slots equal to the published ones |

## 1. Why the cars, and why props only

The police cars are prop texture `sc4prop_1ABE787D_1EDA0400` (SC4's shared prop atlas): white body, black side panels and
windows. Car texels (909 opaque, the atlas piece at x 56-115, y 212-244): luminance p10 / p25 / p50 0.158 / 0.334 / 0.665,
saturation median 0.10 in every luminance band below 0.7 (p90 0.20-0.27). The baked tone lifts 0.158 to 0.33 and 0.334 to
0.59: the panels go mid grey and the car reads as one white shape.

Tree texels in the same atlas (`sc4prop_1ABE787D_29810420`, the crown at x 106-153, y 2-69, 2,199 texels): luminance
p50 0.216, saturation p10 / p50 0.31 / 0.44. Below luminance 0.5, 83-92% of car texels (two car pieces) have s < 0.3 against 9% of tree texels.
Saturation separates them, luminance does not.

Whole frame against props only (mock, `work/measure_m1*.txt`, `work/mj`): every whole-frame toe moved the JMyers fit
(zoom-3 structure p10 0.286 baked -> 0.181 to 0.247, p50 0.468 -> 0.408 to 0.461), because the house views hold their
own dark roofs and windows. Props only leaves all 96 JMyers frames byte for byte. The owner's complaint is props, so the
guard is props only.

## 2. Mock (dev\darktone\work: mock.py, measure.py, grid.py)

Six buildings (Small Police Station, Large Fire Station, Hagia Sofia, Gazebo, Mayor's House, Chez Eyler; later Small
Fire Station, Local Branch Library), zoom 3 + zoom 4 native, 4 slots, against the current `baked_sharp`. 15 variants:

| family | examples | outcome |
|---|---|---|
| knee on every texel | knee 0.25 / 0.35 | cars better at 0.35, trees darker: green pixels darker by > 8 on 30-57% of Hagia / Chez Eyler greens |
| knee + saturation, whole frame | 0.25-0.50 with s ramp | trees mostly kept, JMyers fit moves (p10 0.286 -> 0.206-0.247) |
| knee + saturation, props only | 0.4-2.0, ramps 0.15-0.30 and 0.08-0.20 | JMyers byte-identical; cars improve with the knee; the tight ramp (0.08-0.20) keeps Hagia's trees |
| + green-lead gate | (0.01, 0.04), (0.0, 0.02) | removes the last vegetation darkening pre-palette (Mayor's House 1.96% -> 0.29%) |

Cars per knee (props only, s ramp 0.08-0.20), parking-row pixels darker than 90: knee 0.5 10.3%, 1.0 12.6%, 2.0 13.8%
(raw 26.8%). Gazebo (its building is a prop) mean lightness 0.598 -> 0.592 / 0.580 / 0.573. Knee 1.0 is the middle:
whites keep the full tone (smoothstep is 1 at y = 1), darks keep most of their value. With the green gate the cars give
up a little (darker than 90: 12.6% -> 11.0%).

The first pick (knee 0.5, then knee 1.0 without the green gate) was built, installed and shot in game before the
before / after crops showed shrubs a little darker. With the palette step off (`palette=None`) the Small Fire Station
bush box (frame rows 95-140, columns 40-130) moved 3 pixels by more than 8 levels, mean 0.03 / 255: the visible shift was
the 255-colour palette re-pick, which moves pixels both ways after any change (`owner_shots\04`). The green gate was
added anyway, because pre-palette Mayor's House greens still darkened 1.96% without it. Earlier game frames are kept in
`p50t\` and `p100t\`.

## 3. Numbers, final curve (`work/final_numbers.txt`, zoom 4, 4 slots, against main's baked_sharp)

| building | structure mean before | after | pixels changed (|dY| > 8) | greens darker > 8, palette on | palette off |
|---|---|---|---|---|---|
| Small Police Station | 0.566 | 0.559 | 9.9% | 6.30% | 3.54% |
| Large Fire Station | 0.509 | 0.509 | 1.8% | 1.32% | 0.28% |
| Hagia Sofia | 0.603 | 0.603 | 0.9% | 1.51% | 0.56% |
| Gazebo | 0.598 | 0.580 | 16.2% | 0.50% | |
| Mayor's House | 0.594 | 0.591 | 3.5% | 0.51% | 0.29% |
| Chez Eyler | 0.715 | 0.714 | 1.9% | 0.73% | |
| Small Fire Station | 0.563 | 0.557 | 8.7% | 2.86% | 0.73% |
| Local Branch Library | 0.554 | 0.551 | 4.1% | 1.51% | 0.62% |

"Green" = G > R + 8 and G > B + 8 on the before frame (lawn included, the lawn is not toned). The police lot's 3.54%
palette-off pixels lie inside the parking rows (frame x 74-180, y 134-184 of slot 2), not on its trees. The Gazebo's
16.2% is the gazebo itself, which SC4 places as a prop: its shaded roof and lamp post go darker.

Forum set, sheet slot (`work/fo_diff_final.txt`): pixels darker by > 16, from 0.00% (Ferrrara Inc., Tennis Court) to 3.32%
(City Museum), Gazebo 11.30%. 17 sheets change by 100 pixels or more.

## 4. Sheets (`verify/sc4cmp/forum/`, old copies `*_pre_darktone.jpg`, report `sheet_darktone.json`)

Re-made with `work/sheets.py` (forumshots' wrapper pointed at this branch and this branch's conversion `work/conv`,
`MATCH_MAX` 32^2 as sc4art's for Tsvirkunov): 00 and 01 Small Police Station, 02 Courthouse, 03 Gazebo, 07 Retail
Stores, 08 Lam Banking, 13 Mayor's House, 14 Hagia Sofia, 15 City Hall, 16 Main Library, 17 Faneuil Hall, 18 Large Fire
Station, 19 Small Fire Station, 20 Elementary School, 22 City Museum, 23 Local Branch Library, 29 Tsvirkunov
Electronics, extra/lee_avionics. Each looked at (`work/contact_0.jpg`, `contact_1.jpg`). The 12 others change by under
100 pixels and keep the published sheet.

In-city strips are all from new game frames (`dev\darktone\tree`, windowed 1430 x 900, posted input and Frida game
calls, harness claimed and released for every run):

- Madison: the 13 civic, park, reward and landmark looks placed with `work/lab.py place` (forumshots' lab pointed at
  this tree). The first spots left City Hall in front of Hagia Sofia and pylons over the Elementary School, so these,
  the Branch Library, Courthouse, Faneuil Hall and Large Fire Station have copies in open land: Hagia (204,223),
  Elementary School (212,223), Branch Library (214,213), Courthouse (219,216), Faneuil Hall (207,213), Large Fire Station (216,226). Several frames caught the blinking no-power bolt: up to 17 dumps
  per sheet slot were taken and the best match kept.
- Retail Stores, Lam Banking: forumshots' commercial save (`runs/com/saves/save03.sc3`), Tsvirkunov: the industry save
  (`save09.sc3`), Lee Avionics: the same save at lot (32,150) (the default lot (157,235) matched at RMS 65), all with
  churn off (`work/grow_lab.py`).
- Match RMS on the sheet slot (`work/spec_final.txt`): 2.6 to 3.4 for 11 of them, Lam Banking 6.4, Branch Library 9.6,
  Courthouse 11.2 (trees in front), Retail Stores 16.3, Lee Avionics 18.6, City Hall 19.2 (Hagia's minaret beside it),
  Tsvirkunov 31.2 (a grown neighbour in front, sc4art had 31.3). Looked at: the right building, whole, no bolt.

Game PIDs started and stopped by this session: 11840, 11832, 9396, 25320, 22472, 15992, 3680, 21564 (lab.py) and
24792, 23444, 9504, 20876, 10332, 20716, 24612, 25252, 1508 (grow_lab). Only the start-up `0xC0000096 at
SC3U.exe+0x84122` in each log. No BMP left.

## 5. Pictures (`owner_shots\`, local)

| file | what |
|---|---|
| 01 | police cars: baked before, after, SC4 tone (`baked_raw`), zoom 4 x4; forum sheet crop before and after |
| 02 | trees: Hagia Sofia crowns, Mayor's House hedges and shrubs, Gazebo, before and after |
| 03 | dark roofs: Small Fire Station, Local Branch Library, Large Fire Station, before and after |
| 04 | palette off: Small Fire Station and Mayor's House vegetation before and after (no change) |

## 6. Files

Code in `dev\darktone\wt` (no commit): `re/tools/bldimport/bldrender.py` (`_tone_toe`, STYLES), `re/tools/bldimport/bldweb.js`
(same float32 op order), `docs/buildings/importer/bldweb.js` (`sync_css.py --publish`), `docs/buildings/index.html`
(one clause on `baked_sharp`). Records (MAIN): this file, `re/sessions/STATUS_darktone.md`. Local: `owner_shots\`,
`fd\`, `runs\`, `p50t\`, `p100t\`, `verify\sc4cmp\forum\` (re-made sheets), `dev\darktone\work\` (mock, conversions,
tools, numbers).
