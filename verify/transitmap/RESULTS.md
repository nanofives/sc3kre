# transitmap RESULTS (round 2026-11-02)

Rewritten 2026-11-02 after the original was lost with `dev\transitmap\wt`. Content rebuilt from the run logs in
`runs\` and the session's notes. No new runs.

Build: child/transitmap (merged to main as cd3dcef / 17d3160). `sc3dataview.c` TRANSIT block (new panel),
`sc3resize_vdbars.c` TRIPCELLS (per-origin-cell trip counts). Switches: `SC3DATAVIEW_TRANSIT=0`,
`SC3RESIZE_TRIPCELLS=0`. Driving: posted input only (dataview_lab), no real mouse or keyboard. City: Berlin.

## What it is

New Ver datos panel "Mapa de transporte publico", icon slot 10 (under Mapa de zonas, train icon 0x14 from
`000005E5_Maps.ixf`), panel id 0x606. SIMUI `FUN_10044430` fills slots 0..9 (maps), 12 (Cuadros), 13 (Graficas),
so 10 and 11 were free. Hook at SIMUI+0x4436b, then `FUN_1004458c(dialog, panel, slot)`. The panel is the traffic
panel factory 0x1004ac53 with its own copy of vtable 0x100a8bd8 (0x26 slots), Init +0xc re-implemented from
0x1004acf9. Slot +0x8c 0x1004773c runs with the id swapped to 0x602 (it leaves the view mode uninitialised for
unknown ids).

Map: red = trips from that cell with no bus, train or subway, transit colour = trips on transit. The game stores
no trip mode, so TRIPCELLS counts at the route_trip pop (SimTransit+0x72f8) per origin cell (origin node type
0x80, rect 1x1). A month in Berlin is about 1,250 counted trips, which draws as dots, so the map keeps a 1/8 fade
history and sums a 5x5 neighbourhood.

## Runs

| run | what | result |
|---|---|---|
| T1 | panel opens right after load | caption "Todavia no hay viajes contados", 0 cells. Cause: lab cities load PAUSED |
| T2 | same, speed keys 1-4 | still 0 trips. Speed keys do not unpause, the lab must post P (vk 0x50) |
| T3 | sim running (P posted), 16 months counted | "Mes pasado: 16,4% de 880 viajes en transporte publico", last month 1,263 trips, 144 transit, 383 no network. 1,774 cells with trips (315 transit), 1,772 carry the game's trip bit. Raw one-cell map was dots, which led to the fade + 5x5 sum |
| T4 | final build, fade + 5x5 | month 14: 13,3% of 977 (1,473 trips, 130 transit, 496 no network), 44,745 cells drawn. Month 19: 15,8% of 1,012 (1,495 trips, 160 transit, 483 no network), 45,619 cells drawn, 945 all transit |

Percent is transit over trips that had a network (total minus "no network").

Each run folder holds `dataview.log`, `resize.log` and `strip.png`. T4 also has frame dumps in `fd\`.

## Owner pictures

`owner_shots\`:
1. `1_icono_bajo_mapa_de_zonas.png` the new icon under Mapa de zonas
2. `2_mapa_transporte_publico_berlin.png` the panel on Berlin
3. `3_trafico_para_comparar.png` stock traffic panel for comparison
4. `4_usar_mapa_minimapa.png` "usar mapa" on the minimap

## Lab traps

- Cities load paused. Post P, not 1-4.
- `dataview_lab --out` must be an absolute path. Log paths are resolved from the game folder, else "city up FAIL"
  (fixed in `re/tools/dataview_lab.py` in this stream).

## Open

- Owner hand test of the look (colours, caption wording) not done.
- Slot 11 is still free for another panel.
