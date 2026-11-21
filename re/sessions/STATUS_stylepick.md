# STATUS stylepick (round 2026-11-21, SC4-like building style choice)

## goal
The game's own style choice (Options > City Properties) picks which style NEW growables use. Standing buildings keep
their look. "Mix all three styles" stays a choice. A city remembers its choice. A mods page row: on = SC4-like, off =
stock re-skin.

## verdict + deciding RVAs
DONE, checked in game (verify/stylepick/RESULTS.md, pictures in verify/stylepick/owner_shots/).
- Picker: SIMUI Execute 0x10011bc5 calls scheme vt+0x18 SetCityScheme(land, flora, set, mode == 0) on OK.
- SetCityScheme SIMINIT 0x10006589 re-skins only when the set differs from +0x50, so passing the current set = no
  re-skin. UpdateDevelopers 0x10006ec9 re-reads the families at run time. Family parse SIMGEOM 0x10001250 (called at
  0x10001170): vector +0x20, count +0x1c.
- Save SIMCITY 0x10004ccd (called at 0x10004458), load SIMINIT 0x10009e1f (called at 0x10008f9c).

## built
- sc3netmod STYLEPICK (default on, SC3NETMOD_STYLEPICK=0 = stock): no re-skin from City Properties, New City keeps set
  0, family filter by picked style + Mix flag, own save record {0x0525A6B9, 0x4525A6E2, 0x5354594C}, dialog shows the
  picked style, exports for sc3resize.
- sc3resize SPMIX (SC3RESIZE_SPMIX=0 off): "Mix all three styles" box in City Properties and New City.
- Turn mods on/off row "Style: new buildings only" (SC3NETMOD_STYLEPICK), feature rows 15 px.
- style_mix 1.1.0: North American copies (+2600000, 141 buildings, 166 family lines, no art) so a European / Asian
  city can grow North American buildings.
- 2 strings x 7 tables.

## proven game-side vs static only
Game side: no re-skin on pick (Sacramento, Moscow), new growth only in the picked style (counts), Mix grows all three,
save + reload keeps the choice, Moscow grows North American copies, row off = stock re-skin, the row writes / clears
the ini, New City logs skin 0 + picked style, a stylepick save loads in the stock game.
Static only: growth inside a brand-new city, Asian picked in a running city, the 6 other languages on screen.
Open: one crash (GZGraphicD+0x18C7A, NULL surface Blt) once in 7 New City windows with the box after a Preferences
visit, not reproduced in 4 more tries, 0 of 2 without the box: [UNCERTAIN] whether the box plays a part.

## blocked on
- (release) stage/src still has style_mix 1.0.0: `netpack.py uninstall style_mix` + `install
  re/tools/netmod/examples/style_mix` there (about 45 min each, all 25 packages re-merge). The dev tree
  dev/stylepick/tree has 1.1.0 installed (ledger + packs copied in from stage/src).

## files owned
From dev/stylepick/wt:
- re/harness/src/sc3netmod_stylepick.c (new, gitignored: needs git add -f), re/harness/src/sc3netmod.c
- re/harness/src/sc3resize_stylepick.c (new, gitignored: needs git add -f), re/harness/src/sc3resize.c
- re/harness/lang/de.txt en.txt es.txt fr.txt it.txt nl.txt sv.txt
- re/tools/netmod/netpack_stylesets.py, netpack.py, netpack.schema.json, stylemix_build.py,
  examples/style_mix/manifest.json, examples/style_mix/README.md, stylepick_count.py (new)
- re/analysis/BUILDING_PICK.md (section 8)
MAIN: verify/stylepick/RESULTS.md, re/sessions/STATUS_stylepick.md.
Not to commit: verify/stylepick/owner_shots/*.png (game art).

## game-harness need
None (dev tree only, posted input + the game's own menu command through np_drive cmd).

## asks of other sessions
- civicstyle (next stream): the civic list window is untouched. STYLEPICK only filters BUILDFAM families.
- Release: reinstall style_mix 1.1.0 in stage/src (above), and ship sc3netmod + sc3resize + the lang tables together
  (the box needs both DLLs).
