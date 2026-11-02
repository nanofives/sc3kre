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
