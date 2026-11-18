# bldlook results (round 2026-11-18c): rendered buildings look like the stock art by default

**Verdict: done.** `bldrender.py` has three named styles. `stock` is the default, `stock_sharp` is the same with a
native zoom 4, and `clean` is the 2026-11-18b look (byte for byte, 40 of 40 frames compared with the old renderer).
The three test models, rendered in the default style, grew in Sacramento by the first autosave (2.4 game-run minutes
at speed 4): 531 lots of 38000, 517 of 38001, 94 of 38002. Notes: `re/analysis/BUILDING_ART.md` 4.1.

## What makes stock building art look the way it does (75 stock growables, 1,200 frames, zooms 0-3)

1. **Zoom 4 is zoom 3 doubled** (1,908 of 1,936 census frames). Zoom 3 is not zoom 2 doubled: 4 % of its 2x2 blocks
   are one colour. Each smaller zoom has its own render (zoom z against zoom z + 1 halved: 13-14 of 255 mean abs).
2. **At most 255 colours per frame**: 1,200 of 1,200 frames, zoom 3 median 248, max 255. An 8-bit palette per frame
   went in before the RGB565 export.
3. **The lit wall follows the model's axis, not the screen.** Right / left luminance at zoom 3 is 0.81 / 1.27 /
   0.81 / 1.23 in slots 0-3: the model's +-u walls are light and +-v walls dark in every slot, the same rule as the
   stock highway walls. Grown lots stay at state 0, so in view rotations 1 and 3 every stock house has its lit face on
   the lower right. `clean` lit the lower-left face in every slot (0.88 / 0.88 / 0.76 / 0.91), which is the opposite
   of the houses next to it in two of the four views.
4. **The lawn is darker along the two front edges of the lot.** A heat map of dark-lawn pixels over every 1x1 and
   2x2 lot (`work/shadowmap.png`) shows it, and there is no cast shadow beside the building. Dark-lawn share:
   0.18 / 0.10 / 0.04 / 0.00 at zooms 3..0.
5. **The roof is not the brightest surface**: the lit wall is lighter than the roof.
6. At smaller zooms contrast and saturation fall and the lawn gets lighter.

## Metrics per style (median over frames; stock = 75 buildings, styles = 6 models: 3 test + 3 classifier samples)

"Structure" = opaque pixels that are not lawn green. Contrast = (p90 - p10) / p50 of structure luminance.
Texture = mean abs(luminance - 3x3 mean) inside the structure. Dark lawn = lawn pixels below 0.7 x the lawn median.


zoom 3
| metric | stock (75 bldgs) | clean | stock | stock_sharp |
|---|---|---|---|---|
| colours | 248.0 | 138.5 | 143.5 | 143.5 |
| shadow_dx | 0.006 | 0.176 | 0.001 | 0.001 |
| shadow_dy | 0.183 | 0.096 | 0.239 | 0.239 |
| struct_L_p10 | 0.201 | 0.337 | 0.244 | 0.244 |
| struct_L_p50 | 0.400 | 0.395 | 0.366 | 0.366 |
| struct_L_p90 | 0.688 | 0.665 | 0.731 | 0.731 |
| struct_contrast | 1.234 | 0.653 | 1.106 | 1.106 |
| struct_S | 0.225 | 0.132 | 0.184 | 0.184 |
| hue_spread_deg | 60.3 | 56.5 | 60.7 | 60.7 |
| outline_L_ratio | 1.053 | 0.997 | 1.018 | 1.018 |
| texture_hf | 0.045 | 0.019 | 0.032 | 0.032 |
| grad | 0.066 | 0.028 | 0.046 | 0.046 |
| shadow_frac | 0.178 | 0.016 | 0.120 | 0.120 |
| grass RGB | [94, 136, 73] | [97, 128, 76] | [97, 136, 74] | [97, 136, 74] |

zoom 2
| metric | stock (75 bldgs) | clean | stock | stock_sharp |
|---|---|---|---|---|
| colours | 236.0 | 99.5 | 133.0 | 133.0 |
| shadow_dx | -0.012 | 0.080 | -0.036 | -0.036 |
| shadow_dy | 0.192 | 0.099 | 0.258 | 0.258 |
| struct_L_p10 | 0.262 | 0.345 | 0.277 | 0.277 |
| struct_L_p50 | 0.427 | 0.399 | 0.383 | 0.383 |
| struct_L_p90 | 0.661 | 0.665 | 0.700 | 0.700 |
| struct_contrast | 0.941 | 0.630 | 0.947 | 0.947 |
| struct_S | 0.179 | 0.121 | 0.160 | 0.160 |
| hue_spread_deg | 55.3 | 65.4 | 64.0 | 64.0 |
| outline_L_ratio | 1.040 | 1.006 | 1.002 | 1.002 |
| texture_hf | 0.046 | 0.029 | 0.039 | 0.039 |
| grad | 0.067 | 0.041 | 0.056 | 0.056 |
| shadow_frac | 0.098 | 0.012 | 0.092 | 0.092 |
| grass RGB | [99, 133, 81] | [98, 128, 76] | [101, 132, 81] | [101, 132, 81] |

zoom 1
| metric | stock (75 bldgs) | clean | stock | stock_sharp |
|---|---|---|---|---|
| colours | 204.5 | 54.5 | 67.0 | 67.0 |
| shadow_dx | 0.012 | - | 0.252 | 0.252 |
| shadow_dy | 0.220 | - | 0.200 | 0.200 |
| struct_L_p10 | 0.322 | 0.366 | 0.319 | 0.319 |
| struct_L_p50 | 0.456 | 0.408 | 0.417 | 0.417 |
| struct_L_p90 | 0.639 | 0.609 | 0.635 | 0.635 |
| struct_contrast | 0.700 | 0.525 | 0.684 | 0.684 |
| struct_S | 0.137 | 0.085 | 0.133 | 0.133 |
| hue_spread_deg | 48.8 | 61.8 | 72.0 | 72.0 |
| outline_L_ratio | 1.022 | 1.002 | 1.041 | 1.041 |
| texture_hf | 0.044 | 0.036 | 0.043 | 0.043 |
| grad | 0.064 | 0.045 | 0.055 | 0.055 |
| shadow_frac | 0.035 | 0.000 | 0.000 | 0.000 |
| grass RGB | [104, 131, 90] | [98, 128, 76] | [107, 131, 90] | [107, 131, 90] |

zoom 0
| metric | stock (75 bldgs) | clean | stock | stock_sharp |
|---|---|---|---|---|
| colours | 104.0 | 23.5 | 23.0 | 23.0 |
| shadow_dx | 0.174 | - | - | - |
| shadow_dy | 0.318 | - | - | - |
| struct_L_p10 | 0.376 | 0.442 | 0.434 | 0.434 |
| struct_L_p50 | 0.485 | 0.561 | 0.573 | 0.573 |
| struct_L_p90 | 0.629 | 0.664 | 0.698 | 0.698 |
| struct_contrast | 0.511 | 0.394 | 0.429 | 0.429 |
| struct_S | 0.106 | 0.031 | 0.072 | 0.072 |
| hue_spread_deg | 43.2 | - | 48.8 | 48.8 |
| outline_L_ratio | 0.997 | 1.021 | 1.077 | 1.077 |
| texture_hf | 0.036 | 0.024 | 0.032 | 0.032 |
| grad | 0.057 | 0.055 | 0.057 | 0.057 |
| shadow_frac | 0.000 | 0.009 | 0.009 | 0.009 |
| grass RGB | [114, 137, 104] | [88, 118, 70] | [117, 140, 105] | [117, 140, 105] |

| LR ratio z3 slot 0/1/2/3 | 0.81 / 1.27 / 0.81 / 1.23 | 0.88 / 0.88 / 0.76 / 0.91 | 0.82 / 1.35 / 0.73 / 1.12 | 0.82 / 1.35 / 0.73 / 1.12 |
| z0_vs_down_z1_MAE | 12.882 | 17.361 | 27.746 | 27.746 |
| z1_vs_down_z2_MAE | 13.066 | 5.172 | 12.130 | 12.130 |
| z2_vs_down_z3_MAE | 13.944 | 3.623 | 11.457 | 11.457 |
| z0_2x2_uniform | 0.000 | 0.000 | 0.000 | 0.000 |
| z1_2x2_uniform | 0.007 | 0.105 | 0.000 | 0.000 |
| z2_2x2_uniform | 0.018 | 0.212 | 0.019 | 0.019 |
| z3_2x2_uniform | 0.041 | 0.381 | 0.017 | 0.017 |

| zoom 4: share of 2x2 blocks of one colour | stock 1.00 (scale 2) | clean 0.45 | stock 1.00 | stock_sharp 0.02 |
|---|---|---|---|---|

Colours per frame are lower for the styles than for stock because the test models have little detail. The palette
cap (255) holds: the most colours in any `stock` frame is 165. What the styles do not reach: stock p10 0.20 against 0.24
and texture 0.045 against 0.032 at zoom 3. Both come from painted detail (windows, eaves, porches) that the test
models do not have. More model detail closes the gap; a global filter would not.

## The styles (`bldrender.STYLES`)

| style | light | zoom 4 | colour and surface |
|---|---|---|---|
| `stock` (default) | axis light (model +-u walls 0.37, +-v walls 0.20, roof 0.42 x up, ambient 0.47); cast shadows from the screen sun only on surfaces facing it, strength 0.25-0.70 by zoom | zoom 3 doubled | vibrance (less on already saturated colours), luminance-only contrast by zoom, 255-colour palette per frame, lawn by zoom fitted to the stock lit lawn, smooth grain (6 and 2 px), front-edge lawn band |
| `stock_sharp` | as stock | native | as stock |
| `clean` | the 2026-11-18b screen sun | native | unchanged |

Choose one: `render_model(..., style="clean")` or `SC3BLD_STYLE=clean` for a `bldimport.py build --force` run
(the render cache key does not cover the variable). `bldimport.py` does not pass a style yet (bldfile owns that file
this round). The proposal is to read `x_bldrender.style` per model and add it to the cache key.

## Checks run

| check | result |
|---|---|
| `clean` vs the 2026-11-18b renderer (house_tex 1x1, block 2x2, 20 frames each) | 0 of 40 frames differ |
| `bldimport.py calibrate --game dev\bldlook\tree` (10 stock buildings, 1x1-4x4, zooms 0-3) | 0 frame(s) differ |
| `bldimport.py build` + `check` of the 3 test models, default style | 3 of 3 ok, 20/20 frames equal; zoom 4 PNG = zoom 3 doubled |
| rebuild after the last edit (comments only) | B1D10001_bldimport.DAT sha256 unchanged |
| in game, `bld_lab.py --tag run1` (test slot), Sacramento, windowed 1600x1000, posted keys only, PID 12584 started and stopped by the lab | grown 531 / 517 / 94; 9 frame dumps; 1 fault line: `0xC0000096 at SC3U.exe+0x84122` at 70 ms, before the city loads, the same line as bldrender run1 and four older dataview runs, so this change did not cause it |

The first lab attempt got a relative `--out` path. The game runs from `tree\Apps`, so it wrote no log and the lab
reported "city up FAIL" and stopped its own PID. The re-run with an absolute path is the one above.

## Pictures (`owner_shots/`, phone size, at most 1400 px wide)

| file | what |
|---|---|
| `01_styles_zoom3_1x1.jpg` | zoom 3 doubled for viewing: each 1x1 model in clean and stock, 4 slots, next to its class's stock base (115 / 126) |
| `02_styles_zoom3_2x2.jpg` | the same for the 2x2 block against 3020 |
| `03_styles_zoom4_1x1.jpg` | zoom 4 at game size: clean, stock (doubled), stock_sharp (native), stock base |
| `04_styles_zoom4_2x2.jpg` | the same for the 2x2 block |
| `05_sacramento_zoom4.jpg` | Sacramento at zoom 4, default style, test cottages and brick houses among stock houses |
| `06_closeup_zoom4_x2.jpg` | the middle of 05 doubled |
| `07_four_view_rotations_zoom4.jpg` | the same lot in view rotations 0-3 (the lit side swaps with the stock houses) |
| `08_block_2x2_zoom4_x2.jpg` | a grown 2x2 block |
| `09_sacramento_zoom3.jpg`, `10_closeup_zoom3_x2.jpg` | zoom 3 |

## Not done / open

- By eye, the rendered lots' lawn looks a little darker and more olive in game than some stock neighbours. The stock
  lawn varies per building, and the style uses the median of the 75.
- Per-model style in `models.json`: needs the bldimport change above.
- Test buildings are left installed in `dev\bldlook\tree` (remove with `bldimport.py restore --game dev\bldlook\tree`).
