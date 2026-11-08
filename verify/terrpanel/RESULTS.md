# TERRPANEL: taller terrain editor panel + "Bosque denso" (child/terrpanel, 2026-11-06)

Owner (2026-11-06): forest fill as a tick in the New City terraformer, "do a taller panel". Plan and decisions:
`re/analysis/COMMUNITY_MODS.md`. Code: `re/harness/src/sc3resize_terrpanel.c` (ignored by the deny-by-default
.gitignore: `git add -f`), hooks in `sc3resize.c`. `SC3RESIZE_TERRPANEL=0` = stock panel.

## What it does

- The terrain editor panel grows from 172 x 480 to 172 x 544 (same width, so the sc3resize dock still finds it).
- The stock art keeps its size: the panel's background mode at `+0xc0` goes from 1 (stretch) to 0 (plain blit)
  [CONFIRMED @ SIMUI 0x1002cb73]. A framed strip under it holds "Más opciones:" and a "Bosque denso" checkbox.
- Ticking the box plants the densest trees on every land cell through the game's own `InitFloraLevel`
  (terrain `vt+0x90`, SIMDIRT `0x100064a0`). While ticked, every Re-Generate is filled too (terrain message handler,
  vtable slot SIMDIRT `0x1002046c + 0xc`, wrapped). Unticking applies from the next Re-Generate.

- The six tool buttons are moved onto the circles printed in the background art. Stock builds them 43 px apart
  (x 0x1c / 0x47 / 0x72, rows 0x156 / 0x17e, SIMUI `0x1005f621`) but the art circles are 41 px apart and 1 px higher:
  matched against the decoded art (image 2 of `22DEC90F_TerrEdit.ixf`, QFS at +0x18, RGB565), the circles sit at the
  button + (3, -1), (1, -1), (-1, -1) per column. Stock therefore shows a second ring / doubled shadow round each button.
  After the move the best match is (0, 0) for all six and the pixels that differ from the art in the tool area drop
  from 4166 to 362 (the buttons' own anti-aliased edges). Child rects at `+0x14` are screen coords; SetPos `+0xcc`
  takes parent-local ones.

## Measured in game (256 map, dev tree, 800x600, frames from the in-process FRAMEDUMP: the monitor was asleep)

| check | result | picture |
|---|---|---|
| stock panel, `SC3RESIZE_TERRPANEL=0` | reference | `owner_shots/1_stock_panel.png` |
| first build: window grown, background left on stretch | art stretched 480 -> 544: slider icons drift, a ghost Regenerate frame under the button | `owner_shots/0_first_try_stretched_art.png` |
| fixed build | stock art identical to the reference, strip below, docked and centred | `owner_shots/2_taller_panel.png` |
| tick "Bosque denso" | whole map forested, water left clear, 156-187 ms | `owner_shots/3_bosque_denso_ticked.png` |
| Re-Generate with the tick on | new terrain, filled after the generator (172 ms) | `owner_shots/4_regenerate_with_tick.png` |
| tool buttons on their circles | 6 of 6 moved, stock ring gone | `owner_shots/6_tools_before_after.png`, `owner_shots/7_tools_zoom_before_after.png` |
| Accept | city starts with the forest, Pob 0, no fault | `owner_shots/5_city_after_accept.png` |

The checkbox notifies the panel's DoWinMsg with message 3, p3 2, p4 = our id (logged with `SC3RESIZE_TERRPANEL_LOG=1`).

## NATWORLD: Classic Natural World colours, second checkbox in the strip ("Natural World")

Code: `re/harness/src/sc3resize_natworld.c` (git add -f). Data: `sc3natworld.bin` beside sc3resize.dll, built by
`re/tools/natworld_pack.py <Natural World package> <out>` (only the colours of the 8 palette images; the game's files
are never replaced). Hook: SIMDIRT `sc3_dirt_load_palette` 0x10016cce, 5-byte `mov eax` prologue. After each stock load
of palette 4 (land, instance from the scheme manager) or 6 / 7 / 8 (water, edges) the table is overwritten when the
switch is on. The switch repeats the landscape-change sequence of SIMDIRT FUN_10016c45 for ids 4, 6, 7, 8. Saved as
sc3resize.ini `[natworld] on`. `SC3RESIZE_NATWORLD=0` = not installed.

| check | result | picture |
|---|---|---|
| packing measured on the first stock load | table vs stock file 100.0% as RGB565, rows top-down (both runs) | log |
| tick | terrain and water change at once, 93.8% of the map pixels differ from stock | `owner_shots/9_natworld_on.png`, `12_natworld_off_vs_on.png` |
| untick | back to stock, 0.00% pixels differ from the frame before the tick | `owner_shots/8_natworld_off.png` |
| Re-Generate + Accept with it on | city keeps the colours | `owner_shots/10_natworld_city.png` |
| next game start | switch read back ON, colours from the first load | `owner_shots/11_natworld_remembered.png` |

All 5 landscapes (one game per landscape, New City from the main menu, the Panorama icon clicked, frames with the switch
on and off at the same camera). Icon -> land palette instance read from the scheme manager: icon 1 -> 1, icon 2 -> 3,
icon 3 -> 2, icon 4 -> 5, icon 5 (default) -> 4. Every load logged `palette 4 written`, no fault.

| Panorama icon | instance | map pixels that differ on vs off |
|---|---|---|
| 1 | 1 | 47.5% |
| 2 (winter) | 3 | 9.3% (low ground nearly unchanged, water bluer) |
| 3 | 2 | 41.4% |
| 4 | 5 | 84.5% |
| 5 (default) | 4 | 93.8% (earlier run) |

Picture: `owner_shots/13_natworld_landscapes.png`.

Craterville (landscape 1, high ground), same camera, NW on vs a start with the panel off (`15_natworld_craterville.png`):
stock brown desert becomes near white. Not our write: rows 0..~190 of the author's instance 1 (and 4) are (209,220,233),
where stock has rock browns (85,68,78), (110,78,52). Ver datos map: 0.0% pixels differ. Minimap terrain: unchanged (the
9.4% that differ are the main-view corner and moving sim dots). Both draw their own colours, not the land palette
(`14_natworld_verdatos_minimap.png`). The original mod, installed as files, would leave them unchanged too.

## "Activar mods" row

`k_mt_rows` gains "Panel de terreno ampliado" / "Larger terrain panel" -> `SC3RESIZE_TERRPANEL` (Natural World goes with
it: `nw_install` runs inside `tp_install`). Key `resize.mt_terrpanel` plus the three `tp_*` keys machine-translated into
de/fr/it/nl/sv, `sc3lang.py check` clean for all 7. In game: the row is drawn at the bottom of Funciones
(`16_activar_mods_row.png`), untick + OK logged `MODTOGGLE> SC3RESIZE_TERRPANEL off at the next start` and wrote
`[env] SC3RESIZE_TERRPANEL=0`. Next start: sc3mods.log `[env] SC3RESIZE_TERRPANEL=0 (sc3mods.ini)`, resize.log
`TERRPANEL> off`, stock colours. The ini line was removed afterwards.

## Not ours, found on the way

- New City from a loaded city (options flyout > Nueva ciudad) crashed at `SIMRCI+0x29CA5` before the panel was built.
  Same address as the saltfix session's A/B crash. Tests here start New City from the main menu.
- One start died at `GZGraphicD+0x18C7A` during the intro while Escape was posted every 4 s. The next start, with no
  input until the menu, was clean.

## Not checked

- Larger windows / DLGSCALE-enlarged panel, 512 and 1024 maps (fill time there not measured).
- Weather option for the strip not built.

## WEATHER: "Clima: Lluvia y nubes" on the Opciones de mods page

Code: `re/harness/src/sc3resize_weather.c` (git add -f). Static read by a subagent, addresses checked against the PE:
- SIMMISC `cSC3WeatherLayer` vtable 0x10041000, SetWeather +0x60 = 0x1001b733 (thiscall (type, int), ret 8): stores
  +0x7c / +0x80, posts 0xF2ED2A04. Its season tick 0x1001b4bb calls SetWeather(0) on some season changes. Type not saved.
- SIMSPR `cSC3WeatherViewSimulator`: clouds and rain shown while visibility bytes +0x18 / +0x48 == 0xF. The 0xF2ED2A04
  handler 0x1002b526 sets the weather bit for a non-zero type only when `RandomUint32Uniform(3) == 0`
  (`85 c0 75 7f` at 0x1002b559). That roll is the "fade" the cheat's author reports.

While ticked: the jnz at SIMSPR 0x1002b55b is NOPed, the SetWeather cell SIMMISC 0x10041060 is wrapped (type 0 -> 1),
and 3 s after a new city appears SetWeather(1) is sent once (the view reads the type once when it is built, so a load
showed no clouds before this). Unticked: bytes put back, wrapper passes through, SetWeather(0) now. Saved as
sc3resize.ini `[weather] rain`, off by default; nothing is patched at start unless it is on. Off switch
`SC3RESIZE_WEATHER=0`, also an "Interruptor de clima" row on Activar mods.

| check (Craterville, 800x600, FRAMEDUMP) | result |
|---|---|
| tick + OK, city open | `WEATHER> rain and clouds ON, applied to this city`, clouds and shadows at the far zoom |
| sim at speed 3 from 10/6/1933 to 3/17/1935 (6 season changes) | clouds and rain still there, shadows move |
| untick + OK | `off (stock weather), applied to this city`, sky clear at once |
| restart with `rain=1` saved | `new city: rain and clouds requested` 6 s after start, clouds over the city with the sim paused |

Picture: `owner_shots/17_weather_switch.png`. Not checked: 512/1024 maps, lightning frequency (still the game's own 1 in 3).

## TREEBAR + FILLSLICE (owner hand test 2026-11-08, MARIANO-PC, 1024 map)

Owner: "bosque denso enabled should also depend on the tree bar" and "it froze the game for a few seconds". His log:
`forest fill: 1048576 of 1048576 cells planted, 2157 ms`, one call on the UI thread.

- TREEBAR: the tree slider is the right one (0x72e867af, tree icon in image 2 of 22DEC90F_TerrEdit.ixf), stored in
  the window proc's byte +0x14 [CONFIRMED @ SIMUI 0x1005f352], packed as bits 16..22 of the Re-Generate message
  [CONFIRMED @ SIMUI 0x10060ab2]. Bar 0..0xff -> InitFloraLevel level 0x20..0xff (density 1..7). A bar move while
  ticked refills when the density step changes. `SC3RESIZE_TP_TREEBAR=0` = always 0xff.
- FILLSLICE: one-shot thread timer, 50 ms slices, re-armed 10 ms after each. Accept plants what is left first.
  `SC3RESIZE_TP_SLICE=0` = the old single call.

| check (LIVING-PC, 1024 map, 800x600, dev tree) | result |
|---|---|
| periodic 10 ms timer, 20 ms slices (first try) | 0 fps for the whole 3.7 s: timer always due, dropped |
| one slice per frame from the fnlog idx 0 hook | hook ran ~3 times a second here, 58 s total, dropped |
| tick, bar at 128 | density 4, 55 slices, 3402 ms planting, 7984 ms total, game drew between slices |
| bar dragged 128 -> 20 while ticked | refills at density 3, 2, 1 |
| Accept mid-fill | `planting the last 824 rows now`, then the city HUD built, no new fault |

Not checked: screenshots (a Happy window covered the game for the whole run, sc3io refused every grab). One start
died in the intro at `GZGraphicD+0x18C7A`, before the panel existed, the same intro crash as above.
