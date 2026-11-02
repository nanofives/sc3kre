# Restoring an ageing building (child `restore`, 2026-11-02)

Owner, 2026-11-02: "en el menú de información de un edificio debería haber un botón para restaurar (con costo acorde)
el edificio en cuestión si tiene vida útil, luego agregar otro menú dentro de la sección de reunirse (botón al lado de
la cruz)". Owner calls: the button only for buildings the game ages; cost = build price x fraction of life used; refused
when funds are short. Evidence: `verify/restore/RESULTS.md`.

## 1. How the game ages a building

A building with a lifespan answers QueryInterface **0x43680ca9** (`IBuildingMortal`; the iOS sibling names it, 
`SimCity::IBuildingMortal`, iOS 0x001faea0). The slot layout is the same in both modules that implement it:

| slot | meaning | SIMUTIL (plants, water) | SIMECO incinerator |
|---|---|---|---|
| +0x00 | QueryInterface, accepts 0x43680ca9 | 0x10007834 (base), 0x10007e28 (coal plant) | 0x10002e37 |
| +0x0c / +0x10 | Set / Get MaxAge, months | 0x10009fbd / 0x10006b6f (obj +0x1c) | 0x100013fc / 0x10001408 (class global DAT_100200a4) |
| +0x14 / +0x18 | Set / Get DeclineAge | 0x10009fc7 / 0x10006b63 (obj +0x20) | 0x1000140e / 0x1000141a |
| +0x1c | GetAge | 0x100120a1 | 0x10001582 |
| +0x20 | IsAging: building state 1 and age >= DeclineAge | 0x10006d98 | 0x100015d9 |
| +0x24 / +0x28 | Kill / IsDefunct (byte) | 0x10011e2e / 0x10006b42 (obj +0x24) | 0x10001420 / 0x10012dec |

Vtables: SIMUTIL coal plant 0x10020c48 (GetAge sits in 16 SIMUTIL vtables), SIMECO 0x1001b160 and 0x1001b5d0
`[CONFIRMED, read from the PE]`.

**GetAge** = (year x 12 + month) of the city date (city vt+0x1e4 GetDate(&month, &day, &year)) minus the same of the
birthdate `[CONFIRMED @ SIMUTIL 0x100120a1, SIMECO 0x10001582]`. Days do not count.

**Birthdate** = a date object {vtable, Julian day number}: SIMUTIL obj +0x14 (number at +0x18), SIMECO incinerator
mortal +0x08 (number at +0x0c). Julian arithmetic: encode SIMUTIL 0x10016309, decode 0x10016432, base 0x1a431f.
Read and written through the **building interface** (QI 0xe0faadc7): vt+0x3c HasBirthdate, vt+0x40 GetBirthdate(date&)
(calls date vt+0x10 Set(day number)), **vt+0x44 SetBirthdate(const date&)** (reads date vt+0x68) `[CONFIRMED @ SIMUTIL
0x1000b4a7 -> 0x10006b86, SIMECO 0x100013c9 / 0x100013dc]`. The game itself uses vt+0x44 to give a dead plant's date to
its rubble (SIMUTIL 0x1000690c, BecomeDefunctDueToAge).

**MaxAge / DeclineAge** come from the ini files once per building: SC3PowerLayer.ini `MaxLifeSpan` / `DeclineAge` with
`PercentageVariationInLongevity=15` drawn per plant in the ctor (SIMUTIL 0x10006ba6; Berlin's coal plant: 939 months
from an ini 840), SC3Tune.ini for water treatment / incinerator / recycling, SC3WaterLayer.ini `WaterPumpLife=110` etc.
(years: the pumps read 1320 months in game).

**Expiry.** A plant whose age passes MaxAge becomes rubble (SIMUTIL vt+0x48 0x10007afb: age > MaxAge -> vt+0x70); the
incinerator at age >= MaxAge (SIMECO 0x1000234d). A plant's output falls linearly from DeclineAge to MaxAge
(SIMUTIL 0x100069fb) and is recomputed every update, so a new birthdate also gives the output back.

Measured in game (Berlin, 256x256): 229 buildings answer 0x43680ca9, 216 alive: coal / nuclear / solar plants, water
treatment, desalination plants and many water pumps. The query dialog's own "Edad (max) 28 años (78 años)" line matches
GetAge 341 / MaxAge 939.

## 2. Restore

- **Cost** = price x clamp(age / MaxAge, 0, 1), rounded half up. Price = budget vt+0x54(type id), the build price the building tool
  charges (SIMGEOM 0x100072f6; budget = city vt+0x15c, SIMMISC vtable 0x1003c550). Coal plant: price 5000, 341 of 939
  months used, cost 1815.
- **Funds** = budget vt+0x10. Refused when short. Paid with budget vt+0x14 (Withdraw, the slot the building tool's
  commit uses).
- **New birthdate** = the first day of the city's current month, so GetAge reads 0. The current year/month is derived
  from the old birthdate plus the game's own GetAge, so no date source of ours is involved. MaxAge and DeclineAge (with
  their per-building variation) are kept.
- A dead building (IsDefunct, the rubble left by an expired plant keeps its class and name) gets no button and no
  row. Measured: the output of an aged plant returns to its base on the game's next update.
- Saves: only the stock birthdate changes, so a save loads the same without the mod.

## 3. Where it lives

- `re/harness/src/sc3restore.c` -> `sc3restore.dll`: the mechanism, nothing patched. Exports `sc3restore_info`,
  `sc3restore_apply`, `sc3restore_apply_at(x0, z0, type, max_cost, ...)`, `sc3restore_apply_all(max_total, ...)`,
  `sc3restore_list`, `sc3restore_funds`. `SC3RESTORE=0`: every export refuses. Log `sc3restore.log`.
  The list scans every cell with the surface occupant manager (city vt+0x11c, GetOccupantAtCell vt+0x7c) and counts a
  building at the first cell of its footprint: 256x256 in 24 ms.
- `re/harness/src/sc3resize_restore.c`, #included by sc3resize.c (RESTORE block, `SC3RESIZE_RESTORE=0` = nothing added):
  1. Query dialog (handler SIMUI 0x1006338f, already detoured by QUERYID/RELOCATE/LANDFILL, so not a second DLL):
     "Restaurar $N" (the game font draws `$` as the simoleon sign). After a restore the dialog is closed and opened
     again on the building through the "?" tool's own Apply (SIMGEOM 0x1000b6b4, `__thiscall(tool, LONG *coord 8.8)`,
     ret 4, reads no tool field) so the game's own text shows the new age, with "Restaurado ($N)" on the button.
  2. Reunirse list page: detour on its message handler SIMUI FUN_100042f7, **`__thiscall` with five stack args,
     `ret 0x14` at 0x10004402** (Ghidra shows four; a four-arg detour crashed the game on the next Reunirse open).
     msg 0xa2bf8ace = build (FUN_10004405), msg 3 p3 1 = button click (id in p4), 0x22c05b3f = the page's periodic
     refresh (about every 5 s). "Vida útil" sits left of the close box. Its click turns the same window into the list
     (MODSPAGE style: the game's windows below the title bar are hidden, children and their children; the petition
     rows the game adds while the page is open come up visible and are hidden after each message to the page). 7 two-line
     rows a page, least life left first, "Restaurar $N" each, "Restaurar todos ($total)", "<" ">", "Volver".
     The list refreshes on every 0x22c05b3f, and a click whose price rose since it was drawn is refused with
     "El costo subió a $N: pulsá de nuevo" (the sim keeps running while Reunirse is open).

## 4. Traps found on the way

- FUN_100042f7's arity: see above. Check the `ret` of any handler before detouring it, the decompiler drops unused args.
- A thread timer (SetTimer with no window) set inside the query dialog's modal loop fired about 10 s late. Posted
  messages to the game window are dispatched at once (15 to 31 ms measured).
- `fd_set` is a winsock typedef pulled in by windows.h: do not name a function that in a mod source.
