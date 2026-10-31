# graphfix: Graficas axis on the plot's left edge, inside the plot, right on first show (owner report 2026-10-31)

Owner (Spanish, `owner_report.png`, Energia % only): "The scale should be at the far left of the graph, nothing may render
outside it (it fixes itself when unticking and ticking again)." In the picture the ticks and numbers sit about 40 native px
in from the plot's left edge and the "0" is drawn under the plot, over the year row and the checkboxes.

## Cause

`gx_after` (GRAPHAXIS block, `sc3resize.c`) placed the axis at `chart abs - page abs`. On the page's first render, which is
every time Ver datos opens the Graficas page (a new page object each time), those absolute rects are not final yet. Logged
in this tree with the released build, every open:

```
GRAPHAXIS> page 0x160220E0 ...: on 1 cols 1 mode 3 plot 1 10 167 y0 167 off 46 44 | scale 59 rgb FF6800 ...
GRAPHAXIS>   chart local [6 10 362 199] abs [84 84 440 273], page abs [38 40 420 436]
```

Every later render (a checkbox click, a range radio) logs `off 6 10`, which is the chart's local rect. So the whole axis
sat 40 px right and 34 px down until the next render, and the bottom label's clamp used the same wrong offset, so it did
not hold the "0" inside. A re-tick only "fixed" it because it renders the page again. The plot rect and the Y range were
already right on the first render (`plot 1 10 167 y0 167` both times). Old runs in `verify/graphaxis/runs/*` show the same
`off 46 44` on each first render.

## Fix (GRAPHAXIS block only, `SC3RESIZE_GRAPHAXIS=0` still turns the whole axis off)

- The offset comes from the chart's local rect (`+0x80` / `+0x84`) when the page is its parent (`+0x3c`), which it is.
  Parent-local rects are final on the first render. The absolute difference stays only as the fallback for a chart that is
  not a direct child (not seen). The log line now says `local` or `abs`, and the plot's right edge.
- Column 0's tick starts on the first pixel inside the plot's left frame line (`pl + 1`, was `pl + 2`), the number right
  after the tick. Column 1 (2 graphs on) follows 46 px later, as before.
- Ticks are clamped into the plot rows too (a value at the bottom line used to draw its tick on the x-axis line, one row
  under the plot). Label boxes were already clamped top and bottom, now against the right offset.
- A label box that would cross the plot's right edge (`+0xb4`) is narrowed, and a column with no room left hides.
  With today's 255 px plot and at most 2 columns this never triggers. It is a guard.

No other behaviour changed. Range switching, the column layout, units and the 3-or-more hide rule are as before.

## Check (dev/graphfix/tree, all mods, Berlin, posted clicks only, `re/tools/graphaxis_lab.py`)

Each "reopen" closes Ver datos with its X and opens it again on Graficas: the first render the owner sees.

| case | before (released build) | after |
|---|---|---|
| reopen, Energia % only, 2.25x | `off 46 44`, axis 40 px in, "0" under the plot (= owner picture) | `off 6 10 local`, on the edge, "0" inside |
| reopen, Fondos + Energia, 2.25x | same shift, both columns | both columns from the edge, all labels inside |
| same two at 1x (`SC3RESIZE_DLGSCALE=0`) | same shift, "0" lost under the plot | on the edge, inside |
| 10 anos / 100 anos / 1 ano radios | | axis stays put (mode 4 / 5 / 3 logged) |
| live resize 2560x1351 -> 1600x900 (1.5x) -> 2560x1351 | | stays on the edge at each factor, reopen at 1600 too |

Pictures (`owner_shots\`, dialog crops at screen resolution):
`1_antes/despues_1grafico_2.25x`, `2_antes/despues_2graficos_2.25x`, `3_antes/despues_1grafico_1x`,
`4_antes/despues_2graficos_1x`, `5_despues_100anos_2.25x`, `6_despues_ventana_1600x900_1.5x`,
`7_despues_vuelta_a_2560_2.25x`. Logs and strips: `runs\before*`, `runs\after*`.

## Not driven

- A live change of the interface scale option and loading another city. Both go through what was checked: the axis is laid
  out in native page pixels and DLGSCALE only resamples the dialog (factor 1x, 1.5x and 2.25x checked, plus live
  resizes), and a city load closes Ver datos, so the next open is the reopen path above (new page object, first render).

## Lab changes (`re/tools/graphaxis_lab.py`)

`NAME:reopen` (close Ver datos, open it again on the same view), `NAME:size=WxH` (live resize, HUD click points
recomputed), `--dlg x,y` (dialog origin when dialogs are native: the GRAPHAXIS "dialog abs" line names the page, 38,40
inside the dialog), strip crops each frame at the dialog box it was taken with.
