# civicstyle: civic buildings and parks in every style, picked in the civic list window (2026-11-21)

Asked on Simtropolis: "you could mix and match what schools/parks/hospitals/etc. appear in a city". Verdict: **done and
checked in game.** A civic button with set art opens the civic list window with one row per style (the original
first, in the city's own style, then the other styles), picking a row arms the stock tool with that look, placed looks
save and reload, and the stock game loads them as the game's own building of the same kind. No import needed: the
looks come from the game's own European and Asian building sets, through style_mix 1.2.0. Own switch and mods page
row "Cívicos: estilos del juego" (`SC3RESIZE_CIVSTYLE`); off = no hook (stock buttons).

## Which civic buildings have set art (offline, `re/analysis/CIVIC_REWARD.md` 7.1)

Read of the two set archives against the 18 civic bases (17 plain commands + Marina):

| Buttons | Looks offered |
|---|---|
| Police, Fire, School, Museum, Baseball, Marina | North American, European, Asian |
| Jail, Hospital, College, Library, Small Park, Big Park, Playground, Pond, Fountain | North American, Asian |
| Zoo, Bus Stop, Train Station, Subway, Rail to Subway | none (stock button) |

All 21 set exemplars have the base's type id (prop 0x65) and footprint (0x66 x and z); they differ only in height,
frame table, name key and 0x6f.

## What was built

| Piece | What it does |
|---|---|
| style_mix 1.2.0 (`netpack_stylesets.py`, manifest key `"civic": true`) | copies the set exemplars of the civic bases verbatim at base + 400000 (European, 6) / + 1500000 (Asian, 15) with frame tables and pixels, and the stock exemplar of the 15 re-skinned bases at + 2600000 (North American look in a European or Asian city). No family line: nothing grows them. Type and footprint checked at install. A manifest without `"civic"` compiles byte-identically to before (1.1.0 checked: 121 / 130 / 141 copies, 145 / 154 / 166 lines, same hash). |
| sc3resize CIVSTYLE (`sc3resize_civic.c`) | per press `cv_looks()`: original, the other styles whose copy is in the attrib cache, then the bldimport looks. Used by the list window, the cycle (CIVDLG off) and the cost label. Rows renamed "<region>: <name>" (cIGZWinListBox::ModifyString vt+0x20). Marina hook on SIMGEOM 0x1000afc0 (shore tool). Description per style row. |
| Switch | `SC3RESIZE_CIVSTYLE=0` / `sc3resize.ini [buildings] civicstyles=0`, mods page row "Cívicos: estilos del juego" / "Civic buildings: game styles" (left column rows 17 -> 15 px to fit). CIVSTYLE off and no bldimport look = no hook installed. |
| Strings | 10 keys (`resize.cs_*`, `resize.mt_civstyle`), all 7 tables, `sc3lang.py check` clean (373 keys). fr / de / it / nl / sv are mine, for review. |
| Lab | `re/tools/civmod_lab.py`: hotkey / command jobs wait up to 600 s and stay attached 4 s after (fault below). |

## Evidence (dev/civicstyle/tree, windowed, posted input and Frida game calls only)

Overlay: the stage source's 25 packages with style_mix swapped for 1.2.0, merged in 352 s; only the 5 files style_mix
writes changed (BUILDFAM, OccupantAttribs_Korea, CSAttrib_Korea, the two set pixel DATs). Merge report: civic looks
210, 211, 8084, 212, 215, 248 + 400000; 15 bases + 1500000; 15 bases + 2600000.

1. **The window per button** (Madison, North American city), opened with the city view's hotkey and, for Small Park,
   with a posted click on the real Parks button (`04`):
   - Police: `CIVDLG> entry 0: key 0x57E 0xD2 type 13130 lot 3x3 price 500 style Norteamericano`, entry 1 `0x61B52`
     (European), entry 2 `0x16E432` (Asian), `3 of 3 list row(s) renamed`. Rows "Norteamérica: Comisaría",
     "Europa: Comisaría", "Asia: Comisaría", each with its own picture (`01`, `02`).
   - School 3 entries (types 13010), Hospital 2 (`0x16E431`, `03`), Small Park 2 (`0x16E36D`, price 100),
     Marina 3 (`0x61B78`, `0x16E458`, price 3000). Same type, footprint and price as the original in every row.
   - First build wrote "<name> (<style>)": at 800x600 "Comisaría (Norteamericano)" lost its last letters (`02`). Rows
     now put a short region word first; they fit (`01`).
2. **Pick and place.** After OK the city view's tool is the stock building tool (SIMGEOM+0x29504) with the picked key,
   one-shot 0, and the cost label shows the look ("Aspecto 2 de 3: Europeo | §500", "Aspecto 2 de 2: Asiático |
   §100", `05`). Placed in Madison: European and Asian police, European and Asian school, Asian hospital, Asian small
   park (`06`). The 2-minute autosave (`tree\Cities\cs_madison_2.sc3`) read with `occupant_layer.py`:
   `400210` police (183,215), `1500210` police (179,208), `408084` school (185,206), `1508084` school (190,210),
   `1500209` hospital (187,222), all 3x3, `1500013` small park (183,211) 1x1; stored types 0x334a = 13130,
   0x32d2 = 13010, 0x33fe = 13310, 0x37e7 = 14311.
3. **Save and reload with the mods.** The European police save (`cs_madison_1.sc3`) loaded in a new game: drawn where
   it was (`15`), and the next autosave still holds `400210`. `cs_madison_2.sc3` loaded again in later runs, all
   six looks drawn.
4. **Without the mods.** `sc3dev run -Stock -City cs_madison_2.sc3` (no mods, sc3winonly only): the city loads, every
   look is the game's own building of the same kind at the same place: two North American police stations, two
   schools, the small park, the hospital (`07`). Process alive 60+ s, no fault.
5. **A European city** (Berlin, set e523f3fb): Police lists "Europa: Comisaría" (the base key, drawn European), then
   "Norteamérica: Comisaría" = `0x27AD12` (210 + 2600000), then Asia (`08`). The North American police placed in
   Berlin draws the stock North American art next to Berlin's European buildings (`09`, top left).
6. **Row off = stock.** `SC3RESIZE_CIVSTYLE=0`: `CIVSTYLE> off`, `CIVVAR> no civic variants ... not installed, the
   civic buttons are stock`; Police arms `0x57E 0xD2` with no window and the plain "§537" label; the placed looks
   still draw (`10`). The row on the mods page (`11`) sits in the left column, nothing overlaps (notes, city
   checkbox, Volver unchanged). Unticking it and OK wrote `[env] SC3RESIZE_CIVSTYLE=0` to `sc3mods.ini`
   (`MODTOGGLE> -SC3RESIZE_CIVSTYLE off at the next start`); the file was removed again.
7. **With imported looks too** (civdlg's test models, `bldimport.py build`): Police has 6 rows, the 3 styles then
   "Police blue / green / red" with their own names and "Aspecto importado" text (`12`); picking Police green armed
   `0xB1D10002 0x9471`, label "Aspecto 5 de 6: Police green" (`13`). School: 3 styles + "School blue" (`14`, final
   description wording). Esc closed with no tool.
8. **Cycle** (`SC3RESIZE_CIVDLG=0`): three Hospital presses armed `0xD1`, `0x16E431`, `0xD1` (stock, Asian, stock).
9. **Marina hook**: picking Europa logged `CIVVAR> button of base 0xF8: look 2 of 3, Europeo, key ... 0x00061B78`
   from the shore tool's constructor call 0x1000afc0.

## Fault seen (lab, not the mod)

One run died 1 s after a School pick: `VEH FAULT 0xC0000005 at 0x13CF0A1A (no module)`, `[esp]` another no-module
address, then only SC3U message-loop frames. `civmod_lab.py hotkey` runs the press inside a Frida DispatchMessageA
hook and the list window's modal loop runs inside it; the tool detached the moment the job returned (and after its
20 s timeout while a window was still open). With a wrapper that stays attached 4 s after the job (now in
`civmod_lab.py`), 19 presses over the next 5 runs, no fault. Every other run logged only the start-up `0xC0000096 at SC3U.exe+0x84122`.

## Not checked / open

- **Marina placed on a shore**: window, pick and the shore tool's key were checked; a placement needs a coastline
  and the Parks sub-flyout, which a posted click did not open (it built the Small Park window). Needs owner check.
- Fire, Museum, Baseball, Jail, College, Library, Big Park, Playground, Pond, Fountain: same code path, windows not
  opened in game (the merge report lists their copies).
- Asian city (Seoul): same logic as Berlin with the Asian set.
- Other 6 languages not seen in game (tables checked). The Spanish "Norteamérica: Parque Pequeño" still clips at
  800x600 (region visible, name cut).
- The three extra Small Park exemplars (0x2348, 0x2349, 0x234d) have Asian art but no button builds them: not offered.
- Release: stage/src still has style_mix 1.0.0; it needs `netpack.py uninstall style_mix` + `install
  re/tools/netmod/examples/style_mix` (1.2.0) there, as stylepick noted for 1.1.0. Without it the buttons stay as
  they are (no copies in the attrib cache = no style rows).

## Files

- Commit (from `dev/civicstyle/wt`): `re/harness/src/sc3resize_civic.c`, `re/harness/src/sc3resize.c`,
  `re/harness/lang/{de,en,es,fr,it,nl,sv}.txt`, `re/tools/netmod/netpack_stylesets.py`, `re/tools/netmod/netpack.py`
  (report line), `re/tools/netmod/netpack.schema.json`, `re/tools/netmod/stylemix_build.py`,
  `re/tools/netmod/examples/style_mix/manifest.json` (1.2.0), `re/tools/netmod/examples/style_mix/README.md`,
  `re/tools/civmod_lab.py`, `re/analysis/CIVIC_REWARD.md` (section 7).
  MAIN: `verify/civicstyle/RESULTS.md`, `re/sessions/STATUS_civicstyle.md`.
- Not committed: `verify/civicstyle/owner_shots/*.png` (game art), test saves in `dev/civicstyle/tree/Cities`
  (`cs_madison_1.sc3`, `cs_madison_2.sc3`), the bldimport test plugin in `dev/civicstyle/tree/Apps/PlugIn`.
