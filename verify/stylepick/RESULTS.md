# stylepick: the building style picks what NEW buildings grow, like SimCity 4 (2026-11-21)

Asked on Simtropolis: "choosing a building style doesn't change the appearance of existing buildings, but it does
affect what buildings get built". Verdict: **done and checked in game.** With the new default, Options > City
Properties no longer redraws the city: the style picked there (North American, European, Asian) decides which style new
lots grow, a new **"Mix all three styles"** box in the same window is today's style mix, each city saves its choice,
and a Turn mods on/off row brings the stock re-skin back.

## How the stock game does it (static evidence, `re/analysis/BUILDING_PICK.md` section 8)

- The in-game picker is Options > City Properties (menu item `0x1000900A`, command `0x855a2dc4`). On OK, SIMUI
  `0x10011bc5` calls `SetCityScheme(landscape, flora, building set, progress = mode 0)`. The New City window is the
  same dialog class in modes 1 to 3. [CONFIRMED @ SIMUI 0x10011bc5]
- SetCityScheme SIMINIT `0x10006589` re-skins only when the building set differs from `+0x50`: it unloads the old set,
  registers the new one and re-Inits every live building of its keys (`0x10006f69`). Same set = nothing redrawn.
  [CONFIRMED]
- Family weights can change while the game runs: `0x10006ec9` (Linux name UpdateDevelopers) drops every family
  resource and has the ZoneLayer re-read them, and SIMGEOM `0x10001250` parses each family again into its
  `{attrib, weight}` vector (`+0x20`, count `+0x1c`). [CONFIRMED, and measured: 31 more family parses per OK]
- A city saves `[building set, flora, landscape]` in `{0x0525A6B9, 0x4525A6E2, 1}` (SIMCITY `0x10004ccd` writes,
  SIMINIT `0x10009e1f` reads). [CONFIRMED]

## What was built

| Piece | What it does |
|---|---|
| sc3netmod STYLEPICK (`sc3netmod_stylepick.c`, switch `SC3NETMOD_STYLEPICK=0`) | scheme vt+0x18 hook: City Properties keeps the city's building set (no re-skin), a New City keeps set 0, a load keeps the saved set; the picked style P and the Mix flag M are kept apart. Family filter after `0x10001250` (call at SIMGEOM `0x10001170`): keeps the members whose art is the wanted style, removes the rest and lowers the count (the state a weight-0 line leaves, as STYLEMIX already ships); never empties a family. Save: P and M in a new record `{0x0525A6B9, 0x4525A6E2, 0x5354594C}` after the stock saver (call at SIMCITY `0x10004458`); load: read before the stock loader (call at SIMINIT `0x10008f9c`). Scheme vt+0x64 answers P to the dialog's constructor only, so the window shows the picked style. Exports `sc3netmod_stylepick_state` / `_pending_mix` for sc3resize. |
| sc3resize SPMIX (`sc3resize_stylepick.c`, switch `SC3RESIZE_SPMIX=0`) | "Mix all three styles" box under the Buildings icons of City Properties and New City (dialog messages `0x1005bb2e`); on OK it hands the box to sc3netmod before SetCityScheme runs. No box when sc3netmod or STYLEPICK is off. |
| Turn mods on/off row | "Style: new buildings only" (es "Estilo: solo edificios nuevos"), env `SC3NETMOD_STYLEPICK`, default on. Feature rows now 15 px apart (18 rows at 16 put the city "Recalcular agua salada" box under Volver, `sp13`). |
| style_mix 1.1.0 (`netpack_stylesets.py`, set `"00000000"`) | North American copies: the stock exemplar of every member a set re-skins, at id + 2600000, 141 buildings, 166 family lines, no new art (their frame tables are stock `CSAttrib*.IXF` records no set archive holds: 141 of 141 checked offline). Needed so a city saved with the European or Asian style (Moscow, Berlin, Seoul, most player cities made with a style) can grow North American buildings. With STYLEPICK off the filter drops them, so the mix keeps its old ratio. |
| Strings | `resize.mt_stylepick`, `resize.sp_mix` in all 7 tables (`sc3lang.py check` clean, 363 keys). de / fr / it / nl / sv are mine, for review. |

Which members grow (P = picked style, M = Mix box, S = the city's own building set):

| Member | Grows when |
|---|---|
| European copy (+400000) | M, or P = European |
| Asian copy (+1500000) | M, or P = Asian |
| base building | the North American look is wanted (M, P = North American, or P is a set with no copy of it) and S does not re-skin it |
| North American copy (+2600000) | the North American look is wanted and S re-skins the base building |

## Evidence (dev/stylepick tree, windowed, posted input and the game's own menu command only)

Arms ran at speed 4 with `simrun.ini [churn] anarchy_res=5000, anarchy_com=5000` (lots rebuild fast) and autosave every
120 s. Counts: `re/tools/netmod/stylepick_count.py <before> <after>`: "new" = a building that was not on that cell
with that key in the earlier save. "base, re-skinnable" = a base id a set re-skins, split by which set.

| Case | Save pair | New buildings | Standing buildings |
|---|---|---|---|
| Sacramento (set 0), picked European, Mix off | autosave 1 -> 2 | European 6,093, base 1,977, base re-skinnable by the Asian set only 46, Asian 0, North American copies 0 | 5,045 re-skinnable base buildings still stand with their base id; set 0 kept, so they still draw North American |
| same city, Mix ticked | autosave 3 -> 4 | North American (re-skinnable base) 2,324, European 2,196, Asian 1,959, base 1,305 | |
| Sacramento European save loaded in a new game | load -> autosave 1 | European 5,686, base 1,824, base Asian-only 54, Asian 0 | |
| Moscow (set European), picked North American, Mix off | autosave 1 -> 2 | North American copies 8,456, base 6,263, base Asian-only 456, European-re-skinnable base 0, European 0, Asian 0 | the city's set stays European (stock record), so Moscow's own buildings keep their European look |

1. **Picking a style does not redraw the city.** Sacramento, North American -> European, Mix off: the first frame after
   OK (`sp04`) shows the same blue-roof houses; the log has
   `SetCityScheme from City Properties ... asked set E523F3FB, skin 00000000 -> 00000000, style European` and no
   progress window. Moscow, European -> North American (`sp08`, before / after): the European buildings stay.
   The control with the row off (`sp11`): the same click redraws every house European behind the stock "Cambio de
   Conjunto de Edificios" progress window.
2. **New lots grow in the picked style** (table): with European picked no Asian copy and no North American copy grew;
   the 46 / 54 base buildings that did are ones only the Asian set re-skins, so they look North American, as in a
   stock European city. `sp05`: red-roof European houses growing among the old North American ones.
3. **Mix grows all three**, about a third each (2,324 / 2,196 / 1,959).
4. **The city remembers its choice.** Each save holds the record (`stylepick record: style e523f3fb, mix 0`), the
   stock record keeps set 0. Loaded in a fresh game: `load: the city has a saved style ... style European`, the dialog
   shows European with the box unticked (`sp07`), and it keeps growing European only. A city saved before this
   (no record) loads with its own set picked and Mix on, so it grows what it grew before (log
   `no saved style (style = the city's set, mix on)`).
5. **A European city can grow North American buildings**: Moscow's 8,456 new North American copies, none of the base
   buildings the European set re-skins. `sp09` / `sp10` show the result next to the river.
6. **Row off = stock.** `[env] SC3NETMOD_STYLEPICK=0`: log `stylepick: OFF ... family filter in (drops the North
   American copies only)`, no Mix box (`SPMIX> no box: sc3netmod has STYLEPICK off`), the picker re-skins (`sp11`).
   Ticking the row and OK: `MODTOGGLE> SC3NETMOD_STYLEPICK on at the next start`, key removed from the ini.
7. **New City**: the same box is in the New City window (`sp14`); OK with Asian picked and Mix off logged
   `SetCityScheme from New City ... asked set 6523F3D5, skin 00000000 -> 00000000, style Asian` and the new map
   opened.
8. **Stock game**: a save with the stylepick record loads in `sc3dev run -Stock` (the stock exe without mods), no
   fault.
9. Escape closes the dialog without a SetCityScheme call (no log line), so Cancel changes nothing.

## Not checked / open

- One crash, not reproduced: in one run, after opening Preferences > Opciones de mods > Activar mods, closing it with
  Escape twice and then New City > "No", the game died 3.5 ms after the New City window was built, read of address 0 at
  `GZGraphicD+0x18C7A` (FUN_10018c58, a surface Blt: `[this+4]` or the source surface is NULL), under the SIMUI
  window painter. The same sequence then ran 4 more times with the box (0 crashes) and once without it (0 crashes),
  and New City without Preferences twice with the box (0 crashes). Whether the box plays a part is [UNCERTAIN]: 1 in
  7 New City windows with the box, 0 in 2 without. The stack did not survive (the log is rewritten at each start).
- Growth inside a brand-new city (needs zoning, power, roads): the filter is the same code as in the measured cities.
- Asian picked in a running city, and switching back to North American in Sacramento (European and Mix were run, North
  American in Moscow).
- The window in the other 6 languages (Spanish drawn). The longest box caption is 25 characters ("Mélanger les trois
  styles", fr), the box is 200 px wide. The French row caption "Style : nouveaux bâtiments seuls" (32 characters) is the longest
  on the Turn mods on/off page and may not fit its 208 px. Check it, or shorten it.
- STYLEMIX off with STYLEPICK on: no copies are served at all (weight 0 in the file), so every style grows base
  buildings; by design, not run.
- The stage source (`stage/src`) still has style_mix 1.0.0: the release needs `netpack.py uninstall style_mix` then
  `install re/tools/netmod/examples/style_mix` there (about 45 min each on this PC, all 25 packages are re-merged).
  Without it, STYLEPICK still works, but a European or Asian city cannot grow North American art for the buildings its
  set re-skins (they grow as base ids, which draw in the city's set).

## Files

- Commit (from `dev/stylepick/wt`): `re/harness/src/sc3netmod_stylepick.c` (new), `re/harness/src/sc3netmod.c`
  (include + thread + header item 9), `re/harness/src/sc3resize_stylepick.c` (new), `re/harness/src/sc3resize.c`
  (include, install, env, row, 15 px rows), `re/harness/lang/{de,en,es,fr,it,nl,sv}.txt`,
  `re/tools/netmod/netpack_stylesets.py`, `re/tools/netmod/netpack.py` (no pixel DAT for the base set; growable report
  printed a list family with `%d` and crashed after every install with bat_slots, now `%s`),
  `re/tools/netmod/netpack.schema.json`, `re/tools/netmod/stylemix_build.py`,
  `re/tools/netmod/examples/style_mix/manifest.json` (1.1.0), `re/tools/netmod/examples/style_mix/README.md`,
  `re/tools/netmod/stylepick_count.py` (new), `re/analysis/BUILDING_PICK.md` (section 8).
  MAIN: `verify/stylepick/RESULTS.md`, `re/sessions/STATUS_stylepick.md`.
- Not committed: `verify/stylepick/owner_shots/sp01..sp14*.png` (game art), the test saves in `dev/stylepick/tree/Cities`.
