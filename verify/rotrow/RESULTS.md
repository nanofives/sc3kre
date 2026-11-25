# rotrow: mods-page row for ROTPLACE (2026-11-25)

## Verdict

**Done.** The "Activar mods" page has a default-on row for sc3resize ROTPLACE (TAB rotates a square plopped building
while placing, main 4bdd79dc). es "Girar con TAB al colocar", en "TAB rotates when placing". Unchecking it and pressing
OK writes `[env] SC3RESIZE_ROTPLACE=0` into `sc3mods.ini`; checking it again deletes the key. Applied at the next start,
like the page's other rows.

## Change

- `re/harness/src/sc3resize.c` `k_mt_rows`: row `resize.mt_rotplace`, env `-SC3RESIZE_ROTPLACE` (a '-' row: default
  on, left column under "Simulacion y edificios", after "Zonas: edificios no cuadrados"). The code already reads
  `SC3RESIZE_ROTPLACE` after `sc3resize.ini [buildings] rotate`, so the env written by the loader wins.
- Layout: the left column's eighth row. Gap above the heading 6 -> 4, heading to first row 18 -> 16, rows stay 14 px:
  254 + 8 x 14 = 366, notes at 370, and the note / city lines below them 18/40/58 -> 16/32/48, so the SALTFIX city
  checkbox stays at local y 418 (the place measured clear of Volver in hwyspeed).
- `re/harness/lang/*.txt`: key `resize.mt_rotplace`. es/en by `sc3lang.py extract`; fr "Tourner avec TAB en placant"
  (with cedilla), de "Mit TAB beim Platzieren drehen", it "Ruota con TAB piazzando", nl "Draaien met TAB bij plaatsen",
  sv "Rotera med TAB vid placering" by `sc3lang.py merge` (machine translations, marked for review like the others).
  `sc3lang.py check`: 376 keys, 0 missing, 0 unknown, 0 format mismatches, 0 not in cp1252 in all 7 tables.

## In game (dev\rotrow\tree, Madison, windowed, posted clicks)

| step | result | picture (`verify/rotrow/owner_shots/`, not committed) |
|---|---|---|
| es page, row default on | 8 rows under "Simulacion y edificios", last "Girar con TAB al colocar"; notes, city heading and "Recalcular agua salada" clear of Volver, no overlap with the features column | `toggle_es.png` |
| uncheck + OK | log `MODTOGGLE> -SC3RESIZE_ROTPLACE off at the next start`, `sc3mods.ini` = `[env] SC3RESIZE_ROTPLACE=0` | `toggle_es_unchecked.png` |
| restart (SC3MODS_LANG=en) | log `ROTPLACE> off`; en page shows "TAB rotates when placing" unchecked, fits | `toggle_en_off.png` |
| check + OK, restart | log `MODTOGGLE> -SC3RESIZE_ROTPLACE on at the next start`, `[env]` empty, next start `ROTPLACE> on` | `toggle_en_on.png` |

TAB rotation itself is covered by verify/rotplace/RESULTS.md and the release smoke (verify/mods_release_1125).
