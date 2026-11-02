# graphs2 results (2026-11-02)

Verdict: built and checked in game (Berlin, windowed 2560x1351, HUD 2.25x). All six owner items done. Libraries and
museums keep no user count in the sim; that is shown, not invented.

| # | Owner item | Result | Picture |
|---|---|---|---|
| 1 | Graficas line-graph tabs as real tabs, one aligned row | 5 drawn tabs hang under the chart, the selected one lighter, taller and joined to the chart | `owner_shots/5_graficas_redes.png`, `6_graficas_economia.png` |
| 2 | Cuadros radios become tabs | 7 tabs in the same style under the Cuadros chart: Educacion, Salud, Poblacion, Energia (the stock "Electricidad" chart, shorter word so 7 fit), Basura, Agua, Transporte | all `1_..4_` |
| 3 | Education: capacity vs students | Under the stock EQ chart: schools 163,2K pupils / 123K places (133%), colleges 67,9K / 45K (151%), libraries (0), museums (7) 516K residents aged 25-89 / 581K places, teachers 4.715, professors 1.038, strike | `1_cuadros_educacion.png` |
| 4 | Health: patients vs capacity | Under the stock life-expectancy chart: patients 52,2K / beds 39K (134%), doctors 2.990, strike | `2_cuadros_salud.png` |
| 5 | Water sources + processing | Pumps (153) 164,4K of 229,5K, towers (23) 12,8K of 13,8K, desalination (3) 6.004 of 15K, delivered 132,2K of 183,2K (72%), 91 of 13.831 buildings dry, water pollution 5,3%; treatment last month 1,1M of 36,8M treated (3%), 1 plant (aging) | `3_cuadros_agua.png` |
| 6 | Transportation methods used | Trips using each network, last month, 1.473 trips: streets 63%, highways 3,0%, bus 0%, rail 5,3%, subway 7,5%, no network 31,1%; no destination 0,4% | `4_cuadros_transporte.png` |

Off switch: `SC3RESIZE_VDTABS=0` gives the stock radio pages back (`7_apagado_VDTABS0_cuadros_stock.png`).

## What the sim keeps (sources with RVAs: `re/analysis/GRAPH_SERIES.md` section 9)
- Students and patients are demand counts (every resident of the age band; population x pollution rate), not enrolment.
- Libraries and museums: places and building count only. No user count: their seats feed the per-age EQ arrays mixed
  with schools. The bar compares places with the residents of the age band they serve, which is the population the
  sim compares the seats with. With no library built, the [Library] INI section is never read (lazy load in the
  library ctor), so the library age band is not shown.
- Not stored: unmet water demand, water held by towers, sewage volume, trips per mode (counted by the mod, TRIPMODES).

## Checks
- Per-source water outputs add up to the layer supply exactly (165,354 + 12,842 + 6,140 = 184,336).
- Highway share of trips that used a network 4.9%, inside the hwtrips range (4.2-7.1%).
- Tab clicks on both pages, Ver datos closed and reopened, tab kept across starts (sc3resize.ini [graphs] tab,
  [cuadros] tab), no fault logged by the new code over 7 runs.

## Not covered
- English text (owner install is Spanish). A city with libraries. Cuadros tabs under sc3cartrips (dev tool: TRIPMODES
  refuses and the Transporte tab says counting is off). Hover colour of a tab caption after a click stays blue until
  the pointer moves (posted clicks leave the hover state).

Runs: `runs/base` (stock look), `t1..t7`, `off`.
