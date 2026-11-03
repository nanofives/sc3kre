# STATUS placehints (round 2026-11-02b)

## goal
A. Why "Tráfico aéreo: Escaso" (and "Tráfico portuario") with airport/port demand (owner shot image-1793660447362.png).
B. Airport/seaport zone placement preview (what can develop + capacity vs use).
C. Park/plop placement preview of its land value halo.

## verdict + deciding RVAs
A (SIMMISC `0x1000f49c`, seaport `0x1000fc5d`): ratio = valve 5000 supply / (4000 x airport buildings), < 0.8 Escaso,
< 1.1 Medio, < 1.5 Denso, else Congestionado. "Vuelos puntuales" = min(98, (city aura + 128) / 255 x 100 / ratio).
Not demand, not the A/P bars (cap of 5000/8000), not power. Detail: `re/analysis/PLACEHINTS.md` A.

B + C built as sc3resize block PLACEHINTS (`sc3resize_placehints.c`), reusing the game's own preview:
- highlight grid SIMSPR vtable `0x10067a5c` (vt+0x2c set cell, vt+0x58 push; nibble 0xf = code 0x24 red);
- zone tool preview SIMRCI `0x1000b9d2` (vtable `0x1004c06c` +0x54), building tool preview SIMGEOM `0x1000968b`
  (4 vtables +0x54);
- cost label SIMSPR `0x1004a3d7` (view vtable `0x10067894` +0x50), text in the view+0x134 string;
- tooltip 256 px limits SC3U `0x00443149` (text) and `0x00442f16` (raster).
B: red = no transport within 6 (SIMRCI `0x100330b7`), label = cells the tool takes, red count, C/I capacity added and
use now -> after, demand ceiling now -> after, runway / pier reminder, "needs power and water".
C: replay of land value stamp + 2 smoothing passes (SIMRCI `0x1001d840`, `0x1001d3f1`), halo where the strongest
class rises/falls by >= 1/4 of its peak, label = R C I peaks + reach.

## built
`dev\placehints\inst\sc3resize.dll` (sc3resize only in this inst), clean build.

## proven game-side vs static only
- game-side (posted input, frame dumps, `verify/placehints/RESULTS.md`): airport drag numbers = stock cost, red cells
  past the rail's 6-cell reach, seaport label, Big/Small Park halo and peaks (match LAND_VALUE.md replays), Esc clears,
  road tool label plain.
- static only: A; power/water/pier not drawn (plan in PLACEHINTS.md B); aura/crime/pollution not in the plop label.
- not run: `SC3RESIZE_PLACEHINTS=0`, real mouse, the full mod set together.

## blocked on
-

## files owned
- re/harness/src/sc3resize_placehints.c  (NEW, matched by `.gitignore` `/re/*`: needs `git add -f`)
- re/harness/src/sc3resize.c  (#include after zd_thread + ph_thread start after the ZONEDEMO thread, 5 lines)
- re/tools/roadover_drive.py  (tool names airport / seaport / smallpark / bigpark)
- re/analysis/PLACEHINTS.md  (NEW)
- verify/placehints/RESULTS.md  (NEW)
- re/sessions/STATUS_placehints.md (this file, MAIN)
- pictures in MAIN\verify\placehints\owner_shots\ (not for git)

## game-harness need
-

## asks of other sessions
- modlang: new inline es/en strings in `sc3resize_placehints.c` (`ph_zprev`, `ph_bprev`).
- the label shares SC3U's cost tooltip; any mod that changes that tooltip should know about the two width patches.

# STATUS placehints2 (2026-11-02, follow-up round)

## goal
Owner after trying placehints: hint text only while Shift is held, impact halo in green (light blue = the zone colour).

## verdict + deciding RVAs
- Shift text: `ph_label` adds the hint only while Shift is down. The state is read from the game window's WM_KEYDOWN /
  WM_KEYUP VK_SHIFT in `rz_wndproc`, and a change re-posts the label (view vt+0x50) with its last arguments.
- Stock Shift meaning: at left-button-up only. MK_SHIFT -> GZ flag 1 (GZGraphicD `0x10017b90`). The zone tool
  `0x1003f7ca` (SIMRCI) and the building tool `0x1002165e` (SIMGEOM) commit only when flag 1 is clear, so Shift held at
  release cancels. Measured: airport drag, no zone, no cost. Kept as stock. Owner call open (RESULTS 1).
- Green: terrain colour = SIMDIRT palette row per code (`0x1001576a`, palettes `0x10016cce`), sprite tint = SIMSPR
  `0x10018081` +0xdc / +0xde. New highlighter nibble 2 -> code 0x35, a green row appended to palette style 0. Getter
  slot SIMSPR vtable `0x10067a5c` +0x30 is hooked, and so is the call at `0x10019903`. Detail `re/analysis/PLACEHINTS.md` D.

## built
`dev\placehints2\inst\sc3resize.dll`, clean build.

## proven game-side vs static only
- game-side (Berlin, posted input, `verify/placehints2/RESULTS.md`): no text without Shift. Text with a posted Shift
  down and gone on Shift up, both without a mouse move, park and airport. Green halo on terrain and buildings, blue
  footprint, red falls unchanged, Esc clears. Shift plus release cancels (stock).
- not run: the physical Shift key (owner check), `_SHIFT=force|never`, `_GREEN=0`, the full mod set.

## blocked on
-

## files owned
- re/harness/src/sc3resize_placehints.c  (force-add, `/re/*` ignore rule)
- re/harness/src/sc3resize.c  (1 line in rz_wndproc: ph_shiftmsg)
- re/harness/lang/{es,en,fr,de,it,nl,sv}.txt  (placehints.in_green)
- re/analysis/PLACEHINTS.md  (section D)
- verify/placehints2/RESULTS.md  (MAIN)
- re/sessions/STATUS_placehints.md  (this section, MAIN)
- pictures in MAIN\verify\placehints2\owner_shots\ (not for git)

## game-harness need
-

## asks of other sessions
- any mod that reads highlighter codes through vt+0x30 can now see 0x35 (only under a plop halo). sc3undo's tint
  clear is unaffected.

# STATUS placehints3 (2026-11-02, Shift + release places)

## goal
Owner: Shift + release places the zone. Only hint tools, only the button-up, off switch `SC3RESIZE_PLACEHINTS_SHIFTPLACE=0`.

## verdict + deciding RVAs
Wrapped the left-up slots: SIMRCI `0x1004c06c`+0x28 (`0x1003f7ca`) and SIMGEOM 4 vtables +0x28 (`0x1002165e`). The wrapper
clears flag bit 0 (MK_SHIFT) when the tool is the current hint tool. Flag meaning: GZGraphicD `0x10017b90`.

## built
`dev\placehints3\inst\sc3resize.dll`, clean build.

## proven game-side vs static only
- game-side (`verify/placehints3/RESULTS.md`): airport 30 cells placed, charged $15,000. Big Park placed, charged
  $1,045. Road drag with Shift + release still cancels (stock).
- not run: `_SHIFTPLACE=0`, the physical key, the full mod set.

## blocked on
-

## files owned
- re/harness/src/sc3resize_placehints.c  (force-add)
- verify/placehints3/RESULTS.md  (MAIN)
- re/sessions/STATUS_placehints.md  (this section, MAIN)
- pictures in MAIN\verify\placehints3\owner_shots\ (not for git)

## game-harness need
-

## asks of other sessions
-

# STATUS placehints4 (2026-11-03, owner feedback on sc3mods-2026-11-03)

## goal
1. Plop land value halo only while Shift is held. 2. Public transport in the Shift view: (a) station catchment + trip
counts, with the in-box transit split (orchestrator go).

## verdict + deciding RVAs
1. Built. Halo marked only with Shift down. A Shift edge re-runs the building tool preview (tool vt+0x54 with tool+0x40,
   as SIMGEOM `0x10021764`); the stock fill SIMSPR `0x1004af93` clears (`0x1004b653`) and re-pushes the grid. Guard: hint
   tool is a SIMGEOM building tool and the view's current tool (view+0x228). Airport/seaport red cells stay always on.
2. Built (`ph_station`). Catchment = trip start scan SimTransit `0x1000755e` (lot rect + r, corners skipped, r =
   layer+0xc5..0xc8 live, Berlin 5/4/6/7). Onward step from a station = rect + 1, corners skipped, a cell lacking 0x10
   with road 1 / rail 4 / tunnel 8 (`ph_station_links`, shared with stationwarn). Station types 12210 / 12230 / 12360 /
   12361 (measured). Trips from TRIPCELLS.

## built
`dev\placehints4\inst\sc3resize.dll`, clean build.

## proven game-side vs static only
- game-side (`verify/placehints4/RESULTS.md`): halo only on Shift (A1-A4). Train station touching a laid rail line links 2,
  one cell off 0 and red (B1-B3), city spot with green transit cells and trip counts (B4), bus stop beside a road (C1).
- not run: physical Shift, `_SHIFT=force|never`, `_STATION=0`, subway / rail-to-subway shots, airport drag re-shot.

## blocked on
-

## files owned
- re/harness/src/sc3resize_placehints.c  (force-add, `/re/*` ignore rule)
- re/harness/lang/{es,en,fr,de,it,nl,sv}.txt  (13 placehints.st_* / placehints.station keys)
- re/analysis/PLACEHINTS.md  (section E)
- verify/placehints4/RESULTS.md  (MAIN)
- re/sessions/STATUS_placehints.md  (this section, MAIN)
- pictures in MAIN\verify\placehints4\owner_shots\ (not for git)

## game-harness need
-

## asks of other sessions
- stationwarn: share `ph_station_links` (signature sent 2026-11-03).
- GRAPHNEW / TRIPCELLS owner: TRIPCELLS months close only after the Graficas page was opened once (`gn_month` gated on
  `g_gn_if[0]`), so the transit map and this hint have no monthly history before that. Not changed here.

# STATUS tripmonth (2026-11-03, orchestrator round after placehints4)

## goal
1. TRIPCELLS month close from the city load, graphs unchanged. 2. Station preview: (a) "somewhere to go" flood, (b)
exact per-class reach. 3. Owner: Shift label in 2 or 3 lines.

## verdict + deciding RVAs
1. `gn_month` (SIMMISC `0x10007d88` detour) closed trip months only with the graph series made (Graficas opened once).
   New else branch: key = `gn_key(budget+0x14)`, `tm_month(key)`. Built, measured.
2. (a) `ph_station_dest`: flood over rail 4 / tunnel 8, edge 0x1000 / 0x2000 (SimTransit `0x10008a94`), other station
   entry with reach, or a ring bus stop (stationwarn's rule). (b) per lot: class `0x100057f6`, rect occ vt+0xcc, lot rect
   + r_k corners cut holds a footprint cell (start scan `0x1000755e`). Built, measured.
3. TIPLINES: SC3U `0x00442f06` raster height 3 lines, `0x00443331` render wrapped (font vtable copy, vt+0x58 / vt+0x88
   line by line), split at "|" groups. Built, measured es + de.

## built
`dev\tripmonth\inst\sc3resize.dll`, clean build.

## proven game-side vs static only
- game-side (`verify/tripmonth/RESULTS.md`): months 24805..24823 closed with Graficas never opened; connected line links 2
  dest 1, stub links 2 dest 0 red; per-lot area; labels 3 lines (station, airport, es), 2 lines (park es, station de).
- static only: graphs after opening the page (path untouched), subway kinds in game, `_LINES=0`, scaled HUD.

## blocked on
-

## files owned
- re/harness/src/sc3resize_graphs.c  (gn_month else branch)
- re/harness/src/sc3resize_placehints.c  (force-add: station dest + per-lot reach + TIPLINES + octal fix)
- re/harness/lang/{es,en,fr,de,it,nl,sv}.txt  (3 keys placehints.st_nodest_*, es "vía" fix)
- re/analysis/PLACEHINTS.md  (section F)
- verify/tripmonth/RESULTS.md, verify/tripmonth/lang_resolved_on_main_41150db/  (MAIN)
- re/sessions/STATUS_placehints.md  (this section, MAIN)
- pictures in MAIN\verify\tripmonth\owner_shots\ (not for git)

## conflicts against main 41150db
- lang fr/de/it/nl/sv.txt: both sides appended a block at the end (3 placehints keys / 12 stationwarn keys). Keep both;
  resolved copies in verify/tripmonth/lang_resolved_on_main_41150db (check: 306 keys). Everything else merges clean.

## game-harness need
-

## asks of other sessions
- stationwarn: `ph_station_dest` is the placement copy of sw_flood (no shared code); keep the two rules in step.
- main has "v355a" in es.txt (3 placehints keys) until this merges.

# STATUS ghosttiles (2026-11-03, owner bug on sc3mods-2026-11-03b: ghost coloured tiles while placing)

## goal
Find and fix highlight cells left on the map while placing a ploppable.

## verdict + deciding RVA
Highlighter push vt+0x58 SIMSPR `0x1004b779` sets the dirty rect +0x50 to the rect it is given (LAB_1004b931). The
tools' clear `0x1004b653` (in the fill `0x1004af93` and the cancel `0x1004ae23`) wipes only +0x50. STATIONWARN's blink
pushed the station rect every 700 ms, so the tool's old cells were stranded (every tool, any city with a flagged
station). PLACEHINTS' halo push could leave the footprint out. Fix: block GHOSTFIX `hl_push` (stationwarn restores +0x50
after its push, placehints pushes the union with +0x50). `SC3RESIZE_GHOSTFIX=0` = before.

## built
`dev\ghosttiles\inst\sc3resize.dll`, clean build.

## proven game-side vs static only
- game-side (`verify/ghosttiles/RESULTS.md`): 5 ghosts before, 0 after, 5 again with `_GHOSTFIX=0`. Shift held moves,
  Shift up, Esc, tool change clean. Stationwarn marker still blinks.
- not run: real mouse / physical Shift, station plop and airport drag shots, dialog open while placing.

## blocked on
-

## files owned
- re/harness/src/sc3resize_stationwarn.c  (hl_push + sw_paint call, force-add rule `/re/*`)
- re/harness/src/sc3resize_placehints.c   (ph_push calls hl_push, force-add)
- verify/ghosttiles/RESULTS.md  (MAIN)
- re/sessions/STATUS_placehints.md  (this section, MAIN)
- pictures in MAIN\verify\ghosttiles\owner_shots\ (not for git)

## game-harness need
-

## asks of other sessions
- any mod that pushes the cell highlighter (vt+0x58) should use `hl_push` (keep = 1 for a marker outside the tools'
  rect, 0 for a preview), or it strands the tools' cells.
