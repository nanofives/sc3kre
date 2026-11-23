# STATUS forumshots (round 2026-11-23b)

## goal
Every forum picture re-taken with the current converter, 8+ more Maxis SC4 comparisons, "Choose a look" + City
Properties fully in English, a style pick before/after that shows the difference. Not the Small Police Station sheets
(civlot).

## verdict
Done. Results: `verify/forumshots/RESULTS.md`.
- 29 sheets in `verify/sc4cmp/forum/` (02-29) + `extra/lee_avionics.jpg`, main's converter (baked_sharp, civic on
  SC4 lots after civlot's merge), 27 with in-city strips from this round's frames (no strip: Eyler Refining, Maxis
  Theatre). 17 new comparisons.
- English UI shots in `verify/forumshots/ui/` (5).
- `verify/forumshots/style_pick_before_after.jpg`: same camera, Sacramento, European picked with Mix off: 7,131 new
  European lots, 0 North American copies, 4,712 re-skinnable base buildings kept their base id (look unchanged).

## built
No code. Workspace `dev\forumshots\{wt,tree,inst}`, wt fast-forwarded to main 42df68e. Tree text `ENGLISH` ->
`ENGLISH_es`, `English-UK` copied as `ENGLISH`. bldimport plugin (ids 38000-38028) installed in the tree.
`inst\perf.ini` = shipped perf.ini with overlay=0.

## proven game-side vs static only
Game-side: every strip is a game frame dump (matched by FFT, kept by eye). Style pick counts from two saves.

## found (not fixed, not this stream)
- Crash: Sacramento, churn anarchy 5000, speed 4, 105 s after the City Properties pick:
  `RZ *** VEH FAULT *** code=0xC0000005 at STRTSIM.DLL+0x94DB (base 0x02F40000)`, `access=READ addr=0x00000000`,
  `eax=193143E0 ecx=00000000 edx=1990D488 ebx=000102B9 esi=1A581228 edi=00EC4160`, tid = main thread, stack
  STRTSIM+0x2D468, STRTSIM+0x12F75, SC3U.exe+0x2638B, +0xD0FA4, +0xC3F78, SIMSPR+0x1CB09, SIMSPR+0x42B07,
  sc3overscroll+0x1B6F, +0x2146, SC3U.exe+0x837DB, +0x75B2D. One occurrence.
- Choose a look, English 800x600: first row cut at "North America: Police Stat".
- compare_sheet subtitle: class 8900 has no label ("Growable building").

## blocked on
Nothing. BSC pack not available (Downloads: none, `\\mariano-server\Compartido`: access refused). Not needed for Maxis
lots.

## files owned
None in git. Local only: `verify/forumshots/**`, `verify/sc4cmp/forum/02..29*.jpg`, `extra/lee_avionics.jpg`,
`sheet_forumshots.json` (removed extra/city_hall, small_fire_station, mayors_house: now 15, 19, 13), this file.

## game-harness need
None now. No game running, claim released.

## asks of other sessions
None.
