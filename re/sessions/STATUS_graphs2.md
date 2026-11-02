# STATUS graphs2 (child of "SC3 graphs tabs + Vida util/restore/query UI round", 2026-11-02)

## goal
Ver datos: Graficas line-graph tabs drawn as real tabs (one aligned row, selected tab distinct); Cuadros radios become
tabs in the same tab system; Educacion (schools / universities capacity vs students, libraries + museums), Salud
(patients vs hospital capacity), Agua (sources + processing), Transporte (trip share by mode). Native widgets, off
switches, every value from the sim with its RVA.

## verdict + deciding RVA
DONE, checked in game (Berlin). Results + pictures: verify/graphs2/RESULTS.md, verify/graphs2/owner_shots/ (7 PNGs).
- No tab class exists in GZWIND [CONFIRMED @ GZWIND 0x1000121d]. Tab = shape polygons style 0x31 (filled; 0x11 only
  strokes, SIMUI 0x10046590) + caption-only text button (factory +0x2c, iface vt+0x58(NULL), style 0x10)
  [CONFIRMED @ GZWIND 0x10008935, 0x10008adf, 0x10008fdb].
- Cuadros page hooked by vtable slot (director 0x100a4080 build +0xc 0x1001f3df / close +0x10 0x10020ffd, control
  0x100a4014 -> 0x1001f30d ret 0x14, refresh 0x100a3ff4 -> 0x1001f3b3), so sc3dataview's prologue hook on the fill
  0x100245c7 keeps working.
- Educacion / Salud bars: under the stock charts (they replace sc3dataview's text column while shown). Agua and
  Transporte: new tabs 6 and 7. Values + RVAs: re/analysis/GRAPH_SERIES.md section 9.
- Libraries / museums: places + building count only; NO user count in the sim (seats go into per-age EQ arrays mixed
  with schools). Shown: places vs residents of the age band served (what the sim compares seats with).
- Not stored by the game (said, not proxied): unmet water demand, tower storage, sewage volume, trips per mode.
- Trips per mode: counted by the mod (TRIPMODES, pop call SimTransit 0x100072f8, sc3cartrips' recipe), per month.
- One owner-visible wording change: the stock "Electricidad" chart's tab reads "Energia" (the Graficas word) so 7 tabs
  fit one row.

## built
dev\graphs2\inst\sc3resize.dll (sc3dev build graphs2 -Mods sc3resize), clean build, no warnings.

## proven game-side vs static only
Game-side (7 lab runs, Berlin): all tab clicks on both pages, close + reopen Ver datos, tab kept across starts, the
off switch, every bar value logged and pictured; water per-source outputs sum to the layer supply exactly; trip
counts per month (1,276..1,612 trips). Static only: English text, a city with libraries, a city with buses.

## blocked on
Nothing. Layout matches the owner's words and decision (orchestrator 2026-11-02): Graficas and Cuadros stay separate
pages, each with its own tabs directly under its chart; capacity bars inside Educacion and Salud; Agua and Transporte
new Cuadros tabs.

## files owned (commit by path; the two NEW files are under the deny-by-default .gitignore: `git add -f`)
- re/harness/src/sc3resize_vdtabs.c   (NEW, git add -f)
- re/harness/src/sc3resize_vdbars.c   (NEW, git add -f)
- re/harness/src/sc3resize.c          (2 include lines + vb_install call)
- re/harness/src/sc3resize_graphs.c   (drawn tabs on Graficas: layout, click, close; monthly trip snapshot)
- re/analysis/GRAPH_SERIES.md         (section 9)
- verify/graphs2/RESULTS.md, verify/graphs2/owner_shots/*.png (MAIN, not in the worktree)

## game-harness need
None left. Off switches: SC3RESIZE_VDTABS=0, SC3RESIZE_VDBARS=0, SC3RESIZE_TRIPMODES=0, SC3RESIZE_VDBARS_LOCK=0;
log SC3RESIZE_VDTABS_LOG=1.

## asks of other sessions
- restoreui also edits sc3resize.c: my sc3resize.c change is 3 lines next to the GRAPHNEW include and gn_install call.
- sc3cartrips (dev tool) and TRIPMODES patch the same SimTransit call: whichever loads second refuses and logs it.
