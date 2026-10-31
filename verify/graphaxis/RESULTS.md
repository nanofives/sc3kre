# graphaxis: vertical reference axis on the Graficas page (owner request 2026-10-30)

Owner: "Graphs should have a vertical reference bar on the left that disappears if many graphs are switched on."

## What was built (sc3resize.c, block GRAPHAXIS, `SC3RESIZE_GRAPHAXIS=0` turns it off)

- Detour on SIMUI `0x1002ed75` (the Graficas page renderer). After the game draws, the block reads the series that are on,
  their scale (series vt+0x20) and colour, and the chart's own Y mapping (min / max +0x12c / +0x134, plot rect
  +0xac..+0xb8, y of 0 at +0x16c, SIMUI `0x100703f0` / `0x1007033e`). Values on the axis are real: the plotted value is
  `recorded * 100 / scale`, so a tick at real value R sits where the game would draw R.
- The axis is made of game widgets added to the page: a 5 px tick per round value (the game's line-end leader shape) and a
  label (the game's label class, left-aligned, font 0xf), both in the series colour. So it is scaled by DLGSCALE, drawn
  sharp by NATIVETEXT and follows resizes like the page's own text.
- Round values: 1 / 2 / 5 x 10^k, about 4 steps, shown as `0.5M`, `500K`, `40`, `0`.
- Several series on, decided as follows:
  - 1 series: one column.
  - 2 series: one column each, side by side, each in its series colour. Two series that share a scale share one column.
  - 3 or more: the axis hides. `SC3RESIZE_GRAPHAXIS_MAX=<n>` moves the limit. A third column would cover a quarter of the
    plot.
- Fondos is recorded as `(max(treasury, -100000) + 100000) / 1000` (SIMMISC `0x10007d88`), so its column is converted
  back to money: `500K` is 500,000 in the treasury, `0` is 0. The other 15 series are shown in the units the game
  records. The fixed scales are game indexes (Aprobacion, Valor del Terreno and Crimen 0..260, Educacion 0..150,
  Salud 0..89, Trafico 0..220, Desempleo / Polucion / Agua % 0..100).

## Check (dev/graphaxis/tree, all mods, Berlin, posted clicks only)

Driver: `re/tools/graphaxis_lab.py` (opens Ver datos > Graficas, clicks checkboxes / range radios, FRAMEDUMP after each).

| client | HUD / dialog factor | 1 series | 2 series | Fondos + Aprobacion | 5 series |
|---|---|---|---|---|---|
| 2560x1351 (owner size) | 2.25 | axis 0 / 0.5M / 1M | two columns (Tamano green, Energia orange) | Fondos 0 / 500K, Aprobacion 0 / 100 / 200 | hidden |
| 1600x900 | 1.5 | same | same | same | hidden |

Also checked in the logs: 10 anos range (mode 4) keeps the axis (scale does not depend on the range); switching series on
and off redraws the axis at every click.

Pictures (`owner_shots\`, dialog crops at screen resolution):
`1_un_grafico_*.png`, `2_dos_graficos_*.png`, `2b_dos_graficos_fondos_aprobacion_*.png`, `3_muchos_graficos_sin_eje_*.png`,
each at `2560x1351` and `1600x900`.

## Not checked / open

- A live window resize while the page is open was not driven (the two sizes are separate games). The axis is native page
  content, so DLGSCALE re-renders it like the checkbox text.
- The axis labels sit inside the plot and can overlap a line (e.g. "200" on the Aprobacion line). The page has no free
  space left of the plot (the icon column touches it).
- Lab trap: the game handles a posted click right after the next present. The lab dumps a throwaway frame first.
- `tree\Apps\SC3.cfg` was un-hard-linked in this tree before toggling checkboxes (the game keeps the page's checkbox state
  in prefs).
