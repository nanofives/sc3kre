# lvwrap A/B (2026-11-14, LIVING-PC, child/lvwrap 64ae198)

City: Berlin, Germany, dev/lvwrap tree. To push the true land value average past 255 the tree's netmod overlay
`mods\netmod\overlay\Apps\Sys\SYS.PAK` (the copy the game opens with netmod installed, not `Apps\Sys\SYS.PAK`) has
`SC3LandValue.INI [TuningParameters]` Res/Com/IndCityCenterEffect = 250 everywhere and WaterEffect = 70. Stock Berlin
averages 88. Lab: `py -3.12 re/tools/lvwrap_lab.py --tag <observe|cap> --mode <2|1> --stores 6` (speed 4, posted input).

Numbers are logged by sc3simrun LVWRAP after each store; the tax is the game's own SIMMISC 0x100090a7 for R / C / I.

| store | true average | observe (stock wrap): byte, R / C / I a month | cap: byte, R / C / I a month |
|---|---:|---|---|
| 1 | 128 | 128: 7,098 / 5,582 / 2,168 | 128: 7,098 / 5,582 / 2,168 |
| 2 | 259 | 3: 1,606 / 1,399 / 574 | 255: 11,506 / 10,251 / 4,226 |
| 3 | 267..269 | 13: 1,582 / 1,342 / 551 | 255: 12,032 / 9,750 / 4,059 |
| 4..8 | over 256 | 9..11: R 1,690..1,803 | 255: R 11,950..13,022 |

Budget window (Ingresos), February 2068: Impuesto residencial so far 1,803 (observe) / 13,000 (cap), year estimate
21,636 / 156,000. Graph: Valor del Terreno runs along the bottom (observe) and at the top, 255 of the fixed 260
(cap).

Pictures: `owner_shots/AB_budget_ingresos.png`, `owner_shots/AB_graph_valor_terreno.png` (left observe, right cap),
single frames `owner_shots/{observe,cap}_*.png`. Logs: `runs/{observe,cap}/simrun.log`, `lv.json`.

Not run in game: mode 0 (stock bytes, the block does not arm; the code path only logs `### LVWRAP: off`).

## Fix-up (3d6b834): the tax formula, measured

The first table does not fit `max(avg, 5) * 0.0143` with a constant base. The reason: `sc3_budget_read_ini`
SIMMISC `0x100053bb` overwrites the image defaults at load from `SC3BudgetLayer.INI`: floor `MinAverageLV=35`,
factors `LVTo{Res,Com,Ind}TaxTransmogrifier` 35/45/50 x 0.0001. sc3simrun now logs (with `SC3SIMRUN_LVWRAP_TAX=1`)
the inputs `0x100090a7` reads, from the same addresses, next to its result:

| run | true avg | byte | floor | factors | n R | game R tax | recomputed |
|---|---:|---:|---:|---|---:|---:|---:|
| d_check | 128 | 128 | 35 | 0.0035/0.0045/0.0050 | 792,278 | 7,098 | 7,099 |
| d_check | 259 | 3 | 35 | same | 664,697 | 1,628 | 1,628 |
| d_check | 269 | 13 | 35 | same | 647,078 | 1,585 | 1,585 |
| d_cap | 259 | 255 | 35 | same | 643,339 | 11,482 | 11,483 (by hand) |

So tax = (rate x n / 100) x max(avg, 35) x factor: a wrapped byte under 35 pays 35/255 of the tax at 255 for the same
`n`. `n` (last month's valve supply) moves between months (R 545k..792k), so stock and fix are compared per store.

No-env launch (`runs/noenv`, no `SC3SIMRUN_LVWRAP*` set): `### LVWRAP: mode=1 (land value average capped at 255),
armed=1`, 3 average lines (128, 259 -> 255, 269 -> 255), 0 tax lines.
