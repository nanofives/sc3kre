# Placement hints: airport/seaport query rows, zone drag preview, plop land value halo (placehints, 2026-11-02)

Owner requests (2026-11-02, round `ROUND_2026-11-02b_owner_feedback.md`):

- A. "i have demand for airport but still 'Tráfico aéreo' is 'Escaso', same with ports, why?"
- B. "when placing airports and ports would you be able to display the extents of how much will it plop? i want to
  avoid placing things that won't have buildings, same with the limits of RCI"
- C. "for parks and other plopabble buildings show the impact it has in nearby zones"

Code: `re/harness/src/sc3resize_placehints.c` (block PLACEHINTS, #included by `sc3resize.c` after ZONEDEMO).
Off switches: `SC3RESIZE_PLACEHINTS=0` (all), `_ZONE=0`, `_PLOP=0`. `_LOG=1` logs every hint change.

## A. What "Tráfico aéreo" and "Tráfico portuario" read

Query rows of an airport building: SIMMISC `0x1000f49c` `[CONFIRMED, decomp + disassembly 0x1000f53f..0x1000f62c]`.

```
S     = valve 5000 slot +0x28           last month's SUPPLY of the commercial demand valve
N     = building layer (city +0x138) vt+0x60(0x3016)     0x3016 = 12310 Airport; N == 0 -> no rows
ratio = S / (N * 4000.0)                DAT_1003ec18 = 4000.0
row   = ratio < 0.8 -> 255 "Escaso" | < 1.1 -> 256 "Medio" | < 1.5 -> 257 "Denso" | else 258 "Congestionado"
        (DAT_1003ec08 / ec00 / ebf8; SC3StringsQuery.IXF group 0x82e0074c, label 254 "Tráfico aéreo:")
pct   = ftol((aura + 128) * (1/255) * (1/ratio) * 100), capped at 98     "Vuelos puntuales" (259 / 260)
        aura = aura layer (0x259c03f / 0x4259c018) vt+0x44(), the city aura, signed byte; 1/255 = DAT_1003e210
```

Seaport rows: SIMMISC `0x1000fc5d` `[CONFIRMED decomp]`, the same code with valve **8000** supply (industrial) and
count `vt+0x60(0x302a)` (12330 Seaport), strings 261..265, same 4000 / 0.8 / 1.1 / 1.5 constants.

Who supplies valve 5000 / 8000: commercial / industrial buildings, per cell (`SC3ValveLayer.ini [AgentValveEffects]`,
format `valve:supply:demand`): commercial 17..19 low, 61..64 medium, 128..130 high (plus 19002 / 19003 / 1002);
industrial 11..130. The same rows demand 5001 / 8001 by the same amount, so S is also about the commercial load on
the connection capacity.

So the row is "commercial development per airport building", with a yardstick of 3,200 (Medio) to 6,000
(Congestionado) per building. It does not read demand, the A / P bars, the queried building or its power:

- The A / P bars (RCIBARS) show the cap byte of 5000 / 8000 = `100 * demand(5001) / supply(5001)`
  (SIMRCI `0x1000ee50` / `0x10016061`). An airport cell adds 500 to supply(5001).
- Power: the valve stamp gate (SIMRCI `0x1002f5af`, QI `0xe0faadc7` vt+0x4c == 1) is the occupancy state "standing"
  (`LAND_VALUE.md` 3), not power, and `0x1000f49c` reads no power. Power only stops new cells from growing
  (UpdateCell `0x10004784` returns `0xe`).
- 98% is the cap of "Vuelos puntuales", reached whenever the traffic is light.

Derived from the rows (not run): with the A bar full, load >= 25,000 + connections + 500 per airport cell, while
"Medio" needs 3,200 load per airport building. So past a few buildings the airport reads "Escaso" exactly when the
capacity it adds is used, and more airport makes the row more "Escaso" while it raises the commercial ceiling. Berlin
(`PORTS_AIRPORTS.md` 1.4): 613,363 / (334 x 4,000) = 0.46 = Escaso, at a commercial cap of 57.

Unit of N (buildings or cells) is open (`PORTS_AIRPORTS.md` 7). It changes the ratio by the multi-cell share only.

## B. Airport / seaport zone drag preview (built)

The zone tools (all 13 types, SIMRCI vtable `0x1004c06c`) draw the drag through slot `+0x54` `0x1000b9d2(rect6 =
tool+0x40, out)`: highlighter vt+0x4c fills the rect with `tool+0x128`, or 0x24 (red) when the stock refused the
rect (`tool+0x38/+0x39/+0x3a`) `[CONFIRMED, disassembly, ret 8]`. The wrap runs the stock fill, then for zone types 14
and 15:

- only cells the zone tool takes count: no occupant, or flora (GeomFlag 0x400), or a power line (0x400000 + 0x800),
  the CanZone rule (`0x1003559f`, `ZONEDEMO.md` 1). Occupant manager city vt+0x11c vt+0x7c(x, z, &occ), IsGeomFlag
  occ vt+0x3c. This matches the stock cost: 15 cells, $7,500 in the Berlin test.
- each counted cell is tested with the zone layer's `vt+0x6c({x, z}, 6)` = SIMRCI `0x100330b7`, the
  transport-within-6 test of the airport / seaport UpdateCell (`0x10004784` / `0x1002ca1f`). It searches transport
  occupants in `[x-7, x+7] x [z-7, z+7]` (clamped) with the layer's filter `+0x2b4`, so it answers the same before
  and after zoning. A failing cell is set to 0x24 (red) through highlighter vt+0x2c and the rect is pushed (vt+0x58).
- the cost label gets four more lines: cells and red cells; capacity added if every non-red cell grows (airport 500
  per cell to 5001, seaport 250 to 8001) with capacity in use now and after (`demand * 100 / (supply + added)`, as
  `0x1000ee50` / `0x10016061`); the demand ceiling now and after (`max - max * cap / 100`, max = valve +0x24 = 2000);
  the runway rule for small airport drags (`0x1002b04c`: rect >= 3x3 with a side >= 5) or the pier rule for seaports
  (`0x1002d27f`, a reminder only); "needs power and water".

Not drawn, on purpose:

- **Power.** Whether an empty zoned cell conducts power is open: POWER_GRID.md leaves the writer of the conductive
  mask (`+0x5c`) unread. A per-cell power colour before zoning would be a guess.
- **Water.** The plumbing getter the UpdateCell calls (developer `+0x64` vt+0x48) was not read, so whether it
  answers for unzoned cells is unknown.
- **Pier water run.** The pier rule's terrain getters are named only by the iOS match (`PORTS_AIRPORTS.md` 2.4).

Plan for those three: read the power mask writer (SIMUTIL, writers of power layer `+0x5c`) and the plumbing getter,
then colour per cell in the same wrap. The pier run needs the terrain `vt+0x54` body (open water + unoccupied) and
the edge walk of `0x1002d27f`; it would mark edge cells with no 5-cell water run red.

### The cost label carries the hint

- SIMSPR view vtable `0x10067894` slot `+0x50` = `FUN_1004a3d7(show, cost, nofunds)` formats the cost into the string
  at view+0x134 only when cost differs from view+0x130 (formatter `FUN_1004ff6a()` vt+0x94(0) vt+0x3c(lo, hi, str)),
  then posts the tooltip record view+0x168 (+8 = that string) with message 0x22c010d0 `[CONFIRMED]`. The wrap formats
  the cost the same way, appends `"  |  " + hint` through the string's vt+0x10 (assign from char*), and sets +0x130 =
  cost so the stock body keeps the text.
- Only posts from the hinted tools keep the hint: return address inside SIMRCI `0x1003f5d4` (zone tools, 77 bytes) or
  SIMGEOM `0x1002146b` (building tools, 77 bytes), or the wrap's own re-post. Any other tool (road, query) drops it
  (first build kept the park text on the road tool, `C3_road_label_plain.png` was taken before that fix).
- The tools post the label before they draw the preview (`0x1003f91e`: vt+0x50 cost, `0x1003f5d4` label, then
  vt+0x54), so the preview wrap posts it again once the hint is known.
- The tooltip has no line breaks and two 256 px limits: `FUN_004431e1(str, 0x100, font)` cuts the text with "..."
  (push at SC3U `0x00443149`), and `FUN_00442e88` makes its raster 0x100 px wide (push at `0x00442f16`). The text limit
  is set to 768 only while a hint is shown and put back to 256 after. The raster is made 768 wide at install. The
  window still sizes to its text, so stock labels look unchanged (`C2_after_esc.png`, road label).

## C. Plop land value halo (built)

Building tools (SIMGEOM vtables `0x10029504`, `0x100295e4`, `0x1002968c`, `0x10029734`) draw the footprint through slot
`+0x54` `0x1000968b(pos3*, out rect6*)`, `tool+0x116` = width - 1, `tool+0x117` = depth - 1 (the rect end is
`start + w * 0x100`, cells inclusive), code 0x23 or 0x24 when refused `[CONFIRMED]`. Type id: SIMGEOM `DAT_1003092c` vt+0x24(key = tool+0x108, 0xe075ef51, &attrib), attrib vt+0x50
`[CONFIRMED @ 0x10006bb8..0x10006be4]`.

The wrap replays what the land value layer does with the building alone (`LAND_VALUE.md` 3-4):

1. row = exact type in the map `SIMRCI DAT_10058688` (node: +8 left, +0xc right, +0x10 key, +0x14 R C I A; find =
   `0x10029c40`), else the first row whose type is an ancestor (agent type tree = app `SIMRCI 0x1003ceec()` vt+0x40,
   vt+0x24(ancestor, type)), as `0x1001d840`;
2. the row is added once per footprint cell to its 4x4-cell block;
3. two in-place passes, x outer and z inner, of the 3x3 block average over in-bounds blocks, with the sums cast to
   short and C division, as `0x1001d3f1`;
4. every changed block of the strongest class is marked (0x23 where it goes up, 0x24 red where it goes down), footprint
   cells left to the stock preview, then pushed. The game's highlight also tints the sprites of buildings standing in
   marked cells (SIMSPR `0x10018081` -> `0x10019899`), so the buildings that gain land value show tinted too.
   Measured: Big Park (14312, row R 50 C 30 I 10, 3x3) inside one block = R +38%, as the replay in `LAND_VALUE.md` 6;
   across blocks R +31%. Reach 13 to 15 cells. The label shows the peak per class (percent of the cell's base land
   value for that class, `0x1001deca`) and the reach in cells from the footprint.

Between rebuilds the game keeps a new building's stamp unsmoothed in its own blocks (`LAND_VALUE.md` 4), so the halo is
the steady state, reached when the 16-step block cursor next wraps.

Not in the label yet: aura (`SC3Aura.ini`, flat over the rect grown by the radius, SIMMISC `0x1000314a`), crime
(SIMSERV `0x10007d35`) and pollution (SIMECO `0x100095e7`, linear falloff). Their tables are loaded into maps of the
same kind; reading them is the next step (same lookup shape, `LAND_VALUE.md` 8).

## D. Round 2 (placehints2, 2026-11-02): text on Shift, green halo

Owner after trying it: "the extra information when placing a zone should be visible when pressing shift, the zone
impact should be in a shade of green, light blue is the same as the zone it's being placed".

### Stock meaning of Shift during placement

| step | what the code does | evidence |
|---|---|---|
| Win32 to GZ mouse flags | MK_SHIFT (4) -> 0x1, MK_CONTROL (8) -> 0x2, MK_LBUTTON -> 0x10, MK_RBUTTON -> 0x20 | GZGraphicD `0x10017b90` `[CONFIRMED]` |
| view to tool | SIMSPR city view input slots (LDown `0x10049336`, Move `0x1004947d`, LUp `0x10049540`, ...) store the flags at view+0x20c and pass them unchanged to the active handler (the tool) | `[CONFIRMED]` |
| zone tool left up | `if ((flags & 1) == 0)` pick cell, preview +0x54, commit +0x48; then always resets the drag | SIMRCI `0x1003f7ca` `[CONFIRMED]` |
| building tool left up | same gate before its commit | SIMGEOM `0x1002165e` `[CONFIRMED]` |
| down / move | no read of the flags | SIMRCI `0x1003f737`, `0x1003f91e`, SIMGEOM `0x100215a9`, `0x10021764` |
| keys | city view KeyDown `0x10049265` reacts to Ctrl (0x11) and Alt (0x12) only, not to VK_SHIFT. Tool key slots only forward | SIMSPR, SIMRCI `0x1003f308` / `0x1003f31b` |

Shift held when the left button is released cancels the zone drag or the plop. Measured: a posted `WM_LBUTTONUP` with
wParam MK_SHIFT after a 30-cell airport drag in Berlin placed no zone and the money stayed at $123,479
(`verify/placehints2/owner_shots/B3_release_with_shift_cancels.png`). PLACEHINTS keeps that stock rule.

### Text on Shift

`ph_label` adds the hint only while `ph_shift()`. The state comes from the game window's own `WM_KEYDOWN` /
`WM_KEYUP` VK_SHIFT (`rz_wndproc` -> `ph_shiftmsg`, `WM_KILLFOCUS` = up), not from `GetKeyState`, so a posted key
message drives it in the lab. On a change the label is posted again (view vt+0x50) with the show / cost / no-funds
arguments of its last post, when that post showed it and a hint waits. `SC3RESIZE_PLACEHINTS_SHIFT=force|never`
overrides. Red and green cells are not text and stay on.

### Where the highlight colour comes from

The highlighter cell byte holds a state per nibble (1 = tool code hl+0x2c, 0xf = 0x24, 0 = none, getter
`0x1004adcd` = vt+0x30). Two readers turn the code into a colour:

- Terrain: sprite manager `0x1001a4c8` (Linux `cSC3CitySpriteManager::createTerrainSpriteCellCursor`) passes
  (hl+0x28 style, code) to DirtBag (city vt+0x13c) vt+0x70 = SIMDIRT `0x10005d20` -> cell cursor `0x10016b11` (+8 style,
  +9 = code | 0x80). Its colour, `0x1001576a`: `palette[style & 0x3f].rows[code & 0x7f][shade >> 1]`, palette table at
  `DAT_10025bac + 0xc`, 9 entries of 8 bytes {loaded byte, rows - 1 short at +2, row array at +4}, loaded from
  palBasic.bmp, data1Pal.bmp, data2Pal.bmp, data3Pal.bmp, (4 dynamic), palUnder.bmp, palWater.bmp, palEdgeL.bmp,
  palEdgeD.bmp (`0x10016cce`, rows made by `0x10012342`, freed by `0x100121a9` with msvcrt free). Pixel decode:
  cdecl `DAT_10025bb4(pixel, &c0, &c1, &c2)` (`add esp, 0x10` after the call at `0x100157b5`).
  Measured: style 0 has 53 rows of 32 shades. Row 0x23 mid shade decodes to 0 101 131.
- Sprites (buildings standing on highlighted cells): `0x10018081` (Linux `isRegionHighlighted`, sole caller the E8 at
  `0x10019903` in `0x10019899`) returns +0xdc (RGB 0 0x8a 0xb4) if any cell is highlighted, +0xde (RGB 0xdf 0x2c 0x2c)
  if one is 0x24. Both are made once at `0x10016eba` by FUN_1004feba() vt+0x88(&out, r, g, b). The tint goes to the
  sprite instance vt+0x28.

### Green

Nibble 2 = a new code, the index of a row appended to the style's palette (0x35 in style 0): the light blue row 0x23
recoloured with the same shading (brightness l = max channel -> RGB l/4, l, 3l/10, mid shade 32 129 32). The getter
slot returns that code for nibble 2. The `0x10019903` call returns RGB 0x2c 0xb4 0x36 when every highlighted cell under
a sprite is green. A rising halo cell is set through the stock setter with the tool code (dirty rect, push
bookkeeping) and its low nibble is then changed to 2. The stock clear (`0x1004b653`, low nibble -> 0) and push
(`0x1004b779`, nibble compare) handle any value. Falls stay 0x24 red. `SC3RESIZE_PLACEHINTS_GREEN=0` = the old colour.

## E. Round 4 (placehints4, 2026-11-03): halo on Shift, transit research

**Halo only while Shift is held (built).** Owner: "without shift it should hide the area affecting a ploppable
building". `ph_bprev` still computes the halo (the label needs the reach) but marks cells only when Shift is down.
A Shift edge re-runs the building tool's preview: tool vt+0x54(tool+0x40, out rect6), the same call the move handler
SIMGEOM `0x10021764` makes. The stock fill under it, highlighter vt+0x4c = SIMSPR `0x1004af93`, clears every live
cell (`0x1004b653`), fills the footprint and pushes rect plus dirty rect (vt+0x58), so the old halo is pushed away
`[CONFIRMED @ SIMSPR 0x1004af93]`. The call is made only when the hint tool is a building tool (one of the 4 SIMGEOM
vtables) and the city view's current tool (view+0x228, measured by the picker), so a switched-away or freed tool is
never called. The sprite tint follows the cells, so it goes too. The airport / seaport red no-transport cells stay
always on: they say where the dragged zone cannot grow, like the stock red refusal.

**Transit catchment (built, station preview).** The trip start node (type 0x80) in SimTransit `0x1000755e` scans the lot
rect grown by r cells, corners skipped, r = layer+0xc5 (Res, 4), +0xc6 (Com, 3), +0xc7 (Ind, 5), +0xc8 (other, 5) by
the lot kind from `0x100057f6` (STTraffic `TripMaxDistanceToRoad`, +1 with the shuttle ordinance, `0x100087fd`). A
cell whose layer+0x5c flags hold 0x10 is a station candidate: with the bus mode and flag 1 a bus stop (node 0x50),
flag 0x20 rail-subway (0x30), flag 4 with the rail mode rail (0x14), else subway (0x18). A station candidate below
`DAT_1001f0c0` sets the keep value to 0xff, so any station in range beats every road cell `[CONFIRMED @ SimTransit
0x1000755e]`. Whether the trip has the mode at all is the building's flags and the 60% roll (`0x100097b9`,
PUBLIC_TRANSIT.md 2). Per-cell trip counts and their transit share: TRIPCELLS (`sc3resize_vdbars.c`).

**Station preview (built, `ph_station`).** Station plop types measured from the plop tool type log after the menu
commands (MenuItem.INI names): Bus Stop `0x10004004` -> 12210, Train Station `0x10004102` -> 12230 (both building tool
vtable SIMGEOM `0x10029504`), Subway Station `0x10004202` -> 12360, Rail To Subway `0x10004009` -> 12361 (vtable
`0x1002968c`). With Shift: the cells within the Res reach (layer+0xc5) of the footprint, corners skipped, drawn in the
tool colour, green where TRIPCELLS has trips from that cell that used bus, rail or subway, and the label sums the trips
starting in the area. Always: footprint red when `ph_station_links` = 0. The onward step from a station node (same
function, generic ring branch: rect + 1, corners skipped) goes to a cell that lacks 0x10 and has: bus stop 0x50 ->
road 1 (node 0x41), rail station 0x14 -> rail 4, subway station 0x18 -> tunnel 8, rail-subway 0x30 -> 4 or 8
`[CONFIRMED @ SimTransit 0x1000755e]`. Measured in Berlin: a 2x2 train station touching a new rail line gives links 2,
one cell off gives 0 (railgap measured 0 trips for the same gap).

Live reach bytes in Berlin: layer+0xc5..+0xc8 = 5 / 4 / 6 / 7, while STTraffic lists 4 / 3 / 5 / 5. The shuttle
ordinance (+1 each, `0x100087fd`) would account for 5 / 4 / 6 / 6. `[UNCERTAIN]` whether Berlin has that ordinance on,
and where the 7 for "other" comes from; the hint reads the live bytes either way.

TRIPCELLS limit: it closes a month only from GRAPHNEW's budget hook (`sc3resize_graphs.c` `gn_month`), which does
nothing until the Graficas page has been opened once (`g_gn_if[0]` is made by `gn_make` from the page enumeration).
Before that the hint has only the count since the load, and the label says so.
