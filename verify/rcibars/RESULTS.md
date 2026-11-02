# rcibars: Aeropuerto / Puerto bars on the RCI (child rcibars, 2026-11-02)

Owner request: "can we modify the RCI to include Agricultural, Ports and Airports?" Owner pick: Aeropuerto + Puerto now,
agriculture after research.

## Verdict

- **Built**: the RCI meter has two more columns after R C I: **A** (Aeropuerto, purple) = commercial connection capacity
  in use, **P** (Puerto, orange) = industrial connection capacity in use. A 1 px dark red tick on both marks 75%, where the
  City Planner starts warning. Hovering the "A P" letters shows "Capacidad en uso: Aeropuerto 56%, Puerto 17%"
  ("Capacity in use: Airport .., Seaport .." on an English install).
- **Agriculture: no bar.** The sim keeps no farm demand and no farm valve. Farms take the ordinary industrial valves. The
  only farm-specific number is a farm building count, used by the advisors (details below). This needs an owner call.

## What the bars show (and why it is not demand)

Airports and seaports have no demand of their own. Each developed airport cell adds 500 to valve 5001 (commercial
connection capacity), each seaport cell 250 to valve 8001 (industrial), and every C / I building uses some of it. At month
end SIMRCI `0x1000ee50` / `0x10016061` turn the usage into the cap byte (+0x3c) of the demand valves 5000 / 8000:
0 if demand is 0, 100 if supply < demand, else demand x 100 / supply. The demand bar's ceiling is then max x (1 - cap/100).
The A / P bars show that byte, read through valve vt+0x70: the same byte the advisor compares with 75
(`re/analysis/PORTS_AIRPORTS.md` 1.2, 5.1). Bar height = cap% x 16 px, the RCI's own full-bar height (`this+0xe8` = 16.0).

Berlin, read live in the test (log line `RCIBARS> capacity in use`): commercial 56% (5001 supply 1,078,500, demand
614,402), industrial 17% (8001 supply 1,030,800, demand 180,069). portsre measured 57% / 16-17% on the same city
(`verify/portsre/berlin_valves.txt`).

## How it is built (SC3RESIZE_RCIBARS=0 = stock RCI)

`re/harness/src/sc3resize_rcibars.c`, #included by sc3resize.c. RCI = SIMUI class vtable `0x100ab274` [CONFIRMED, PE + bodies]:
- Init `+0x24` (`0x10064b08`) wrapped: after the stock Init, a 59x88 raster replaces the 41x88 background `+0xa8` (game's
  raster recipe from SIMUI `0x1006d56c`). Stock art copied in, two more column strips copied from the C column (panel rows
  only: rows 0..29 are the globe tab of the "Visitar Bolsa de SimCity" button), the right-edge shading moved to the new
  edge, "A" / "P" drawn with the stock font 0xf and colour (0x1f,0x29,0x88). The stock colour key lives in the surface
  object's Blt flags `+0xdc` / DDBLTFX `+0x78` (GZGraphicD `0x10018c58` passes the source's), so they are copied too.
  Then one SetRect: the RCI's own SetRect (`0x100651ba`) sizes to the raster and the base recreates the surface (`vt+0x170`).
- Draw `+0x144` (`0x10065214`) wrapped: two more fills through the stock fill path, inside NATIVETEXT's RCI window, so the
  enlarged HUD draws them sharp like R C I.
- Tooltip: an image button over the letter rows 51..62 of A P, its image a copy of those pixels (4 frames), so it is
  invisible. The stock 0x52fb06f0 image is the globe tab (first build drew a second globe).
- sc3resize BARKIDS: the RCI's right edge is clamped to the minimap's left edge. Without it, at 800x600 (console cannot
  slide left) the minimap covered P. At 800x600 the RCI now starts at x 581 over the plain right end of the console art.
- `SC3RESIZE_RCIBARS_LOG=1` logs every value change.

## Pictures (`owner_shots/`)

1. `1_rci_antes_ahora_800x600.png`: stock (off) vs new, Berlin, 800x600, x3.
2. `2_tooltip_capacidad.png`: posted hover on the A P letters.
3. `3_hud_escalado_1920.png`: 1920x1040, HUD Auto x1.733. HUDSCALE maps the RCI as one window,
   [1701 960 1760 1040] -> [1540 901 1643 1040].
4. `4_rci_zoom_x8.png`: the new RCI pixel by pixel.

## Tested / not tested

- Tested in one Berlin session (tree dev\rcibars): bars, letters, ticks, tooltip, 800x600, 1600x900 and 1920x1040 layouts,
  HUD scale, off switch (stock RCI, no RCIBARS log lines).
- Not tested: a month end with the sim running (the Draw reads the cap byte on every draw, and the stock month-end
  messages for 5000 / 8000 repaint the RCI), loading a second city in the same session (Init runs again, the old tooltip
  button reference is released then), the English tooltip text.
- Clicks on the A P letters land on the tooltip button and do nothing. The globe button is unchanged.

## Agriculture research (owner call needed)

Report from a delegated read, two citations spot-checked here:
- Farms are agent type 9300 IndAgricultural under 8000 Industrial [DATA CitySim.ini:49, 323]. Their valve row
  `9300=8000:11:0+7000:0:10+8001:0:11` uses the same 8000 / 7000 / 8001 valves as other industry
  [DATA SC3ValveLayer.ini:31, checked]. No code reads a farm-only valve id.
- The industrial developer picks farms by chance, not by demand: `PctChanceAg=90` when the cell's air and water pollution
  are at or below `MinAgAirPollution` / `MinAgWaterPollution` (450), Lawn Chemicals Ban / Farmer's Market ordinances
  move the chance, and farms over `MaxAg*` (451) are removed [CONFIRMED @ SIMRCI 0x10016290, 0x100188d3, 0x10017fc0;
  DATA SC3Tune.ini:38-42]. Farms appear only on low-density industrial zones [DATA SC3ZoneLayer.ini:13].
- The one farm quantity: **farm building count** = BuildingLayer vt+0x60(0x2454), stored in the City Planner at +0x21c
  [CONFIRMED @ SIMADV 0x100094e7, checked]. Used by advice 222 "Farm Zones Suggested" and two reward/petition checks.
  Unit (buildings vs tiles) [UNCERTAIN].

Options for the owner: (a) no Agricola bar, (b) an "Agricola" column showing the farm building count (not a demand, no
natural 100%, would need a chosen scale), (c) show farms elsewhere (a Ver datos layer or a graph line).
