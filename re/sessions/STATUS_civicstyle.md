# STATUS civicstyle (round 2026-11-21, civic buildings per style)

## goal
The style sets' European and Asian art for stock civic buildings and parks offered as looks in the civic list window
(civdlg), with no import: Police lists North American / European / Asian, and so on for every button with set art.
Stock exactly when the row is off; placed looks survive save and reload and come back as stock without the mods.

## verdict + deciding RVAs
DONE, checked in game (verify/civicstyle/RESULTS.md, pictures in verify/civicstyle/owner_shots/).
- Set art (offline): European e523f3fb 6 bases (Police, Fire, School, Museum, Baseball, Marina), Asian 6523f3d5 15
  (those + Jail, Hospital, College, Library, Small Park, Big Park, Playground, Pond, Fountain). Zoo, Bus Stop, Train
  Station, Subway: none. Every set exemplar keeps the base's type id and footprint.
- Hooks: plain civic call SIMGEOM 0x1000b1a3 (CIVVAR), Marina call 0x1000afc0 -> 0x1000a246 (new), factory slot
  SIMGEOM+0x2920c (CIVDLG). Rows renamed with cIGZWinListBox::ModifyString (vt+0x20, CodeView). City skin from the
  scheme manager [[0x4fa86c]+0x108] +0x50/+0x58.

## built
- netpack style_mix 1.2.0 (`"civic": true`): civic set exemplars at +400000 / +1500000 with tables and pixels,
  stock exemplars of re-skinned civic bases at +2600000, no family line. 1.1.0 manifest compiles identically.
- sc3resize CIVSTYLE: per-press look list (original in the city's style, other styles found in the attrib cache,
  bldimport looks), rows "<region>: <name>", style descriptions, Marina hook, mods page row
  "Civicos: estilos del juego" (env SC3RESIZE_CIVSTYLE, ini [buildings] civicstyles=), left column rows 15 px.
- 10 lang keys, sc3lang check clean (373 keys in 7 tables).
- civmod_lab.py: hotkey/command jobs stay attached 4 s after the modal returns (lab fault, RESULTS "Fault seen").

## proven game-side vs static only
Game-side: windows for Police, School, Hospital, Small Park (also via the real Parks button), Marina; European and
Asian police and school, Asian hospital and small park placed, saved, reloaded with mods, loaded in the stock game as
stock buildings; Berlin (European set) lists Europa original + North American copy, NA police placed there; row off
= no hook, stock tool; mods page row writes sc3mods.ini; bldimport looks listed after the styles; cycle mode.
Static only: the other 10 buttons' windows (same path), Marina placement on a shore, an Asian city.

## blocked on
Nothing.

## files owned (dev/civicstyle/wt)
re/harness/src/sc3resize_civic.c, re/harness/src/sc3resize.c, re/harness/lang/{de,en,es,fr,it,nl,sv}.txt,
re/tools/netmod/netpack_stylesets.py, re/tools/netmod/netpack.py, re/tools/netmod/netpack.schema.json,
re/tools/netmod/stylemix_build.py, re/tools/netmod/examples/style_mix/manifest.json,
re/tools/netmod/examples/style_mix/README.md, re/tools/civmod_lab.py, re/analysis/CIVIC_REWARD.md.
MAIN: re/sessions/STATUS_civicstyle.md, verify/civicstyle/RESULTS.md.
Not to commit: verify/civicstyle/owner_shots/*.png (game art).

## game-harness need
None now (no game running).

## asks of other sessions
- Release: install style_mix 1.2.0 in stage/src (`netpack.py uninstall style_mix`, then `install
  re/tools/netmod/examples/style_mix`) and ship sc3resize + lang tables with it.
- Owner check: a Marina look placed on a shore (needs the Parks sub-flyout and a coastline).
