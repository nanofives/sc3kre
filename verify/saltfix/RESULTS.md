# saltfix: salt water only at sea, rivers and lakes fresh (child/saltfix, 2026-11-04)

Owner report: "what's the logic between salt water and regular water on big island maps? i see regular water in between
salt water, can we fix that?" Owner calls: water linked to the sea turns salt where it is wide, rivers and lakes stay
fresh. New terrain gets the rule by itself, an existing city only through a "Recalcular agua salada" button.

## Cause (confirmed, static + game-side)

SIMDIRT `FUN_100181d6`, the generator's salt pass (called by Generate `FUN_10017c2d`), is not a flood fill. For each map
edge in the generator's 4-bit sea mask, every row or column casts a straight ray inward and marks each vertex salt
(`FUN_100183eb`, bitmap gen+0x20), land included. A ray stops after `(water & 0xff) * N >> 8` cells or after 5 cells where
water < height - 1. Water behind a headland, an island or a shoal, or past the ray length, stays fresh. On Big One (1024)
the stock layer shows exactly that: straight fresh streaks and fresh bays inside the sea, and a salt fringe on land
(`owner_shots/existing_city_bigone_button.png`, left).

The flag the game keeps: SIMECO bit 0x40000000 of the pollution grid, one bit per 2x2 cells (`IsSaltWater` 0x10008d90,
`SetIsSaltWater` 0x10008ecd, interface vtable SIMECO 0x1001b984, shift 1 set by the ctor 0x10004379). It is saved in the
city: Big One after the button, autosaved and loaded again, read 454168 salt cells on load, 0 blocks changed by a second press.

## The fix (`re/harness/src/sc3resize_saltfix.c`, one block in sc3resize, `SC3RESIZE_SALTFIX=0` = stock)

Rule, R = ceil(0.6 * sqrt(map side)) = 10 / 14 / 20 cells at 256 / 512 / 1024, L = 2R:

- water cell: any corner under water (height <= water, the game's tile test SIMDIRT 0x100065f0)
- wide water: inside a (2R+1) x (2R+1) square that is all water (off the map counts as water)
- sea: flood from the map edge (wide water on the edge, or an edge run of 2R+1 water cells) through water, crossing at
  most L narrow cells in a row (wide water resets the count)
- salt: the sea, written through the game's own corner expansion over wet corners only. Land never gets the flag.

So the open sea, bays, straits between islands and lochs behind a short neck are salt. Lakes are never reached. Rivers:
generated rivers are carved `sqrt(N) * (water + 64) / 128` deep (SIMDIRT 0x100187da, banks +2 per vertex at 0x10018b57),
13-16 cells wide at 256, and flare to 30-40 cells where they meet the sea. Width alone cannot tell such an estuary from a
bay, so on new terrain the carve is recorded: Generate's `call 0x100187da` at SIMDIRT 0x10018151 is wrapped, and the land
vertices it puts under water are river. River cells are never wide, so a generated river turns salt for at most L cells
from the sea and stays fresh after that.

- New terrain: generator vtable SIMDIRT 0x10020be8 slot +0x28 (Apply, 0x10017683) rebuilds the salt bitmap from the
  generator's final grids, then runs the stock Apply. 0-47 ms.
- Existing city: "Activar mods" page (Preferencias > Opciones de mods > Activar mods), checkbox "Recalcular agua salada"
  under its own heading "Ahora, en esta ciudad (al aceptar, sin reiniciar)", shown only with a city open, applied on OK.
  Writes per 2x2 block, only the blocks that change. 156-312 ms on a 1024 map.
  Placement call: kept on page C with that heading, not on page B. Page B (Opciones de mods) has no free row (checked on
  a frame of it: every row is used down to the Volver / Idioma / OK bar), page C has room under its notes, and the
  heading says in so many words that this one acts now, unlike the "al reiniciar" note above it.
- "Agua salada solo en el mar" row in the Funciones list = `SC3RESIZE_SALTFIX`, off at the next start.
- `SC3RESIZE_SALTFIX_DUMP=1` writes `saltfix_<n>_before/after.bmp` beside sc3resize.log (the pictures here).
- 3 new text keys (`resize.mt_saltfix`, `resize.mt_city`, `resize.mt_saltcalc`), es/en extracted, fr/de/it/nl/sv
  machine-translated, `sc3lang.py check` clean (336 keys x 7).

Limit: a saved city has no record of its rivers, so the button sees shapes only. A river narrower than 2R+1 behaves as on
new terrain. An estuary wider than 2R+1 turns salt like a bay. A large lake that reaches the map edge on 2R+1 cells counts
as sea.

## Check (dev/saltfix tree, 800x600 windowed, posted input only, FRAMEDUMP)

| case | result | picture |
|---|---|---|
| Big One (saved 1024 city), button | salt cells 430116 -> 470884 read back, 20342 blocks changed, 312 ms. Sea, bays and the west loch salt, inland lakes fresh, no land fringe | `existing_city_bigone_button.png` |
| same, saved and loaded again | 454168 salt cells on load (earlier build), second press 0 blocks changed | log only |
| New City 256 (from Craterville) | stock rays 8912 salt cells -> 7380. River fresh except its mouth, sea salt, lakes fresh. River carve 3205 vertices | `new_terrain_256.png` |
| New City 512 (Enorme slider 512) | 28109 -> 27387. Same picture: coast pockets salt, river fresh | `new_terrain_512.png` |
| New City 1024 (Enorme slider 1024) | 55425 -> 65444. Thin sea strip along the edge salt, river fresh | `new_terrain_1024.png` |
| same spot in play | Big One, cell (463, 239) and the 60x60 cells around it: fresh in stock, salt after (3043 water cells, read from the dumps at the cell the query tool reported). Frame at the same camera before / after: sea pixels differ less than land pixels (mean 6.9 vs 11.0, frame noise), so the water looks the same. The query panel on that cell reads "Agua" before and "Agua salada" after | `water_art_unchanged.png`, `same_spot_query_before_after.png` |
| edge midpoints (SIMDIRT 0x1000f450 / 0x10018e24 read IsSaltWater at the 4 edge midpoints) | same value before and after on all 4 maps | log only |
| page C | heading + checkbox drawn under the notes, row "Agua salada solo en el mar" in Funciones | `mods_page_recalcular.png` |

Colours in the maps: navy salt water, light blue fresh water, red the salt flag on a land cell (the stock rays mark land,
after the button only the edge of a 2x2 block shows it), green land. Each map is the whole city, 1 pixel per cell.

## What the salt flag changes on SC3U

Every reader of the flag found in the export: city vt+0x16c then interface +0x50 (`IsSaltWater`), swept over all 51
functions that fetch that interface, plus SIMUTIL's copy of the interface at this+0x2c (stored by `FUN_1000d262`).

| effect | evidence |
|---|---|
| Water supply buildings, fresh side: a building of type 3 gets full output with fresh water on the ring 1 cell around it, the reduced output `DAT_1002856c` % (the `WaterPumpDistanceFactor` value) on the 2-cell ring, else 0 | `[CONFIRMED @ SIMUTIL 0x1000f771]` calls ring scan `FUN_1000f57d(..., 0)`; the scan tests water (terrain vt+0x54) and `IsSaltWater == wanted` at `0x1000f57d`. Same fresh test in `0x1000e0b5` |
| Water supply buildings, salt side: a building of type 5 needs salt water on the ring around a 3x3 footprint | `[CONFIRMED @ SIMUTIL 0x1000f771]` `FUN_1000f57d(x-1, y-1, x+3, y+3, 1)`; same in `0x1000e675` |
| Which buildings are types 3 and 5 | `[UNCERTAIN]` read from the footprints and the `WaterPumpCapa` / `DesaltPlantCapa` settings as pump (1x1, fresh) and desalination plant (3x3, salt). The type id to building mapping was not traced |
| Query panel title "Agua" / "Agua salada" | `[CONFIRMED @ SIMUI 0x10010c39]` picks text 0xc2 when `IsSaltWater` is 0; seen in game on cell (463, 239) |
| Edge midpoints (purpose not traced) | SIMDIRT `0x1000f450` (terrain vt+0x168) and `0x10018e24` read the 4 edge midpoints. Unchanged on all 4 maps here |
| Water art | not a reader: the SIMDIRT draw path reads eco +0x68, not +0x50 (`0x10013fab`, `0x1001461d`); frames show no change |
| Boats | `[UNCERTAIN]`: no +0x50 reader found in SIMSPR / SimTransit by this sweep. A reader that keeps the interface in a member other than SIMUTIL's would be missed |

So in play the button can change which pumps and desalination plants have water: a pump on a pocket that turns salt
loses it, a desalination plant there gains it. That is why existing cities only change on the button.

## Found on the way, not from this change

New City started from a loaded city crashes in SIMRCI 25-160 s after the terrain editor opens: SIMRCI+0x29CA5, +0x109BE,
+0xC31D (write to 0x6D69536C = ASCII "lSim" once). Same with `SC3RESIZE_SALTFIX=0` (A/B on Craterville, died 25 s after
accept), so it is not the salt pass. Logs: `work/logs/crash_craterville_saltfix_on.log`, `..._off.log`.

## Not checked / needs owner

- Pump / desalination output was not measured on a placed building (static above). After the button the code repeats
  the stock "salt on" cheat's last call (city vt+0x18c -> vt+0x4c, SIMDIRT 0x1000e520), purpose of that call `[UNCERTAIN]`.
- The look of estuaries on saved cities, and whether R = 0.6 * sqrt(side) matches what the owner calls "wide".
- Translations fr/de/it/nl/sv are machine-made.

`work/` holds every dump (PNG), earlier rule versions included: 3x3 window (`bigone_after.png`, `gen256_ba.png`), width
only (`bigone_after_v2`, `gen256b/c`, `gen512`, `gen1024`: rivers 13-16 wide went salt, then estuaries), flood without the
river record (`v3_bigone`, `final256/512`, `g1024a/b/c`: estuaries salt), final (`rv*`, `final_bigone`). `proto_rule.py`
is the offline prototype of the rule over a dump.
