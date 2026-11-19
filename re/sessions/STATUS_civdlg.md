# STATUS civdlg (round 2026-11-19k)

## goal
A civic button with imported looks opens a small list window in the game's look (original first, then the looks;
name, price, picture). A pick arms the stock tool with that key and closes it. Esc / close = no tool. A button with no
looks stays stock. Scales with the interface scale. Decide stock catalog window vs new SIMUI window with evidence.

## verdict
Done, game-side. The window IS the stock catalog dialog (the Rewards / Landmarks list, GZCOM class `0xe3091435`),
driven the way its own command does (SIMUI `0x10011919`), with our items added between SetMode and Init under a mode id
no advisor answers. No SIMUI patch. The press is caught at SIMGEOM's command factory handler slot (vtable
`0x100291f4` +0x18, dword `0x1002920c`): cancel returns no command (both callers test it), a pick runs the stock
handler and the existing `cv_pick` (SIMGEOM `0x1000b1a3`) builds that key.
Why reuse: look, building picture, Esc / close / OK, DLGSCALE scaling and window position all come from the stock
dialog; a new SIMUI window would rebuild all of them and a building preview no mod draws today.
Press-to-cycle: replaced. The "Activar mods" page has no free row, so it is only the off-switch `SC3RESIZE_CIVDLG=0`
/ `sc3resize.ini [buildings] civiclist=0`. The "Civicos: varios aspectos" row still turns the whole feature off.

Deciding evidence: `re/analysis/CIVIC_REWARD.md` section 6, `verify/civdlg/RESULTS.md`, `verify/civdlg/owner_shots/01-11`.

## built
- CIVDLG in `re/harness/src/sc3resize_civic.c` (`cd_dialog`, `cd_getcmd`, `cd_tick`, `cd_install`, `cv_pick` takes the
  pick), two lines in `sc3resize.c` (ini/env switch, `cd_tick()` in the frame heartbeat next to `sw_tick()`).
- 5 text keys in all 7 tables (`resize.cd_*`), `sc3lang.py check` clean.
- `make_testmodels.py --civdlg` (3 police looks, 1 fire, 1 school).

## proven game-side vs static only
Game-side: real menu button (Police, Fire, Hospital) and hotkey path; window at Normal and 200%; pictures of stock and
imported looks; each of the 4 police entries picked and placed; Esc, close box = no tool; hospital stock with no
window; save + reload (autosave read back with occupant_layer, then loaded: same 4 keys at the same cells); off-switch
gives the shipped cycle; all 11 mods on, only the start-up VEH FAULT `0xC0000096 at SC3U.exe+0x84122`.
Static only: the window position memory (the dialog's own prefs write, `0x100683ee`).
Not seen: the other 6 languages in game, double click on an entry.

## blocked on
Nothing.

## files owned (to commit, all in dev\civdlg\wt)
- `re/harness/src/sc3resize_civic.c`
- `re/harness/src/sc3resize.c`
- `re/harness/lang/{es,en,fr,de,it,nl,sv}.txt`
- `re/tools/bldimport/make_testmodels.py`
- `re/analysis/CIVIC_REWARD.md` (section 6)
- `verify/civdlg/RESULTS.md`
- this file (MAIN `re/sessions/STATUS_civdlg.md`)
Local only: `verify/civdlg/owner_shots/` (MAIN), lab scripts in `dev\civdlg\work\`.

## game-harness need
None. The tree keeps the civdlg test plugin (`bldimport.py restore --game dev\civdlg\tree` removes it) and
`tree\Cities\civdlg_saved.sc3`.

## asks of other sessions / orchestrator
- At release, the player text that still describes the cycle needs the new behaviour:
  - README.md line 76-78, suggested: "Civic looks and new rewards from the building importer: a civic button with
    looks opens a list of the original and your looks, with picture and price, and builds the one you pick; your
    rewards unlock at the population and year you set."
  - `docs/buildings/index.html` civic section (line 319, "Each press of that button then builds the next look ..."),
    suggested: "Pressing that button then opens a list: the stock building first, then your looks in the order of
    models.json, each with its picture and price. Pick one and place it with the usual tool."
  - The comment bldimport writes at the top of `bldimport_civic.ini` (and bldweb.js `civicIni`) still says "each
    press ... builds the next look". Data comment only, not changed here so the page's byte identity is untouched.
- Open (not asked): the model's own description line is not shown in the window (a fixed line is).
