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

---

# Part 2 built: five new graphs (owner pick 2026-10-30, block GRAPHNEW, `SC3RESIZE_GRAPHNEW=0` off)

Owner pick: 1 income vs expenses, 2 power and water supply vs demand, 3 R/C/I demand, 4 air vs water pollution.

## Layout (agreed before building)

The 16 stock checkboxes fill rows 0..5. The free cells are row 5 col 1 and rows 6..7 in cols 0..1; col 2 of those rows
is the 1 / 10 / 100 years radios. The game's own placement would put the 17th checkbox on the "1 ano" radio, so the
mod moves the 5 new ones after the game lays out the page. No stock control moves except Agua %, which the game itself
puts at row 5 col 0 once the list is longer. Mockup: `mockup_layout_5_new.png`.

| checkbox | lines | values |
|---|---|---|
| Ingresos/Gastos | Ingresos, Gastos | money per month (all budget income / expense lines, departments included) |
| Energia of./dem. | oferta, demanda | game power units; demand counts unpowered tiles too |
| Agua of./dem. | oferta, demanda | supply = pump capacity, "demanda" = water delivered (the game keeps no unmet water total) |
| Demanda RCI | R, C, I | the HUD bar's scale, -1000..1000, 0 in the middle |
| Contam. aire/agua | aire, agua | % of the game's UI maximum (same base as Polucion) |

Lines of one graph share one scale and one axis column. The axis counts checkboxes, not lines: 1 or 2 graphs on = axis,
3 or more = hidden. Sources and RVAs: `re/analysis/GRAPH_SERIES.md` section 7.

## History

The game's series keep 12 months / 10 years / 10 decades only in memory. The mod writes them to `<city>.sc3.graphs` next
to the city after each successful save, and reads them back when the city is opened again at the same date. The `.sc3`
is written by the game's own save, unchanged. Without the mod the extra file is ignored.

## Check (dev/graphaxis/tree, all mods, client 2560x1351, posted input only)

| step | result |
|---|---|
| Berlin copy `GraphTest.sc3`, ~10 months at speed 4, Save (menu command 0x10009002) | `GraphTest.sc3.graphs` written (1,512 bytes), log `history written ... closed month key 24814` |
| reopen `GraphTest.sc3` | log `history read from the .graphs file`; the graphs show the months recorded before the save (`0_cargada_con_historia.png`) |
| each graph after ~8 more months | `1_ingresos_energia.png`, `2_energia_agua.png`, `3_agua_rci.png` (2 graphs, 2 columns each), `4_contaminacion_sola.png` (1 graph) |
| 4 graphs on | axis hidden (`5_muchos_sin_eje.png`) |
| `SC3RESIZE_GRAPHNEW=0` with the saved city | the stock 16-checkbox page (`6_interruptor_apagado_GRAPHNEW0.png`) |
| stock game, no mods (`SC3MODS_OFF=1`), saved city | ran 120 s, no error dialog from that process. No picture (desktop grab blocked by another session's window) |

Values on Berlin per month: income ~12,500, expenses ~12,400, power supply 195,168 vs demand ~157,000, water 182,000 vs
132,000, R/C/I 570 / 440 / -700..600, air 18-19 %, water 5 %.

Pictures: `owner_shots_nuevos\` (dialog crops at 2.25x).

## Not checked / open

- 10-year and 100-year views were not run long enough to fill (a year takes ~1 min at speed 4, a decade ~10 min). They
  use the same rings and roll-up rule as the stock series. The saved file round-trips all three rings.
- Months before the mod was installed show as 0 (no data). The game does not keep these values anywhere older.
- With many lines on, the game's own line-end labels stack on each other, as with the stock graphs.
- Autosaves get no `.graphs` file: sc3autosave saves to a temp name and puts the city name back, so the city's own file
  never changes. Loading an autosave starts the new graphs empty.
